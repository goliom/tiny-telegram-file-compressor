"""Recursively extract ZIP/RAR/7z archives, optionally deleting successful sources."""
import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from archive_layout import is_link, named_payload, publish_extraction, remove_empty_wrappers
from archive_tools import seven_zip, subprocess_options
from sevenzip_runner import run_sevenzip

JOURNAL = ".decompression-tout.json"


@dataclass
class Archive:
    first: Path
    volumes: list
    destination: Path
    error: str = ""
    merge: bool = False


def discover(root):
    """Group volumes per directory; never follow links or partial extractions."""
    archives = []
    def scan_error(error):
        raise error  # Do not silently claim to process an inaccessible subtree.
    for directory, folders, names in os.walk(root, followlinks=False, onerror=scan_error):
        parent = Path(directory)
        folders[:] = sorted(folder for folder in folders if not is_link(parent / folder)
                            and ".extraction-en-cours" not in folder and ".doublon-en-cours-" not in folder
                            and not folder.endswith(".compression-en-cours"))
        groups = {}
        for name in sorted(names):
            path = parent / name
            if is_link(path):
                continue
            match = re.fullmatch(r"(.+\.(?:7z|zip))\.(\d{3,})", name, re.I)
            if match:
                base, index = match[1], int(match[2])
                kind, output, start = "split", str(Path(base).with_suffix("")), 1
            elif match := re.fullmatch(r"(.+)\.part(\d+)\.rar", name, re.I):
                base, index = match[1], int(match[2])
                kind, output, start = "rar-part", base, 1
            elif match := re.fullmatch(r"(.+)\.r(\d{2,3})", name, re.I):
                base, index = match[1], int(match[2]) + 1
                kind, output, start = "rar", base, 0
            elif match := re.fullmatch(r"(.+)\.z(\d{2,3})", name, re.I):
                base, index = match[1], int(match[2])
                kind, output, start = "zip", base, 0
            elif path.suffix.lower() in {".zip", ".rar", ".7z"}:
                base, index = path.stem, 0
                kind, output, start = path.suffix.lower()[1:], base, 0
            else:
                continue
            key = (kind, base.casefold())
            group = groups.setdefault(key, {"parts": {}, "output": output, "start": start, "duplicate": False})
            if index in group["parts"]:
                group["duplicate"] = True
            group["parts"][index] = path
        for group in groups.values():
            parts, start = group["parts"], group["start"]
            ordered = [parts[index] for index in sorted(parts)]
            error = ""
            if group["duplicate"]:
                error = "Plusieurs volumes portent le même numéro"
            elif start not in parts or min(parts) != start or len(parts) != max(parts) - start + 1:
                error = "Archive en plusieurs parties incomplète : premier volume ou partie intermédiaire manquante"
            merge = parent.name.casefold() == group["output"].casefold()
            destination = parent if merge else parent / group["output"]
            archives.append(Archive(parts.get(start, ordered[0]), ordered, destination, error, merge))
    return archives


def fingerprint(path):
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def archive_weight(archive):
    try:
        return max(1, sum(path.stat().st_size for path in archive.volumes))
    except OSError:
        return None


def inside(path, root):
    if is_link(path) or not path.resolve().is_relative_to(root):
        raise RuntimeError(f"Chemin hors du dossier choisi ou lien refusé : {path}")


def save_journal(root, entries):
    target = root / JOURNAL
    temporary = root / (JOURNAL + ".tmp")
    if is_link(target) or is_link(temporary):
        raise RuntimeError("Journal lié refusé")
    temporary.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def remaining_sources(root, record):
    """Validate the extraction and all remaining volumes without deleting anything."""
    destination = root / record["output"]
    inside(destination, root)
    if not destination.is_dir():
        raise RuntimeError(f"Dossier extrait introuvable : {destination}")
    remaining = []
    for relative, expected in record["volumes"].items():
        path = root / relative
        inside(path, root)
        if path.exists():
            if fingerprint(path) != expected:
                raise RuntimeError(f"Archive modifiée depuis l'extraction, conservée : {path}")
            remaining.append(path)
    return remaining


def delete_sources(root, record):
    """Validate all remaining volumes before deleting any of them."""
    for path in remaining_sources(root, record):
        path.unlink()


def publish_into_parent(staging, destination, root):
    """Avoid Model/Model when Model.zip already lives inside Model; never overwrite."""
    payload = named_payload(staging, destination.name)
    children = list(payload.iterdir())
    for child in children:
        inside(child, root)
        target = destination / child.name
        inside(target, root)
        if target.exists():
            raise FileExistsError(f"Fichier ou dossier déjà présent, aucun écrasement : {target}")
    moved = []
    try:
        for child in children:
            target = destination / child.name
            if target.exists() or is_link(target):
                raise FileExistsError(f"Fichier ou dossier déjà présent, aucun écrasement : {target}")
            inside(child, root)
            inside(target, root)
            child.rename(target)
            moved.append((child, target))
    except Exception:
        for child, target in reversed(moved):
            inside(child, root)
            inside(target, root)
            target.rename(child)
        raise
    remove_empty_wrappers(staging, payload)


def extract_one(archive, root, executable, journal, delete_archives=True, on_progress=None):
    if archive.error:
        raise RuntimeError(archive.error)
    key = str(archive.first.relative_to(root))
    for path in [archive.destination, *archive.volumes]:
        inside(path, root)
    snapshot = {str(path.relative_to(root)): fingerprint(path) for path in archive.volumes}
    previous = journal.get(key)
    if previous and previous.get("state") in {"extracted", "kept"}:
        if delete_archives:
            delete_sources(root, previous)
        else:
            remaining_sources(root, previous)
        previous["state"] = "complete" if delete_archives else "kept"
        save_journal(root, journal)
        return
    if archive.destination.exists() and not archive.merge:
        raise RuntimeError(f"Dossier cible déjà présent, aucun écrasement : {archive.destination}")
    staging = (archive.first.parent / (archive.first.name + ".extraction-en-cours") if archive.merge
               else archive.destination.with_name(archive.destination.name + ".extraction-en-cours"))
    inside(staging, root)
    if staging.exists():
        raise RuntimeError(f"Extraction incomplète conservée : {staging}. Vérifiez et déplacez ce dossier avant de réessayer.")
    if len(archive.volumes) > 1:
        print("Lecture des en-têtes du jeu de volumes :", archive.first, flush=True)
        listing = subprocess.run([executable, "l", "-slt", "-sccUTF-8", str(archive.first)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 encoding="utf-8", errors="replace", timeout=60, check=True, **subprocess_options())
        header = listing.stdout.split("----------", 1)[0]
        counts = [int(value) for value in re.findall(r"^Volumes = (\d+)\s*$", header, re.M)]
        if not counts or max(counts) != len(archive.volumes):
            raise RuntimeError("Le nombre de volumes reconnu par 7-Zip ne correspond pas aux fichiers regroupés. Jeu conservé pour contrôle manuel.")
    staging.mkdir()
    run_sevenzip([executable, "x", "-y", f"-o{staging}", str(archive.first)],
                 f"Extraction : {archive.first} ({len(archive.volumes)} volume(s))", on_progress=on_progress)
    if not any(staging.iterdir()):
        raise RuntimeError("Archive vide après extraction, source conservée")
    if any(fingerprint(root / relative) != signature for relative, signature in snapshot.items()):
        raise RuntimeError("Une archive a changé pendant l'extraction : sources et extraction provisoire conservées")
    # Both resolved absolute paths must remain within the selected tree before the move.
    inside(staging, root)
    inside(archive.destination, root)
    if archive.merge:
        publish_into_parent(staging, archive.destination, root)
    else:
        publish_extraction(staging, archive.destination)
    record = {"state": "extracted" if delete_archives else "kept",
              "output": str(archive.destination.relative_to(root)), "volumes": snapshot}
    journal[key] = record
    save_journal(root, journal)  # Durable success record BEFORE any source deletion.
    if delete_archives:
        delete_sources(root, record)
        record["state"] = "complete"
        save_journal(root, journal)


def process(root, executable, delete_archives=True, on_event=None, stop_event=None):
    def emit(kind, **values):
        if on_event:
            on_event(kind, **values)

    def stopped():
        return stop_event is not None and stop_event.is_set()

    root = root.resolve()
    emit('scan')
    journal_path = root / JOURNAL
    inside(journal_path, root)
    journal = json.loads(journal_path.read_text(encoding="utf-8")) if journal_path.exists() else {}
    errors, completed, reused, processed, total, attempted = [], 0, 0, 0, 0, set()
    # Recover a stopped source-cleanup, even if the first volume was already deleted.
    for key, record in journal.items():
        if stopped():
            break
        if record.get("state") in {"extracted", "kept"}:
            total += 1
            emit('weights', weights={key: 0})  # Cleanup does not measure decompression throughput.
            emit('current', name=key, index=processed + 1, total=total)
            try:
                if delete_archives:
                    delete_sources(root, record)
                    record["state"] = "complete"
                    save_journal(root, journal)
                else:
                    remaining_sources(root, record)
                    if record["state"] != "kept":
                        record["state"] = "kept"
                        save_journal(root, journal)
                reused += 1
                emit('archive_done', name=key, status='deleted' if delete_archives else 'reused',
                     completed=processed + 1, total=total)
            except Exception as exc:
                errors.append(f"Reprise {key} : {exc}")
                emit('archive_done', name=key, status='error', error=str(exc), completed=processed + 1, total=total)
            processed += 1
            attempted.update(str(root / name) for name in record["volumes"])
    while not stopped():
        emit('scan')
        archives = [archive for archive in discover(root) if str(archive.first) not in attempted]
        if not archives:
            break
        total += len(archives)
        emit('weights', weights={str(archive.first.relative_to(root)): archive_weight(archive) for archive in archives})
        for archive in archives:
            if stopped():
                break
            attempted.add(str(archive.first))
            name = str(archive.first.relative_to(root))
            emit('current', name=name, index=processed + 1, total=total)
            try:
                extract_one(archive, root, executable, journal, delete_archives=delete_archives,
                            on_progress=(lambda percent: emit('percent', percent=percent)) if on_event else None)
                completed += 1
                print("OK, archive(s) " + ("supprimée(s) :" if delete_archives else "conservée(s) :"), archive.first, flush=True)
                emit('archive_done', name=name, status='deleted' if delete_archives else 'kept',
                     completed=processed + 1, total=total)
            except Exception as exc:
                message = f"{archive.first} : {exc}"
                errors.append(message)
                print("ERREUR, sources restantes conservées :", message, flush=True)
                emit('archive_done', name=name, status='error', error=str(exc), completed=processed + 1, total=total)
            processed += 1
        # Rescan to find archives contained within newly extracted folders.
    if errors:
        (root / "decompression-erreurs.txt").write_text("\n".join(errors), encoding="utf-8")
    print(f"Terminé : {completed} archive(s) extraite(s), {len(errors)} erreur(s).", flush=True)
    emit('finished', completed=completed, errors=len(errors), reused=reused, stopped=stopped())
    return 1 if errors else 0


def process_locked(root, executable, **options):
    """Use the same Windows lock for the GUI and standalone launcher."""
    import msvcrt
    root = Path(root).resolve()
    lock_path = root / ".decompression-tout.lock"
    inside(lock_path, root)
    with lock_path.open("a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("Un autre exemplaire de cet outil traite déjà ce dossier") from error
        try:
            return process(root, executable, **options)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def main():
    parser = argparse.ArgumentParser(description="Décompresser récursivement ZIP, RAR, 7z et leurs volumes, puis supprimer les sources réussies.")
    parser.add_argument("dossier", nargs="?")
    parser.add_argument("--choisir", action="store_true", help="Choisir le dossier dans une fenêtre Windows")
    parser.add_argument("--apercu", action="store_true", help="Afficher les archives sans rien modifier")
    parser.add_argument("--appliquer", action="store_true", help="Démarrer sans la confirmation interactive")
    parser.add_argument("--garder-archives", action="store_true", help="Conserver les archives après extraction réussie")
    args = parser.parse_args()
    selected = args.dossier
    if args.choisir or not selected:
        import tkinter as tk
        from tkinter.filedialog import askdirectory
        window = tk.Tk()
        window.withdraw()
        selected = askdirectory(title="Choisir le dossier à décompresser (sous-dossiers inclus)", mustexist=True)
        window.destroy()
        if not selected:
            return 0
    root = Path(selected).expanduser().resolve()
    if not root.is_dir():
        parser.error("Dossier introuvable")
    executable = seven_zip()
    archives = discover(root)
    print("Dossier choisi :", root)
    for archive in archives:
        print(f" - {archive.first.relative_to(root)} -> {archive.destination.name} ({len(archive.volumes)} volume(s))" +
              (f" [ERREUR : {archive.error}]" if archive.error else ""))
    print(f"{len(archives)} archive(s) détectée(s). Les archives contenues dans les extractions seront également traitées.")
    if args.apercu:
        print("Aperçu uniquement : aucune modification.")
        return 0
    if not archives and not (root / JOURNAL).exists():
        return 0
    action = "conserver" if args.garder_archives else "supprimer"
    if not args.appliquer and input(f"Extraire puis {action} les archives réussies ? Tapez oui pour démarrer : ").strip().lower() != "oui":
        return 0
    # A single extraction process per selected root.
    return process_locked(root, executable, delete_archives=not args.garder_archives)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nArrêt demandé. Archives restantes et extraction provisoire conservées.")

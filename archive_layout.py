"""Remove only sole, identically named directory wrappers; preserve all other layouts."""
import uuid
from pathlib import Path


def is_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def named_payload(root, name):
    root = Path(root)
    if is_link(root):
        raise ValueError(f"Dossier lié refusé : {root}")
    current = root
    while True:
        children = list(current.iterdir())
        if len(children) != 1:
            return current
        child = children[0]
        if not child.is_dir() or is_link(child) or child.name.casefold() != name.casefold():
            return current
        if not child.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Dossier hors du périmètre : {child}")
        current = child


def remove_empty_wrappers(root, payload_parent):
    current = payload_parent
    while True:
        current.rmdir()  # Never delete recursively; refuse any unexpected content.
        if current == root:
            break
        current = current.parent


def publish_extraction(staging, destination):
    payload = named_payload(staging, destination.name)
    parent = payload.parent
    payload.rename(destination)
    if payload != staging:
        remove_empty_wrappers(staging, parent)


def flatten_existing(folder, boundary):
    folder, boundary = Path(folder).absolute(), Path(boundary).resolve()
    if not folder.resolve().is_relative_to(boundary) or folder == boundary:
        raise ValueError("Le dossier cible doit rester dans le périmètre choisi")
    payload = named_payload(folder, folder.name)
    if payload == folder:
        return False
    backup = folder.with_name(folder.name + ".doublon-en-cours-" + uuid.uuid4().hex)
    # Validate the absolute source and target of both directory renames.
    if not backup.resolve().is_relative_to(boundary):
        raise ValueError("Dossier temporaire hors du périmètre")
    relative = payload.relative_to(folder)
    folder.rename(backup)
    moved_payload = backup / relative
    try:
        if not moved_payload.resolve().is_relative_to(backup.resolve()):
            raise ValueError("Contenu hors du dossier temporaire")
        moved_payload.rename(folder)
    except Exception:
        if not folder.exists():
            backup.rename(folder)
        raise
    remove_empty_wrappers(backup, moved_payload.parent)
    return True

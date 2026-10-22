# Code signing policy

## Current status

We are preparing an application to the [SignPath Foundation](https://signpath.org/) open-source signing program. No acceptance or sponsorship has been granted. Current Windows releases are unsigned.

If accepted, signed releases will carry the acknowledgement: "Free code signing provided by SignPath.io, certificate by SignPath Foundation". This statement does not describe current releases.

## Responsibilities and approval

- Maintainer, author, reviewer and proposed signing approver: [goliom](https://github.com/goliom).
- Signing access will require multi-factor authentication for both GitHub and SignPath.
- Each signing request will require explicit approval by the maintainer after review of its source revision, build results and release files.
- External contributions must be reviewed before inclusion in a signed release.

## Build provenance

The public [Windows release workflow](.github/workflows/publish-release.yml) builds the executable from the exact source commit on GitHub Actions, runs tests and exercises the compiled application. Release files include `BUILDINFO.json` and `SHA256SUMS.txt`.

Signing is not currently configured. If approved, it will be inserted after successful build verification and before final packaging, checksum generation and publication. Only this project's own release artifacts will be submitted for signing.

Python and Tcl/Tk runtimes and the PyInstaller bootloader are included in the executable under their own licenses. 7-Zip is installed separately. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Privacy

The application processes files locally. See the [privacy policy](PRIVACY.md).

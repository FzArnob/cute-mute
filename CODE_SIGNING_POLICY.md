# Code signing policy

CuteMute's released binaries are signed. This document says who may sign, what
gets signed, and how you can check any of it yourself — it exists both because
[SignPath Foundation](https://signpath.org/) requires projects it sponsors to
publish one, and because a signature nobody can interrogate is not worth much.

## Free code signing provided by SignPath.io

Authenticode certificate by [SignPath Foundation](https://signpath.org/), free
code signing for open-source projects, with signing performed by
[SignPath.io](https://signpath.io/). The private key is generated and held in a
hardware security module operated by SignPath; nobody on this project has a copy
of it, and no key material exists in this repository, in any repository secret,
or on any maintainer's machine.

Because the certificate is issued to *SignPath Foundation*, that — rather than
`Fz's Lab` — is the publisher name Windows displays. The project's own identity
stays in the file's version resource, which the Properties dialog shows on the
Details tab.

## Roles

This is a single-maintainer project, and pretending otherwise in a security
document would be worse than saying so plainly.

| Role | Who | What they may do |
| --- | --- | --- |
| Author | Md. Farhan Zaman ([@FzArnob](https://github.com/FzArnob)), plus anyone whose pull request is merged | write and modify code |
| Reviewer | Md. Farhan Zaman | review every external contribution before it is merged |
| Approver | Md. Farhan Zaman | approve a signing request for a release |

All accounts with write access to the repository, and to the SignPath
organisation, have multi-factor authentication enabled.

External contributions are reviewed before merge. No contribution is signed
without having been read.

## What is signed, and what is not

Only `CuteMute.exe`, built from the source in this repository by
[`.github/workflows/release.yml`](.github/workflows/release.yml), on a
GitHub-hosted Windows runner, from a tagged commit.

- Nothing is signed that was built anywhere else — not on a maintainer's
  machine, not from a branch, not from a local working tree.
- No third-party or upstream binary is signed. CuteMute has no third-party
  dependencies to bundle; it is Python's standard library and direct Win32 and
  COM calls. The only foreign code in the exe is the PyInstaller bootloader and
  the CPython runtime, neither of which is signed by this project.
- Every signing request requires manual approval by the Approver above.

Each build carries a version resource generated from
[`cutemute/__init__.py`](cutemute/__init__.py) by
[`tools/make_version.py`](tools/make_version.py), so product name, version,
publisher, description and copyright are always present and always agree with
the tag. The release workflow fails the build if the tag and `__version__`
disagree, or if the version resource is missing from the finished exe.

## Verifying a release, without trusting this page

Two independent signatures, checkable separately.

**Authenticode** — what Windows reads. Right-click the exe → Properties →
Digital Signatures, or:

```powershell
Get-AuthenticodeSignature .\CuteMute.exe | Format-List Status, SignerCertificate
```

**Sigstore** — proves which workflow run produced the file, which Authenticode
does not tell you. There is no key here either; the signature is bound to the
workflow's own identity and recorded in a public transparency log:

```powershell
python -m pip install sigstore

python -m sigstore verify github CuteMute.exe `
  --bundle CuteMute.exe.sigstore.json `
  --cert-identity "https://github.com/FzArnob/cute-mute/.github/workflows/release.yml@refs/tags/v1.0.0" `
  --repository FzArnob/cute-mute
```

Swap the tag for the version you have; each release page carries the exact
command. The two answer different questions — *is this from a real publisher*
and *is this the artefact that this build produced* — and a release should pass
both.

## Privacy

CuteMute makes no network connections of any kind: no telemetry, no update
check, no crash reporting. See [PRIVACY.md](PRIVACY.md).

Signing itself is not anonymous, and should not be: the Sigstore transparency
log is public and permanent, and each release's log entry records the workflow
identity that signed it. That is the point of it. No personal email address is
published by this process, because the signer is a workflow, not a person.

## Reporting a problem

Signing or verification problems, and anything else with security
consequences: see [SECURITY.md](SECURITY.md). A release that fails verification
is the most interesting bug report this project can receive — please send it.

# Security

## What CuteMute touches

Worth knowing before you run a program that watches your keyboard:

- A **`WH_KEYBOARD_LL` hook**, so it sees every keystroke on the machine. It
  compares each one against the configured hotkey and drops it. Nothing is
  logged, buffered, or written anywhere — [`cutemute/hotkey.py`](cutemute/hotkey.py)
  is short on purpose, so this is checkable rather than merely promised.
- **Core Audio**, to set and clear the mute flag on capture devices. It does not
  open an audio stream, so it cannot record.
- Three **per-user registry and shortcut entries** on first run, listed in the
  README, all removable with `CuteMute.exe --uninstall`.
- **No network access, of any kind.** No telemetry, no update check, no crash
  reporting. CuteMute makes no outbound connections.

It needs no administrator rights, and asking for them changes only one thing:
a low-level hook cannot see keystrokes sent to an elevated window unless the
hook's own process is elevated too.

## Verifying a release

Releases are built and signed by
[`.github/workflows/release.yml`](.github/workflows/release.yml) on a GitHub
runner, using Sigstore keyless signing. No signing key exists — not in a
repository secret, not on a maintainer's machine — so there is none to leak.

The verification commands are in
[the README](README.md#verify-the-download). Please verify before running, and
please tell me if verification fails: that is the interesting case.

Note that Sigstore is not Authenticode. Windows SmartScreen will still prompt on
a fresh download, because the exe carries no Authenticode certificate. That is
expected and documented; it is not evidence of tampering.

## Reporting a vulnerability

Report privately through GitHub's
[**Security → Report a vulnerability**](https://github.com/FzArnob/cute-mute/security/advisories/new)
form, which opens a private advisory. Please do not open a public issue for
anything exploitable.

Useful in a report: the CuteMute version (`--version`, or the exe's Properties
dialog), your Windows build, and what an attacker gets out of it. A proof of
concept helps and does not have to be tidy.

This is a single-maintainer hobby project, so expect a first reply in days
rather than hours. Only the latest release is supported; fixes go into a new
release rather than into patches for old ones.

## Scope

In scope: anything that lets other software read keystrokes through CuteMute,
escalate privileges via its registry or shortcut entries, subvert its settings
file to run code, or defeat the release signing described above.

Out of scope: the SmartScreen prompt on unsigned downloads, antivirus false
positives on PyInstaller builds, and the documented limits in the README — a
fullscreen exclusive app drawing over the badge, and the hook not seeing
keystrokes destined for elevated windows.

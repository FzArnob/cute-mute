# Privacy policy

CuteMute collects nothing, sends nothing, and has no way to do either.

## No network access

CuteMute makes no outbound connections of any kind. No telemetry, no analytics,
no update check, no crash reporting, no licence check, no "anonymous usage
statistics". It contains no HTTP client and opens no socket. You can confirm
that from the source, and you can confirm it from outside with any firewall or
with Resource Monitor.

This is not a policy decision that could quietly be reversed in a later
version — it is simply what the program is. Any release that changed it would
have to change this file too, and the version that did so would be visible in
the commit history.

## What it stores, and where

One file, on your machine only:

```
%APPDATA%\CuteMute\config.json
```

It holds your settings — the hotkey, badge size and position, opacity, and the
handful of switches in the settings window. Nothing else. No identifiers, no
history of what you muted or when, no keystrokes.

Three per-user entries are written on first run so Windows can find the program:
a Start menu shortcut, an `App Paths` key for Win+R, and an installed-apps
entry. They contain the path to the exe, its name, its version and its
publisher. All three are removed by `CuteMute.exe --uninstall`, along with the
run-at-login entry and the settings file above.

## Keystrokes

CuteMute installs a low-level keyboard hook, which is how a mute key can work
while another application has focus. It has to see keystrokes to do that, so it
is worth being exact about what happens to them.

Each keystroke is compared against the configured hotkey and then discarded.
Nothing is stored, buffered, logged, aggregated, or transmitted — there is
nowhere for it to go, since the program has no network access and writes only
the settings file described above. The comparison happens in
[`cutemute/hotkey.py`](cutemute/hotkey.py), which is deliberately short so that
this claim is checkable rather than merely asserted.

## Microphone

CuteMute sets and clears the mute flag on your capture devices through Core
Audio. It never opens an audio stream, so it cannot record, and there is no code
in it that could.

## The website

[fzarnob.github.io/cute-mute](https://fzarnob.github.io/cute-mute/) is a single
static HTML file with no third-party scripts, no analytics, no cookies, and no
embedded fonts or assets from other hosts. It is served by GitHub Pages, and
GitHub may log requests to it as described in
[GitHub's privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).
Downloads come from GitHub Releases, which GitHub also logs; that is the source
of the download counter on the README.

## Releases

Release signing writes a record to Sigstore's public transparency log. Those
entries are permanent, public, and identify the GitHub Actions workflow that
signed the release — not a person, and not an email address. See
[CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

## Questions

Open an issue at
[github.com/FzArnob/cute-mute/issues](https://github.com/FzArnob/cute-mute/issues).
If you find something in the code that contradicts any of the above, that is a
bug and a security issue — please report it as described in
[SECURITY.md](SECURITY.md).

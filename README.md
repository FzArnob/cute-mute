<p align="center">
  <img src="docs/assets/mark-muted.svg" width="104" height="104" alt="">
</p>

<h1 align="center">CuteMute</h1>

<p align="center"><em>One key to mute your microphone.</em></p>

<p align="center">
  <a href="https://fzarnob.github.io/cute-mute/"><b>Website</b></a> &nbsp;·&nbsp;
  <a href="https://github.com/FzArnob/cute-mute/releases/latest"><b>Download</b></a> &nbsp;·&nbsp;
  <a href="#verify-the-download"><b>Verify</b></a>
</p>

<p align="center">
  <a href="https://github.com/FzArnob/cute-mute/releases/latest"><img alt="latest release" src="https://img.shields.io/github/v/release/FzArnob/cute-mute?style=flat-square&color=2f7ce8&label=release"></a>
  <a href="https://github.com/FzArnob/cute-mute/actions/workflows/build.yml"><img alt="build" src="https://img.shields.io/github/actions/workflow/status/FzArnob/cute-mute/build.yml?branch=main&style=flat-square&label=build"></a>
  <a href="#verify-the-download"><img alt="signed with Sigstore" src="https://img.shields.io/badge/signed-Sigstore-2f7ce8?style=flat-square"></a>
  <a href="https://github.com/FzArnob/cute-mute/releases"><img alt="downloads" src="https://img.shields.io/github/downloads/FzArnob/cute-mute/total?style=flat-square&color=8b8b94&label=downloads"></a>
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/github/license/FzArnob/cute-mute?style=flat-square&color=8b8b94"></a>
</p>

One keypress mutes your microphone. While it is muted, a small badge sits in the
corner of the screen on top of everything, so you can never be *accidentally*
muted or *accidentally* live.

- **Toggle key:** `Tab` by default, changeable in the window
- **Badge:** 20x20 px, bottom-right, always on top, click-through
- **Settings save themselves** as you touch them, and take effect at once
- **Runs in the tray** once you close the window, no console window, no
  measurable CPU when idle
- **Registers itself** on first run: Start menu, Search, Win+R, Installed apps
- **No third-party dependencies** — stdlib Python plus direct Win32/COM calls

---

## Get it

[**Download `CuteMute.exe`**](https://github.com/FzArnob/cute-mute/releases/latest) — one
file, about 10 MB, no installer, no runtime to install first. Windows 10 or 11,
64-bit. Run it once and it puts itself in the Start menu; delete the file to be
rid of it.

There is also a Microsoft Store package
([STORE_SUBMISSION.md](STORE_SUBMISSION.md)), which is the version to prefer if
you would rather not think about any of what follows: the Store signs what it
distributes, so it installs with a real publisher name and no warning at all.
The exe below is for people who want a single file they can check for
themselves.

### The first run, and SmartScreen

The first time you run it, Windows will say **“Windows protected your PC”** and
offer only a *Don't run* button. That is SmartScreen, and it is worth knowing
exactly what it is telling you: this file carries no Authenticode certificate,
and Microsoft has not seen enough copies of it to have formed an opinion. It is
not a scan result. Nothing was found.

Each release page states whether that build is Authenticode-signed. Getting to a
signed build with a real publisher name, for free, is
[a section of its own](#the-free-route-to-a-named-publisher) — it needs an
approval this project has not yet been through.

To run it anyway: **More info** → **Run anyway**. Once per copy of the file.

The prompt itself is triggered by the *mark of the web* — a tag your browser
attaches to anything it downloads. So the other route, once you have checked the
file, is to take the tag off:

```powershell
Unblock-File .\CuteMute.exe
```

That is a real decision either way, and a README telling you to make it is
exactly what a hostile README would also say. So don't take it on faith — spend
thirty seconds on the next section instead. Then the only thing the prompt is
telling you is something you already know.

### Verify the download

Every release is signed with [Sigstore](https://www.sigstore.dev/) by the
workflow that built it. There is no private key involved — none on a runner,
none in a repository secret, none on my machine — so there is no key to be stolen
and none you have to trust. What you check is a public transparency log instead.

Download `CuteMute.exe.sigstore.json` from the same release, put it beside the
exe, and:

```powershell
python -m pip install sigstore

python -m sigstore verify github CuteMute.exe `
  --bundle CuteMute.exe.sigstore.json `
  --cert-identity "https://github.com/FzArnob/cute-mute/.github/workflows/release.yml@refs/tags/v1.0.0" `
  --repository FzArnob/cute-mute
```

Change the tag in `--cert-identity` to whichever version you downloaded; every
release page carries the exact command, already filled in. `OK` means four
things at once:

| | |
| --- | --- |
| the exe is unmodified | the signature covers its hash; one flipped byte fails |
| a workflow built it | the signer is a file path in this repo, not a person holding a key |
| from that tag | the identity ends in the git ref, so the version is part of the claim |
| and it is on the record | the signature is in a public log, so it cannot be made quietly or unmade later |

If you would rather just compare a hash, every release ships `SHA256SUMS` too:

```powershell
(Get-FileHash CuteMute.exe -Algorithm SHA256).Hash.ToLower()
```

To see what a bundle claims before you decide what to expect from it:

```powershell
python tools\sigstore_identity.py CuteMute.exe.sigstore.json
```

**What this does not do:** Sigstore does not stop the SmartScreen prompt. Windows
reads Authenticode signatures embedded in the file; a Sigstore bundle is a
separate file Windows never looks at. The two solve different problems, and only
one of them is free. See [Signing](#signing-and-unknown-publisher).

---

## Running it

```powershell
# from source, no console window
pythonw CuteMute.pyw

# or with a console, handy while trying things out
python -m cutemute
```

Starting CuteMute shows its window. Close the window and it keeps running in
the notification area: green mic = live, red slashed mic = muted.

| Action | How |
| --- | --- |
| Toggle mute | the hotkey, or left-click the tray icon |
| Open the window | right-click the tray icon → **Open**, or double-click it |
| Send it back to the tray | close the window |
| Quit | right-click the tray icon → Exit CuteMute |

The tray menu is four items — Open, Mute Microphone, Start with Windows,
Exit CuteMute — painted in the app's palette rather than the system's.

The first run also puts CuteMute where Windows looks for programs, so you can
find it by typing *cute* into Start instead of hunting for the exe:

| Where | What goes there |
| --- | --- |
| Start menu and Search | `%APPDATA%\...\Start Menu\Programs\CuteMute.lnk` |
| Win+R, and `start cutemute` | the per-user `App Paths` key |
| Settings → Installed apps | name, version, publisher, and an uninstall entry |

All three are per-user, need no admin rights, and are rewritten only when the
exe moves or the version changes. `CuteMute.exe --uninstall` takes them back
out, along with the run-at-login entry and the saved settings; the exe itself
stays put, because a running program cannot delete its own file.

### Building CuteMute.exe

```powershell
python -m pip install pyinstaller
.\build.ps1              # -> dist\CuteMute.exe   (single file, no console)
.\build.ps1 -OneDir      # -> dist\CuteMute\      (starts faster)
```

`build.ps1` regenerates `CuteMute.ico` from the same code that draws the badge,
so the exe, the tray and the overlay never drift apart. It also generates the
version resource from `cutemute/__init__.py`, which is what fills in the
Properties dialog — description, product, version, company, copyright — and
the name Task Manager and UAC show for the process.

### Signing, and "unknown publisher"

A full version resource is not a signature. There are two kinds of signature
here and they answer different questions, which is why CuteMute uses one of them
and documents the other.

**Sigstore** answers *did this file come from that project?* It is free, there is
no key to keep anywhere, and the signature goes into a public transparency log.
This is what every release is signed with, in CI, by
[`.github/workflows/release.yml`](.github/workflows/release.yml). You can do it
locally too:

```powershell
python -m pip install sigstore
.\build.ps1 -Sigstore        # -> dist\CuteMute.exe.sigstore.json
```

That opens a browser and asks an identity provider — GitHub, Google, Microsoft —
who you are, then signs as that identity. Nothing is stored on disk afterwards
except the bundle. In CI there is no browser and no question: the runner already
holds a workflow OIDC token, and `sigstore` finds it by itself.

A local signature and a CI signature are not worth the same thing. A local one
says *some GitHub account signed this*; a CI one says *this workflow, in this
repository, at this tag, produced exactly these bytes* — and the workflow is a
file you can read. That is why releases are signed by the workflow.

**Authenticode** answers *whose program is this?* — and it is the only thing
that answers it, because Windows reads nothing else. No Sigstore bundle, no
version resource, and no amount of documentation changes the words *Unknown
publisher*. Only a certificate from a CA in the Microsoft Trusted Root program
does, and there is no free source of those.

There is, however, a free source of *signing done with one*, which is what
matters — and the whole reason the release pipeline is built the way it is.

#### The free route to a named publisher

[**SignPath Foundation**](https://signpath.org/) does Authenticode signing for
open-source projects at no cost, with the key held in an HSM at
[SignPath.io](https://signpath.io/) and the signing driven from CI. It is a real
publicly-trusted certificate, so *Unknown publisher* becomes a name.

The name is **SignPath Foundation**, not `Fz's Lab` — the certificate is issued
to the foundation that sponsors the signing, and a shared certificate is the
reason it can be free. CuteMute's own identity stays in the version resource,
on the Details tab of the same Properties dialog. That is the trade: a verified
publisher name that is not yours, or your own name for money.

[`release.yml`](.github/workflows/release.yml) already has the signing step,
gated on four repository variables. Set them and releases start coming out
signed with no edit to the workflow:

| Where | Name | Value |
| --- | --- | --- |
| Secret | `SIGNPATH_API_TOKEN` | the submitter token from SignPath |
| Variable | `SIGNPATH_ORGANIZATION_ID` | your SignPath organisation id |
| Variable | `SIGNPATH_PROJECT_SLUG` | the project slug |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG` | usually `release-signing` |
| Variable | `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` | the artifact configuration slug |

Until `SIGNPATH_ORGANIZATION_ID` is set the step is skipped, the release still
goes out, and its notes say plainly that it carries no Authenticode signature.

Applying takes a form and then a wait of days to a few weeks. The conditions,
and where CuteMute stands against each, are in
[CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md) — most of them are things this
repository already does, which is not a coincidence: an OSI licence, no
proprietary components, a version resource on every build, and releases built
only by a workflow from a tag, never from a laptop. The two that needed writing
down were the signing policy itself and [PRIVACY.md](PRIVACY.md). What is still
needed is a published release for the reviewers to look at, and multi-factor
authentication on the accounts involved.

#### The other free route: the Store

The **Microsoft Store** is free to publish to as an individual, and Microsoft
signs what it distributes. A Store install therefore shows **your own**
publisher name and raises no SmartScreen prompt at all — it is the only free
route that gets both, because you never sign anything: you upload an unsigned
`.msix` and Microsoft re-signs it with a certificate Windows already trusts.

The cost is not money. It is packaging, a certification review, and two Store
policies that bite this particular app. Both the packaging and the policies are
done and written up:

```powershell
python tools\make_msix_assets.py     # 37 logo assets, from cutemute.iconart
.\tools\make_msix.ps1                # -> dist\CuteMute.msix
.\tools\make_msix.ps1 -SelfSign      # ...and sign it, to install and try locally
```

No Windows SDK? Don't install one — [`msix.yml`](.github/workflows/msix.yml)
builds it on a runner that already has `makeappx.exe`, checks the generated
assets are current, and reads the manifest back out of the finished package to
confirm the identity and both executables are really in there.

**[STORE_SUBMISSION.md](STORE_SUBMISSION.md) is the walkthrough**, including the
two traps: a privacy policy URL is *mandatory* for a Win32 app that touches
personal information, and `Fz's Lab` as a publisher name may read as a business
entity and force a paid Company account. Both have cheap fixes, and both are
much cheaper before a rejection than after one.

Inside a package CuteMute behaves slightly differently, because three of the
things it does for itself are things a package already provides and cannot write
anyway — the Start menu entry, the Win+R name, and the run-at-login registry
key. [`cutemute/packaged.py`](cutemute/packaged.py) detects the container and
skips all three; run-at-login moves to the manifest's `windows.startupTask`,
which puts the switch in Settings › Apps › Startup where Windows owns it. The
settings window says so rather than drawing a switch that could only lie.

The two channels are worth keeping side by side: the Store for people who want
an app, the signed exe for people who want to check what they are running.

#### And if you would rather just pay

| Route | Publisher shown | Cost |
| --- | --- | --- |
| nothing | *Unknown publisher* | free |
| self-signed | a name, on machines that trust your certificate — which is to say yours | free, and useless for distribution |
| SignPath Foundation | *SignPath Foundation* | free, subject to approval |
| Microsoft Store, as MSIX | your own | free, plus packaging work |
| Azure Artifact Signing (was Trusted Signing) | your own | about $10/month; individuals in the US and Canada, organisations need three years of verifiable history |
| OV, from a CA | your own | roughly $150–300/year |
| EV | your own, and the closest thing to immediate trust | the most expensive |

To sign with a certificate you already hold:

```powershell
.\build.ps1 -Certificate mycert.pfx     # or a cert thumbprint from your store
```

#### SmartScreen is a separate question

Worth being clear about, because it is where people expect a certificate to do
more than it does: SmartScreen weighs download reputation as well as signature,
and reputation accrues to the *certificate*. Neither OV nor Azure Artifact
Signing grants instant trust — a brand-new certificate's first signed release
can still prompt. Only EV comes close to immediate.

This is another quiet advantage of the SignPath Foundation route: its
certificate already signs a great many open-source projects, so it arrives with
reputation rather than having to earn it from your download count.

Antivirus false positives on PyInstaller one-file builds are common and are not
about your code — a self-extracting binary simply looks like one. `build.ps1`
passes `--noupx` for that reason, since UPX-packed executables trip noticeably
more heuristics. Beyond that, a signature and Microsoft's false-positive
submission form are the two things that actually help.

To start it with Windows, tick **Start CuteMute with Windows** in the window or
in the tray menu. It writes the per-user `Run` key — no admin rights, no
scheduled task — with `--tray`, so logging in does not pop the window open.

### Command line

| Flag | Effect |
| --- | --- |
| *(none)* | show the window; closing it leaves CuteMute in the tray |
| `--tray` | start straight into the tray — what run-at-login uses |
| `--toggle` | toggle mute once and exit — for binding from other tools |
| `--uninstall` | remove those entries and the settings, then exit |
| `--selftest` | start up, print diagnostics, flash the badge, exit |
| `--version` | print the version |

Launching a second copy does not start a second instance; it just brings the
running one's window up.

---

## A word about `Tab`

`Tab` is the default because you asked for it, but it is worth knowing what it
means. By default CuteMute **watches** for the key and lets it through, so `Tab`
still indents, still moves between fields — and also toggles your mic. That is
usually not what you want while typing.

Two ways to fix it, both in settings:

- **Block the key from other apps** — `Tab` now belongs to CuteMute alone and
  nothing else ever sees it. Simple, but you lose `Tab`.
- **Pick a different key** — click the key box and hit anything (`Esc`
  cancels, and so does clicking the box again): `F13`, `Pause`,
  `Scroll Lock`, a spare mouse-side key, or a combination like `Ctrl+Alt+M`.
  This is the recommended route.

Modifiers must match exactly, so a hotkey of plain `Tab` is *not* triggered by
`Alt+Tab` or `Ctrl+Tab`. Holding the key down toggles once, not once per repeat.

---

## Settings

There is no Save button. Every change is written a quarter of a second after
you stop fiddling and pushed straight into the running app — new hotkey, new
badge, new audio scope, all live — with a small *Saving / Saved* indicator in
the corner, so the write is visible rather than merely promised. Closing the
window flushes anything still pending.

Everything lives in `%APPDATA%\CuteMute\config.json`, written atomically, and
regenerated with defaults if it is missing or corrupt.

| Setting | Default | Notes |
| --- | --- | --- |
| Toggle key | `Tab` | captured through the global hook, so exotic keys work |
| Block the key from other apps | off | swallow the keystroke entirely |
| Show badge while muted | on | |
| Size | `20` px | real physical pixels at any display scaling |
| Margin | `8` px | distance from the corner of the work area |
| Corner | bottom-right | any of the four |
| Opacity | `100%` | |
| Mute every input device | off | on = every active capture endpoint |
| Play a short beep when toggling | off | low = muted, high = live |
| Start CuteMute with Windows | off | per-user `Run` key |

---

## How it works

Four threads, each blocked on something the kernel wakes it for. Nothing polls
in a spin loop, which is why idle CPU measures as flat zero.

```
main            waits on a queue; builds the window when asked, and is asked
                as soon as CuteMute starts unless --tray says otherwise
CuteMute-winui  one Win32 message pump shared by the badge and the tray icon
CuteMute-hotkey a WH_KEYBOARD_LL hook, kept deliberately tiny
CuteMute-audio  owns the COM apartment and does every mute/unmute
```

**The realtime path is short on purpose:**

```
hook callback  ->  queue.put_nowait  ->  audio thread  ->  IAudioEndpointVolume::SetMute
   (integer compares only)                                 (~3 ms, measured)
```

The hook callback never touches audio, GUI or COM. That is not just tidiness:
if a low-level keyboard hook takes longer than `LowLevelHooksTimeout` (300 ms by
default) Windows silently tears it down, and a stalled hook delays *every*
keystroke on the machine, in every app. So the callback compares a few integers,
pushes to a queue and returns. The badge is updated after the fact.

### Some specific choices

**Mute is a hook, not `RegisterHotKey`.** `RegisterHotKey` always consumes the
key, which would break `Tab` everywhere with no way to opt out. A hook can watch
and pass through, so swallowing becomes a setting.

**Both default capture devices are muted.** The console default and the
communications default are usually the same microphone, but when a headset is
set as the "chat" device they are not — and one keypress should silence both.

**The badge is a layered window with per-pixel alpha.** `UpdateLayeredWindow`
with a premultiplied ARGB bitmap gives a genuinely anti-aliased rounded badge
over whatever is underneath, instead of the hard colour-keyed fringe you get
from a transparent-colour window. It is `WS_EX_TRANSPARENT` (clicks pass
through), `WS_EX_NOACTIVATE` (never steals focus) and `WS_EX_TOOLWINDOW` (stays
out of Alt+Tab), and it re-asserts topmost every 3 s in case something else
grabs the top slot.

**The process is per-monitor-DPI-aware.** So 20 px is 20 real pixels and the
badge is never blurred by the compositor. The window scales every coordinate
it draws instead, and shrinks that scale if the panel would not fit the
screen.

**The icon is drawn in code.** `cutemute/iconart.py` rasterises the mic badge
from signed-distance tests with 4x4 supersampling — a few milliseconds, cached,
and it means one definition feeds the overlay, the tray icon and the `.ico`,
at any size, with no image files to ship.

**No pycaw, no comtypes, no Pillow.** `cutemute/audio.py` calls the Core Audio
COM vtables directly through `ctypes`; it is about eighty lines, has no
packaging quirks when frozen, and keeps the toggle path down to a couple of
virtual calls.

**The window is drawn, not themed.** ttk cannot give you rounded dark rows, a
switch or a dark combobox on Windows, so the panel is a single Tk canvas
painted from anti-aliased sprites (`paint.py`), with hit-testing done against
a list of rectangles rather than canvas tags — which is also what stops a
hovered row flickering as the pointer crosses the five items it is made of.
Sprite geometry is cached for the life of the process; the `PhotoImage`
objects die with the window.

**The title bar is ours too.** A window that says it cannot be maximised still
gets a greyed-out maximise button beside minimise, and no window style means
"minimise and close only" — so the frame goes (`overrideredirect`), and the
taskbar button, the Alt+Tab entry and the rounded corners are all asked for
again by hand.

**The tray menu is a real menu with owner-drawn items.** Windows keeps the
parts that are easy to get wrong — keyboard navigation, dismissing on a click
somewhere else, multi-monitor placement — and the items are painted in the
app's palette. Its background brush is not optional: Windows 11 still draws a
classic Win32 menu in the light theme even on a fully dark desktop.

**Settings UI is built on demand and thrown away.** The resident app keeps no
GUI toolkit state while it is just sitting in the tray.

### Measured

| | |
| --- | --- |
| Idle CPU | 0 ms over 15 s (below the 15.6 ms clock granularity) |
| Working set | ~25 MB (~12 MB private) |
| Mute latency | ~3 ms for the Core Audio call; hook overhead is sub-millisecond |

### Known limits

- A **fullscreen exclusive** game or app can draw over any topmost window,
  including the badge. Borderless-windowed mode is fine.
- The badge is placed on the **primary** monitor's work area.
- A low-level hook cannot see keystrokes sent to a window running **elevated**
  unless CuteMute is elevated too. Run it as administrator if you need the
  hotkey to work while an admin app has focus.

---

## Releasing

Tag it, and [`release.yml`](.github/workflows/release.yml) does the rest on a
clean Windows runner: build, check the tag against `__version__`, check the
version resource landed, sign with Sigstore, verify its own signature with the
command the README gives you, and publish the release with the exe, the bundle
and `SHA256SUMS` attached.

```powershell
# bump __version__ in cutemute/__init__.py first -- the workflow fails if the
# tag and the package disagree
git tag v1.0.1
git push origin v1.0.1
```

`workflow_dispatch` builds and signs without publishing, so the pipeline can be
exercised without spending a version number. The same tag also builds the Store
package via [`msix.yml`](.github/workflows/msix.yml), which uploads it as an
artifact rather than publishing it — a Store submission is a manual step, and
should be.

Once SignPath is configured, a release also waits for a human to approve the
signing request in SignPath — the workflow gives it half an hour before it
gives up.

Two documents exist because SignPath's conditions require them, and both have to
stay true: [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md) and
[PRIVACY.md](PRIVACY.md). If the release process changes, they change with it.

### The website

[`docs/`](docs/) is the landing page, served by GitHub Pages from
**Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**. It is one
self-contained HTML file — no build step, no Jekyll, no dependencies.

Its logo, favicons and social card are generated, not drawn:

```powershell
python tools\make_brand.py       # -> docs/assets/
```

Everything comes out of `cutemute.iconart.SHAPE`, the same geometry the overlay
and the tray icon are rasterised from, so the mark on the website cannot drift
away from the one in your notification area. `build.yml` regenerates them on
every push and fails if the committed files differ.

`docs/assets/og.png` is also the right thing to upload under
**Settings → General → Social preview**.

---

## Layout

```
cutemute/
  app.py          wiring, lifecycle, single instance, CLI
  audio.py        Core Audio mute via raw ctypes COM + the audio thread
  hotkey.py       WH_KEYBOARD_LL listener, chord matching, capture mode
  overlay.py      the layered always-on-top badge window
  tray.py         tray icon and its context menu
  menu.py         that menu, owner-drawn to match the window
  winui.py        the Win32 UI thread hosting overlay + tray
  settings_ui.py  the settings window: one canvas, saves as you touch it
  paint.py        its anti-aliased sprites, built without dependencies
  theme.py        the palette the window and the menu share
  iconart.py      procedural badge rasteriser
  winicon.py      badge -> HICON
  keys.py         virtual-key names, modifier state
  config.py       %APPDATA% JSON settings
  startup.py      run-at-login registry entry
  install.py      Start menu, Win+R and Installed apps entries
  w32.py          the Win32 ctypes bindings everything else uses
  packaged.py     am I inside an MSIX package, and what changes if I am
tools/
  make_ico.py     build CuteMute.ico from iconart
  make_version.py the version resource stamped into the exe
  make_brand.py   the website's logo, favicons and social card, from iconart
  make_msix_assets.py   the 37 Store logo assets, also from iconart
  make_msix.ps1   stage and pack the MSIX
  check_manifest.py     fail fast on a broken package manifest
  preview_icon.py render a PNG contact sheet of the badge
  sigstore_identity.py  read a bundle, print the verify command that matches it
packaging/msix/
  AppxManifest.xml      the package manifest, with placeholders
  Assets/         generated -- do not edit by hand, run make_msix_assets.py
docs/
  index.html      the landing page; GitHub Pages serves this folder
  privacy.html    the privacy policy the Store requires a URL for
  assets/         generated -- do not edit by hand, run make_brand.py
.github/workflows/
  build.yml       every push: compile, build the exe, check assets are current
  release.yml     every v* tag: build, sign with Sigstore, publish the release
  msix.yml        every v* tag: build the Store package
CuteMute.pyw      console-free entry point
build.ps1         PyInstaller build, optionally signing
CODE_SIGNING_POLICY.md  who may sign a release, and how to check one
STORE_SUBMISSION.md     getting into the Microsoft Store, and the two traps
PRIVACY.md        what CuteMute stores, and what it never sends
SECURITY.md       what it touches, and how to report a hole in it
```

# Publishing CuteMute to the Microsoft Store

The Store is the only free route that gives CuteMute **your own publisher name
and no SmartScreen prompt at all**. It works because you never sign anything:
you upload an unsigned `.msix`, and Microsoft re-signs it with its own
certificate during ingestion. Windows trusts that certificate implicitly, so an
install from the Store shows *your* name, raises no "unknown publisher", and
shows no "Windows protected your PC".

The cost is not money. It is packaging, a certification review, and the two
traps in the next section.

---

## Read this part first

Two Store policies bite this specific app, and both are cheaper to handle now
than after a rejection.

### The publisher name may force a paid account

[Policy 10.14](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies#1014-account-type):

> Company accounts must be used for organizations, businesses, and any person
> acting in relation to their trade or profession. […] A company account is
> required […] **if a reasonable consumer would interpret your application or
> publisher name to be that of a business entity.**

`Fz's Lab` reads like a business entity. Registering as an Individual and then
publishing under that name is the kind of thing that gets caught at review, and
a Company account is neither free nor instant — it needs business verification.

**Recommendation:** register an Individual account and set the publisher display
name to your own name, `Md. Farhan Zaman`. That is what
[`tools/make_msix.ps1`](tools/make_msix.ps1) defaults to. `Fz's Lab` stays where
it is harmless: in the exe's version resource, and in the README.

This changes nothing about the app. It changes the words under the title on the
Store page, and it is the difference between a free account and a verified one.

### A privacy policy URL is mandatory, not optional

[Policy 10.5.1](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies#105-personal-information):

> Product types that inherently have access to Personal Information must always
> have privacy policies. These include, but are not limited to, **Desktop Bridge
> and Win32 products.**

CuteMute is a Win32 product *and* it installs a keyboard hook, so this is not a
grey area. The policy is already written and hosted:

```
https://fzarnob.github.io/cute-mute/privacy.html
```

Paste that into Partner Center under Properties → Privacy policy URL. It needs
GitHub Pages switched on first (Settings → Pages → `main` / `/docs`).

### And disclose the keyboard hook plainly

No policy forbids a global hotkey — but [10.1.1](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies#1011)
requires the description to accurately reflect functionality "including required
or supported input devices". An app that watches every keystroke and does not
say so invites a reviewer to reach for the
[unwanted-software criteria](https://learn.microsoft.com/en-us/windows/security/threat-protection/intelligence/criteria).

Say it in the description, and say it again in **Notes for certification**.
Suggested wording is at the bottom of this file.

---

## Build the package

```powershell
python tools\make_msix_assets.py     # 37 logo assets, from cutemute.iconart
.\tools\make_msix.ps1                # -> dist\CuteMute.msix
```

`make_msix.ps1` needs `makeappx.exe` from the Windows SDK. If you do not have
it, don't install it — let CI build the package instead:

```powershell
gh workflow run msix.yml
```

[`.github/workflows/msix.yml`](.github/workflows/msix.yml) is the reference
build: `windows-latest` already has the SDK, it checks the generated assets are
current, and it reads the manifest back out of the finished `.msix` to confirm
the identity, the version and both executables are really in there.

### What is in the package, and why

| | |
| --- | --- |
| `CuteMute.exe` + `_internal/` | a PyInstaller **onedir** build. A onefile exe unpacks itself to a temp directory on every launch, which is pure waste inside a package that is already compressed |
| `CuteMuteTray.exe` | a byte-identical copy of `CuteMute.exe`, for the startup task |
| `Assets/` | 37 PNGs, generated from `cutemute.iconart.SHAPE` |
| `AppxManifest.xml` | [the template](packaging/msix/AppxManifest.xml) with the identity filled in |

The duplicate exe is not a mistake. The MSIX `windows.startupTask` extension
cannot pass arguments, and logging in is not a request to see the settings
window — so the startup task launches `CuteMuteTray.exe`, and
[`app.py`](cutemute/app.py) reads its own filename and starts hidden. The onedir
bootloader locates `_internal` from the executable's directory rather than its
name, so a renamed copy works; this is verified, not assumed.

### What changes inside a package

[`cutemute/packaged.py`](cutemute/packaged.py) detects the container and turns
off three things the loose exe does, because the package already provides all
three and a package cannot write outside itself anyway:

- **the Start menu shortcut** — the manifest declares it
- **the Win+R name and installed-apps entry** — `windows.appExecutionAlias`
  declares the first, and MSIX uninstalls cleanly
- **the run-at-login `Run` key** — virtualised inside a package, so writing it
  silently does nothing. `windows.startupTask` is the supported route, and it
  puts the switch in **Settings › Apps › Startup**, where Windows owns it

That last one is a real difference in behaviour: in the Store build the settings
window shows a line explaining that Windows manages startup, rather than a
switch that could only lie about its own state. The tray menu's *Start with
Windows…* item opens the Settings page.

---

## Test it locally before submitting

```powershell
.\tools\make_msix.ps1 -SelfSign
```

Then trust the test certificate and install, in an **elevated** prompt (the
script prints these too):

```powershell
Export-Certificate -Cert Cert:\CurrentUser\My\<thumbprint> -FilePath test.cer
Import-Certificate -FilePath test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
Add-AppxPackage .\dist\CuteMute.msix
```

Worth checking by hand, because none of it can be tested unpackaged:

- [ ] the tile and app-list icon look right at every size, light theme and dark
- [ ] the hotkey works while another app has focus — this is the one that would
      prove `runFullTrust` is doing its job
- [ ] the badge appears over other windows
- [ ] muting actually mutes, in Sound settings
- [ ] the settings window shows the "Windows manages this" startup row
- [ ] **Settings › Apps › Startup** lists CuteMute; enabling it and logging back
      in starts CuteMute **in the tray, with no window**
- [ ] `CuteMute` typed into a terminal starts it (the execution alias)
- [ ] uninstalling from Start leaves nothing behind

Remove it again with:

```powershell
Get-AppxPackage *CuteMute* | Remove-AppxPackage
```

---

## Submit

1. **Register.** [partner.microsoft.com](https://partner.microsoft.com/dashboard)
   → Windows & Xbox. Individual registration is free. See the publisher-name
   warning above before you choose a display name.
2. **Reserve the name** `CuteMute`. If it is taken, the reserved name and the
   `DisplayName` in the manifest must still agree.
3. **Copy the identity values** from Product → Product identity, and set them as
   repository variables so CI builds a submittable package:

   | Variable | From Partner Center |
   | --- | --- |
   | `STORE_IDENTITY_NAME` | Package/Identity/Name, e.g. `12345FzArnob.CuteMute` |
   | `STORE_IDENTITY_PUBLISHER` | Package/Identity/Publisher, e.g. `CN=ABCDEF12-3456-…` |
   | `STORE_PUBLISHER_DISPLAY_NAME` | Package/Properties/PublisherDisplayName |

   A package whose identity does not match the reservation **exactly** is
   rejected at upload. This is the single most common failure.
4. **Build and upload** the `.msix`. Upload it unsigned.
5. **Fill in the listing** — see below.
6. **Submit.** Certification usually takes hours to a couple of days. A
   rejection comes with the policy number; fix and resubmit.

### Listing fields

| Field | What to put |
| --- | --- |
| Category | Utilities & tools |
| Privacy policy URL | `https://fzarnob.github.io/cute-mute/privacy.html` — **required** |
| Website | `https://fzarnob.github.io/cute-mute/` |
| Support contact | your GitHub issues URL |
| Age rating | complete the IARC questionnaire; this app has no rateable content |
| Screenshots | at least one, 1366×768 or larger. The settings window and the badge in a screen corner |

### Notes for certification

Paste something like this into the field. It exists so a reviewer does not have
to guess why a mute utility hooks the keyboard:

> CuteMute is a microphone mute utility. It installs a low-level Windows
> keyboard hook (`WH_KEYBOARD_LL`) so that its configurable mute hotkey works
> while any application has focus. Keystrokes are compared against the
> configured hotkey and discarded immediately: nothing is stored, logged or
> transmitted, and the app makes no network connections of any kind and declares
> no networking capability. It also uses Core Audio
> (`IAudioEndpointVolume::SetMute`) to mute and unmute capture devices; it never
> opens an audio stream and cannot record. `runFullTrust` is required for both.
> Source: https://github.com/FzArnob/cute-mute — privacy policy:
> https://fzarnob.github.io/cute-mute/privacy.html

---

## Afterwards

The Store package and the signed `.exe` are two channels for the same build, and
both should keep working:

- **Store** — your publisher name, no prompt, automatic updates. Best for
  ordinary users.
- **Direct `.exe`** — one file, no account, verifiable with Sigstore. Best for
  people who want to check what they are running. See
  [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).

Bump `__version__` in [`cutemute/__init__.py`](cutemute/__init__.py) for each
Store submission; the Store rejects a package whose version is not higher than
the last one. The MSIX version is that number with a `.0` revision — the Store
requires the fourth part to be zero, which is why `make_msix.ps1` sets it rather
than reading four parts from anywhere.

# Store listing copy

Everything Partner Center asks for, written out. Paste it; don't retype it.

Two of these fields are the ones that get submissions rejected, so they are
first: the publisher display name, and the certification notes that explain why
a microphone utility hooks the keyboard.

---

## Publisher display name

```
Md. Farhan Zaman
```

Not `Fz's Lab`. [Policy 10.14](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies#1014-account-type)
requires a Company account if a reasonable consumer would read the publisher
name as a business entity, and `Fz's Lab` reads like one. Company accounts are
neither free nor instant. `Fz's Lab` stays in the exe's version resource, where
it is harmless.

---

## Notes for certification

Not shown to users. It exists so a reviewer does not have to guess why this app
installs a keyboard hook.

```
CuteMute is a microphone mute utility.

It installs a low-level Windows keyboard hook (WH_KEYBOARD_LL) so that its
configurable mute hotkey works while any application has focus. Keystrokes are
compared against the configured hotkey and discarded immediately: nothing is
stored, logged, buffered or transmitted. The app makes no network connections of
any kind and declares no networking capability, so there is nowhere for such
data to go even in principle.

It uses Core Audio (IAudioEndpointVolume::SetMute) to mute and unmute capture
devices. It never opens an audio stream and cannot record.

runFullTrust is required for both of the above; neither API is available to a
sandboxed app.

Full source, MIT licensed: https://github.com/FzArnob/cute-mute
The keyboard hook is ~120 lines: https://github.com/FzArnob/cute-mute/blob/main/cutemute/hotkey.py
Privacy policy: https://fzarnob.github.io/cute-mute/privacy.html
```

---

## Product name

```
CuteMute
```

## Short description

```
One keypress mutes your microphone, and a small badge sits on top of every window while you are muted — so you always know whether you are live.
```

## Description

```
CuteMute does one thing: it puts your microphone mute on a single key, and then makes very sure you know which state you are in.

Muting is the easy part. Knowing whether you are muted is the part every meeting gets wrong — so while your microphone is muted, a small badge sits in the corner of the screen on top of every window. It is click-through, it never steals focus, and it never appears in Alt+Tab. Unmute and it disappears.

WHAT IT DOES

• One key, anywhere. A low-level keyboard hook means the hotkey works while any application has focus, not just when CuteMute is in front. Pick any key — including F13, Pause, Scroll Lock or a combination like Ctrl+Alt+M.

• Watches, or swallows. By default the key still reaches the app underneath, so a key like Tab keeps doing its normal job as well. One switch makes CuteMute keep the key to itself instead.

• Both of your default microphones. Windows keeps a separate "console" default and "communications" default, and when a headset is set as the chat device they are different devices. One keypress silences both. Optionally, every capture device on the machine.

• A badge you can tune. Size, corner, margin and opacity are all adjustable, and it is drawn with real per-pixel transparency, so it is genuinely anti-aliased rather than a hard-edged rectangle.

• Optional confirmation beep — low for muted, high for live — for when you are not looking at the screen.

• Runs in the notification area. Green microphone means live, red crossed-out microphone means muted. Left-click toggles.

BUILT TO STAY OUT OF THE WAY

CuteMute idles at zero measurable CPU. Four threads, each blocked waiting on something the kernel wakes it for; nothing polls. Muting takes about three milliseconds. The keyboard hook does nothing but compare a few integers and hand off to another thread, because a slow hook delays every keystroke on the machine.

It has no third-party dependencies at all — just Python's standard library and direct Windows API calls.

PRIVACY

CuteMute makes no network connections of any kind. No telemetry, no analytics, no update check, no crash reporting. It contains no HTTP client and declares no networking capability.

It has to see keystrokes to offer a global hotkey. Each one is compared against your configured key and discarded. Nothing is stored, logged or sent — and with no network access, there is nowhere for it to go. The comparison is about 120 lines of code, and you can read it.

Settings are one small JSON file on your own machine. That is the only thing CuteMute writes.

FREE AND OPEN SOURCE

MIT licensed, and the entire source is public. Every release is also published as a standalone exe signed with Sigstore, so anyone can verify exactly which build produced which file.

https://github.com/FzArnob/cute-mute
```

## Search terms

Seven at most. These avoid the product name, which is already indexed.

```
mute microphone
mic mute
push to mute
mute hotkey
microphone indicator
meeting mute
mute overlay
```

## Product features

Short bullets, shown near the top of the listing.

```
Mute your microphone with one keypress, from any application
An always-on-top badge shows at a glance when you are muted
Choose any hotkey, including F13, Pause or a modifier combination
Mutes both of Windows' default capture devices, or every device
Adjustable badge size, corner, margin and opacity
Optional confirmation beep — low for muted, high for live
Zero measurable idle CPU and no background network activity
Free, open source, MIT licensed, no telemetry
```

## What's new in this version

```
First Store release.

• Mute your microphone with one keypress from any application
• An always-on-top badge while muted, so you always know your state
• Configurable hotkey, badge size, corner, margin and opacity
• Optional confirmation beep
• No network access of any kind
```

---

## The rest of the form

| Field | Value |
| --- | --- |
| Category | Utilities & tools |
| Privacy policy URL | `https://fzarnob.github.io/cute-mute/privacy.html` — **required**, and it must resolve |
| Website | `https://fzarnob.github.io/cute-mute/` |
| Support contact info | `https://github.com/FzArnob/cute-mute/issues` |
| Pricing | Free |
| Age rating | Complete the IARC questionnaire. CuteMute has no rateable content: no user-generated content, no ads, no purchases, no data collection, no network access. Expect the lowest rating. |
| Markets | All |
| Device families | Windows 10 and 11 desktop, x64 |
| Accessibility | Do not claim accessibility support; nothing has been formally tested |

## Screenshots

In this folder, both 1920x1080 PNG, which clears the 1366x768 minimum:

| File | What it shows |
| --- | --- |
| `screenshot-1-settings.png` | the real settings window, captured from a running build |
| `screenshot-2-badge.png` | the badge sitting above another window |

The window in the first is a genuine capture. The second is an illustration
drawn from the generated brand assets — no real desktop content, and the caption
says the badge is shown enlarged, because at its 20 px default it would be a
handful of pixels in a 1920-wide image. Do not crop that caption out:
[policy 10.1.1](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies#1011)
is about metadata accurately reflecting the product.

Regenerate with:

```powershell
# with CuteMute running and its settings window open
powershell -File tools\make_store_shots.ps1
```

## Store logo

Partner Center may ask for a 300x300 listing logo separately from the package
assets. Use `packaging/msix/Assets/Square310x310Logo.png`, or generate any size
from the badge with `python tools/make_msix_assets.py`.

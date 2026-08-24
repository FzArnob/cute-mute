### Download

[`CuteMute.exe`](https://github.com/{{REPO}}/releases/download/{{TAG}}/CuteMute.exe) — one file, about 10 MB, no installer, nothing to install first. Windows 10 or 11, 64-bit.

{{AUTHENTICODE}}

SmartScreen may still prompt on a file it has not seen many copies of, signed or not, because it also weighs download reputation. **More info → Run anyway** gets past it — or spend thirty seconds verifying the file first, which is the better habit:

### Verify

```powershell
python -m pip install sigstore

python -m sigstore verify github CuteMute.exe `
  --bundle CuteMute.exe.sigstore.json `
  --cert-identity "{{IDENTITY}}" `
  --repository {{REPO}}
```

Download `CuteMute.exe.sigstore.json` from the assets below and put it beside the exe first. `OK` means this exe is byte-for-byte what this repository's release workflow built from `{{TAG}}`, and that the signature is recorded in Sigstore's public transparency log. No private key exists anywhere in this process, so there is none for you to have to trust.

Sigstore is not Authenticode, so it does not stop the SmartScreen prompt. It tells you exactly what you downloaded, which is the part a certificate does not actually tell you.

Or just compare the hash:

```powershell
(Get-FileHash CuteMute.exe -Algorithm SHA256).Hash.ToLower()
# {{SHA256}}
```

### Assets

| File | What it is |
| --- | --- |
| `CuteMute.exe` | the application |
| `CuteMute.exe.sigstore.json` | its Sigstore bundle: certificate, signature, transparency log entry |
| `SHA256SUMS` | the checksum above |

Built by [`.github/workflows/release.yml`](https://github.com/{{REPO}}/blob/{{TAG}}/.github/workflows/release.yml) from `{{SHA}}`.

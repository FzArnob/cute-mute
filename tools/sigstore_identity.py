"""Read a Sigstore bundle and print the verify command that matches it.

    python tools\\sigstore_identity.py CuteMute.exe.sigstore.json

`sigstore verify` will not simply accept whatever identity a bundle claims --
you have to tell it which signer and which issuer to expect, which is the whole
point of it. That is awkward the first time, because the two strings you need
are inside the bundle you are trying to check.

So: this prints them, and prints the command with them filled in. It proves
nothing on its own -- a forged bundle would happily tell you the identity it
wants you to expect. Use it to *find out* what a bundle claims, then check that
claim against who you believe published the file, and let `sigstore verify` do
the actual cryptography.
"""
import json
import sys
from base64 import b64decode
from pathlib import Path

# Fulcio's OIDs, from sigstore/fulcio's docs/oid-info.md.
OID_ISSUER_V2 = "1.3.6.1.4.1.57264.1.8"     # DER-wrapped UTF8String
OID_ISSUER_V1 = "1.3.6.1.4.1.57264.1.1"     # bare UTF-8, deprecated
GITHUB_ACTIONS = "https://token.actions.githubusercontent.com"


def _utf8string(raw):
    """Unwrap a DER UTF8String (tag 0x0c), or pass bare bytes straight through.

    The V1 issuer extension stored the URL as raw UTF-8; V2 wraps it properly.
    Both are still in the wild, so sniff the tag rather than assuming.
    """
    if len(raw) >= 2 and raw[0] == 0x0C:
        length = raw[1]
        if length & 0x80:                       # long form: 0x8n, then n bytes
            count = length & 0x7F
            length = int.from_bytes(raw[2:2 + count], "big")
            return raw[2 + count:2 + count + length].decode("utf-8")
        return raw[2:2 + length].decode("utf-8")
    return raw.decode("utf-8")


def read(bundle_path):
    """(identity, issuer) as they appear in the bundle's signing certificate."""
    try:
        from cryptography import x509
    except ImportError:
        sys.exit("needs the cryptography package: python -m pip install sigstore")

    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    material = bundle.get("verificationMaterial", {})
    if "certificate" in material:
        der = material["certificate"]["rawBytes"]
    else:
        # Older bundles carried a chain rather than a single leaf; the leaf is
        # always first.
        der = material["x509CertificateChain"]["certificates"][0]["rawBytes"]
    cert = x509.load_der_x509_certificate(b64decode(der))

    san = cert.extensions.get_extension_for_class(
        x509.SubjectAlternativeName).value
    names = (san.get_values_for_type(x509.RFC822Name)
             + san.get_values_for_type(x509.UniformResourceIdentifier))
    if not names:
        # A workflow or machine identity can arrive as an otherName instead.
        names = [_utf8string(entry.value)
                 for entry in san.get_values_for_type(x509.OtherName)]

    issuer = None
    for oid in (OID_ISSUER_V2, OID_ISSUER_V1):
        try:
            ext = cert.extensions.get_extension_for_oid(x509.ObjectIdentifier(oid))
        except x509.ExtensionNotFound:
            continue
        issuer = _utf8string(ext.value.value)
        break

    return (names[0] if names else None), issuer


def command(subject, bundle_path, identity, issuer):
    """The `sigstore verify` invocation this bundle should be checked with."""
    if issuer == GITHUB_ACTIONS:
        # A workflow identity looks like
        #   https://github.com/OWNER/REPO/.github/workflows/FILE.yml@REF
        # and `verify github` can additionally pin the repository slug.
        repo = "/".join(identity.split("/")[3:5]) if identity else "OWNER/REPO"
        return ["python -m sigstore verify github %s \\" % subject,
                "  --bundle %s \\" % bundle_path,
                '  --cert-identity "%s" \\' % identity,
                "  --repository %s" % repo]
    return ["python -m sigstore verify identity %s \\" % subject,
            "  --bundle %s \\" % bundle_path,
            '  --cert-identity "%s" \\' % identity,
            '  --cert-oidc-issuer "%s"' % issuer]


def main(argv):
    if not argv:
        sys.exit(__doc__.strip().splitlines()[2].strip())

    bundle_path = Path(argv[0])
    subject = (bundle_path.name[:-len(".sigstore.json")]
               if bundle_path.name.endswith(".sigstore.json")
               else str(bundle_path.with_suffix("")))

    identity, issuer = read(bundle_path)
    print("bundle   : %s" % bundle_path)
    print("signer   : %s" % (identity or "(none found)"))
    print("issuer   : %s" % (issuer or "(none found)"))
    if identity and issuer == GITHUB_ACTIONS:
        print("kind     : GitHub Actions workflow -- no human held a key")
    elif identity:
        print("kind     : an account at that issuer")
    print()
    print("Verify with:")
    for line in command(subject, bundle_path, identity, issuer):
        print("  " + line)
    print()
    print("Only trust the result if that signer is who you expected.")


if __name__ == "__main__":
    main(sys.argv[1:])

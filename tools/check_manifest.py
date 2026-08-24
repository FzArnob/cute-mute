"""Check the MSIX manifest template before a tag finds out the hard way.

    python tools\\check_manifest.py

packaging/msix/AppxManifest.xml is only exercised when a package is actually
built, which happens on tags. This runs on every push instead, and catches the
two ways the template breaks silently:

  * XML that is not well-formed. The usual culprit is a `--` inside an XML
    comment, which is illegal and which nothing warns you about until a parser
    refuses the file.
  * A placeholder renamed on one side only. make_msix.ps1 substitutes a fixed
    set of names and fails on anything left over, but it cannot know about a
    placeholder that was deleted from the template and is still being
    substituted, or vice versa.

Exits non-zero with a readable message on either.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "packaging" / "msix" / "AppxManifest.xml"

# Must match the substitutions in tools/make_msix.ps1, exactly.
PLACEHOLDERS = {
    "IDENTITY_NAME",
    "IDENTITY_PUBLISHER",
    "VERSION",
    "DISPLAY_NAME",
    "PUBLISHER_DISPLAY_NAME",
    "DESCRIPTION",
}

FOUNDATION = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
DESKTOP = "http://schemas.microsoft.com/appx/manifest/desktop/windows10"


def main():
    if not MANIFEST.exists():
        sys.exit("missing %s" % MANIFEST)
    raw = MANIFEST.read_text(encoding="utf-8")

    found = set(re.findall(r"\{\{(\w+)\}\}", raw))
    if found != PLACEHOLDERS:
        missing = sorted(PLACEHOLDERS - found)
        extra = sorted(found - PLACEHOLDERS)
        lines = ["placeholders in the manifest do not match make_msix.ps1:"]
        if missing:
            lines.append("  substituted but not present: %s" % ", ".join(missing))
        if extra:
            lines.append("  present but never substituted: %s" % ", ".join(extra))
        sys.exit("\n".join(lines))

    filled = raw
    for name in found:
        filled = filled.replace("{{%s}}" % name, "placeholder")
    try:
        root = ET.fromstring(filled)
    except ET.ParseError as exc:
        sys.exit("AppxManifest.xml is not well-formed: %s\n"
                 "(a `--` inside an XML comment is the usual cause)" % exc)

    # The pieces the package would be broken without, and which a typo in a
    # namespace prefix would quietly remove rather than fail on.
    app = root.find(".//{%s}Application" % FOUNDATION)
    task = root.find(".//{%s}StartupTask" % DESKTOP)
    extension = root.find(".//{%s}Extension" % DESKTOP)
    problems = []
    if app is None:
        problems.append("no <Application> element")
    elif app.get("EntryPoint") != "Windows.FullTrustApplication":
        problems.append("Application EntryPoint is not Windows.FullTrustApplication "
                        "-- the keyboard hook and Core Audio both need full trust")
    if task is None:
        problems.append("no windows.startupTask -- run-at-login would not work "
                        "in the package")
    if extension is not None and extension.get("Executable") != "CuteMuteTray.exe":
        problems.append("the startup task should launch CuteMuteTray.exe, so the "
                        "app starts hidden (see cutemute/app.py)")
    if problems:
        sys.exit("\n".join(["AppxManifest.xml:"] + ["  - " + p for p in problems]))

    print("AppxManifest.xml: well-formed, %d placeholders, full-trust entry "
          "point, startup task intact" % len(found))


if __name__ == "__main__":
    main()

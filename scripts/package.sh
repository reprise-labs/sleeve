#!/bin/zsh
set -eu
cd "${0:A:h}/.."
ROOT_DIR="$PWD"
APP="$ROOT_DIR/Sleeve.app"
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")
DESTINATION="${1:-$ROOT_DIR/../Sleeve-release}"
mkdir -p "$DESTINATION"
STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/sleeve-package.XXXXXX")"
trap 'rm -rf "$STAGE_ROOT"' EXIT
PACKAGE="$STAGE_ROOT/Sleeve-$VERSION"
mkdir -p "$PACKAGE/scripts" "$PACKAGE/Documentation"
/usr/bin/ditto "$APP" "$PACKAGE/Sleeve.app"
/bin/cp 'Installeer beeldonderdelen.command' requirements.txt README.md "$PACKAGE/"
/bin/cp scripts/setup-runtime.sh "$PACKAGE/scripts/"
if [[ -f Documentation/TESTS.md ]]; then /bin/cp Documentation/TESTS.md "$PACKAGE/TESTS.md"; /bin/cp Documentation/TESTS.md "$PACKAGE/Documentation/TESTS.md"; fi
if [[ -f Documentation/CHANGELOG.md ]]; then /bin/cp Documentation/CHANGELOG.md "$PACKAGE/CHANGELOG.md"; /bin/cp Documentation/CHANGELOG.md "$PACKAGE/Documentation/CHANGELOG.md"; fi
# GitHub browser uploads and source ZIPs can lose execute bits. Always set them here.
/bin/chmod 755 "$PACKAGE/Installeer beeldonderdelen.command" "$PACKAGE/scripts/setup-runtime.sh"
/usr/bin/codesign --verify --deep --strict "$PACKAGE/Sleeve.app"
ZIP="$DESTINATION/Sleeve-$VERSION-macOS-arm64.zip"
/usr/bin/ditto -c -k --keepParent "$PACKAGE" "$ZIP"
/usr/bin/python3 - "$ZIP" "$VERSION" <<'PY'
import sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.testzip() is None
    prefix='Sleeve-'+sys.argv[2]+'/'
    for name in ['Installeer beeldonderdelen.command','scripts/setup-runtime.sh','Sleeve.app/Contents/MacOS/Sleeve','Sleeve.app/Contents/Resources/Tools/sleeve_ocr']:
        entry=z.getinfo(prefix+name)
        assert entry.external_attr>>16 & 0o111, 'Uitvoerrechten ontbreken: '+name
print('ZIP intact; installer, script en app zijn uitvoerbaar.')
PY
# Verify the permissions after real macOS extraction too.
/usr/bin/ditto -x -k "$ZIP" "$STAGE_ROOT/Uitgepakt"
EXTRACTED="$STAGE_ROOT/Uitgepakt/Sleeve-$VERSION"
[[ -x "$EXTRACTED/Installeer beeldonderdelen.command" ]]
[[ -x "$EXTRACTED/scripts/setup-runtime.sh" ]]
/usr/bin/codesign --verify --deep --strict "$EXTRACTED/Sleeve.app"
/usr/bin/shasum -a 256 "$ZIP"

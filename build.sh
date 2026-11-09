#!/bin/zsh
set -eu
cd "${0:A:h}"
APP="$PWD/Sleeve.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
/usr/bin/swiftc -target arm64-apple-macosx14.0 -swift-version 5 -O -parse-as-library Source/*.swift -o "$APP/Contents/MacOS/Sleeve" -framework SwiftUI -framework AppKit
/usr/bin/rsync -a --delete --delete-excluded --exclude __pycache__ Resources/ "$APP/Contents/Resources/"
/usr/bin/swiftc -target arm64-apple-macosx14.0 -O Resources/Tools/sleeve_ocr.swift -o "$APP/Contents/Resources/Tools/sleeve_ocr" -framework Vision -framework AppKit
/usr/bin/touch "$APP/Contents/Resources/Tools/sleeve_ocr"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Sleeve</string>
<key>CFBundleIdentifier</key><string>com.repriselabs.Sleeve</string>
<key>CFBundleName</key><string>Sleeve</string>
<key>CFBundleDisplayName</key><string>Sleeve</string>
<key>CFBundleIconFile</key><string>Studio</string>
<key>UTExportedTypeDeclarations</key><array><dict><key>UTTypeIdentifier</key><string>com.repriselabs.sleeve-project</string><key>UTTypeDescription</key><string>Sleeve project</string><key>UTTypeConformsTo</key><array><string>com.apple.package</string></array><key>UTTypeTagSpecification</key><dict><key>public.filename-extension</key><array><string>sleeveproject</string></array></dict></dict></array>
<key>UTImportedTypeDeclarations</key><array><dict><key>UTTypeIdentifier</key><string>nl.anoukmusic.scan-project</string><key>UTTypeDescription</key><string>Legacy scan project</string><key>UTTypeConformsTo</key><array><string>com.apple.package</string></array><key>UTTypeTagSpecification</key><dict><key>public.filename-extension</key><array><string>anoukproject</string></array></dict></dict></array>
<key>CFBundleDocumentTypes</key><array><dict><key>CFBundleTypeName</key><string>Sleeve-project</string><key>CFBundleTypeRole</key><string>Editor</string><key>LSItemContentTypes</key><array><string>com.repriselabs.sleeve-project</string><string>nl.anoukmusic.scan-project</string></array><key>LSTypeIsPackage</key><true/></dict></array>
<key>CFBundleVersion</key><string>43</string>
<key>CFBundleShortVersionString</key><string>0.5.15</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>NSHumanReadableCopyright</key><string>Sleeve · Local test version</string>
</dict></plist>
PLIST
/usr/bin/codesign --force --deep --sign - "$APP"
printf '%s\n' "$APP"

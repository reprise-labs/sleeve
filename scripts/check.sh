#!/bin/zsh
set -eu
cd "${0:A:h}/.."
ROOT_DIR="$PWD"
CHECK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sleeve-checks.XXXXXX")"
RUNTIME_PY="$HOME/Library/Application Support/com.repriselabs.Sleeve/Runtime/bin/python3"
if [[ ! -x "$RUNTIME_PY" ]]; then RUNTIME_PY=/usr/bin/python3; fi
export PYTHONDONTWRITEBYTECODE=1
"$RUNTIME_PY" Tests/check_names.py
for check in bridge audits progress cancel circle_edit memory release_advice grouping; do
 "$RUNTIME_PY" "Tests/check_${check}.py" "$CHECK_DIR/$check"
done
mkdir -p "$CHECK_DIR/Checks.app/Contents/MacOS"
ln -s "$ROOT_DIR/Resources" "$CHECK_DIR/Checks.app/Contents/Resources"
cat > "$CHECK_DIR/Checks.app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>CFBundleExecutable</key><string>Checks</string><key>CFBundleIdentifier</key><string>com.repriselabs.sleeve.checks</string><key>CFBundlePackageType</key><string>APPL</string></dict></plist>
PLIST
/usr/bin/swiftc -swift-version 5 -O -parse-as-library Source/StudioModel.swift Source/StudioProjects.swift Source/StudioEditing.swift Source/StudioDiscovery.swift Tests/ProjectQueueChecks.swift -o "$CHECK_DIR/Checks.app/Contents/MacOS/Checks" -framework SwiftUI -framework AppKit
"$CHECK_DIR/Checks.app/Contents/MacOS/Checks" "$CHECK_DIR/project-queue"
/usr/bin/swiftc -swift-version 5 -O -parse-as-library Source/StudioModel.swift Source/StudioProjects.swift Source/StudioEditing.swift Source/StudioDiscovery.swift Tests/EditingChecks.swift -o "$CHECK_DIR/Checks.app/Contents/MacOS/Checks" -framework SwiftUI -framework AppKit
"$CHECK_DIR/Checks.app/Contents/MacOS/Checks" "$CHECK_DIR/editing"
/usr/bin/swiftc -swift-version 5 -O -parse-as-library Source/StudioModel.swift Source/StudioProjects.swift Source/StudioEditing.swift Source/StudioDiscovery.swift Tests/ModelChecks.swift -o "$CHECK_DIR/ModelChecks" -framework SwiftUI -framework AppKit
"$CHECK_DIR/ModelChecks"
print "Controles geslaagd. Verslagen: $CHECK_DIR"

#!/bin/zsh
set -eu
cd "${0:A:h}/.."
RUNTIME_DIR="${1:-$HOME/Library/Application Support/com.repriselabs.Sleeve/Runtime}"
PYTHON_BIN=""
for candidate in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3; do
 if [[ -x "$candidate" ]]; then PYTHON_BIN="$candidate"; break; fi
done
if [[ -z "$PYTHON_BIN" ]]; then
 print 'Installeer eerst Python 3.11 van python.org of via Homebrew (brew install python@3.11).'
 exit 1
fi
print 'Sleeve: afzonderlijke beeldonderdelen installeren…'
"$PYTHON_BIN" -m venv "$RUNTIME_DIR"
"$RUNTIME_DIR/bin/python3" -m pip install --disable-pip-version-check -r requirements.txt
"$RUNTIME_DIR/bin/python3" -c 'import cv2,numpy,PIL; print("Beeldonderdelen gereed:",cv2.__version__,numpy.__version__,PIL.__version__)'
print 'Gereed. Je kunt Sleeve nu openen.'

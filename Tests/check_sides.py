"""Side markers on vinyl labels: explicit syntax, common OCR misreads, never inferred from words."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_alles as SA
line=lambda text:f'0\t0.5\t{text}\n'
assert SA.side_markers(line('SIDE A'))=={'A'}
assert SA.side_markers(line('SDEA'))=={'A'}                 # TGHT: "SIDE A" gelezen als SDEA
assert SA.side_markers(line('S1DE B'))=={'B'}
assert SA.side_markers(line('KANT C'))=={'C'}
assert SA.side_markers(line('- D -'))=={'D'}
assert SA.side_markers(line('SIDE TWO'))=={'B'}
for text in ('INSIDE','SIDEBAR','SIDES','GRADUATED FOOL','ANOUK'):
 assert not SA.side_markers(line(text)),text
print('Kantmarkeringen: expliciet, leesfouten van SIDE en geen woorden als kant.')

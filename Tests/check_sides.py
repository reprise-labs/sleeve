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
print('Kantmarkeringen: expliciet, leesfouten of SIDE en geen woorden als kant.')
# Straight text lines decide the last degrees (HNY side A: Discogs photo 1.5 degrees off).
from PIL import Image, ImageDraw
import scan_cutout as CU
label=Image.new('RGB',(1600,1600),'white');draw=ImageDraw.Draw(label)
for y in range(520,1100,90):draw.rectangle((420,y,1180,y+34),fill='black')
for tilt in (0.0,1.5,-2.5):
    measured=CU.text_line_angle(label.rotate(tilt,resample=Image.BICUBIC,fillcolor='white'))
    assert measured is not None and abs(measured+tilt)<.3,(tilt,measured)
assert CU.text_line_angle(Image.new('RGB',(1600,1600),'white')) is None
print('Straight text lines give the remaining label angle; no lines, no correction.')

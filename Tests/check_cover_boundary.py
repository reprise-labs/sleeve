from pathlib import Path
import sys,numpy as np,cv2
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_stitch as S
x=np.zeros((1000,1000),np.float32);y=x.copy()
x[80:921,80:83]=10;x[80:921,918:921]=10
y[80:83,80:921]=10;y[918:921,80:921]=10
# Strong unrelated scanner and printed-artwork lines must not replace the cover.
x[:,10:13]=100;y[30:33,:]=100
x[150:850,300:303]=150;x[150:850,850:853]=150
y[150:153,300:853]=150;y[847:850,300:853]=150
result=S.find_square(x,y,(5000,5000));mask,angle,box,support,closed=result
assert closed and abs(angle)<.1
left,top,w,h=box
assert 400<left<550 and 400<top<550 and 4000<w<4300 and abs(w-h)<20,box
# A round object alone cannot acquire a closed rectangular identity.
circle=np.zeros((1000,1000),np.float32);cv2.circle(circle,(500,500),420,100,2)
assert not S.find_square(circle,circle,(5000,5000))[4]
print('Closed cover boundary beats scanner/artwork lines; a circle does not become a closed rectangle.')
# A clean already-aligned outer boundary retains the established profile crop.
clean_x=np.zeros((1000,1000),np.float32);clean_y=clean_x.copy()
clean_x[80:921,80:83]=100;clean_x[80:921,918:921]=100
clean_y[80:83,80:921]=100;clean_y[918:921,80:921]=100
assert not S.find_square(clean_x,clean_y,(5000,5000))[4]
print('A clean existing crop is retained.')
# White sheet on the white lid (Deena & Jim lyrics): faint paper edge, a printed
# rule plus a text line form a stronger inner 'square'. Text outside it must
# widen the crop to the paper edge instead of cutting the text away.
rng=np.random.default_rng(5)
sheet_x=np.zeros((1000,1000),np.float32);sheet_y=sheet_x.copy()
sheet_x[60:941,60:62]=6;sheet_x[60:941,938:940]=6;sheet_y[60:62,60:941]=6;sheet_y[938:940,60:941]=6
sheet_x[150:850,250:254]=120;sheet_y[150:154,250:850]=120;sheet_x[150:850,846:850]=120;sheet_y[846:850,250:850]=120
for top,left in [(100,90),(100,300),(400,90),(400,500),(700,300),(860,120),(860,600),(200,870)]:
    block=rng.uniform(20,60,(50,50)).astype(np.float32)
    sheet_x[top:top+50,left:left+50]=block;sheet_y[top:top+50,left:left+50]=block[::-1]
left,top,w,h=S.find_square(sheet_x,sheet_y,(5000,5000))[2]
assert left<350 and top<350 and w>4300 and abs(w-h)<60,(left,top,w,h)
print('Text outside a printed inner frame widens the crop to the faint paper edge.')
# The wider crop must not change the cover/record decision: the support stays
# that of the strong square (a faint paper edge once turned lyric sheets into records).
widened=S.find_square(sheet_x,sheet_y,(5000,5000))[3]
keep=S.INK_OUTSIDE;S.INK_OUTSIDE=1.0
original=S.find_square(sheet_x,sheet_y,(5000,5000))[3];S.INK_OUTSIDE=keep
assert abs(widened-original)<1e-9,(widened,original)
print('Cover/record support is unchanged by the wider crop.')
# Unfolded inside: a 2:1 rectangle, and Sleeve stores it as two squares split on the fold.
wide_x=np.zeros((2000,1000),np.float32);wide_y=wide_x.copy()
wide_x[100:1900,100:103]=40;wide_x[100:1900,897:900]=40;wide_y[100:103,100:900]=40;wide_y[1897:1900,100:900]=40
left,top,w,h=S.find_square(wide_x,wide_y,(5000,10000),ratio=2.0)[2]
assert abs(h/w-2)<.08 and 3700<w<4100,(left,top,w,h)
import tempfile,os
from PIL import Image
sys.path.insert(0,str(root/'Resources/Tools'));import scan_alles as A
with tempfile.TemporaryDirectory() as folder:
    spread=os.path.join(folder,'deel_hoes.png');Image.new('RGB',(400,200),(10,20,30)).save(spread)
    records=[{'name':'deel_hoes.png','part':'unknown','scans':['a','b']}];parts={};doubt=set()
    out=A.split_spreads([(spread,'hoes','a'),('plaat.png','vinyl','b')],parts,doubt,records)
    assert [Image.open(p).size for p,_,_ in out[:2]]==[(200,200),(200,200)] and out[2][1]=='vinyl'
    assert [parts[p] for p,_,_ in out[:2]]==['insert_left','insert_right'] and len(records)==2 and not os.path.exists(spread)
print('A 2:1 inside is found and split into two square panels.')

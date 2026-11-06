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

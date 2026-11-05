"""Physical scan scale must survive different crop sizes; partial outputs cannot all be front."""
from pathlib import Path
from unittest.mock import patch
import sys,json
import numpy as np,cv2
from PIL import Image
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'));import scan_alles as A
work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(214)
base=cv2.GaussianBlur(rng.integers(0,256,(2400,2600,3),dtype=np.uint8),(0,0),1.1)
other=cv2.GaussianBlur(rng.integers(0,256,(2200,1800,3),dtype=np.uint8),(0,0),1.1)
paths=[]
for name,array in [('large',base[:2200,:1800]),('cropped',base[300:2100,200:1800]),('different',other)]:
 path=work/(name+'.png');Image.fromarray(array).save(path,dpi=(1200,1200));paths.append(str(path))
with patch.object(A,'disc_side',return_value=None):groups=A.groups(paths)
assert {frozenset(g) for g in groups}=={frozenset(paths[:2]),frozenset(paths[2:])},groups
sys.path.insert(0,str(root/'Resources'));import studio_bridge as B
folder=work/'outputs';folder.mkdir(exist_ok=True)
for name in ['Scan 12_hoes.png','album_back.png','Scan 1_hoes.png']:Image.new('RGB',(30,30)).save(folder/name)
(folder/'Studio-onderdelen.json').write_text(json.dumps({'files':[{'name':'Scan 1_hoes.png','part':'front','source':paths[0]}]}))
files=B.report_outputs(folder,partial=True);parts={Path(f['path']).name:f['part'] for f in files}
assert parts=={'Scan 12_hoes.png':'unknown','album_back.png':'back','Scan 1_hoes.png':'front'},parts
assert all(f['partial'] for f in files)
try:B.names_preview({'discogs':'https://www.discogs.com/release/33664818'},[{'path':paths[0],'part':'unknown'}]);raise AssertionError('Unknown parts must be chosen before naming')
except ValueError as error:assert 'onderdeel' in str(error)
# If the primary image cannot be downloaded, the first successful secondary
# image must never silently become the primary/front reference.
import scan_discogs as D,io
buffer=io.BytesIO();Image.new('RGB',(60,60),(20,40,60)).save(buffer,format='PNG')
def fetch(url):
 if '/releases/' in url:return json.dumps({'title':'Test','images':[{'uri':'bad','type':'primary'},{'uri':'good','type':'secondary'}]}).encode()
 if url=='bad':raise OSError('unavailable')
 return buffer.getvalue()
with patch.object(D,'get',side_effect=fetch):
 title,images,roles=D.release_images('https://www.discogs.com/release/1',with_metadata=True)
 assert len(images)==1 and roles==['secondary']
 assert len(D.release_images('https://www.discogs.com/release/1'))==2
report={'primary_image_identity_survives_failed_download':True,'different_crop_same_dpi_grouped' :True,'unrelated_image_kept_apart':True,'partial_unnamed_output_not_front':True,'known_output_identity_retained':True,'unknown_names_require_choice':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)

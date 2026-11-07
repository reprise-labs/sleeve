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
except ValueError as error:assert 'part' in str(error)
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
# A red record and dark label can share their grayscale brightness.
from PIL import ImageDraw
from types import SimpleNamespace
label_source=work/'red-label.png';label=Image.new('RGB',(700,700),(255,0,0));ImageDraw.Draw(label).ellipse((250,250,450,450),fill=(76,76,76));label.save(label_source)
preview=cv2.cvtColor(np.array(label),cv2.COLOR_RGB2BGR)
with patch.object(cv2,'HoughCircles',return_value=np.array([[[350.,350.,100.]]],dtype=np.float32)),patch.object(A.CU,'ocr_tool',return_value='mock-ocr'),patch.object(A.CU,'disc_text_angle',return_value=0),patch.object(A.subprocess,'run',side_effect=[SimpleNamespace(stdout='0\t0.5\tUnreadable'),SimpleNamespace(stdout='180\t0.5\tSIDE A')]) as reader:
 assert A.disc_side_from_preview(str(label_source),preview)=='A'
 assert reader.call_count==2
assert A.side_markers('0\t0.5\tSIDE A\n180\t0.5\tSIDE B')=={'A','B'}
assert not A.side_markers('0\t0.5\tALBUM A')
print('Chromatic circular label boundary and high-contrast explicit side retry verified.')
# A cropped fourth corner can have one strong overlap with an existing group.
scores=np.full((7,7),np.nan)
for group in ([0,1,2],[3,4,5]):
 for i in group:
  for j in group:
   if i!=j:scores[i,j]=.92
scores[6,2]=scores[2,6]=.85
paths=[str(i) for i in range(7)]
assert any(set(g)=={'0','1','2','6'} for g in A.cluster_paths(paths,scores))
scores[6,5]=scores[5,6]=.86
assert any(g==['6'] for g in A.cluster_paths(paths,scores)), 'Ambiguous corner must remain separate'
scores[6,5]=scores[5,6]=np.nan;scores[6,0]=scores[0,6]=-1
assert any(g==['6'] for g in A.cluster_paths(paths,scores)), 'Explicit conflict must veto attachment'
# Four quarter-turned parts of one sheet (TGHT 13-16): neighbours overlap well,
# diagonal pairs only in a narrow middle strip. Merge only when every pair is a
# quarter turn; two record sides with the same label design lie at random angles.
values={(0,1):.76,(2,3):.75,(0,2):.53,(1,3):.55,(0,3):.70,(1,2):.70}
scores=np.full((4,4),np.nan)
for (i,j),v in values.items():scores[i,j]=scores[j,i]=v
paths=[str(i) for i in range(4)];quarter=np.ones((4,4),bool)
assert A.cluster_paths(paths,scores,None,quarter)==[['0','1','2','3']]
quarter[0,2]=quarter[2,0]=False
assert len(A.cluster_paths(paths,scores,None,quarter))==2, 'Record sides at random angles stay apart'
assert len(A.cluster_paths(paths,scores))==2
assert A.quarter_turn(np.array([[0.,-1,5],[1,0,3]])) and not A.quarter_turn(cv2.getRotationMatrix2D((0,0),17,1))
print('Quarter-turned sheet parts merge; record sides at random angles stay separate.')
# Unfolded inside (DEENA 37-42): a wide sheet whose ends do not overlap, linked by
# several strong quarter-turn pairs, becomes one group; random angles do not.
scores=np.full((6,6),np.nan)
for (i,j),v in {(0,1):.97,(1,2):.93,(0,4):.90,(1,3):.80,(1,4):.63,(2,3):.85,(3,4):.93,(4,5):.93}.items():scores[i,j]=scores[j,i]=v
paths=[str(i) for i in range(6)];quarter=np.ones((6,6),bool)
assert A.cluster_paths(paths,scores,None,quarter)==[paths]
assert len(A.cluster_paths(paths,scores,None,np.zeros((6,6),bool)))>1
print('Unfolded inside chain merges only through exact quarter turns.')
# A repeated logo cannot identify an entire cover as the front.
first=rng.integers(0,256,(700,700,3),dtype=np.uint8);second=rng.integers(0,256,(700,700,3),dtype=np.uint8)
first=cv2.GaussianBlur(first,(0,0),1);second=cv2.GaussianBlur(second,(0,0),1)
second[20:160,30:660]=first[20:160,30:660]
localized=D.matches(first,[second],with_coverage=True);whole=D.matches(first,[first],with_coverage=True)
assert localized and localized[0][3]<.20 and whole and whole[0][3]>.60
assert len(D.matches(first,[first])[0])==3
print('Unique cropped corner joins its cover; ambiguous/conflicting corners stay separate; shared logo is not a front identity.')

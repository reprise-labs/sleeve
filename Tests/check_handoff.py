"""Lossless stage handoff and fused cover orientation preserve the actual pixels."""
from pathlib import Path
import sys,tempfile,json
import cv2,numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_stitch as ST,scan_cutout as CU
from scan_memory import MappedArrayStore
rng=np.random.default_rng(461)
for h,w in ((319,281),(1667,1703),(2401,3301)):
 rgba=rng.integers(0,256,(h,w,4),dtype=np.uint8);bgra=rgba[:,:,[2,1,0,3]].copy()
 expected=Image.fromarray(rgba).convert('RGB');expected.thumbnail((1600,1600))
 actual=ST.upright_preview(bgra)
 assert np.array_equal(np.asarray(expected),np.asarray(actual)),(h,w,'thumbnail')
view=bgra[2:-3,5:-7]
expected=Image.fromarray(view[:,:,[2,1,0,3]]).convert('RGB');expected.thumbnail((1600,1600))
assert np.array_equal(np.asarray(expected),np.asarray(ST.upright_preview(view)))
with tempfile.TemporaryDirectory() as folder:
 folder=Path(folder);rgba=rng.integers(0,256,(419,381,4),dtype=np.uint8);bgra=rgba[:,:,[2,1,0,3]].copy()
 assert cv2.imwrite(str(folder/'image.tif'),bgra,[cv2.IMWRITE_TIFF_COMPRESSION,1])
 Image.fromarray(rgba).save(folder/'image.png')
 rgb1,a1=CU.load_rgb(folder/'image.tif');rgb2,a2=CU.load_rgb(folder/'image.png')
 assert np.array_equal(np.asarray(rgb1),np.asarray(rgb2))
 assert np.array_equal(np.asarray(a1),np.asarray(a2))
 original=CU.reading_quadrant
 try:
  for q in (None,0,90,180,270):
   CU.reading_quadrant=lambda preview,q=q:q
   with MappedArrayStore(0) as store:
    source=store.put('input',bgra)
    result=ST.upright_output(source,store)
    expected=np.rot90(bgra,-int((q or 0)//90))
    assert np.array_equal(expected,result),q
    result=source=None
 finally:CU.reading_quadrant=original
print(json.dumps({'RGB_thumbnails_identical':True,'lossless_TIFF_and_PNG_cutout_inputs_identical':True,'all_quarter_turns_exact':True}))
# A clean cover does not need the expensive fill budget; a real paper gap does.
clean=np.full((180,200,4),245,np.uint8);clean[:,:,3]=255
called=[];assert np.array_equal(ST.repair_paper_gaps(clean.copy(),lambda:called.append('fill')),clean)
assert not called
hole=clean.copy();hole[84:88,94:98]=0
expected=ST.repair_paper_gaps(hole.copy())
actual=ST.repair_paper_gaps(hole.copy(),lambda:called.append('fill'))
assert called==['fill'] and np.array_equal(expected,actual)
print({'paper_repair_budget_only_when_needed':True,'paper_fill_pixels_unchanged':True})

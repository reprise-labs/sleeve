"""Compact planes and streamed decoders preserve pixel data and clean up on errors."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,cv2
from PIL import Image,ImageCms
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Resources/Tools'))
import scan_stitch as S
from scan_fields import CorrectedImage
from scan_memory import MappedScanStore
cv2.setNumThreads(2);work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(43);raw=rng.integers(50,200,(801,703,3),dtype=np.uint8);y,x=np.mgrid[:801,:703];mask=np.ones(raw.shape[:2],bool)
reference=raw.astype(np.float32)*(.95+.04*x[:,:,None]/703+.02*y[:,:,None]/801).astype(np.float32)
dense,gain=S.gain_correct(raw.astype(np.float32),mask,reference,mask)
plane=S.gain_correct(raw,mask,reference,mask,fit_only=True);image=CorrectedImage(raw);image.gain=plane
assert np.array_equal(gain,plane.rows(0,801)) and np.array_equal(dense,image[:]) and np.array_equal(dense[255:513],image[255:513])
for mode,channels in [('RGB',3),('RGBA',4),('L',None)]:
 shape=(801,703,channels) if channels else (801,703)
 values=rng.integers(0,256,shape,dtype=np.uint8);path=work/(mode+'.png')
 Image.fromarray(values).save(path,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
 original=path.read_bytes();expected=S.load(str(path))
 with MappedScanStore([str(path)],[0],S.load,scratch=work,decode_into=S.load_into) as store:assert np.array_equal(store[0],expected)
 assert not store.maps and path.read_bytes()==original
failed=MappedScanStore([str(path)],[0],S.load,scratch=work,decode_into=lambda p,a:(_ for _ in ()).throw(RuntimeError('failure')))
try:
 with failed:raise AssertionError('Expected failure')
except RuntimeError:pass
assert not failed.maps and not failed.arrays
report={'lighting_fields_and_corrected_bands_exact':True,'streamed_RGB_RGBA_gray_and_ICC_exact':True,'sources_unchanged':True,'failed_stream_closes_maps':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)

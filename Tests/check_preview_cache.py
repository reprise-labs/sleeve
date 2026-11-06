"""Only exact-scale, unchanged-source previews can bypass original decoding."""
from pathlib import Path
from unittest.mock import patch
import os,sys,tempfile,numpy as np
from PIL import Image,ImageCms
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_stitch as ST,scan_previews as C
rng=np.random.default_rng(608)
with tempfile.TemporaryDirectory() as folder:
 folder=Path(folder);cache=folder/'cache'
 for mode in ('RGB','RGBA','L'):
  shape=(433,537) if mode=='L' else (433,537,len(mode))
  path=folder/(mode+'.png');Image.fromarray(rng.integers(0,256,shape,dtype=np.uint8),mode).save(path,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
  for scale in (.257,1.,1.026):
   with patch.dict(os.environ,{'SLEEVE_WORK_PREVIEWS':''}):expected=ST.load(path,scale)
   preview=ST.load_previews(path,[scale])[0]
   assert np.array_equal(expected,preview)
   with patch.dict(os.environ,{'SLEEVE_WORK_PREVIEWS':str(cache)}):
    C.put(path,scale,preview)
    with patch.object(ST,'open_srgb',side_effect=AssertionError('original decoded despite exact cache')):
     assert np.array_equal(ST.load(path,scale),expected)
     link=folder/'source-link.png';link.unlink(missing_ok=True);link.symlink_to(path)
     assert np.array_equal(ST.load(link,scale),expected)
    assert C.get(path,np.nextafter(scale,2.)) is None
    assert np.array_equal(C.get(path,scale,consume=True),expected)
    assert C.get(path,scale) is None
    C.put(path,scale,preview)
    stat=path.stat();os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1))
    assert C.get(path,scale) is None
 print({'cached_pixels_exact':True,'exact_scale_required':True,'source_changes_invalidate':True,'symlink_source_identity_preserved':True})

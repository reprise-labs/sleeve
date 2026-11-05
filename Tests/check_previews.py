"""Two previews decode the source once and preserve the former pixel path."""
from pathlib import Path
from unittest.mock import patch
import sys,json
import numpy as np
from PIL import Image,ImageCms
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Resources/Tools'))
import scan_stitch as S,scan_alles as A
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(127);factors=[.31,.67,1.]
for mode,shape in [('RGB',(359,487,3)),('RGBA',(359,487,4)),('L',(359,487))]:
 path=root/(mode+'.png');Image.fromarray(rng.integers(0,256,shape,dtype=np.uint8)).save(path,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
 expected=[S.load(str(path),f) for f in factors]
 with patch('PIL.Image.open',wraps=Image.open) as opened:
  actual=S.load_previews(str(path),factors)
  assert opened.call_count==1
 assert all(np.array_equal(a,b) for a,b in zip(expected,actual))
source=root/'RGB.png';preview=actual[0]
original_bytes=source.read_bytes()
# Exercise both the in-place native reader and the separate preview transform.
with patch('PIL.ImageCms.getProfileDescription',return_value='Conversion fixture'):
 expected=S.load_previews(str(source),[1.])[0]
 actual=S.load(str(source),1.)
 assert np.array_equal(expected,actual)
assert source.read_bytes()==original_bytes

with patch.object(A,'disc_side_from_preview',return_value='A') as read:
 assert A.disc_side(str(source),preview)=='A'
 assert A.disc_side(str(source),preview)=='A'
 assert read.call_count==1
 Image.new('RGB',(120,110)).save(source)
 assert A.disc_side(str(source),preview)=='A'
 assert read.call_count==2
report={'in_place_profile_pixels_equal_and_source_unchanged':True,'source_decoded_once':True,'RGB_RGBA_gray_and_ICC_previews_exact':True,'side_cache_reused_and_invalidated_on_source_change':True}
(root/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)

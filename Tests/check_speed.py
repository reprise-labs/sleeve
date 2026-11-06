"""Avoid redundant PNG encoding without changing pixels, alpha, DPI or ICC."""
from pathlib import Path
from unittest.mock import patch
import sys,io,json
import numpy as np
from PIL import Image,ImageCms,PngImagePlugin
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_alles as A,scan_discogs as D
work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(85);pixels=rng.integers(0,256,(300,420,4),dtype=np.uint8)
icc=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
info=PngImagePlugin.PngInfo();info.add_text('source-note','preserve')
source=work/'source.png';Image.fromarray(pixels).save(source,dpi=(600,600),icc_profile=icc,pnginfo=info)
original=source.read_bytes();destination=work/'finished.png'
A.save_merged_cover(source,destination)
assert not source.exists() and destination.read_bytes()==original
source.write_bytes(original)
for output in [source,work/'separate.png']:
 with patch.object(sys,'argv',['scan_discogs.py',str(source),str(destination),'--alleen-stand','--uit',str(output)]),patch.object(D,'matches',return_value=[(200,0,np.array([[1.,0.,0.],[0.,1.,0.]]),.8)]):D.main()
 assert output.read_bytes()==original
 with Image.open(output) as image:
  assert np.array_equal(np.array(image),pixels) and image.info['icc_profile']==icc
# Real rotation remains lossless and must not take the unchanged-file path.
rotated=work/'rotated.png';rotation_source=work/'opaque.png'
opaque=pixels.copy();opaque[:,:,3]=255;Image.fromarray(opaque).save(rotation_source)
with patch.object(sys,'argv',['scan_discogs.py',str(rotation_source),str(destination),'--alleen-stand','--uit',str(rotated)]),patch.object(D,'matches',return_value=[(200,0,np.array([[0.,-1.,300.],[1.,0.,0.]]),.8)]):D.main()
with Image.open(rotated) as image:
 assert np.array_equal(np.array(image),np.rot90(opaque,-1))
report={'merged_cover_bytes_preserved':True,'unchanged_orientation_skips_encoding':True,'source_alpha_icc_dpi_preserved':True,'real_quarter_turn_pixels_exact':True}
(work/'RESULTAAT.json').write_text(json.dumps(report,indent=2));print(report)

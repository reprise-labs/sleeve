"""Self-contained image regression checks; no album scans or network needed."""
import json,sys,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[1];work=Path(sys.argv[1]).resolve();work.mkdir(exist_ok=True,parents=True)
sample=root/'Resources/Samples/Voorbeeld_sidea.png';ref=root/'Resources/Samples/Oranje-referentie.png'
row={'path':str(sample),'part':'sidea','reference':False}
def job(req,name,ok=True):
 out=work/name;out.mkdir();req['output']=str(out);f=out/'request.json';f.write_text(json.dumps(req))
 p=subprocess.run([sys.executable,str(root/'Resources/studio_bridge.py'),str(f)],capture_output=True,text=True,timeout=90)
 assert (p.returncode==0)==ok,(p.stdout,p.stderr)
 return [json.loads(s) for s in p.stdout.splitlines() if s.startswith('{')]
events=job({'action':'colour','inputs':[row],'reference':str(ref),'strength':.85,'scope':'vinyl'},'colour')
path=Path(next(e['files'] for e in events if e['event']=='outputs')[0]['path'])
a=np.array(Image.open(sample));b=np.array(Image.open(path));y,x=np.ogrid[:1100,:1100];label=np.hypot(x-550,y-550)<175
assert np.array_equal(a[:,:,3],b[:,:,3]);assert np.array_equal(a[label],b[label]);assert not np.array_equal(a,b)
# Names-copy requests also verify filename safety and actual source identity.
proposal={'source':str(sample),'newName':'demo_sidea.png','size':sample.stat().st_size,'mtime':sample.stat().st_mtime_ns}
events=job({'action':'namesApply','inputs':[row],'proposals':[proposal]},'names')
copy=Path(next(e['files'] for e in events if e['event']=='outputs')[0]['path'])
assert copy.read_bytes()==sample.read_bytes() and copy.stat().st_ino!=sample.stat().st_ino
job({'action':'namesApply','inputs':[row],'proposals':[dict(proposal,newName='../bad.png')]},'unsafe',False)
job({'action':'namesPreview','inputs':[row],'discogs':'https://example.com/release/1'},'url',False)
checks={'label_and_alpha_exact':True,'colour_changes_record':True,'name_copy_independent_and_identical':True,'unsafe_name_and_url_rejected':True}
(work/'RESULTAAT.json').write_text(json.dumps(checks,indent=2));print(checks)

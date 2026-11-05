"""Automatic checks must catch missing areas/ellipses/corruption without visual approvals."""
from pathlib import Path
import sys,json,subprocess
from PIL import Image,ImageDraw
root=Path(sys.argv[1]).resolve();root.mkdir(exist_ok=True,parents=True)
bridge=Path(__file__).resolve().parents[1]/'Resources/studio_bridge.py'
for name,ellipse,gap in [('rond_sidea.png',(2,2,598,598),False),('ovaal_sideb.png',(15,105,585,495),False),('gat_sidec.png',(2,2,598,598),True)]:
 im=Image.new('RGBA',(600,600),(0,0,0,0));d=ImageDraw.Draw(im);d.ellipse(ellipse,fill=(220,110,20,255));d.ellipse((290,290,310,310),fill=(0,0,0,0))
 if gap:d.rectangle((400,170,470,420),fill=(0,0,0,0))
 im.save(root/name)
req={'action':'audit','inputs':[{'path':str(p),'part':'sidea'} for p in root.glob('*.png')]};f=root/'request.json';f.write_text(json.dumps(req));r=subprocess.run([sys.executable,str(bridge),str(f)],capture_output=True,text=True);assert r.returncode==0,r.stdout
rows={Path(e['audits'][0]['path']).name:e['audits'][0] for e in map(json.loads,r.stdout.splitlines()) if e['event']=='audit'}
assert rows['rond_sidea.png']['round'] and rows['rond_sidea.png']['missingInteriorPercent']==0
assert not rows['ovaal_sideb.png']['round']
assert rows['gat_sidec.png']['missingInteriorPercent']>.2
assert all(not row['colourKnown'] for row in rows.values())
(root/'kapot_sidea.png').write_bytes(b'geen PNG')
f.write_text(json.dumps({'action':'audit','inputs':[{'path':str(root/'kapot_sidea.png'),'part':'sidea'}]}));r=subprocess.run([sys.executable,str(bridge),str(f)],capture_output=True,text=True);assert r.returncode!=0
row=next(e['audits'][0] for e in map(json.loads,r.stdout.splitlines()) if e['event']=='audit');assert not row['readable'] and row['signature']
(root/'RESULTAAT.json').write_text(json.dumps({'round_disc_detected':True,'ellipse_rejected':True,'missing_inside_detected':True,'corrupt_png_rejected':True,'unknown_colour_not_presented_as_original':True},indent=2));print('Eindcontroles slagen voor ronde, ovale, onvolledige en beschadigde beelden.')

#!/usr/bin/env python3
"""Local job adapter for Sleeve. JSON lines on stdout; no AI calls."""
import contextlib,ctypes,datetime,functools,io,json,os,re,shutil,signal,subprocess,sys,traceback,urllib.parse,uuid
from pathlib import Path
TOOLS=Path(__file__).parent/'Tools'
try:
 import numpy,cv2,PIL
except ImportError:
 print(json.dumps({'event':'error','message':'De beeldonderdelen ontbreken. Sluit Sleeve en voer eerst Installeer beeldonderdelen.command uit het downloadpakket uit.'}),flush=True)
 raise SystemExit(1)
sys.path.insert(0,str(TOOLS))
PARTS={'front','back','inside','insert','inlay','sidea','sideb','sidec','sided','cd','cd1','cd2','sticker'}
EXTS={'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}
EVENT_STREAM=sys.stdout
CHECKING_AFTER_PROCESS=False
PENDING_COMPLETION=None
JOB_OUTPUTS={}
JOB_WARNINGS=[]
child=None
try:os.setpgid(0,0)
except OSError:pass

def emit(event,**kwargs):
 global PENDING_COMPLETION
 if event=='outputs':
  for file in kwargs.get('files',[]):JOB_OUTPUTS[file['path']]=file
 if event=='warning':JOB_WARNINGS.append(kwargs.get('message',''))
 if event=='complete' and CHECKING_AFTER_PROCESS:
  PENDING_COMPLETION=kwargs;return
 print(json.dumps({'event':event,**kwargs},ensure_ascii=False),file=EVENT_STREAM,flush=True)

def cancel(signum,frame):
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 if child is not None and child.poll() is None:
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 if os.getpgrp()==os.getpid():
  try:os.killpg(os.getpgrp(),signal.SIGTERM)
  except ProcessLookupError:pass
 emit('error',message='Verwerking door jou gestopt. Reeds gemaakte bestanden blijven bewaard.')
 raise SystemExit(130)
signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)

def release_url(value):
 p=urllib.parse.urlparse(value.strip())
 if p.scheme not in ('http','https') or p.hostname not in ('discogs.com','www.discogs.com') or not re.search(r'/(release|master)/\d+',p.path):
  raise ValueError('Vul de Discogs-link van de juiste uitgave in.')
 return value.strip()

def inputs(req):
 rows=req.get('inputs',[])
 if not rows:raise ValueError('Voeg eerst afbeeldingen toe.')
 seen=set();out=[]
 for row in rows:
  p=Path(row['path']).expanduser().resolve()
  if not p.is_file() or p.suffix.lower() not in EXTS:raise ValueError('Deze afbeelding is niet beschikbaar: '+p.name)
  if str(p) in seen:continue
  seen.add(str(p));out.append(dict(row,path=str(p),part=row.get('part','front') if row.get('part') in PARTS else 'front'))
 return out

def job_folder(req,label):
 parent=Path(req['output']).expanduser().resolve()
 if not parent.is_dir():raise ValueError('Kies een bestaande resultatenmap.')
 stamp=datetime.datetime.now().strftime('%Y-%m-%d %H.%M.%S')
 for number in range(1,1000):
  p=parent/(label+' '+stamp+(' '+str(number) if number>1 else ''))
  try:p.mkdir();return p
  except FileExistsError:continue
 raise ValueError('Een nieuwe resultatenmap kon niet worden gemaakt.')

def run(args):
 global child
 emit('status',message='De verwerking loopt op je Mac.')
 stage='Verwerking';index=None;total=None;resource_error=None
 child=subprocess.Popen([sys.executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
 for line in child.stdout:
  text=line.rstrip()
  if text.startswith(('ValueError: Te weinig vrije schijfruimte','ValueError: Een afzonderlijke scan')):resource_error=text.split(': ',1)[1]
  if text:
   emit('log',message=text)
   if any(word in text.lower() for word in ('niet beschikbaar','niet betrouwbaar','mislukt')):emit('warning',message=text)
   m=re.match(r'\[(\d+)/(\d+)\]\s*(.*)',text)
   if m:
    index=int(m[1]);total=int(m[2]);stage='Onderdeel '+m[1]+' van '+m[2]
    emit('progress',fraction=None,index=index,total=total,phase='Uitlijnen en samenvoegen')
    emit('status',message=stage+': '+m[3][:150])
   elif re.fullmatch(r'\s*\d+%',text):
    percent=int(text.strip()[:-1])
    if percent<100:
     emit('progress',fraction=percent/100,index=index,total=total,phase='Beeld opbouwen')
     emit('status',message=stage+' · beeld opbouwen')
    else:
     emit('progress',fraction=None,index=index,total=total,phase='Beeld opslaan')
     emit('status',message=stage+' · beeld opgebouwd; opslaan…')
   elif 'volle resolutie opbouwen:' in text:
    emit('progress',fraction=0,index=index,total=total,phase='Beeld opbouwen')
    emit('status',message=stage+' · '+text)
   elif text.startswith('klaar:'):
    emit('progress',fraction=None,index=index,total=total,phase='Controle en uitsnijden')
    emit('status',message=stage+' · samengestelde scan controleren…')
 rc=child.wait();child=None
 if rc and resource_error:raise RuntimeError(resource_error)
 if rc:raise RuntimeError('De verwerking is gestopt op een controlefout. Bekijk het logboek; er wordt niets als compleet aangemerkt als het dat niet is.')

def profile_for(rows):
 parents={str(Path(row['path']).parent) for row in rows}
 if len(parents)!=1:raise ValueError('Kies scans van één uitgave uit één bronmap. Cd en vinyl apart verwerken.')
 parent=Path(next(iter(parents)));p=parent/'.anouk-referenties.json'
 if not p.exists():return {}
 raw=json.loads(p.read_text());profile={'reference_files':[],'scan_groups':[]}
 basenames={Path(row['path']).name for row in rows}
 for group in raw.get('scan_groups',[]):
  if not isinstance(group,dict) or group.get('part') not in PARTS:continue
  names=[name for name in group.get('files',[]) if isinstance(name,str) and Path(name).name==name and name in basenames]
  if names:profile['scan_groups'].append({'part':group['part'],'files':names})
 return profile

def report_outputs(folder,mapping=None,partial=False,part=None):
 files=[]
 for p in sorted(folder.glob('*')):
  if p.is_file() and not p.name.startswith('.') and p.suffix.lower() in EXTS:
   files.append({'path':str(p),'source':(mapping or {}).get(str(p),''),'partial':partial,**({'part':part} if part else {})})
 emit('outputs',files=files)
 return files

def reference_photos(req,work):
 import scan_discogs as D,scan_naam as N
 url=release_url(req.get('discogs',''))
 emit('status',message='Referentiefoto’s van Discogs ophalen…')
 title,images=D.release_images(url)
 if not images:raise ValueError('Deze uitgave heeft geen beschikbare referentiefoto’s. Kies een eigen foto.')
 import cv2
 refs=[]
 folder=work/'references';folder.mkdir(exist_ok=True)
 for i,img in enumerate(images):
  p=folder/f'Foto {i+1}.png';cv2.imwrite(str(p),img);refs.append({'path':str(p),'title':f'Foto {i+1}'})
 emit('references',files=refs,message=title)

def scan(req,rows,work):
 import scan_naam as N
 selected=[row for row in rows if not row.get('reference')]
 if not selected:raise ValueError('Er zijn alleen referentiebeelden geselecteerd. Voeg ook de oorspronkelijke scans toe.')
 if req.get('discogs') and any(req.get(flag) for flag in ('useNames','useStand','useColour')):
  url=release_url(req['discogs']);match=re.search(r'/(release|master)/(\d+)',urllib.parse.urlparse(url).path)
  emit('status',message='De Discogs-uitgave controleren…')
  metadata=N.get('https://api.discogs.com/'+('masters' if match[1]=='master' else 'releases')+'/'+match[2])
  if match[1]=='master':metadata=N.get('https://api.discogs.com/releases/'+str(metadata['main_release']))
  if (req.get('useStand') or req.get('useColour')) and not metadata.get('images'):
   raise ValueError('Deze uitgave heeft geen referentiefoto’s. Zet stand en hoeskleur uit of kies een andere uitgave.')
 profile=profile_for(rows)
 if req.get('rerunPart'):
  part=req['rerunPart']
  if part not in PARTS:raise ValueError('Kies een geldig onderdeel.')
  if any(row.get('reference') for row in rows):raise ValueError('Kies alleen de bronbeelden voor dit onderdeel.')
  profile={'reference_files':[],'scan_groups':[{'part':part,'files':[Path(row['path']).name for row in rows]}]}
 staging=work/'scans';staging.mkdir()
 for row in rows:
  p=Path(row['path']);os.symlink(p,staging/p.name)
 profile['reference_files']=[Path(row['path']).name for row in rows if row.get('reference')]
 (staging/'.anouk-referenties.json').write_text(json.dumps(profile))
 output=job_folder(req,'Scans');emit('destination',path=str(output))
 cmd=[TOOLS/'scan_alles.py',*[staging/Path(row['path']).name for row in rows],'--geen-vragen','--uit',output]
 if req.get('discogs'):
  url=release_url(req['discogs']);cmd+=['--discogs',url]
  if req.get('useStand'):cmd+=['--discogs-stand']
  if req.get('useColour'):cmd+=['--discogs-kleur']
  if not req.get('useNames',True):cmd+=['--geen-discogs-namen']
 if req.get('variant'):cmd+=['--variant',req['variant']]
 if req.get('rerunPart'):cmd+=['--een-onderdeel']
 try:
  run(cmd)
 except BaseException:
  report_outputs(output,partial=True)
  raise
 files=report_outputs(output,part=req.get('rerunPart'))
 if req.get('rerunPart'):
  if len(files)!=1:raise ValueError('De gekozen scans leveren niet precies één onderdeel op. Controleer de selectie; het vorige resultaat blijft behouden.')
  for file in files:file['part']=req['rerunPart'];JOB_OUTPUTS[file['path']]=file
  emit('outputs',files=files)
 (output/'Studio-verwerking.json').write_text(json.dumps({'action':'scan','inputs':rows,'outputs':files,'discogs':req.get('discogs',''),'one_release_per_batch':True},ensure_ascii=False,indent=2))
 if not files:raise ValueError('Er zijn geen verwerkte afbeeldingen gemaakt. Bekijk het logboek.')
 has_vinyl=any(re.search(r'_side[abcd](?:_\d+)?$',Path(file['path']).stem) for file in files)
 emit('complete',message=f'{len(files)} afbeeldingen verwerkt.'+(' Vinylkleur is nog niet aangepast.' if has_vinyl else ''),path=str(output))

def colour(req,rows,work):
 import scan_colour as C
 ref=Path(req.get('reference','')).expanduser()
 if not ref.is_file():raise ValueError('Kies eerst een eigen foto of een Discogs-referentiefoto.')
 strength=float(req.get('strength',1))
 if not 0<=strength<=1:raise ValueError('De kleursterkte moet tussen 0 en 100% liggen.')
 output=job_folder(req,'Kleurvoorstellen');emit('destination',path=str(output));mapping={}
 scope=req.get('scope','vinyl')
 for i,row in enumerate(rows):
  if row.get('reference'):continue
  src=Path(row['path']);stem=src.stem+'_kleur';dst=output/(stem+'.png');suffix=2
  while dst.exists():dst=output/(stem+'_'+str(suffix)+'.png');suffix+=1
  emit('status',message=f'Kleurvoorstel {i+1} van {len(rows)}: {src.name}')
  temporary=output/('.voorstel-'+uuid.uuid4().hex+'.png')
  if scope=='vinyl':
   from PIL import Image
   import scan_cutout as CU
   with Image.open(src) as im:
    if im.mode!='RGBA':raise ValueError('Gebruik hier een al uitgeknipte vinylplaat met transparantie. Kies voor andere afbeeldingen de passende-foto-methode.')
    probe=im.getchannel('A');probe.thumbnail((1400,1400))
    if CU.already_cut(probe) is None:raise ValueError('Deze afbeelding is nog geen uitgeknipte plaat. Verwerk eerst de scans.')
   with contextlib.redirect_stdout(io.StringIO()) as captured:C.recolor(str(src),str(ref),str(temporary),strength,progress=lambda fraction,phase:emit('progress',fraction=fraction,index=i+1,total=len(rows),phase=phase))
   emit('log',message=captured.getvalue())
  else:
   run([TOOLS/'scan_discogs.py',src,ref,'--alleen-kleur','--uit',temporary])
  os.replace(temporary,dst)
  mapping[str(dst)]=str(src);emit('outputs',files=[{'path':str(dst),'source':str(src),'part':row.get('part','front'),'partial':False}])
 files=report_outputs(output,mapping)
 if not files:raise ValueError('Er zijn geen kleurvoorstellen gemaakt. Kies ook een bronbeeld.')
 reference_folder=output/'Referentie';reference_folder.mkdir()
 shutil.copy2(ref,reference_folder/('Gebruikte-foto'+ref.suffix.lower()))
 (output/'Studio-verwerking.json').write_text(json.dumps({'action':'colour','source_reference':str(ref),'strength':strength,'scope':scope,'inputs':rows,'outputs':files},ensure_ascii=False,indent=2))
 emit('complete',message=f'{len(files)} nieuwe kleurvoorstellen bewaard; de originelen zijn behouden.',path=str(output))

def names_preview(req,rows):
 import scan_naam as N
 emit('status',message='Bestandsnamen van Discogs ophalen…')
 url=release_url(req.get('discogs',''));N.get=functools.lru_cache(maxsize=32)(N.get)
 proposals=[];used=set()
 for row in rows:
  if row.get('reference'):continue
  p=Path(row['path']);part=row['part'];name=N.naam(url,part,req.get('variant',''))+p.suffix.lower()
  base=Path(name);i=2
  while name.casefold() in used:name=base.stem+'_'+str(i)+base.suffix;i+=1
  used.add(name.casefold());st=p.stat();proposals.append({'source':str(p),'newName':name,'part':part,'size':st.st_size,'mtime':st.st_mtime_ns})
 emit('names',rows=proposals);emit('complete',message='Namen opgehaald. Controleer het voorstel vóór het bewaren.')

def independent_copy(source,destination):
 # APFS copy-on-write, with an independent inode. Never use hard links.
 try:
  libc=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
  if libc.clonefile(os.fsencode(source),os.fsencode(destination),0)==0:return
 except (AttributeError,OSError):pass
 shutil.copy2(source,destination)

def names_apply(req,rows):
 proposals=req.get('proposals',[])
 if not proposals:raise ValueError('Haal eerst de voorgestelde namen op.')
 allowed={row['path'] for row in rows};checked=[];used=set()
 for row in proposals:
  src=Path(row['source']).resolve();name=row['newName']
  if str(src) not in allowed or not name or Path(name).name!=name or name in ('.','..') or name.casefold() in used:raise ValueError('Het namenvoorstel is ongeldig. Haal het opnieuw op.')
  if Path(name).suffix.lower() not in EXTS:raise ValueError('De bestandsextensie van het voorstel is ongeldig.')
  st=src.stat()
  if st.st_size!=row['size'] or st.st_mtime_ns!=row['mtime']:raise ValueError('Een bronbestand is gewijzigd. Haal de namen opnieuw op.')
  used.add(name.casefold());checked.append((src,name))
 output=job_folder(req,'Nieuwe namen');emit('destination',path=str(output));mapping={}
 for src,name in checked:
  dst=output/name;temporary=output/('.kopie-'+uuid.uuid4().hex+dst.suffix);independent_copy(src,temporary);os.replace(temporary,dst);mapping[str(dst)]=str(src)
 files=report_outputs(output,mapping)
 (output/'Naamwijzigingen.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2))
 emit('complete',message=f'{len(files)} kopieën met nieuwe namen bewaard.',path=str(output))

def audit_files(req,files,action):
 from PIL import Image
 import numpy as np,cv2
 Image.MAX_IMAGE_PIXELS=None
 audits=[]
 rows={str(Path(row['path']).resolve()):row for row in req.get('inputs',[])}
 for i,file in enumerate(files):
  p=Path(file['path']);row=rows.get(file.get('source',''),rows.get(str(p),{}))
  match=re.search(r'_(side[abcd]|cd\d*|front|back|inside|insert|inlay|sticker)(?:_kleur)?(?:_\d+)?$',p.stem)
  part=file.get('part') or (match[1] if match else row.get('part','front'))
  emit('progress',fraction=None,index=i+1,total=len(files),phase='Eindcontrole')
  emit('status',message=f'Bestandscontrole {i+1} van {len(files)}: {p.name}')
  result={'path':str(p),'readable':False,'part':part,'round':None,'missingInteriorPercent':None,
          'namesApplied':action=='namesApply' or (action=='scan' and bool(req.get('discogs')) and req.get('useNames',True) and not any('naam via Discogs mislukt' in w for w in JOB_WARNINGS)),
          'colourApplied':action=='colour','colourKnown':action in ('scan','colour'),'message':''}
  try:
   before=p.stat()
   result['signature']=f'{before.st_size}:{before.st_mtime_ns//10**9}:{before.st_mtime_ns%10**9}'
   with Image.open(p) as image:result.update(width=image.width,height=image.height);image.verify()
   if part.startswith('side') or part.startswith('cd'):
    with Image.open(p) as image:
     if 'A' in image.getbands():
      image.thumbnail((1400,1400));mask=np.asarray(image.getchannel('A'))>128
      contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
      if not contours:raise ValueError('Geen zichtbare schijf in het transparantiemasker.')
      contour=max(contours,key=cv2.contourArea)
      if len(contour)<5:raise ValueError('De ronde rand kon niet worden gemeten.')
      (cx,cy),(a,b),angle=cv2.fitEllipse(contour)
      result['round']=bool(min(a,b)>0 and max(a,b)/min(a,b)<1.005)
      yy,xx=np.ogrid[:mask.shape[0],:mask.shape[1]];radius=(a+b)/4;distance=np.hypot(xx-cx,yy-cy)
      annulus=(distance>.32*radius)&(distance<.97*radius)
      missing=float(100*(annulus&~mask).sum()/max(1,annulus.sum()))
      result['missingInteriorPercent']=round(missing,4)
      if missing>=.2:result['message']=f'Er ontbreekt circa {missing:.1f}% binnen de schijf; controleer het bronbeeld.'
      elif not result['round']:result['message']='De buitenrand is niet betrouwbaar rond gemeten.'
     else:result['message']='Rondheid niet automatisch meetbaar zonder transparante uitsnede.'
   after=p.stat()
   if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError('Het bestand is tijdens de controle gewijzigd.')
   result['signature']=f'{after.st_size}:{after.st_mtime_ns//10**9}:{after.st_mtime_ns%10**9}'
   result['readable']=True
   if file.get('partial'):result['message']='Afgebroken verwerking; dit resultaat moet opnieuw worden gecontroleerd.'
  except Exception as error:result['message']=str(error)
  audits.append(result);emit('audit',audits=[result])
 if any(not row['readable'] for row in audits):raise ValueError('Een resultaat kon niet volledig worden gelezen. De wachtrij is gepauzeerd; bekijk de eindcontrole.')
 return audits

def fingerprint(path):
 st=Path(path).stat()
 return f'{st.st_size}:{st.st_mtime_ns//10**9}:{st.st_mtime_ns%10**9}'

def manual_crop(req,rows,work):
 import math,numpy as np
 from PIL import Image,ImageOps,PngImagePlugin
 if len(rows)!=1:raise ValueError('Kies precies één bronbeeld voor de ronde uitsnede.')
 row=rows[0];src=Path(row['path']);expected=req.get('sourceSignature')
 if not expected or fingerprint(src)!=expected:raise ValueError('Het bronbeeld is gewijzigd. Open de uitsnede opnieuw.')
 cx,cy,diameter=[float(req[key]) for key in ('cropX','cropY','cropDiameter')]
 if not all(math.isfinite(v) for v in (cx,cy,diameter)) or not(0<=cx<=1 and 0<=cy<=1 and 0<diameter<=1):raise ValueError('De cirkelinstellingen zijn niet geldig.')
 part=req.get('cropPart','')
 if part not in PARTS or not(part.startswith('side') or part.startswith('cd')):raise ValueError('Deze correctie is bedoeld voor ronde cd- en vinylbeelden.')
 output=job_folder(req,'Uitsnede');emit('destination',path=str(output))
 with Image.open(src) as raw:
  raw.load();icc=raw.info.get('icc_profile');dpi=raw.info.get('dpi');image=ImageOps.exif_transpose(raw).convert('RGBA')
  width,height=image.size;size=int(round(diameter*min(width,height)))
  if size<16:raise ValueError('De cirkel is te klein. Kies een grotere diameter.')
  left=int(round(cx*width-size/2));top=int(round(cy*height-size/2))
  if left<0 or top<0 or left+size>width or top+size>height:raise ValueError('De cirkel valt buiten het bronbeeld. Verklein of verplaats hem.')
  cropped=image.crop((left,top,left+size,top+size));alpha=np.array(cropped.getchannel('A'));centre=(size-1)/2;radius=(size-1)/2
  xx=np.arange(size,dtype=np.float64)[None,:]-centre
  for start in range(0,size,256):
   end=min(size,start+256);yy=np.arange(start,end,dtype=np.float64)[:,None]-centre
   edge=np.clip(radius+.5-np.hypot(xx,yy),0,1)
   alpha[start:end]=np.rint(alpha[start:end]*edge).astype(np.uint8)
   emit('progress',fraction=end/size if end<size else None,phase='Ronde uitsnede opbouwen' if end<size else 'Beeld opslaan')
  cropped.putalpha(Image.fromarray(alpha));metadata=PngImagePlugin.PngInfo();metadata.add_text('sleeve_disc_cut','3')
  destination=output/(src.stem+'_uitsnede.png');temporary=output/'.uitsnede.png'
  options={'pnginfo':metadata}
  if icc:options['icc_profile']=icc
  if dpi:options['dpi']=dpi
  cropped.save(temporary,**options)
  if fingerprint(src)!=expected:temporary.unlink();raise ValueError('Het bronbeeld is tijdens het verwerken gewijzigd; de vorige versie blijft behouden.')
  os.replace(temporary,destination)
 files=[{'path':str(destination),'source':str(src),'part':part,'partial':False}]
 emit('outputs',files=files)
 (output/'Studio-verwerking.json').write_text(json.dumps({'action':'manualCrop','inputs':rows,'outputs':files,'circle':{'x':cx,'y':cy,'diameter':diameter},'pixel_box':[left,top,size,size]},indent=2))
 emit('complete',message='Nieuwe ronde uitsnede bewaard. Vergelijk de vorige en nieuwe versie; controleer ook de tekst langs de rand.')


def main():
 global CHECKING_AFTER_PROCESS
 req=json.loads(Path(sys.argv[1]).read_text());work=Path(sys.argv[1]).parent
 import cv2,PIL,numpy
 action=req.get('action')
 if action=='references':reference_photos(req,work);emit('complete',message='Referentiefoto’s geladen. Kies de juiste foto.');return
 rows=inputs(req)
 CHECKING_AFTER_PROCESS=action in ('scan','colour','namesApply','manualCrop')
 if action=='scan':scan(req,rows,work)
 elif action=='colour':colour(req,rows,work)
 elif action=='manualCrop':manual_crop(req,rows,work)
 elif action=='namesPreview':names_preview(req,rows)
 elif action=='namesApply':names_apply(req,rows)
 elif action=='audit':
  audit_files(req,[{'path':row['path'],'source':row.get('source',''),'partial':row.get('partial',False)} for row in rows],'audit')
  emit('complete',message='Bestandscontroles bijgewerkt. Beoordeel de beelden en namen zelf in de eindcontrole.')
 else:raise ValueError('Onbekende actie.')
 if CHECKING_AFTER_PROCESS:
  audit_files(req,list(JOB_OUTPUTS.values()),action);CHECKING_AFTER_PROCESS=False
  emit('complete',**(PENDING_COMPLETION or {'message':'Verwerking afgerond; visuele controle staat nog open.'}))
if __name__=='__main__':
 try:main()
 except SystemExit:raise
 except BaseException as e:
  emit('error',message=str(e));emit('log',message=traceback.format_exc());sys.exit(1)

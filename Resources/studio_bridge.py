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
OCR_CHILDREN=set()
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
 for process in [child,*list(OCR_CHILDREN)]:
  if process is not None and process.poll() is None:
   try:os.killpg(process.pid,signal.SIGTERM)
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
  seen.add(str(p));out.append(dict(row,path=str(p),part=row.get('part','front') if row.get('part') in PARTS|{'unknown'} else 'unknown'))
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
  if text.startswith('SLEEVE_PROGRESS '):
   try:payload=json.loads(text[len('SLEEVE_PROGRESS '):])
   except ValueError:continue
   phase=payload.get('phase','Verwerking');scope=payload.get('scope','component');fraction=payload.get('fraction')
   if not isinstance(fraction,(float,int)) or not 0<=fraction<=1:fraction=None
   if isinstance(payload.get('componentTotal'),int):total=payload['componentTotal']
   component=payload.get('componentIndex',index) if scope=='component' else None
   active=payload.get('activeParts',1)
   current_stage=f'Onderdeel {component} van {total}' if component is not None and total else stage
   emit('progress',fraction=fraction,index=component,total=total,phase=phase,scope=scope,unitsDone=payload.get('unitsDone'),unitsTotal=payload.get('unitsTotal'),completedParts=payload.get('completedParts'),activeParts=active,detail=payload.get('detail',''))
   emit('status',message=(current_stage+' · ' if scope=='component' else '')+phase)
   emit('log',message=phase+(f" · {payload['unitsDone']} / {payload['unitsTotal']}" if payload.get('unitsTotal') else ''))
   continue
  if text.startswith(('ValueError: Te weinig vrije schijfruimte','ValueError: Een afzonderlijke scan','ValueError: Onvolledige schijf','ValueError: De schijf valt buiten')):resource_error=text.split(': ',1)[1]
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
 files=[];components={}
 try:components={r['name']:r for r in json.loads((folder/'Studio-onderdelen.json').read_text()).get('files',[]) if isinstance(r,dict) and 'name' in r}
 except (OSError,ValueError,TypeError):pass
 for p in sorted(folder.glob('*')):
  if p.is_file() and not p.name.startswith('.') and p.suffix.lower() in EXTS:
   match=re.search(r'_(side[abcd]|cd\d*|front|back|inside|insert|inlay|sticker)(?:_kleur)?(?:_\d+)?$',p.stem)
   files.append({'path':str(p),'source':(mapping or {}).get(str(p),components.get(p.name,{}).get('source','')),'partial':partial,'part':part or (match[1] if match else components.get(p.name,{}).get('part','unknown'))})
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
 if req.get('discogs') and any(req.get(flag) for flag in ('useNames','useStand')):
  url=release_url(req['discogs']);match=re.search(r'/(release|master)/(\d+)',urllib.parse.urlparse(url).path)
  emit('status',message='De Discogs-uitgave controleren…')
  metadata=N.get('https://api.discogs.com/'+('masters' if match[1]=='master' else 'releases')+'/'+match[2])
  if match[1]=='master':metadata=N.get('https://api.discogs.com/releases/'+str(metadata['main_release']))
  if req.get('useStand') and not metadata.get('images'):
   raise ValueError('Deze uitgave heeft geen referentiefoto’s. Zet ‘Hoes en plaat juist draaien’ uit of kies een andere uitgave.')
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
 made,name=auto_vinyl_colour(release_url(req['discogs']),files,work) if has_vinyl and req.get('discogs') and req.get('autoColour',True) else ([],'')
 if made:note=f' De plaatkleur week af van Discogs ({name}): {len(made)} kleurvoorstel{"len" if len(made)!=1 else ""} (_kleur) gemaakt met een Discogs-foto; de originelen blijven behouden.'
 elif has_vinyl and name in __import__('scan_colour').HUES:note=f' Vinylkleur komt overeen met Discogs ({name}).'
 else:note=' Vinylkleur is nog niet aangepast.' if has_vinyl else ''
 emit('complete',message=f'{len(files)} afbeeldingen verwerkt.'+note,path=str(output))

def colour_destination(source):
 # Follow only explicit legacy colour provenance, never a raw scan source.
 current=Path(source);seen=set()
 for _ in range(16):
  if str(current) in seen:break
  seen.add(str(current))
  try:
   data=json.loads((current.parent/'Studio-verwerking.json').read_text())
   if data.get('action')!='colour':break
   previous=next((item.get('source') for item in data.get('outputs',[]) if Path(item.get('path',''))==current),None)
   if not previous or not Path(previous).is_file():break
   current=Path(previous)
  except (OSError,ValueError,TypeError):break
 return current.parent

def colour(req,rows,work):
 import scan_colour as C
 ref=Path(req.get('reference','')).expanduser()
 if not ref.is_file():raise ValueError('Kies eerst een eigen foto of een Discogs-referentiefoto.')
 strength=float(req.get('strength',1))
 if not 0<=strength<=1:raise ValueError('De kleursterkte moet tussen 0 en 100% liggen.')
 scope=req.get('scope','vinyl')
 if scope not in ('vinyl','photo'):raise ValueError('Kies vinylplaten of een hoes.')
 rows=[row for row in rows if not row.get('reference')]
 if not rows:raise ValueError('Vink eerst de beelden aan die je wilt aanpassen.')
 if scope=='photo' and len(rows)!=1:raise ValueError('Kies één hoes bij de passende referentiefoto.')
 if scope=='vinyl':
  from PIL import Image
  import scan_cutout as CU
  for row in rows:
   part=row.get('part','unknown')
   if part!='unknown' and not part.startswith('side'):raise ValueError('Bij vinylkleur mogen alleen vinylkanten zijn aangevinkt. Een hoes wordt niet met een plaatfoto aangepast.')
   with Image.open(row['path']) as im:
    if im.mode!='RGBA':raise ValueError('Gebruik hier uitgeknipte vinylplaten met transparantie. Verwerk eerst de scans.')
    probe=im.getchannel('A');probe.thumbnail((1400,1400))
    if CU.already_cut(probe) is None:raise ValueError('Een geselecteerd beeld is nog geen uitgeknipte plaat. Verwerk eerst de scans.')
 output=colour_destination(rows[0]['path']);emit('destination',path=str(output))
 files=[colour_copy(row,ref,strength,scope,i,len(rows)) for i,row in enumerate(rows)]
 if not files:raise ValueError('Er zijn geen kleurvoorstellen gemaakt. Kies ook een bronbeeld.')
 colour_metadata(ref,strength,scope,rows,files)
 emit('complete',message=f"{len(files)} nieuwe kleurkopie{'ën' if len(files)!=1 else ''} opgeslagen. Bekijk Nieuwe kleuren; de originelen blijven behouden.",path=str(output))

def colour_copy(row,ref,strength,scope,i,total):
 import scan_colour as C
 src=Path(row['path']);output=colour_destination(src);stem=re.sub(r'(?:_kleur(?:_\d+)?)+$','',src.stem)+'_kleur';dst=output/(stem+'.png');suffix=2
 while dst.exists():dst=output/(stem+'_'+str(suffix)+'.png');suffix+=1
 emit('status',message=f'Nieuwe kleur voor {i+1} van {total}: {src.name}')
 temporary=output/('.voorstel-'+uuid.uuid4().hex+'.png')
 if scope=='vinyl':
  with contextlib.redirect_stdout(io.StringIO()) as captured:C.recolor(str(src),str(ref),str(temporary),strength,progress=lambda fraction,phase:emit('progress',fraction=fraction,index=i+1,total=total,phase=phase))
  emit('log',message=captured.getvalue())
 else:
  run([TOOLS/'scan_discogs.py',src,ref,'--alleen-kleur','--uit',temporary])
 os.replace(temporary,dst)
 file={'path':str(dst),'source':str(src),'part':row.get('part','unknown'),'partial':False}
 emit('outputs',files=[file])
 return file

def colour_metadata(ref,strength,scope,rows,files,**extra):
 output=colour_destination(rows[0]['path'])
 metadata_folder=output/'.sleeve'/'colour'/uuid.uuid4().hex
 reference_folder=metadata_folder/'Referentie';reference_folder.mkdir(parents=True)
 shutil.copy2(ref,reference_folder/('Gebruikte-foto'+ref.suffix.lower()))
 (metadata_folder/'Studio-verwerking.json').write_text(json.dumps({'action':'colour','source_reference':str(ref),'strength':strength,'scope':scope,'inputs':rows,'outputs':files,**extra},ensure_ascii=False,indent=2))

def discogs_release(url):
 import scan_naam as N
 match=re.search(r'/(release|master)/(\d+)',urllib.parse.urlparse(url).path)
 release=N.get('https://api.discogs.com/'+('masters' if match[1]=='master' else 'releases')+'/'+match[2])
 if match[1]=='master':release=N.get('https://api.discogs.com/releases/'+str(release['main_release']))
 return release

def auto_vinyl_colour(url,files,work):
 """Wijkt de gescande plaatkleur af van de kleurnaam op Discogs (bv. oranje
 vinyl dat de scanner rood maakt)? Dan een _kleur-voorstel naast het origineel,
 met een Discogs-foto waarvan de tint wél bij die naam past."""
 import scan_colour as C,scan_discogs as D,scan_naam as N
 vinyl=[f for f in files if re.search(r'_side[abcd](?:_\d+)?$',Path(f['path']).stem)]
 if not vinyl:return [],''
 emit('status',message='Vinylkleur vergelijken met de kleur op Discogs…')
 try:
  formats=discogs_release(url).get('formats',[])
  words=[(d or '').lower() for f in formats for d in (f.get('descriptions') or [])]+[w.lower() for f in formats for w in re.split(r'[\s,/]+',f.get('text') or '')]
  if any(word in words for word in ('marbled','splatter','swirl','multicolor','multicoloured')):return [],''
  name=next((k for k in N.KLEUREN if k in words),'')
  if name not in C.HUES:return [],name
  _,images=D.release_images(url)
  plan,chosen=C.vinyl_plan([f['path'] for f in vinyl],images,name)
 except (Exception,SystemExit) as error:
  emit('warning',message=f'Vinylkleur niet met Discogs vergeleken ({error}).');return [],''
 if not plan:return [],name
 folder=work/'references';folder.mkdir(exist_ok=True)
 ref=folder/f'Discogs-foto {chosen["photo"]}.png';chosen['reference'].save(ref)
 rows=[f for f in vinyl if f['path'] in plan]
 made=[colour_copy(row,ref,1.0,'vinyl',i,len(rows)) for i,row in enumerate(rows)]
 colour_metadata(ref,1.0,'vinyl',rows,made,automatic={'discogs_colour':name,'discogs_photo':chosen['photo']})
 return made,name

def names_preview(req,rows):
 import scan_naam as N
 emit('status',message='Bestandsnamen van Discogs ophalen…')
 url=release_url(req.get('discogs',''));N.get=functools.lru_cache(maxsize=32)(N.get)
 proposals=[];used=set()
 for row in rows:
  if row.get('reference'):continue
  p=Path(row['path']);part=row['part']
  if part not in PARTS:raise ValueError('Kies eerst het onderdeel bij elk beeld voordat je bestandsnamen laat voorstellen.')
  name=N.naam(url,part,req.get('variant',''))+p.suffix.lower()
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

def component_quality(path):
 """Meldingen uit het samenvoegen (naad door verschoven tekst, labelstand
 niet met Discogs gecontroleerd) die bij dit resultaat horen. Een _kleur-kopie
 krijgt de meldingen van het origineel."""
 path=Path(path);base=re.sub(r'_kleur(?:_\d+)?$','',path.stem)+path.suffix
 for folder in (path.parent,colour_destination(path)):
  try:records=json.loads((folder/'Studio-onderdelen.json').read_text()).get('files',[])
  except (OSError,ValueError,TypeError):continue
  for record in records:
   if isinstance(record,dict) and record.get('name') in (path.name,base):
    return [str(note) for note in record.get('quality',[]) if note]
 return []

def audit_files(req,files,action):
 from PIL import Image
 import numpy as np,cv2
 Image.MAX_IMAGE_PIXELS=None
 audits=[]
 rows={str(Path(row['path']).resolve()):row for row in req.get('inputs',[])}
 for i,file in enumerate(files):
  p=Path(file['path']);row=rows.get(file.get('source',''),rows.get(str(p),{}))
  match=re.search(r'_(side[abcd]|cd\d*|front|back|inside|insert|inlay|sticker)(?:_kleur)?(?:_\d+)?$',p.stem)
  part=file.get('part') or (match[1] if match else row.get('part','unknown'))
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
   notes=component_quality(p)
   if notes:result['message']=' '.join([result['message']]+notes if result['message'] else notes)
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
 if action=='releaseAdvice':
  import scan_release_advice as A
  def recognize_command(command):
   # Wordt vanuit twee threads tegelijk aangeroepen: elk een eigen proces,
   # niet de gedeelde 'child' (die werd door de andere thread overschreven).
   process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   OCR_CHILDREN.add(process)
   try:
    stdout,_=process.communicate(timeout=20)
    if process.returncode:raise ValueError('Tekstherkenning niet gelukt')
    return stdout
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGKILL);process.communicate();raise
   finally:OCR_CHILDREN.discard(process)
  emit('releaseAdvice',advice=A.advice(req,inputs(req),recognize_command));emit('complete',message='Releasevoorstellen opgehaald.');return
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

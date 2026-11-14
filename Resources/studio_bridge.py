#!/usr/bin/env python3
"""Local job adapter for Sleeve. JSON lines on stdout; no AI calls."""
import contextlib,ctypes,threading,datetime,functools,io,json,os,re,shutil,signal,subprocess,sys,traceback,urllib.parse,uuid
from pathlib import Path
TOOLS=Path(__file__).parent/'Tools'
try:
 import numpy,cv2,PIL
except ImportError:
 print(json.dumps({'event':'error','message':'The image components are missing. Quit Sleeve and first run Installeer beeldonderdelen.command from the download package.'}),flush=True)
 raise SystemExit(1)
sys.path.insert(0,str(TOOLS))
PARTS={'front','back','inside','insert','insert_left','insert_right','inlay','sidea','sideb','sidec','sided','cd','cd1','cd2','sticker'}
EXTS={'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}
EVENT_STREAM=sys.stdout
CHECKING_AFTER_PROCESS=False
PENDING_COMPLETION=None
JOB_OUTPUTS={}
JOB_WARNINGS=[]
child=None
OCR_CHILDREN=set()
EMIT_LOCK=threading.Lock()
try:os.setpgid(0,0)
except OSError:pass

# Feit: dezelfde hoes twee keer scannen gaf tot ~2 mm verschil (Fire-back, twee rondes: 312,1 en
# 310,4 mm; karton ligt niet elke keer even plat). Kleinere verschillen zijn meetruis, geen snijfout.
SAME_PRINT_MM=2.5
# Feit: inserts van één release zijn soms verschillende vellen (boekje 291 mm, los vel 300 mm: 9 mm verschil).
# Scheelt het minder dan dit, dan is het eerder hetzelfde vel dat anders gesneden is.
SAME_SHEET_MM=6.0

def emit(event,**kwargs):
 global PENDING_COMPLETION
 if event=='outputs':
  for file in kwargs.get('files',[]):JOB_OUTPUTS[file['path']]=file
 if event=='warning':JOB_WARNINGS.append(kwargs.get('message',''))
 if event=='complete' and CHECKING_AFTER_PROCESS:
  PENDING_COMPLETION=kwargs;return
 # één schrijfactie per bericht, onder een slot: onderdelen lopen parallel en mogen hun regels
 # niet door elkaar schrijven (dan kan de app het bericht niet lezen en mist er een onderdeel)
 line=json.dumps({'event':event,**kwargs},ensure_ascii=False)+'\n'
 with EMIT_LOCK:
  EVENT_STREAM.write(line);EVENT_STREAM.flush()

def cancel(signum,frame):
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 for process in [child,*list(OCR_CHILDREN)]:
  if process is not None and process.poll() is None:
   try:os.killpg(process.pid,signal.SIGTERM)
   except ProcessLookupError:pass
 if os.getpgrp()==os.getpid():
  try:os.killpg(os.getpgrp(),signal.SIGTERM)
  except ProcessLookupError:pass
 emit('error',message='Processing stopped by you. Files already made are kept.')
 raise SystemExit(130)
signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)

def release_url(value):
 p=urllib.parse.urlparse(value.strip())
 if p.scheme not in ('http','https') or p.hostname not in ('discogs.com','www.discogs.com') or not re.search(r'/(release|master)/\d+',p.path):
  raise ValueError('Enter the Discogs link of the right release.')
 return value.strip()

def inputs(req):
 rows=req.get('inputs',[])
 if not rows:raise ValueError('Add images first.')
 seen=set();out=[]
 for row in rows:
  p=Path(row['path']).expanduser().resolve()
  if not p.is_file() or p.suffix.lower() not in EXTS:raise ValueError('This image isn’t available: '+p.name)
  if str(p) in seen:continue
  seen.add(str(p));out.append(dict(row,path=str(p),part=row.get('part','front') if row.get('part') in PARTS|{'unknown'} else 'unknown'))
 return out

def job_folder(req,label):
 parent=Path(req['output']).expanduser().resolve()
 if not parent.is_dir():raise ValueError('Choose an existing output folder.')
 stamp=datetime.datetime.now().strftime('%Y-%m-%d %H.%M.%S')
 for number in range(1,1000):
  p=parent/(label+' '+stamp+(' '+str(number) if number>1 else ''))
  try:p.mkdir();return p
  except FileExistsError:continue
 raise ValueError('A new output folder couldn’t be created.')

def run(args):
 global child
 emit('status',message='Processing runs on your Mac.')
 stage='Processing';index=None;total=None;resource_error=None
 child=subprocess.Popen([sys.executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
 for line in child.stdout:
  text=line.rstrip()
  if text.startswith('SLEEVE_PROGRESS '):
   try:payload=json.loads(text[len('SLEEVE_PROGRESS '):])
   except ValueError:continue
   phase=payload.get('phase','Processing');scope=payload.get('scope','component');fraction=payload.get('fraction')
   if not isinstance(fraction,(float,int)) or not 0<=fraction<=1:fraction=None
   if isinstance(payload.get('componentTotal'),int):total=payload['componentTotal']
   component=payload.get('componentIndex',index) if scope=='component' else None
   active=payload.get('activeParts',1)
   current_stage=f'Part {component} of {total}' if component is not None and total else stage
   emit('progress',fraction=fraction,index=component,total=total,phase=phase,scope=scope,unitsDone=payload.get('unitsDone'),unitsTotal=payload.get('unitsTotal'),completedParts=payload.get('completedParts'),activeParts=active,detail=payload.get('detail',''))
   emit('status',message=(current_stage+' · ' if scope=='component' else '')+phase)
   emit('log',message=phase+(f" · {payload['unitsDone']} / {payload['unitsTotal']}" if payload.get('unitsTotal') else ''))
   continue
  if text.startswith(('ValueError: Not enough free disk space','ValueError: A single scan','ValueError: Incomplete disc','ValueError: The disc extends beyond')):resource_error=text.split(': ',1)[1]
  if text:
   emit('log',message=text)
   if any(word in text.lower() for word in ('not available','not reliabl','failed')):emit('warning',message=text)
   m=re.match(r'\[(\d+)/(\d+)\]\s*(.*)',text)
   if m:
    index=int(m[1]);total=int(m[2]);stage='Part '+m[1]+' of '+m[2]
    emit('progress',fraction=None,index=index,total=total,phase='Aligning and merging')
    emit('status',message=stage+': '+m[3][:150])
   elif re.fullmatch(r'\s*\d+%',text):
    percent=int(text.strip()[:-1])
    if percent<100:
     emit('progress',fraction=percent/100,index=index,total=total,phase='Building image')
     emit('status',message=stage+' · building image')
    else:
     emit('progress',fraction=None,index=index,total=total,phase='Saving image')
     emit('status',message=stage+' · image built; saving…')
   elif 'building full resolution:' in text:
    emit('progress',fraction=0,index=index,total=total,phase='Building image')
    emit('status',message=stage+' · '+text)
   elif text.startswith('done:'):
    emit('progress',fraction=None,index=index,total=total,phase='Checking and cutting out')
    emit('status',message=stage+' · checking merged scan…')
 rc=child.wait();child=None
 if rc and resource_error:raise RuntimeError(resource_error)
 if rc:raise RuntimeError('Processing stopped on a check error. See the log; nothing is marked complete unless it is.')

def layout_from_groups(rows):
 """Vakken uit de app: scans die je samen in één vak sleepte, vormen één onderdeel.
 Het onderdeel van het vak (Front, Side A …) staat vast; zonder onderdeel bepaalt
 Sleeve de soort zelf. Referenties doen niet mee."""
 groups={}
 for row in rows:
  key=str(row.get('group') or '').strip()
  if key and not row.get('reference'):groups.setdefault(key,[]).append(row)
 layout=[]
 for members in groups.values():
  parts={m.get('part') for m in members if m.get('part') in PARTS}
  layout.append({'part':parts.pop() if len(parts)==1 else '','files':[Path(m['path']).name for m in members]})
 return layout

def remember_layout(rows,layout):
 """Indeling per bronmap onthouden (.anouk-referenties.json), zodat de vakken de
 volgende keer meteen gevuld zijn. Lukt schrijven niet (alleen-lezen), dan niet."""
 parent=Path(rows[0]['path']).parent;p=parent/'.anouk-referenties.json'
 try:
  data=json.loads(p.read_text()) if p.exists() else {}
  data['scan_groups']=layout
  data['reference_files']=[Path(r['path']).name for r in rows if r.get('reference')]
  p.write_text(json.dumps(data,ensure_ascii=False,indent=1))
 except (OSError,ValueError):
  emit('log',message='Layout not remembered (folder not writable).')

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
 emit('status',message='Fetching reference photos from Discogs…')
 title,images=D.release_images(url)
 if not images:raise ValueError('This release has no reference photos available. Choose your own photo.')
 import cv2
 refs=[]
 folder=work/'references';folder.mkdir(exist_ok=True)
 for i,img in enumerate(images):
  p=folder/f'Foto {i+1}.png';cv2.imwrite(str(p),img);refs.append({'path':str(p),'title':f'Foto {i+1}'})
 emit('references',files=refs,message=title)

def part_time_limit(files):
 """Feit: een onderdeel is in minuten klaar; hoe lang hangt af van de hoeveelheid beeld. Duurt het
 veel langer (15 minuten plus 1,5 s per megapixel aan scans), dan hangt er iets en komt het niet
 meer goed: stoppen en melden, zodat de andere onderdelen en de app doorgaan."""
 if os.environ.get('SLEEVE_PART_TIMEOUT'):return float(os.environ['SLEEVE_PART_TIMEOUT'])
 mpx=0.0
 try:
  from PIL import Image;Image.MAX_IMAGE_PIXELS=None
  for f in files:
   with Image.open(f) as im:mpx+=im.size[0]*im.size[1]/1e6
 except Exception:pass
 return 900+1.5*mpx

def release_format(req,parts):
 """Feit: alle onderdelen van één release hebben hetzelfde formaat (een cd-vak = een cd), en de
 verpakking (Discogs of jouw keuze) bepaalt de maten bij een cd."""
 fmt=req.get('format') if req.get('format') in ('cd','vinyl') else ('cd' if any(part.startswith('cd') for part in parts) else '')
 pk=req.get('packaging') or ''
 if pk in ('','auto') and req.get('discogs'):
  try:
   import scan_release as RI;pk=RI.info(release_url(req['discogs'])).get('packaging','')
  except Exception as e:emit('log',message=f'Packaging not read from Discogs: {e}')
 if pk in ('slimjewel','superjewel','digipak','cardsleeve') and (fmt=='cd' or req.get('format')=='cd' or (not fmt and req.get('mediaKind')=='cd')):fmt='cd-'+pk
 return fmt

def run_facts(output):
 """Formaat en resolutie waarmee deze map gemaakt is (voor een beslissing achteraf: zelfde feiten)."""
 try:
  data=json.loads((Path(output)/'Studio-verwerking.json').read_text())
  if data.get('route')=='feiten' and 'format' in data:return data['format'],float(data.get('release_dpi') or 0.0)
 except (OSError,ValueError,TypeError):pass
 return None

def feiten_part(req,part,files,output,work,decision=None,fmt='',release_dpi=0.0,target=None):
 """Eén onderdeel door de feitenroute (scan_feitenroute.py); geeft de uitkomst."""
 cmd=[sys.executable,str(TOOLS/'scan_feitenroute.py'),'--part',part,'--out',str(output),'--work',str(work),*files]
 if req.get('discogs'):cmd+=['--discogs',release_url(req['discogs'])]
 if req.get('variant'):cmd+=['--variant',req['variant']]
 if decision is not None:cmd+=['--decision',json.dumps(decision)]
 if str(req.get('year') or '').strip().isdigit():cmd+=['--year',str(req['year']).strip()]
 if fmt:cmd+=['--format',fmt]
 if release_dpi:cmd+=['--release-dpi',str(release_dpi)]
 if target:cmd+=['--target',str(target)]
 work.mkdir(parents=True,exist_ok=True)
 process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 OCR_CHILDREN.add(process)
 err_lines=[]
 def read_err():
  # stap voor stap laten zien wat er gebeurt (SLEEVE_STEP-regels van de route)
  for line in process.stderr:
   if line.startswith('SLEEVE_STEP '):
    emit('status',message=f'{part}: {line[12:].strip()}…')
   else:err_lines.append(line)
 reader=threading.Thread(target=read_err,daemon=True);reader.start()
 limit=part_time_limit(files);timed_out=threading.Event()
 def stop():
  timed_out.set()
  try:os.killpg(process.pid,signal.SIGKILL)               # het onderdeel en alles wat het gestart heeft
  except (ProcessLookupError,PermissionError):pass
 timer=threading.Timer(limit,stop);timer.daemon=True;timer.start()
 try:out=process.stdout.read();process.wait();reader.join(10)
 finally:
  timer.cancel();OCR_CHILDREN.discard(process);shutil.rmtree(work,ignore_errors=True)
 if timed_out.is_set():
  return {'part':part,'scans':files,'verdict':'FOUT','why':[f'stopped after {limit/60:.0f} minutes without a result (it hung). The other parts went on; process this part again.']}
 err=''.join(err_lines)
 for line in (err or '').splitlines()[-5:]:emit('log',message=line)
 try:return json.loads(out.strip().splitlines()[-1])
 except (ValueError,IndexError):return {'part':part,'scans':files,'verdict':'FOUT','why':[(err or 'no result').strip().splitlines()[-1] if (err or '').strip() else 'no result']}

def feiten_file(result):
 return {'path':result.get('path',''),'source':(result.get('scans') or [''])[0],'partial':False,'part':result.get('part','unknown'),
         'verdict':result.get('verdict'),'why':result.get('why',[]),'choices':result.get('choices',[]),'scans':result.get('scans',[]),
         'message':result.get('message'),'applied':result.get('applied')}

def warm_up_text_recognition(work):
 """Het nauwkeurige tekstmodel van macOS op de achtergrond laten voorbereiden (de eerste keer
 ±1 minuut) terwijl het samenvoegen en uitsnijden lopen. Lukt het, dan mag de route het weer gebruiken."""
 def run():
  try:
   import numpy as np,cv2,tempfile
   img=np.full((80,400,3),255,np.uint8);cv2.putText(img,'Sleeve warm up',(10,55),0,1.2,(0,0,0),2)
   p=work/'warmup.png';cv2.imwrite(str(p),img)
   process=subprocess.Popen([str(TOOLS/'sleeve_ocr'),str(p),'--boxes'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
   OCR_CHILDREN.add(process)
   try:
    if process.wait(timeout=180)==0:
     with contextlib.suppress(OSError):os.remove(os.path.join(tempfile.gettempdir(),'sleeve-accurate-ocr-slow'))
   except subprocess.TimeoutExpired:process.kill()
   finally:OCR_CHILDREN.discard(process)
  except Exception:pass
 threading.Thread(target=run,daemon=True).start()


def feiten_scan(req,rows,layout,work):
 """Feitenroute: elk vak is één onderdeel; uitsnijden en rechtop op feiten, goed of twijfel."""
 warm_up_text_recognition(work)
 import concurrent.futures as CF
 by_name={Path(r['path']).name:r['path'] for r in rows}
 jobs=[]
 for group in layout:
  if group.get('part') not in PARTS:raise ValueError('Give every slot its part (Front, Back, Side A …) before processing.')
  jobs.append((group['part'],[by_name[name] for name in group['files']]))
 # Feit (Discogs): welke plaatkanten de release heeft (tracklist A1, B1 …). Ontbreekt er
 # een kant in je vakken, dan melden; niets raden.
 missing=[]
 if req.get('discogs'):
  try:
   import scan_naam as N
   m=re.search(r'/(release|master)/(\d+)',release_url(req['discogs']))
   r=N.get('https://api.discogs.com/'+('masters' if m[1]=='master' else 'releases')+'/'+m[2])
   if m[1]=='master':r=N.get('https://api.discogs.com/releases/'+str(r['main_release']))
   if any((f.get('name') or '').lower()=='vinyl' for f in r.get('formats',[])):
    sides={t['position'][0].lower() for t in r.get('tracklist',[]) if t.get('position') and t['position'][0].isalpha()}
    have={part[4:] for part,_ in jobs if part.startswith('side')}
    missing=sorted(sides-have)
    if missing:emit('warning',message='Discogs lists side '+', '.join(x.upper() for x in sorted(sides))+'; no slot for side '+', '.join(x.upper() for x in missing)+'.')
  except Exception as e:emit('log',message=f'Sides not checked against Discogs: {e}')
 # hoezen en vellen eerst: daarop meet Sleeve het lichtpatroon van het glas, dat de platen daarna gebruiken
 jobs.sort(key=lambda j:j[0].startswith(('side','cd')))
 output=job_folder(req,'Scans');emit('destination',path=str(output))
 done=0;results=[]
 emit('progress',fraction=0,index=None,total=len(jobs),phase='Processing parts',scope='preparation',completedParts=0,activeParts=min(2,len(jobs)))
 # 1200 dpi: één onderdeel tegelijk (geheugen en tijdelijke schijfruimte); anders twee
 import scan_dpi as SD
 dpis=[SD.read(f) for _,files in jobs for f in files]
 good=sorted(d for d in dpis if d)
 release_dpi=good[len(good)//2] if good else 0.0     # feit: zelfde release, zelfde scanner
 if any(not d for d in dpis) and release_dpi:emit('log',message=f'Some scans have no reliable resolution stored; using {release_dpi:.0f} dpi from the other scans of this release.')
 workers=1 if (release_dpi or 300)>=900 else 2
 with CF.ThreadPoolExecutor(max_workers=workers) as pool:
  fmt=release_format(req,[part for part,_ in jobs])
  run_format=fmt
  futures={pool.submit(feiten_part,req,part,files,output,work/f'part{i}-{uuid.uuid4().hex[:8]}',None,fmt,release_dpi):part for i,(part,files) in enumerate(jobs)}
  for future in CF.as_completed(futures):
   result=future.result();done+=1;results.append(result)
   emit('status',message=f'{futures[future]}: {result.get("verdict")} ({done} of {len(jobs)})')
   emit('progress',fraction=done/len(jobs),index=None,total=len(jobs),phase='Processing parts',scope='preparation',completedParts=done,activeParts=min(2,len(jobs)-done))
   if result.get('panels'):emit('outputs',files=[dict(feiten_file(result),path=q['path'],part=q['part']) for q in result['panels']])
   elif result.get('path'):emit('outputs',files=[feiten_file(result)])
   for why in result.get('why',[]):emit('warning',message=f'{futures[future]}: {why}')
 # Feit: voor- en achterkant zijn dezelfde hoes, dus even groot; de inserts van één release
 # zijn hetzelfde drukwerk, dus even groot. Wijkt er één af, dan twijfel (met de maten).
 def dims(r):return sorted(r.get('size_mm') or [0,0])
 changed=[]
 def doubt(r,msg):
  r['verdict']='TWIJFEL';r.setdefault('why',[]).append(msg)
  if 'keep' not in (r.get('choices') or []):r['choices']=['keep']+list(r.get('choices') or [])
  changed.append(r)
 by_part={}
 for r in results:
  if r.get('path') and not r.get('panels'):by_part.setdefault(r.get('part'),[]).append(r)
 fr,bk=(by_part.get('front') or [None])[0],(by_part.get('back') or [None])[0]
 is_cd=str(fmt).startswith('cd') or any(str(p).startswith('cd') for p in by_part)
 if fr and bk and fr.get('size_mm') and bk.get('size_mm') and not is_cd:   # cd: boekje en achterkant zijn niet even groot
  a,b=dims(fr),dims(bk)
  if max(abs(a[0]-b[0]),abs(a[1]-b[1]))>SAME_PRINT_MM:
   m=f'front {a[1]} x {a[0]} mm and back {b[1]} x {b[0]} mm differ; they are the same sleeve, so one side is cut at a print edge'
   doubt(fr,m);doubt(bk,m)
 # Feit: twee kanten van hetzelfde vel zijn even groot; verschillende vellen (een boekje van 29 cm en
 # een los vel van 30 cm) hoeven dat niet te zijn. Twijfel alleen als twee inserts bíjna even groot
 # zijn (verschil tussen de meetruis en SAME_SHEET_MM): dan is het hetzelfde vel, anders gesneden.
 ins=by_part.get('insert') or []
 for i,r in enumerate(ins):
  d=dims(r)
  if any(max(abs(d[0]-o[0]),abs(d[1]-o[1]))<=SAME_PRINT_MM for o in (dims(x) for j,x in enumerate(ins) if j!=i)):continue   # er is een insert van dezelfde maat
  near=[x for j,x in enumerate(ins) if j!=i and max(abs(d[0]-dims(x)[0]),abs(d[1]-dims(x)[1]))<=SAME_SHEET_MM]
  if near:
   o=dims(near[0])
   doubt(r,f'this insert is {d[1]} x {d[0]} mm, another is {o[1]} x {o[0]} mm: almost the same, so probably the same sheet cut differently')
 if changed:emit('outputs',files=[feiten_file(r) for r in {id(r):r for r in changed}.values()])
 # Feit: kant A en B (C en D) zijn dezelfde plaat: kleurverschil van de scanner gelijktrekken
 made={r['part']:r['path'] for r in results if r.get('path') and r.get('part','').startswith('side')}
 for x,y in (('sidea','sideb'),('sidec','sided')):
  if x in made and y in made:
   emit('status',message=f'Same record, same colour: matching {x} and {y}')
   try:
    cp=subprocess.run([sys.executable,str(TOOLS/'scan_kleur_kanten.py'),made[x],made[y]],capture_output=True,text=True,timeout=600)
    for line in (cp.stdout+cp.stderr).splitlines()[-3:]:emit('log',message=line)
   except subprocess.TimeoutExpired:
    emit('warning',message=f'{x} and {y}: matching the colour took too long and was skipped; both sides are kept as scanned.')
 files=[]
 for r in results:
  if r.get('panels'):files+=[dict(feiten_file(r),path=q['path'],part=q['part']) for q in r['panels']]
  elif r.get('path'):files.append(feiten_file(r))
 (output/'Studio-verwerking.json').write_text(json.dumps({'action':'scan','route':'feiten','format':run_format,'release_dpi':release_dpi,'inputs':rows,'outputs':files,'results':results,'discogs':req.get('discogs','')},ensure_ascii=False,indent=2))
 if not files:raise ValueError('No processed images were made: '+' '.join(f"{r.get('part')}: {'; '.join(r.get('why') or ['no reason'])}." for r in results))
 # Een onderdeel dat niet gemaakt kon worden, heeft geen bestand en staat dus niet in de eindcontrole:
 # daarom hier hardop melden, met de reden (nooit stil laten verdwijnen).
 failed=[r for r in results if not r.get('path') and not r.get('panels')]
 good=sum(r.get('verdict')=='GOED' for r in results);doubt=len(results)-good-len(failed)
 note=(' Missing according to Discogs: side '+', '.join(x.upper() for x in missing)+'.') if missing else ''
 fail_note=''.join(f" NOT MADE: {r.get('part')} – {'; '.join(r.get('why') or ['no reason given'])}." for r in failed)
 for r in failed:emit('warning',message=f"NOT MADE: {r.get('part')} – {'; '.join(r.get('why') or ['no reason given'])}")
 emit('complete',message=f'{len(results)} parts processed: {good} good'+(f', {doubt} in doubt' if doubt else '')+(f', {len(failed)} not made' if failed else '')+('. Decide in the Final Check.' if doubt else '.')+fail_note+note,path=str(output))

def feiten_decide(req,work):
 """Beslissing van de gebruiker voor één onderdeel: onthouden en dat onderdeel opnieuw maken."""
 part=req.get('part');files=req.get('scans') or []
 if part not in PARTS or not files:raise ValueError('Choose a part to decide on.')
 choice=req.get('choice','');decision={}
 if choice in ('keep','square'):decision['crop']=choice
 elif choice.startswith('rotate'):decision['rotate']=int(choice[6:] or 0)
 else:raise ValueError('Unknown choice.')
 old=Path(req.get('path','')) if req.get('path') else None
 if choice=='keep' and old and old.exists():
  # "Zo laten" = klaar: het bestaande bestand blijft precies zoals het is, niets opnieuw maken.
  sys.path.insert(0,str(TOOLS));import scan_feitenroute as FR
  FR.save_decision(os.path.dirname(files[0]),files,part,decision)
  result={'path':str(old),'part':part,'scans':files,'verdict':'GOED','why':[],'choices':[],'applied':'kept as it is (your decision)'}
  emit('outputs',files=[dict(feiten_file(result),replace=True)])
  emit('complete',message=f'{part}: kept as it is. Nothing changed.');return
 output=old.parent if old else Path(req['output'])
 # Feit: een beslissing verandert alleen wat jij kiest. Het onderdeel wordt opnieuw gemaakt met
 # hetzelfde formaat, dezelfde verpakking en dezelfde resolutie als de eerste keer.
 fmt,release_dpi=run_facts(output) or (release_format(req,[part]),0.0)
 result=feiten_part(req,part,files,output,work/f'decide-{uuid.uuid4().hex[:8]}',decision,fmt,release_dpi,target=old if old and old.suffix.lower()=='.png' else None)
 if old and result.get('path') and Path(result['path'])!=old and old.exists():
  shutil.move(result['path'],old);result['path']=str(old)
 # Feit: kant A en B (C en D) zijn dezelfde plaat. Een opnieuw gemaakte kant krijgt weer de kleur van
 # zijn andere kant (die al gelijkgetrokken is en zo blijft); zonder dit liepen ze na een beslissing uiteen.
 if result.get('path') and part in ('sidea','sideb','sidec','sided'):
  other={'sidea':'sideb','sideb':'sidea','sidec':'sided','sided':'sidec'}[part]
  me=Path(result['path']);mate=me.with_name(re.sub(r'_'+part+r'(?=(_\d+)?$)','_'+other,me.stem)+me.suffix)
  if mate!=me and mate.exists():
   try:
    cp=subprocess.run([sys.executable,str(TOOLS/'scan_kleur_kanten.py'),str(me),str(mate),'--first-only'],capture_output=True,text=True,timeout=600)
    for line in (cp.stdout+cp.stderr).splitlines()[-3:]:emit('log',message=line)
   except subprocess.TimeoutExpired:emit('warning',message=f'{part}: matching the colour to {other} took too long; kept as scanned.')
 if result.get('path'):emit('outputs',files=[dict(feiten_file(result),replace=True)])
 emit('complete',message=f'{part}: {result.get("verdict")}'+(f' ({result.get("applied")})' if result.get('applied') else ''))


def scan(req,rows,work):
 """Alleen de feitenroute: jij zet de scans in vakken (één vak = één onderdeel), Sleeve
 snijdt uit en zet rechtop op feiten. Geen oude regels, geen gegokte indeling."""
 selected=[row for row in rows if not row.get('reference')]
 if not selected:raise ValueError('Only reference images are selected. Add the original scans too.')
 if req.get('rerunPart'):
  part=req['rerunPart']
  if part not in PARTS:raise ValueError('Choose a valid part.')
  if any(row.get('reference') for row in rows):raise ValueError('Choose only the source images for this part.')
  output=job_folder(req,'Scans');emit('destination',path=str(output))
  result=feiten_part(req,part,[row['path'] for row in rows],output,work/f'rerun-{uuid.uuid4().hex[:8]}',None,release_format(req,[part]))
  if not result.get('path'):raise ValueError('This part could not be made: '+'; '.join(result.get('why',[])))
  files=[feiten_file(result)];JOB_OUTPUTS[files[0]['path']]=files[0]
  emit('outputs',files=files)
  (output/'Studio-verwerking.json').write_text(json.dumps({'action':'scan','route':'feiten','format':release_format(req,[part]),'release_dpi':0.0,'inputs':rows,'outputs':files,'results':[result],'discogs':req.get('discogs','')},ensure_ascii=False,indent=2))
  emit('complete',message=f'{part}: {result.get("verdict")}',path=str(output));return
 layout=layout_from_groups(rows)
 # Feit: elk onderdeel bestaat één keer (twee vakken 'Side A' of twee keer 'CD' kan niet; inserts wel)
 seen={}
 for g in layout:
  if g['part'] and g['part'] not in ('insert','unknown') and g['part'] in seen:
   hint=' Inside is one opened gatefold sleeve; for loose sheets or booklet pages use Insert slots (as many as you need).' if g['part']=='inside' else ''
   raise ValueError(f"Two slots are both '{g['part']}' ({', '.join(seen[g['part']])} and {', '.join(g['files'])}). Check the slots in Arrange Scans."+hint)
  seen.setdefault(g['part'],g['files'])
 # Feit: heet een scan naar een onderdeel (…_cd.png) en ligt hij in een vak van een ander onderdeel, melden
 for g in layout:
  for f in g['files']:
   last=re.split(r'[_\- ]',Path(f).stem.lower())[-1]
   if last in PARTS and g['part'] and last!=g['part'] and not (last.startswith('insert') and g['part'].startswith('insert')):
    emit('warning',message=f"{f} is named '{last}' but lies in the slot '{g['part']}'. Check the slots.")
 if not layout:
  # Feit: heet elk bestand naar zijn onderdeel (front, back, cd, inlay …), dan is elke scan
  # zijn eigen vak (bijvoorbeeld een cd: elk onderdeel past in één scan).
  named=[r for r in rows if not r.get('reference')]
  # laatste woord van de naam: 'front', '2015_hold_me_front', 'Deena cd' …
  stems=[re.split(r'[_\- ]',Path(r['path']).stem.lower())[-1] for r in named]
  if named and all(stem in PARTS for stem in stems) and len(set(stems))==len(stems):
   layout=[{'part':stem,'files':[Path(r['path']).name]} for stem,r in zip(stems,named)]
   for r,stem in zip(named,stems):r['group']=stem;r['part']=stem
   emit('status',message='Each file is named after its part; using one slot per file.')
 if not layout:
  raise ValueError('Put the scans in slots first (Arrange Scans…). Sleeve works only from your slots and the facts; it doesn’t guess which scans belong together.')
 loose=[Path(r['path']).name for r in rows if not r.get('reference') and not str(r.get('group') or '').strip()]
 if loose:emit('warning',message=f'Not in a slot, so not used: '+', '.join(loose))
 remember_layout(rows,layout)
 feiten_scan(req,rows,layout,work)


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
 if not ref.is_file():raise ValueError('First choose your own photo or a Discogs reference photo.')
 strength=float(req.get('strength',1))
 if not 0<=strength<=1:raise ValueError('The color strength must be between 0 and 100%.')
 scope=req.get('scope','vinyl')
 if scope not in ('vinyl','photo'):raise ValueError('Choose vinyl records or a cover.')
 rows=[row for row in rows if not row.get('reference')]
 if not rows:raise ValueError('First check the images you want to adjust.')
 if scope=='photo' and len(rows)!=1:raise ValueError('Choose one cover for the matching reference photo.')
 if scope=='vinyl':
  from PIL import Image
  import scan_cutout as CU
  for row in rows:
   part=row.get('part','unknown')
   if part!='unknown' and not part.startswith('side'):raise ValueError('For vinyl color, only vinyl sides may be checked. A cover isn’t adjusted with a record photo.')
   with Image.open(row['path']) as im:
    if im.mode!='RGBA':raise ValueError('Use cut-out vinyl records with transparency here. Process the scans first.')
    probe=im.getchannel('A');probe.thumbnail((1400,1400))
    if CU.already_cut(probe) is None:raise ValueError('A selected image isn’t a cut-out record yet. Process the scans first.')
 output=colour_destination(rows[0]['path']);emit('destination',path=str(output))
 files=[colour_copy(row,ref,strength,scope,i,len(rows)) for i,row in enumerate(rows)]
 if not files:raise ValueError('No color suggestions were made. Choose a source image too.')
 colour_metadata(ref,strength,scope,rows,files)
 emit('complete',message=f"{len(files)} new color cop{'ies' if len(files)!=1 else 'y'} saved. See New Colors; the originals are kept.",path=str(output))

def colour_copy(row,ref,strength,scope,i,total):
 import scan_colour as C
 src=Path(row['path']);output=colour_destination(src);stem=re.sub(r'(?:_kleur(?:_\d+)?)+$','',src.stem)+'_kleur';dst=output/(stem+'.png');suffix=2
 while dst.exists():dst=output/(stem+'_'+str(suffix)+'.png');suffix+=1
 emit('status',message=f'New color for {i+1} of {total}: {src.name}')
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
 reference_folder=metadata_folder/'Reference';reference_folder.mkdir(parents=True)
 shutil.copy2(ref,reference_folder/('Used-photo'+ref.suffix.lower()))
 (metadata_folder/'Studio-verwerking.json').write_text(json.dumps({'action':'colour','source_reference':str(ref),'strength':strength,'scope':scope,'inputs':rows,'outputs':files,**extra},ensure_ascii=False,indent=2))

def discogs_release(url):
 import scan_naam as N
 match=re.search(r'/(release|master)/(\d+)',urllib.parse.urlparse(url).path)
 release=N.get('https://api.discogs.com/'+('masters' if match[1]=='master' else 'releases')+'/'+match[2])
 if match[1]=='master':release=N.get('https://api.discogs.com/releases/'+str(release['main_release']))
 return release

def names_preview(req,rows):
 import scan_naam as N
 emit('status',message='Fetching file names from Discogs…')
 url=release_url(req.get('discogs',''));N.get=functools.lru_cache(maxsize=32)(N.get)
 proposals=[];used=set()
 for row in rows:
  if row.get('reference'):continue
  p=Path(row['path']);part=row['part']
  if part not in PARTS:raise ValueError('First choose the part for each image before asking for file names.')
  name=N.naam(url,part,req.get('variant',''))+p.suffix.lower()
  base=Path(name);i=2
  while name.casefold() in used:name=base.stem+'_'+str(i)+base.suffix;i+=1
  used.add(name.casefold());st=p.stat();proposals.append({'source':str(p),'newName':name,'part':part,'size':st.st_size,'mtime':st.st_mtime_ns})
 emit('names',rows=proposals);emit('complete',message='Names fetched. Check the suggestion before saving.')

def independent_copy(source,destination):
 # APFS copy-on-write, with an independent inode. Never use hard links.
 try:
  libc=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
  if libc.clonefile(os.fsencode(source),os.fsencode(destination),0)==0:return
 except (AttributeError,OSError):pass
 shutil.copy2(source,destination)

def names_apply(req,rows):
 proposals=req.get('proposals',[])
 if not proposals:raise ValueError('Fetch the suggested names first.')
 allowed={row['path'] for row in rows};checked=[];used=set()
 for row in proposals:
  src=Path(row['source']).resolve();name=row['newName']
  if str(src) not in allowed or not name or Path(name).name!=name or name in ('.','..') or name.casefold() in used:raise ValueError('The name suggestion is invalid. Fetch it again.')
  if Path(name).suffix.lower() not in EXTS:raise ValueError('The file extension in the suggestion is invalid.')
  st=src.stat()
  if st.st_size!=row['size'] or st.st_mtime_ns!=row['mtime']:raise ValueError('A source file has changed. Fetch the names again.')
  used.add(name.casefold());checked.append((src,name))
 output=job_folder(req,'New Names');emit('destination',path=str(output));mapping={}
 for src,name in checked:
  dst=output/name;temporary=output/('.kopie-'+uuid.uuid4().hex+dst.suffix);independent_copy(src,temporary);os.replace(temporary,dst);mapping[str(dst)]=str(src)
 files=report_outputs(output,mapping)
 (output/'Naamwijzigingen.json').write_text(json.dumps(proposals,ensure_ascii=False,indent=2))
 emit('complete',message=f'{len(files)} copies saved with new names.',path=str(output))

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
  emit('progress',fraction=None,index=i+1,total=len(files),phase='Final check')
  emit('status',message=f'File check {i+1} of {len(files)}: {p.name}')
  result={'path':str(p),'readable':False,'part':part,'round':None,'missingInteriorPercent':None,
          'namesApplied':action=='namesApply' or (action=='scan' and bool(req.get('discogs')) and req.get('useNames',True) and not any('name via Discogs failed' in w for w in JOB_WARNINGS)),
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
      if not contours:raise ValueError('No visible disc in the transparency mask.')
      contour=max(contours,key=cv2.contourArea)
      if len(contour)<5:raise ValueError('The round edge couldn’t be measured.')
      (cx,cy),(a,b),angle=cv2.fitEllipse(contour)
      result['round']=bool(min(a,b)>0 and max(a,b)/min(a,b)<1.005)
      yy,xx=np.ogrid[:mask.shape[0],:mask.shape[1]];radius=(a+b)/4;distance=np.hypot(xx-cx,yy-cy)
      annulus=(distance>.32*radius)&(distance<.97*radius)
      missing=float(100*(annulus&~mask).sum()/max(1,annulus.sum()))
      result['missingInteriorPercent']=round(missing,4)
      if missing>=.2:result['message']=f'About {missing:.1f}% is missing inside the disc; check the source image.'
      elif not result['round']:result['message']='The outer edge wasn’t measured as reliably round.'
     else:result['message']='Roundness can’t be measured automatically without a transparent crop.'
   after=p.stat()
   if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError('The file changed during the check.')
   result['signature']=f'{after.st_size}:{after.st_mtime_ns//10**9}:{after.st_mtime_ns%10**9}'
   result['readable']=True
   if file.get('partial'):result['message']='Interrupted run; this result must be checked again.'
   notes=component_quality(p)
   if notes:result['message']=' '.join([result['message']]+notes if result['message'] else notes)
  except Exception as error:result['message']=str(error)
  audits.append(result);emit('audit',audits=[result])
 if any(not row['readable'] for row in audits):raise ValueError('A result couldn’t be read completely. The queue is paused; see the final check.')
 return audits

def fingerprint(path):
 st=Path(path).stat()
 return f'{st.st_size}:{st.st_mtime_ns//10**9}:{st.st_mtime_ns%10**9}'

def manual_crop(req,rows,work):
 import math,numpy as np
 from PIL import Image,ImageOps,PngImagePlugin
 if len(rows)!=1:raise ValueError('Choose exactly one source image for the round crop.')
 row=rows[0];src=Path(row['path']);expected=req.get('sourceSignature')
 if not expected or fingerprint(src)!=expected:raise ValueError('The source image has changed. Open the crop again.')
 cx,cy,diameter=[float(req[key]) for key in ('cropX','cropY','cropDiameter')]
 if not all(math.isfinite(v) for v in (cx,cy,diameter)) or not(0<=cx<=1 and 0<=cy<=1 and 0<diameter<=1):raise ValueError('The circle settings aren’t valid.')
 part=req.get('cropPart','')
 if part not in PARTS or not(part.startswith('side') or part.startswith('cd')):raise ValueError('This correction is meant for round CD and vinyl images.')
 output=job_folder(req,'Crop');emit('destination',path=str(output))
 with Image.open(src) as raw:
  raw.load();icc=raw.info.get('icc_profile');dpi=raw.info.get('dpi');image=ImageOps.exif_transpose(raw).convert('RGBA')
  width,height=image.size;size=int(round(diameter*min(width,height)))
  if size<16:raise ValueError('The circle is too small. Choose a larger diameter.')
  left=int(round(cx*width-size/2));top=int(round(cy*height-size/2))
  if left<0 or top<0 or left+size>width or top+size>height:raise ValueError('The circle extends beyond the source image. Make it smaller or move it.')
  cropped=image.crop((left,top,left+size,top+size));alpha=np.array(cropped.getchannel('A'));centre=(size-1)/2;radius=(size-1)/2
  xx=np.arange(size,dtype=np.float64)[None,:]-centre
  for start in range(0,size,256):
   end=min(size,start+256);yy=np.arange(start,end,dtype=np.float64)[:,None]-centre
   edge=np.clip(radius+.5-np.hypot(xx,yy),0,1)
   alpha[start:end]=np.rint(alpha[start:end]*edge).astype(np.uint8)
   emit('progress',fraction=end/size if end<size else None,phase='Building round crop' if end<size else 'Saving image')
  cropped.putalpha(Image.fromarray(alpha));metadata=PngImagePlugin.PngInfo();metadata.add_text('sleeve_disc_cut','3')
  destination=output/(src.stem+'_uitsnede.png');temporary=output/'.crop.png'
  options={'pnginfo':metadata}
  if icc:options['icc_profile']=icc
  if dpi:options['dpi']=dpi
  cropped.save(temporary,**options)
  if fingerprint(src)!=expected:temporary.unlink();raise ValueError('The source image changed during processing; the previous version is kept.')
  os.replace(temporary,destination)
 files=[{'path':str(destination),'source':str(src),'part':part,'partial':False}]
 emit('outputs',files=files)
 (output/'Studio-verwerking.json').write_text(json.dumps({'action':'manualCrop','inputs':rows,'outputs':files,'circle':{'x':cx,'y':cy,'diameter':diameter},'pixel_box':[left,top,size,size]},indent=2))
 emit('complete',message='New round crop saved. Compare the previous and new version; also check the text along the edge.')


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
    if process.returncode:raise ValueError('Text recognition failed')
    return stdout
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGKILL);process.communicate();raise
   finally:OCR_CHILDREN.discard(process)
  emit('releaseAdvice',advice=A.advice(req,inputs(req),recognize_command));emit('complete',message='Release suggestions fetched.');return
 if action=='decide':feiten_decide(req,work);return
 if action=='suggestGroups':
  # vakken vooraf invullen op feiten (barcode, Discogs-hoesfoto, cd van 120 mm); de rest blijft leeg
  files=[r['path'] for r in req.get('inputs',[]) if not r.get('reference')]
  if not req.get('discogs') or not files:emit('complete',message='Drag the scans into the slots.');return
  emit('status',message='Looking for facts: barcode, Discogs cover photo, disc…')
  cmd=[sys.executable,str(TOOLS/'scan_vakken.py'),release_url(req['discogs']),str(req.get('format') or ''),','.join(req.get('slots') or []),*files]
  try:out=subprocess.run(cmd,capture_output=True,text=True,timeout=120+45*len(files))
  except subprocess.TimeoutExpired:emit('complete',message='Looking for facts took too long. Drag the scans into the slots.');return
  try:res=json.loads(out.stdout.strip().splitlines()[-1])
  except (ValueError,IndexError):emit('complete',message='No slots filled in. Drag the scans into the slots.');return
  emit('groups',groups=res.get('groups',[]))
  done=[f"{g['part']}: {Path(f).name} ({res['why'].get(f,'')})" for g in res.get('groups',[]) for f in g['files']]
  emit('complete',message=('Filled in on facts: '+'; '.join(done)+'. Check them and drag the rest.') if done else 'No facts found to fill in slots. Drag the scans into the slots.');return
 if action=='releaseInfo':
  import scan_release as RI,scan_naam as N
  emit('status',message='Fetching the release from Discogs…')
  info=RI.info(release_url(req.get('discogs','')))
  thumbs=[]
  for i,u in enumerate(info.get('images') or []):
   try:
    p=work/f'thumb{i}.jpg';p.write_bytes(N.fetch(u));thumbs.append(str(p))
   except Exception:pass
  info['thumbs']=thumbs
  emit('releaseInfo',info=info);emit('complete',message='Release loaded. Check the details.');return
 if action=='references':reference_photos(req,work);emit('complete',message='Reference photos loaded. Choose the right photo.');return
 rows=inputs(req)
 CHECKING_AFTER_PROCESS=action in ('scan','colour','namesApply','manualCrop')
 if action=='scan':scan(req,rows,work)
 elif action=='colour':colour(req,rows,work)
 elif action=='manualCrop':manual_crop(req,rows,work)
 elif action=='namesPreview':names_preview(req,rows)
 elif action=='namesApply':names_apply(req,rows)
 elif action=='audit':
  audit_files(req,[{'path':row['path'],'source':row.get('source',''),'partial':row.get('partial',False)} for row in rows],'audit')
  emit('complete',message='File checks updated. Judge the images and names yourself in the final check.')
 else:raise ValueError('Unknown action.')
 if CHECKING_AFTER_PROCESS:
  audit_files(req,list(JOB_OUTPUTS.values()),action);CHECKING_AFTER_PROCESS=False
  emit('complete',**(PENDING_COMPLETION or {'message':'Processing finished; visual check still open.'}))
if __name__=='__main__':
 try:main()
 except SystemExit:raise
 except BaseException as e:
  emit('error',message=str(e));emit('log',message=traceback.format_exc());sys.exit(1)

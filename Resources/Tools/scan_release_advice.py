"""Local bounded OCR + explicit Discogs release suggestions. No source image upload."""
import concurrent.futures,json,re,subprocess,urllib.error,urllib.parse,urllib.request
from pathlib import Path

UA='Sleeve/0.4.2 (+https://github.com/reprise-labs/sleeve)'

def normalized(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())
def valid_barcode(value):
 value=re.sub(r'[\s-]','',str(value))
 if not value.isdigit() or len(value) not in (8,12,13,14) or len(set(value))==1:return ''
 check=(10-sum(int(d)*(3 if i%2==0 else 1) for i,d in enumerate(reversed(value[:-1])) )%10)%10
 return value if check==int(value[-1]) else ''
def barcode_key(value):
 value=valid_barcode(value);return value.zfill(14) if value else ''

def sample_rows(rows,limit=6):
 # Spread unclassified partial scans across the whole batch, then favour distinct parts.
 usable=[r for r in rows if not r.get('reference')]
 if len(usable)<=limit:return usable
 selected=[]
 for part in ('back','front','cd','sidea'):
  match=next((r for r in usable if r.get('part')==part),None)
  if match and match not in selected:selected.append(match)
 for i in [len(usable)-1,len(usable)//2,len(usable)//3,2*len(usable)//3,len(usable)//4,3*len(usable)//4]:
  if usable[i] not in selected:selected.append(usable[i])
 return selected[:limit]

def extract_hints(documents):
 lines={};barcodes=[]
 for document in documents:
  for value in document.get('barcodes',[]):
   code=valid_barcode(value)
   if code and code not in barcodes:barcodes.append(code)
  rotations={}
  for row in document.get('lines',[]):
   text=re.sub(r'\s+',' ',row.get('text','')).strip()
   if float(row.get('confidence',0))<.35 or not text:continue
   rotations.setdefault(row.get('rotation',0),[]).append(dict(row,text=text))
  # Avoid treating four rotations of the same words as independent evidence.
  if not rotations:continue
  def reading_score(rows):
   text=' '.join(r['text'] for r in rows)
   words=len(re.findall(r"\b(?:the|and|of|to|in|on|for|music|records|made|exclusive|license|universal|netherlands|germany|vinyl|disc|reserved|all|rights|you|me|can|how|with)\b",text,re.I))
   return words*30+sum(min(35,len(r['text']))*float(r.get('confidence',0)) for r in rows)
  best=max(rotations.values(),key=reading_score)
  for row in best:
   text=row['text'];code=valid_barcode(text)
   if code and code not in barcodes:barcodes.append(code)
   key=text.casefold()
   if key not in lines or row.get('height',0)>lines[key].get('height',0):lines[key]=row
 ordered=sorted(lines.values(),key=lambda r:float(r.get('height',0)),reverse=True)
 clean=[r['text'] for r in ordered if len(r['text'])>=3 and not re.search(r'copyright|reserved|manufactur|photograph|art direction|graphic design|exclusive license|www\.|https?:|made in|stereo|side [abcd]|rpm|\bbiem\b|\bsdrm\b',r['text'],re.I) and sum(c.isalpha() for c in r['text'])>=3]
 clean=[s for s in clean if len(s)<=100 and not re.match(r'^\d{1,2}[.)]\s',s)][:16]
 artist=clean[0] if clean else ''
 title=next((s for s in clean[1:] if normalized(s)!=normalized(artist)),'')
 catalogs=[]
 for row in ordered:
  text=row['text']
  for expression in [r'\b[A-Z]{2,6}[ .-]?\d{3,9}(?:[-./]\d{1,3})?\b',r'\b\d{2,4}[ .-]\d{3,5}[ .-]\d{1,2}\b']:
   for candidate in re.findall(expression,text):
    if not valid_barcode(candidate) and candidate not in catalogs:catalogs.append(candidate)
 return {'artist':artist,'title':title,'barcode':barcodes[0] if barcodes else '', 'catno':catalogs[0] if catalogs else '', 'text':clean,'barcodes':barcodes[:4]}

def recognize(rows,runner=None):
 helper=Path(__file__).with_name('sleeve_ocr')
 if not helper.is_file():raise ValueError('De tekstherkenner ontbreekt. Je kunt de zoekgegevens zelf invullen.')
 if runner is None:runner=lambda command:subprocess.run(command,capture_output=True,text=True,timeout=20,check=True).stdout
 documents=[]
 for row in sample_rows(rows):
  try:
   document=json.loads(runner([str(helper),row['path'],'--identify']));documents.append(document)
   if any(valid_barcode(value) for value in document.get('barcodes',[])):break
  except (ValueError,OSError,subprocess.SubprocessError):continue
 return extract_hints(documents)

def api_get(url):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=8) as response:return json.load(response)
 except urllib.error.HTTPError as error:
  if error.code==429:raise RuntimeError('Discogs ontvangt nu te veel zoekopdrachten. Probeer het later opnieuw.') from None
  if error.code in (401,403):raise RuntimeError('Discogs staat zoeken vanuit de app nu niet toe. Gebruik ‘Zoek op Discogs’ en plak de uitgavelink.') from None
  raise RuntimeError('Discogs zoeken is tijdelijk niet beschikbaar.') from None
 except (OSError,ValueError):raise RuntimeError('Geen verbinding met Discogs. Je kunt de zoekgegevens bewaren en later opnieuw zoeken.') from None

def search(hints,format_filter='',get=api_get):
 terms={k:str(hints.get(k,'')).strip()[:160] for k in ('artist','title','barcode','catno')}
 terms['barcode']=valid_barcode(terms['barcode'])
 common={'type':'release','per_page':20}
 if format_filter in ('Vinyl','CD'):common['format']=format_filter
 queries=[]
 if terms['barcode']:queries.append(dict(common,barcode=terms['barcode']))
 if terms['catno'] and not terms['barcode']:queries.append(dict(common,catno=terms['catno']))
 if not terms['barcode'] and (terms['artist'] or terms['title']):
  queries.append(dict(common,**({'artist':terms['artist']} if terms['artist'] else {}),**({'release_title':terms['title']} if terms['title'] else {})))
 if not queries:return [],'Vul een artiest en titel, barcode of catalogusnummer in.'
 results={};problems=[]
 for query in queries[:3]:
  try:
   for row in get('https://api.discogs.com/database/search?'+urllib.parse.urlencode(query)).get('results',[]):
    rid=row.get('id')
    if isinstance(rid,int) and rid>0:results[rid]=row
  except RuntimeError as error:problems.append(str(error))
 def evidence(row):
  reasons=[];score=0
  if terms['barcode'] and any(barcode_key(code)==barcode_key(terms['barcode']) for code in row.get('barcode',[])):
   score+=100;reasons.append('Barcode komt overeen')
  if terms['catno'] and normalized(terms['catno'])==normalized(row.get('catno','')):score+=60;reasons.append('Catalogusnummer komt overeen')
  title=normalized(row.get('title',''))
  if terms['artist'] and normalized(terms['artist']) in title:score+=15;reasons.append('Artiest komt overeen')
  if terms['title'] and normalized(terms['title']) in title:score+=20;reasons.append('Titel komt overeen')
  return score,reasons
 ranked=sorted(results.values(),key=lambda r:(-evidence(r)[0],r['id']))[:5]
 def convert(row):
  detail={}
  try:detail=get(f"https://api.discogs.com/releases/{row['id']}")
  except RuntimeError:pass
  formats=detail.get('formats',[])
  variant=' · '.join(str(f.get('text','')) for f in formats if f.get('text'))
  return {'id':row['id'],'title':str(row.get('title','')),'year':str(row.get('year','')),'country':str(row.get('country','')),'format':', '.join(map(str,row.get('format',[]))),'catno':str(row.get('catno','')),'variant':variant,'url':f"https://www.discogs.com/release/{row['id']}",'reasons':evidence(row)[1] or ['Gevonden met deze zoekgegevens']}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:candidates=list(pool.map(convert,ranked))
 message='Controleer formaat, kleur en land voordat je een uitgave kiest.' if candidates else (problems[0] if problems else 'Geen passende uitgaven gevonden. Controleer de herkende zoekgegevens.')
 if candidates and problems:message+=' Een deel van de zoekopdrachten lukte niet.'
 return candidates,message

def advice(req,rows,runner=None,get=api_get):
 hints=recognize(rows,runner) if req.get('recognize',True) else {k:req.get(k,'') for k in ('artist','title','barcode','catno')}
 if req.get('recognize',True) and (hints.get('barcode') or hints.get('catno')):
  hints['artist']='';hints['title']=''
 candidates,message=search(hints,req.get('format',''),get)
 if candidates and len({c['title'] for c in candidates})==1:
  artist,separator,title=candidates[0]['title'].partition(' - ')
  if separator:hints['artist']=artist;hints['title']=title
 return {'hints':hints,'candidates':candidates,'message':message}

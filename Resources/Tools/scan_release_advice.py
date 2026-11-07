"""Local bounded OCR + explicit Discogs release suggestions. No source image upload."""
import concurrent.futures,json,re,subprocess,urllib.error,urllib.parse,urllib.request
from pathlib import Path

UA='Sleeve/0.4.16 (+https://github.com/reprise-labs/sleeve)'

def normalized(value):return re.sub(r'[^a-z0-9]','',str(value).casefold())
def split_words(value):
 # AnoukUrbanSolitude -> Anouk Urban Solitude; dubbele woorden één keer.
 words=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',str(value)).split();seen=[]
 for word in words:
  if word.casefold() not in [w.casefold() for w in seen]:seen.append(word)
 return ' '.join(seen)[:160]
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

DURATION=re.compile(r'\s*\d{1,2}[.:,]{1,2}\d{2}\s*$')   # "New Day 3.37" -> "New Day"
# ISRC van de opname (promo's): "ISRC: NL-XA9-15-00002". Discogs zoekt er niet op,
# maar zet hem vaak bij de uitgave; dan bevestigt hij een kandidaat.
ISRC=re.compile(r'IS[RA]C\W*([A-Z]{2})\W?([A-Z0-9]{3})\W?(\d{2})\W?(\d{5})')
CREDITS=re.compile(r'^\s*(?:[@©℗]|\([cp]\))|\bis[ra]c\b|\bupc\b|\bean\b|^ed\.?:|licen[cs]|promotional use|not for sale|\b(?:written|produced|mixed|published|engineered|recorded|mastered|arranged|programming|vocals|lyrics|music) by\b',re.I)

def extract_hints(documents):
 lines={};barcodes=[];seen_in={};isrcs=[]
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
   # Ondersteboven gelezen tekst geeft onzinwoorden (">lnONV", "3Mnoa"): cijfers
   # midden in letters of rare tekens tellen tegen.
   junk=len(re.findall(r"\S*(?:[A-Za-z]\d|\d[A-Za-z]|[<>|\[\]{}\\])\S*",text))
   return words*30-junk*15+sum(min(35,len(r['text']))*float(r.get('confidence',0)) for r in rows)
  best=max(rotations.values(),key=reading_score)
  for row in best:
   text=row['text'];code=valid_barcode(text)
   if code and code not in barcodes:barcodes.append(code)
   key=text.casefold()
   if key not in lines or row.get('height',0)>lines[key].get('height',0):lines[key]=row
   for found in ISRC.findall(text.upper()):
    if ''.join(found) not in isrcs:isrcs.append(''.join(found))
   seen_in.setdefault(normalized(DURATION.sub('',text)),set()).add(id(document))
 ordered=sorted(lines.values(),key=lambda r:float(r.get('height',0)),reverse=True)
 clean=[r['text'] for r in ordered if len(r['text'])>=3 and not re.search(r'copyright|reserved|manufactur|photograph|art direction|graphic design|exclusive license|www\.|https?:|made in|stereo|side [abcd]|rpm|\bbiem\b|\bsdrm\b',r['text'],re.I) and sum(c.isalpha() for c in r['text'])>=3]
 clean=[s for s in clean if len(s)<=100 and not re.match(r'^\d{1,2}[.)]\s',s) and not CREDITS.search(s)][:16]
 repeats=lambda s:len(seen_in.get(normalized(DURATION.sub('',s)),()))
 # Artiest: de grootste tekst die op meer dan één deel staat (ANOUK op hoes,
 # achterkant en cd), anders de grootste; losse randtekst van een cd telt dan niet.
 artist=next((s for s in clean if repeats(s)>=2 and not DURATION.search(s)),clean[0] if clean else '')
 # "& DOUWE BOB" / "feat. …" onder de naam hoort bij de artiest.
 partner=next((s for s in clean if re.match(r'^\s*(?:&|feat\.?|ft\.|with)\s',s,re.I) and normalized(s)!=normalized(artist)),'')
 if partner and normalized(partner) not in normalized(artist):artist=f'{artist} {partner.strip()}'
 options=[]
 for s in clean:
  s=DURATION.sub('',s)
  if normalized(s) and normalized(s)!=normalized(artist) and normalized(s) not in normalized(artist) and normalized(s) not in [normalized(o) for o in options]:options.append(s)
 # Een titel staat meestal op meerdere delen (hoes, achterkant, cd); een
 # copyright- of creditregel niet. Herhaalde tekst gaat dus voor, dan grootte.
 title=max(options,key=lambda s:(repeats(s)>=2,repeats(s)),default='') if options else ''
 # Een catalogusnummer staat in het kleine drukwerk ("Made in the EU … MOVLP1572").
 # Grote losse tekst die erop lijkt is vaak een titel of logo, verkeerd om gelezen
 # (TOGETHER ondersteboven -> JIH13901): drukwerkregels eerst, dan kleinste tekst.
 context=re.compile(r'made|music|universal|rights|reserved|licen|manufactur|distribut|netherlands|\beu\b|records|vinyl|℗|©',re.I)
 found=[]
 for row in ordered:
  text=row['text']
  for expression in [r'\b[A-Z]{2,6}[ .-]?\d{3,9}(?:[-./]\d{1,3})?\b',r'\b\d{2,4}[ .-]\d{3,5}[ .-]\d{1,2}\b']:
   for candidate in re.findall(expression,text):
    if not valid_barcode(candidate):found.append((context.search(text) is None,float(row.get('height',0)),candidate))
 catalogs=[]
 for _,_,candidate in sorted(found,key=lambda f:f[:2]):
  if candidate not in catalogs:catalogs.append(candidate)
 return {'artist':artist,'title':title,'barcode':barcodes[0] if barcodes else '', 'catno':catalogs[0] if catalogs else '', 'text':clean,'barcodes':barcodes[:4],'isrc':isrcs[:4],'promo':any(re.search(r'promotional|promo only|not for sale',k) for k in lines)}

def recognize(rows,runner=None):
 helper=Path(__file__).with_name('sleeve_ocr')
 if not helper.is_file():raise ValueError('De tekstherkenner ontbreekt. Je kunt de zoekgegevens zelf invullen.')
 if runner is None:runner=lambda command:subprocess.run(command,capture_output=True,text=True,timeout=20,check=True).stdout
 # Barcode en catalogusnummer staan vaak op één deelscan van de achterkant.
 # Lees daarom zo nodig alle scans (~1 s per scan), maar stop bij de eerste
 # bruikbare barcode. Artiest en titel komen zoals voorheen uit de steekproef.
 sampled=sample_rows(rows)
 order=sampled+[r for r in rows if not r.get('reference') and r not in sampled]
 documents=[]
 for row in order:
  try:document=json.loads(runner([str(helper),row['path'],'--identify']))
  except (ValueError,OSError,subprocess.SubprocessError):document=None
  documents.append(document)
  if document and any(valid_barcode(value) for value in document.get('barcodes',[])):break
 hints=extract_hints([d for d in documents[:len(sampled)] if d])
 everything=extract_hints([d for d in documents if d])
 hints['barcodes']=everything['barcodes'];hints['barcode']=everything['barcode'];hints['isrc']=everything['isrc'];hints['promo']=everything['promo']
 if not hints['catno']:hints['catno']=everything['catno']
 return hints

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
 isrcs=[str(code) for code in hints.get('isrc',[]) if str(code).strip()][:4]
 common={'type':'release','per_page':20}
 if format_filter in ('Vinyl','CD'):common['format']=format_filter
 # Eerst de barcode; levert die niets op (of is er geen), dan catalogusnummer
 # én tekst samen: een verkeerd gelezen catalogusnummer mag de tekst niet wegdrukken.
 queries=[]
 if terms['catno']:queries.append(dict(common,catno=terms['catno']))
 if terms['artist'] or terms['title']:
  queries.append(dict(common,**({'artist':terms['artist']} if terms['artist'] else {}),**({'release_title':terms['title']} if terms['title'] else {})))
  # Logo's lezen vaak als één woord (AnoukUrbanSolitude): ook vrij zoeken, met woorden gesplitst.
  for free in (split_words(terms['artist']),split_words(' '.join(t for t in (terms['artist'],terms['title']) if t))):
   if free and dict(common,q=free) not in queries:queries.append(dict(common,q=free))
 if not queries and not terms['barcode']:return [],'Vul een artiest en titel, barcode of catalogusnummer in.'
 results={};problems=[]
 def run(query):
  try:
   for row in get('https://api.discogs.com/database/search?'+urllib.parse.urlencode(query)).get('results',[]):
    rid=row.get('id')
    if isinstance(rid,int) and rid>0:results[rid]=row
  except RuntimeError as error:problems.append(str(error))
 if terms['barcode']:run(dict(common,barcode=terms['barcode']))
 if not results:
  for query in queries[:3]:run(query)
 def evidence(row):
  reasons=[];score=0
  if terms['barcode'] and any(barcode_key(code)==barcode_key(terms['barcode']) for code in row.get('barcode',[])):
   score+=100;reasons.append('Barcode komt overeen')
  if terms['catno'] and normalized(terms['catno'])==normalized(row.get('catno','')):score+=60;reasons.append('Catalogusnummer komt overeen')
  title=normalized(row.get('title',''))
  if terms['artist'] and normalized(terms['artist']) in title:score+=15;reasons.append('Artiest komt overeen')
  if terms['title'] and normalized(terms['title']) in title:score+=20;reasons.append('Titel komt overeen')
  if hints.get('promo') and 'Promo' in row.get('format',[]):score+=10;reasons.append('Promo-uitgave, zoals op de scan')
  return score,reasons
 ranked=sorted(results.values(),key=lambda r:(-evidence(r)[0],r['id']))[:5]
 def convert(row):
  detail={}
  try:detail=get(f"https://api.discogs.com/releases/{row['id']}")
  except RuntimeError:pass
  formats=detail.get('formats',[])
  variant=' · '.join(str(f.get('text','')) for f in formats if f.get('text'))
  reasons=evidence(row)[1]
  listed=normalized(' '.join(str(i.get('value','')) for i in detail.get('identifiers',[]))+' '+str(detail.get('notes','')))
  # Soms zonder landcode ingevoerd (Hold Me: "XA9-15-00001").
  if any(normalized(code)[2:] in listed for code in isrcs):reasons=reasons+['ISRC komt overeen']
  return {'id':row['id'],'title':str(row.get('title','')),'year':str(row.get('year','')),'country':str(row.get('country','')),'format':', '.join(map(str,row.get('format',[]))),'catno':str(row.get('catno','')),'variant':variant,'url':f"https://www.discogs.com/release/{row['id']}",'reasons':reasons or ['Gevonden met deze zoekgegevens']}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:candidates=list(pool.map(convert,ranked))
 candidates.sort(key=lambda c:'ISRC komt overeen' not in c['reasons'])   # stabiel: verder volgorde van het bewijs
 message='Controleer formaat, kleur en land voordat je een uitgave kiest.' if candidates else (problems[0] if problems else 'Geen passende uitgaven gevonden. Controleer de herkende zoekgegevens.')
 if candidates and problems:message+=' Een deel van de zoekopdrachten lukte niet.'
 return candidates,message

def advice(req,rows,runner=None,get=api_get):
 hints=recognize(rows,runner) if req.get('recognize',True) else {k:req.get(k,'') for k in ('artist','title','barcode','catno')}
 candidates,message=search(hints,req.get('format',''),get)
 if req.get('recognize',True) and any(reason in c['reasons'] for c in candidates for reason in ('Barcode komt overeen','Catalogusnummer komt overeen','ISRC komt overeen')):
  hints['artist']='';hints['title']=''     # zekere treffer: geen gelezen tekstruis tonen
 barcode_hits=[c for c in candidates if 'Barcode komt overeen' in c['reasons'] and c['catno']]
 if req.get('recognize',True) and barcode_hits and len({normalized(c['catno']) for c in barcode_hits})==1:
  hints['catno']=barcode_hits[0]['catno']  # catalogusnummer van de uitgave zelf, niet een misgelezen titel
 sure=[c for c in candidates if any(reason in c['reasons'] for reason in ('Barcode komt overeen','Catalogusnummer komt overeen','ISRC komt overeen'))]
 if len({c['title'] for c in sure or candidates})==1 and candidates:
  artist,separator,title=(sure or candidates)[0]['title'].partition(' - ')
  if separator:hints['artist']=artist;hints['title']=title
 return {'hints':hints,'candidates':candidates,'message':message}

"""Release suggestions: identifiers, ambiguous pressings, network failure, old scan settings."""
from pathlib import Path
from unittest.mock import patch
import sys,json,urllib.parse,tempfile
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_release_advice as A
work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=True)
assert A.valid_barcode('0 602475 888833')=='0602475888833'
assert A.barcode_key('602475888833')==A.barcode_key('0602475888833')
for value in ['0000000000000','0602475888834','758 888-3','1234567']:
 assert not A.valid_barcode(value),value
base={'title':'Anouk - Set This Thing On Fire','year':'2025','country':'Netherlands','format':['Vinyl','LP','Album'],'catno':'758 888-3','barcode':['0 602475 888833']}
calls=[]
def get(url):
 calls.append(url)
 if '/database/search?' in url:return {'results':[dict(base,id=33644769),dict(base,id=33664818),dict(base,id=33664818)]}
 return {'formats':[{'text':'Orange' if url.endswith('33664818') else ''}]}
req={'recognize':False,'artist':'Anouk','title':'Set This Thing On Fire','barcode':'0602475888833'}
advice=A.advice(req,[],get=get)
assert [r['id'] for r in advice['candidates']]==[33644769,33664818]
assert advice['candidates'][1]['variant']=='Orange'
assert all('Barcode matches' in r['reasons'] for r in advice['candidates'])
assert len([u for u in calls if '/database/search?' in u])==1
assert 'artist=' not in calls[0] and 'token' not in calls[0]
# Unknown/no text never searches vaguely or invents a release.
calls.clear();empty=A.advice({'recognize':False},[],get=get);assert not empty['candidates'] and not calls
# Best reading orientation wins even if an upside-down view has more gibberish.
doc={'barcodes':['0602475888833'],'lines':[{'text':'photography xxxxxxxxxxxxxxxxxxxxx','confidence':.5,'height':.2,'rotation':0},{'text':'Made in Germany 758 888-3 Universal Music','confidence':.5,'height':.1,'rotation':180}]}
h=A.extract_hints([doc]);assert h['catno']=='758 888-3'
# Local recognition sends identifiers, not images or raw OCR text, to Discogs.
with patch.object(A,'recognize',return_value=dict(h,artist='bad OCR',title='wrong song')):
 calls.clear();recognized=A.advice({'recognize':True},[],get=get)
 assert recognized['hints']['artist']=='Anouk'
 assert recognized['hints']['title']=='Set This Thing On Fire'
 assert not any('bad+OCR' in u or 'wrong+song' in u for u in calls)
# Promo (New Day): copyright langs de cd-rand is groter dan de titel; de titel staat op
# meerdere delen, met speelduur. ISRC bevestigt een uitgave, ook zonder landcode.
line=lambda text,height:{'text':text,'confidence':.9,'height':height,'rotation':0}
docs=[{'lines':[line('ANOUK',.07),line('NEW DAY',.02)]},
      {'lines':[line('ANOUK',.05),line('New Day 3.37',.03),line('ISRC: NL-XA9-15-00002',.01),line('For promotional use only - NOT FOR SALE',.02)]},
      {'lines':[line('ANOUK',.06),line('@ 2015 Goldilox, under the exclusive licen* to Universal Music BV',.09),line('New Day 3:37',.02)]}]
h=A.extract_hints(docs)
assert (h['artist'],h['title'],h['isrc'],h['promo'])==('ANOUK','New Day',['NLXA91500002'],True),h
def promo_get(url):
 if '/database/search?' in url:return {'results':[{'id':2,'title':'Anouk - New Day','format':['File','AAC']},{'id':3,'title':'Anouk - New Day','format':['CDr','Promo']}]}
 return {'identifiers':[{'type':'ISRC','value':'XA9-15-00002'}]} if url.endswith('/3') else {}
found,_=A.search(h,'',promo_get)
assert found[0]['id']==3 and 'ISRC matches' in found[0]['reasons'] and 'ISRC matches' not in found[1]['reasons']
# Big words on the front read as separate lines ("PLACES" "TOGO", "You" "&I"); the
# track line with its duration gives the real title; the artist comes from the credits.
places=[{'lines':[line('PLACES',.18),line('TOGO',.18),line('nou',.11)]},
        {'lines':[line('ANOUK',.14),line('Places To Go 3..47',.03),line('lyrics by Anouk Teeuwe',.02),line("Eerste single of Anouk's nieuwe album",.02),line('For promotional use only - NOT FOR SALE',.02)]}]
h=A.extract_hints(places);assert (h['artist'],h['title'])==('ANOUK','Places To Go'),h
you=[{'lines':[line('You',.30),line('&I',.29)]},
     {'lines':[line('You &13..54',.03),line('Written by Anouk Teeuwe and N. Van De Wall',.02),line('Produced by Anouk Teeuwe',.02),line('For promotional use only - NOT FOR SALE',.02)]}]
h=A.extract_hints(you);assert (h['artist'],h['title'])==('Anouk','You & I'),h
def offline(url):raise RuntimeError('No connection to Discogs.')
failed=A.advice(req,[],get=offline);assert not failed['candidates'] and 'No connection' in failed['message']
# A usable barcode stops recognition without decoding the rest of the batch.
seen=[]
def runner(command):
 seen.append(command);return json.dumps({'barcodes':['0602475888833'],'lines':[]})
A.recognize([{'path':str(i),'part':'front'} for i in range(30)],runner)
assert len(seen)==1
# Explicit format filter stays in the request, no guessing from an album title.
calls.clear();A.search({'artist':'Anouk','title':'Fake It Till We Die'},'Vinyl',get)
assert urllib.parse.parse_qs(urllib.parse.urlparse(calls[0]).query)['format']==['Vinyl']
rows=[{'path':str(i),'part':'front','reference':i==0} for i in range(30)]
chosen=A.sample_rows(rows);assert len(chosen)==6 and rows[0] not in chosen and rows[-1] in chosen
# A legacy project/queue with useColour=true must never colour-correct during scans.
sys.path.insert(0,str(root/'Resources'));import studio_bridge as B
class Captured(Exception):pass
captured=[]
def fake_run(command):captured.extend(map(str,command));raise Captured()
with tempfile.TemporaryDirectory(dir=work) as folder:
 folder=Path(folder);output=folder/'output';output.mkdir();staging=folder/'work';staging.mkdir()
 sample=root/'Resources/Samples/Voorbeeld_sidea.png'
 with patch.object(B,'run',side_effect=fake_run):
  try:B.scan({'output':str(output),'discogs':'https://www.discogs.com/release/33664818','useNames':False,'useStand':False,'useColour':True},[{'path':str(sample),'part':'sidea'}],staging)
  except Captured:pass
 assert captured and '--discogs-kleur' not in captured
checks={'barcode_checksum_and_upc_ean_equivalence':True,'distinct_pressings_need_user_choice':True,'orange_variant_shown':True,'no_upload_of_images_or_raw_text':True,'offline_and_no_text_handled':True,'format_filter_and_bounded_sampling':True,'legacy_scan_colour_disabled':True,'promo_title_isrc':True,'split_title_and_credit_artist':True}
(work/'RESULTAAT.json').write_text(json.dumps(checks,indent=2));print(checks)

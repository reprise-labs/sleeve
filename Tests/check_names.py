"""Keep the collection's legacy label rule restricted to its actual artist."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Resources/Tools'))
import scan_naam as n
release={'year':2020,'title':'Demo','formats':[{'name':'Vinyl'}],'labels':[{'name':'Universal Music'}],'artists':[{'name':'Another Artist'}]}
n.get=lambda url:release
assert 'universalmusic' in n.naam('https://www.discogs.com/release/1','sidea')
release['artists']=[{'name':'Anouk'}]
assert 'goldilox' in n.naam('https://www.discogs.com/release/1','sidea')
print('Labelnamen blijven correct voor andere artiesten; bestaande collectieregel blijft werken.')

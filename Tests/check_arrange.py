"""Slots from the arrange screen: the user's grouping is followed exactly and remembered per folder."""
from pathlib import Path
import sys,json,tempfile
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources'));sys.path.insert(0,str(root/'Resources/Tools'))
import studio_bridge as B
with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder)
    rows=[{'path':str(folder/f'Scan {i}.jpeg'),'part':part,'group':group,'reference':False} for i,part,group in
          [(1,'sidea','a'),(2,'sidea','a'),(3,'sideb','b'),(4,'sideb','b'),(5,'unknown','x'),(6,'unknown','x'),(7,'front','')]]
    rows.append({'path':str(folder/'Scan 8.jpeg'),'part':'unknown','group':'a','reference':True})
    layout=B.layout_from_groups(rows)
    assert layout==[{'part':'sidea','files':['Scan 1.jpeg','Scan 2.jpeg']},{'part':'sideb','files':['Scan 3.jpeg','Scan 4.jpeg']},{'part':'','files':['Scan 5.jpeg','Scan 6.jpeg']}],layout
    mixed=[dict(rows[0]),dict(rows[1],part='sideb')]
    assert B.layout_from_groups(mixed)==[{'part':'','files':['Scan 1.jpeg','Scan 2.jpeg']}]
    assert B.layout_from_groups([dict(r,group='') for r in rows])==[]
    (folder/'.anouk-referenties.json').write_text(json.dumps({'note':'kept'}))
    B.remember_layout(rows,layout)
    saved=json.loads((folder/'.anouk-referenties.json').read_text())
    assert saved['scan_groups']==layout and saved['reference_files']==['Scan 8.jpeg'] and saved['note']=='kept'
print('Arrange slots: grouping followed, mixed parts left to Sleeve, layout remembered per folder.')

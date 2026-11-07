"""Placement of four quarter-turned parts: errors along the tree must not pile up on one seam."""
from pathlib import Path
import sys
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Resources/Tools'))
import scan_stitch as ST
rng=np.random.default_rng(3)
def rigid(angle,tx,ty):
    a=np.radians(angle);return np.array([[np.cos(a),-np.sin(a),tx],[np.sin(a),np.cos(a),ty],[0,0,1.0]])
# True placement of four parts (a quarter turn each) on one canvas.
truth={0:np.eye(3),1:rigid(90,2400,0),2:rigid(180,2400,2400),3:rigid(270,0,2400)}
canvas=rng.uniform(300,2100,(4000,2))
pairs={}
for i in range(4):
    for j in range(4):
        if i!=j:
            pts=canvas[rng.choice(len(canvas),600,replace=False)]
            to=lambda k:(np.c_[pts,np.ones(len(pts))]@np.linalg.inv(truth[k]).T)[:,:2]
            pairs[(i,j)]=(np.float32(to(j)+rng.normal(0,.3,(600,2))),np.float32(to(i)+rng.normal(0,.3,(600,2))))
# Tree placement: each part via one neighbour, small errors add up on the 2-3 seam.
tree={0:truth[0],1:rigid(90.03,2401.0,0),3:rigid(269.97,0,2401.0)}
tree[2]=tree[1]@np.linalg.inv(truth[1])@truth[2]@rigid(.03,1.0,0)
D=np.array([1.0,1.0],np.float32)
links={k:v for k,v in pairs.items() if k[0]<k[1]}
before=ST.pair_errors(tree,links)
after=ST.pair_errors(ST.refine_placement(tree,0,pairs,D),links)
assert max(before.values())>2.0 and max(after.values())<max(before.values())*0.6,(before,after)
assert all(after[k]<=before[k]+ST.REFINE_SLACK for k in links)
# Without a loop (a single overlap) the tree is already the only answer.
single={(0,1):pairs[(0,1)],(1,0):pairs[(1,0)]}
assert ST.refine_placement({0:tree[0],1:tree[1]},0,single,D)[1] is tree[1]
print('Placement over all overlaps: worst seam %.2f -> %.2f px; single overlap unchanged.'%(max(before.values()),max(after.values())))

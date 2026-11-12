#!/usr/bin/env python3
"""Een plaatkleur uit een referentiefoto toepassen, met etiket en alfa intact.
Deze expliciete kleurproef verandert geen vorm, stand, namen of ontbrekende delen.
"""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
AUTO_DELTA=12.  # ΔE (Lab) tussen scan en Discogs-foto waarboven Sleeve zelf een kleurvoorstel maakt

def swatch(image,reference=False):
 a=image.copy();a.thumbnail((1000,1000));rgb=np.asarray(a.convert('RGB'));h,w=rgb.shape[:2]
 yy,xx=np.ogrid[:h,:w];r=np.hypot(xx-w/2,yy-h/2)/(min(w,h)/2)
 mask=(r>.47)&(r<.80)
 if image.mode=='RGBA':mask&=np.asarray(a.getchannel('A'))>250
 hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
 if reference:
  chroma=mask&(hsv[:,:,1]>60)&(hsv[:,:,2]>60)
  if chroma.sum()<.02*mask.size:raise ValueError('The reference photo has too little colored record outside the label.')
  mask=chroma
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 return np.median(lab[mask],axis=0)

def discogs_proposal(path,images):
 """Zoek tussen de Discogs-foto's (BGR) die van deze plaat (het label past) en
 vergelijk de plaatkleur. De foto wordt in de stand van de scan gelegd, zodat
 swatch() dezelfde ring meet. Geeft None zonder bruikbare gekleurde foto."""
 import scan_discogs as D
 with Image.open(path) as im:raw=im.convert('RGBA');raw.thumbnail((1000,1000))
 ours=D.on_white(cv2.cvtColor(np.asarray(raw),cv2.COLOR_RGBA2BGRA))
 best=None
 for count,index,M in D.matches(ours,images)[:4]:
  aligned=cv2.warpAffine(images[index],cv2.invertAffineTransform(M),(ours.shape[1],ours.shape[0]),flags=cv2.INTER_AREA,borderValue=(0,0,0))
  photo=Image.fromarray(cv2.cvtColor(aligned,cv2.COLOR_BGR2RGB))
  try:target=swatch(photo,True)
  except ValueError:continue
  if best is None or count>best['matches']:best={'matches':count,'photo':index+1,'reference':photo,'target':target}
 if best is None:return None
 best['source']=swatch(raw);best['delta']=float(np.linalg.norm(best['target']-best['source']))
 return best

# Tintbereik (Lab-hoek in graden) per Discogs-kleurnaam. Neutrale kleuren
# (zilver, zwart, clear …) en mengvormen (marbled, splatter) zijn bewust weggelaten:
# Discogs-foto's daarvan zijn te wisselend belicht om op te vertrouwen.
HUES={'red':(10,42),'orange':(43,75),'yellow':(76,105),'gold':(60,100),'green':(110,200),
      'turquoise':(180,230),'blue':(220,300),'purple':(290,330),'magenta':(320,355),'pink':(330,30)}

def fits(lab,name):
 hue=np.degrees(np.arctan2(lab[2],lab[1]))%360;lo,hi=HUES[name]
 return float(np.hypot(lab[1],lab[2]))>=8 and (lo<=hue<=hi if lo<hi else hue>=lo or hue<=hi)

def vinyl_plan(paths,images,name):
 """Welke plaatkanten wijken af van de Discogs-kleurnaam, en met welke foto
 (waarvan de tint wél bij die naam past) kan Sleeve een voorstel maken?
 Eén referentie voor de hele uitgave: beide kanten hebben dezelfde plaat."""
 if name not in HUES:return {},None
 proposals={path:discogs_proposal(path,images) for path in paths}
 usable=[p for p in proposals.values() if p and fits(p['target'],name)]
 if not usable:return {},None
 chosen=max(usable,key=lambda p:p['matches'])
 plan={}
 for path,p in proposals.items():
  with Image.open(path) as im:source=swatch(im.convert('RGBA'))
  if not fits(source,name):plan[path]=source
 return plan,chosen

def label_edge(raw,source,n=360):
 """Feit: het label houdt op waar de plaat begint. Per richting vanuit het midden: van buiten naar
 binnen lopen tot de kleur geen plaatkleur meer is. Geeft per richting de straal van het label
 (deel van de plaatstraal), of None als dat niet rondom te meten is (dan de vaste grens 0,34)."""
 a=raw.copy();a.thumbnail((2400,2400));rgb=np.asarray(a.convert('RGB'));h,w=rgb.shape[:2];R=min(w,h)/2
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 radii=np.arange(.42,.27,-.5/R);out=np.full(n,np.nan,np.float32)
 inner=lab[int(h/2-.2*R):int(h/2+.2*R),int(w/2-.2*R):int(w/2+.2*R)].reshape(-1,3)
 paper=np.median(inner,axis=0);gap=float(np.linalg.norm(paper-source))
 if gap<15:return None                                   # label en plaat lijken te veel op elkaar
 for k in range(n):
  t=2*np.pi*k/n;xs=(w/2+radii*R*np.cos(t)).astype(int).clip(0,w-1);ys=(h/2+radii*R*np.sin(t)).astype(int).clip(0,h-1)
  d=np.linalg.norm(lab[ys,xs]-source,axis=1)
  off=np.nonzero(d>.5*gap)[0]
  if len(off) and off[0]>3:out[k]=radii[off[0]-1]         # de laatste straal die nog plaat is
 if np.isnan(out).mean()>.2:return None
 med=np.nanmedian(out);out=np.where(np.isnan(out),med,out)
 pad=np.r_[out[-8:],out,out[:8]];out=np.array([np.median(pad[i:i+17]) for i in range(n)],np.float32)   # glad over ±8 graden
 if not (.30<=out.min() and out.max()<=.40) or out.std()>.012:return None
 return out

def photo_target(raw,reference):
 """Feit: op jouw foto staat dezelfde plaat met hetzelfde label. Het label wijst de plaat aan in de
 foto (waar hij ook ligt), en is in scan en foto hetzelfde papier: daarmee wordt de belichting en de
 kleurzweem van de foto gelijkgetrokken met de scan. Daarna is de plaatkleur van de foto de maat.
 Geeft (Lab, toelichting) of None als het label niet in de foto te vinden is."""
 import scan_discogs as D
 small=raw.copy();small.thumbnail((1000,1000))
 ours=D.on_white(cv2.cvtColor(np.asarray(small),cv2.COLOR_RGBA2BGRA))
 photo=cv2.cvtColor(np.asarray(reference.convert('RGB')),cv2.COLOR_RGB2BGR)
 k=2000/max(photo.shape[:2])
 if k<1:photo=cv2.resize(photo,None,fx=k,fy=k,interpolation=cv2.INTER_AREA)
 found=D.matches(ours,[photo])
 if not found or found[0][0]<25:return None
 M=found[0][2];h,w=ours.shape[:2]
 inv=cv2.invertAffineTransform(M)
 aligned=cv2.warpAffine(photo,inv,(w,h),flags=cv2.INTER_AREA,borderValue=(0,0,0))
 inside=cv2.warpAffine(np.full(photo.shape[:2],255,np.uint8),inv,(w,h),flags=cv2.INTER_NEAREST)>0
 yy,xx=np.ogrid[:h,:w];r=np.hypot(xx-w/2,yy-h/2)/(min(w,h)/2)
 alpha=np.asarray(small.getchannel('A'))>250
 lin=lambda bgr:np.where(bgr<=.04045,bgr/12.92,((bgr+.055)/1.055)**2.4)
 label=(r>.14)&(r<.29)&inside&alpha
 if label.sum()<500:return None
 scan_label=np.median(ours[label].astype(np.float32)/255,axis=0);photo_label=np.median(aligned[label].astype(np.float32)/255,axis=0)
 if photo_label.max()>.98 or photo_label.min()<.08:return None      # label overbelicht of te donker: geen betrouwbare maat
 gain=lin(scan_label)/np.maximum(lin(photo_label),1e-4)
 fixed=np.clip(lin(aligned.astype(np.float32)/255)*gain,0,1)
 fixed=np.where(fixed<=.0031308,fixed*12.92,1.055*fixed**(1/2.4)-.055).astype(np.float32)
 ring=(r>.47)&(r<.80)&inside&alpha
 if ring.sum()<.3*((r>.47)&(r<.80)).sum():return None                # de plaat staat niet genoeg op de foto
 lab=cv2.cvtColor(fixed[:,:,::-1].copy(),cv2.COLOR_RGB2LAB)
 return np.median(lab[ring],axis=0),{'matches':int(found[0][0]),'label_gain_bgr':[round(float(g),3) for g in gain]}

def recolor(src,reference,dst,strength=1.,progress=None):
 with Image.open(src) as im:raw=im.convert('RGBA')
 source=swatch(raw);how={'reference':'ring around the photo centre'}
 with Image.open(reference) as ref:
  found=None
  try:found=photo_target(raw,ref)
  except Exception:found=None
  if found:target,note=found;how={'reference':'record located by its label; exposure matched on the label',**note}
  else:target=swatch(ref,True)
 w,h=raw.size;out=raw;xs=np.arange(w,dtype=np.float32)[None,:]
 edge=label_edge(raw,source)
 if progress:progress(0.,"Applying color")
 for y in range(0,h,256):
  block=np.array(raw.crop((0,y,w,min(y+256,h))))
  yy=np.arange(y,min(y+256,h),dtype=np.float32)[:,None]
  r=np.hypot(xs-w/2,yy-h/2)/(min(w,h)/2)
  if edge is None:weight=np.clip((r-.34)/.018,0,1)
  else:
   # tot aan de gemeten rand van het label kleuren (overgang van ±0,5 mm), zodat er geen donkere ring blijft staan
   at=edge[(np.degrees(np.arctan2(yy-h/2,xs-w/2))%360/360*len(edge)).astype(int)%len(edge)]
   weight=np.clip((r-at)/.0035,0,1)
  weight=weight*strength*(block[:,:,3]>0)
  lab=cv2.cvtColor(block[:,:,:3].astype(np.float32)/255,cv2.COLOR_RGB2LAB)
  desired=lab.copy();desired[:,:,0]=target[0]+(lab[:,:,0]-source[0])*.85
  desired[:,:,1:]=target[1:]+(lab[:,:,1:]-source[1:])*.25
  lab=lab*(1-weight[:,:,None])+desired*weight[:,:,None]
  rgb=(cv2.cvtColor(lab,cv2.COLOR_LAB2RGB).clip(0,1)*255+.5).astype(np.uint8)
  rgb[weight==0]=block[:,:,:3][weight==0];block[:,:,:3]=rgb
  out.paste(Image.fromarray(block),(0,y))
  if progress:progress(min(y+256,h)/h,"Applying color")
 if progress:progress(None,"Saving color suggestion")
 metadata={key:raw.info[key] for key in ('dpi','icc_profile') if key in raw.info}
 out.save(dst,compress_level=3,**metadata)
 print(json.dumps({'source':str(src),'reference':str(reference),'output':str(dst),'strength':strength,'source_lab':source.tolist(),'reference_lab':np.asarray(target).tolist(),'label_protected_to_radius':.34 if edge is None else [round(float(edge.min()),4),round(float(edge.max()),4)],**how},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('reference');p.add_argument('output');p.add_argument('--strength',type=float,default=1.)
 a=p.parse_args();assert 0<=a.strength<=1
 recolor(a.source,a.reference,a.output,a.strength)

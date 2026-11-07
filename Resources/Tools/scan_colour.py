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

def recolor(src,reference,dst,strength=1.,progress=None):
 with Image.open(src) as im:raw=im.convert('RGBA')
 with Image.open(reference) as ref:target=swatch(ref,True)
 source=swatch(raw);w,h=raw.size;out=raw;xs=np.arange(w,dtype=np.float32)[None,:]
 if progress:progress(0.,"Applying color")
 for y in range(0,h,256):
  block=np.array(raw.crop((0,y,w,min(y+256,h))))
  yy=np.arange(y,min(y+256,h),dtype=np.float32)[:,None]
  r=np.hypot(xs-w/2,yy-h/2)/(min(w,h)/2)
  weight=np.clip((r-.34)/.018,0,1)*strength*(block[:,:,3]>0)
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
 print(json.dumps({'source':str(src),'reference':str(reference),'output':str(dst),'strength':strength,'source_lab':source.tolist(),'reference_lab':target.tolist(),'label_protected_to_radius':.34},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('reference');p.add_argument('output');p.add_argument('--strength',type=float,default=1.)
 a=p.parse_args();assert 0<=a.strength<=1
 recolor(a.source,a.reference,a.output,a.strength)

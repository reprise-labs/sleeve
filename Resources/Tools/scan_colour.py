#!/usr/bin/env python3
"""Een plaatkleur uit een referentiefoto toepassen, met etiket en alfa intact.
Deze expliciete kleurproef verandert geen vorm, stand, namen of ontbrekende delen.
"""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS=None

def swatch(image,reference=False):
 a=image.copy();a.thumbnail((1000,1000));rgb=np.asarray(a.convert('RGB'));h,w=rgb.shape[:2]
 yy,xx=np.ogrid[:h,:w];r=np.hypot(xx-w/2,yy-h/2)/(min(w,h)/2)
 mask=(r>.47)&(r<.80)
 if image.mode=='RGBA':mask&=np.asarray(a.getchannel('A'))>250
 hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
 if reference:
  chroma=mask&(hsv[:,:,1]>60)&(hsv[:,:,2]>60)
  if chroma.sum()<.02*mask.size:raise ValueError('Referentiefoto heeft te weinig gekleurde plaat buiten het etiket.')
  mask=chroma
 lab=cv2.cvtColor(rgb.astype(np.float32)/255,cv2.COLOR_RGB2LAB)
 return np.median(lab[mask],axis=0)

def recolor(src,reference,dst,strength=1.,progress=None):
 with Image.open(src) as im:raw=im.convert('RGBA')
 with Image.open(reference) as ref:target=swatch(ref,True)
 source=swatch(raw);w,h=raw.size;out=raw.copy();xs=np.arange(w,dtype=np.float32)[None,:]
 if progress:progress(0.,"Kleur toepassen")
 for y in range(0,h,512):
  block=np.array(raw.crop((0,y,w,min(y+512,h))))
  yy=np.arange(y,min(y+512,h),dtype=np.float32)[:,None]
  r=np.hypot(xs-w/2,yy-h/2)/(min(w,h)/2)
  weight=np.clip((r-.34)/.018,0,1)*strength*(block[:,:,3]>0)
  lab=cv2.cvtColor(block[:,:,:3].astype(np.float32)/255,cv2.COLOR_RGB2LAB)
  desired=lab.copy();desired[:,:,0]=target[0]+(lab[:,:,0]-source[0])*.85
  desired[:,:,1:]=target[1:]+(lab[:,:,1:]-source[1:])*.25
  lab=lab*(1-weight[:,:,None])+desired*weight[:,:,None]
  rgb=(cv2.cvtColor(lab,cv2.COLOR_LAB2RGB).clip(0,1)*255+.5).astype(np.uint8)
  rgb[weight==0]=block[:,:,:3][weight==0];block[:,:,:3]=rgb
  out.paste(Image.fromarray(block),(0,y))
  if progress:progress(min(y+512,h)/h,"Kleur toepassen")
 if progress:progress(None,"Kleurvoorstel opslaan")
 metadata={key:raw.info[key] for key in ('dpi','icc_profile') if key in raw.info}
 out.save(dst,compress_level=3,**metadata)
 print(json.dumps({'source':str(src),'reference':str(reference),'output':str(dst),'strength':strength,'source_lab':source.tolist(),'reference_lab':target.tolist(),'label_protected_to_radius':.34},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('reference');p.add_argument('output');p.add_argument('--strength',type=float,default=1.)
 a=p.parse_args();assert 0<=a.strength<=1
 recolor(a.source,a.reference,a.output,a.strength)

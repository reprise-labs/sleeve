"""Job-local, exact-scale sRGB work previews; never substitute a nearby scale."""
import hashlib,os
from pathlib import Path
import numpy as np


def cache_path(path,scale):
    root=os.environ.get('SLEEVE_WORK_PREVIEWS')
    if not root:return None
    source=Path(path).resolve();stat=source.stat()
    signature=f'{source}\0{stat.st_size}\0{stat.st_mtime_ns}\0{float(scale).hex()}'
    return Path(root)/(hashlib.sha256(signature.encode()).hexdigest()+'.npy')


def put(path,scale,image):
    destination=cache_path(path,scale)
    if destination is None:return
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.tmp')
    try:
        with temporary.open('wb') as file:np.save(file,image,allow_pickle=False)
        os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)


def get(path,scale,consume=False):
    destination=cache_path(path,scale)
    if destination is None or not destination.exists():return None
    from PIL import Image
    try:
        with Image.open(path) as source:shape=(max(1,round(source.height*scale)),max(1,round(source.width*scale)),3)
        image=np.load(destination,allow_pickle=False)
        if image.dtype==np.uint8 and image.shape==shape:
            if consume:destination.unlink(missing_ok=True)
            return image
    except (OSError,ValueError,EOFError):pass
    return None

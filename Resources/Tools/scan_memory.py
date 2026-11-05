"""Bounded full-resolution sources, with anonymous scratch files on macOS/POSIX."""
import gc,mmap,os,shutil,subprocess,tempfile
import numpy as np
from PIL import Image
MiB=1024**2
GiB=1024**3

def physical_memory():
    try:
        return int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'],timeout=2))
    except (OSError,ValueError,subprocess.SubprocessError):
        return 8*GiB

def render_tile_size():
    return 1024 if physical_memory() <= 8*GiB else 2048

class MappedScanStore:
    """Decode each source once; resident source pages can be dropped after each tile.

    TemporaryFile is unlinked on POSIX, so a killed worker cannot leave large raw
    scratch files behind. No source is modified and no resolution is reduced.
    """
    def __init__(self,paths,keys,loader,output_bytes=0,scratch=None,on_loaded=None):
        self.paths=paths;self.keys=list(keys);self.loader=loader;self.on_loaded=on_loaded
        self.arrays={};self.maps=[];self.scratch=scratch or tempfile.gettempdir()
        total=0;maximum=0
        for k in self.keys:
            with Image.open(paths[k]) as im:
                size=im.width*im.height*3;total+=size;maximum=max(maximum,size)
        needed=total+int(output_bytes)+GiB
        free=shutil.disk_usage(self.scratch).free
        if free < needed:
            raise ValueError(f'Te weinig vrije schijfruimte voor veilig samenvoegen: ongeveer {needed/GiB:.1f} GB nodig, {free/GiB:.1f} GB vrij. Maak ruimte vrij en probeer opnieuw.')
        if maximum*4 > physical_memory()*.35:
            raise ValueError('Een afzonderlijke scan is te groot om op deze Mac veilig te openen. Gebruik een scan op lagere resolutie of een Mac met meer geheugen.')
        self.required_bytes=needed
    def __enter__(self):
        try:
            for k in self.keys:
                source=self.loader(self.paths[k],1.0)
                shape=source.shape;length=source.nbytes
                # Write the already colour-normalized BGR bytes without another full copy.
                with tempfile.TemporaryFile(prefix='sleeve-scan-',dir=self.scratch) as file:
                    file.truncate(length)
                    write_map=mmap.mmap(file.fileno(),length,access=mmap.ACCESS_WRITE)
                    try:
                        write_map.write(memoryview(source).cast('B'))
                        del source
                        write_map.flush()
                        read_map=mmap.mmap(file.fileno(),length,access=mmap.ACCESS_READ)
                    finally:
                        write_map.close()
                    self.maps.append(read_map)
                    self.arrays[k]=np.ndarray(shape,dtype=np.uint8,buffer=read_map)
                    self.arrays[k].setflags(write=False)
                    self.drop_pages()
                gc.collect()
                if self.on_loaded:self.on_loaded(len(self.arrays),len(self.keys))
            return self
        except BaseException:
            self.close();raise
    def __getitem__(self,key):return self.arrays[key]
    def drop_pages(self):
        for mapped in self.maps:
            if hasattr(mapped,'madvise') and hasattr(mmap,'MADV_DONTNEED'):
                try:mapped.madvise(mmap.MADV_DONTNEED)
                except (OSError,ValueError):pass
    def close(self):
        self.arrays.clear()
        for mapped in self.maps:mapped.close()
        self.maps.clear()
    def __exit__(self,*args):self.close()

class MappedArrayStore:
    """Exact float32 work buffers backed by anonymous files, not anonymous RAM."""
    def __init__(self,expected_bytes,scratch=None):
        self.scratch=scratch or tempfile.gettempdir();self.arrays={};self.maps={}
        needed=int(expected_bytes)+GiB;free=shutil.disk_usage(self.scratch).free
        if free<needed:raise ValueError(f'Te weinig vrije schijfruimte voor veilig samenvoegen: ongeveer {needed/GiB:.1f} GB nodig, {free/GiB:.1f} GB vrij. Maak ruimte vrij en probeer opnieuw.')
    def empty(self,key,shape,dtype=np.float32):
        self.discard(key)
        dtype=np.dtype(dtype);length=int(np.prod(shape))*dtype.itemsize
        with tempfile.TemporaryFile(prefix='sleeve-work-',dir=self.scratch) as file:
            file.truncate(length);mapped=mmap.mmap(file.fileno(),length,access=mmap.ACCESS_WRITE)
        self.maps[key]=mapped;self.arrays[key]=np.ndarray(shape,dtype=dtype,buffer=mapped)
        return self.arrays[key]
    def put(self,key,value):
        result=self.empty(key,value.shape,value.dtype);result[:]=value;self.drop_pages();return result
    def discard(self,key):
        self.arrays.pop(key,None)
        mapped=self.maps.pop(key,None)
        if mapped is not None:mapped.close()
    def keep_only(self,keys):
        for key in list(self.maps):
            if key not in keys:self.discard(key)
    def drop_pages(self):
        for mapped in self.maps.values():drop_mapping_pages(mapped)
    def close(self):
        self.arrays.clear()
        for mapped in self.maps.values():mapped.close()
        self.maps.clear()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def drop_mapping_pages(mapped):
    try:
        mapped.flush()
        if hasattr(mapped,'madvise') and hasattr(mmap,'MADV_DONTNEED'):mapped.madvise(mmap.MADV_DONTNEED)
    except (OSError,ValueError):pass

def drop_array_pages(array):
    base=getattr(array,'base',None)
    while isinstance(base,np.ndarray):base=base.base
    if isinstance(base,mmap.mmap):drop_mapping_pages(base)

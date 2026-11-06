"""Bounded full-resolution sources, with anonymous scratch files on macOS/POSIX."""
import gc,mmap,os,shutil,subprocess,tempfile
import numpy as np
from PIL import Image
MiB=1024**2
GiB=1024**3
GB=1000**3

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
    def __init__(self,paths,keys,loader,output_bytes=0,scratch=None,on_loaded=None,decode_into=None,on_reserved=None):
        self.paths=paths;self.keys=list(keys);self.loader=loader;self.on_loaded=on_loaded;self.decode_into=decode_into;self.on_reserved=on_reserved;self.shapes={}
        self.arrays={};self.maps=[];self.scratch=scratch or tempfile.gettempdir()
        total=0;maximum=0
        for k in self.keys:
            with Image.open(paths[k]) as im:
                size=im.width*im.height*3;total+=size;maximum=max(maximum,size)
                self.shapes[k]=(im.height,im.width,3)
        needed=total+int(output_bytes)+GiB
        free=shutil.disk_usage(self.scratch).free
        if free < needed and not os.environ.get('SLEEVE_MEMORY_POOL'):
            raise ValueError(f'Te weinig vrije schijfruimte voor veilig samenvoegen: ongeveer {needed/GB:.1f} GB nodig, {free/GB:.1f} GB vrij. Maak ruimte vrij en probeer opnieuw.')
        if maximum*4 > physical_memory()*.35:
            raise ValueError('Een afzonderlijke scan is te groot om op deze Mac veilig te openen. Gebruik een scan op lagere resolutie of een Mac met meer geheugen.')
        self.required_bytes=needed
        self.space=ScratchLease(needed,self.scratch)
    def __enter__(self):
        try:
            self.space.__enter__()
            if self.on_reserved:self.on_reserved()
            for k in self.keys:
                source=None
                if self.decode_into is None:
                    source=self.loader(self.paths[k],1.0)
                    shape=source.shape;length=source.nbytes
                else:
                    shape=self.shapes[k];length=int(np.prod(shape))
                # Write the already colour-normalized BGR bytes without another full copy.
                with tempfile.TemporaryFile(prefix='sleeve-scan-',dir=self.scratch) as file:
                    file.truncate(length)
                    write_map=mmap.mmap(file.fileno(),length,access=mmap.ACCESS_WRITE)
                    try:
                        if self.decode_into is None:
                            write_map.write(memoryview(source).cast('B'))
                            del source
                        else:
                            target=np.ndarray(shape,dtype=np.uint8,buffer=write_map)
                            try:self.decode_into(self.paths[k],target)
                            finally:target=None
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
        self.space.__exit__(None,None,None)
    def __exit__(self,*args):self.close()

class MappedArrayStore:
    """Exact float32 work buffers backed by anonymous files, not anonymous RAM."""
    def __init__(self,expected_bytes,scratch=None):
        self.scratch=scratch or tempfile.gettempdir();self.arrays={};self.maps={}
        needed=int(expected_bytes)+GiB;free=shutil.disk_usage(self.scratch).free
        if free<needed:raise ValueError(f'Te weinig vrije schijfruimte voor veilig samenvoegen: ongeveer {needed/GB:.1f} GB nodig, {free/GB:.1f} GB vrij. Maak ruimte vrij en probeer opnieuw.')
        self.activity=ScratchActivity()
    def empty(self,key,shape,dtype=np.float32):
        self.discard(key)
        dtype=np.dtype(dtype);length=int(np.prod(shape))*dtype.itemsize
        with tempfile.TemporaryFile(prefix='sleeve-work-',dir=self.scratch) as file:
            file.truncate(length);mapped=mmap.mmap(file.fileno(),length,access=mmap.ACCESS_WRITE)
        self.maps[key]=mapped;self.arrays[key]=np.ndarray(shape,dtype=dtype,buffer=mapped)
        self.activity.set(True)
        return self.arrays[key]
    def put(self,key,value):
        result=self.empty(key,value.shape,value.dtype);result[:]=value;self.drop_pages();return result
    def discard(self,key):
        self.arrays.pop(key,None)
        mapped=self.maps.pop(key,None)
        if mapped is not None:mapped.close()
        if not self.maps:self.activity.set(False)
    def keep_only(self,keys):
        for key in list(self.maps):
            if key not in keys:self.discard(key)
    def drop_pages(self):
        for mapped in self.maps.values():drop_mapping_pages(mapped)
    def close(self):
        self.arrays.clear()
        for mapped in self.maps.values():mapped.close()
        self.maps.clear()
        self.activity.set(False)
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


def flush_array_rows(array,start,stop):
    """Flush/release only completed page-aligned rows of a mapped decoder target."""
    base=array.base
    if not isinstance(base,mmap.mmap):return
    page=mmap.PAGESIZE
    offset=(int(start)*array.strides[0]//page)*page
    end=min(len(base),((int(stop)*array.strides[0]+page-1)//page)*page)
    base.flush(offset,end-offset)
    if hasattr(base,'madvise') and hasattr(mmap,'MADV_DONTNEED'):
        try:base.madvise(mmap.MADV_DONTNEED,offset,end-offset)
        except (OSError,ValueError):pass


class MemoryLease:
    """Cross-process memory budget; 64 MiB admission units shared by preparation, decoding and rendering."""
    def __init__(self,weight=3,phase=None):
        self.weight=weight;self.held=[];self.phase=phase
        self.root=os.environ.get('SLEEVE_MEMORY_POOL')
        self.capacity=int(os.environ.get('SLEEVE_MEMORY_SLOTS','72'))
    def __enter__(self):
        if not self.root:return self
        import fcntl,time
        from pathlib import Path
        if not 1<=self.weight<=self.capacity:raise ValueError('Invalid memory budget')
        root=Path(self.root);root.mkdir(parents=True,exist_ok=True)
        announced=False
        while not self.held:
            acquired=[]
            try:
                with (root/'guard').open('a+b') as guard:
                    fcntl.flock(guard,fcntl.LOCK_EX)
                    ticket=root/os.environ['SLEEVE_MEMORY_START'] if os.environ.get('SLEEVE_MEMORY_START') else None
                    pending=sorted(root.glob('start-*')) if ticket is not None and ticket.exists() else []
                    eligible=not pending or pending[0]==ticket
                    for index in range(self.capacity) if eligible else ():
                        slot=(root/str(index)).open('a+b')
                        try:fcntl.flock(slot,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        except BlockingIOError:slot.close();continue
                        except BaseException:slot.close();raise
                        acquired.append(slot)
                        if len(acquired)==self.weight:
                            self.held=acquired;acquired=[]
                            if ticket is not None:ticket.unlink(missing_ok=True)
                            break
            finally:
                for slot in acquired:slot.close()
            if not self.held:
                if not announced:
                    from scan_progress import progress
                    progress('Wachten op beschikbaar werkgeheugen');announced=True
                time.sleep(.05)
        if announced and self.phase:
            from scan_progress import progress
            progress(self.phase)
        return self
    def resize(self,weight):
        if weight>self.weight:raise ValueError('A memory lease can only shrink')
        self.weight=weight
        while len(self.held)>weight:self.held.pop().close()
    def grow(self,weight,phase=None):
        """Acquire the decoder budget after reserving disk, retaining small fields.

        Callers first held the larger preparation budget, then shrank it to the
        resident fields. Thus the last preparer can always regain its former
        budget; no renderer grows again before releasing its source maps.
        """
        if weight<=self.weight:self.resize(weight);return
        if not self.root:self.weight=weight;return
        if weight>self.capacity:raise ValueError('Invalid memory budget')
        import fcntl,time
        from pathlib import Path
        root=Path(self.root);announced=False
        while self.weight<weight:
            acquired=[]
            try:
                with (root/'guard').open('a+b') as guard:
                    fcntl.flock(guard,fcntl.LOCK_EX)
                    held_names={slot.name for slot in self.held}
                    for index in range(self.capacity):
                        if str(root/str(index)) in held_names:continue
                        slot=(root/str(index)).open('a+b')
                        try:fcntl.flock(slot,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        except BlockingIOError:slot.close();continue
                        except BaseException:slot.close();raise
                        acquired.append(slot)
                        if len(acquired)==weight-self.weight:
                            self.held.extend(acquired);acquired=[];self.weight=weight;break
            finally:
                for slot in acquired:slot.close()
            if self.weight<weight:
                if not announced:
                    from scan_progress import progress
                    progress('Wachten op beschikbaar werkgeheugen');announced=True
                time.sleep(.05)
        if announced and phase:
            from scan_progress import progress
            progress(phase)

    def release(self):
        while self.held:self.held.pop().close()
    def __exit__(self,*args):self.release()


class ScratchLease:
    """Reserve unwritten bytes, then account for committed source/output pages.

    Allocation already visible in disk_usage is never subtracted a second time.
    Workers wait only while another live renderer can release its source maps.
    """
    def __init__(self,needed,scratch):
        import uuid
        from pathlib import Path
        self.needed=int(needed);self.remaining=max(0,self.needed-GiB);self.scratch=scratch
        root=os.environ.get('SLEEVE_MEMORY_POOL')
        self.root=Path(root) if root else None
        self.marker=self.root/('scratch-'+uuid.uuid4().hex+'.json') if root else None
        self.active=False
    def write(self):
        import json
        temporary=self.marker.with_suffix('.tmp')
        temporary.write_text(json.dumps({'pid':os.getpid(),'remaining':self.remaining}))
        os.replace(temporary,self.marker)
    def __enter__(self):
        if self.root is None:return self
        import fcntl,json,time
        self.root.mkdir(exist_ok=True,parents=True);announced=False
        while True:
            with (self.root/'scratch-guard').open('a+b') as guard:
                fcntl.flock(guard,fcntl.LOCK_EX)
                reserved=0;others=0
                for path in self.root.glob('scratch-*.json'):
                    try:
                        item=json.loads(path.read_text());pid=int(item['pid'])
                        if pid<=0:raise ValueError('Invalid pid')
                        os.kill(pid,0)
                        # Our own work buffers cannot make progress while this
                        # thread waits here; do not count them as another producer.
                        if item.get('activity') and pid==os.getpid():continue
                        reserved+=max(0,int(item['remaining']));others+=1
                    except (OSError,ValueError,KeyError,TypeError):path.unlink(missing_ok=True)
                free=shutil.disk_usage(self.scratch).free
                if free-reserved>=self.needed:
                    self.write();self.active=True;break
                if not others:
                    raise ValueError(f'Te weinig vrije schijfruimte voor veilig samenvoegen: ongeveer {self.needed/GB:.1f} GB nodig, {free/GB:.1f} GB vrij. Maak ruimte vrij en probeer opnieuw.')
            if not announced:
                from scan_progress import progress
                progress('Wachten op tijdelijke schijfruimte');announced=True
            time.sleep(.1)
        if announced:
            from scan_progress import progress
            progress('Originele scans openen')
        return self
    def committed(self,count):
        if not self.active:return
        import fcntl
        with (self.root/'scratch-guard').open('a+b') as guard:
            fcntl.flock(guard,fcntl.LOCK_EX)
            self.remaining=max(0,self.remaining-int(count));self.write()
    def __exit__(self,*args):
        if self.active:self.marker.unlink(missing_ok=True);self.active=False


class ScratchActivity:
    """Keep live mapped work/output buffers visible until their maps close.

    These bytes already appear in disk_usage, so they reserve no extra space.
    Unlike source maps, output maps remain alive during repair and PNG encoding.
    """
    def __init__(self):
        import uuid
        from pathlib import Path
        root=os.environ.get('SLEEVE_MEMORY_POOL')
        self.root=Path(root) if root else None
        self.marker=self.root/('scratch-work-'+uuid.uuid4().hex+'.json') if root else None
        self.active=False
    def set(self,active):
        if self.root is None or active==self.active:return
        import fcntl,json
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'scratch-guard').open('a+b') as guard:
            fcntl.flock(guard,fcntl.LOCK_EX)
            if active:
                temporary=self.marker.with_suffix('.tmp')
                temporary.write_text(json.dumps({'pid':os.getpid(),'remaining':0,'activity':True}))
                os.replace(temporary,self.marker)
            else:self.marker.unlink(missing_ok=True)
            self.active=active

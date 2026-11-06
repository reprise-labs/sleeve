"""Isolated component processes, shared memory budget, and indexed progress."""
import concurrent.futures,json,os,re,signal,subprocess,sys,threading
from pathlib import Path


class ComponentPool:
    def __init__(self,total,folder,workers=3):
        self.total=total;self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.workers=workers;self.lock=threading.RLock();self.running={};self.active=set();self.completed=0
        self.cancelled=threading.Event();self.previous={};self.start_tickets={}

    def __enter__(self):
        for sig in (signal.SIGTERM,signal.SIGINT):
            self.previous[sig]=signal.getsignal(sig)
            signal.signal(sig,self.stop)
        return self

    def stop(self,signum,frame):
        self.cancel()
        raise SystemExit(128+signum)

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            processes=list(self.running.values())
            for process in processes:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        for process in processes:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()

    def emit(self,index,payload):
        with self.lock:
            payload=dict(payload,scope='component',componentIndex=index,componentTotal=self.total,activeParts=len(self.active),completedParts=self.completed)
            print('SLEEVE_PROGRESS '+json.dumps(payload,ensure_ascii=False),flush=True)

    def forward(self,index,line):
        text=line.rstrip()
        if text.startswith('SLEEVE_PROGRESS '):
            try:self.emit(index,json.loads(text[len('SLEEVE_PROGRESS '):]))
            except ValueError:pass
        elif re.fullmatch(r'\s*\d+%',text):
            self.emit(index,{'phase':'Beeld opbouwen','fraction':int(text.strip()[:-1])/100})
        else:
            with self.lock:
                if re.match(r'^\[\d+/\d+\]',text) or text.startswith('klaar:'):
                    text='Onderdeel '+str(index)+': '+text
                print(text,flush=True)

    def execute(self,index,command):
        env=dict(os.environ,SLEEVE_MEMORY_POOL=str((self.folder/'memory').resolve()),SLEEVE_MEMORY_SLOTS='72',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',VECLIB_MAXIMUM_THREADS='1')
        if index in self.start_tickets:env['SLEEVE_MEMORY_START']=self.start_tickets[index].name
        with self.lock:
            if self.cancelled.is_set():raise RuntimeError('Verwerking gestopt')
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env=env)
            self.running[index]=process;self.active.add(index)
        self.emit(index,{'phase':'Onderdeel voorbereiden','fraction':None})
        try:
            for line in process.stdout:self.forward(index,line)
            code=process.wait()
            if code:raise RuntimeError(f'Onderdeel {index} is niet afgerond (code {code}). Bekijk het logboek.')
            return index
        finally:
            with self.lock:
                self.running.pop(index,None);self.active.discard(index)
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            if process.poll() is None:process.wait()
            if process.stdout:process.stdout.close()
            if index in self.start_tickets:self.start_tickets[index].unlink(missing_ok=True)

    def finished(self,index):
        with self.lock:self.completed+=1
        self.emit(index,{'phase':'Onderdeel veilig opgeslagen','fraction':None})

    def run(self,commands):
        commands=list(commands)
        memory=self.folder/'memory';memory.mkdir(exist_ok=True)
        for rank,(index,_) in enumerate(commands):
            ticket=memory/f'start-{rank:06d}';ticket.touch();self.start_tickets[index]=ticket
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures=[executor.submit(self.execute,index,command) for index,command in commands]
            try:
                for future in concurrent.futures.as_completed(futures):yield future.result()
            except BaseException:
                self.cancel()
                for future in futures:future.cancel()
                raise

    def __exit__(self,*args):
        self.cancel()
        for sig,previous in self.previous.items():signal.signal(sig,previous)

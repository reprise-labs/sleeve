"""Measured phase progress; percentages never estimate time or total-job completion."""
import json

def progress(phase,current=None,total=None,scope='component',detail='',completed=None):
 fraction=None
 if current is not None and total is not None and total>0:
  fraction=max(0.,min(1.,current/total))
 payload={'phase':phase,'fraction':fraction,'scope':scope,'detail':detail}
 if current is not None:payload['unitsDone']=int(current)
 if total is not None:payload['unitsTotal']=int(total)
 if completed is not None:payload['completedParts']=int(completed)
 print('SLEEVE_PROGRESS '+json.dumps(payload,ensure_ascii=False),flush=True)

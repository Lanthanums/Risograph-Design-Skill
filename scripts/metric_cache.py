"""Bounded persistent font/fit measurements; optional cache failure is harmless."""
import atexit,hashlib,json,os
from pathlib import Path
from functools import lru_cache

_bank=None;_dirty=False;_hits=0;_misses=0;_enabled=False
def enable():
    global _enabled
    _enabled=True
@lru_cache(maxsize=64)
def font_sha(path,stamp,size):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
@lru_cache(maxsize=1)
def engine_sha():
    root=Path(__file__).parent
    return hashlib.sha256((root/'typefit.py').read_bytes()+(root/'textmetrics.py').read_bytes()).hexdigest()
def _path():
    from state_paths import state_path
    return state_path('font-metrics-v1.json')
def key(kind,values,font):
    import textmetrics as tm
    path=tm.resolve(font[0],font[1])
    if not path:return None
    stat=Path(path).stat()
    return hashlib.sha256(json.dumps([kind,values,font_sha(path,stat.st_mtime_ns,stat.st_size),tm._faces.get((font[0],bool(font[1])),0),engine_sha()],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def get(k):
    global _bank,_hits,_misses
    if _bank is None:
        try:_bank=json.loads(_path().read_text(encoding='utf-8'))
        except (OSError,ValueError):_bank={}
    result=_bank.get(k)
    if result is not None:_hits+=1
    else:_misses+=1
    return result
def put(k,value):
    global _dirty
    if not k:return
    if _bank is None:get(k)
    _bank[k]=value;_dirty=True
    if len(_bank)>4096:_bank.pop(next(iter(_bank)))
def stats():return dict(hits=_hits,misses=_misses,entries=len(_bank or {}))
@atexit.register
def flush():
    if not _dirty or not _enabled:return
    temp=None
    try:
        p=_path();p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
        temp.write_text(json.dumps(_bank,ensure_ascii=False,separators=(',',':')),encoding='utf-8');os.replace(temp,p)
    except OSError:pass
    finally:
        if temp and temp.exists():
            try:temp.unlink()
            except OSError:pass

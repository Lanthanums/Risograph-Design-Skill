"""Per-user runtime state, independent of the read-only skill package."""
import sys
sys.dont_write_bytecode = True
import os
import tempfile
import hashlib
import json
import warnings
from pathlib import Path


def state_dir():
    override = os.environ.get('RISO_DESIGN_STATE_DIR')
    if override:
        return Path(override).expanduser().resolve()
    try:
        home = Path.home()
    except (RuntimeError, OSError):
        return fallback_dir()
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or home / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = home / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_STATE_HOME') or home / '.local' / 'state')
    if str(home) in ('', '.', '~'):
        base = Path(tempfile.gettempdir())
    return base / 'riso-design'


def state_path(name):
    return state_dir() / name


def fallback_dir():
    identity='|'.join(str(os.environ.get(k,'')) for k in ('USERDOMAIN','USERNAME','USER','HOME','USERPROFILE'))
    if hasattr(os,'getuid'):identity+='|'+str(os.getuid())
    suffix=hashlib.sha256(identity.encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / ('riso-design-'+suffix)


def read_path(name):
    default=state_path(name)
    if os.environ.get('RISO_DESIGN_STATE_DIR'):return default
    candidates=[]
    for path in {default,fallback_dir()/name}:
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict):continue
            if name=='history.json' and not isinstance(data.get('decks'),list):continue
            candidates.append((bool(data.get('decks')) if name=='history.json' else True,
                               path.stat().st_mtime_ns,path))
        except (OSError,ValueError):continue
    return max(candidates,key=lambda r:r[:2])[2] if candidates else default


def read_json(name,default=None):
    try:return json.loads(read_path(name).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default if default is not None else {}


def _atomic_write(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,staging=tempfile.mkstemp(prefix='riso-',suffix='.json',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as fh:
            json.dump(payload,fh,ensure_ascii=False,indent=2)
        os.replace(staging,path)
    finally:
        if os.path.exists(staging):os.remove(staging)


def write_json(name,payload):
    path=state_path(name)
    try:
        _atomic_write(path,payload)
        return path
    except OSError as exc:
        if os.environ.get('RISO_DESIGN_STATE_DIR'):
            raise ValueError(f'Explicit RISO_DESIGN_STATE_DIR is not writable: {path.parent}: {exc}') from exc
        fallback=fallback_dir()/name
        warnings.warn(f'Default state write failed at {path.parent}; using external fallback {fallback.parent}: {exc}',RuntimeWarning)
        try:_atomic_write(fallback,payload)
        except OSError as fallback_exc:
            raise ValueError(f'State write failed at {path.parent} and fallback {fallback.parent}: {fallback_exc}') from fallback_exc
        return fallback

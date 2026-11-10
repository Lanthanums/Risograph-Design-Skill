"""Verified full-run cache, stdlib only; checked before PPTX/Pillow imports."""
import hashlib,json,os,platform,shutil,sys,tempfile,time
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def output_files(out,artifact='poster',rendered=False,*,storyboard=False):
    """Explicit generated-file inventory; never cache unrelated user files."""
    out=Path(out)
    names={'source.json','compiled-spec.json','content-plan.json','run.json','summary.json',
           'timings.json','run-manifest.json','qa.json','layout.json',
           artifact+'.pptx',artifact+'.style.json','preflight.json','plan-summary.json',
           'poster.plan.json','qa.log','layout_check.log'}
    folders={artifact+'-media'}
    if artifact == 'deck' and storyboard:
        names.add('storyboard.md')
    if rendered:
        names.update(('qa-rendered.json','qa-rendered.log','render.log','evidence-presence.json'))
        folders.update(('preview','visual'))
    else:
        names.update(('draft.png','wireframe.png'));folders.add('draft')
    return sorted(p for p in out.rglob('*') if p.is_file()
                  and not any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(out).parts)
                  and (p.relative_to(out).as_posix() in names or p.relative_to(out).parts[0] in folders))

# Rendering, fonts, vector primitives, legacy element placement and source
# evidence parsing are common infrastructure. Composition code is route-local.
POSTER_FILES = {
    'auto_garnish', 'build_poster', 'content_plan', 'evidence_forms',
    'evidence_scale', 'evidence_style', 'infographic',
}


def pipeline_code(root, artifact):
    files = {}
    for path in sorted(root.glob('*.py')):
        stem = path.stem
        is_deck = stem.startswith('deck_') or stem in ('build_deck', 'compose')
        is_poster = stem.startswith('poster_') or stem in POSTER_FILES
        if (artifact == 'deck' and is_poster) or (artifact == 'poster' and is_deck):
            continue
        files[path.name] = sha(path)
    return files


def key(inputs,options):
    root=Path(__file__).resolve().parent
    artifact = options.get('artifact', 'poster')
    code = pipeline_code(root, artifact)
    code['VERSION']=(root.parent/'VERSION').read_text().strip()
    environment={k:v for k,v in os.environ.items() if k.startswith(('RISO','FONT','LIBREOFFICE'))}
    # Executable identity without importing a renderer or invoking a process.
    executable=os.environ.get('RISOSLIDES_SOFFICE') or shutil.which('soffice') or shutil.which('libreoffice')
    candidates=[executable] if executable else [r'C:\Program Files\LibreOffice\program\soffice.com',r'C:\Program Files (x86)\LibreOffice\program\soffice.com','/usr/bin/soffice','/Applications/LibreOffice.app/Contents/MacOS/soffice']
    renderer={str(Path(p).resolve()):[Path(p).stat().st_size,Path(p).stat().st_mtime_ns] for p in candidates if p and Path(p).is_file()}
    # Include catalog additions/removals as well as used-font SHA checks at restore.
    from font_catalog import font_paths
    catalog={str(p):[p.stat().st_size,p.stat().st_mtime_ns] for p in font_paths()}
    assets={}
    def walk(value,base):
        if isinstance(value,dict):
            for entry in value.values():
                walk(entry, base)
        elif isinstance(value,list):
            for v in value:walk(v,base)
        elif isinstance(value,str) and len(value)<4096 and Path(value).suffix.lower() in ('.png','.jpg','.jpeg','.svg','.ttf','.otf','.ttc','.js','.exe','.com','.json'):
            p=Path(value);p=p if p.is_absolute() else base/p
            if p.is_file():assets[str(p.resolve())]=sha(p)
    for path in inputs.values():
        if path:
            p=Path(path)
            try:
                document = json.loads(p.read_text(encoding='utf-8-sig'))
            except ValueError:
                continue
            base = p.resolve().parent
            walk(document, base)
            if artifact == 'deck' and isinstance(document, dict):
                source = document.get('source', {}) if document.get('mode') == 'editorial' else document
                media = source.get('meta', {}).get('media')
                if isinstance(media, str):
                    directory = (base / media).resolve()
                    if directory.is_dir():
                        for child in directory.rglob('*'):
                            if child.is_file():
                                assets[str(child.resolve())] = sha(child)
    # Explicit and registered kit/node changes must invalidate complete-run hits,
    # even when the path and the input JSON remain unchanged.
    configured={}
    if not options.get('system'):
        import argparse,render
        node,kit=render.find_kit(argparse.Namespace(kit=options.get('kit'),node=options.get('node'),autodiscover=options.get('autodiscover',False)))
        for name in (node,kit):
            if name and Path(name).is_file():configured[str(Path(name).resolve())]=sha(name)
    from importlib.metadata import version,PackageNotFoundError
    packages={}
    for name in ('python-pptx','Pillow','numpy','PyMuPDF'):
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    payload=dict(code=code,inputs={k:sha(v) for k,v in inputs.items() if v},assets=assets,options=options,packages=packages,environment=environment,renderer=renderer,configured_renderer=configured,fonts=catalog,python=sys.version,platform=dict(sys_platform=sys.platform,os_name=os.name,architecture=os.environ.get('PROCESSOR_ARCHITECTURE','')))
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    from state_paths import state_path
    directory=state_path('input-cache')/artifact/digest
    return directory,payload

def restore(directory,out):
    start=time.perf_counter();directory=Path(directory);out=Path(out).resolve()
    try:
        record=json.loads((directory/'cache.json').read_text(encoding='utf-8'))
        files=record['files']
        for name,h in files.items():
            path=(directory/name).resolve()
            if directory.resolve() not in path.parents or not path.is_file() or sha(path)!=h:return None
        for name,h in record.get('fonts',{}).items():
            if not Path(name).is_file() or sha(name)!=h:return None
        if not files or 'summary.json' not in files or 'run-manifest.json' not in files:return None
        previous={}
        for name in files:
            if not name.startswith('visual/') or not name.endswith('review.json'):continue
            try:
                review=json.loads((out/name).read_text(encoding='utf-8'))
                if review.get('reviewer'):previous[name]=review
            except (ValueError,OSError):pass
        cached_manifest=json.loads((directory/'run-manifest.json').read_text(encoding='utf-8'))
        if any(name not in files for name in cached_manifest.get('artifact_hashes',{})):return None
        out.mkdir(parents=True,exist_ok=True)
        for name in files:
            target=(out/name).resolve()
            if out not in target.parents:return None
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.is_file() and sha(target)==files[name]:continue
            shutil.copy2(directory/name,target)
        changed=set()
        for name,review in previous.items():
            cached=json.loads((out/name).read_text(encoding='utf-8'))
            anchors=('pptx_sha256','render_sha256','plan_sha256','source_sha256')
            if all(review.get(k)==cached.get(k) for k in anchors):
                dump(out/name,review);changed.add(name)
        summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
        rendered='preview/render.json' in files
        summary.update(cache='INPUT_HIT',render='INPUT_CACHE_HIT' if rendered else 'NOT_REQUESTED',cached_stages=summary.get('stages'),stages=dict(cache_restore=round(time.perf_counter()-start,4)),engine_seconds=round(time.perf_counter()-start,4),verification='SHA-verified cached QA; validators not rerun')
        dump(out/'summary.json',summary)
        status=json.loads((out/'run.json').read_text(encoding='utf-8'));status.update(cache='INPUT_HIT',render='INPUT_CACHE_HIT' if rendered else 'NOT_REQUESTED');dump(out/'run.json',status)
        changed.update(('run.json','summary.json'))
        manifest=cached_manifest
        manifest.update(cache=dict(status='INPUT_HIT',cache_key=directory.name,sha_verified=True),parameters={**manifest.get('parameters',{}),'out':str(out)})
        manifest['artifact_hashes']={n:sha(out/n) if n in changed else files[n] for n in manifest.get('artifact_hashes',{})}
        dump(out/'run-manifest.json',manifest)
        return status
    except (OSError,ValueError,KeyError,TypeError):return None

def store(directory,out,payload):
    directory=Path(directory);out=Path(out).resolve();directory.parent.mkdir(parents=True,exist_ok=True)
    # A corrupt existing entry is replaced only by a fully written validated run.
    stage=Path(tempfile.mkdtemp(prefix='.entry-',dir=directory.parent));files={}
    status=json.loads((out/'run.json').read_text(encoding='utf-8'))
    artifact=payload.get('options',{}).get('artifact','poster')
    storyboard = bool(status.get('content_plan', {}).get('storyboard'))
    for path in output_files(out,artifact,status.get('render','NOT_REQUESTED')!='NOT_REQUESTED',storyboard=storyboard):
        name=path.relative_to(out)
        if not path.is_file() or any(p.startswith('.') for p in name.parts):continue
        if path.suffix.lower() not in ('.json','.png','.jpg','.jpeg','.pptx','.pdf','.log','.md'):continue
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);files[name.as_posix()]=sha(path)
    manifest=json.loads((out/'run-manifest.json').read_text(encoding='utf-8'))
    fonts={r['path']:sha(r['path']) for r in manifest.get('fonts',[]) if r.get('path') and Path(r['path']).is_file()}
    dump(stage/'cache.json',dict(files=files,fonts=fonts,payload=payload))
    if directory.exists():
        # File-level replacement is safe for this dedicated cache entry; no user
        # output directories are recursively removed.
        for p in stage.rglob('*'):
            if p.is_file():target=directory/p.relative_to(stage);target.parent.mkdir(parents=True,exist_ok=True);os.replace(p,target)
        shutil.rmtree(stage)
    else:os.replace(stage,directory)

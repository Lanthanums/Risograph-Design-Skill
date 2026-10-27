#!/usr/bin/env python3
"""Environment checks; --out OUTPUT_DIR saves doctor-report.json after a write probe."""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import hashlib
sys.dont_write_bytecode = True
from runtime import prepare
prepare()


def inspect(out=None,refresh=False):
    dependencies = {}
    for module, package in [('pptx','python-pptx'), ('PIL','Pillow'), ('numpy','numpy')]:
        try:
            imported = importlib.import_module(module)
            dependencies[package] = {'ok': True, 'version': getattr(imported,'__version__','unknown')}
        except Exception as exc:
            dependencies[package] = {'ok': False, 'error': str(exc)}
    writable = None
    if out:
        target = Path(out).expanduser().resolve()
        probe = target / ('.riso-probe-' + uuid.uuid4().hex)
        try:
            target.mkdir(parents=True, exist_ok=True)
            with probe.open('xb') as stream: stream.write(b'ok')
            writable = True
        except OSError as exc:
            writable = str(exc)
        finally:
            if probe.is_file(): probe.unlink()
    package=Path(__file__).resolve().parents[1]
    code_hash=hashlib.sha256(Path(__file__).read_bytes()+Path(__file__).with_name('render.py').read_bytes()).hexdigest()
    cache_path=Path(out).resolve().parent/'.riso-state/env.json' if out else None
    if cache_path and cache_path.exists() and writable is True and not refresh:
        try:
            cached=json.loads(cache_path.read_text(encoding='utf-8'))
            binary=Path(cached['soffice'])
            if (cached.get('interpreter')==sys.executable and cached.get('dependencies')==dependencies
                and cached.get('probe_code_hash')==code_hash and cached.get('ready_render')
                and binary.is_file() and cached.get('soffice_stamp')==binary.stat().st_mtime_ns
                and all((package/f).is_file() for f in ('VERSION','SKILL.md','scripts/content_plan.py'))
                and cached.get('engine_version')==(package/'VERSION').read_text(encoding='utf-8').strip()
                and cached.get('renderer_version')==__import__('run_manifest').renderer_version(str(binary))):
                cached.update(environment_cache='HIT: verified binary/code/dependency identity',report_path=str(target/'doctor-report.json'))
                (target/'doctor-report.json').write_text(json.dumps(cached,ensure_ascii=False,indent=2),encoding='utf-8')
                return cached
        except (OSError,ValueError,KeyError,TypeError):pass
    try:
        child = subprocess.run([sys.executable,'-c','print("ok")'], capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=10)
        spawn = child.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        spawn = str(exc)
    from state_paths import state_dir
    import render
    renderer_error=None
    try:
        route=render.pick_route(argparse.Namespace(kit=None,node=None,autodiscover=True))
        soffice=render.find_soffice()
    except (OSError,ValueError) as exc:
        route=None;soffice=None;renderer_error=str(exc)
    result = {'python': sys.executable, 'version': sys.version.split()[0],
              'dependencies': dependencies, 'output_writable': writable,
              'state_dir': str(state_dir()), 'state_write': 'not probed; set RISO_DESIGN_STATE_DIR to workspace/.riso-state in a sandbox',
              'child_python': spawn, 'renderer_execution': 'UNVERIFIED; render a real PPTX',
              'soffice': soffice, 'renderer_route':route, 'renderer_discovery_error':renderer_error,
              'renderer_hint':'Discovery only. Run render.py --autodiscover on a real PPTX to verify execution.',
              'kit': os.environ.get('RISOSLIDES_KIT'),
              'ready': all(d['ok'] for d in dependencies.values()) and writable in (None, True) and spawn is True}
    root=Path(__file__).resolve().parents[1]
    required=['VERSION','SKILL.md','scripts/poster_run.py','scripts/content_plan.py','scripts/render.py']
    result['package_integrity']={'missing':[name for name in required if not (root/name).is_file()]}
    from run_manifest import engine_version,renderer_version
    result['engine_version']=engine_version(root)
    result['renderer_version']=renderer_version(soffice)
    result['ready_build']=result['ready']
    result['ready_render']=False
    if out and writable is True and result['ready_build'] and route:
        try:
            from pptx import Presentation
            from pptx.util import Inches,Pt
            from PIL import Image
            folder=target/'renderer-probe';folder.mkdir(exist_ok=True)
            prs=Presentation();prs.slide_width=Inches(2);prs.slide_height=Inches(2)
            slide=prs.slides.add_slide(prs.slide_layouts[6])
            slide.shapes.add_textbox(Pt(12),Pt(12),Pt(110),Pt(60)).text='Raster probe'
            deck=folder/'probe.pptx';prs.save(deck)
            pdf,_=render.to_pdf(route,str(deck),str(folder/'pdf'))
            pngdir=folder/'png'
            if route[0]=='soffice+png':
                render.render_direct_png(route,deck,pngdir,72)
                result['pdf_raster_probe']='UNAVAILABLE: direct PPTX-to-PNG fallback verified separately'
            else:
                render.render_pdf(route,pdf,str(pngdir),72)
                result['pdf_raster_probe']='PASS'
            with Image.open(pngdir/'page-0001.png') as image:
                if image.size!=(144,144):raise ValueError('Probe dimensions differ: '+str(image.size))
                if image.convert('L').getextrema()[0]>220:raise ValueError('Probe is blank')
            result.update(ready_render=True,renderer_execution='PASS: real conversion and nonblank 144x144 PNG')
        except Exception as exc:
            result['renderer_execution']='FAILED: '+str(exc)
    elif not route:
        result['renderer_execution']='ROUTE_MISSING: no renderer; run python scripts/render.py --describe --autodiscover'
    result['ready']=result['ready_build'] and result['ready_render'] and not result['package_integrity']['missing']
    if out and writable is True:
        cache=target.parent/'.riso-state';cache.mkdir(exist_ok=True)
        (cache/'env.json').write_text(json.dumps(dict(result,interpreter=sys.executable,probe_code_hash=code_hash,
            soffice_stamp=Path(soffice).stat().st_mtime_ns if soffice and Path(soffice).is_file() else None),ensure_ascii=False,indent=2),encoding='utf-8')
    if out and writable is True:
        report_path=target/'doctor-report.json'
        result['report_path']=str(report_path)
        report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', help='workspace output directory to probe once')
    ap.add_argument('--refresh',action='store_true',help='ignore validated environment cache')
    args = ap.parse_args()
    report = inspect(args.out,args.refresh)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report['ready'] else 2)

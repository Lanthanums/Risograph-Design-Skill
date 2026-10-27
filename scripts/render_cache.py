"""Shared, SHA-verified render reuse. QA always runs against the saved artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        stage.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
        os.replace(stage, path)
    finally:
        stage.unlink(missing_ok=True)


def identity(deck, options, font_rows=None):
    import render
    from run_manifest import renderer_version, presentation_fonts
    parser = argparse.ArgumentParser(add_help=False)
    for name in ('system', 'autodiscover', 'keep-pdf'):
        parser.add_argument('--' + name, action='store_true')
    for name in ('kit', 'node', 'pages'):
        parser.add_argument('--' + name)
    parser.add_argument('--dpi', type=int, default=110)
    args = parser.parse_args(options)
    route = render.pick_route(args)
    binaries = {}
    for name in route[1:] if route else ():
        if name and Path(name).is_file():
            path = Path(name).resolve()
            stat = path.stat()
            binaries[str(path)] = [stat.st_size, stat.st_mtime_ns]
    from importlib.metadata import version, PackageNotFoundError
    try:
        raster = version('PyMuPDF')
    except PackageNotFoundError:
        raster = None
    rows = presentation_fonts(deck) if font_rows is None else font_rows
    from font_catalog import font_paths
    catalog = {str(p): [p.stat().st_size, p.stat().st_mtime_ns] for p in font_paths()}
    return dict(schema=1, pptx_sha256=sha(deck),
                pdf_name=Path(deck).stem if args.keep_pdf else None,
                options=vars(args), route=route, binaries=binaries,
                renderer_version=renderer_version(render.find_soffice()),
                raster_version=raster,
                code={name: sha(Path(__file__).with_name(name)) for name in
                      ('render.py', 'render_cache.py', 'run_manifest.py', 'state_paths.py')},
                font_catalog=catalog,
                fonts={f"{row['family']}:{row['bold']}": row.get('sha256') for row in rows})


def verified(folder, key):
    """Corrupt or incomplete optional cache data is a miss, including bad JSON."""
    folder = Path(folder)
    try:
        record = json.loads((folder / '.render-cache.json').read_text(encoding='utf-8'))
        files = record['files']
        if record['key'] != key or not isinstance(files, dict) or 'render.json' not in files:
            return None
        for name, digest in files.items():
            if not name or Path(name).name != name or not (folder / name).is_file():
                return None
            if sha(folder / name) != digest:
                return None
        metadata = json.loads((folder / 'render.json').read_text(encoding='utf-8'))
        pages = metadata['pages']
        if not pages or set(pages) != {n for n in files if n.startswith('page-') and n.endswith('.png')}:
            return None
        if any(metadata['png_hashes'].get(n) != files[n] for n in pages):
            return None
        if {p.name for p in folder.glob('page-*.png')} != set(pages):
            return None
        return record
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def copy_files(source, target, files):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in files:
        stage = target / ('.' + name + '.' + uuid.uuid4().hex)
        try:
            shutil.copy2(Path(source) / name, stage)
            os.replace(stage, target / name)
        finally:
            stage.unlink(missing_ok=True)
    for stale in target.glob('page-*.png'):
        if stale.name not in files:
            stale.unlink()


def render_cached(deck, preview, options, execute, mode='fast', font_rows=None):
    """Cache only renderer outputs; audit forces actual conversion and fresh QA."""
    from state_paths import state_path
    signature = identity(deck, options, font_rows)
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    preview = Path(preview)
    directory = state_path('render-cache-v4') / key
    if mode != 'audit':
        if verified(preview, key):
            return 'CACHE_HIT'
        record = verified(directory, key)
        if record:
            copy_files(directory, preview, record['files'])
            write(preview / '.render-cache.json', record)
            return 'CACHE_HIT'
    execute()
    remember(deck, preview, options, signature=signature)
    return 'RENDERED_ONCE'


def remember(deck, preview, options, signature=None):
    """Bind an already completed renderer/batch result to the shared cache."""
    from state_paths import state_path
    preview = Path(preview)
    signature = identity(deck, options) if signature is None else signature
    key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    directory = state_path('render-cache-v4') / key
    metadata = json.loads((preview / 'render.json').read_text(encoding='utf-8'))
    if metadata['source_sha256'] != signature['pptx_sha256'] or metadata['dpi'] != signature['options']['dpi']:
        raise ValueError('Renderer metadata does not match the saved PPTX and DPI')
    names = ['render.json', *metadata['pages']]
    if signature['options']['keep_pdf']:
        names.append(Path(deck).stem + '.pdf')
    if any(Path(name).name != name for name in names):
        raise ValueError('Renderer output names must be local files')
    record = dict(key=key, identity=signature, files={name: sha(preview / name) for name in names})
    write(preview / '.render-cache.json', record)
    # Cache storage is optional; an unwritable cache must not invalidate a render.
    try:
        copy_files(preview, directory, record['files'])
        write(directory / '.render-cache.json', record)
    except OSError:
        pass
    return record

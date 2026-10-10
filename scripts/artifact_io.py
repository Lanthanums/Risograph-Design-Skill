"""Artifact-local output/sidecars and spec-relative source paths."""
import sys
sys.dont_write_bytecode = True
import json
from pathlib import Path
import shutil
import zipfile
import io


def input_path(raw, base_dir=None, role='asset', directory=False):
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(base_dir or Path.cwd()) / path
    path = path.resolve()
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError(f'Missing input {role}: {path}')
    return path


def paths(artifact):
    out = Path(artifact).resolve()
    return out, out.with_suffix('.style.json'), out.parent / (out.stem+'-media')


def read_style(artifact):
    _, sidecar, _ = paths(artifact)
    if not sidecar.exists():
        sidecar = sidecar.parent / 'style.json'
    return json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}


def discover_media(artifact):
    out, _, media = paths(artifact)
    return media if media.is_dir() else out.parent / 'media'


def background_file(media, page):
    """Use the exact embedded print plate named by the artifact manifest."""
    directory = Path(media)
    manifest = directory / 'manifest.json'
    if manifest.is_file():
        for entry in json.loads(manifest.read_text(encoding='utf-8')).get('pages', []):
            name = entry.get('file', '')
            if entry.get('page') == page and name and Path(name).name == name:
                candidate = directory / name
                if candidate.is_file():
                    return candidate
    for ext in ('.jpg', '.png', '.jpeg'):
        candidate = directory / f'bg{page}{ext}'
        if candidate.is_file():
            return candidate
    return None


def write_style(artifact, style):
    out, sidecar, _ = paths(artifact)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(style, ensure_ascii=False, indent=2)
    sidecar.write_text(payload, encoding='utf-8')
    alias = out.parent / 'style.json'
    if not alias.exists():
        alias.write_text(payload, encoding='utf-8')
    return str(sidecar)


def legacy_media_alias(artifact):
    out, _, media = paths(artifact)
    alias = out.parent / 'media'
    if not alias.exists() and media.is_dir():
        shutil.copytree(media, alias)


def canonical_pptx(path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            entry = zipfile.ZipInfo(name, (1980,1,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, source.read(name))
    Path(path).write_bytes(buffer.getvalue())

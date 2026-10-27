"""Shared font search roots; discovery and cache invalidation must agree."""
import os
from pathlib import Path

FONT_SUFFIXES = frozenset(('.ttf', '.otf', '.ttc', '.otc'))
FONT_DIRS = [
    os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
    os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts'),
    '/System/Library/Fonts', '/Library/Fonts',
    '/usr/share/fonts', '/usr/share/fonts/truetype', '/usr/local/share/fonts',
    os.path.expanduser('~/.local/share/fonts'), os.path.expanduser('~/.fonts'),
    os.path.expanduser('~/Library/Fonts'),
]


def font_paths(directories=None):
    """List each file once, even when search roots overlap."""
    roots = []
    for directory in FONT_DIRS if directories is None else directories:
        path = Path(directory).expanduser().resolve()
        if not path.is_dir() or any(path == root or root in path.parents for root in roots):
            continue
        roots = [root for root in roots if path not in root.parents]
        roots.append(path)
    return sorted({p for root in roots for p in root.rglob('*')
                   if p.suffix.lower() in FONT_SUFFIXES and p.is_file()})

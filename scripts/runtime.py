"""Small stdlib-only CLI boundary; never installs or changes interpreters."""
import sys
sys.dont_write_bytecode = True


def prepare():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    original = sys.excepthook
    def report(kind, value, trace):
        if '--verbose' in sys.argv:
            original(kind, value, trace)
        elif issubclass(kind, ModuleNotFoundError):
            print(f'Missing dependency {value.name!r} in {sys.executable}. '
                  'Run this interpreter with scripts/doctor.py; use the harness runtime '
                  'or install requirements.txt into a workspace venv.', file=sys.stderr)
        elif issubclass(kind, (ValueError, OSError)):
            print(f'error: {value}', file=sys.stderr)
        else:
            original(kind, value, trace)
    sys.excepthook = report

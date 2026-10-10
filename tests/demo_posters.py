"""Generate external review/gallery evidence, never inside the runtime package."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_poster import build


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default=str(Path(tempfile.gettempdir())/'riso_poster_demo'))
    ap.add_argument('--render',action='store_true')
    args=ap.parse_args()
    output=Path(args.out).resolve()
    if output==ROOT or ROOT in output.parents:
        ap.error('Review/gallery output must be outside the skill package')
    for fixture in sorted((ROOT/'tests'/'posters').glob('*.json')):
        out=output/fixture.stem/'poster.pptx'
        build(json.loads(fixture.read_text(encoding='utf-8')),str(out),fixture.parent)
        if args.render:
            result=subprocess.run([sys.executable,str(ROOT/'scripts'/'render.py'),
                     '--deck',str(out),'--out',str(out.parent/'preview'),'--keep-pdf','--autodiscover'])
            if result.returncode:
                print(f'{fixture.stem}: render requested but failed; pixel QA UNVERIFIED')
                return result.returncode
        for tool in ('qa.py','layout_check.py'):
            cmd=[sys.executable,str(ROOT/'scripts'/tool),'--deck',str(out),
                 '--json',str(out.parent/(tool.replace('.py','')+'.json'))]
            if tool=='qa.py':
                cmd+=['--media',str(out.parent/'media')]
                if args.render:cmd+=['--render',str(out.parent/'preview'),'--require-render']
            result=subprocess.run(cmd)
            if result.returncode:return result.returncode
    print(f'Gallery review demos: {output}')
    return 0


if __name__=='__main__':sys.exit(main())

"""Builds must not mutate an installed/copied skill tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'))
import compose
import state_paths


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class StateTests(unittest.TestCase):
    def test_paths_and_read_only_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'state'
            with patch.dict(os.environ,{'RISO_DESIGN_STATE_DIR':str(base)}):
                self.assertEqual(state_paths.state_dir(),base.resolve())
                self.assertEqual(compose.load_history(str(ROOT)),{'decks':[]})
                self.assertFalse(base.exists())
                compose.append_history(str(ROOT),{'deck':'x','seed':1,'primary':'A','secondary':'C'})
                self.assertTrue((base/'history.json').exists())
            with patch.dict(os.environ,{'LOCALAPPDATA':tmp,'XDG_STATE_HOME':tmp}):
                os.environ.pop('RISO_DESIGN_STATE_DIR',None)
                for platform in ('win32','linux','darwin'):
                    with patch.object(state_paths.sys,'platform',platform):
                        self.assertNotIn(str(ROOT),str(state_paths.state_dir()))
                with patch.object(state_paths.Path,'home',side_effect=RuntimeError('no home')):
                    self.assertEqual(state_paths.state_dir(),state_paths.fallback_dir())

    def test_rebuild_and_last_n_avoidance(self):
        hist={'decks':[{'deck':'a','seed':1,'primary':'D','secondary':'E','chosen_by':'domain'}]}
        self.assertEqual(compose.pick_dialects('report','report',1,hist,self_key=('a',1))[:2],('D','E'))
        self.assertNotEqual(compose.pick_dialects('report','report',2,hist,self_key=('b',2))[:2],('D','E'))
        hist['decks'] += [{'deck':'b','seed':2,'primary':'E','secondary':'D'},
                         {'deck':'c','seed':3,'primary':'A','secondary':'C'},
                         {'deck':'d','seed':4,'primary':'B','secondary':'A'}]
        self.assertEqual(compose.pick_dialects('report','report',1,hist,self_key=('a',1))[:2],('D','E'))
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RISO_DESIGN_STATE_DIR':tmp}):
            compose.append_history(None,hist['decks'][0])
            compose.append_history(None,hist['decks'][0])
            self.assertEqual(len(compose.load_history()['decks']),1)

    def test_real_deck_and_poster_cli_leave_copied_package_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            package=tmp/'package'
            shutil.copytree(ROOT,package,ignore=shutil.ignore_patterns('.git','__pycache__','state'))
            before=snapshot(package)
            env=dict(os.environ,RISO_DESIGN_STATE_DIR=str(tmp/'state'))
            # Do not depend on a no-bytecode environment: CLI entry points own this.
            env.pop('PYTHONDONTWRITEBYTECODE',None)
            spec=json.loads((ROOT/'tests'/'fixtures'/'report_en.json').read_text(encoding='utf-8'))
            work=tmp/'deck';work.mkdir()
            spec['meta']['media']=str(work/'media')
            sf=work/'spec.json';sf.write_text(json.dumps(spec))
            commands=[['make_textures.py','bg','--out',str(work/'media'),
                       '--pages',str(len(spec['pages'])),'--palette',spec['meta'].get('palette','G'),
                       '--seed',str(spec['meta'].get('seed',1)),
                       '--manifest',str(work/'media'/'manifest.json')],
                      ['build_deck.py','--spec',str(sf),'--out',str(work/'deck.pptx')]]
            poster=tmp/'poster.json';poster.write_text(json.dumps({'content':{'title':'STATE CHECK'},'meta':{'elements':False}}))
            commands.append(['build_poster.py','--spec',str(poster),'--out',str(tmp/'poster'/'poster.pptx')])
            commands.append(['qa.py','--deck',str(tmp/'poster'/'poster.pptx'),
                             '--media',str(tmp/'poster'/'media')])
            commands.append(['layout_check.py','--deck',str(tmp/'poster'/'poster.pptx')])
            for command in commands:
                p=subprocess.run([sys.executable,str(package/'scripts'/command[0]),*command[1:]],
                     cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertEqual(snapshot(package),before)
            self.assertTrue((tmp/'state'/'history.json').exists())


if __name__=='__main__':unittest.main()

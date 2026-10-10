"""Export plumbing independent of a GUI renderer; not visual verification."""
import contextlib
import argparse
import os
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'))
from canvas import poster_canvas
import render
import riso_kit as rk


class ExportTests(unittest.TestCase):
    def test_discovery_three_states_and_execution_boundary(self):
        args=argparse.Namespace(autodiscover=False,kit=None,node=None)
        self.assertIn('NOT executed',render.discovery_message(args,None))
        self.assertIn('--autodiscover',render.discovery_message(args,None))
        args.autodiscover=True
        self.assertIn('no renderer found after',render.discovery_message(args,None))
        args.autodiscover=False
        route=('kit','node-path','cli-path')
        with patch.object(render,'find_kit',return_value=('node-path','cli-path')),\
             patch.object(render,'pick_route',return_value=route),\
             contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(render.describe(args),0)
        self.assertIn('renderer found',printed.getvalue())
        self.assertIn('UNVERIFIED by --describe',printed.getvalue())
        self.assertIn('node-path',printed.getvalue());self.assertIn('cli-path',printed.getvalue())

    def test_keep_pdf_and_custom_canvas_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            c=poster_canvas('4:5')
            prs=rk.new_deck(c)
            rk.add_page(prs,None)
            deck=tmp/'custom.pptx';prs.save(deck)
            def pdf(route,path,out):
                out=Path(out);out.mkdir(parents=True)
                result=out/'custom.pdf';result.write_bytes(b'%PDF-1.4 mock export transport')
                return str(result),{}
            def png(route,path,out,dpi,pages):
                out=Path(out);out.mkdir(parents=True)
                Image.new('RGB',(int(c.width/72*dpi),int(c.height/72*dpi)),'white').save(out/'page-0001.png')
                return {}
            with patch.object(render,'pick_route',return_value=('mock',None,None)),\
                 patch.object(render,'to_pdf',side_effect=pdf),\
                 patch.object(render,'render_pdf',side_effect=png),\
                 patch.object(sys,'argv',['render.py','--deck',str(deck),'--out',str(tmp/'preview'),'--keep-pdf']),\
                 contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(render.main(),0)
                self.assertNotIn('scaling content',printed.getvalue())
            self.assertTrue((tmp/'preview'/'custom.pdf').exists())
            self.assertTrue((tmp/'preview'/'page-0001.png').exists())
            self.assertIsNone(__import__('qa').preview_problem(str(deck),str(tmp/'preview')))

    def test_windows_workspace_inherits_without_private_mkdtemp(self):
        if os.name!='nt':
            with patch.object(render.tempfile,'mkdtemp',return_value='private-work') as private:
                self.assertEqual(render.workspace('test-'), 'private-work')
                private.assert_called_once()
            return
        with tempfile.TemporaryDirectory() as tmp,\
             patch.object(render.tempfile,'mkdtemp',side_effect=AssertionError('0700 private ACL')):
            path=Path(render.workspace('test-',tmp))
            (path/'readable.txt').write_text('inherited workspace')
            self.assertEqual((path/'readable.txt').read_text(),'inherited workspace')

    def test_absent_renderer_has_specific_status(self):
        with patch.object(render,'pick_route',return_value=None),\
             patch.object(sys,'argv',['render.py','--deck','unused.pptx']),\
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(render.main(),3)


if __name__=='__main__':unittest.main()

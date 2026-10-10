"""Behavioral recovery regressions: measurements, bad injections, and real CLIs."""
import sys
sys.dont_write_bytecode=True
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from pptx import Presentation
from pptx.util import Pt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import artifact_io as aio
import build_deck as bd
import build_poster as bp
import compose
import elements as E
import layout as lay
import layout_check as lc
import qa
import riso_kit as rk
import state_paths as sp
import textmetrics as tm
import typefit as tf
from canvas import DECK_CANVAS,poster_canvas


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.work=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'RISO_DESIGN_STATE_DIR':str(self.work/'state')})
        self.env.start()
        self.theme=rk.Theme(lang='en')

    def tearDown(self):
        self.env.stop();self.tmp.cleanup()

    def page(self,arch,spec):
        prs=rk.new_deck();slide=rk.add_page(prs,None)
        bd.ARCHETYPES[arch](slide,dict(archetype=arch,**spec),self.theme,1,1,{})
        return slide

    def cli(self,script,*args,cwd=None):
        return subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],
             cwd=cwd or self.work,capture_output=True,text=True,encoding='utf-8',errors='replace')

    def geometry(self,slide,canvas=DECK_CANVAS,style=None):
        rep=qa.Report()
        qa.geometry_checks(rep,slide,1,argparse.Namespace(edge_tol=1.5,text_protection=9,
                            media=None,canvas=canvas,style=style or {}))
        return [r for r in rep.items if not r['ok'] and r['severity']=='fail']

    def test_cover_multiline_and_support_is_reserved(self):
        title='MEASURING MAKES ROOM FOR BETTER QUESTIONS'
        slide=self.page('cover',{'title':title,'subtitle':'Supplied support stays present.'})
        fronts=[s for s in slide.shapes if 'cover-title' in s.name and 'riso-layer[front]' in s.name]
        self.assertGreaterEqual(len(fronts),2)
        self.assertGreater(min(s.text_frame.paragraphs[0].runs[0].font.size.pt for s in fronts),54)
        self.assertEqual(' '.join(s.text for s in fronts),title)
        support=next(s for s in slide.shapes if 'cover-subtitle' in s.name)
        self.assertGreater(support.top.pt,max(tm.ink_rect(s)[3] for s in fronts))
        self.assertFalse(lay.measured_issues(slide))
        self.assertFalse(any(lay.line_segment(s) for s in slide.shapes))
        sparse=self.page('cover',{'title':'PACKAGE CHECK'})
        checked=lc.check_slide(sparse,1,archetype='cover')
        self.assertFalse(checked['fails'],checked['fails'])

    def test_offsets_scale_background_override_and_identical_layers(self):
        for mode in ('print','reverse'):
            self.assertLess(rk.misreg_offsets(24,mode)[0],rk.misreg_offsets(100,mode)[0])
            self.assertLessEqual(rk.misreg_offsets(300,mode)[0],rk.DESIGN['misregistration'][mode]['cap'])
        self.assertGreater(rk.misreg_offsets(80,'reverse')[0],rk.misreg_offsets(80,'print')[0])
        self.assertEqual(rk.misreg_offsets(122),tuple(rk.DESIGN['misregistration']['display_xl']))
        slide=self.page('cover',{'title':'A SUPPLIED MULTILINE TITLE','title_size':90,'offsets':(2.25,0)})
        fronts=[s for s in slide.shapes if 'riso-layer[front]' in s.name]
        backs=[s for s in slide.shapes if 'riso-layer[back]' in s.name]
        self.assertEqual([s.text for s in fronts],[s.text for s in backs])
        for front,back in zip(fronts,backs):self.assertAlmostEqual(back.left.pt-front.left.pt,2.25,places=2)
        # An override of zero really means zero, and independent body duplicates
        # must not acquire the intentional-layer collision exemption.
        prs=rk.new_deck();sl=rk.add_page(prs,None)
        rk.stack(sl,50,80,700,80,[('ZERO',self.theme.f_display,60,True)],self.theme,offsets=(0,0))
        self.assertEqual(len(sl.shapes),1)
        for _ in range(2):rk.text(sl,50,250,400,40,[dict(runs=[('Repeated body',{})],font=self.theme.f_body,size=20)],wrap=False)
        self.assertTrue(any('text blocks' in r['check'] for r in self.geometry(sl)))

    def test_closing_statement_rule_injections_fail_both_checkers(self):
        for arch,spec in (('closing',{'quote':'Let us not be passive users, but active explorers.','big':'THANK YOU'}),
                          ('statement',{'lines':[['A supplied claim',44]],'body':'Let us not be passive users, but active explorers.','note':'Supplied note','sticker':'01'})):
            with self.subTest(arch=arch):
                slide=self.page(arch,spec)
                self.assertFalse(lay.measured_issues(slide))
                host=next(s for s in slide.shapes if ('closing-quote' if arch=='closing' else 'statement body') in s.name)
                r=tm.ink_rect(host)
                rk.rule(slide,r[0]-10,(r[1]+r[3])/2,r[2]-r[0]+20,self.theme.text,lw=2)
                self.assertTrue(any('line-glyph' in r['detail'] for r in self.geometry(slide)))
                self.assertTrue(any('line-glyph' in s for s in lc.check_slide(slide,1,archetype=arch)['fails']))

    def test_line_path_width_and_empty_gaps(self):
        self.assertGreater(lay.segment_rect_distance((0,0),(100,100),(5,70,20,85)),30)
        self.assertEqual(lay.segment_rect_distance((0,0),(100,100),(45,45,60,60)),0)
        prs=rk.new_deck();slide=rk.add_page(prs,None)
        rk.text(slide,50,100,500,50,[dict(runs=[('WORD      GAP',{})],font=self.theme.f_body,size=26)],wrap=False)
        glyphs=tm.glyph_rects(slide.shapes[-1])
        # A connector's broad bounds cross the paragraph, but its actual path
        # lies in whitespace and must stay legal.
        rk.rule(slide,800,120,120,self.theme.text,lw=3)
        self.assertFalse(lay.measured_issues(slide))
        self.assertTrue(glyphs)

    def test_venn_true_circle_and_intersection_bad_label(self):
        slide=self.page('venn',{'title':'Shared conditions','left':'Test','right':'Choice','centre':'Both',
                                 'note':'Supplied caption.','takeaway':'Supplied conclusion.'})
        self.assertFalse(lay.measured_issues(slide))
        host=next(s for s in slide.shapes if s.name=='venn-label[centre]')
        host.left+=Pt(70)
        self.assertTrue(any('Venn' in r['detail'] for r in self.geometry(slide)))
        self.assertTrue(any('Venn' in s for s in lc.check_slide(slide,1,archetype='venn')['fails']))
        self.assertFalse(lay.ellipse_contains((0,0,100,100),(0,0,20,20)))
        with self.assertRaisesRegex(ValueError,'venn'):
            self.page('venn',{'left':'An extraordinarily long label that cannot fit','centre':'Both'})

    def test_grid_weights_and_invalid_diagnostics(self):
        spec={'title':'Supplied comparison','columns':[{'label':'Short'},{'label':'Long description'}],
              'column_weights':[1,3],'rows':[{'label':'Evidence','cells':[{'text':'A'},{'text':'Supplied longer explanation'}]}]}
        slide=self.page('grid',spec)
        cells=[s for s in slide.shapes if 'grid cell' in s.name]
        self.assertGreater(cells[1].width.pt,cells[0].width.pt*2.5)
        self.assertFalse(lay.measured_issues(slide))
        for weights in ([0,1],[-1,2],[float('nan'),1],[1],['x',1],[True,1]):
            with self.assertRaisesRegex(ValueError,'grid column_weights'):
                self.page('grid',dict(spec,column_weights=weights))

    def test_timeline_long_description_never_truncated(self):
        desc='Measure the available region and preserve every supplied word across several explicitly broken lines.'
        slide=self.page('timeline',{'title':'A supplied sequence','items':[
            {'month':'1','name':'Measure','desc':desc},{'month':'2','name':'Build','desc':'Keep the measured result.'}]})
        host=next(s for s in slide.shapes if 'timeline description[0]' in s.name)
        self.assertEqual(' '.join(host.text.split()),desc)
        self.assertGreater(len(host.text_frame.paragraphs),1)
        self.assertFalse(lay.measured_issues(slide))
        with self.assertRaisesRegex(ValueError,'timeline description.*block=0'):
            self.page('timeline',{'items':[{'month':'1','name':'Long','desc':desc*100}]})

    def test_four_gauge_rows_clear_summary(self):
        rows=[{'label':f'Supplied row {i}','value':f'{i}%','pct':i} for i in range(1,5)]
        slide=self.page('numbered',{'title':'Supplied data','hero':'4','gauge':{'title':'Measured rows','rows':rows},
                                     'takeaway':'Every row remains visible.'})
        last=next(s for s in slide.shapes if 'gauge value[3]' in s.name)
        summary=next(s for s in slide.shapes if 'numbered takeaway' in s.name)
        self.assertLess(tm.ink_rect(last)[3],tm.ink_rect(summary)[1])
        self.assertFalse(lay.measured_issues(slide))

    def test_word_boundaries_and_speech_proxy(self):
        prs=rk.new_deck();slide=rk.add_page(prs,None)
        sh=rk.text(slide,48,90,600,130,[dict(runs=[('alpha beta',{})]),dict(runs=[('gamma delta',{})])],
                   font=self.theme.f_body,size=20,wrap=False)
        self.assertEqual(lc.words_of(lc._text_info(sh)[0]),4)
        self.assertEqual(compose.density_band('speech','D2',[20,42]),(20,42))
        self.assertNotEqual(compose.density_band('speech','D2'),compose.density_band('report','D2'))
        with self.assertRaisesRegex(ValueError,'word_band'):compose.density_band('speech','D2',[40,20])

    def test_fitting_failure_preserves_source_and_cjk_punctuation(self):
        with self.assertRaisesRegex(ValueError,'body.*block=3.*120.0x20.0.*requested 28pt.*minimum 18pt'):
            tf.fit('This supplied paragraph cannot disappear. '*20,self.theme.f_body,28,120,20,minimum=18,role='body',block_index=3)
        text='这是用户提供的文字，必须完整保留。闭合标点不应出现在行首！\n第二段保持独立。'
        font=rk.Theme(lang='zh').f_body
        f=tf.fit(text,font,24,210,600,minimum=24)
        self.assertEqual(''.join(f.lines),text.replace('\n',''))
        self.assertTrue(all(not t or t[0] not in tf.CLOSING for t in f.lines))
        self.assertEqual(tf.lines_of('first\n\nthird',self.theme.f_body,20,300),['first','','third'])

    def test_schema_direct_build_and_reusable_plan_no_side_effects(self):
        p=self.cli('build_poster.py','--schema');self.assertEqual(p.returncode,0,p.stderr)
        spec=json.loads(p.stdout);sf=self.work/'poster.json';sf.write_text(json.dumps(spec))
        absent=self.work/'absent'
        before=set(self.work.rglob('*'))
        p=self.cli('build_poster.py','--spec',sf,'--plan','--out',absent/'poster.pptx')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(set(self.work.rglob('*')),before)
        self.assertFalse((self.work/'state').exists())
        envelope=json.loads(p.stdout);self.assertIn('reading_order',envelope['plan'])
        sf.write_text(json.dumps(envelope));p=self.cli('build_poster.py','--spec',sf,'--out',absent/'poster.pptx')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertTrue((absent/'poster.pptx').exists())
        for bad in ({'unexpected':1,'content':{'title':'X'}},{'family':'invalid','content':{'title':'X'}},
                    {'canvas':{'width':0},'content':{'title':'X'}},{'layout':{'columns':3},'content':{'title':'X'}}):
            with self.assertRaises(ValueError):bp.plan(bad)

    def test_spec_relative_image_two_artifacts_sidecars_and_alias_priority(self):
        inputs=self.work/'input';inputs.mkdir()
        Image.new('RGB',(100,120),(30,80,120)).save(inputs/'image.png')
        spec={'family':'image_led','meta':{'elements':False},'content':{'title':'SUPPLIED IMAGE','image':'image.png'}}
        sf=inputs/'poster.json';sf.write_text(json.dumps(spec))
        outputs=self.work/'nested/output'
        for stem in ('one','two'):
            p=self.cli('build_poster.py','--spec',sf,'--out',outputs/(stem+'.pptx'),cwd=self.work)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        one=outputs/'one.pptx';two=outputs/'two.pptx'
        self.assertTrue(aio.paths(one)[2].joinpath('user-duotone.png').exists())
        self.assertTrue(aio.paths(two)[2].joinpath('user-duotone.png').exists())
        original=(outputs/'style.json').read_bytes()
        style=aio.read_style(two);style['title']='ARTIFACT TWO'
        aio.write_style(two,style)
        self.assertEqual((outputs/'style.json').read_bytes(),original)
        self.assertEqual(aio.read_style(two)['title'],'ARTIFACT TWO')
        for tool in ('qa.py','layout_check.py'):
            p=self.cli(tool,'--deck',two);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        spec['content']['image']='missing.png'
        with self.assertRaisesRegex(ValueError,'Missing input poster image.*missing.png'):bp.plan(spec,inputs)

    def test_deck_spec_relative_media_nested_output_and_rebuild_bytes(self):
        input_dir=self.work/'input';input_dir.mkdir()
        p=self.cli('make_textures.py','bg','--out',input_dir/'media','--pages',1,'--palette','G','--seed',11,
                   '--manifest',input_dir/'media/manifest.json')
        self.assertEqual(p.returncode,0,p.stderr)
        sf=input_dir/'deck.json';sf.write_text(json.dumps({'meta':{'lang':'en','seed':11,'title':'SAME',
            'media':'media','bg_manifest':'media/manifest.json','elements':False},'pages':[{'archetype':'cover','title':'SUPPLIED TITLE'}]}))
        first=self.work/'nested/deck.pptx'
        for out in (first,self.work/'nested/other.pptx'):
            p=self.cli('build_deck.py','--spec',sf,'--out',out,cwd=self.work)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(first.read_bytes(),first.with_name('other.pptx').read_bytes())
        self.assertTrue(aio.paths(first)[1].exists())
        self.assertTrue(aio.paths(first)[2].is_dir())
        spec=json.loads(sf.read_text());spec['meta']['media']='missing'
        with self.assertRaisesRegex(ValueError,'Missing input deck media'):bd.build(spec,self.work/'bad.pptx',input_dir)

    def test_automatic_text_decoration_filter_exclusions_and_empty_pool(self):
        for a in compose.DIALECTS:
            names={n for _,n in compose.element_pool(a,a)}
            self.assertFalse(names & (set(E.COPY_FIELDS)|compose.NUMBER_BEARING))
        with self.assertRaisesRegex(ValueError,'requires supplied fields'):E.render('ticket_stub',{'inkA':'#D7261E'})
        spec={'meta':{'lang':'en','elements':True,'seed':4,'dialect':['A','C']},
              'pages':[{'archetype':'cover','title':'NO GENERATED COPY','element_pool':[]},
                       {'archetype':'cover','title':'EXCLUDED','exclude_elements':list(E.REGISTRY)}]}
        out=self.work/'empty.pptx';bd.build(spec,out)
        self.assertEqual(aio.read_style(out)['elements'],[])
        self.assertFalse(any(s.name.startswith('el[') for sl in Presentation(out).slides for s in sl.shapes))

    def test_poster_modules_footer_alignment_reading_order_and_demotions(self):
        spec={'family':'type_led','meta':{'elements':False},'layout':{'columns':2,'alignment':'c'},
              'content':{'title':'SUPPLIED HIERARCHY','quote':{'text':'Supplied quote'},'key_number':{'value':'42','label':'Supplied number'},
                         'blocks':[{'title':'Short','text':'Supplied short body.'},{'title':'Longer','text':'Supplied longer body. '*8}],
                         'footer':'Supplied footer'}}
        out=self.work/'poster.pptx';bp.build(spec,out)
        policy=aio.read_style(out)['poster'];roles=policy['roles']
        self.assertEqual(policy['layout']['columns'],2)
        blocks=[r for r in roles if r['role']=='block'];self.assertGreater(blocks[1]['rect'][3]-blocks[1]['rect'][1],blocks[0]['rect'][3]-blocks[0]['rect'][1])
        self.assertEqual({r['role'] for r in policy['role_demotions']},{'quote','key_number'})
        slide=Presentation(out).slides[0];names={s.name for s in slide.shapes}
        for r in policy['reading_order']:
            self.assertTrue(r['shapes']);self.assertTrue(set(r['shapes'])<=names)
        footer=next(r for r in roles if r['role']=='footer')
        self.assertLess(footer['rect'][3],poster_canvas().safe[3]-50)
        self.assertLessEqual(policy['vertical_shift'],(poster_canvas().safe[3]-poster_canvas().safe[1])*.12)
        spec['layout'].update(footer_anchor='edge',vertical_alignment='top',structure='none')
        result=bp.plan(spec)['plan'];edge=next(r for r in result['roles'] if r['role']=='footer')
        self.assertAlmostEqual(edge['rect'][3],poster_canvas().safe[3],places=2)
        self.assertEqual(result['vertical_shift'],0)
        spec['content']['key_number']['value']=0
        spec['content']['body']=['First supplied paragraph','Second supplied paragraph']
        result=bp.plan(spec)['plan']
        self.assertEqual(next(r['text'] for r in result['roles'] if r['role']=='key_number'),'0')
        self.assertEqual(next(r['text'] for r in result['roles'] if r['role']=='body'),
                         'First supplied paragraph\nSecond supplied paragraph')

    def test_supplied_comparison_process_are_vectors_and_both_survive(self):
        spec={'family':'type_led','meta':{'lang':'en','elements':False},
              'layout':{'body_size':18,'title_size':92,'vertical_alignment':'top'},
              'content':{'title':'SUPPLIED RELATIONS',
                         'comparison':[{'label':'First option','text':'Source description'},'Second option'],
                         'process':['Source step one','Source step two']}}
        out=self.work/'information.pptx';bp.build(spec,out)
        policy=aio.read_style(out)['poster'];slide=Presentation(out).slides[0]
        self.assertEqual([d['kind'] for d in policy['diagrams']],['comparison','process'])
        self.assertEqual(policy['diagrams'][0]['edges'],[])
        self.assertEqual(policy['diagrams'][1]['edges'],[[0,1]])
        self.assertEqual(len([s for s in slide.shapes if s.name.startswith('information[')]),5)
        for kind in ('comparison','process'):
            self.assertEqual([r['block_index'] for r in policy['roles'] if r['role']==kind],[0,1])
        for tool in ('qa.py','layout_check.py'):
            p=self.cli(tool,'--deck',out);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        spec['content'].pop('comparison');spec['content'].pop('process')
        self.assertEqual(bp.plan(spec)['plan']['diagrams'],[])

    def test_state_actual_write_failure_override_and_fallback_reuse(self):
        default=self.work/'default';fallback=self.work/'fallback'
        real=sp._atomic_write
        def failing(path,payload):
            if path.parent==default:raise PermissionError('injected actual write failure')
            return real(path,payload)
        with patch.dict(os.environ,{},clear=False),patch.object(sp,'state_dir',return_value=default),patch.object(sp,'fallback_dir',return_value=fallback):
            os.environ.pop('RISO_DESIGN_STATE_DIR',None)
            with patch.object(sp,'_atomic_write',side_effect=failing),self.assertWarnsRegex(RuntimeWarning,'external fallback'):
                compose.append_history(None,{'deck':'A','seed':1,'primary':'A','secondary':'C'})
            default.mkdir();(default/'history.json').write_text('{"decks":[]}')
            self.assertEqual(compose.load_history()['decks'][0]['deck'],'A')
            with patch.object(sp,'_atomic_write',side_effect=failing),self.assertWarns(RuntimeWarning):
                compose.append_history(None,{'deck':'B','seed':2,'primary':'C','secondary':'A'})
            self.assertEqual(len(compose.load_history()['decks']),2)
        bad=self.work/'not-a-directory';bad.write_text('file')
        with patch.dict(os.environ,{'RISO_DESIGN_STATE_DIR':str(bad)}):
            with self.assertRaisesRegex(ValueError,'Explicit RISO_DESIGN_STATE_DIR.*not-a-directory'):
                compose.append_history(None,{'deck':'bad','seed':3})

    def test_renderer_execution_workdir_failure_preserves_source(self):
        import contextlib,io,render
        prs=rk.new_deck();rk.add_page(prs,None);source=self.work/'source.pptx';prs.save(source)
        before=source.read_bytes()
        args=['render.py','--deck',str(source),'--out',str(self.work/'preview'),'--work-dir',str(self.work/'scratch')]
        with (patch.object(render,'pick_route',return_value=('mock',None,None)),
              patch.object(render,'to_pdf',side_effect=PermissionError('execution denied')),
              patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()) as err):
            self.assertEqual(render.main(),4);self.assertIn('execution/workdir',err.getvalue())
        self.assertEqual(source.read_bytes(),before);self.assertFalse((self.work/'preview').exists())
        bad=self.work/'bad-work';bad.write_text('file')
        args[-1]=str(bad)
        with patch.object(render,'pick_route',return_value=('mock',None,None)),patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(render.main(),4)

    def test_element_png_and_complete_artifact_bytes_are_seeded(self):
        import io, zipfile, numpy as np
        palette={'inkA':'#D7261E','inkB':'#1E1E1E','paper':'#EFE7D8'}
        before=np.random.get_state()
        for name in sorted(E.REGISTRY):
            hashes=[]
            for trial in range(3):
                np.random.seed(900+trial)
                global_before=np.random.get_state()
                image=E.render(name,palette,size=(120,90),seed=17,allow_defaults=True)
                buf=io.BytesIO();image.save(buf,format='PNG')
                hashes.append(hashlib.sha256(buf.getvalue()).hexdigest())
                global_after=np.random.get_state()
                self.assertTrue(all(np.array_equal(a,b) for a,b in zip(global_before,global_after)),name)
            self.assertEqual(len(set(hashes)),1,name)
        np.random.set_state(before)
        specs=[('deck',{'meta':{'lang':'en','seed':42,'dialect':['E','C']},
                       'pages':[{'archetype':'cover','title':'SEEDED PRINT'}]}),
               ('poster',{'family':'type_led','meta':{'lang':'en','seed':42,'dialect':['E','C']},
                          'content':{'title':'SEEDED PRINT','body':'Supplied source copy.'}})]
        for kind,spec in specs:
            hashes=[];members=[]
            for trial in range(3):
                out=self.work/f'{kind}-{trial}'/'print.pptx'
                (bd if kind=='deck' else bp).build(copy.deepcopy(spec),out)
                hashes.append(hashlib.sha256(out.read_bytes()).hexdigest())
                with zipfile.ZipFile(out) as z:
                    members.append({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('ppt/media/')})
            self.assertEqual(len(set(hashes)),1,kind)
            self.assertEqual(members[0],members[1]);self.assertEqual(members[1],members[2])

    def test_pixel_sampling_uses_glyphs_and_keeps_bad_contrast_failure(self):
        from PIL import ImageDraw
        prs=rk.new_deck();slide=rk.add_page(prs,None)
        shape=rk.label(slide,48,100,700,'ACTUAL GLYPHS',self.theme,size=20)
        # A separate traversal creates a different proxy for the same XML.
        ts=qa.text_shapes(slide)[0]
        expected=tm.ink_rect(shape)
        self.assertEqual(ts['glyph'],expected)
        self.assertLess(ts['measure_w'],shape.width.pt/2)
        preview=self.work/'preview';preview.mkdir()
        img=Image.new('RGB',(960,540),'white')
        x0,y0,x1,y1=map(int,expected)
        ImageDraw.Draw(img).rectangle((x0,y0,(x0+x1)//2,y1),fill='black')
        img.save(preview/'page-0001.png');deck=self.work/'pixel.pptx';prs.save(deck)
        args=argparse.Namespace(canvas=DECK_CANVAS,max_outside=.004,max_bg_ink=.03,strict_chrome=False)
        rep=qa.Report();qa.pixel_checks(rep,str(deck),str(self.work/'absent-media'),str(preview),args)
        item=next(i for i in rep.items if i['check']=='text is legible where it sits')
        self.assertTrue(item['ok'],item)
        Image.new('RGB',(960,540),'white').save(preview/'page-0001.png')
        rep=qa.Report();qa.pixel_checks(rep,str(deck),str(self.work/'absent-media'),str(preview),args)
        item=next(i for i in rep.items if i['check']=='text is legible where it sits')
        self.assertFalse(item['ok']);self.assertEqual(qa.MIN_GLYPH_DELTA,45)

    def test_pixel_skip_report_and_ci_missing_previews(self):
        out=self.work/'qa.pptx'
        bd.build({'meta':{'lang':'en','elements':False},'pages':[{'archetype':'cover','title':'CHECK SOURCE'}]},out)
        report=self.work/'qa.json'
        p=self.cli('qa.py','--deck',out,'--json',report)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('SKIPPED',p.stdout);self.assertIn('UNVERIFIED, not passed',p.stdout)
        data=json.loads(report.read_text(encoding='utf-8'));self.assertEqual(data['pixel_checks'],'skipped')
        self.assertEqual(data['pixel_check_count'],0);self.assertGreater(data['pixel_checks_scheduled'],0)
        p=self.cli('qa.py','--deck',out,'--require-render','--json',report)
        self.assertEqual(p.returncode,3,p.stdout+p.stderr)
        self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['verification'],'incomplete')
        p=self.cli('qa.py','--deck',out,'--require-render','--render',self.work/'missing')
        self.assertEqual(p.returncode,3)
        preview=self.work/'stale';preview.mkdir()
        Image.new('RGB',(960,540),'white').save(preview/'page-0001.png')
        (preview/'render.json').write_text(json.dumps({'source_sha256':'stale'}))
        p=self.cli('qa.py','--deck',out,'--require-render','--render',preview)
        self.assertEqual(p.returncode,3);self.assertIn('source hash',p.stdout)

    def test_chrome_quiet_plate_and_reverse_ink(self):
        import make_textures as mt, numpy as np
        image=Image.new('RGB',(960,540),(20,20,20))
        regions=[(850,490,910,510)]
        one=mt.quiet_plate(image,regions,(239,231,216),7)
        two=mt.quiet_plate(image,regions,(239,231,216),7)
        self.assertEqual(one.tobytes(),two.tobytes())
        self.assertGreater(np.asarray(one)[495:505,855:905].mean(),210)
        self.assertEqual(one.getpixel((100,100)),image.getpixel((100,100)))
        prs=rk.new_deck();slide=rk.add_page(prs,None)
        rk.chrome(slide,self.theme,1,1,'SUPPLIED HEADER','',on_red=True)
        for sh in slide.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:self.assertEqual(str(r.font.color.rgb),self.theme.paper.lstrip('#').upper())

    def test_quote_frame_fits_measured_multiline_body(self):
        lines=['Supplied first sentence.','Supplied second sentence.']
        slide=self.page('quote',{'lines':lines,'attribution':'Supplied author','source':'Supplied source'})
        body=next(sh for sh in slide.shapes if sh.name.startswith('quote-body'))
        self.assertEqual(body.text,'\n'.join(lines))
        self.assertFalse(lc.check_slide(slide,1,archetype='quote')['fails'])
        slide=self.page('quote',{'lines':lines+['Supplied third sentence.'], 'size':40,
                                'highlight':'Supplied','attribution':'Supplied author','source':'Supplied source'})
        body=next(sh for sh in slide.shapes if sh.name.startswith('quote-body'))
        self.assertLess(body.text_frame.paragraphs[0].runs[0].font.size.pt,40)
        self.assertFalse(lc.check_slide(slide,1,archetype='quote')['fails'])

    def test_resolved_font_files_and_collection_faces(self):
        for family in (self.theme.f_body,rk.Theme(lang='zh').f_body,rk.Theme(lang='zh').f_heading):
            path=tm.resolve(family)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(tm.font(family,24).getname()[0].casefold(),family.casefold())
        self.assertIsNone(tm.resolve('NoSuchRisoFeedbackFont'))
        with self.assertRaisesRegex(ValueError,'Font not resolvable'):tm.advance('text','NoSuchRisoFeedbackFont',24)
        from demo_seeds import spec_for
        spec=spec_for(101);out=self.work/'real-cjk.pptx'
        background_plan=self.work/'background-plan.json'
        background_plan.write_text(json.dumps({'pages':spec['backgrounds']}))
        media=self.work/'cjk-media'
        p=self.cli('make_textures.py','bg','--out',media,'--pages',4,'--palette','G','--seed',101,
                   '--plan-file',background_plan,'--manifest',media/'manifest.json')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        spec['meta'].update(media=str(media),bg_manifest=str(media/'manifest.json'))
        bd.build(spec,out)
        style=aio.read_style(out)
        self.assertTrue(any(r.get('dialect')=='E' for r in style['elements']))
        for tool in ('qa.py','layout_check.py'):
            p=self.cli(tool,'--deck',out);self.assertEqual(p.returncode,0,p.stdout+p.stderr)


if __name__=='__main__':unittest.main()

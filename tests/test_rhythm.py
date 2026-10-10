"""Whole-deck checker must reject degeneration and permit sensible repetition."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'))
import compose
import layout_check as lc
import rhythm
import riso_kit as rk


class RhythmTests(unittest.TestCase):
    def page(self,prs,x=60,y=110):
        slide=rk.add_page(prs,None)
        rk.text(slide,x,y,300,150,[dict(runs=[('24%',{})],font='Georgia',size=110,color='#2B2B2B')])
        return lc.check_slide(slide,len(prs.slides),archetype='data')

    def test_eleven_identical_pages_fail_and_cli_reports_deck(self):
        prs=rk.new_deck()
        pages=[self.page(prs) for _ in range(11)]
        report=rhythm.check_deck(pages)
        self.assertFalse(report['pass'])
        self.assertTrue(any('run' in f for f in report['fails']))
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            prs.save(tmp/'bad.pptx')
            (tmp/'style.json').write_text(json.dumps({'pages':[{'archetype':'data'}]*11}))
            p=subprocess.run([sys.executable,str(ROOT/'scripts'/'layout_check.py'),
                 '--deck',str(tmp/'bad.pptx'),'--json',str(tmp/'report.json'),'--deck-level'],
                 capture_output=True,text=True,encoding='utf-8',errors='replace')
            self.assertEqual(p.returncode,1,p.stdout+p.stderr)
            r=json.loads((tmp/'report.json').read_text())
            self.assertFalse(r['deck']['pass'])
            self.assertEqual(len(r['deck']['archetype_sequence']),11)

    def test_two_data_pages_in_distinct_zones_are_legal(self):
        prs=rk.new_deck()
        pages=[self.page(prs),self.page(prs,580,280)]
        self.assertNotEqual(pages[0]['protagonist_zone'],pages[1]['protagonist_zone'])
        self.assertTrue(rhythm.check_deck(pages)['pass'])

    def test_near_identical_and_aggregate_repetition_fail(self):
        prs=rk.new_deck()
        pages=[self.page(prs,60+i,110+i) for i in range(3)]
        self.assertFalse(rhythm.check_deck(pages)['pass'])
        different=self.page(prs,580,280)
        pages=[pages[0],pages[0],different,pages[0],pages[0],different,
               pages[0],pages[0],pages[0],pages[0]]
        self.assertTrue(any('repeat one' in f for f in rhythm.check_deck(pages)['fails']))

    def test_identical_pair_warns_without_failing(self):
        prs=rk.new_deck()
        pages=[self.page(prs),self.page(prs)]
        r=rhythm.check_deck(pages)
        self.assertTrue(r['pass'])
        self.assertTrue(r['warns'])

    def test_chart_geometry_changes_signature_without_moving_title(self):
        prs=rk.new_deck()
        pages=[]
        for i in range(3):
            self.page(prs)
            rk.rect(prs.slides[-1],450,250+i*70,240,25,fill='#2B2B2B')
            pages.append(lc.check_slide(prs.slides[-1],i+1,archetype='data'))
        self.assertEqual(len({p['protagonist_zone'] for p in pages}),1)
        self.assertNotEqual(pages[0]['layout_signature'],pages[1]['layout_signature'])
        self.assertTrue(rhythm.check_deck(pages)['pass'])

    def test_plan_preserves_copy_page_count_and_source_roles(self):
        pages=[{'archetype':'data','hero':'24%','planning':{'claim':'supplied claim',
                    'support':'supplied support','anchor':'24%'}},
               {'archetype':'quote','quote':'supplied quote'}]
        original=copy.deepcopy(pages)
        plan=compose.plan_rhythm(pages)
        self.assertEqual(pages,original)
        self.assertEqual(len(plan),len(pages))
        self.assertEqual(plan[0]['roles'],pages[0]['planning'])
        self.assertEqual(plan[1]['emphasis_candidates']['quote'],pages[1]['quote'])


if __name__=='__main__':unittest.main()

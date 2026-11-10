"""One command: source plan -> editable deck -> geometry -> render -> QA -> manifest."""
import argparse,contextlib,hashlib,importlib,io,json,os,shutil,subprocess,sys,time
from pathlib import Path

def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def render_options(args):
    if getattr(args,'kit',None):options=['--kit',args.kit]
    elif getattr(args,'autodiscover',False):options=['--autodiscover']
    else:options=['--system']
    if getattr(args,'node',None):options+=['--node',args.node]
    return options+['--dpi',str(args.dpi)]

def draft_slide(slide, width):
    """Draw each text shape once. Shape proxies change on every iteration."""
    from PIL import Image,ImageDraw
    import textmetrics as tm
    image=Image.new('RGB',(960,540),'#faf7ef');draw=ImageDraw.Draw(image);scale=960/width
    for shape in slide.shapes:
        if not shape.has_text_frame or not shape.text.strip():continue
        run=next((r for p in shape.text_frame.paragraphs for r in p.runs),None)
        font=tm.font(run.font.name or 'Arial',round((run.font.size.pt if run.font.size else 18)*scale),bool(run.font.bold)) if run else None
        draw.multiline_text((shape.left.pt*scale,shape.top.pt*scale),shape.text,font=font,fill='#172e49')
    return image

def run(args):
    start=time.perf_counter();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True);timings={};stages={};status=dict(status='STARTED',render='NOT_REQUESTED',visual_review='AWAITING_INSPECTION');spec={}
    def timed(name,fn):
        t=time.perf_counter()
        try:result=fn();stages[name]=dict(exit_code=0);return result
        except Exception:stages[name]=dict(exit_code=1);raise
        finally:timings[name]=round(time.perf_counter()-t,4)
    def command(name,argv):
        def execute():
            buf=io.StringIO();old=sys.argv
            try:
                sys.argv=[name,*map(str,argv)]
                with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):rc=importlib.import_module(name.split('-')[0]).main()
            finally:sys.argv=old
            (out/(name+'.log')).write_text(buf.getvalue(),encoding='utf-8')
            if rc:raise ValueError(name+' failed: '+buf.getvalue()[-1800:])
        timed(name,execute)
    try:
        from deck_content_plan import compile_plan,gate,text
        require_storyboard = getattr(args, 'require_storyboard', False)
        if args.plan:
            plan=json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
            if plan.get('target')!='deck':raise ValueError('deck_run requires target=deck')
            spec, report = timed('compile', lambda: compile_plan(plan, require_storyboard=require_storyboard))
            args.content_plan = args.plan
            status['content_plan'] = dict(skipped=True, reason='explicit --skip-plan compatibility escape') if args.skip_plan else report
        else:
            spec=json.loads(Path(args.spec).read_text(encoding='utf-8-sig'))
            status['content_plan']=timed('content-plan',lambda:gate(spec,args.content_plan,args.skip_plan,args.spec,require_storyboard=require_storyboard))
        write(out/'source.json',spec)
        if args.content_plan and Path(args.content_plan).resolve()!=out/'content-plan.json':shutil.copy2(args.content_plan,out/'content-plan.json')
        if status['content_plan'].get('storyboard'):
            from deck_storyboard import markdown
            if not args.plan:
                plan = json.loads(Path(args.content_plan).read_text(encoding='utf-8-sig'))
            (out/'storyboard.md').write_text(markdown(plan, text), encoding='utf-8')
        from build_deck import build
        deck=out/'deck.pptx';timed('build',lambda:build(spec,deck,Path(args.spec).resolve().parent if args.spec else Path(args.plan).resolve().parent))
        command('qa',['--deck',deck,'--json',out/'qa.json'])
        command('layout_check',['--deck',deck,'--json',out/'layout.json'])
        if args.draft:
            from pptx import Presentation
            folder=out/'draft';folder.mkdir(exist_ok=True);prs=Presentation(deck)
            for i,slide in enumerate(prs.slides,1):
                image=draft_slide(slide,prs.slide_width.pt)
                image.save(folder/f'page-{i:04d}.png')
            status['status']='DRAFT_GEOMETRY_PASS'
        elif args.auto or args.render:
            opts=render_options(args)
            from render_cache import render_cached
            render_status=timed('render-cache',lambda:render_cached(deck,out/'preview',['--keep-pdf',*opts],
                lambda:command('render',['--deck',deck,'--out',out/'preview','--keep-pdf',*opts]),args.mode))
            command('qa-rendered',['--deck',deck,'--render',out/'preview','--require-render','--json',out/'qa-rendered.json'])
            status.update(status='RENDERED_QA_PASS',render=render_status)
            from deck_preview import review_images, RUBRIC, variants_contact
            pngs=sorted((out/'preview').glob('page-*.png'));visual=out/'visual';visual.mkdir(exist_ok=True)
            for png in pngs:
                row=review_images(png,visual/png.stem);row.update(reviewer='',viewed=dict(full=False,thumbnail=False,blur=False),scores=dict.fromkeys(RUBRIC),weaknesses=[],pptx_sha256=sha(deck),source_sha256=sha(out/'source.json'),plan_sha256=spec.get('content_plan',{}).get('plan_sha256'))
                write(visual/png.stem/'review.json',row)
            variants_contact(pngs,visual/'contact.png')
        else:status['status']='GEOMETRY_PASS'
    except Exception as exc:status.update(status='FAILED',error=str(exc))
    finally:
        from run_manifest import engine_version,presentation_fonts
        # Style sidecar is a regular artifact; source plans remain explicit.
        style=json.loads((out/'deck.style.json').read_text(encoding='utf-8')) if (out/'deck.style.json').is_file() else {}
        plans=[r['plan'] for r in style.get('evidence_pages',[])]
        font_rows=presentation_fonts(out/'deck.pptx') if stages.get('build',{}).get('exit_code')==0 else []
        timings['total']=round(time.perf_counter()-start,4)
        status['next']='Inspect visual/contact.png and per-page review scaffolds; aesthetic scores remain unfilled.'
        write(out/'run.json',status);write(out/'timings.json',timings)
        write(out/'summary.json',dict(status=status['status'],render=status['render'],engine_seconds=timings['total'],stages=timings,evidence_level=spec.get('evidence',{}).get('level'),pages=len(spec.get('pages',[])),page_types=[p.get('archetype') for p in spec.get('pages',[])],metrics=[p.get('infographic_metrics') for p in plans],error=status.get('error'),visual_review=status['visual_review']))
        from input_cache import output_files
        storyboard = bool(status.get('content_plan', {}).get('storyboard'))
        files=[p for p in output_files(out,'deck',status['render']!='NOT_REQUESTED',storyboard=storyboard) if p.name!='run-manifest.json']
        write(out/'run-manifest.json',dict(engine_version=engine_version(),status=status['status'],artifact_hashes={p.relative_to(out).as_posix():sha(p) for p in files},stages=stages,fonts=font_rows,parameters=dict(out=str(out),draft=args.draft,mode=args.mode),exit_code=int(status['status']=='FAILED')))
    return status

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('spec','plan','content-plan','out','kit','node'):ap.add_argument('--'+k)
    for k in ('auto','render','draft','system','autodiscover','skip-plan','require-storyboard'):ap.add_argument('--'+k,action='store_true')
    ap.add_argument('--mode',choices=['fast','audit'],default='fast');ap.add_argument('--dpi',type=int,default=110)
    a=ap.parse_args()
    if not a.out or not (a.plan or a.spec):ap.error('--out and --plan/--spec required')
    if a.plan and a.spec:ap.error('choose --plan or --spec')
    if a.skip_plan and a.require_storyboard:ap.error('--skip-plan cannot be combined with --require-storyboard')
    if a.system and (a.kit or a.autodiscover):ap.error('--system is exclusive with --kit/--autodiscover')
    a.system = not (a.kit or a.autodiscover)
    from input_cache import key,restore,store
    options={k:v for k,v in vars(a).items() if k not in ('spec','plan','content_plan','out','mode')};options['artifact']='deck'
    cache,payload=key(dict(spec=a.spec,plan=a.plan or a.content_plan),options)
    status=restore(cache,a.out) if a.mode!='audit' else None
    if status is None:
        status=run(a)
        if status['status']!='FAILED':store(cache,a.out,payload)
    for k in ('status','render','cache','error','next'):
        if k in status:print(k+': '+str(status[k]))
    print('evidence: '+str(Path(a.out).resolve()));return int(status['status']=='FAILED')

if __name__=='__main__':raise SystemExit(main())

"""One bounded poster workflow. Detailed evidence in files; <=40 summary lines."""
import argparse,contextlib,hashlib,io,json,os,platform,shutil,subprocess,sys,time,importlib
from pathlib import Path
from importlib.metadata import version

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def run(spec,out,render=False,mode='fast',autofit=True,verbose=False,plan_only=False,content_plan=None,skip_plan=False,element_density=None,render_options=None,draft_only=False):
    from build_poster import normalize
    from poster_flow import make_plan,preflight,CapacityError
    from poster_preview import wireframe,contact
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);start=time.perf_counter();timings={};stages={};p={};s={};renderer_info={'status':'NOT_INVOKED'};status={'status':'STARTED','render':'NOT_REQUESTED','visual_review':'AWAITING_INSPECTION'}
    def timed(name,fn):
        begin=time.perf_counter()
        try:
            result=fn();stages[name]={'exit_code':getattr(result,'returncode',0)};return result
        except Exception:
            stages[name]={'exit_code':1};raise
        finally:timings[name]=round(time.perf_counter()-begin,4)
    def command(name,args):
        def execute():
            module=name.split('-')[0]
            if module=='render':return subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),*map(str,args)],capture_output=True,text=True,encoding='utf-8',timeout=300)
            # Same CLI validators, same flags, no extra Python process/imports.
            saved=sys.argv;stdout=io.StringIO();stderr=io.StringIO()
            try:
                sys.argv=[module,*map(str,args)]
                with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):rc=importlib.import_module(module).main()
                return subprocess.CompletedProcess(sys.argv,rc,stdout.getvalue(),stderr.getvalue())
            finally:sys.argv=saved
        result=timed(name,execute)
        log=(result.stdout or '')+(result.stderr or '');(out/(name+'.log')).write_text(log,encoding='utf-8')
        if verbose:print(log)
        if result.returncode:raise RuntimeError(f'{name} failed ({result.returncode}):\n'+log.strip())
        return result
    environment=dict(python=sys.version.split()[0],platform=platform.platform(),packages={k:version(k) for k in ('python-pptx','Pillow','numpy')},sample_count=1,mode=mode,cold_warm='process cold; OS/font/LibreOffice cache state not controlled')
    try:
        path=Path(spec).resolve();raw=json.loads(path.read_text(encoding='utf-8-sig'))
        from content_plan import gate
        status['content_plan']=timed('content-plan',lambda:gate(raw,content_plan,skip_plan,path))
        if content_plan:shutil.copyfile(content_plan,out/'content-plan.json') if Path(content_plan).resolve()!=out/'content-plan.json' else None
        s=timed('validate',lambda:normalize(raw,path.parent))
        s.setdefault('art_direction',{});s['art_direction']['autofit']=autofit
        if element_density:s['art_direction']['element_density']=element_density
        write(out/'source.json',s)
        p=timed('plan',lambda:make_plan(s));write(out/'poster.plan.json',p)
        write(out/'preflight.json',preflight(s,plan=p))
        if not render:
            status['wireframe']=timed('wireframe',lambda:wireframe(p,out/'wireframe.png'))
            from poster_preview import draft
            status['draft']=timed('draft',lambda:draft(p,out/'draft.png'))
        write(out/'plan-summary.json',{k:v for k,v in p.items() if k not in ('objects','content_roles')})
        if plan_only or draft_only:
            blocking=[e for e in p['coordination']['fails'] if not e.startswith('Accent area below')]
            if blocking:raise ValueError('; '.join(blocking))
            p.setdefault('contract_warnings',[]).extend(e for e in p['coordination']['fails'] if e.startswith('Accent area below'))
            status.update(status='PLANNED',body_size=p['scale_ladder']['body'],hero_share=p['hero']['share'],dialect=p['dialect'],archetype=p['archetype'],recipe=p['graphic_design']['recipe'],meaning=p['graphic_design']['meaning'],warnings=p.get('contract_warnings',[]),next='Inspect wireframe.png and plan-summary.json. Saved-PPTX geometry and pixels remain UNVERIFIED; omit --plan-only and add --render for final build.')
            return status
        from poster_direction import build as build_prepared
        deck=out/'poster.pptx';timed('build',lambda:build_prepared(s,deck,plan=p));write(out/'plan-summary.json',{k:v for k,v in p.items() if k not in ('objects','content_roles')})
        command('qa',['--deck',deck,'--json',out/'qa.json'])
        # qa runs layout_check's exact modern poster checker on the saved PPTX.
        # Export that same per-run result, never a stale plan-only approval.
        checked=json.loads((out/'qa.json').read_text(encoding='utf-8'))['poster_layout']
        timed('layout_check',lambda:write(out/'layout.json',dict(deck=deck.name,artifact='poster',pages=checked,**{'pass':bool(checked) and all(q['pass'] for q in checked)},provenance='same saved-PPTX checker result from qa; no duplicate traversal')))
        status.update(body_size=p['scale_ladder']['body'],hero_share=p['hero']['share'],archetype=p['archetype'],meaning=p['graphic_design']['meaning'],warnings=p.get('contract_warnings',[]),status='GEOMETRY_PASS',dialect=p['dialect'],recipe=p['graphic_design']['recipe'],fields=p['preflight']['fields'],words=p['content_words'],autofit=p['autofit']['changes'],voids=p['voids'])
        if render:
            # PPTX hash includes source, geometry, font names, all native objects
            # and paper. Renderer environment/code participates in the cache key.
            import render as renderer
            soffice=renderer.find_soffice();stamp=str(Path(soffice).stat().st_mtime_ns) if soffice and Path(soffice).is_file() else 'unknown'
            renderer_info=dict(path=soffice,stamp=stamp,status='DISCOVERED',version='UNVERIFIED')
            from run_manifest import renderer_version
            renderer_info['version']=timed('renderer-version',lambda:renderer_version(soffice))
            from render_cache import render_cached
            preview=out/'preview';options=render_options or ['--system']
            status['render']=timed('render-cache',lambda:render_cached(deck,preview,options,
                lambda:command('render',['--deck',deck,'--out',preview,*options]),mode))
            environment['render_cache']='warm hit' if status['render']=='CACHE_HIT' else 'cold miss'
            renderer_info['status']=status['render']
            command('qa-rendered',['--deck',deck,'--render',preview,'--require-render','--json',out/'qa-rendered.json'])
            from evidence_presence import measure
            from artifact_io import background_file
            presence=measure(preview/'page-0001.png',p,background_file(out/'poster-media',1))
            write(out/'evidence-presence.json',presence)
            if p.get('infographic_metrics'):p['infographic_metrics']['evidence_presence']['raster_ink']=presence
            from poster_review import review_images,RUBRIC
            visual=out/'visual';provenance=review_images(preview/'page-0001.png',visual);contact(preview/'page-0001.png',visual/'contact.png',p['dialect'])
            template=dict(provenance,dialect=p['dialect'],mode=mode,reviewer='',viewed=dict(full=False,thumbnail=False,blur=False),scores=dict.fromkeys(RUBRIC,None),weaknesses=[__import__('poster_contract').weakness_example()],metrics=dict(voids=p['voids'],reading_order='checked',body_floor=min(o['fit']['size'] for o in p['objects'] if o['kind']=='text'),graphic_design=p['graphic_design']))
            template.update(plan_sha256=sha(out/'poster.plan.json'),pptx_sha256=sha(deck))
            target=visual/'review.json'
            previous=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
            if any(previous.get(k)!=template[k] for k in ('render_sha256','plan_sha256','pptx_sha256')):write(target,template)
            status['status']='RENDERED_QA_PASS'
        status['next']='Inspect visual/contact.png and fill 9 scores plus 0–5 located weaknesses in visual/review.json; validate with poster_review --review.' if render else 'Inspect wireframe.png; run the same command with --render for final visual review.'
    except CapacityError as e:
        calibrated=preflight(s,diagnostic=e.report)
        write(out/'capacity-error.json',e.report);write(out/'preflight.json',calibrated);status.update(status='CAPACITY_FAILED',error=calibrated['estimated_capacity']+'; '+str(e),next='Read capacity-error.json for columns, tallest modules and repairs; source is unchanged.')
    except Exception as e:status.update(status='FAILED',error=str(e),next='Read the named stage log; do not repeat rendering before geometry passes.')
    finally:
        from run_manifest import fonts
        font_rows=fonts(p) if p else []
        timings['total']=round(time.perf_counter()-start,4)
        # A reused output folder may contain older rendered artifacts. Bind only
        # stages completed by this invocation; a draft cannot re-certify that PNG.
        artifacts=[]
        if stages.get('validate',{}).get('exit_code')==0:artifacts+=['source.json']
        if content_plan and stages.get('content-plan',{}).get('exit_code')==0:artifacts+=['content-plan.json']
        if stages.get('plan',{}).get('exit_code')==0:artifacts+=['poster.plan.json']
        if stages.get('build',{}).get('exit_code')==0:artifacts+=['poster.pptx','poster.style.json']
        if 'qa' in stages:artifacts+=['qa.json']
        if status['render']!='NOT_REQUESTED':artifacts+=['preview/render.json','preview/page-0001.png']
        if 'qa-rendered' in stages:artifacts+=['qa-rendered.json']
        write(out/'run-manifest.json',dict(schema_version='1.1',artifact_hashes={name:sha(out/name) for name in artifacts if (out/name).is_file()},engine_version=__import__('run_manifest').engine_version(),content_plan=status.get('content_plan'),parameters=dict(spec=str(spec),out=str(out),render=render,mode=mode,autofit=autofit,plan_only=plan_only,skip_plan=skip_plan),effective_controls=p.get('effective_controls',{}),stages={k:dict(v,seconds=timings[k]) for k,v in stages.items()},engine_seconds=timings['total'],exit_code=1 if status['status'] in ('FAILED','CAPACITY_FAILED') else 0,fallback_reasons=p.get('autofit',{}).get('changes',[]),fonts=font_rows,renderer=renderer_info,environment=environment,status=status['status']))
        write(out/'timings.json',dict(environment=environment,seconds=timings));write(out/'run.json',status)
        write(out/'summary.json',dict(status=status['status'],engine_seconds=timings['total'],stages=timings,render=status['render'],content_plan=status.get('content_plan'),metrics=p.get('infographic_metrics',p.get('coordination')),warnings=p.get('contract_warnings',[]),visual_review=status['visual_review'],tool_calls=dict(simulated_minimal=3,independent_agent=False,record_real_calls='Count command, image inspection, edit and validation calls separately'),error=status.get('error')))
    return status

def cached_run(args):
    from input_cache import key,restore,store
    inputs=dict(spec=args.spec,plan=args.plan or args.content_plan)
    options={k:v for k,v in vars(args).items() if k not in ('out','mode','verbose','spec','plan','content_plan')}
    cache,payload=key(inputs,options)
    if args.mode!='audit':
        result=restore(cache,args.out)
        if result:return result
    if args.plan:
        from content_plan import to_spec
        plan=json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        if plan.get('target','poster')!='poster':raise ValueError('Use deck_run.py for target=deck')
        target=Path(args.out).resolve();target.mkdir(parents=True,exist_ok=True)
        spec=target/'compiled-spec.json';write(spec,to_spec(plan));args.spec=str(spec);args.content_plan=args.plan
    result=run(args.spec,args.out,args.render,args.mode,args.autofit,args.verbose,args.plan_only,args.content_plan,args.skip_plan,args.element_density,(['--system'] if args.system else [])+(['--autodiscover'] if args.autodiscover else [])+(['--kit',args.kit] if args.kit else [])+(['--node',args.node] if args.node else []))
    if result['status'] not in ('FAILED','CAPACITY_FAILED'):store(cache,args.out,payload)
    return result

def variants(args):
    """Separate subprocesses isolate CLI state and LibreOffice profiles."""
    from concurrent.futures import ThreadPoolExecutor
    from poster_preview import variants_contact
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    original=json.loads(Path(args.spec).read_text(encoding='utf-8-sig'))
    def execute(columns):
        candidate=json.loads(json.dumps(original))
        candidate.setdefault('art_direction',{}).update(columns=columns,archetype='auto')
        folder=out/f'columns-{columns}';folder.mkdir(exist_ok=True)
        source=folder/'spec.json';write(source,candidate)
        command=[sys.executable,str(Path(__file__).resolve()),'--spec',str(source),'--out',str(folder)]
        if args.content_plan:command+=['--content-plan',str(Path(args.content_plan).resolve())]
        if args.skip_plan:command+=['--skip-plan']
        if args.plan_only:command+=['--plan-only']
        for flag in ('system','autodiscover'):
            if getattr(args,flag):command+=['--'+flag]
        for flag in ('kit','node','element_density'):
            if getattr(args,flag):command+=['--'+flag.replace('_','-'),str(getattr(args,flag))]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=360)
        (folder/'variant.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        png=folder/'preview/page-0001.png'
        if not png.exists():png=folder/'draft.png'
        return dict(columns=columns,exit_code=result.returncode,preview=str(png) if png.exists() else None,command=command)
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(execute,(1,2,3)))
    if args.render and not args.plan_only:
        import render as renderer
        from state_paths import state_path
        state_path('render-work').mkdir(parents=True,exist_ok=True)
        valid=[r for r in rows if r['exit_code']==0]
        renderer.batch_render([dict(deck=str(out/f'columns-{r["columns"]}'/'poster.pptx'),out=str(out/f'columns-{r["columns"]}'/'preview')) for r in valid])
        for r in valid:
            from render_cache import identity,remember
            folder=out/f'columns-{r["columns"]}'
            opts=(['--system'] if args.system or not args.autodiscover and not args.kit else [])+(['--autodiscover'] if args.autodiscover else [])+(['--kit',args.kit] if args.kit else [])+(['--node',args.node] if args.node else [])
            signature=identity(folder/'poster.pptx',opts)
            metadata=json.loads((folder/'preview/render.json').read_text(encoding='utf-8'))
            if signature['route'] and signature['route'][0]==metadata['route']:
                remember(folder/'poster.pptx',folder/'preview',opts,signature=signature)
            command=r['command']+['--render'];result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=360)
            r.update(exit_code=result.returncode,preview=str(out/f'columns-{r["columns"]}'/'preview/page-0001.png'),command=command)
    good=[r for r in rows if r['preview']]
    if good:variants_contact([r['preview'] for r in good],out/'variants-contact.png',[f"columns={r['columns']} exit={r['exit_code']}" for r in good])
    write(out/'variants.json',rows);print(json.dumps(rows,indent=2))
    return int(any(r['exit_code'] for r in rows))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--spec');ap.add_argument('--out');ap.add_argument('--render',action='store_true');ap.add_argument('--plan-only',action='store_true');ap.add_argument('--mode',choices=['fast','audit'],default='fast');ap.add_argument('--autofit',action=argparse.BooleanOptionalAction,default=True);ap.add_argument('--verbose',action='store_true');ap.add_argument('--describe-spec',action='store_true');ap.add_argument('--preflight',action='store_true');ap.add_argument('--auto',action='store_true');ap.add_argument('--draft',action='store_true');ap.add_argument('--variants',action='store_true');ap.add_argument('--system',action='store_true');ap.add_argument('--autodiscover',action='store_true');ap.add_argument('--kit');ap.add_argument('--node');ap.add_argument('--element-density',choices=['sparse','normal','rich']);ap.add_argument('--plan');ap.add_argument('--content-plan');ap.add_argument('--skip-plan',action='store_true');a=ap.parse_args()
    if a.auto and not a.draft:a.render=True
    if a.draft:a.plan_only=True
    if a.system and (a.kit or a.autodiscover):ap.error('--system is exclusive with --kit/--autodiscover')
    if a.plan_only and a.render:ap.error('--plan-only and --render are mutually exclusive')
    if a.describe_spec:
        from poster_flow import describe_spec
        print(json.dumps(describe_spec(),indent=2));return 0
    if not a.spec and not a.plan:ap.error('--spec or --plan required')
    if a.spec and a.plan:ap.error('choose --spec or --plan')
    if a.plan and (a.preflight or a.variants):
        from content_plan import to_spec
        target=Path(a.out or Path(a.plan).resolve().parent);target.mkdir(parents=True,exist_ok=True)
        a.spec=str(target/'compiled-spec.json');write(a.spec,to_spec(json.loads(Path(a.plan).read_text(encoding='utf-8-sig'))));a.content_plan=a.plan
    if a.preflight:
        from build_poster import normalize
        from poster_flow import preflight
        from run_manifest import engine_version
        engine_version()
        try:
            s=normalize(json.loads(Path(a.spec).read_text(encoding='utf-8-sig')),Path(a.spec).resolve().parent);report=preflight(s)
        except Exception as exc:print(str(exc));return 1
        target=Path(a.out) if a.out else Path(a.spec).resolve().parent;target.mkdir(parents=True,exist_ok=True);write(target/'preflight.json',report)
        print(json.dumps(report,ensure_ascii=False,indent=2));return 0
    if not a.out:ap.error('--out directory required')
    if a.variants:return variants(a)
    result=cached_run(a)
    for k in ('status','cache','body_size','hero_share','dialect','archetype','recipe','meaning','warnings','fields','words','render','visual_review','error','next'):
        if k in result:print(k+': '+str(result[k]))
    print('evidence: '+str(Path(a.out).resolve()));return 1 if result['status'] in ('FAILED','CAPACITY_FAILED') else 0
if __name__=='__main__':sys.exit(main())

#!/usr/bin/env python3
"""Build an independent poster artifact using the shared Riso print core.

python scripts/build_poster.py --spec poster.json --out poster.pptx [--render]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
sys.dont_write_bytecode=True
from runtime import prepare
prepare()
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))

from canvas import poster_canvas, POSTER_PRESETS
import make_textures as mt
from poster_layouts import choose_family, compose_poster, FAMILIES, TEXT_ROLES
import riso_kit as rk
import textmetrics as tm
import artifact_io as aio
import graphic_recipes
from poster_layouts import layout_options


from poster_contract import example,describe_spec
SCHEMA=example()


def normalize(spec,base_dir=None):
    from poster_contract import canonical
    if isinstance(spec,dict) and 'spec' in spec:
        extra=set(spec)-{'spec','plan','families','text_roles','canvas_presets'}
        if extra:raise ValueError('Unknown poster envelope fields: '+str(sorted(extra)))
        spec=spec['spec']
    spec,warnings=canonical(spec)
    for warning in warnings:print('warning: '+warning)
    meta=spec.get('meta',{});content=spec['content'];modern='art_direction' in spec
    recipe=meta.get('graphic_recipe','auto');disabled=recipe in ('off','micro')
    if recipe not in ('off','micro'):graphic_recipes.validate(recipe)
    if recipe not in ('auto','off','micro'):
        if meta.get('graphic_element'):raise ValueError('Choose graphic_recipe or graphic_element, not both')
        if spec.get('layout',{}).get('graphic')=='none' or not meta.get('elements',True) or meta.get('element_pool')==[]:raise ValueError('graphic_recipe requires enabled elements and graphic band')
        primary=graphic_recipes.RECIPES[recipe]['dialect'];forced=meta.get('dialect')
        if forced and (forced if isinstance(forced,str) else forced[0])!=primary:raise ValueError('graphic_recipe conflicts with explicit primary dialect')
        meta.setdefault('dialect',[primary]);spec['meta']=meta;spec['layout']=dict(spec.get('layout',{}),graphic='band')
    if disabled and not modern:
        meta['graphic_recipe']='auto';meta['elements']=False;spec['meta']=meta
    if not meta.get('elements',True) or meta.get('element_pool')==[]:
        if spec.get('layout',{}).get('graphic')=='band' or meta.get('graphic_element'):raise ValueError('graphic band/element requires enabled elements and a nonempty pool')
        spec['layout']=dict(spec.get('layout',{}),graphic='none')
    if 'graphic_element' in meta:
        from elements import REGISTRY
        if meta['graphic_element'] not in REGISTRY:raise ValueError('Unknown meta.graphic_element')
        if spec.get('layout',{}).get('graphic')=='none':raise ValueError('graphic_element requires a graphic band')
        spec['layout']=dict(spec.get('layout',{}),graphic='band')
    if content.get('chart') and (spec.get('family') or meta.get('family','explainer'))!='explainer':raise ValueError('content.chart requires family explainer')
    if content.get('full_bleed_reason') and not content.get('image'):raise ValueError('Full bleed exception requires a supplied content image')
    if set(content.get('text_bleed',[]))-set(TEXT_ROLES):raise ValueError('Unknown text bleed role')
    if content.get('image'):
        if recipe not in ('auto','off','micro'):raise ValueError('A supplied image occupies the graphic region; use graphic_recipe auto or remove the recipe')
        raw=content['image'];raw=raw.get('path') if isinstance(raw,dict) else raw
        content['image']={'path':str(aio.input_path(raw,base_dir,'poster image'))}
    poster_canvas(spec.get('canvas'));layout_options(spec.get('layout'));choose_family(content,spec.get('family') or meta.get('family'),meta.get('seed',1))
    return spec

def decoration_plan(slide,result,meta,canvas,family,primary,secondary,seed):
    if not meta.get('elements',True):return []
    import poster_legacy_compose as compose
    items=[]
    audited={t['shape'].name:t for t in tm.audit(slide,mode='ink')}
    for role in result['roles']:
        pieces=[audited[n] for n in role['shapes'] if n in audited]
        if not pieces:continue
        rect=[min(t['rect'][0] for t in pieces),min(t['rect'][1] for t in pieces),
              max(t['rect'][2] for t in pieces),max(t['rect'][3] for t in pieces)]
        if any('riso-layer' in t['shape'].name for t in pieces):
            rect[1]=min(rect[1],min(t['shape'].top.pt for t in pieces))
            rect[3]=max(rect[3],max(t['shape'].top.pt+t['shape'].height.pt for t in pieces))
        items.append({'rect':rect,'text':role['text'],'size':role['size']})
    items.extend(compose.content_obstacles(slide,canvas))
    return compose.plan_page(family,primary,secondary,'poster',random.Random(seed*31+7),
                             items,canvas=canvas,exclusions=meta.get('exclude_elements',[]),
                             candidates=meta.get('element_pool'),graphic_rect=result['graphic_rect'],
                             graphic_element=meta.get('graphic_element'),graphic_recipe=meta.get('graphic_recipe','auto'))


def plan(spec,base_dir=None):
    spec=normalize(spec,base_dir)
    if 'art_direction' in spec:
        import poster_direction
        return {'spec':spec,'plan':poster_direction.make_plan(spec)}
    import poster_legacy_compose as compose
    meta=spec.get('meta',{});content=spec['content'];seed=meta.get('seed',1)
    canvas=poster_canvas(spec.get('canvas'))
    family,why=choose_family(content,spec.get('family') or meta.get('family'),seed)
    theme=rk.Theme(palette=meta.get('palette','G'),palette_hex=meta.get('palette_hex'),
                   print_grammar='none',lang=meta.get('lang','en'),fonts=meta.get('fonts'))
    theme.on_red=bool(meta.get('reverse'))
    # Real editable shapes in memory: identical font/anchor geometry to build,
    # without textures, files, directory creation or history writes.
    prs=rk.new_deck(canvas);slide=rk.add_page(prs,None)
    result=compose_poster(slide,content,theme,canvas,family,seed,
                          content.get('image',{}).get('path'),spec.get('layout'))
    forced=meta.get('dialect')
    if isinstance(forced,str):forced=[forced]
    primary,secondary,why_dialect=compose.pick_dialects(
        content['title']+' '+str(content.get('body','')),'poster',seed,compose.load_history(artifact='poster'),forced,
        self_key=('poster:'+content['title'],seed))
    decor=decoration_plan(slide,result,meta,canvas,family,primary,secondary,seed)
    placed=any(r.get('group')=='composition' for r in decor)
    if result['graphic_rect'] and not placed:
        if result['layout']['graphic']=='band':
            raise ValueError('graphic band geometry rejected its elements during plan: no legal placement within quiet/area limits. '
                             'Change graphic_position or use explainer for an information-led composition.')
        # Remove an unusable reservation and reflow before build. No empty band.
        effective=dict(spec.get('layout',{}),graphic='none')
        prs=rk.new_deck(canvas);slide=rk.add_page(prs,None)
        result=compose_poster(slide,content,theme,canvas,family,seed,
                              content.get('image',{}).get('path'),effective)
        result['graphic_reason']='automatic band rejected by placement limits; reflowed without empty band'
        decor=decoration_plan(slide,result,meta,canvas,family,primary,secondary,seed)
    import place_decor as pd
    import layout as lay
    items=[r['rect'] for r in tm.audit(slide,mode='ink')]
    quiet=pd.largest_quiet([lay.inflate(r,pd.TEXT_PAD) for r in items]+[r['rect'] for r in decor],canvas)[0]
    words=sum(pd.word_count(r['text']) for r in result['roles'])
    floor=pd.TEXT_TIERS[pd.tier_of(words)]['quiet']
    result.update(decoration_plan=decor,dialect={'primary':primary,'secondary':secondary,'chosen_by':why_dialect},
                  quiet={'share':quiet,'floor':floor,'status':'pass' if quiet>=floor else 'review'},
                  content_words=round(words,1))
    safe=canvas.safe
    content_roles=[r for r in result['roles'] if r['role'] not in ('footer','cta')]
    edge=max([r['rect'][3] for r in content_roles]+[safe[1]])
    if result.get('image_rect'):edge=max(edge,result['image_rect'][3])
    if result.get('graphic_rect'):edge=max(edge,result['graphic_rect'][3])
    last=max([r['rect'][3] for r in result['roles']]+[edge])
    result['content_extent']={'body_ratio':round((edge-safe[1])/(safe[3]-safe[1]),3),
                              'last_content_ratio':round((last-safe[1])/(safe[3]-safe[1]),3),
                              'trailing_blank_pt':round(max(0,safe[3]-last),1)}
    notes=[]
    recipe_members=[d for d in decor if d.get('recipe')]
    graphic_design={'requested':meta.get('graphic_recipe','auto'),
                    'recipe':recipe_members[0]['recipe'] if recipe_members else None,
                    'elements':[d['name'] for d in decor if d.get('group')=='composition'],
                    'status':'composed' if recipe_members else 'single-motif' if placed else 'image' if result.get('image_rect') else 'unillustrated'}
    result['graphic_design']=graphic_design
    if not result.get('image_rect') and not recipe_members and meta.get('elements',True):
        notes.append('Graphic craft review: '+('graphic:none disables the illustration region. ' if result['layout']['graphic']=='none' else '')+
                     'Consider a deck-library graphic_recipe with lead, pattern and detail. Rules, process boxes and paper grain do not replace this decision.')
    if result['content_extent']['body_ratio']<.8:
        notes.append('Review composition: body ends before 80% of the safe height; intentional quiet space is allowed.')
    if family=='explainer' and not (result.get('image_rect') or result.get('chart') or result.get('diagrams') or placed):
        notes.append('Review visual concept: rules and text alone remain. Reserve a graphic/image region or add a source-grounded diagram.')
    provenance=[]
    for i,row in enumerate(content.get('chart',{}).get('items',[])):
        record={k:row[k] for k in ('source','status','derivation') if k in row}
        record.update(index=i,status=row.get('status','unspecified'))
        provenance.append(record)
        if record['status']!='supplied':notes.append(f'Chart item {i}: {record["status"]} provenance; check the source and keep derivations/qualifiers visible.')
    result.update(review_notes=notes,chart_provenance=provenance)
    return {'spec':spec,'plan':{'family':family,'family_chosen_by':why,'canvas':canvas.to_dict(),
                              'brief':spec.get('brief',{}),'font_diagnostics':theme.font_diagnostics,
                              **result}}


def build(spec,out_path,base_dir=None):
    normalized=normalize(spec,base_dir)
    if 'art_direction' in normalized:
        import poster_direction
        return poster_direction.build(normalized,out_path)
    import poster_legacy_compose as compose
    planning=plan(spec,base_dir)
    spec=planning['spec']
    meta=spec.get('meta',{})
    content=spec['content']
    canvas=poster_canvas(spec.get('canvas'))
    seed=meta.get('seed',1)
    family,why_family=choose_family(content,spec.get('family') or meta.get('family'),seed)
    out=Path(out_path).resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    media=aio.paths(out)[2]
    media.mkdir(exist_ok=True)
    th=rk.Theme(palette=meta.get('palette','G'),palette_hex=meta.get('palette_hex'),
                print_grammar='none',lang=meta.get('lang','en'),fonts=meta.get('fonts'))
    title=str(content['title'])
    primary,secondary,why=(planning['plan']['dialect'][k] for k in ('primary','secondary','chosen_by'))
    colors=meta.get('palette_hex').split(',') if meta.get('palette_hex') else mt.PALETTES[th.palette]
    ctx=mt.Ctx(canvas.width,canvas.height,meta.get('scale',1.5),colors)
    # Grain only by default; decorative fields are optional and must stay clear
    # of the measured copy. No finished artwork is read to make this background.
    bg_spec={'paper_only':True,'registration_marks':False,
             'reverse':bool(meta.get('reverse',False))}
    th.on_red=bg_spec['reverse']
    bg,_=mt.render_page(ctx,bg_spec,seed,1)
    bg_path=media/'bg1.jpg'
    mt.save_img(bg,str(bg_path),'jpg',90)
    bg_blob=bg_path.read_bytes()
    manifest={'palette':th.palette,'tokens':th.t,'seed':seed,
              'page_size':f'{canvas.width}x{canvas.height}','scale':ctx.s,'format':'jpg',
              'total_bytes':len(bg_blob),'pages':[{'page':1,'file':'bg1.jpg',
                'reversed':th.on_red,'bytes':len(bg_blob),
                'sha256':hashlib.sha256(bg_blob).hexdigest()[:16],
                'spec':'paper','presets':[],**mt.ink_stats(bg,page_width=canvas.width)}]}
    (media/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    image_path=None
    image_record=None
    if content.get('image'):
        raw=content['image']
        raw=raw if isinstance(raw,dict) else {'path':raw}
        source=Path(raw['path']).expanduser()
        if not source.is_absolute():
            source=Path(base_dir or os.getcwd())/source
        source=source.resolve()
        image_path=str(media/'user-duotone.png')
        mt.cmd_duotone(argparse.Namespace(palette=None,colors=','.join(colors),seed=seed,
                         infile=str(source),max_dim=1600,cells=96,
                         out=image_path,format='png',quality=90))
        image_record={'treatment':'duotone_halftone',
                       'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                       'sha256':hashlib.sha256(Path(image_path).read_bytes()).hexdigest()}
    prs=rk.new_deck(canvas)
    slide=rk.add_page(prs,str(bg_path))
    slide.shapes[0].name='riso-paper[background]'
    result=compose_poster(slide,content,th,canvas,family,seed,image_path,planning['plan']['layout'])
    records=[]
    if meta.get('elements',True):
        decor_plan=planning['plan']['decoration_plan']
        records=compose.apply_plan(slide,decor_plan,th,str(media/'el'),seed=seed)
        expected_parts=[r for r in decor_plan if r.get('recipe')]
        rendered_parts=[r for r in records if r.get('recipe') and 'error' not in r]
        if len(rendered_parts)!=len(expected_parts):
            raise ValueError('Graphic recipe rendering failed; incomplete group is not a completed poster')
        if result['graphic_rect'] and not any(r.get('group')=='composition' and 'error' not in r for r in records):
            if result['layout']['graphic']=='band':
                raise ValueError('Required graphic band could not be populated; change element pool/position or reallocate content')
            print('Poster graphic unplaced: review the pool, quiet space and graphic position.',file=sys.stderr)
        for rec in records:
            rec['page']=1
    aio.save_pptx(prs,out)
    poster_policy={'family':family,'family_chosen_by':why_family,
                   'background_sha256':hashlib.sha256(bg_blob).hexdigest(),
                   'protagonist':result['protagonist'],'roles':result['roles'],
                   'text_bleed':content.get('text_bleed',[]),
                   'full_bleed_reason':content.get('full_bleed_reason'),
                   'images':[image_record] if image_record else [],
                   'reading_order':result['reading_order'],'role_demotions':result['role_demotions'],
                   'layout':result['layout'],'vertical_shift':result['vertical_shift'],
                   'diagrams':result['diagrams'],'brief':spec.get('brief',{}),
                   'capacity':result.get('capacity',{}),'chart':result.get('chart'),'quiet_plan':planning['plan']['quiet'],
                   'content_extent':planning['plan']['content_extent'],'review_notes':planning['plan']['review_notes'],
                   'chart_provenance':planning['plan']['chart_provenance'],
                   'graphic_design':planning['plan']['graphic_design'],
                   'graphic':{'region':result['graphic_rect'],'reason':planning['plan']['graphic_reason'],
                              'placed':any(r.get('group')=='composition' and 'error' not in r for r in records)}}
    style={'skill':'riso-slides','artifact':'poster','title':title,'canvas_spec':canvas.to_dict(),
           'scenario':'poster','seed':seed,'lang':th.lang,'fonts':th.fonts,'font_diagnostics':th.font_diagnostics,
           'palette':{'id':th.palette,'tokens':th.t},'print_grammar':'none',
           'grammar':{'header':'none','footer':'none','reg_marks':False},
           'dialect':{'primary':primary,'secondary':secondary,'chosen_by':why},
           'elements':records,'poster':poster_policy,'pages':[{'n':1,'family':family}],
           'calibrated_from_reference':meta.get('calibrated_from_reference',[]),
           'from_content':meta.get('from_content',[])}
    aio.write_style(out,style)
    aio.legacy_media_alias(out)
    compose.append_history(None,{'deck':'poster:'+title,'seed':seed,'artifact':'poster',
                                  'primary':primary,'secondary':secondary,'chosen_by':why}, artifact='poster')
    return str(out)


def main():
    ap=argparse.ArgumentParser(description='Riso poster builder: editable custom-size one-page PPTX')
    ap.add_argument('--spec')
    ap.add_argument('--out')
    ap.add_argument('--schema',action='store_true')
    ap.add_argument('--describe-spec',action='store_true')
    ap.add_argument('--plan',action='store_true')
    ap.add_argument('--summary',action='store_true',help='compact planning diagnostics; use with --plan (not a reusable spec)')
    ap.add_argument('--verbose',action='store_true')
    ap.add_argument('--render',action='store_true',help='export PNG/PDF when a renderer is available')
    args=ap.parse_args()
    if args.summary and not args.plan:ap.error('--summary requires --plan')
    if args.schema:
        print(json.dumps(SCHEMA,indent=2))
        return 0
    if args.describe_spec:
        print(json.dumps(describe_spec(),ensure_ascii=False,indent=2))
        return 0
    if not args.spec or (not args.out and not args.plan):
        ap.error('--spec and --out are required for build; --plan requires only --spec')
    if args.plan:
        result=plan(json.loads(Path(args.spec).read_text(encoding='utf-8')),Path(args.spec).resolve().parent)
        if args.summary:
            p=result['plan']
            if p.get('version') in ('3.3','3.4','3.5','3.6'):
                print(json.dumps({k:v for k,v in p.items() if k not in ('objects','content_roles')},ensure_ascii=False,indent=2))
                return 0
            result={k:p[k] for k in ('family','canvas','font_diagnostics','layout','graphic_rect','graphic_reason','protagonist','quiet','content_words')}
            result['capacity']=p.get('capacity',{})
            result['canvas']={k:p['canvas'][k] for k in ('width','height')}
            result['decoration']=[d['name'] for d in p['decoration_plan']]
            result['type_sizes']={role:sorted(set(round(r['size'],1) for r in p['roles'] if r['role']==role)) for role in dict.fromkeys(r['role'] for r in p['roles'])}
            for k in ('content_extent','review_notes','chart_provenance','graphic_design'):result[k]=p[k]
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    path=build(json.loads(Path(args.spec).read_text(encoding='utf-8')),args.out,
               Path(args.spec).resolve().parent)
    print(f'saved: {path}')
    if args.render:
        import subprocess
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),
                               '--deck',path,'--out',str(Path(path).with_suffix(''))+'-preview','--keep-pdf'])
        if result.returncode:
            print('PPTX built; PNG/PDF export unavailable or failed. See renderer output.')
    return 0


if __name__=='__main__':
    sys.exit(main())

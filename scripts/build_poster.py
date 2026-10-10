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
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))

import compose
from canvas import poster_canvas, POSTER_PRESETS
import make_textures as mt
from poster_layouts import choose_family, compose_poster, FAMILIES, TEXT_ROLES
import riso_kit as rk
import textmetrics as tm
import artifact_io as aio
from poster_layouts import layout_options


SCHEMA={'artifact':'poster','canvas':{'preset':'a3_portrait'},
        'family':'type_led','meta':{'lang':'en','palette':'G','seed':1,'elements':True},
        'layout':{'columns':'auto','structure':'rules','alignment':'l',
                  'footer_anchor':'content','vertical_alignment':'balanced'},
        'content':{'title':'YOUR SUPPLIED TITLE'}}


def normalize(spec,base_dir=None):
    if not isinstance(spec,dict):raise ValueError('Poster spec must be a JSON object')
    if 'spec' in spec:
        extra=set(spec)-{'spec','plan','families','text_roles','canvas_presets'}
        if extra:raise ValueError(f'Unknown poster envelope fields: {sorted(extra)}')
        spec=spec['spec']
    import copy
    spec=copy.deepcopy(spec)
    unknown=set(spec)-{'artifact','canvas','family','meta','content','layout','brief'}
    if unknown:raise ValueError(f'Unknown poster fields: {sorted(unknown)}')
    if spec.get('artifact','poster')!='poster':raise ValueError('Use build_deck.py for deck artifacts')
    meta=spec.get('meta',{})
    if not isinstance(meta,dict):raise ValueError('meta must be an object')
    if 'layout' in spec and not isinstance(spec['layout'],dict):raise ValueError('layout must be an object')
    forbidden={'chrome','header_left','header_right','footer','total'} & set(meta)
    if forbidden or meta.get('print_grammar','none')!='none':
        raise ValueError(f'Poster must not use deck chrome: {sorted(forbidden)}')
    unknown=set(meta)-{'lang','palette','palette_hex','seed','dialect','elements','fonts','scale','reverse',
                       'family','print_grammar','calibrated_from_reference','from_content','exclude_elements','element_pool','graphic_element'}
    if unknown:raise ValueError(f'Unknown poster meta fields: {sorted(unknown)}')
    if 'elements' in meta and not isinstance(meta['elements'],bool):
        raise ValueError('meta.elements must be boolean')
    forced=meta.get('dialect')
    if forced is not None:
        forced=[forced] if isinstance(forced,str) else forced
        if not isinstance(forced,list) or not 1<=len(forced)<=2 or any(d not in compose.DIALECTS for d in forced):
            raise ValueError('meta.dialect must name one or two dialects A-F')
    if not meta.get('elements',True) or meta.get('element_pool')==[]:
        if spec.get('layout',{}).get('graphic')=='band' or meta.get('graphic_element'):
            raise ValueError('graphic band/element requires enabled elements and a nonempty pool')
        spec['layout']=dict(spec.get('layout',{}),graphic='none')
    if 'graphic_element' in meta:
        if not isinstance(meta['graphic_element'],str) or meta['graphic_element'] not in compose.E.REGISTRY:
            raise ValueError('Unknown meta.graphic_element')
        if spec.get('layout',{}).get('graphic')=='none':
            raise ValueError('graphic_element requires a graphic band')
        spec['layout']=dict(spec.get('layout',{}),graphic='band')
    content=spec.get('content',{})
    if not isinstance(content,dict) or not isinstance(content.get('title'),str) or not content['title'].strip():
        raise ValueError('Poster requires a supplied text title; never invent content')
    known={'title','subtitle','body','blocks','date','venue','metadata','cta','key_number','quote',
           'attribution','image','footer','data','text_bleed','full_bleed_reason','comparison','process'}
    if set(content)-known:raise ValueError(f'Unknown poster content roles: {sorted(set(content)-known)}')
    for key in ('blocks','data','comparison','process','text_bleed'):
        if key in content and not isinstance(content[key],list):raise ValueError(f'content.{key} must be a list')
    for i,block in enumerate(content.get('blocks',[])):
        if not isinstance(block,(str,dict)):raise ValueError(f'content.blocks[{i}] must be text or an object')
        if isinstance(block,dict) and set(block)-{'title','text'}:raise ValueError(f'Unknown content.blocks[{i}] fields')
    for i,row in enumerate(content.get('data',[])):
        if not isinstance(row,dict) or set(row)-{'label','value'}:raise ValueError(f'Invalid content.data[{i}] fields')
    for key in ('comparison','process'):
        for i,row in enumerate(content.get(key,[])):
            if not isinstance(row,(str,dict)) or isinstance(row,dict) and set(row)-{'label','text'}:
                raise ValueError(f'Invalid content.{key}[{i}] fields')
    for key,fields in (('quote',{'text','attribution'}),('key_number',{'value','label'}),('image',{'path'})):
        if isinstance(content.get(key),dict) and set(content[key])-fields:raise ValueError(f'Unknown content.{key} fields')
    if content.get('full_bleed_reason') and not content.get('image'):
        raise ValueError('Full bleed exception requires a supplied content image')
    if set(content.get('text_bleed',[]))-set(TEXT_ROLES):raise ValueError('Unknown text bleed role')
    if content.get('image'):
        raw=content['image'];raw=raw.get('path') if isinstance(raw,dict) else raw
        if not isinstance(raw,str):raise ValueError('content.image.path must be a file path')
        content['image']={'path':str(aio.input_path(raw,base_dir,'poster image'))}
    if 'brief' in spec:
        if not isinstance(spec['brief'],dict):raise ValueError('brief must contain provided constraints and sources')
        extra=set(spec['brief'])-{'purpose','viewing_distance','audience','constraints','sources'}
        if extra:raise ValueError(f'Unknown brief fields: {sorted(extra)}')
    poster_canvas(spec.get('canvas'))
    layout_options(spec.get('layout'))
    choose_family(content,spec.get('family') or meta.get('family'),meta.get('seed',1))
    return spec


def plan(spec,base_dir=None):
    spec=normalize(spec,base_dir)
    meta=spec.get('meta',{});content=spec['content'];seed=meta.get('seed',1)
    canvas=poster_canvas(spec.get('canvas'))
    family,why=choose_family(content,spec.get('family') or meta.get('family'),seed)
    theme=rk.Theme(palette=meta.get('palette','G'),palette_hex=meta.get('palette_hex'),
                   print_grammar='none',lang=meta.get('lang','en'),fonts=meta.get('fonts'))
    theme.on_red=bool(meta.get('reverse'))
    result=compose_poster(None,content,theme,canvas,family,seed,
                          content.get('image',{}).get('path'),spec.get('layout'))
    return {'spec':spec,'plan':{'family':family,'family_chosen_by':why,'canvas':canvas.to_dict(),
                              'brief':spec.get('brief',{}),'font_diagnostics':theme.font_diagnostics,
                              **result}}


def build(spec,out_path,base_dir=None):
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
    forced=meta.get('dialect')
    if isinstance(forced,str):
        forced=[forced]
    history=compose.load_history()
    title=str(content['title'])
    primary,secondary,why=compose.pick_dialects(
        title+' '+str(content.get('body','')),'poster',seed,history,forced,
        self_key=('poster:'+title,seed))
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
    result=compose_poster(slide,content,th,canvas,family,seed,image_path,spec.get('layout'))
    records=[]
    if meta.get('elements',True):
        items=[]
        audited={t['shape'].name:t for t in tm.audit(slide,mode='ink')}
        for role in result['roles']:
            pieces=[audited[n] for n in role['shapes'] if n in audited]
            if not pieces:continue
            rect=[min(t['rect'][0] for t in pieces),min(t['rect'][1] for t in pieces),
                  max(t['rect'][2] for t in pieces),max(t['rect'][3] for t in pieces)]
            # A multiline display is one anchor, including both print layers.
            # Reserve its line frames too: renderer baselines can differ from
            # FreeType ink bounds, so accents must not sit inside display lines.
            if any('riso-layer' in t['shape'].name for t in pieces):
                rect[1]=min(rect[1],min(t['shape'].top.pt for t in pieces))
                rect[3]=max(rect[3],max(t['shape'].top.pt+t['shape'].height.pt for t in pieces))
            items.append({'rect':rect,'text':role['text'],'size':role['size']})
        if result['image_rect']:
            items.append({'rect':result['image_rect'],'text':'','size':0})
        for diagram in result['diagrams']:
            items.extend({'rect':node,'text':'','size':0} for node in diagram['nodes'])
        decor_plan=compose.plan_page(family,primary,secondary,'poster',random.Random(seed*31+7),
                               items,canvas=canvas,exclusions=meta.get('exclude_elements',[]),candidates=meta.get('element_pool'),
                               graphic_rect=result['graphic_rect'],graphic_element=meta.get('graphic_element'))
        records=compose.apply_plan(slide,decor_plan,th,str(media/'el'),seed=seed)
        if result['graphic_rect'] and not any(r.get('group')=='composition' and 'error' not in r for r in records):
            if result['layout']['graphic']=='band':
                raise ValueError('Required graphic band could not be populated; change element pool/position or reallocate content')
            print('Poster graphic unplaced: review the pool, quiet space and graphic position.',file=sys.stderr)
        for rec in records:
            rec['page']=1
    prs.save(str(out))
    aio.canonical_pptx(out)
    poster_policy={'family':family,'family_chosen_by':why_family,
                   'background_sha256':hashlib.sha256(bg_blob).hexdigest(),
                   'protagonist':result['protagonist'],'roles':result['roles'],
                   'text_bleed':content.get('text_bleed',[]),
                   'full_bleed_reason':content.get('full_bleed_reason'),
                   'images':[image_record] if image_record else [],
                   'reading_order':result['reading_order'],'role_demotions':result['role_demotions'],
                   'layout':result['layout'],'vertical_shift':result['vertical_shift'],
                   'diagrams':result['diagrams'],'brief':spec.get('brief',{}),
                   'graphic':{'region':result['graphic_rect'],'reason':result['graphic_reason'],
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
                                  'primary':primary,'secondary':secondary,'chosen_by':why})
    return str(out)


def main():
    ap=argparse.ArgumentParser(description='Riso poster builder: editable custom-size one-page PPTX')
    ap.add_argument('--spec')
    ap.add_argument('--out')
    ap.add_argument('--schema',action='store_true')
    ap.add_argument('--describe-spec',action='store_true')
    ap.add_argument('--plan',action='store_true')
    ap.add_argument('--summary',action='store_true',help='compact planning diagnostics; use with --plan (not a reusable spec)')
    ap.add_argument('--render',action='store_true',help='export PNG/PDF when a renderer is available')
    args=ap.parse_args()
    if args.summary and not args.plan:ap.error('--summary requires --plan')
    if args.schema:
        print(json.dumps(SCHEMA,indent=2))
        return 0
    if args.describe_spec:
        print(json.dumps({'example':SCHEMA,'families':FAMILIES,'text_roles':TEXT_ROLES,
                          'canvas_presets':POSTER_PRESETS,'layout':layout_options(),
                          'optional_top_level':['brief'],'optional_content':['blocks','comparison','process','image','quote','key_number'],
                          'asset_paths':'relative to spec file','plan':'reusable spec/plan envelope; no output or state writes'},indent=2))
        return 0
    if not args.spec or (not args.out and not args.plan):
        ap.error('--spec and --out are required for build; --plan requires only --spec')
    if args.plan:
        result=plan(json.loads(Path(args.spec).read_text(encoding='utf-8')),Path(args.spec).resolve().parent)
        if args.summary:
            p=result['plan']
            result={k:p[k] for k in ('family','canvas','font_diagnostics','layout','graphic_rect','graphic_reason','protagonist')}
            result['roles']=[{k:r[k] for k in ('role','size','rect')} for r in p['roles']]
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

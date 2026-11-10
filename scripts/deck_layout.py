"""Deck-only composition. Forked from v4.0; poster planner is intentionally unchanged."""
import copy
import math
import itertools
from collections import Counter
import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import CanvasSpec
from native_vectors import bounds
from glyphs import glyph,circle
from deck_content_plan import choose_form, digest, inventory, text, words
from deck_marks import title_rule
from deck_evidence_forms import FORMS
from deck_scale import scale

INKS = {
    'cobalt-vermilion': {'main':['25488A','CA553D'],'accent':'F2BD4C','paper':'F5EEDD','body':'20252D'},
    'plum-ochre': {'main':['65385C','AA7135'],'accent':'C6D958','paper':'F4EEE4','body':'29232A'},
    'teal-coral': {'main':['166267','B94E61'],'accent':'EECF62','paper':'F0EFE1','body':'172E31'},
}

def make_plan(spec,_vertical_pass=False):
    c=spec['content'];a=spec.get('art_direction',{});meta=spec.get('meta',{})
    canvas=CanvasSpec(**spec.get('canvas', {}));x,y,x1,y1=canvas.safe;w=x1-x;H=canvas.height
    width_fraction = a.get('content_width')
    if width_fraction is not None and (type(width_fraction) not in (int, float)
                                      or not .45 <= width_fraction <= 1):
        raise ValueError('content_width must be a fraction from .45 to 1')
    ink=copy.deepcopy(INKS[a.get('ink','cobalt-vermilion')]);ink['name']=a.get('ink','cobalt-vermilion')
    dialect=a.get('dialect','swiss');dialect='swiss' if dialect=='auto' else dialect
    theme=rk.Theme(palette='A',lang=meta.get('lang','en'),fonts=meta.get('fonts'))
    modules=sorted(copy.deepcopy(c.get('modules',[])),key=lambda m:m.get('order',0))
    from source_profile import profile
    evidence=copy.deepcopy(spec.get('evidence',{}))
    if not evidence:
        evidence=dict(profile=profile(inventory({'content':c})),legacy=True)
    evidence.setdefault('level',evidence['profile']['data_density']);policy=scale(evidence['level'],dialect)
    for module in modules:module.setdefault('visual',choose_form(module,evidence['profile']))
    body=max(18,a.get('body_size',20));gap=a.get('_gap',16)
    p=dict(version='3.8',mode='infographic',source_sha256=digest(c),content_roles=[],archetype='information-bands',
           selection_reason='Stage 0 information types and weights',dialect=dialect,looseness=0,
           skeleton='bands',seed=meta.get('seed',1),canvas=canvas.to_dict(),fonts=theme.fonts,
           font_diagnostics=theme.font_diagnostics,ink_plan=ink,objects=[],overlaps=[],regions=[],micro_layer=[],
           content_words=sum(words(text(m)) for m in modules if not (m.get('level')==1 and (m.get('role')=='title' or text(m)==c['title'])))+words(c['title']),density='medium',columns=2,
           scale_ladder=dict(body=body,detail=16),hero=dict(kind='statistic',object_ids=[],share=0),
           constraints=dict(body_min=18,decor_cap=.12,accent_cap=.18,max_nonstructural_repeat=3,max_edge_void=.14),
           contract_warnings=[],revision=0,review_changes=[],tiers={},preflight=dict(fields=len(modules),words=0),
           intentional_voids=[],parallel_sets=[],reading_order=[],review_notes=[],
           graphic_design=dict(recipe='info-type',status='composed',meaning='Source-driven editable evidence'),
           autofit=dict(enabled=True,attempts=[],changes=[],source_changed=False),effective_controls={},
           content_plan=spec.get('content_plan',{}),module_metrics=[])
    p['evidence']=evidence;p['evidence_policy']=policy
    p['editorial_lists'] = bool(a.get('_editorial'))
    objs=p['objects']
    def put(oid,value,xx,yy,width,size,source=None,role='argument',bold=False,color=None,tidy_rag=False):
        value=str(value)
        if not value.strip():return None
        font=theme.f_heading if bold else theme.f_body
        plates = a.get('type_plates') if oid == 'title' else None
        offset = 0
        if plates and plates != 'off':
            from deck_ink_render import allowance
            offset = allowance(theme, size, plates)
        if oid == 'title' and a.get('_editorial'):
            from deck_title_fit import fit as fit_title
            from deck_ink_render import allowance
            f = fit_title(value, font, size, width, min(144, H * .28),
                          minimum=min(35, size), ls=1.08,
                          offset=(lambda chosen: allowance(theme, chosen, plates)) if offset else 0,
                          keep_phrases=a.get('title_keep_phrases', ()))
        else:
            f=tf.fit(value,font,size,width,H*3,minimum=size,bold=bold,ls=1.08,offset=offset)
        if tidy_rag and len(f.lines) == 2 and '\n' not in value and len(f.lines[-1].split()) == 1:
            from dataclasses import replace
            from deck_title_wrap import choose_title_lines
            measure = lambda line: tm.advance(line, font, f.size, bold)
            usable = (width - rk.NO_WRAP['pad_pt']) / rk.NO_WRAP['slack']
            lines = choose_title_lines(value, 2, measure, usable)
            if lines and len(lines) == 2 and len(lines[-1].split()) > 1:
                f = replace(f, lines=tuple(lines), width=max(map(measure, lines)))
        ob=dict(id=oid,kind='text',text=value,source=source,role=role,rect=[xx,yy,xx+width,yy+f.height],
                fit=f.to_dict(),color=color or ink['body'],background=ink['paper'],rotation=0)
        if offset:
            ob['type_plates'] = plates
        objs.append(ob)
        if source:p['content_roles'].append(dict(id=source,source=source,text=value,role=role))
        return ob
    def rect(oid,r,color,role='data',**extra):
        ob=dict(id=oid,kind='rect',rect=r,fill=color,role=role,rotation=0,**extra);objs.append(ob);return ob
    def path(oid,paths,color=ink['main'][1],role='relation',**extra):
        ob=dict(id=oid,kind='path',paths=paths,rect=bounds(paths,1),line=color,line_width=1.8,role=role,rotation=0,**extra)
        objs.append(ob);return ob
    def node(mid,members,r,band=1,col=0):
        members=[o for o in members if o and o['kind']=='text']
        if not members:return
        p['regions'].append(dict(id=mid,rect=r,objects=[o['id'] for o in members],column=col))
        p['reading_order'].append(dict(order=len(p['reading_order'])+1,region=mid,objects=[o['id'] for o in members],band=band,column=col,x=members[0]['rect'][0]))
    title_size = a.get('title_size', 56)
    comparison = any(m.get('visual') in ('before-after', 'versus', 'contrast-pair') for m in modules)
    if meta.get('lang') == 'en' and comparison and title_size == 44:
        try:
            title_size = tf.fit(c['title'], theme.f_heading, title_size, w, 62,
                                minimum=35, bold=True, ls=1.08).size
        except ValueError:
            pass
    title=put('title',c['title'],x,y,w,title_size,'title','hook',True,ink['main'][0])
    node('title',[title],title['rect'],0)
    focal = meta.get('lang') == 'en' and len(modules) == 1 and modules[0].get('visual') in (
        'key-statement', 'pull-quote', 'text', 'icon-bullet')
    cy=title['rect'][3]+25
    # Safe full-line rule outside the glyph envelope, never across uppercase letters.
    if a.get('title_rule', True):
        objs.append(title_rule(title, cy-8, ink['accent']))
    mains=[(i,m) for i,m in enumerate(modules) if m.get('level')!=4 and not (m.get('level')==1 and (m.get('role')=='title' or text(m)==c['title']))]
    foot=[(i,m) for i,m in enumerate(modules) if m.get('level')==4]
    # Semantic groups are indivisible bands. Process/timeline and high-weight heroes
    # receive full width; unrelated small modules share a row in source order.
    rows=[];pending=[];columns=a.get('columns',1 if evidence['level']<.5 and not evidence.get('legacy') else 2)
    # A primary chart and a short, source-bound companion can share an
    # editorial spread. Other combinations retain the ordinary band packing.
    from deck_press_chart import PRESS_FORMS
    press_spread = (a.get('_press_chart') and not a.get('_press_bands') and columns >= 2 and len(mains) == 2
                    and mains[0][1]['visual'] in PRESS_FORMS
                    and mains[1][1]['visual'] in ('text', 'summary-box', 'stat-tile', 'key-statement')
                    and not any(m.get('keep_together') for _, m in mains))
    for i,m in mains:
        full=m.get('visual') in ('step-flow','timeline','bar-compare','bar-vertical','line-chart','before-after','versus','stamp') or m.get('level')==1 or m.get('weight',1)>=1.5
        if full:
            if pending:rows.append(pending);pending=[]
            rows.append([(i,m)])
        else:
            pending.append((i,m))
    if pending:rows.append(pending)
    if press_spread:
        rows = [mains]
    footer_height=sum(tf.fit(text(m),theme.f_body,16,w-20,H,minimum=16,ls=1.08).height+12 for _,m in foot)+16 if foot else 0
    available=y1-cy-footer_height-gap
    list_candidates = [m for _, m in mains if m['visual'] == 'takeaway-list'
                       and len(m.get('visual_data', {}).get('items', [])) >= 2]
    paper_mode = a.get('_paper_mode', 'off')
    paper_module = (max(list_candidates, key=lambda m: len(m['visual_data']['items']))['id']
                    if paper_mode != 'off' and list_candidates else None)
    # Measured row minima, content-driven area allocation; never shrink body.
    def render_module(index,m,rx,ry,rw,rh,band,col):
        from deck_evidence_forms import render_module as render_evidence
        return render_evidence(index,m,[rx,ry,rx+rw,ry+rh],
            dict(plan=p,put=put,rect=rect,path=path,node=node,theme=theme,heading_size=a.get('heading_size',25 if evidence.get('legacy') else max(26,body*1.3)),bar_thickness=18 if evidence.get('legacy') else max(24,min(48,body*(1+policy['level']))),chart_height=min(180,available*.38),focal=focal,english=meta.get('lang') == 'en',
                 editorial_lists=a.get('_editorial', False), list_order=a.get('list_order', 'unordered'),
                 list_layout=a.get('list_layout', 'auto'),
                 paper_layout=a.get('paper_layout', 'auto'),
                 cut_paper=a.get('_cut_paper', False), press_chart=a.get('_press_chart', False),
                 press_side_legend=not a.get('_press_bands', False),
                 inline_quote=a.get('_inline_quote', False),
                 paper_panel=m['id'] == paper_module and rw >= (310 if paper_mode == 'on' else 495)),band,col)
    # Measure each row using the exact component writer, then discard the probe.
    # Extra page height stays in the exterior margin instead of giant interior holes.
    rowheight=[];rowpacks=[]
    for row in rows:
        checkpoint={key:copy.deepcopy(p[key]) for key in ('objects','content_roles','regions','reading_order','module_metrics','hero','overlaps')}
        ncols=min(columns,len(row));heights=[]
        band_width = w * (width_fraction if width_fraction is not None else .72 if focal else 1)
        rw = (band_width - gap*(ncols-1)) / ncols
        widths = [(band_width-gap)*.62, (band_width-gap)*.38] if press_spread else [rw]*ncols
        starts = [x+sum(widths[:col])+col*gap for col in range(ncols)]
        for col,(index,m) in enumerate(row):
            probe_x = starts[col] if press_spread else x+col*(rw+gap)
            probe_width = widths[col] if press_spread else rw
            start=len(objs);render_module(index,m,probe_x,0,probe_width,H*4,1,col)
            used=[o['rect'][3] for o in objs[start:] if not o.get('micro')]
            staggered = len(p['module_metrics'][-1].get('paper_panels', ())) > 1
            heights.append(max(used, default=0) + (10 if staggered else 18))
        for key,value in checkpoint.items():p[key]=value
        objs=p['objects']
        candidates=[]
        for cuts in itertools.combinations(range(1,len(row)),ncols-1):
            # Deck groups stay on the same slide; explicit column locks still win.
            if any(row[cut-1][1].get('keep_together') and row[cut-1][1].get('group')
                   and row[cut-1][1].get('group') == row[cut][1].get('group') for cut in cuts):
                continue
            breaks=(0,*cuts,len(row))
            stacks=[list(range(breaks[j],breaks[j+1])) for j in range(ncols)]
            totals=[sum(heights[k] for k in stack)+gap*max(0,len(stack)-1) for stack in stacks]
            candidates.append((max(totals),max(totals)-min(totals),stacks))
        if not candidates:
            if columns>1:
                alternate=copy.deepcopy(spec);alternate.setdefault('art_direction',{})['columns']=columns-1
                retry=make_plan(alternate)
                retry['autofit']['changes'].append('Reduced columns to keep a semantic group together')
                return retry
            raise ValueError('Cannot keep grouped modules together in this width')
        required,_,stacks=min(candidates,key=lambda q:(q[0],q[1]))
        rowheight.append(required);rowpacks.append((stacks,heights,starts,widths))
    needed=sum(rowheight)+gap*max(0,len(rows)-1)
    if needed>available:
        raise ValueError(f'Slide evidence needs {needed:.1f}pt; available {available:.1f}pt at {body}pt body; row heights {[round(v,1) for v in rowheight]}. Change columns, grouping or approved copy.')
    if not _vertical_pass and not evidence.get('legacy') and a.get('autofit',True) and available-needed>80 and body<policy['body_max']:
        candidate=copy.deepcopy(spec);ca=candidate.setdefault('art_direction',{})
        factor=min(policy['body_max']/body,max(1,available/max(1,needed)))
        ca['body_size']=round(body*factor*2)/2
        ca['title_size']=min(max(56,a.get('title_size',44)),round(a.get('title_size',44)*factor))
        ca['_gap']=gap
        for trial in range(round(ca['body_size']*2),round(body*2),-1):
            ca['body_size']=trial/2
            try:
                retry=make_plan(candidate,True)
                retry['autofit']['changes'].append(f'Vertical adaptation: body {body:g}->{ca["body_size"]:g}pt; title ->{ca["title_size"]}pt; gap ->{ca["_gap"]}pt, source unchanged')
                return retry
            except ValueError:continue
        p['autofit']['changes'].append('Vertical enlargement exceeded measured capacity; retained original readable sizes')
    # Bounded spacing consumes only a small part of surplus; never stretches
    # short text into giant empty cards or invents copy to occupy the page.
    if rows:
        extra=min(16,max(0,(available-needed)/max(1,len(rows)-1))) if len(rows)>1 else 0
        gap+=extra
        if extra:p['autofit']['changes'].append(f'Increased inter-row spacing by {extra:.1f}pt (bounded)')
    alignment = a.get('vertical_align', 'balanced')
    if alignment not in ('top', 'balanced', 'center', 'bottom'):
        raise ValueError('vertical_align must be top, balanced, center or bottom')
    # Work from measured content, so explicit positioning never erases copy.
    slack = max(0, available - needed - max(0, len(rows)-1) * extra) if rows else 0
    if alignment == 'center' or (alignment == 'balanced' and focal):cy += slack * .42
    elif alignment == 'bottom':cy += slack
    elif alignment == 'balanced' and len(mains) > 1 and len(rows) == 1:
        cy += min(64, slack * .25)
    for row_index,(row,rh,packed) in enumerate(zip(rows,rowheight,rowpacks)):
        stacks,heights,starts,widths=packed
        for col,stack in enumerate(stacks):
            local_y=cy
            for k in stack:
                index,m=row[k]
                xx = starts[col] if press_spread else x+col*(widths[col]+gap)
                render_module(index,m,xx,local_y,widths[col],heights[k],row_index+1,col)
                local_y+=heights[k]+gap
        cy+=rh+gap
    foot_y=max(cy+8,y1-footer_height+8) if foot else cy+8
    for index,m in foot:
        label=text(m)
        ob=put(m['id'],label,x+10,foot_y,w-20,16,f'modules.{index}.footer','meta')
        path(m['id']+'-ticket',[[[x,foot_y],[x,ob['rect'][3]+4],[x1,ob['rect'][3]+4]]],role='structure',anchor=m['id'])
        node(m['id'],[ob],[x,foot_y,x1,ob['rect'][3]+8],len(rows)+2)
        foot_y=ob['rect'][3]+12
    p['reading_graph']=dict(node_ids=[n['region'] for n in p['reading_order']],edges=[[u['region'],v['region']] for u,v in zip(p['reading_order'],p['reading_order'][1:])])
    known={o['id'] for o in objs}
    for o in objs:
        if o.get('anchor') and o['anchor'] not in known:o['anchor']='title'
    p['hero']['share']=sum((o['rect'][3]-o['rect'][1])*(o['rect'][2]-o['rect'][0]) for o in objs if o['id'] in p['hero']['object_ids'])/canvas.area
    p['scale_ladder']['actual']=sorted({o['fit']['size'] for o in objs if o['kind']=='text'},reverse=True)
    p['capacity']=dict(columns=[dict(column=1,height=foot_y-y,measured=foot_y-y,available=y1-y,words=p['content_words'])])
    p['content_extent']=dict(top=title['rect'][3],bottom=cy,footer_edge=foot_y)
    p['voids']=[];p['coordination']=dict(fails=[])
    p['effective_controls']={k:dict(requested=a.get(k,'auto'),effective=v) for k,v in [('body_size',body),('skeleton','bands'),('columns',columns),('dialect',dialect)]}
    p['composition_signature']=digest([dict(id=o['id'],rect=o['rect']) for o in objs])
    p['preflight'].update(words=p['content_words'])
    p['infographic_metrics']=assess(p)
    from deck_material import signature
    p['infographic_metrics']['dialect_signature']=signature(p)
    if p['infographic_metrics']['edge_void']['fails']:
        p['autofit']['changes'].append('Source remains too short for this canvas: consider a smaller format or supply additional source content; no automatic copy expansion')
    p['coordination']['fails']=p['infographic_metrics']['fails']
    return p

def union_area(rects):
    xs=sorted({r[i] for r in rects for i in (0,2)});area=0
    for x,x1 in zip(xs,xs[1:]):
        intervals=sorted((r[1],r[3]) for r in rects if r[0]<x1 and r[2]>x)
        end=-math.inf
        for y,y1 in intervals:
            area+=(x1-x)*max(0,y1-max(y,end));end=max(end,y1)
    return area

def assess(p):
    objects=p['objects'];page=p['canvas']['width']*p['canvas']['height'];body=p['scale_ladder']['body']
    # Bounds union is an explicitly named proxy, not filled-pixel coverage.
    visual=[o['rect'] for o in objects if o['kind']!='text' and o['role'] in ('data','relation') and not o.get('micro')]
    modules=[m for m in p.get('module_metrics',[]) if m['level']==2]
    metadata=[o for o in objects if o['kind']=='text' and o['role']=='meta']
    stats=[o['fit']['size']/body for o in objects if o['kind']=='text' and o.get('stat_tile')]
    levels=len({round(o['fit']['size']/5)*5 for o in objects if o['kind']=='text'})
    fails=[];warnings=[]
    plain_list = (p.get('editorial_lists') and len(modules) == 1
                  and modules[0]['visual'] == 'takeaway-list')
    if levels < (2 if plain_list else 3):
        fails.append('list requires a distinct title and body' if plain_list
                     else 'hierarchy requires at least 3 type levels')
    if body<18:fails.append('infographic body below 18pt')
    if stats and min(stats)<4:fails.append('stat tile numerals must be at least 4x body')
    metadata_weight=union_area([o['rect'] for o in metadata])/page
    if metadata_weight>.12:warnings.append('Metadata occupies over 12% of page; condense only in adapt mode or choose a larger canvas')
    ratio=union_area(visual)/page
    policy=p.get('evidence_policy',scale(p.get('evidence',{}).get('level',0)))
    if not policy['presence_target'][0]<=ratio<=policy['presence_target'][1]:warnings.append(f'evidence_presence bounds={ratio:.3f} outside calibrated {policy["presence_target"]}')
    text_only=sum(m['text_only'] for m in modules)/max(1,len(modules))
    if text_only>policy['text_fraction'] and not p.get('evidence',{}).get('legacy'):fails.append('text-only module ratio exceeds evidence-scaled allowance')
    edge=edge_void(p)
    (warnings if p.get('version')!='3.8' or p.get('evidence',{}).get('legacy') else fails).extend(edge['fails'])
    return dict(visual_area_ratio=round(ratio,4),evidence_presence=dict(bounds_proxy=round(ratio,4),target=policy['presence_target'],raster_ink=None),evidence_level=policy['level'],visual_area_method='union of semantic non-text object bounds; excludes substrate, card backs and garnish; not ink pixels',
                text_only_module_ratio=text_only,hierarchy_levels=levels,stat_numeral_ratio=stats,
                metadata_weight=round(metadata_weight,4),
                edge_void=edge,fails=fails,warnings=warnings)

def edge_void(p):
    W=p['canvas']['width'];H=p['canvas']['height'];rects=[];body_rects=[]
    for o in p['objects']:
        if o.get('micro') or o.get('duplicate_of') or o.get('layer')=='surface':continue
        if o['kind']=='text':
            r=list(o['rect']);r[2]=r[0]+min(r[2]-r[0],o['fit']['width']);rects.append(r)
            if o.get('role') not in ('meta','navigation'):body_rects.append(r)
        elif o.get('role') in ('data','relation'):rects.append(o['rect']);body_rects.append(o['rect'])
    if not rects:return dict(fails=['edge_void: no source content'],bottom_unused=1)
    edges=dict(left=min(r[0] for r in rects)/W,top=min(r[1] for r in rects)/H,right=(W-max(r[2] for r in rects))/W,bottom=(H-max(r[3] for r in rects))/H)
    bottom=max(0,(p['canvas']['safe'][3]-max((r[3] for r in body_rects),default=0))/H)
    limit=p.get('evidence_policy',scale(0))['edge_limit'];fails=[]
    for k,v in edges.items():
        if v>limit:fails.append(f'edge_void: {k} {v:.3f} exceeds {limit:.3f}')
    if bottom>limit:fails.append(f'edge_void: continuous unused lower content interval {bottom:.3f} exceeds {limit:.3f}')
    return dict(**edges,bottom_unused=bottom,limit=limit,fails=fails,method='source text visible width and semantic forms; substrate/garnish excluded; footer cannot hide lower content void')

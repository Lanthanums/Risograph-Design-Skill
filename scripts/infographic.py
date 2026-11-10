"""Source-driven native infographic composition, also usable by deck pages."""
import copy
import math
import itertools
from collections import Counter
import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import poster_canvas
from poster_primitives import bounds
from glyphs import glyph,circle
from content_plan import words,text,leafs,VISUALS
from evidence_forms import FORMS
from evidence_scale import scale

def make_plan(spec,_vertical_pass=False):
    from poster_direction import INKS,digest
    c=spec['content'];a=spec.get('art_direction',{});meta=spec.get('meta',{})
    canvas=poster_canvas(spec.get('canvas'));x,y,x1,y1=canvas.safe;w=x1-x;H=canvas.height
    ink=copy.deepcopy(INKS[a.get('ink','cobalt-vermilion')]);ink['name']=a.get('ink','cobalt-vermilion')
    dialect=a.get('dialect','swiss');dialect='swiss' if dialect=='auto' else dialect
    theme=rk.Theme(palette='A',lang=meta.get('lang','en'),fonts=meta.get('fonts'))
    modules=sorted(copy.deepcopy(c.get('modules',[])),key=lambda m:m.get('order',0))
    from source_profile import profile,choose_form
    evidence=copy.deepcopy(spec.get('evidence',{}))
    if not evidence:
        from content_plan import inventory
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
    objs=p['objects']
    def put(oid,value,xx,yy,width,size,source=None,role='argument',bold=False,color=None):
        value=str(value)
        if not value.strip():return None
        font=theme.f_heading if bold else theme.f_body
        f=tf.fit(value,font,size,width,H*3,minimum=size,bold=bold,ls=1.08)
        ob=dict(id=oid,kind='text',text=value,source=source,role=role,rect=[xx,yy,xx+width,yy+f.height],
                fit=f.to_dict(),color=color or ink['body'],background=ink['paper'],rotation=0)
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
    title=put('title',c['title'],x,y,w,a.get('title_size',56),'title','hook',True,ink['main'][0])
    node('title',[title],title['rect'],0)
    cy=title['rect'][3]+25
    # Safe full-line rule outside the glyph envelope, never across uppercase letters.
    rule=path('title-rule',[[[x,cy-8],[x+min(w,title['fit']['width']),cy-8]]],ink['accent'],'emphasis',anchor='title',micro=True,vocabulary='underline')
    rule['line_width']=4
    if a.get('ornament') == 'focused':
        rule['line_width'] = 2.5
        rule['line'] = ink['main'][1]
    mains=[(i,m) for i,m in enumerate(modules) if m.get('level')!=4 and not (m.get('level')==1 and (m.get('role')=='title' or text(m)==c['title']))]
    foot=[(i,m) for i,m in enumerate(modules) if m.get('level')==4]
    # Semantic groups are indivisible bands. Process/timeline and high-weight heroes
    # receive full width; unrelated small modules share a row in source order.
    rows=[];pending=[];columns=a.get('columns',1 if evidence['level']<.5 and not evidence.get('legacy') else 2)
    for i,m in mains:
        full=m.get('visual') in ('step-flow','timeline','bar-compare','bar-vertical','line-chart','before-after','versus','stamp') or m.get('level')==1 or m.get('weight',1)>=1.5
        if full:
            if pending:rows.append(pending);pending=[]
            rows.append([(i,m)])
        else:
            pending.append((i,m))
    if pending:rows.append(pending)
    footer_height=sum(tf.fit(text(m),theme.f_body,16,w-20,H,minimum=16,ls=1.08).height+12 for _,m in foot)+16 if foot else 0
    available=y1-cy-footer_height-gap
    # Measured row minima, content-driven area allocation; never shrink body.
    rowweights=[max(m.get('weight',1) for _,m in row) for row in rows]
    rowheight=[(available-gap*max(0,len(rows)-1))*wt/sum(rowweights) for wt in rowweights]
    def render_module(index,m,rx,ry,rw,rh,band,col):
        from evidence_forms import render_module as render_evidence
        return render_evidence(index,m,[rx,ry,rx+rw,ry+rh],
            dict(plan=p,put=put,rect=rect,path=path,node=node,theme=theme,heading_size=a.get('heading_size',25 if evidence.get('legacy') else max(26,body*1.3)),bar_thickness=18 if evidence.get('legacy') else max(24,min(48,body*(1+policy['level']))),chart_height=min(180,available*.38)),band,col)
    # Measure each row using the exact component writer, then discard the probe.
    # Extra page height stays in the exterior margin instead of giant interior holes.
    rowheight=[];rowpacks=[]
    for row in rows:
        checkpoint={key:copy.deepcopy(p[key]) for key in ('objects','content_roles','regions','reading_order','module_metrics','hero','overlaps')}
        ncols=min(columns,len(row));rw=(w-gap*(ncols-1))/ncols;heights=[]
        for col,(index,m) in enumerate(row):
            start=len(objs);render_module(index,m,x+col*(rw+gap),0,rw,H*4,1,col)
            used=[o['rect'][3] for o in objs[start:] if not o.get('micro')]
            heights.append(max(used,default=0)+18)
        for key,value in checkpoint.items():p[key]=value
        objs=p['objects']
        candidates=[]
        for cuts in itertools.combinations(range(1,len(row)),ncols-1):
            if any(row[cut-1][1].get('group') and row[cut-1][1].get('group')==row[cut][1].get('group') for cut in cuts):continue
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
        rowheight.append(required);rowpacks.append((stacks,heights,rw))
    needed=sum(rowheight)+gap*max(0,len(rows)-1)
    if needed>available:
        raise ValueError(f'Infographic requires {needed:.1f}pt; available {available:.1f}pt at {body}pt body; row heights {[round(v,1) for v in rowheight]}. Change columns/grouping or explicitly adapt copy; no automatic deletion.')
    if not _vertical_pass and not evidence.get('legacy') and a.get('autofit',True) and available-needed>80 and body<policy['body_max']:
        candidate=copy.deepcopy(spec);ca=candidate.setdefault('art_direction',{})
        factor=min(policy['body_max']/body,max(1,available/max(1,needed)))
        ca['body_size']=round(body*factor*2)/2
        ca['title_size']=min(80,round(a.get('title_size',56)*factor))
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
    for row_index,(row,rh,packed) in enumerate(zip(rows,rowheight,rowpacks)):
        stacks,heights,rw=packed
        for col,stack in enumerate(stacks):
            local_y=cy
            for k in stack:
                index,m=row[k]
                render_module(index,m,x+col*(rw+gap),local_y,rw,heights[k],row_index+1,col)
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
    if a.get('ornament') == 'focused':
        p['element_quota'] = dict(density='focused', suggested_count=[1, 1], minimum_families=1)
        p['micro_layer'] = [dict(kind='underline', role='title emphasis')]
    else:
        from auto_garnish import apply
        apply(p, a.get('element_density', policy['element_density']))
    p['infographic_metrics']=assess(p)
    from evidence_style import signature
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
    from poster_harmony import internal_void
    empty=internal_void(p);fails=[];warnings=[]
    if levels<3:fails.append('hierarchy requires at least 3 type levels')
    if body<18:fails.append('infographic body below 18pt')
    if stats and min(stats)<4:fails.append('stat tile numerals must be at least 4x body')
    metadata_weight=union_area([o['rect'] for o in metadata])/page
    if metadata_weight>.12:warnings.append('Metadata occupies over 12% of page; condense only in adapt mode or choose a larger canvas')
    if empty['share']>.08:fails.append('Internal empty rectangle exceeds 8%; change geometry/module weight')
    ratio=union_area(visual)/page
    policy=p.get('evidence_policy',scale(p.get('evidence',{}).get('level',0)))
    if not policy['presence_target'][0]<=ratio<=policy['presence_target'][1]:warnings.append(f'evidence_presence bounds={ratio:.3f} outside calibrated {policy["presence_target"]}')
    text_only=sum(m['text_only'] for m in modules)/max(1,len(modules))
    if text_only>policy['text_fraction'] and not p.get('evidence',{}).get('legacy'):fails.append('text-only module ratio exceeds evidence-scaled allowance')
    from auto_garnish import assess as element_assess
    elements=element_assess(p);fails.extend(elements['fails']);warnings.extend(elements['warnings'])
    edge=edge_void(p)
    (warnings if p.get('version')!='3.8' or p.get('evidence',{}).get('legacy') else fails).extend(edge['fails'])
    return dict(visual_area_ratio=round(ratio,4),evidence_presence=dict(bounds_proxy=round(ratio,4),target=policy['presence_target'],raster_ink=None),evidence_level=policy['level'],visual_area_method='union of semantic non-text object bounds; excludes substrate, card backs and garnish; not ink pixels',
                text_only_module_ratio=text_only,hierarchy_levels=levels,stat_numeral_ratio=stats,
                metadata_weight=round(metadata_weight,4),
                internal_void=empty,edge_void=edge,**{k:v for k,v in elements.items() if k not in ('fails','warnings')},fails=fails,warnings=warnings)

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

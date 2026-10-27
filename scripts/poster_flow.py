"""v3.5 measured elastic poster layout. Exact source, explicit decisions.

The old planner remains in poster_direction for historical reproduction tests;
this engine is used only for art_direction posters. Deck/legacy paths stay put.
"""
import copy,itertools,math,re
from collections import OrderedDict
import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import poster_canvas
from place_decor import word_count
from poster_primitives import torn,ink_path,bounds
import poster_native_recipes as recipes

from poster_contract import CONTROLS,describe_spec,canonical

class CapacityError(ValueError):
    def __init__(self,report):
        self.report=report
        top=', '.join(f'{m["source"]} {m["height"]:.1f}pt' for m in report.get('tallest_modules',[])[:5])
        columns='; '.join(f'column {q["column"]}: {q["height"]:.1f}/{q["available"]:.1f}pt' for q in report.get('columns',[]))
        predictions='; '.join(str({k:v for k,v in q.items() if k.startswith('predicted')}) for q in report['repairs'])
        super().__init__(f'Poster capacity deficit {report["deficit_pt"]:.1f}pt. Tallest: {top}. '+ '; '.join(r['action'] for r in report['repairs'])+'; '+columns+'; '+predictions)

def settings(spec):
    from poster_dialects import settings as previous
    a=spec.get('art_direction',{})
    c=spec['content'];dialect=a.get('dialect','auto')
    reason='explicit art_direction.dialect'
    if dialect=='auto':
        dialect='swiss' if c.get('chart') or len(c.get('data',[]))>2 else 'doodle' if c.get('process') else 'collage' if c.get('blocks') or c.get('quote') else 'swiss'
        reason='content intent: comparable evidence / sequence / editorial modules'
    s=copy.deepcopy(spec);s['art_direction']['dialect']=dialect
    # Existing provenance guard is retained; v3.5 supports bands in every dialect.
    s['art_direction'].pop('skeleton',None);previous(s)
    return dialect,reason

def preflight(spec, measured=True, plan=None, diagnostic=None):
    from poster_direction import content_roles
    roles=content_roles(spec['content'],spec.get('art_direction',{}).get('roles'));words=sum(word_count(r['text']) for r in roles)
    candidates=[r['source'] for r in roles if r['role'] in ('argument','source','meta','facts')]
    result=dict(fields=len(roles),words=round(words,1),estimated_capacity='measure required' if words<260 and len(roles)<24 else 'high pressure; measure before rendering',
                tier3_candidates=candidates,suggestions=[{'fields':candidates,'action':'Keep supporting copy in T3 sidebar/footer at >=16pt; source remains verbatim.'},
                {'fields':[r['source'] for r in roles if r['source'].startswith('blocks.')],'action':'If still overfull, ask the author to approve a shorter poster summary or merge related modules. Never delete automatically.'}],
                policy='A poster is a summary, not the full manuscript. Supplied poster copy is immutable.')
    result['suggestions'].insert(0,dict(action='Try column/skeleton geometry before changing copy.',
        spec_patches=[{'art_direction':{'columns':n,'skeleton':'bands'}} for n in (1,2,3)],
        command='python scripts/poster_run.py --spec INPUT.json --content-plan content-plan.json --out OUTPUT --variants --plan-only'))
    if measured:
        try:
            if diagnostic is not None:raise CapacityError(diagnostic)
            p=plan if plan is not None else make_plan(spec);rows=p['capacity']['columns'];result['fits']=True;result['effective_body_size']=p['scale_ladder']['body']
            if p.get('element_quota'):result['element_quota']=p['element_quota']
            if p.get('infographic_metrics'):
                result['infographic_metrics']=p['infographic_metrics']
                result['suggestions'][1]['action']='Keep source/logistics in footer tickets; infographic body remains >=18pt.'
        except CapacityError as exc:
            rows=exc.report['columns'];result['fits']=False;result['diagnostic']=exc.report
        budgets=[]
        ratios=[]
        for row in rows:
            used=row.get('measured',row.get('height',0));available=row['available'];ratio=max(0,available)/max(1,used);ratios.append(ratio)
            column_words=row.get('words',words/max(1,len(rows)))
            budgets.append(dict(column=row['column'],current_words=column_words,available_pt=available,used_pt=used,estimated_word_budget=round(column_words*ratio)))
        target=max(0,int(words*min(ratios,default=1)))
        result.update(target_words=target,column_budgets=budgets,estimated_capacity=f'Target <= approximately {target} words; current {words:g} words',calibration='Measured current canvas/fonts/columns and module overhead; word target is an estimate, not permission to delete copy. Uneven columns need local edits.')
    return result

def voids(p,objects=None):
    x,y,x1,y1=p['canvas']['safe'];H=p['canvas']['height'];intervals=[]
    for o in objects or p['objects']:
        if o.get('duplicate_of') or o.get('layer')=='surface' or o['role'] in ('structure','navigation'):continue
        if o['kind']=='text' or o['role'] in ('graphic','data','relation'):
            r=o['rect']
            if r[2]>x and r[0]<x1:intervals.append((max(y,r[1]),min(y1,r[3])))
    if p.get('version') in ('3.6','3.7','3.8') and intervals:
        y1=min(y1,max(v[1] for v in intervals));y=max(y,min(v[0] for v in intervals))
    intervals.sort();gaps=[];end=y
    for a,b in intervals+[(y1,y1)]:
        if a>end and a>H*.2 and end<H*.85 and a-end>H*.08:
            r=[x,end,x1,a]
            intentional=any(v['rect'][1]<=end+1 and v['rect'][3]>=a-1 for v in p.get('intentional_voids',[]))
            gaps.append(dict(rect=r,share=round((a-end)/H,4),intentional=intentional))
        end=max(end,b)
    return gaps

def validate_reading(p):
    by={o['id']:o for o in p['objects']};nodes=p['reading_order'];errors=[]
    if [n['order'] for n in nodes]!=list(range(1,len(nodes)+1)):errors.append('Reading order indices are not sequential')
    expected=set(p.get('reading_graph',{}).get('node_ids',[]))
    if {n['region'] for n in nodes}!=expected:errors.append('Reading order misses a region')
    last=(-1,-1,-1)
    for n in nodes:
        members=[by[k] for k in n['objects'] if k in by]
        if not members:errors.append('Missing reading node '+n['region']);continue
        actual_y=min(o['rect'][1] for o in members);actual_x=min(o['rect'][0] for o in members)
        key=(n['band'],n['column'],actual_y)
        if key<last:errors.append('Reading order geometry inversion at '+n['region'])
        if n['band']==2 and abs(actual_x-n['x'])>2:errors.append('Reading column moved at '+n['region'])
        last=key
    edge_pairs=[[a['region'],b['region']] for a,b in zip(nodes,nodes[1:])]
    if p.get('reading_graph',{}).get('edges')!=edge_pairs:errors.append('Reading order graph edges differ')
    return errors

def make_plan(spec):
    if spec.get('mode','infographic')=='infographic' and 'modules' in spec.get('content',{}):
        from infographic import make_plan as infographic_plan
        return infographic_plan(spec)
    from poster_direction import INKS,ARCHETYPES,content_roles,select_archetype,digest,contrast
    spec,contract_warnings=canonical(spec)
    dialect,reason=settings(spec);a=spec['art_direction'];c=spec['content'];meta=spec.get('meta',{});seed=meta.get('seed',1)
    if not isinstance(seed,int) or isinstance(seed,bool):raise ValueError('meta.seed requires an integer')
    if c.get('image'):raise ValueError('Supplied image requires legacy image_led; remove art_direction or supply source-bound vector content')
    canvas=poster_canvas(spec.get('canvas'));x,y,x1,y1=canvas.safe;W,H=canvas.width,canvas.height;w=x1-x;h=y1-y
    roles=content_roles(c,a.get('roles'));by={r['source']:r for r in roles};words=sum(word_count(r['text']) for r in roles)
    density='dense' if words>180 else 'medium' if words>65 else 'sparse';arch,why=select_archetype(c,roles,density)
    if a.get('archetype','auto')!='auto':arch=a['archetype'];why='explicit source-checked archetype'
    elif c.get('quote') and not any(c.get(k) for k in ('key_number','chart','process')):arch='statement';why='supplied quotation leads editorial content'
    value=c.get('key_number');value=value.get('value','') if isinstance(value,dict) else value
    explicit_hero=a.get('roles',{}).get('key_number.value',a.get('roles',{}).get('key_number'))=='hero_stat'
    numeric=bool(re.fullmatch(r'[+-]?[0-9]+(?:[,.][0-9]+)*%?',str(value or '').strip()))
    if arch=='numeral-hero' and value and not (numeric or explicit_hero):
        arch='staggered-modules';why='Unit-bearing or textual statistic uses a medium content-sized module'
        for row in roles:
            if row['source'].startswith('key_number'):row['role']='facts'
    if arch=='numeral-hero' and not c.get('key_number'):raise ValueError('numeral-hero requires supplied key_number')
    if arch=='statement' and not c.get('quote'):raise ValueError('statement requires supplied quote')
    if arch=='diagram-hero' and not any(c.get(k) for k in ('chart','process','comparison')):raise ValueError('diagram-hero requires supplied relationship')
    inks=copy.deepcopy(INKS[a.get('ink','cobalt-vermilion')]);inks.update(name=a.get('ink','cobalt-vermilion'),multiply=False,solid_blocks=True,multiply_rendering='editable offset ink plates')
    fonts={'display_latin':'Arial Black'};fonts.update(meta.get('fonts') or {});theme=rk.Theme(palette='A',lang=meta.get('lang','en'),fonts=fonts)
    recipe,recipe_reason=recipes.choose(spec)
    tiers={r['source']:'T1' if r['role'] in ('hook','hero_stat','cta') else 'T2' if r['role']=='parallel_set' else 'T3' for r in roles}
    for k,v in a.get('tiers',{}).items():
        if k not in by or v not in ('T1','T2','T3'):raise ValueError('art_direction.tiers requires exact source paths mapped to T1/T2/T3: '+k)
        tiers[k]=v
    for v in a.get('intentional_voids',[]):
        if not isinstance(v,dict) or not v.get('reason') or len(v.get('rect',[]))!=4 or not all(isinstance(q,(int,float)) and math.isfinite(q) for q in v['rect']):raise ValueError('intentional_voids requires finite rect [x,y,x1,y1] and reason')
    for key,src in [('title_lines','title'),('statement_lines','quote.text' if isinstance(c.get('quote'),dict) else 'quote')]:
        if a.get(key) and (src not in by or re.sub(r'\s+','',''.join(a[key]))!=re.sub(r'\s+','',by[src]['text'])):raise ValueError(key+' must preserve exact source and order')
    def measure(text,width,size,bold=False,display=False,compact=False):
        family=theme.f_heading if re.search(r'[\u3400-\u9fff]',text) else theme.f_display if display else theme.f_body
        f=tf.fit(text,family,math.floor(size*2)/2,width,H*20,minimum=math.floor(size*2)/2,bold=bold,ls=1.04 if display else 1.08)
        if display and compact:
            from dataclasses import replace
            face=tm.font(f.font,f.size,f.bold);ink_height=max((face.getbbox(line)[3]-face.getbbox(line)[1] for line in f.lines if line),default=f.size)
            pitch=max(f.size*a.get('title_leading',.98),ink_height+3)
            f=replace(f,pitch=pitch,height=(len(f.lines)-1)*pitch+f.height/len(f.lines))
        return f
    hero_sources=[]
    if arch=='numeral-hero':hero_sources=[r for r in roles if r['source'].startswith('key_number')]
    elif arch=='statement':hero_sources=[r for r in roles if r['source'].startswith('quote')]
    consumed={'title','subtitle','footer','cta'}|{r['source'] for r in hero_sources}
    groups=OrderedDict()
    # Narrative precedes the parallel set; each source group remains contiguous.
    order={'key_number':-1,'body':0,'quote':1,'blocks':2,'data':3,'process':4,'comparison':5,'chart':6}
    for r in sorted(roles,key=lambda r:order.get(r['source'].split('.')[0],7)):
        if r['source'] in consumed:continue
        if r['source']=='body':
            for j,t in enumerate(re.split(r'\n+',r['text'])):
                if t:groups[f'body-{j}']=[dict(r,text=t,source_part=j)]
        else:groups.setdefault(r.get('group',r['source']),[]).append(r)
    for i,note in enumerate(a.get('annotations',[])):
        if not isinstance(note,dict) or note.get('source') not in by or not note.get('text') or note['text'] not in by[note['source']]['text']:raise ValueError('Annotation must be an exact supplied phrase with source path')
        source='annotation-'+str(i);tiers[source]='T3';groups[source]=[dict(id=source,source=None,text=note['text'],role='meta',annotation_source=note['source'])]
    modules=list(groups.items());pref_body=a.get('body_size',20);cols=a.get('columns',2 if modules else 1);cols=min(cols,max(1,len(modules)))
    if 'columns' not in a and words<=160 and len(modules)<=3 and not any(c.get(k) for k in ('chart','process','comparison','key_number')):cols=1
    sk=a.get('skeleton','auto');sk='bands' if dialect=='swiss' else 'asymmetric-notes' if words>100 or len(modules)>4 else 'central-orbit' if sk=='auto' else sk
    if a.get('skeleton','auto')!='auto':sk=a['skeleton']
    if words<=160 and a.get('skeleton','auto')=='auto':sk='compact-columns'
    initial_sk=sk;autofit=a.get('autofit',True);attempts=[];best_fail=None
    def layout(body,title_size,hero_size,gap,skeleton):
        margin=14;cw=(w-gap*(cols-1))/cols
        widths=[cw]*cols
        if cols==2 and words>160:widths=[(w-gap)*.54,(w-gap)*.46]
        title='\n'.join(a['title_lines']) if a.get('title_lines') else c['title']
        tt=measure(title,w-12,title_size,True,True,compact=True)
        subtitle=measure(c['subtitle'],w,16) if c.get('subtitle') else None
        footer=measure(c['footer'],w,16) if c.get('footer') else None
        cta=measure(c['cta'],w-32,max(20,body*1.15),True) if c.get('cta') else None
        header=(subtitle.height+12 if subtitle else 0)+tt.height+10
        foot=(footer.height+12 if footer else 0)+(cta.height+24+gap if cta else 0)
        quote_hero=arch=='statement'
        hw=w-220 if recipe and hero_sources and not quote_hero else w;hero_rows=[]
        for r in hero_sources:
            numeric=r['source'] in ('key_number','key_number.value');sz=hero_size if numeric else hero_size if r['source'] in ('quote','quote.text') else body
            txt='\n'.join(a['statement_lines']) if r['source'] in ('quote','quote.text') and a.get('statement_lines') else r['text']
            fitted=measure(txt,hw-24,sz,numeric or r['role']=='hook',numeric or r['role']=='hook')
            if r['source'] in ('quote','quote.text'):
                while sz>max(32,body*1.5):
                    line_widths=[tm.advance(ln,fitted.font,fitted.size,fitted.bold) for ln in fitted.lines]
                    if len(line_widths)<2 or line_widths[-1]>=max(line_widths)*.5:break
                    sz-=2;fitted=measure(txt,hw-24,sz,True,True)
            hero_rows.append((r,fitted))
        hero_horizontal=arch=='numeral-hero' and len(hero_rows)>1
        if hero_horizontal:
            nr,nf=hero_rows[0];lr,lf=hero_rows[1];lf=measure(lr['text'],max(100,hw-nf.width-48),body)
            hero_rows=[(nr,nf),(lr,lf),*hero_rows[2:]]
        hero_needed=(max(f.height for row,f in hero_rows)+24 if hero_horizontal else sum(f.height+8 for row,f in hero_rows)+12)+(70 if recipe and quote_hero else 0)
        hero=max(90 if recipe else 0,hero_needed if hero_rows else 0)
        # Semantic hero follows measured content; spare page area never enlarges it.
        if not recipe and not hero_rows:hero=0
        cap=h-header-foot-hero-gap*(2 if hero and modules else 1)
        memo={}
        def mm(m,width):
            key=(m[0],width)
            if key in memo:return memo[key]
            items=[];ht=margin*2
            for r in m[1]:
                source=r.get('source') or r['id']
                heading=source.endswith(('.title','.label')) and source.split('.')[0] in ('blocks','process','comparison')
                sz=max(16,body-1) if tiers[source]=='T3' else body
                if heading:sz=body*1.22
                elif source in ('key_number','key_number.value'):sz=min(44,body*2.2)
                elif r['role']=='hook':sz=body*1.4
                f=measure(r['text'],width-margin*2,sz,heading or source in ('key_number','key_number.value'))
                items.append((r,f));ht+=f.height+5
                # Chart values have their own bar row, measured before packing.
                if source.startswith('chart.items.') and source.endswith('.value'):ht+=18
            memo[key]=(items,ht);return memo[key]
        packs=[]
        for cuts in itertools.combinations(range(1,len(modules)),cols-1):
            groups=a.get('keep_together',[])
            if any(any(any(modules[k][0].startswith(prefix) for prefix in group) for k in range(cut))
                       and any(any(modules[k][0].startswith(prefix) for prefix in group) for k in range(cut,len(modules)))
                       for cut in cuts for group in groups):
                continue
            breaks=(0,*cuts,len(modules));stacks=[];heights=[]
            try:
                for j in range(cols):
                    stack=[(m,*mm(m,widths[j])) for m in modules[breaks[j]:breaks[j+1]]]
                    stacks.append(stack);heights.append(sum(m[2] for m in stack)+gap*max(0,len(stack)-1))
            except ValueError:continue
            packs.append((max(heights,default=0),max(heights,default=0)-min(heights,default=0),stacks,heights))
        if not modules:packs=[(0,0,[[]],[0])]
        if not packs:raise ValueError('No column can fit an indivisible source token; choose fewer/wider columns or a shorter author-approved label')
        tallest,_,stacks,heights=min(packs,key=lambda v:(v[0],v[1]))
        return dict(hero_horizontal=hero_horizontal,body=body,title_size=title_size,hero_size=hero_size,gap=gap,skeleton=skeleton,widths=widths,title=tt,subtitle=subtitle,footer=footer,cta=cta,header=header,foot=foot,hero=hero,hero_rows=hero_rows,hw=hw,capacity=cap,stacks=stacks,heights=heights,deficit=max(0,tallest-cap),free=cap-tallest)
    preferred_title=min(a.get('title_size',64),pref_body*3.6)
    candidates=[(pref_body,preferred_title,min(72,pref_body*3.6),24,sk)]
    if autofit:
        candidates.extend([(pref_body,preferred_title,min(72,pref_body*3.6),16,sk),(pref_body,min(preferred_title,pref_body*3.2),pref_body*3.2,14,sk)])
        candidates.extend((b,min(a.get('title_size',64),b*3.5),b*3.5,14,sk) for b in range(math.floor(pref_body)-1,15,-1))
        candidates.append((16,52,56,12,'bands'))
    chosen=None
    for values in candidates:
        try:r=layout(*values)
        except ValueError as e:attempts.append(dict(body=values[0],skeleton=values[-1],error=str(e)));continue
        attempts.append(dict(body=values[0],title=values[1],gap=values[3],skeleton=values[-1],deficit_pt=round(r['deficit'],2)))
        if best_fail is None or r['deficit']<best_fail['deficit']:best_fail=r
        if r['deficit']<.01:chosen=r;break
    if chosen is None:
        r=best_fail
        if r is None:raise ValueError(attempts[-1]['error'])
        tallest=sorted([dict(source=m[0][0],height=round(m[2],2),column=j+1) for j,stack in enumerate(r['stacks']) for m in stack],key=lambda m:-m['height'])
        repairs=[];original_cols=cols
        for n in (1,2,3):
            if n==original_cols or n>len(modules):continue
            cols=n
            try:
                alternate=layout(16,52,56,12,'bands');repairs.append(dict(action=f'Set art_direction.columns={n}, body_size=16, skeleton="bands"',predicted_deficit_pt=round(alternate['deficit'],2),predicted_released_pt=round(r['deficit']-alternate['deficit'],2)))
            except ValueError as exc:repairs.append(dict(action=f'columns={n} cannot fit an indivisible token',reason=str(exc)))
        cols=original_cols
        repairs.append(dict(action='Ask author to approve a shorter poster summary for '+', '.join(m['source'] for m in tallest[:3]),predicted_effect=f'At least {r["deficit"]:.1f}pt must be released in the tallest column; no text has been deleted'))
        raise CapacityError(dict(deficit_pt=round(r['deficit'],2),tallest_modules=tallest,columns=[dict(column=j+1,words=sum(word_count(row['text']) for _,items,_ in r['stacks'][j] for row,_ in items),height=round(v,2),available=round(r['capacity'],2)) for j,v in enumerate(r['heights'])],repairs=repairs,attempts=attempts,preflight=preflight(spec,measured=False)))
    changes=[]
    if len(attempts)>1:changes.append('Fit capacity by reducing gap, then title/hero to meaningful minima, then body; preserve all source fields.')
    # W1: bounded spaces absorb surplus; title and hero never grow to fill it.
    title_ceiling=a.get('title_size',64)
    r=chosen;gap=r['gap'];body=r['body'];extra=max(0,r['free'])
    p=dict(version='3.6',source_sha256=digest(c),content_roles=roles,archetype=arch,selection_reason=why,dialect=dialect,looseness=a.get('looseness',0 if dialect=='swiss' else .65),
           skeleton=r['skeleton'],seed=seed,canvas=canvas.to_dict(),fonts=theme.fonts,font_diagnostics=theme.font_diagnostics,ink_plan=inks,objects=[],overlaps=[],regions=[],micro_layer=[],
           content_words=words,density=density,columns=cols,scale_ladder=dict(body=body,detail=16),hero=dict(kind=arch,source=hero_sources[0]['source'] if hero_sources else 'title',object_ids=[],share=round(r['hero']/h,4)),
           constraints=dict(body_min=16,decor_cap=.40,accent_cap=.08,max_highlights=2,max_nonstructural_repeat=2,max_edge_void=.14,quiet_region_min=0),
           contract_warnings=contract_warnings,revision=a.get('revision',0),review_changes=a.get('review_changes',[]),tiers=tiers,preflight=preflight(spec,measured=False),intentional_voids=a.get('intentional_voids',[]),
           parallel_sets=[dict(source=k,n=len(c[k])) for k in ('blocks','process','comparison') if c.get(k)],reading_order=[],review_notes=[],
           graphic_design=dict(requested=meta.get('graphic_recipe','micro'),status='composed' if recipe else 'micro-only',recipe=recipe,meaning=recipe_reason,implementation='native vector interpretations; legacy deck bitmap generators unchanged'),
           quiet=dict(definition='low texture behind body, consistent safe margins; no required large empty rectangle',body_texture='low-amplitude paper grain',margin_pt=list(canvas.safe)),
           autofit=dict(enabled=autofit,attempts=attempts,changes=changes,source_changed=False),effective_controls={})
    for k,eff,rule in [('dialect',dialect,reason),('columns',cols,'source module count caps unused columns'),('skeleton',r['skeleton'],'content-based selection; capacity fallback within chosen dialect'),('body_size',body,'elastic measured fit; >=16pt'),('hero_share',round(r['hero']/h,4),'preferred semantic hero/graphic band; measured min and content capacity prevail'),('looseness',p['looseness'],'dialect default'),('ink',inks['name'],'explicit or default')]:
        p['effective_controls'][k]=dict(requested=a.get(k,'auto'),effective=eff,rule=rule)
    for k,v in spec.get('layout',{}).items():
        if k in ('graphic','graphic_position','process_style'):
            p['effective_controls']['layout.'+k]=dict(requested=v,effective='hero band' if k=='graphic_position' else v if k=='graphic' else 'numbered-chain',rule='v3.6 measured skeleton owns region placement; process sequence remains visible')
        else:raise ValueError(f'layout.{k} is a legacy control and cannot silently affect art_direction. Use poster_run --describe-spec for the modern equivalent, or remove art_direction for legacy reproduction.')
    objs=p['objects']
    def text(id,row,f,xx,yy,width,color=None):
        o=dict(id=id,kind='text',text=row['text'],source=row.get('source'),role=row.get('role','meta'),rect=[xx,yy,xx+width,yy+f.height],fit=f.to_dict(),color=color or inks['body'],background=inks['paper'],rotation=0)
        if 'source_part' in row:o['source_part']=row['source_part']
        objs.append(o);return o
    def rect(id,box,fill,role='structure',**kw):
        o=dict(id=id,kind='rect',rect=box,fill=fill,role=role,rotation=0,**kw);objs.append(o);return o
    def node(id,members,band,col,xx):
        p['reading_order'].append(dict(order=len(p['reading_order'])+1,region=id,objects=[o['id'] for o in members],band=band,column=col,x=xx))
    surface_seed=a.get('surface_seed',seed);looseness=p['looseness']
    def backing(id,box,targets,style):
        if style=='swiss':return
        if id=='key_number' or id=='hero' and arch=='numeral-hero':
            from poster_primitives import planned_glyphs
            gs=[g for t in targets for g in planned_glyphs(t)]
            if gs:box=[box[0] if id=='key_number' else min(g[0] for g in gs)-8,box[1] if id=='key_number' else min(g[1] for g in gs)-8,max(g[2] for g in gs)+8,max(g[3] for g in gs)+8]
        if style=='collage':
            fill=('EEE5D4','E3E9E4','E5E7EF')[len([o for o in objs if o.get('vocabulary')=='paper'])%3];paths=[torn(box,surface_seed+len(objs))];o=dict(id='paper-'+id,kind='path',rect=box,paths=paths,closed=True,fill=fill,role='surface',layer='surface',rotation=0,vocabulary='paper',anchor=id,anchor_kind='backing')
            for pt in paths[0]:pt[1]=(box[1] if pt[1]<(box[1]+box[3])/2 else box[3])*(1-looseness)+pt[1]*looseness
            objs.insert(min(objs.index(t) for t in targets),o)
            for t in targets:p['overlaps'].append(dict(objects=[o['id'],t['id']],reason='consistent semantic paper backing',min_contrast=4.5))
            n=len([o for o in objs if o.get('vocabulary')=='tape'])
            if n<3:
                tx=box[0]+18 if n%2==0 else box[2]-70;ty=box[1]-5
                tape=rect('tape-'+id,[tx,ty,tx+48,ty+9],(inks['accent'],'D0DACA','D7DDEA')[n],role='surface',layer='surface',vocabulary='tape',anchor=targets[0]['id'])
                tape['rotation']=(-4,5,-6)[n]
        else:
            if sum(o.get('vocabulary')=='underline' for o in objs)>=3:return
            xx,yy,xx1,yy1=box
            paths=ink_path('line',[xx,yy1-2,xx1,yy1],surface_seed+len(objs),looseness)
            objs.append(dict(id='mark-'+id,kind='path',rect=bounds(paths,1),paths=paths,line=inks['main'][1],line_width=1.2,role='surface',layer='surface',rotation=0,vocabulary='underline',anchor=targets[0]['id'],micro=True))
    cy=y
    if r['subtitle']:
        o=text('masthead',by['subtitle'],r['subtitle'],x,cy,w);cy=o['rect'][3]+12;node('masthead',[o],0,0,x)
    title=text('title',by['title'],r['title'],x+3,cy,w-12,inks['main'][0]);p['hero']['object_ids'].append('title');node('title',[title],0,0,x)
    # Every dialect receives one coherent, editable registration layer.
    dup=copy.deepcopy(title);dup.update(id='title-ink',source=None,duplicate_of='title',color=inks['main'][1],role='overprint');dup['rect']=[v+q for v,q in zip(dup['rect'],[1.5,1.5,1.5,1.5])];objs.insert(objs.index(title),dup)
    p['micro_layer'].append(dict(kind='overprint',role='title registration'))
    cy=y+r['header']+gap
    if r['hero']:
        hy=cy;hh=r['hero'];hero_members=[];yy=hy+12
        for row_index,(row,f) in enumerate(r['hero_rows']):
            horizontal=r['hero_horizontal'] and row_index==1
            tx=x+12+(r['hero_rows'][0][1].width+20 if horizontal else 0)
            ty=hy+12+max(0,(r['hero_rows'][0][1].height-f.height)/2) if horizontal else yy
            o=text(row['source'],row,f,tx,ty,min(r['hw']-24,f.width+8),inks['main'][0] if row['role'] in ('hero_stat','hook') else None);hero_members.append(o);yy=o['rect'][3]+8;p['hero']['object_ids'].append(o['id'])
        if hero_members:
            node('hero',hero_members,1,0,x)
            hero_width=min(r['hw'],max(t['rect'][0]+t['fit']['width'] for t in hero_members)-x+14)
            backing('hero',[x,hy,x+hero_width,min(hy+hh,max(t['rect'][3] for t in hero_members)+8)],hero_members,dialect)
        if recipe:
            gx=x+r['hw']+20 if hero_members and arch!='statement' else x+12;gw=x1-gx-8
            if hero_members and arch!='statement':gx=min(x1-208,max(t['rect'][2] for t in hero_members)+20)
            rr=[gx,yy+10 if arch=='statement' else hy+8,min(x1-8,gx+200),min(hy+hh-8,(yy+10 if arch=='statement' else hy+8)+100)]
            graphic_objects=recipes.compose(recipe,rr,inks,seed)
            for item in graphic_objects:item['anchor']=hero_members[-1]['id'] if hero_members else 'title'
            if not hero_members:
                for item in graphic_objects:
                    item['rect'][1]-=16;item['rect'][3]-=16
                    for path in item.get('paths',[]):
                        for point in path:point[1]-=16
            objs.extend(graphic_objects);p['graphic_design'].update(region=rr,placement='hero',parts=['lead','pattern','detail'])
        cy+=hh+gap
    content_top=cy;available=y1-r['foot']-content_top
    avail=min(available,max(r['heights'])+min(max(0,r['free']),24))
    content_bottom=content_top+avail
    xx=x
    stacks_meta=[]
    for j,(stack,width) in enumerate(zip(r['stacks'],r['widths'])):
        need=sum(m[2] for m in stack)+gap*max(0,len(stack)-1);spare=max(0,avail-need)
        # Offset a shorter secondary column within its real slack. This avoids
        # synchronized cross-page holes while preserving column-major order.
        column_offset=0;spare-=column_offset
        local_gap=min(gap+spare/max(1,len(stack)-1),32) if len(stack)>1 else gap
        remainder=max(0,spare-(local_gap-gap)*max(0,len(stack)-1));pad_extra=min(remainder/max(1,len(stack)),8)
        yy=content_top+column_offset;details=[]
        for m,items,mh in stack:
            start=yy;members=[];ty=yy+14
            for row,f in items:
                source=row.get('source') or row['id']
                unit_match=re.fullmatch(r'([+-]?[0-9]+(?:[,.][0-9]+)*)(\s*[A-Za-z]+)',row['text']) if source in ('key_number','key_number.value') else None
                if unit_match:
                    number,unit=unit_match.groups();nf=measure(number,width-28,f.size,True);uf=measure(unit,width-28,body,False)
                    baseline=tm.font(nf.font,nf.size,True).getmetrics()[0]-tm.font(uf.font,uf.size,False).getmetrics()[0]
                    o=text(source,dict(row,text=number,source_part=0),nf,xx+14,ty,nf.width+8,inks['main'][0]);members.append(o)
                    u=text(source+'-unit',dict(row,text=unit,source_part=1,role='facts'),uf,xx+14+nf.width,ty+baseline,uf.width+10,inks['main'][0]);members.append(u)
                    ty=max(o['rect'][3],u['rect'][3])+5
                else:
                    chart_value=source.startswith('chart.items.') and source.endswith('.value')
                    if chart_value:ty=members[-1]['rect'][3]+5
                    tx=xx+14+(width-108)*float(row['text'])/(max(q['value'] for q in c['chart']['items']) or 1)+8 if chart_value else xx+14
                    o=text(source+('-part'+str(row['source_part']) if 'source_part' in row else ''),row,f,tx,ty,f.width+8 if chart_value else width-28,inks['main'][0] if row['role']=='hook' or source.startswith('key_number') else None);members.append(o);ty=o['rect'][3]+5
                if source.startswith('chart.items.') and source.endswith('.value'):
                    peak=max(q['value'] for q in c['chart']['items']) or 1;value=float(row['text'])
                    if value:rect('bar-'+row['source'],[xx+14,o['rect'][1]+5,xx+14+(width-108)*value/peak,o['rect'][1]+17],inks['main'][1],'data')
                    ty+=18
            box=[xx,start,xx+width,start+mh+pad_extra];backing(m[0],box,members,dialect)
            p['regions'].append(dict(id=m[0],rect=list(box),objects=[o['id'] for o in members],column=j,order=len(p['reading_order'])+1));node(m[0],members,2,j,xx+14)
            if m[0].startswith('process.'):
                n=int(m[0].split('.')[1])+1;f=measure(str(n),22,16,True)
                step=text('step-'+str(n),dict(text=str(n),role='navigation'),f,xx-8,start+14,22,inks['main'][0])
                if dialect=='collage':p['overlaps'].append(dict(objects=[step['id'],'paper-'+m[0]],reason='process number in paper gutter',min_contrast=4.5))
            details.append(dict(source=m[0],height=round(mh,2),allocated=round(mh+pad_extra,2)));yy=box[3]+local_gap
        stacks_meta.append(dict(column=j+1,words=sum(word_count(row['text']) for _,items,_ in stack for row,_ in items),width=round(width,2),measured=round(need,2),available=round(avail,2),modules=details));xx+=width+gap
    cy=content_bottom+gap
    if r['cta']:
        bg=rect('cta-accent',[x,cy,x+7,cy+r['cta'].height+16],inks['accent'],'emphasis')
        o=text('cta',by['cta'],r['cta'],x+16,cy+8,w-32,inks['main'][0]);node('cta',[o],3,0,x);cy=o['rect'][3]+gap
    else:rect('accent',[x1-min(85,w*.12),y+r['header']-4,x1,y+r['header']-1],inks['accent'],'emphasis')
    if r['footer']:
        o=text('colophon',by['footer'],r['footer'],x,min(y1-r['footer'].height,cy+8 if r['cta'] else content_bottom+gap),w);node('footer',[o],4,0,x)
    # Registration outside the safe text area; no arbitrary words or numbers.
    for i,(rx,ry) in enumerate(((x-14,y-14),(x1+14,y1+14))):
        rect('register-h'+str(i),[rx-5,ry,rx+5,ry+1],inks['main'][i],'structure');rect('register-v'+str(i),[rx,ry-5,rx+1,ry+5],inks['main'][i],'structure')
    p['micro_layer']+= [dict(kind='paper',role='quiet substrate'),dict(kind='register',role='plate alignment'),dict(kind='accent',role='action anchor')]
    if dialect=='doodle' and arch=='numeral-hero' and not a.get('highlights'):
        from poster_primitives import planned_glyphs,stroke_segments
        import layout as lay
        target=next((o for o in objs if o.get('source') in ('key_number','key_number.value')),None)
        if target:
            gs=list(planned_glyphs(target))
            rr=[min(g[0] for g in gs)-10,min(g[1] for g in gs)-12,max(g[2] for g in gs)+10,max(g[3] for g in gs)+12]
            paths=ink_path('circle',rr,surface_seed,.6);ob=dict(id='hero-source-circle',kind='path',rect=bounds(paths,1),paths=paths,line=inks['main'][1],line_width=1.5,role='surface',layer='surface',anchor=target['id'],vocabulary='circle')
            all_glyphs=[g for o in objs if o['kind']=='text' and not o.get('duplicate_of') for g in planned_glyphs(o)]
            if not any(lay.segment_rect_distance(u,v,g)<1.5 for u,v in stroke_segments(ob) for g in all_glyphs):objs.append(ob)
            else:p['review_notes'].append('Hero circle omitted because it would cross a source glyph; original figure retained.')
    # Explicit marks use exact source substrings and real measured glyphs.
    highlights=a.get('highlights',[])
    if len(highlights)>2:raise ValueError('At most two source highlights')
    for i,mark in enumerate(highlights):
        if not isinstance(mark,dict) or mark.get('source') not in by or not mark.get('text') or mark['text'] not in by[mark['source']]['text']:raise ValueError('Highlight must bind an exact supplied substring')
        target=next((o for o in objs if o.get('source')==mark['source'] and any(mark['text'] in ln for ln in o['fit']['lines'])),None)
        if not target:raise ValueError('Highlight crosses a measured line; choose a shorter exact phrase')
        f=target['fit'];li,line=next((j,ln) for j,ln in enumerate(f['lines']) if mark['text'] in ln);prefix=line[:line.index(mark['text'])]
        tx=target['rect'][0]+tm.advance(prefix,f['font'],f['size'],f['bold'],f['spc']);ty=target['rect'][1]+li*f['pitch'];tw=tm.advance(mark['text'],f['font'],f['size'],f['bold'],f['spc'])
        kind=mark.get('kind','highlight')
        if kind=='highlight':
            ob=rect('source-highlight-'+str(i),[tx,ty+f['size']*.18,tx+tw+2,ty+f['size']*1.05],inks['accent'],'emphasis');objs.remove(ob);objs.insert(objs.index(target),ob)
            p['overlaps'].append(dict(objects=[target['id'],ob['id']],reason='exact source highlight',min_contrast=4.5))
        elif kind in ('circle','underline','wave','bracket'):
            from poster_primitives import planned_glyphs,stroke_segments
            import layout as lay
            if kind!='circle' and len(f['lines'])>1:raise ValueError('Multiline display underline requires a shorter single-line source phrase')
            br=[tx-8,ty-10,tx+tw+8,ty+f['pitch']+8] if kind=='circle' else [tx,ty+f['pitch']-1,tx+tw,ty+f['pitch']+2]
            paths=ink_path(kind,br,surface_seed+i,.5);ob=dict(id='source-mark-'+str(i),kind='path',rect=bounds(paths,1),paths=paths,line=inks['main'][1],line_width=1.2,role='surface',layer='surface',anchor=target['id'],vocabulary=kind,keyword=mark['text'])
            glyphs=[g for o in objs if o['kind']=='text' and not o.get('duplicate_of') for g in planned_glyphs(o)]
            if any(lay.segment_rect_distance(u,v,g)<1.2 for u,v in stroke_segments(ob) for g in glyphs):raise ValueError('Source mark crosses glyphs; choose another exact keyword or highlight backing')
            objs.append(ob)
        else:raise ValueError('Unsupported highlight kind '+str(kind))
    if a.get('halftone')=='auto':
        p['review_notes'].append('Halftone request resolved by the recipe pattern when available; no unanchored edge field added.')
        p['effective_controls']['halftone']=dict(requested='auto',effective='recipe-pattern' if recipe else 'omitted',rule='Keep patterned graphics in reserved graphic region; protect body substrate')
    if a.get('micro_style','label')!='label':
        target=next((o for o in objs if o['id']=='cta'),None)
        if target:
            rct=target['rect'];rect('cta-stamp-rule',[rct[0],rct[3]+4,rct[2],rct[3]+5],inks['main'][1],'structure')
        p['effective_controls']['micro_style']=dict(requested=a['micro_style'],effective='source CTA rule' if target else 'omitted',rule='CTA anchoring; no invented badge copy')
    p['reading_graph']=dict(mode='bands, then columns top-to-bottom and left-to-right',node_ids=[n['region'] for n in p['reading_order']],edges=[[u['region'],v['region']] for u,v in zip(p['reading_order'],p['reading_order'][1:])],visible_numbers='process chain only; ordinary column reading is trivial')
    sequence=sorted((rg for rg in p['regions'] if rg['id'].startswith('process.')),key=lambda rg:int(rg['id'].split('.')[1]))
    for i,(left,right) in enumerate(zip(sequence,sequence[1:])):
        if left['column']==right['column'] and right['rect'][1]-left['rect'][3]>18:
            cx=left['rect'][0]+4;sy=left['rect'][3]+5;ey=right['rect'][1]-9
            paths=[[[cx,sy],[cx,ey]],[[cx-4,ey-6],[cx,ey],[cx+4,ey-6]]]
            objs.append(dict(id='process-arrow-'+str(i),kind='path',rect=bounds(paths,1),paths=paths,line=inks['main'][1],line_width=1.4,role='relation',rotation=0,connects=[left['id'],right['id']]))
    p['capacity']=dict(columns=stacks_meta,tallest_modules=sorted([dict(m,column=s['column']) for s in stacks_meta for m in s['modules']],key=lambda q:-q['height'])[:5])
    header_extra=(r['subtitle'].height+12 if r['subtitle'] else 0)+10
    try:title_max_height=measure(c['title'],w-12,title_ceiling,True,True).height+header_extra
    except ValueError:title_max_height=r['header']
    p['bands']=[dict(id=k,min=lo,pref=pref,max=hi,actual=actual,unit='pt') for k,lo,pref,hi,actual in [('title',measure(c['title'],w-12,52,True,True).height+header_extra,measure(c['title'],w-12,64,True,True).height+header_extra,title_max_height,r['header']),('hero',100 if recipe else 0,h*a.get('hero_share',.24),max(h*.65,r['hero']),r['hero']),('body',max(r['heights']),avail,avail,avail),('footer',r['foot'],r['foot'],r['foot'],r['foot'])]]
    p['content_extent']=dict(top=content_top,bottom=content_bottom,footer_edge=y1)
    movable=[o for o in objs if not o['id'].startswith('register-')]
    low=max(o['rect'][3] for o in movable);high=min(o['rect'][1] for o in movable)
    if (not modules and not c.get('footer') and not c.get('cta')) or (words<=160 and a.get('skeleton','auto')=='auto' and low-high<h*.72 and not a.get('intentional_voids')):
        shift=((y1-low)-(high-y))/2
        for o in movable:
            o['rect'][1]+=shift;o['rect'][3]+=shift
            for path in o.get('paths',[]):
                for pt in path:pt[1]+=shift
        for region in p['regions']:region['rect'][1]+=shift;region['rect'][3]+=shift
        for key in ('top','bottom'):p['content_extent'][key]+=shift
        if p['graphic_design'].get('region'):
            p['graphic_design']['region'][1]+=shift;p['graphic_design']['region'][3]+=shift
        p['skeleton']='compact-centered';p['effective_controls']['skeleton']['effective']='compact-centered'
        p['review_notes'].append('Sparse compact content centered by balancing outer margins; no source or type scale changed.')
    p['process_style']=dict(requested=spec.get('layout',{}).get('process_style','auto'),effective='numbered-chain' if c.get('process') else None,rule='Source sequence uses structural numbers across ordered content columns')
    if c.get('process'):p['review_notes'].append('Process uses a numbered chain in content columns; source labels and text remain separate.')
    p['scale_ladder']['actual']=sorted({o['fit']['size'] for o in objs if o['kind']=='text'},reverse=True)
    from poster_harmony import add_micro,finish_plan,prepare_title
    prepare_title(p)
    add_micro(p,a)
    finish_plan(p,a)
    if a.get('skeleton')=='central-orbit':p['contract_warnings'].append('central-orbit may converge with bands for a top hero; compare composition_signature before treating it as a distinct layout')
    if c.get('key_number') and not hero_sources:p['contract_warnings'].append('hero_stat role demoted by archetype; inspect hierarchy')
    p['voids']=voids(p)
    p['document_style']=bool(body<=16 and r['hero']<100)
    p['composition_signature']=digest([dict(id=o['id'],rect=o['rect']) for o in objs if o.get('layer')!='surface'])
    errors=validate_reading(p)
    if errors:raise ValueError('; '.join(errors))
    return p

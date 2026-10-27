"""Orthogonal poster dialects: measured regions plus anchored editable surfaces.

All randomness is local and seeded. Vocabulary budgets are ceilings, never a
quota to sprinkle decorations into empty space. Body text has zero rotation.
"""
import copy
import math
import random
import re
from collections import Counter
import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import poster_canvas
from place_decor import word_count
from poster_primitives import ink_path,torn,bounds

DIALECTS={
    'swiss':dict(skeleton_jitter=0,angles=[0],offset_quantum=0,vocabulary=[],doodle=[0,0],paper=[0,0],tape=[0,0],irregular_modules=False,stagger=False),
    'collage':dict(skeleton_jitter=0,angles=[0,-6,-4,4,6],offset_quantum=3,vocabulary=['paper','tape','sticker','stamp','underline','circle','arrow','overprint'],doodle=[0,3],paper=[1,5],tape=[0,3],irregular_modules=True,stagger=True),
    'doodle':dict(skeleton_jitter=0,angles=[0,-6,-3,3,6],offset_quantum=3,vocabulary=['line','circle','underline','arrow','star','bracket','wave','paper','tape','sticker','overprint'],doodle=[1,6],paper=[0,2],tape=[0,1],irregular_modules=True,stagger=True),
}
NEW_OPTIONS={'dialect','looseness','skeleton','annotations','colophon_source','source_document','surface_seed','halftone'}
SKELETONS=('asymmetric-notes','central-orbit')
for _dialect in ('collage','doodle'):
    DIALECTS[_dialect]['vocabulary']=sorted(set(DIALECTS[_dialect]['vocabulary'])|{'line','star','bracket','wave','stamp','annotation','register','shadow','halftone'})


def settings(spec):
    opts=spec.get('art_direction',{})
    if not isinstance(opts,dict):raise ValueError('art_direction must be an object')
    dialect=opts.get('dialect','swiss')
    if dialect not in DIALECTS:raise ValueError('dialect must be swiss, collage or doodle')
    looseness=opts.get('looseness',0 if dialect=='swiss' else .65)
    if isinstance(looseness,bool) or not isinstance(looseness,(int,float)) or not math.isfinite(looseness) or not 0<=looseness<=1:raise ValueError('looseness must be finite within 0..1')
    if dialect=='swiss' and looseness!=0:raise ValueError('swiss requires looseness=0')
    if opts.get('skeleton','auto') not in ('auto','bands',*SKELETONS):raise ValueError('Unknown skeleton')
    if opts.get('halftone','off') not in ('off','auto'):raise ValueError('halftone must be off or auto')
    if 'surface_seed' in opts and (not isinstance(opts['surface_seed'],int) or isinstance(opts['surface_seed'],bool)):raise ValueError('surface_seed must be an integer')
    if not isinstance(opts.get('annotations',[]),list):raise ValueError('annotations must be a list')
    if dialect=='swiss' and opts.get('skeleton','auto') not in ('auto','bands'):raise ValueError('Regional skeletons require collage or doodle')
    footer=spec['content'].get('footer')
    evidence=opts.get('colophon_source')
    if evidence is not None:
        if not isinstance(evidence,str) or footer!=evidence:raise ValueError('colophon_source must be the exact supplied footer, without additions')
    document=opts.get('source_document')
    if document is not None:
        if not isinstance(document,str):raise ValueError('source_document must be the original supplied text')
        if footer and re.sub(r'\s+','',footer) not in re.sub(r'\s+','',document):raise ValueError('Colophon does not occur in supplied source_document')
    # Reject these recognizable production claims unless independently supplied
    # in the explicit source record. No general claim of fact verification.
    if footer and re.search(r'No statistics in this draft|Printed in .+ inks on|recycled stock',footer,re.I) and document is None:
        raise ValueError('Production/editor commentary in footer needs original source_document evidence')
    return dialect,float(looseness)


def make_plan(spec):
    from poster_direction import ARCHETYPES,INKS,content_roles,select_archetype,digest,foreground,contrast
    dialect,looseness=settings(spec);opts=spec['art_direction'];c=spec['content'];seed=spec.get('meta',{}).get('seed',1)
    if not isinstance(seed,int) or isinstance(seed,bool):raise ValueError('seed must be an integer')
    rng=random.Random(seed);surface_rng=random.Random(opts.get('surface_seed',seed)+7919)
    policy=copy.deepcopy(DIALECTS[dialect]);canvas=poster_canvas(spec.get('canvas'));W,H=canvas.width,canvas.height
    x,y,x1,y1=canvas.safe;w=x1-x;gap=max(40,W*.05)
    roles=content_roles(c,opts.get('roles'));words=sum(word_count(r['text']) for r in roles)
    density='dense' if words>180 else 'medium' if words>65 else 'sparse'
    arch,reason=select_archetype(c,roles,density)
    if opts.get('archetype','auto')!='auto':arch=opts['archetype'];reason='explicit source-checked archetype'
    if arch not in ARCHETYPES:raise ValueError('Unknown archetype')
    for a,key in [('numeral-hero','key_number'),('statement','quote')]:
        if arch==a and not c.get(key):raise ValueError(a+' requires supplied '+key)
    if arch=='diagram-hero' and not any(c.get(k) for k in ('chart','process','comparison')):raise ValueError('diagram-hero requires a supplied relationship')
    if c.get('image'):raise ValueError('Supplied image remains on legacy image_led route')
    ink=opts.get('ink','cobalt-vermilion')
    if ink not in INKS:raise ValueError('Unknown ink plan')
    inks=copy.deepcopy(INKS[ink]);inks.update(name=ink,multiply=False,solid_blocks=True,multiply_rendering='editable simulated ink plates')
    text_secondary=inks['main'][1]
    while contrast(text_secondary,inks['paper'])<5.5 or contrast(text_secondary,'D4CEC2')<4.5:
        text_secondary=''.join(f'{round(int(text_secondary[j:j+2],16)*.9):02X}' for j in (0,2,4))
    body=float(opts.get('body_size',18 if density=='dense' else 20 if density=='medium' else 24))
    if not math.isfinite(body) or body<16:raise ValueError('body_size must be finite and >=16pt')
    fonts={'display_latin':'Arial Black'};fonts.update(spec.get('meta',{}).get('fonts') or {})
    theme=rk.Theme(palette='A',lang=spec.get('meta',{}).get('lang','en'),fonts=fonts)
    skeleton=opts.get('skeleton','auto')
    if skeleton=='auto':skeleton=SKELETONS[seed%2]
    if skeleton=='bands':raise ValueError('collage/doodle need a regional skeleton; use swiss for bands')
    p={'version':'3.4','dialect':dialect,'looseness':looseness,'dialect_policy':policy,'seed':seed,'skeleton':skeleton,
       'source_sha256':digest(c),'content_roles':roles,'archetype':arch,'selection_reason':reason,'density':density,'content_words':words,
       'canvas':canvas.to_dict(),'fonts':theme.fonts,'font_diagnostics':theme.font_diagnostics,'ink_plan':inks,'objects':[],'overlaps':[],
       'micro_layer':[],'regions':[],'reading_order':[],'parallel_sets':[{'source':k,'n':len(c[k])} for k in ('blocks','process','comparison') if c.get(k)],
       'hero':{'kind':arch,'source':'title','object_ids':[]},'scale_ladder':{'body':body,'detail':16,'heading':body*1.25,'lead':body*1.5,'hero':body*4},
       'constraints':{'body_min':16,'decor_cap':.40,'accent_cap':.08,'max_highlights':2,'max_nonstructural_repeat':2,'max_edge_void':.30,'quiet_region_min':.015},
       'revision':opts.get('revision',0),'review_changes':opts.get('review_changes',[]),'columns':2,
       'provenance':{'footer':'source_document verified' if opts.get('source_document') is not None else 'content.footer supplied; external provenance unverified'}}
    objects=p['objects'];used=set();module_records=[]
    def add(o):o.setdefault('layer','skeleton');o.setdefault('rotation',0);objects.append(o);return o
    def measure(text,width,size,bold=False,display=False,font=None):
        font=font or (theme.f_heading if re.search(r'[\u3400-\u9fff]',text) else theme.f_display if display else theme.f_body)
        size=max(16,math.floor(size*2)/2)
        return tf.fit(text,font,size,width,H*8,minimum=size,bold=bold,ls=.90 if display else 1.08)
    def put(id,text,xx,yy,width,size,role,source=None,bold=False,display=False,color=None,bg=None,font=None):
        f=measure(text,width,size,bold,display,font)
        o=add(dict(id=id,kind='text',text=text,source=source,role=role,rect=[xx,yy,xx+width,yy+f.height],fit=f.to_dict(),color=color or inks['body'],background=bg or inks['paper']))
        if source:used.add(source)
        return o
    def plate(id,rect,color,role='support',**kw):return add(dict(id=id,kind='rect',rect=list(rect),fill=color,role=role,**kw))
    def declare(a,b,reason):p['overlaps'].append(dict(objects=[a['id'],b['id']],reason=reason,min_contrast=4.5))
    top=y
    if c.get('subtitle'):
        o=put('masthead',c['subtitle'],x,top,w,16,'meta','subtitle');top=o['rect'][3]+12
    title=c['title'];frags=opts.get('title_lines')
    if frags:
        if not isinstance(frags,list) or any(not isinstance(a,str) or not a.strip() for a in frags) or re.sub(r'\s+','',''.join(frags))!=re.sub(r'\s+','',title):raise ValueError('title_lines must preserve source title')
    else:
        tokens=title.split();mid=max(1,len(tokens)//2)
        frags=[' '.join(tokens[:mid]),' '.join(tokens[mid:])] if len(tokens)>2 else [title]
        if len(frags)==1 and len(title)>8 and re.search(r'[\u3400-\u9fff]',title):frags=[title[:len(title)//2],title[len(title)//2:]]
    title_objects=[]
    # Headline sizing is content-derived. Compact archetypes leave room for the
    # semantic hero; no fixed two-line slot or prescribed artwork coordinates.
    for i,frag in enumerate(frags):
        font=theme.f_heading if re.search(r'[\u3400-\u9fff]',frag) else theme.f_display
        limit=66 if arch in ('numeral-hero','diagram-hero','statement') else 98
        sz=min(limit,(w-42)*.93/max(tm.advance(frag,font,100,True)/100,.01))
        if title_objects:
            previous=title_objects[-1];pf=previous['fit'];po,ph=tm.ink_band(previous['text'],pf['font'],pf['size'],True,pf['ls'])
            nf=measure(frag,w-18,sz,True,True);no,nh=tm.ink_band(frag,nf.font,nf.size,True,nf.ls)
            top=previous['rect'][1]+po+ph+max(9,sz*.10)-no
        o=put('title-'+str(i),frag,x+6*(i%2),top,w-18,sz,'hook','title',True,True,text_secondary if dialect=='collage' and i%2 else inks['main'][0]);title_objects.append(o)
        o['source_part']=i
        top=o['rect'][3]+2
    top+=gap
    # Footer is measured from exact source. It is not an authoring sandbox.
    bottom=y1
    if c.get('footer'):
        f=measure(c['footer'],w,16);bottom-=f.height
        put('colophon',c['footer'],x,bottom,w,16,'source','footer');bottom-=gap
    # Reserve a real navigation gutter within the safe area.
    x+=26;w-=26
    # Group semantic leaves without inventing a label, number, quote or unit.
    groups=[];group_by={}
    for r in roles:
        if r['source'] in used:continue
        if r['source']=='body':
            for j,t in enumerate(re.split(r'\n\s*\n',r['text'])):
                if t:groups.append({'id':'body-'+str(j),'rows':[dict(r,text=t,id=r['id']+'-part'+str(j))]})
        else:
            key=r.get('group',r['source'])
            if key not in group_by:group_by[key]={'id':key,'rows':[]};groups.append(group_by[key])
            group_by[key]['rows'].append(r)
    hero_key='key_number' if arch=='numeral-hero' else 'quote' if arch=='statement' else ('chart' if c.get('chart') else 'process' if c.get('process') else 'comparison') if arch=='diagram-hero' else None
    hero_groups=[m for m in groups if m['id']==hero_key or hero_key in ('process','comparison') and m['id'].startswith(hero_key+'.')]
    for m in hero_groups:groups.remove(m)
    # A type hero already exists above. Region hero remains tied to a meaningful
    # supplied hook/module instead of introducing decorative filler.
    if not hero_groups and groups:
        candidate=next((m for m in groups if m['id']=='quote'),groups[0]);hero_groups=[candidate];groups.remove(candidate)
    p['hero']['source']=hero_key or 'title'
    def row_size(r,hero=False,width=None):
        if hero and r['source'] in ('key_number','key_number.value'):return 132
        if hero and r['source'] in ('quote','quote.text'):
            size=64 if density=='dense' else 76 if density=='medium' else 96
            if width:
                # Keep a short final fragment from becoming an isolated
                # display line; adjust scale without changing source copy.
                while size>max(40,body*1.5):
                    fitted=measure(r['text'],width,size,True,True)
                    widths=[tm.advance(line,fitted.font,fitted.size,True,fitted.spc) for line in fitted.lines]
                    if len(widths)<2 or widths[-1]>=max(widths)*.45:break
                    size-=2
            return size
        if r['role']=='source':return 16
        if r['source'].endswith(('.title','.value')):return body*1.25
        if r['source']=='cta':return body*1.25
        return body
    def module_size(m,width,hero=False):
        total=0
        for r in m['rows']:
            sz=row_size(r,hero,width);bold=r['source'].endswith(('.title','.value')) or r['source']=='cta' or hero and r['role']=='hook'
            f=measure(r['text'],width,sz,bold,hero and r['role'] in ('hero_stat','hook'))
            total+=f.height+7
            if r['source'].startswith('chart.items.') and r['source'].endswith('.value'):total+=26
        return total+12
    def render_module(m,rect,hero=False):
        xx,yy,xx1,yy1=rect;width=xx1-xx;start=len(objects);cy=yy
        for r in m['rows']:
            sz=row_size(r,hero,width);bold=r['source'].endswith(('.title','.value')) or r['source']=='cta' or hero and r['role']=='hook'
            ob=put(r['id'],r['text'],xx,cy,width,sz,r['role'],r['source'],bold,hero and r['role'] in ('hero_stat','hook'),inks['main'][0] if hero or r['role']=='cta' else None)
            if '-part' in r['id']:ob['source_part']=int(r['id'].rsplit('-part',1)[1])
            cy=ob['rect'][3]+7
            if hero:p['hero']['object_ids'].append(ob['id'])
            if r['source'].startswith('chart.items.') and r['source'].endswith('.value'):
                value=float(r['text']);peak=max(float(a['value']) for a in c['chart']['items']) or 1
                if value>0:plate('bar-'+r['id'],(xx,cy,xx+width*value/peak,cy+14),inks['main'][1],'data')
                cy+=26
        actual=[xx,yy,xx1,cy+5];record={'id':m['id'],'rect':actual,'objects':[o['id'] for o in objects[start:]],'hero':hero}
        module_records.append(record);p['regions'].append(record);return cy+5
    # Measured regional packing: variable column split and mirrored weighting
    # change with seed, independently of surface jitter and palette.
    ratio=.52+(seed%6)*.02;leftw=(w-gap)*ratio;rightw=w-gap-leftw
    if skeleton=='asymmetric-notes':
        left=[*hero_groups,*[m for m in groups if m['id'].startswith('body-') or m['id']=='cta']]
        right=[m for m in groups if m not in left]
        if not right and len(left)>1:right=[left.pop()]
        def needed(members,width):return sum(module_size(m,width,m in hero_groups) for m in members)+gap*max(0,len(members)-1)
        for _ in range(len(groups)):
            if needed(left,leftw)<=bottom-top and needed(right,rightw)<=bottom-top:break
            src,dst,sw,dw=(left,right,leftw,rightw) if needed(left,leftw)>bottom-top else (right,left,rightw,leftw)
            movable=[m for m in reversed(src) if m not in hero_groups and needed([*dst,m],dw)<=bottom-top]
            if not movable:break
            m=movable[0];src.remove(m);dst.append(m)
        for col,(members,xx,width) in enumerate(((left,x,leftw),(right,x+leftw+gap,rightw))):
            heights=[module_size(m,width,m in hero_groups) for m in members]
            need=sum(heights)+gap*max(0,len(members)-1)
            if need>bottom-top:raise ValueError(f'{skeleton} region {col} needs {need:.1f}pt, has {bottom-top:.1f}; revise body_size/region or content allocation')
            cy=top+(min(36,(bottom-top-need)*.25) if col else 0)
            for m,height in zip(members,heights):
                render_module(m,(xx,cy,xx+width,cy+height),m in hero_groups);cy+=height+gap
    else:
        # A source-bound hero occupies the centre. Optional short modules sit
        # above it, remaining ordered modules orbit below in unequal columns.
        topmods=[]
        for m in groups:
            if m['id']!='cta' and module_size(m,min(leftw,rightw))<150 and len(topmods)<2:topmods.append(m)
        hero_width=w*(.76 if density=='dense' else .72);hx=x+(w-hero_width)/2
        hero_h=sum(module_size(m,hero_width,True) for m in hero_groups)+gap*max(0,len(hero_groups)-1)
        upper_h=max([module_size(m,leftw if i==0 else rightw) for i,m in enumerate(topmods)]+[0])
        hy=top+(upper_h+gap if topmods else 0)
        remaining=[m for m in groups if m not in topmods]
        lows=[hy+hero_h+gap,hy+hero_h+gap]
        # Verify capacity before adding objects; don't silently fall back to bands.
        placements=[]
        for m in remaining:
            col=min(range(2),key=lambda i:lows[i]+module_size(m,(leftw,rightw)[i]))
            width=(leftw,rightw)[col];mh=module_size(m,width);xx=(x,x+leftw+gap)[col]
            placements.append((m,[xx,lows[col],xx+width,lows[col]+mh]));lows[col]+=mh+gap
        if max(lows,default=hy+hero_h)-gap>bottom:raise ValueError('central-orbit has insufficient measured space; use asymmetric-notes or smaller hero allocation')
        for i,m in enumerate(topmods):
            xx=(x,x+leftw+gap)[i];width=(leftw,rightw)[i];render_module(m,[xx,top,xx+width,top+upper_h])
        for m in hero_groups:
            mh=module_size(m,hero_width,True);render_module(m,[hx,hy,hx+hero_width,hy+mh],True);hy+=mh+gap
        for m,rect in placements:render_module(m,rect)
    p['hero']['object_ids']=p['hero']['object_ids'] or [o['id'] for o in title_objects]
    # Explicit navigation is assigned after regional packing, in source order.
    source_rank={r['source']:i for i,r in enumerate(sorted(roles,key=lambda r: (9 if r['role']=='cta' else 7 if r['role'] in ('source','facts','meta') else 4 if r['role']=='parallel_set' else 1 if r['role']=='argument' else 0)))}
    object_by={o['id']:o for o in objects}
    ordered=sorted(module_records,key=lambda m:min([(source_rank.get(object_by[id].get('source'),999),object_by[id].get('source_part',0)) for id in m['objects']]+[(999,0)]))
    for i,m in enumerate(ordered):
        m['order']=i+1
        xx,yy,xx1,yy1=m['rect']
        # The rail sits in the measured gutter, with a native structural number.
        number=put('route-'+str(i+1),str(i+1),max(2,xx-23),yy,22,16,'meta',None,True,color=text_secondary)
        m['navigation']=number['id']
        p['reading_order'].append({'order':i+1,'region':m['id'],'marker':number['id'],'objects':m['objects'],'source_paths':[next(o for o in objects if o['id']==id).get('source') for id in m['objects']]})
    # Surfaces are generated from existing semantic anchors, never page slots.
    def surface(id,kind,rect,anchor,rotation=0,**kw):
        return add(dict(id=id,kind=kind,rect=list(rect),role='surface',layer='surface',anchor=anchor,rotation=rotation,offset=[0,0],**kw))
    def behind(o,targets):
        objects.remove(o);at=min(objects.index(t) for t in targets);objects.insert(at,o)
        for t in targets:declare(t,o,'anchored editable backing')
    # Preserve explicit source process relationships as native arrows in the
    # navigation gutter. Endpoints reference region identifiers in the plan.
    process_regions=sorted([m for m in module_records if m['id'].startswith('process.')],key=lambda m:int(m['id'].split('.')[1]))
    for i,(a,b) in enumerate(zip(process_regions,process_regions[1:])):
        ax,ay,ax1,ay1=a['rect'];bx,by,bx1,by1=b['rect']
        if abs(ax-bx)<1 and by>ay1:
            cx=ax-12;start=ay1+3;end=by-5
            paths=[[[cx,start],[cx,end]],[[cx-4,end-7],[cx,end],[cx+4,end-7]]]
            arrow=surface('sequence-arrow-'+str(i),'path',bounds(paths),a['id'],line=inks['main'][1],line_width=1.5,paths=paths,anchor_kind='sequence',vocabulary='arrow',connects=[a['id'],b['id']])
            p['overlaps'].append({'objects':[arrow['id'],a['id'],b['id']],'reason':'source process order in navigation gutter'})
    surface_count=Counter();papermax=round(policy['paper'][1]*looseness);tapemax=round(policy['tape'][1]*looseness)
    title_candidates=[{'id':o['id'],'rect':[o['rect'][0],o['rect'][1],o['rect'][0]+o['fit']['width']+16,o['rect'][3]],'objects':[o['id']],'hero':True} for o in title_objects]
    candidates=title_candidates+module_records
    surface_rng.shuffle(candidates)
    if dialect=='collage' and title_candidates:
        lead=surface_rng.choice(title_candidates);candidates.remove(lead);candidates.insert(0,lead)
    for m in candidates:
        if surface_count['paper']>=papermax:break
        targets=[o for o in objects if o['id'] in [*m['objects'],m.get('navigation')] and o['kind']=='text']
        if not targets:continue
        xx,yy,xx1,yy1=m['rect'];ww=xx1-xx;hh=yy1-yy
        # Large backings stay horizontal. Clear diagonals belong to bounded
        # short strips, so tilted paper cannot cross another paragraph.
        angle=surface_rng.choice(policy['angles'][1:]) if hh<100 and ww<400 else 0
        color=inks['paper'] if dialect=='doodle' else ''.join(f'{round(int(inks["main"][1][j:j+2],16)*.13+int(inks["paper"][j:j+2],16)*.87):02X}' for j in (0,2,4))
        if m['id'].startswith('title-'):
            f=targets[0]['fit'];off,ih=tm.ink_band(targets[0]['text'],f['font'],f['size'],f['bold'],f['ls'])
            yy+=off;yy1=yy+ih
        rect=[xx-6,yy-2,xx1+5,yy1+2] if m['id'].startswith('title-') else [xx-6,yy-5,xx1+5,yy1+5]
        paper=surface('paper-'+m['id'],'path',rect,m['id'],angle,fill=color,closed=True,paths=[torn(rect,surface_rng.randrange(10**9))],anchor_kind='backing',vocabulary='paper')
        if m['id'].startswith('title-'):targets=list(title_objects)
        behind(paper,targets);surface_count['paper']+=1
        # A quantized shadow supplies a physical anchor for a tilted paper.
        shadow=copy.deepcopy(paper);shadow.update(id='shadow-'+m['id'],fill='D4CEC2',offset=[3,3],anchor=paper['id'],anchor_kind='shadow',vocabulary='shadow')
        shadow['rect']=[a+3 for a in shadow['rect']];shadow['paths']=[[[a+3,b+3] for a,b in path] for path in shadow['paths']]
        add(shadow);behind(shadow,[paper,*targets])
        if surface_count['tape']<tapemax and not m['id'].startswith('title-') and surface_rng.random()<.85:
            tw=min(68,ww*.3);tx=xx+ww*surface_rng.choice([.2,.65]);ty=yy-10
            tr=[tx,ty,tx+tw,ty+17]
            tape=surface('tape-'+m['id'],'path',tr,paper['id'],surface_rng.choice(policy['angles'][1:]),fill=inks['main'][1],opacity=28,closed=True,paths=[torn(tr,surface_rng.randrange(10**9),6)],anchor_kind='tape',vocabulary='tape')
            # Tape sits above the paper but below all content; source stays clear.
            behind(tape,targets);surface_count['tape']+=1
    # A short hook/figure/label can be a sticker or outlined stamp. The text
    # remains native and horizontal; only its physical backing may tilt.
    if looseness>=.4:
        slots=[o for o in objects if o['kind']=='text' and o.get('source') and o['role'] in ('hook','hero_stat','cta') and len(o['fit']['lines'])==1 and o['fit']['width']<260 and o['fit']['size']<80]
        if slots:
            target=surface_rng.choice(slots);f=target['fit'];xx,yy,xx1,yy1=target['rect'];off,ih=tm.ink_band(target['text'],f['font'],f['size'],f['bold'],f['ls'])
            rect=[xx-7,yy+off-6,xx+f['width']+10,yy+off+ih+6]
            stamp=opts.get('micro_style')=='stamp'
            sticker=surface('sticker-'+target['id'],'path',rect,target['id'],0,fill=None if stamp else inks['paper'],line=inks['main'][1],line_width=2,closed=True,paths=[torn(rect,surface_rng.randrange(10**9),10)],anchor_kind='sticker',vocabulary='stamp' if stamp else 'sticker',text_slot={'source':target['source'],'object':target['id']})
            behind(sticker,[target]);surface_count['sticker']+=1
    # Source-word doodles use exact measured glyph positions. Defaults select
    # semantic hooks/figures; explicit highlights retain the v3.3 source contract.
    highlights=opts.get('highlights')
    if highlights is not None and (not isinstance(highlights,list) or len(highlights)>2):raise ValueError('At most two exact highlights')
    marks=[]
    if highlights is not None:
        for mark in highlights:
            if not isinstance(mark,dict) or set(mark)-{'source','text','kind'} or not all(mark.get(k) for k in ('source','text')):raise ValueError('Invalid highlight')
            kind=mark.get('kind','underline')
            if kind not in ('line','circle','underline','arrow','star','bracket','wave'):raise ValueError('Unknown source mark kind')
            target=next((o for o in objects if o['kind']=='text' and o.get('source')==mark['source'] and any(mark['text'] in line for line in o['fit']['lines'])),None)
            if not target:raise ValueError('Highlight must bind a measured source substring')
            marks.append((target,mark['text'],kind))
    else:
        targets=[o for o in objects if o['kind']=='text' and o.get('source') and (o['role'] in ('hero_stat','hook') or o['source'].endswith('.title')) and (not o['id'].startswith('title-') or o is title_objects[-1])]
        surface_rng.shuffle(targets)
        for target in targets[:round(policy['doodle'][1]*looseness)]:
            f=target['fit'];line=max(f['lines'],key=len)
            token=max(re.findall(r'[A-Za-z]+|[0-9]+',line),key=len,default=line[:4])
            kind='circle' if target['role']=='hero_stat' and len(line)<10 else surface_rng.choice(['underline','wave','bracket'])
            marks.append((target,token,kind))
    from poster_primitives import stroke_segments,planned_glyphs
    from layout import segment_rect_distance,intersection,inflate
    glyph_boxes=[r for ob in objects if ob['kind']=='text' for r in planned_glyphs(ob)]
    for i,(target,token,kind) in enumerate(marks):
        f=target['fit']
        if len(f['lines'])>1 and f['size']>=40 and kind in ('line','underline','wave'):
            if highlights is not None:raise ValueError('Multiline display underline needs renderer-specific baseline evidence; use a bracket or another exact source word')
            kind='bracket'
        line=next(a for a in f['lines'] if token in a);li=f['lines'].index(line)
        xx=target['rect'][0]+tm.advance(line[:line.index(token)],f['font'],f['size'],f['bold'],f['spc'])
        width=tm.advance(token,f['font'],f['size'],f['bold'],f['spc']);off,ih=tm.ink_band(token,f['font'],f['size'],f['bold'],f['ls'])
        yy=target['rect'][1]+li*f['pitch']+off
        if kind in ('underline','wave'):
            lo,lh=tm.ink_band(line,f['font'],f['size'],f['bold'],f['ls']);yy=target['rect'][1]+li*f['pitch']+lo;ih=lh
        end=target['rect'][0]+tm.advance(line,f['font'],f['size'],f['bold'],f['spc'])
        rect=[xx-width*.24-7,yy-ih*.18-5,xx+width*1.24+7,yy+ih*1.18+5] if kind=='circle' else [xx,yy+ih+6,xx+width,yy+ih+10] if kind in ('underline','wave','line') else [end+8,yy+ih*.25,end+23,yy+ih*.25+15] if kind=='star' else [end+8,yy-3,end+13,yy+ih+3]
        if kind=='circle':
            # LibreOffice can place large display figures above the FreeType
            # ink band. Enclose the line origin too, rather than trusting a
            # single renderer's ascender offset for the top arc.
            rect[1]=min(rect[1],target['rect'][1]+li*f['pitch']-max(12,f['size']*.18))
        paths=ink_path(kind,rect,surface_rng.randrange(10**9),.75)
        stroke=dict(paths=paths,smooth=kind not in ('bracket','star'))
        region=inflate(bounds(paths),3);nearby=[g for g in glyph_boxes if intersection(region,g)]
        if any(segment_rect_distance(a,b,g)<1.3 for a,b in stroke_segments(stroke) for g in nearby):
            if highlights is not None:raise ValueError('Explicit source mark has no glyph-safe space; choose another exact keyword')
            p.setdefault('surface_omissions',[]).append({'source':target['source'],'kind':kind,'reason':'stroke would cross glyphs'})
            continue
        mark=surface('mark-'+str(i),'path',bounds(paths,1),target['id'],line=inks['main'][1],line_width=1.5,paths=paths,smooth=kind not in ('bracket','star'),vocabulary=kind,keyword=token,source=target['source'],anchor_kind='source-word')
        declare(target,mark,'source-bound stroke outside glyphs');surface_count['doodle']+=1
    # Headline misregistration uses native duplicate text, with an explicit
    # original anchor. Body/figures/numbered navigation never rotate.
    if looseness>0:
        for title_obj in title_objects:
            duplicate=copy.deepcopy(title_obj);shift=3 if looseness<.8 else 6
            duplicate.update(id='ink-'+title_obj['id'],source=None,duplicate_of=title_obj['id'],layer='surface',anchor=title_obj['id'],anchor_kind='ink-layer',offset=[shift,0],vocabulary='overprint',role='ink-layer',color=inks['main'][1])
            duplicate['rect']=[title_obj['rect'][0]+shift,title_obj['rect'][1],title_obj['rect'][2]+shift,title_obj['rect'][3]]
            add(duplicate);behind(duplicate,[title_obj])
    # Optional exact handwritten annotation: visible source substring only.
    cjk_annotation=any(re.search(r'[\u3400-\u9fff]',a.get('text','')) for a in opts.get('annotations',[]) if isinstance(a,dict))
    chain=['KaiTi','Microsoft YaHei',theme.f_heading,theme.f_body] if cjk_annotation else ['Segoe Print','Comic Sans MS',theme.f_heading,theme.f_body]
    resolved=next((font for font in chain if tm.resolve(font)),theme.f_body)
    p['annotation_font']={'requested_chain':chain,'resolved':resolved,'handwritten_available':resolved in ('KaiTi','Segoe Print','Comic Sans MS')}
    annotations=opts.get('annotations',[])
    if not isinstance(annotations,list) or len(annotations)>2:raise ValueError('annotations allows at most two source phrases')
    for i,a in enumerate(annotations):
        if not isinstance(a,dict) or set(a)!={'source','text'} or not a['text']:raise ValueError('Invalid annotation')
        target=next((o for o in objects if o['kind']=='text' and o.get('source')==a['source'] and a['text'] in o['text']),None)
        if not target:raise ValueError('Annotation must be an exact source substring')
        # Find measured free interval beneath the target. Reject rather than
        # cover another module or invent a shortened note.
        yy=target['rect'][3]+10;width=target['rect'][2]-target['rect'][0]
        note=put('annotation-'+str(i),a['text'],target['rect'][0],yy,width,16,'annotation',None,font=resolved,color=text_secondary)
        note.update(layer='surface',anchor=target['id'],anchor_kind='source-annotation',vocabulary='annotation',annotation_source=a['source'],offset=[0,0])
        for pair in list(p['overlaps']):
            if target['id'] in pair['objects']:
                for oid in pair['objects']:
                    backing=next((ob for ob in objects if ob['id']==oid and ob.get('fill')),None)
                    if backing:declare(note,backing,'exact source annotation shares its content backing')
    # Register marks live in the trim margin, not beside body paragraphs.
    for i,(xx,yy) in enumerate(((x*.45,y*.4),(W-x*.45,H-y*.4))):
        paths=[[[xx-7,yy],[xx+7,yy]],[[xx,yy-7],[xx,yy+7]]]
        surface('register-'+str(i),'path',bounds(paths),'canvas',line=inks['main'][i],line_width=.7,paths=paths,vocabulary='register',anchor_kind='trim')
    if opts.get('halftone','off')=='auto':
        # Find a substantial clear edge region. Failure means omit, never
        # shrink the field into residual-looking edge confetti.
        from poster_primitives import halftone_paths
        field_w=W*.16;field_h=H*.18;field=None
        for cy in (bottom-field_h-gap,top+H*.12,top+H*.35):
            for cx in (-canvas.bleed,W-field_w+canvas.bleed):
                rect=[cx,cy,cx+field_w,cy+field_h]
                if cy>=top and cy+field_h<=bottom and not any(intersection(inflate(rect,10),g) for g in glyph_boxes):
                    field=rect;break
            if field:break
        if field:
            paths=halftone_paths(field,spacing=14)
            anchor=min(module_records,key=lambda m:abs((m['rect'][1]+m['rect'][3])/2-(field[1]+field[3])/2))['id'] if module_records else title_objects[-1]['id']
            surface('large-halftone','path',bounds(paths),anchor,fill=inks['main'][1],closed=True,paths=paths,smooth=True,vocabulary='halftone',anchor_kind='edge-rhythm',bleed=True)
            p['overlaps'].append({'objects':['large-halftone','canvas'],'reason':'declared large edge bleed, clear of reading glyphs'})
        else:p.setdefault('surface_omissions',[]).append({'kind':'halftone','reason':'no substantial clear edge region; no small substitute'})
    p['surface_counts']=dict(surface_count)
    p['surface_budget']={kind:[0,round(policy[kind][1]*looseness)] for kind in ('doodle','paper','tape')}
    p['micro_layer']=[{'kind':k,'count':n,'role':'source anchored surface'} for k,n in surface_count.items()]
    p['scale_ladder']['actual']=sorted({o['fit']['size'] for o in objects if o['kind']=='text'},reverse=True)
    p['composition_signature']=digest([(m['id'],m['rect']) for m in module_records])
    return p


def validate_plan(p):
    """Structural surface contract, also called against actual saved objects."""
    issues=[];by={o['id']:o for o in p['objects']};policy=DIALECTS[p.get('dialect','swiss')]
    for o in p['objects']:
        rot=o.get('rotation',0);offset=o.get('offset',[0,0])
        if o.get('layer')=='surface':
            if o.get('vocabulary') not in policy['vocabulary']:issues.append('Vocabulary outside dialect: '+o['id'])
            if o.get('anchor') not in by and o.get('anchor') not in {r['id'] for r in p.get('regions',[])} and o.get('anchor')!='canvas':issues.append('Missing surface anchor: '+o['id'])
            if rot not in policy['angles']:issues.append('Non-discrete surface angle: '+o['id'])
            q=policy['offset_quantum']
            if any(not math.isfinite(v) or (q and abs(v/q-round(v/q))>1e-6) or (not q and v) for v in offset):issues.append('Non-quantized offset: '+o['id'])
            if rot and o.get('anchor_kind') not in ('backing','shadow','tape','sticker'):issues.append('Tilt without physical anchor: '+o['id'])
            if o.get('annotation_source'):
                original=next((r['text'] for r in p['content_roles'] if r['source']==o['annotation_source']),None)
                if not original or o['text'] not in original:issues.append('Annotation is not an exact source phrase: '+o['id'])
            if o.get('keyword'):
                original=next((r['text'] for r in p['content_roles'] if r['source']==o.get('source')),None)
                if not original or o['keyword'] not in original:issues.append('Mark keyword has no source: '+o['id'])
        elif rot:issues.append('Skeleton rotation must be zero: '+o['id'])
        if o.get('kind')=='text' and o.get('role') in ('argument','parallel_set','hero_stat','facts','meta') and rot:issues.append('Reading text rotated: '+o['id'])
    order=p.get('reading_order',[])
    if p.get('dialect','swiss')!='swiss':
        if [r['order'] for r in order]!=list(range(1,len(order)+1)):issues.append('Reading order is not sequential')
        if {r['region'] for r in order}!={r['id'] for r in p.get('regions',[])}:issues.append('Reading order misses regions')
        for r in order:
            if r.get('marker') not in by or by[r['marker']].get('text')!=str(r['order']):issues.append('Missing reading-order marker')
        for kind,limits in p.get('surface_budget',{}).items():
            actual=sum(o.get('vocabulary')==kind if kind!='doodle' else o.get('anchor_kind')=='source-word' for o in p['objects'])
            if actual>limits[1]:issues.append('Surface budget exceeded: '+kind)
    return issues

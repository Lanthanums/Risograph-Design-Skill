"""Source-bound composition planning, before text fitting. Poster-only v3.3 path.

Coordinates are derived from canvas, roles and measured content; no sample art.
The JSON plan is the drawing contract, including explicit overlap pairs.
"""
import copy
import hashlib
import itertools
import json
import math
import re
from functools import lru_cache
from pathlib import Path
import typefit as tf
import textmetrics as tm
import riso_kit as rk
from canvas import poster_canvas
from place_decor import word_count

ARCHETYPES = {
    'type-hero': {'ratio': 5.5, 'hero_share': .34, 'decor_cap': .18},
    'numeral-hero': {'ratio': 9, 'hero_share': .30, 'decor_cap': .22},
    'diagram-hero': {'ratio': 4, 'hero_share': .32, 'decor_cap': .25},
    'banded': {'ratio': 5, 'hero_share': .32, 'decor_cap': .40},
    'staggered-modules': {'ratio': 4.5, 'hero_share': .28, 'decor_cap': .20},
    'statement': {'ratio': 4.8, 'hero_share': .40, 'decor_cap': .22},
}
INKS = {
    'cobalt-vermilion': {'main':['25488A','CA553D'],'accent':'F2BD4C','paper':'F5EEDD','body':'20252D'},
    'plum-ochre': {'main':['65385C','AA7135'],'accent':'C6D958','paper':'F4EEE4','body':'29232A'},
    'teal-coral': {'main':['166267','B94E61'],'accent':'EECF62','paper':'F0EFE1','body':'172E31'},
}
from poster_contract import ROLES

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def rgb(h):
    return tuple(int(h.lstrip('#')[i:i+2],16) for i in (0,2,4))

def multiply(a,b):
    return ''.join(f'{round(x*y/255):02X}' for x,y in zip(rgb(a),rgb(b)))

def contrast(a,b):
    def lum(h):
        v=[x/255 for x in rgb(h)]
        v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
        return sum(x*y for x,y in zip(v,(.2126,.7152,.0722)))
    lo,hi=sorted((lum(a),lum(b)))
    return (hi+.05)/(lo+.05)

def foreground(bg,inks):
    return max((inks['paper'],inks['body']),key=lambda c:contrast(c,bg))

def content_roles(content, overrides=None):
    """Leaf text and exact source paths; no paraphrasing or number inference."""
    result=[]
    def add(path,value,role,group=None):
        if value is None or str(value)=='':return
        result.append({'id':path,'source':path,'text':tf.source_text(value),'role':role,**({'group':group} if group else {})})
    for key in ('title','subtitle','body','cta','footer','date','venue','attribution'):
        role={'title':'hook','subtitle':'meta','body':'argument','cta':'cta','footer':'source','date':'facts','venue':'facts','attribution':'source'}[key]
        add(key,content.get(key),role,'event-facts' if key in ('date','venue') else None)
    for key,role,fields in (('key_number','hero_stat',('value','label')),('quote','hook',('text','attribution'))):
        raw=content.get(key)
        if isinstance(raw,dict):
            for field in fields:add(key+'.'+field,raw.get(field),'source' if field=='attribution' else role,key)
        else:add(key,raw,role,key)
    for key in ('blocks','data','process','comparison'):
        for i,row in enumerate(content.get(key,[])):
            if isinstance(row,dict):
                for field in (('value','label') if key=='data' else ('title','label','text','value')):
                    if field in row:add(f'{key}.{i}.{field}',row[field],'parallel_set' if key!='data' else 'facts',f'{key}.{i}')
            else:add(f'{key}.{i}',row,'parallel_set',f'{key}.{i}')
    raw=content.get('metadata')
    if isinstance(raw,dict):
        for k,v in raw.items():add('metadata.'+k,k+': '+str(v),'meta','metadata')
    elif isinstance(raw,list):
        for i,v in enumerate(raw):add(f'metadata.{i}',v,'meta','metadata')
    else:add('metadata',raw,'meta')
    chart=content.get('chart')
    if chart:
        add('chart.title',chart.get('title'),'facts','chart')
        add('chart.unit',chart.get('unit'),'facts','chart')
        for i,row in enumerate(chart['items']):
            add(f'chart.items.{i}.label',row['label'],'facts','chart')
            add(f'chart.items.{i}.value',row['value'],'hero_stat','chart')
    for path,role in (overrides or {}).items():
        if role not in ROLES:raise ValueError('Unknown semantic role '+str(role))
        found=[r for r in result if r['source']==path]
        if not found:raise ValueError('Role override has no source: '+path)
        found[0]['role']=role
    return result

def select_archetype(content,roles,density):
    if content.get('key_number'):return 'numeral-hero','explicit supplied number with its qualifier'
    if content.get('process') or content.get('chart'):return 'diagram-hero','explicit supplied relationship'
    if content.get('quote') and density=='sparse':return 'statement','supplied quotation dominates sparse content'
    if len(content.get('blocks',[]))>=3:return 'staggered-modules','parallel modules need a shared grid'
    if content.get('date') or content.get('venue'):return 'banded','event facts benefit from distinct information bands'
    return 'type-hero','title is the strongest supplied anchor'

def make_plan(spec):
    from poster_flow import make_plan as flow_plan
    return flow_plan(spec)


def _make_v34_plan(spec):
    from poster_dialects import settings,NEW_OPTIONS,make_plan as dialect_plan,DIALECTS,validate_plan
    dialect,looseness=settings(spec)
    opts=spec.get('art_direction',{})
    allowed={'archetype','ink','body_size','hero_share','columns','title_lines','statement_lines','highlights','roles','micro_style','revision','review_changes'}|NEW_OPTIONS
    if set(opts)-allowed:raise ValueError('Unknown art_direction fields: '+str(sorted(set(opts)-allowed)))
    if dialect!='swiss':
        p=dialect_plan(spec)
        errors=validate_plan(p)
        if errors:raise ValueError('; '.join(errors))
        return p
    legacy=copy.deepcopy(spec)
    legacy['art_direction']={k:v for k,v in opts.items() if k not in NEW_OPTIONS}
    p=_make_swiss_plan(legacy)
    p.update(version='3.4',dialect='swiss',looseness=0,skeleton='bands',dialect_policy=copy.deepcopy(DIALECTS['swiss']))
    return p


def _make_swiss_plan(spec):
    opts=spec.get('art_direction',{})
    if not isinstance(opts,dict):raise ValueError('art_direction must be an object')
    allowed={'archetype','ink','body_size','hero_share','columns','title_lines','statement_lines','highlights','roles','micro_style','revision','review_changes'}
    if set(opts)-allowed:raise ValueError('Unknown art_direction fields: '+str(sorted(set(opts)-allowed)))
    c=spec['content'];canvas=poster_canvas(spec.get('canvas'));W,H=canvas.width,canvas.height
    if c.get('image'):raise ValueError('v3.3 composition path does not yet support supplied images; use legacy image_led explicitly')
    roles=content_roles(c,opts.get('roles'))
    words=sum(word_count(r['text']) for r in roles)
    density='dense' if words>180 else 'medium' if words>65 else 'sparse'
    archetype,reason=select_archetype(c,roles,density)
    if opts.get('archetype','auto')!='auto':archetype,reason=opts['archetype'],'explicit art direction; semantic prerequisites checked'
    if archetype not in ARCHETYPES:raise ValueError('Unknown archetype '+str(archetype))
    if archetype=='numeral-hero' and not c.get('key_number'):raise ValueError('numeral-hero requires supplied key_number; numbers are not inferred from prose')
    if archetype=='diagram-hero' and not any(c.get(k) for k in ('chart','process','comparison')):raise ValueError('diagram-hero requires a supplied chart/process/comparison')
    if archetype=='statement' and not c.get('quote'):raise ValueError('statement requires a supplied quotation')
    ink=opts.get('ink','cobalt-vermilion')
    if ink not in INKS:raise ValueError('Unknown ink plan '+str(ink))
    inks=copy.deepcopy(INKS[ink]); inks.update(name=ink,solid_blocks=True,multiply=True,multiply_rendering='editable intersection plates; not an Office blend-mode claim')
    base=ARCHETYPES[archetype]
    body=float(opts.get('body_size',18 if density=='dense' else 22 if density=='medium' else 26))
    if not math.isfinite(body) or body<16:raise ValueError('body_size must be finite and >=16pt')
    hs=float(opts.get('hero_share',base['hero_share']+(.14 if density=='sparse' else 0)))
    if not .18<=hs<=.65:raise ValueError('hero_share must be within .18..65')
    columns=opts.get('columns',3 if archetype=='staggered-modules' and len(c.get('blocks',[]))>=3 and density!='dense' else 2)
    if columns not in (1,2,3) or isinstance(columns,bool):raise ValueError('columns must be 1,2,3')
    if density=='sparse' and not c.get('blocks'):columns=1
    p={'version':'3.3','source_sha256':digest(c),'content_roles':roles,'parallel_sets':[{'source':k,'n':len(c[k])} for k in ('blocks','process','comparison') if c.get(k)],
       'archetype':archetype,'selection_reason':reason,'density':density,'content_words':round(words,1),'canvas':canvas.to_dict(),
       'hero':{'kind':{'numeral-hero':'numeral','diagram-hero':'diagram','statement':'quotation','banded':'ink-band'}.get(archetype,'type'),'source':'key_number' if archetype=='numeral-hero' else 'quote' if archetype=='statement' else 'title','share':hs},
       'scale_ladder':{'hero':body*base['ratio'],'lead':body*1.7,'heading':body*1.3,'body':body,'detail':16},
       'ink_plan':inks,'micro_layer':[],'overlaps':[],'objects':[],
       'constraints':{'body_min':16,'decor_cap':base['decor_cap']-(.02 if density=='dense' else 0),'accent_cap':.08,'max_highlights':2,'max_nonstructural_repeat':2,'max_edge_void':.23 if density=='sparse' else .14,'quiet_region_min':.015 if density=='dense' else .035},
       'revision':opts.get('revision',0),'review_changes':opts.get('review_changes',[]),'columns':columns}
    default_fonts={'display_latin':'Arial Black'}
    default_fonts.update(spec.get('meta',{}).get('fonts') or {})
    theme=rk.Theme(palette='A',lang=spec.get('meta',{}).get('lang','en'),fonts=default_fonts)
    p['fonts']=theme.fonts;p['font_diagnostics']=theme.font_diagnostics
    x,y,x1,y1=canvas.safe;w=x1-x;h=y1-y;gap=max(14,W*.018)
    objs=p['objects'];used=set();count=0
    def box(id,rect,fill,role='support',kind='rect',**kw):
        o={'id':id,'kind':kind,'rect':list(rect),'fill':fill,'role':role,**kw};objs.append(o);return o
    def fittext(id,text,rect,size,role,source=None,bold=False,color=None,bg=None,spc=0):
        xx,yy,xx1,yy1=rect
        # Native PPTX sizes are serialized to hundredths. Keep requested sizes
        # on the same exact half-point grid as the fitter so Pillow rounding
        # cannot cross a pixel boundary after save/reload or cache warm-up.
        size=max(16,math.floor(size*2)/2)
        family=theme.f_heading if re.search(r'[\u3400-\u9fff]',text) else theme.f_display if size>body*1.5 else theme.f_body
        f=tf.fit(text,family,size,xx1-xx,yy1-yy,minimum=16,bold=bold,ls=1.08,spc=spc,role=id)
        obj={'id':id,'kind':'text','text':text,'source':source,'role':role,'rect':[xx,yy,xx1,yy+f.height],'fit':f.to_dict(),'color':color or inks['body'],'background':bg or inks['paper']}
        objs.append(obj)
        if source:used.add(source)
        return obj
    def overlap(a,b,reason):
        p['overlaps'].append({'objects':[a['id'],b['id']],'reason':reason,'min_contrast':4.5,'readability':'measured glyph fit + rendered review required'})
    by={r['source']:r for r in roles}
    def source_text(path):return by[path]['text'] if path in by else ''
    # Masthead uses supplied subtitle, never a fabricated issue/date.
    top=y
    if c.get('subtitle'):
        o=fittext('masthead',c['subtitle'],(x,top,x1,top+h*.09),body,'meta','subtitle',spc=.8)
        top=o['rect'][3]+gap
        box('masthead-rule',(x,top-5,x1,top-4),inks['main'][1],role='structure')
        p['micro_layer'].append({'kind':'masthead','role':'context','source':'subtitle'})
    hero_bottom=top+h*hs
    # Explicit source title fragments permit functional words at smaller scale.
    title=c['title'];fragments=opts.get('title_lines')
    if fragments is not None:
        if not isinstance(fragments,list) or not fragments or any(not isinstance(v,str) or not v.strip() for v in fragments):raise ValueError('title_lines must be nonempty original text fragments')
        if re.sub(r'\s+','', ''.join(fragments))!=re.sub(r'\s+','',title):raise ValueError('title_lines must preserve the entire title and order')
    else:
        tokens=title.split()
        if len(tokens)>=2:
            pivot=max(1,len(tokens)//2);fragments=[' '.join(tokens[:pivot]),' '.join(tokens[pivot:])]
        elif len(title)>6 and re.search(r'[\u3400-\u9fff]',title):
            pivot=len(title)//2;fragments=[title[:pivot],title[pivot:]]
        else:fragments=[title]
    compact=archetype in ('numeral-hero','diagram-hero','statement')
    title_h=h*.115 if compact else hero_bottom-top
    title_bg=None
    if archetype=='banded':
        title_bg=box('hero-band',(-canvas.bleed,top-gap*.25,W+canvas.bleed,hero_bottom+gap*.5),inks['main'][0],role='hero',bleed=True)
        slab=box('second-plate',(W*.71,top-gap*.25,W+canvas.bleed,hero_bottom+gap*.5),inks['main'][1],role='support',bleed=True)
        over=box('multiply-plate',slab['rect'],multiply(inks['main'][0],inks['main'][1]),role='overprint')
        p['overlaps'].append({'objects':[title_bg['id'],slab['id']],'reason':'two ink plates','blend':'multiply','intersection':over['id']})
    yy=top
    for i,frag in enumerate(fragments):
        fam=theme.f_heading if re.search(r'[\u3400-\u9fff]',frag) else theme.f_display
        width_size=((w-rk.NO_WRAP['pad_pt'])/rk.NO_WRAP['slack'])*.97/max(tm.advance(frag,fam,100,True)/100,.01)
        requested=min(body*2.3,width_size) if compact else width_size
        if len(fragments)>1 and i==0 and len(frag)<len(fragments[-1])*.8:requested*=.84
        # Functional-only lines get a smaller size; no casing or wording changes.
        if frag.lower().strip() in ('the','a','an','of','and','to','for'):requested=min(requested,body*1.5)
        lh=title_h/len(fragments)
        background=inks['main'][0] if title_bg else inks['paper']
        # Right-hand intersection has a second background: choose the best minimum contrast.
        color=max((inks['paper'],inks['body']),key=lambda cc:min(contrast(cc,background),contrast(cc,multiply(*inks['main'])))) if title_bg else inks['main'][0]
        if contrast(color,background)<4.5:color=foreground(background,inks)
        o=fittext('title-'+str(i),frag,(x,yy,x1,yy+lh),max(16,requested),'hook','title',True,color,background)
        if title_bg:
            for b in (title_bg,slab,over):overlap(o,b,'headline intentionally on solid ink')
        yy=o['rect'][3]+gap*.3
    # Large source-grounded hero, separate from the headline when appropriate.
    if compact:
        yy=top+title_h+gap
        if archetype=='numeral-hero':
            raw=c['key_number'];value=str(raw.get('value')) if isinstance(raw,dict) else str(raw)
            path='key_number.value' if isinstance(raw,dict) else 'key_number'
            plate=box('number-plate',(x,yy,x+w*.55,hero_bottom),inks['main'][0],role='hero')
            o=fittext('hero-number',value,(x+12,yy+8,x+w*.55-12,hero_bottom-10),body*base['ratio'],'hero_stat',path,True,foreground(plate['fill'],inks),plate['fill'])
            overlap(o,plate,'number hero on source-bound plate')
            label=raw.get('label') if isinstance(raw,dict) else None
            if label:fittext('hero-qualifier',label,(x+w*.61,yy+gap,x1,hero_bottom),body*1.5,'hero_stat','key_number.label',False)
            box('number-foot',(x,hero_bottom+gap*.5,x1,hero_bottom+gap*.5+2),inks['main'][1],role='structure')
        elif archetype=='statement':
            path='quote.text' if isinstance(c['quote'],dict) else 'quote'
            statement=source_text(path)
            if opts.get('statement_lines'):
                statement='\n'.join(opts['statement_lines'])
                if re.sub(r'\s+','',statement)!=re.sub(r'\s+','',source_text(path)):raise ValueError('statement_lines must preserve the supplied quote')
            attribution_path='quote.attribution' if 'quote.attribution' in by else 'attribution' if 'attribution' in by else None
            reserve=body*1.5+gap if attribution_path else 0
            quote_size=body*base['ratio']
            if opts.get('statement_lines'):
                fam=theme.f_heading if re.search(r'[\u3400-\u9fff]',statement) else theme.f_display
                widest=max(tm.advance(line,fam,100,True)/100 for line in opts['statement_lines'])
                quote_size=min(quote_size,((w-rk.NO_WRAP['pad_pt'])/rk.NO_WRAP['slack'])*.97/max(widest,.01))
            quote_obj=fittext('hero-statement',statement,(x,yy,x1,hero_bottom-reserve),quote_size,'hook',path,True,inks['main'][0])
            if attribution_path:
                ay=quote_obj['rect'][3]+gap
                fittext('quote-credit',source_text(attribution_path),(x,ay,x1,hero_bottom),16,'source',attribution_path)
        else:
            # Reserve diagram geometry now; source labels are never invented.
            relationship='chart' if c.get('chart') else 'process' if c.get('process') else 'comparison'
            p['hero']['source']=relationship
            if relationship=='chart':
                chart=c['chart'];rows=chart['items'];cy=yy
                for path in ('chart.title','chart.unit'):
                    if path in by:
                        ob=fittext(path,source_text(path),(x,cy,x1,hero_bottom),body,'facts',path,True);cy=ob['rect'][3]+8
                rh=(hero_bottom-cy)/len(rows);peak=max(r['value'] for r in rows) or 1
                for i,row in enumerate(rows):
                    lp=f'chart.items.{i}.label';vp=f'chart.items.{i}.value'
                    fittext(lp,source_text(lp),(x,cy,x+w*.33,cy+rh-5),body,'facts',lp)
                    fittext(vp,source_text(vp),(x+w*.87,cy,x1,cy+rh-5),body,'hero_stat',vp,True)
                    if row['value']>0:box('bar-'+str(i),(x+w*.36,cy+6,x+w*.36+w*.47*row['value']/peak,cy+rh*.48),inks['main'][i%2],role='data')
                    cy+=rh
            else:
                rows=c[relationship];cw=(w-gap*(len(rows)-1))/len(rows)
                for i,row in enumerate(rows):
                    xx=x+i*(cw+gap);cy=yy+gap
                    fields=[r for r in roles if r.get('group')==f'{relationship}.{i}']
                    for r in fields:
                        ob=fittext(r['id'],r['text'],(xx,cy,xx+cw,hero_bottom-gap),body*1.2,'parallel_set',r['source'],True);cy=ob['rect'][3]+8
                    box('node-rule-'+str(i),(xx,hero_bottom-6,xx+cw,hero_bottom-4),inks['main'][i%2],role='structure')
                    if relationship=='process' and i<len(rows)-1:
                        box('flow-'+str(i),(xx+cw+2,yy,xx+cw+gap-2,yy+10),inks['main'][1],role='relation',kind='arrow')
                p['hero']['relation']=relationship
    content_top=hero_bottom+gap*1.5
    # CTA and colophon are measured and reserved, not collapsed into body style.
    footer=None;cta=None;bottom=y1
    if c.get('footer'):
        f=tf.fit(c['footer'],theme.f_body,16,w,h*.14,minimum=16,ls=1.08,role='source')
        footer=fittext('colophon',c['footer'],(x,bottom-f.height,x1,bottom),16,'source','footer')
        bottom=footer['rect'][1]-gap*1.2
        box('colophon-rule',(x,bottom+gap*.5,x1,bottom+gap*.5+1),inks['main'][1],role='structure')
        p['micro_layer'].append({'kind':'colophon','role':'provenance','source':'footer'})
    if c.get('cta'):
        f=tf.fit(c['cta'],theme.f_body,body*1.25,w-24,h*.16,minimum=16,bold=True,ls=1.08,role='cta')
        r=(x,bottom-f.height-20,x1,bottom)
        bg=box('cta-slot',r,inks['main'][0],role='cta',slot='cta')
        cta=fittext('cta',c['cta'],(x+12,r[1]+10,x1-12,bottom-10),body*1.25,'cta','cta',True,foreground(bg['fill'],inks),bg['fill'])
        overlap(cta,bg,'editable CTA text slot');bottom=r[1]-gap
        p['micro_layer'].append({'kind':'label','role':'action','source':'cta'})
    # Unconsumed sources become indivisible logical modules, paragraphs may split.
    modules=[];grouped={}
    for r in roles:
        if r['source'] in used:continue
        if r['source']=='body':
            paras=re.split(r'\n\s*\n',r['text'])
            for j,para in enumerate(paras):
                if para:modules.append([dict(r,text=para,part=j)])
        else:
            group=r.get('group',r['source'])
            if group not in grouped:grouped[group]=[];modules.append(grouped[group])
            grouped[group].append(r)
    if not modules:columns=1
    columns=min(columns,max(1,len(modules)));p['columns']=columns
    cw=(w-gap*(columns-1))/columns
    def measure_module(module,width=None):
        width=cw if width is None else width
        items=[];height=0
        numbered=any(r.get('group','').startswith('blocks.') for r in module)
        if numbered:height+=body*1.1+gap*.35
        for r in module:
            heading=r['source'].endswith(('.title','.value')) or r['role']=='hero_stat'
            sz=body*2.8 if r['role']=='hero_stat' and not r['source'].endswith('.label') else body*1.3 if heading else body*1.55 if r['role']=='hook' else body
            if r['role']=='source':sz=16
            f=tf.fit(r['text'],theme.f_heading if re.search(r'[\u3400-\u9fff]',r['text']) else theme.f_body,sz,width,bottom-content_top,minimum=16,bold=heading,ls=1.08,role=r['source'])
            items.append((r,f,heading));height+=f.height+gap*.35
        return items,height+gap*.8
    def draw_module(measured,xx,cy,width):
        grouped_module=next((r for r,f,bold in measured[0] if r.get('group','').startswith('blocks.')),None)
        if grouped_module:
            index=int(grouped_module['group'].split('.')[1])+1
            number=fittext('module-index-'+str(index),f'{index:02}',(xx,cy,xx+body*2,cy+body*1.3),body,'meta',None,True,inks['main'][0])
            box('module-icon-'+str(index),(xx+body*2.2,cy+body*.35,xx+body*2.2+8,cy+body*.35+8),inks['main'][0],role='structure')
            cy=number['rect'][3]+gap*.35
        for r,f,bold in measured[0]:
            id=r['id']+('-part'+str(r['part']) if 'part' in r else '')
            ob=fittext(id,r['text'],(xx,cy,xx+width,cy+f.height+2),f.size,r['role'],r['source'],bold,inks['main'][0] if r['role'] in ('hook','hero_stat') else None)
            cy=ob['rect'][3]+gap*.35
        return cy+gap*.8
    parallel=[m for m in modules if any(r.get('group','').startswith('blocks.') for r in m)]
    if len(parallel)>=2:
        # Parallel sets stay together, in row-major order. Introductory arguments
        # cannot consume one of their columns and scatter 01/02/03 across the page.
        intro=[m for m in modules if m not in parallel]
        grid_cols=min(3,len(parallel));p['columns']=grid_cols
        grid_w=(w-gap*(grid_cols-1))/grid_cols
        im=[measure_module(m,w) for m in intro];pm=[measure_module(m,grid_w) for m in parallel]
        offset=gap*1.4 if archetype=='staggered-modules' else 0
        row_heights=[max(v[1] for v in pm[i:i+grid_cols])+offset for i in range(0,len(pm),grid_cols)]
        grid_h=sum(row_heights)+gap*max(0,len(row_heights)-1)
        intro_h=sum(v[1] for v in im)
        if intro_h+grid_h+gap>bottom-content_top:
            raise ValueError(f'Grouped parallel set needs {intro_h+grid_h+gap:.1f}pt; has {bottom-content_top:.1f}; revise hero allocation, never omit source')
        cy=content_top
        for measured in im:cy=draw_module(measured,x,cy,w)
        cy=max(cy+gap,bottom-grid_h)
        p['parallel_grid']={'columns':grid_cols,'column_width':grid_w,'top':cy,'source':'blocks','order':'row-major'}
        for row,rh in enumerate(row_heights):
            for col,measured in enumerate(pm[row*grid_cols:(row+1)*grid_cols]):
                draw_module(measured,x+col*(grid_w+gap),cy+offset*(col%2),grid_w)
            cy+=rh+gap
    else:
        measured=[measure_module(m) for m in modules]
        choices=[]
        for cuts in itertools.combinations(range(1,len(modules)),columns-1):
            boundaries=(0,)+cuts+(len(modules),)
            heights=[sum(v[1] for v in measured[a:b]) for a,b in zip(boundaries,boundaries[1:])]
            choices.append((max(heights,default=0),boundaries,heights))
        _,bounds,heights=min(choices,default=(0,(0,0),[0]))
        for col,(a,b) in enumerate(zip(bounds,bounds[1:])):
            stagger=gap*1.4*(col%2) if archetype=='staggered-modules' else 0
            cy=content_top+stagger;available=bottom-cy
            if heights[col]>available+gap*.8:raise ValueError(f'{archetype} column {col+1}: needs {heights[col]:.1f}pt, has {available:.1f}; revise hero_share/columns, preserve 16pt body')
            extra=max(0,available-heights[col]+gap*.8)/max(1,b-a-1) if b-a>1 else 0
            if b-a==1:cy+=max(0,available-heights[col])*.35
            for j in range(a,b):cy=draw_module(measured[j],x+col*(cw+gap),cy,cw)+extra
    # Small layer: structure-linked marks and one bounded halftone gap/edge.
    if c.get('blocks'):p['micro_layer'].append({'kind':'module-symbols','role':'parallel membership','source':'blocks','repetition':'structural'})
    # Native halftone dots occupy the gutter/outer edge, never a fixed figure slot.
    edge_left=archetype in ('statement','staggered-modules','numeral-hero')
    dx=0 if edge_left else W-x*.70;dy=H*.56 if archetype=='statement' else H*.32
    dots=[]
    for rr in range(12):
        for cc in range(3):
            rad=(.6+1.6*(1-rr/12))*(1-cc*.18)
            dots.append([dx+cc*7,dy+rr*8,rad])
    if archetype in ('type-hero','numeral-hero'):
        objs.append({'id':'edge-halftone','kind':'halftone','role':'detail','fill':inks['main'][1],'rect':[dx,dy,dx+20,dy+96],'dots':dots})
        p['micro_layer'].append({'kind':'halftone','role':'edge rhythm','count':1})
    elif archetype=='statement':
        box('statement-keyline',(x-9,top+title_h+gap,x-7,hero_bottom),inks['main'][1],role='structure')
        p['micro_layer'].append({'kind':'keyline','role':'quotation grouping','source':'quote'})
    elif archetype=='banded':
        box('plate-register',(x1-16,hero_bottom+gap*.6,x1,hero_bottom+gap*.6+3),inks['accent'],role='structure')
        p['micro_layer'].append({'kind':'plate-register','role':'overprint alignment','count':1})
    # Source-bound highlight: only exact substrings and at most two occurrences.
    highlights=opts.get('highlights')
    if highlights is None:
        candidate=next((r for r in roles if r['role']=='hook' and r['source']!='title'),None)
        if candidate is None:candidate=next((r for r in roles if r['source'].endswith('.title')),None)
        token=(max(re.findall(r'[A-Za-z]+',candidate['text']),key=len,default='') if candidate else '')
        if candidate and not token:token=candidate['text'][:min(4,len(candidate['text']))]
        highlights=[{'source':candidate['source'],'text':token}] if candidate and token else []
    if len(highlights)>2:raise ValueError('At most two source keyword highlights per page')
    for i,mark in enumerate(highlights):
        if not isinstance(mark,dict) or set(mark)!={'source','text'} or mark['source'] not in by or not mark['text'] or mark['text'] not in by[mark['source']]['text']:raise ValueError('Highlight must bind an exact nonempty source substring')
        target=next((o for o in objs if o['kind']=='text' and o.get('source')==mark['source'] and any(mark['text'] in l for l in o['fit']['lines'])),None)
        if not target:raise ValueError('Highlight crosses a measured line; choose a shorter exact keyword')
        f=target['fit'];line=next(l for l in f['lines'] if mark['text'] in l);li=f['lines'].index(line)
        prefix=line[:line.index(mark['text'])];xx=target['rect'][0]+tm.advance(prefix,f['font'],f['size'],f['bold'],f['spc'])
        ww=tm.advance(mark['text'],f['font'],f['size'],f['bold'],f['spc']);yy=target['rect'][1]+li*f['pitch']
        hi=box('highlight-'+str(i),(xx,yy+f['size']*.18,xx+ww+1,yy+f['size']*1.05),inks['accent'],role='emphasis',keyword=mark['text'])
        objs.remove(hi);objs.insert(objs.index(target),hi);overlap(target,hi,'exact source keyword highlight')
        p['micro_layer'].append({'kind':'highlight','role':'source keyword','source':mark['source'],'text':mark['text']})
    # A content-bound stamp/badge is an alternative micro primitive, no sample copy.
    slot=opts.get('micro_style','label')
    if slot not in ('label','stamp','badge'):raise ValueError('micro_style must be label, stamp, badge')
    if cta and slot!='label':
        cta_background=next(o for o in objs if o['id']=='cta-slot')
        cta_background['slot']=slot
        cta_background['line']=inks['main'][1]
        p['micro_layer']=[dict(m,kind=slot) if m['role']=='action' else m for m in p['micro_layer']]
    # Sparse title-only posters still have meaningful print details, never filler copy.
    while len(p['micro_layer'])<3:
        n=len(p['micro_layer']);rx=x1 if n%2 else x
        box('ink-register-'+str(n),(rx-5,H-y*.4-n*4,rx+5,H-y*.4-n*4+1.5),inks['main'][n%2],role='structure')
        p['micro_layer'].append({'kind':'ink-register','role':'plate alignment','count':1})
    p['micro_layer']=p['micro_layer'][:6]
    p['ink_plan']['multiply']=any(o['role']=='overprint' for o in objs)
    p['ink_plan']['solid_blocks']=any(o['kind']=='rect' and o['rect'][3]-o['rect'][1]>30 for o in objs)
    p['scale_ladder']['actual']=sorted(set(round(o['fit']['size'],2) for o in objs if o['kind']=='text'),reverse=True)
    p['hero']['object_ids']=[o['id'] for o in objs if o['id'].startswith(('title-','hero-'))]
    p['reading_order']=[{'id':o['id'],'source':o.get('source'),'role':o['role'],'rect':o['rect']} for o in objs if o['kind']=='text']
    return p

def draw(slide,p,theme):
    """Native vectors and text. Multiply intersections remain editable objects."""
    from pptx.enum.shapes import MSO_SHAPE
    for o in p['objects']:
        x,y,x1,y1=o['rect'];w=x1-x;h=y1-y
        if o['kind']=='path':
            from poster_primitives import native_path
            native_path(slide,o)
        elif o['kind']=='text':
            f=tf.Fit(**dict(o['fit'],lines=tuple(o['fit']['lines'])))
            shapes=tf.draw(slide,x,y,w,f,theme,color=o['color'],role='poster-art')
            if p.get('version') in ('3.5','3.6','3.7','3.8'):
                # The fit records an absolute measured pitch. Relative spacing
                # is renderer/font dependent and accumulated line-position
                # drift in long CJK paragraphs. Preserve the measured pitch in
                # native OOXML instead of weakening raster legibility checks.
                from pptx.util import Pt
                for shape in shapes:
                    for paragraph in shape.text_frame.paragraphs:
                        paragraph.line_spacing=Pt(f.pitch)
            for i,s in enumerate(shapes):
                s.name=f"art[{o['id']}]/{i}"
                s.rotation=o.get('rotation',0)
        elif o['kind']=='halftone':
            for i,(cx,cy,r) in enumerate(o['dots']):
                sh=rk.oval(slide,cx,cy,r*2,r*2,fill=o['fill']);sh.name=f"art[{o['id']}]/{i}"
        else:
            kind=MSO_SHAPE.CHEVRON if o['kind']=='arrow' else MSO_SHAPE.ROUNDED_RECTANGLE if o.get('slot')=='badge' else MSO_SHAPE.RECTANGLE
            sh=rk.shape(slide,kind,x,y,w,h,fill=o.get('fill'),line=o.get('line'),lw=2 if o.get('slot')=='stamp' else .75)
            sh.name=f"art[{o['id']}]"
            sh.rotation=o.get('rotation',0)

@lru_cache(maxsize=8)
def paper_bytes(width,height,paper,seed,dialect='swiss'):
    """Bounded immutable cache; indexed PNG stores correlated RGB grain exactly.

    The old texture added one noise value to all RGB channels. An indexed
    palette represents those same pixels without compressing three channels.
    No artwork is cached on disk or placed inside the installed skill.
    """
    from PIL import Image
    import numpy as np
    import io
    pw=int(width*1.7);ph=int(height*1.7)
    rng=np.random.default_rng(seed)
    grain=rng.normal(0,1.1 if dialect=='swiss' else 2.2,(ph,pw))
    levels=np.clip(np.floor(grain),-255,255).astype('int16')
    lo=int(levels.min());hi=int(levels.max())
    if hi-lo>255:
        # Very large custom noise ranges fall back to exact RGB, never wrap.
        arr=np.clip(np.array(rgb(paper))+levels[:,:,None],0,255).astype('uint8')
        im=Image.fromarray(arr);buf=io.BytesIO();im.save(buf,format='PNG',compress_level=1);return buf.getvalue()
    indices=(levels-lo).astype('uint8')
    im=Image.fromarray(indices).convert('P')
    im.putpalette([max(0,min(255,c+i+lo)) for i in range(256) for c in rgb(paper)])
    bits=next(b for b in (1,2,4,8) if 2**b>=hi-lo+1)
    buf=io.BytesIO();im.save(buf,format='PNG',compress_level=3,bits=bits)
    return buf.getvalue()


def build(spec,out_path,plan=None):
    import metric_cache
    metric_cache.enable()
    import artifact_io as aio
    from PIL import Image
    p=make_plan(spec) if plan is None else plan
    if p['source_sha256']!=digest(spec['content']):raise ValueError('Prepared plan does not match supplied source')
    out=Path(out_path).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    canvas=poster_canvas(spec.get('canvas'));inks=p['ink_plan'];media=aio.paths(out)[2];media.mkdir(exist_ok=True)
    theme=rk.Theme(palette='A',lang=spec.get('meta',{}).get('lang','en'),fonts=spec.get('meta',{}).get('fonts'))
    # Low amplitude paper grain: quiet enough for 16pt detail at export resolution.
    bg=media/'bg1.png';bg.write_bytes(paper_bytes(canvas.width,canvas.height,inks['paper'],spec.get('meta',{}).get('seed',1),p.get('dialect','swiss')))
    prs=rk.new_deck(canvas);slide=rk.add_page(prs,str(bg));slide.shapes[0].name='riso-paper[background]';draw(slide,p,theme)
    # Delete only empty text boxes. Native rectangles carry an empty txBody by
    # OOXML convention and must remain as editable chart/diagram geometry.
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for shape in list(slide.shapes):
        if shape.shape_type==MSO_SHAPE_TYPE.TEXT_BOX and not shape.text.strip():
            shape._element.getparent().remove(shape._element)
    aio.save_pptx(prs,out)
    tokens={'inkA':inks['main'][0],'inkB':inks['main'][1],'accent1':inks['accent'],'paper':inks['paper'],'text':inks['body'],'multiply':multiply(*inks['main'])}
    if p.get('version') in ('3.5','3.6','3.7','3.8') or p.get('dialect','swiss')!='swiss':
        for color in sorted({o.get(k) for o in p['objects'] for k in ('color','fill','line') if o.get(k)}):
            if color not in tokens.values():tokens['derived-'+str(len(tokens))]=color
    manifest={'tokens':tokens,'pages':[{'page':1,'file':bg.name,'reversed':False,'sha256':hashlib.sha256(bg.read_bytes()).hexdigest()}],'total_bytes':bg.stat().st_size}
    (media/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    style={'skill':'riso-slides','version':p['version'],'artifact':'poster','canvas_spec':canvas.to_dict(),'fonts':theme.fonts,'font_diagnostics':theme.font_diagnostics,'palette':{'tokens':tokens},'poster':{'art_direction':p,'background_sha256':manifest['pages'][0]['sha256']},'pages':[{'n':1,'archetype':p['archetype']}]}
    aio.write_style(out,style)
    out.with_suffix('.plan.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    return str(out)

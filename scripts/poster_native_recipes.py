"""Editable vector interpretations of the eight recipe descriptors.

Legacy deck generators are raster generators and remain unchanged. These paths
retain their lead/pattern/detail grammar, without rasterizing the poster group.
They are abstract motifs, never measurements or factual illustrations.
"""
import math,re
from graphic_recipes import RECIPES,validate
from poster_primitives import torn,ink_path,bounds

def choose(spec):
    meta=spec.get('meta',{});requested=meta.get('graphic_recipe','micro')
    if requested in ('off','micro'):return None,'micro elements only; large graphic group disabled'
    validate(requested)
    if spec.get('layout',{}).get('graphic')=='none' or not meta.get('elements',True) or meta.get('element_pool')==[]:
        if requested!='auto':raise ValueError('Named graphic_recipe conflicts with disabled graphic region')
        return None,'explicit typography-only configuration'
    if meta.get('graphic_element'):
        raise ValueError('art_direction uses complete graphic_recipe groups; graphic_element is legacy-only. Choose a named recipe.')
    text=str(spec.get('brief',''))+' '+str(spec.get('content',{}))
    text=text.lower()
    key=requested
    if key=='auto':
        forced=meta.get('dialect');forced=forced[0] if isinstance(forced,list) else forced
        if forced:key=next(k for k,r in RECIPES.items() if r['dialect']==forced)
        else:
            rules=[('cut-paper',('card','postcard','paper','mail','纸')),('echo',('sound','listen','listening','倾听','听见')),('canopy',('seed','garden','plant','种子')),('terraces',('city','roof','urban')),('editorial',('library','archive','book','reading','笔记')),('signal',('ai','digital','code')),('festival',('festival','event')),('hand-drawn',('repair','workshop','participation','修理'))]
            def select(value):
                def matches(word):return word in value if re.search(r'[\u3400-\u9fff]',word) else re.search(r'(?<![a-z])'+re.escape(word)+r'(?:s|ing)?(?![a-z])',value)
                return next((k for k,words in rules if any(matches(w) for w in words)),None)
            key=select(' '.join(meta.get('topic_tags',[])).lower()) or select(text) or ('hand-drawn' if spec.get('content',{}).get('process') or spec.get('content',{}).get('quote') else 'editorial')
    recipe=RECIPES[key];excluded=set(meta.get('exclude_elements',[]));pool=meta.get('element_pool')
    if excluded.intersection(recipe['elements']) or pool is not None and not set(recipe['elements'])<=set(pool):
        raise ValueError(f'graphic_recipe {key} cannot place all three members: excluded elements or element_pool conflict; allow {recipe["elements"]}')
    return key,RECIPES[key]['use']

def paths_for(name,r,seed):
    x,y,x1,y1=r;w=x1-x;h=y1-y
    def poly(points):return [[x+a*w,y+b*h] for a,b in points]
    def ring(cx,cy,rx,ry):return [[cx+rx*math.cos(i*math.tau/40),cy+ry*math.sin(i*math.tau/40)] for i in range(41)]
    if name in ('handcut_polygon','washi_tape'):return [torn(r,seed)],True
    if name=='layered_stack':return [poly([(0,.18),(.8,0),(1,.8),(.2,1),(0,.18)]),poly([(.1,.12),(.9,.06),(.96,.86),(.16,.94),(.1,.12)])],False
    if name in ('ring','scribble_circle'):return [ring(x+w/2,y+h/2,w*.46,h*.46),ring(x+w/2,y+h/2,w*.34,h*.34)],False
    if name=='arch':return [poly([(0,1),(0,.45)])+[[x+w/2+w/2*math.cos(t*math.pi/30),y+h*.45-h*.44*math.sin(t*math.pi/30)] for t in range(30,-1,-1)]+poly([(1,1)])],False
    if name=='stairs':return [poly([(0,1),(0,.72),(.25,.72),(.25,.48),(.5,.48),(.5,.24),(.75,.24),(.75,0),(1,0),(1,1),(0,1)])],True
    if name in ('line_screen','stripe_band','scribble_fill'):
        return [poly([(0,i/9),(1,(i+.3)/9)]) for i in range(9)],False
    if name in ('quarter_tiles','scallop_block'):
        return [poly([(i/3,1),((i+1)/3,1),((i+1)/3,.2),(i/3,.6),(i/3,1)]) for i in range(3)],True
    if name=='spiral':return [[[x+w/2+math.cos(i*.17)*w*.46*i/110,y+h/2+math.sin(i*.17)*h*.46*i/110] for i in range(111)]],False
    if name=='fold_line':return [poly([(0,0),(.5,.5),(1,0)]),poly([(.5,.5),(.5,1)])],False
    if name=='pixel_icon':return [poly([(0,.3),(.3,.3),(.3,0),(.7,0),(.7,.3),(1,.3),(1,.7),(.7,.7),(.7,1),(.3,1),(.3,.7),(0,.7),(0,.3)])],True
    if name=='dot_screen':return [ring(x+(i+.5)*w/7,y+(j+.5)*h/4,min(w/7,h/4)*.16,min(w/7,h/4)*.16) for i in range(7) for j in range(4)],True
    if name=='cursor_arrow':return [poly([(0,0),(1,.5),(.6,.6),(.5,1),(0,0)])],True
    if name=='starburst':return [poly([(.5+math.cos(i*math.pi/12)*(.5 if i%2==0 else .28),.5+math.sin(i*math.pi/12)*(.5 if i%2==0 else .28)) for i in range(25)])],True
    if name=='zigzag_strip':return [poly([(i/12,.2 if i%2==0 else .8) for i in range(13)])],False
    raise ValueError('No native interpretation for '+name)

def compose(key,region,inks,seed):
    x,y,x1,y1=region;w=x1-x;h=y1-y
    if w<130 or h<55:raise ValueError(f'graphic_recipe {key}: allocated {w:.1f} x {h:.1f}pt; requires at least 130 x 55pt for a complete group')
    # A large lead, a subordinate patterned piece, and a small detail. Fixed
    # allocation prevents an explicit recipe silently becoming a tiny motif.
    # Fit every native member at its catalogue aspect; never stretch a square
    # into a page-height sliver merely to defeat the whitespace detector.
    import elements
    raw=[]
    for i,name in enumerate(RECIPES[key]['elements']):
        lo,hi,low,high=elements.REGISTRY[name]['size'];aspect=(lo+hi)/(low+high)
        maxw=w*(.49,.27,.14)[i];maxh=h*(.94,.72,.44)[i]
        ww=min(maxw,maxh*aspect);hh=ww/aspect;raw.append((ww,hh))
    cells=[]
    for i,(ww,hh) in enumerate(raw):
        cx=x+w*(.245,.685,.93)[i];cy=y+h/2
        cells.append([cx-ww/2,cy-hh/2,cx+ww/2,cy+hh/2])
    out=[]
    for i,(name,rect) in enumerate(zip(RECIPES[key]['elements'],cells)):
        paths,closed=paths_for(name,rect,seed+i)
        out.append(dict(id=f'recipe-{i}',kind='path',role='graphic',rect=bounds(paths,1.5),paths=paths,closed=closed,
                        fill=inks['main'][i%2] if closed else None,line=None if closed else inks['main'][i%2],line_width=2,
                        recipe=key,recipe_part=('lead','pattern','detail')[i],element=name,rotation=0,layer='graphic'))
    return out

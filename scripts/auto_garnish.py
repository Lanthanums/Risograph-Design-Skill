"""Bounded default accents; every object is attached to a real text anchor."""
from collections import Counter
import layout as lay
from poster_primitives import bounds,planned_glyphs

QUOTAS={'sparse':(4,7,3),'normal':(8,14,4),'rich':(12,20,5)}
ICON_BY_TYPE=dict(statistic='person',claim='chat',process_step='arrow',comparison='document',
                  part_whole='box',timeline='calendar',definition='book',quote='chat',
                  example='bulb',cta='flag',logistics='location',source='document')

def apply(plan,density='normal'):
    if density not in QUOTAS:raise ValueError('element_density must be sparse, normal or rich')
    low,high,families=QUOTAS[density];objs=plan['objects'];ink=plan['ink_plan']
    text=[o for o in objs if o['kind']=='text' and not o.get('duplicate_of')]
    occupied=[g for o in text for g in planned_glyphs(o)]
    for i,t in enumerate(text):
        if sum(bool(o.get('micro')) for o in objs)>=high:break
        r=t['rect'];f=t['fit'];x=r[0];y=r[3]+5
        # Alternating anchored families, deterministic and topic-independent.
        family=('underline','pin','corner','separator','tape')[i%5]
        if plan.get('dialect')=='swiss' and family not in ('underline','separator','corner'):continue
        if family=='underline':
            paths=[[[x,y],[x+min(65,f['width']),y]]]
        elif family=='pin':
            x=min(r[2]-12,r[0]+f['width']+10);y=r[1]+7
            paths=[[[x-3,y],[x+3,y]],[[x,y-3],[x,y+7]]]
        elif family=='corner':
            x=r[0]-5;y=r[1]+3;paths=[[[x+5,y],[x,y],[x,y+9]]]
        elif family=='separator':
            paths=[[[x,y],[x+25,y]],[[x+31,y-2],[x+33,y],[x+31,y+2],[x+29,y],[x+31,y-2]]]
        else:
            x=r[0]+max(0,min(r[2]-r[0],f['width'])-29);y=r[1]-7;paths=[[[x,y],[x+24,y-1],[x+24,y+2],[x,y+3],[x,y]]]
        rect=bounds(paths,1)
        if not lay.inside(rect,plan['canvas']['safe'],tol=0):continue
        if any(lay.intersection(rect,g) for g in occupied):continue
        objs.append(dict(id='garnish-'+str(i),kind='path',rect=rect,paths=paths,
                         line=ink['main'][1] if family=='pin' else ink['accent'],line_width=1.5,
                         role='emphasis',rotation=0,anchor=t['id'],micro=True,vocabulary=family))
    plan['element_quota']=dict(density=density,suggested_count=[low,high],minimum_families=families)
    plan['micro_layer']=[dict(kind=k,role='content anchor') for k in ('paper','registration','garnish')]
    plan['element_metrics']=assess(plan)

def assess(plan):
    marks=[o for o in plan['objects'] if o.get('micro')]
    quota=plan.get('element_quota',dict(suggested_count=[8,14],minimum_families=4))
    page=plan['canvas']['width']*plan['canvas']['height'];known={o['id'] for o in plan['objects']}
    area=lambda o:max(0,o['rect'][2]-o['rect'][0])*max(0,o['rect'][3]-o['rect'][1])
    fails=[];warnings=[];counts=Counter(o.get('vocabulary','unknown') for o in marks)
    for o in marks:
        if o.get('anchor') not in known:fails.append('unanchored garnish: '+o['id'])
        if area(o)/page>.06:fails.append('garnish exceeds 6% page area: '+o['id'])
    total=sum(area(o) for o in marks)/page
    if total>.10:fails.append('garnish total exceeds 10% page area')
    if len(marks)<quota['suggested_count'][0] or len(counts)<quota['minimum_families']:
        warnings.append('Element quota below suggestion. Repair: python scripts/poster_run.py --spec INPUT.json --content-plan content-plan.json --out OUTPUT --element-density rich --auto')
    return dict(element_count=len(marks),element_variety=len(counts),families=dict(counts),decorative_area_ratio=total,
                fails=fails,warnings=warnings,quota=quota)

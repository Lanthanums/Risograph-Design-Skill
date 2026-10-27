"""Poster art direction using the SAME copy-free generators as slide decks.

Recipes describe relationships, not finished artwork or factual illustrations.
All members pass the existing collision, area and quiet-space gates atomically.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import math

RECIPES = {
    'echo': {'dialect':'C', 'elements':['ring','line_screen','stripe_band'],
             'use':'Repetition, listening, connection; an abstract motif, not a waveform.'},
    'canopy': {'dialect':'C', 'elements':['arch','scallop_block','line_screen'],
               'use':'Shelter and shade; abstract cover and filtered light, not measured canopy.'},
    'terraces': {'dialect':'C', 'elements':['stairs','quarter_tiles','stripe_band'],
                 'use':'Built layers, rooftops or stages; not a scale model or data chart.'},
    'cut-paper': {'dialect':'A', 'elements':['handcut_polygon','layered_stack','washi_tape'],
                  'use':'Material, craft and assembled ideas, with a pasted-paper rhythm.'},
    'hand-drawn': {'dialect':'B', 'elements':['scribble_circle','scribble_fill','spiral'],
                   'use':'Informal participation, workshop and exploration.'},
    'editorial': {'dialect':'D', 'elements':['layered_stack','line_screen','fold_line'],
                  'use':'Archive, reading and publication, with layered paper and print lines.'},
    'signal': {'dialect':'E', 'elements':['pixel_icon','dot_screen','cursor_arrow'],
               'use':'Digital interaction and systems; symbols carry no invented labels.'},
    'festival': {'dialect':'F', 'elements':['starburst','handcut_polygon','zigzag_strip'],
                 'use':'Energetic cultural/event work, with cut shapes and a serrated rhythm.'},
}


def validate(value):
    if not isinstance(value,str) or value not in ('auto',*RECIPES):
        raise ValueError('meta.graphic_recipe must be auto or one of: '+', '.join(RECIPES))


def place(placer, region, primary, requested='auto'):
    """Try a bounded horizontal or vertical group, preserving generator aspect.

    Failed attempts are rolled back in full. Explicit recipes cannot silently
    become one unrelated shape; exclusions and restricted pools remain binding.
    """
    import elements as E
    import layout as lay
    validate(requested)
    allowed={n for _,n in placer._pools['main']}
    choices=[requested] if requested!='auto' else [k for k,r in RECIPES.items() if r['dialect']==primary]
    if requested=='auto':placer.rnd.shuffle(choices)
    x0,y0,x1,y1=region
    rw,rh=x1-x0,y1-y0
    gap=12.0
    for key in choices:
        recipe=RECIPES[key]
        if recipe['dialect']!=primary or not set(recipe['elements'])<=allowed:
            if requested!='auto':raise ValueError('graphic_recipe conflicts with primary dialect, element_pool or exclude_elements')
            continue
        # Long screens need a shallower cell than compact shapes. Size is fitted
        # to physical space, never stretched into a different visual language.
        aspects=[]
        for name in recipe['elements']:
            a,b,c,d=E.REGISTRY[name]['size']
            aspects.append((a+b)/(c+d))
        available=placer.area_cap*placer.page_area-placer.taken_area-sum(lay.area(p['rect']) for p in placer.placed)
        target=min(available*.94,placer.page_area*.074,rw*rh*.72)
        # Three distinct scales, shared bottom or left axis. Compact header
        # regions stack the two support pieces beside the lead.
        for scale in (1.0,.88,.76):
            dims=[(math.sqrt(target*f*a)*scale, math.sqrt(target*f/a)*scale)
                  for f,a in zip((.70,.22,.08),aspects)]
            horizontal=rw/rh>=2.1
            side_stack=aspects[2]<2
            if horizontal:
                total_w=sum(w for w,h in dims)+gap*2;total_h=max(h for w,h in dims)
            elif side_stack:
                total_w=dims[0][0]+gap+max(dims[1][0],dims[2][0])
                total_h=max(dims[0][1],dims[1][1]+gap+dims[2][1])
            else:
                total_w=max(dims[0][0]+gap+dims[1][0],dims[2][0])
                total_h=max(dims[0][1],dims[1][1])+gap+dims[2][1]
            fit=min(1,(rw-16)/total_w,(rh-42)/total_h)
            if fit<=0:continue
            dims=[(w*fit,h*fit) for w,h in dims]
            if dims[0][0]*dims[0][1]<placer.page_area*.015:continue
            if horizontal:
                total_w=sum(w for w,h in dims)+gap*2;total_h=max(h for w,h in dims)
            elif side_stack:
                total_w=dims[0][0]+gap+max(dims[1][0],dims[2][0])
                total_h=max(dims[0][1],dims[1][1]+gap+dims[2][1])
            else:
                total_w=max(dims[0][0]+gap+dims[1][0],dims[2][0])
                total_h=max(dims[0][1],dims[1][1])+gap+dims[2][1]
            for side in ('left','right'):
                xx=x0+6 if side=='left' else x1-6-total_w
                yy=y0+(rh-total_h)/2
                if horizontal:
                    positions=[];cx=xx
                    for w,h in dims:positions.append((cx,yy+total_h-h,cx+w,yy+total_h));cx+=w+gap
                elif side_stack:
                    w,h=dims[0];positions=[(xx,yy+total_h-h,xx+w,yy+total_h)]
                    cx=xx+w+gap;cy=yy+total_h-dims[1][1]-gap-dims[2][1]
                    for w,h in dims[1:]:positions.append((cx,cy,cx+w,cy+h));cy+=h+gap
                else:
                    top_h=max(dims[0][1],dims[1][1]);positions=[];cx=xx
                    for w,h in dims[:2]:positions.append((cx,yy+top_h-h,cx+w,yy+top_h));cx+=w+gap
                    w,h=dims[2];cy=yy+top_h+gap
                    positions.append((xx,cy,xx+w,cy+h))
                before=len(placer.placed);used=dict(placer.used_names)
                for i,(name,rect) in enumerate(zip(recipe['elements'],positions)):
                    if not lay.inside(rect,region) or not placer.commit(name,'support' if i==0 else 'micro',rect,0,
                            'grouped','metaphor' if i==0 else 'rhythm',group='composition'):
                        break
                    placer.placed[-1].update(recipe=key,recipe_part=('lead','pattern','detail')[i])
                if len(placer.placed)-before==3:return True
                del placer.placed[before:];placer.used_names=used
    if requested!='auto':
        raise ValueError('graphic_recipe cannot fit as a complete group; revise graphic_position/columns, not readable type or QA limits')
    return False


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dialect',choices=list('ABCDEF'))
    args=ap.parse_args()
    print(json.dumps({k:v for k,v in RECIPES.items() if not args.dialect or v['dialect']==args.dialect},indent=2))


if __name__=='__main__':main()

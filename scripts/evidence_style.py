"""Seeded, editable dialect materials. Never used as semantic evidence area."""
import hashlib,math,random
from collections import Counter
from poster_primitives import bounds

def apply(plan,start,module,rect,bottom):
    objs=plan['objects'];dialect=plan['dialect'];ink=plan['ink_plan'];rx,ry,x1,_=rect
    seed=int(hashlib.sha256((str(plan['seed'])+module['id']).encode()).hexdigest()[:12],16);rnd=random.Random(seed)
    content=list(objs[start:]);anchor=next((o['id'] for o in content if o['kind']=='text'),'title')
    def stroke(oid,paths,color=None,material='drawn-line',width=1.3):
        ob=dict(id=oid,kind='path',paths=paths,rect=bounds(paths,width/2),line=color or ink['main'][0],line_width=width,role='surface',rotation=0,anchor=anchor,material=material,layer='surface')
        return ob
    if dialect=='swiss':
        for o in content:
            if o['kind']=='path' and o.get('line'):o['line_width']=.75
        return
    if dialect=='collage':
        # One source-bound paper per module. Backings/tape are explicitly
        # excluded from evidence bounds and raster semantic masks.
        yy=bottom+5;left=rx+2;right=x1-2
        outline=[[left,ry+3],[right-8,ry+1],[right,ry+5],[right-1,yy-2],[right-9,yy+1],[left+8,yy-1],[left,yy+2],[left+1,ry+3]]
        paper=dict(id=module['id']+'-paper',kind='path',paths=[outline],rect=bounds([outline]),closed=True,fill='FFFDF4',line=ink['main'][1],line_width=.7,role='surface',rotation=0,layer='surface',material='paper-card',anchor=anchor)
        objs.insert(start,paper)
        tape=dict(id=module['id']+'-tape',kind='rect',rect=[rx+18,ry-2,rx+72,ry+6],fill='ECE4CA',role='surface',rotation=rnd.choice([-3,3]),anchor=anchor,material='tape',layer='surface')
        objs.append(tape)
        for ob in content:
            if ob['kind']=='text':plan['overlaps'].append(dict(objects=[ob['id'],paper['id']],reason='Source-bound paper backing',min_contrast=4.5))
        for o in content:
            if o['kind']=='rect' and o['role']=='data' and o.get('fill'):
                r=o['rect'];over=dict(id=o['id']+'-registration',kind='rect',rect=[r[0]+2,r[1]+2,r[2]+2,r[3]+2],fill=ink['main'][1],role='overprint',rotation=0,anchor=anchor,material='registration-offset')
                objs.insert(objs.index(o),over)
    else:
        for o in content:
            if o['kind']=='path' and o.get('line') and not o.get('fill'):
                o['paths']=[[[x+rnd.uniform(-.65,.65),y+rnd.uniform(-.65,.65)] for x,y in path] for path in o['paths']]
                o['rect']=bounds(o['paths'],o.get('line_width',1.5)/2);o['material']='jitter-stroke'
        x=rx+3;ys=[ry+7+i*(max(1,bottom-ry-8))/12 for i in range(13)]
        bracket=stroke(module['id']+'-bracket',[[[x+4,ys[0]],[x,ys[0]]]+[[x+rnd.uniform(-.6,.6),y] for y in ys]+[[x+4,ys[-1]]]],material='hand-bracket')
        objs.append(bracket)
        for o in content:
            if o['kind']!='rect' or o['role']!='data' or not o.get('fill'):continue
            r=o['rect'];color=o.pop('fill');o.update(line=color)
            paths=[];height=r[3]-r[1]
            for offset in range(0,max(1,int(r[2]-r[0])),9):
                sx=r[0]+offset;ex=min(r[2],sx+height)
                paths.append([[sx,r[3]],[ex,r[3]-(ex-sx)]])
            if paths:
                hatch=stroke(o['id']+'-hatch',paths,color,material='hatch-fill',width=1.2);hatch['role']='data';hatch['layer']='evidence';objs.append(hatch)

def signature(plan):
    counts=Counter(o.get('material') for o in plan['objects'] if o.get('material'))
    return dict(dialect=plan['dialect'],materials=dict(counts),material_objects=sum(counts.values()),text_rotation_max=max((abs(o.get('rotation',0)) for o in plan['objects'] if o['kind']=='text'),default=0))

"""Seeded editable DrawingML surfaces. No images or example artwork."""
import math
import random
from native_vectors import bounds, native_path, planned_glyphs


def ink_path(kind, rect, seed, amplitude=1.3):
    """Two independently perturbed strokes, anchored to the supplied bounds."""
    rng=random.Random(seed);x,y,x1,y1=rect;w=x1-x;h=y1-y
    if kind=='circle':
        # A slightly squared hand loop leaves room around glyph corners.
        # A mathematical ellipse cuts through wide display figures even when
        # its top/bottom bounds clear the measured line.
        def bow(v):return math.copysign(abs(v)**.65,v)
        points=[(x+w/2+w/2*bow(math.cos(t*math.tau/32)),y+h/2+h/2*bow(math.sin(t*math.tau/32))) for t in range(33)]
    elif kind=='star':
        points=[(x+w/2+math.cos(-math.pi/2+t*math.pi/5)*w/2*(1 if t%2==0 else .44),
                 y+h/2+math.sin(-math.pi/2+t*math.pi/5)*h/2*(1 if t%2==0 else .44)) for t in range(11)]
    elif kind=='bracket':points=[(x,y),(x1,y),(x1,y1),(x,y1)]
    elif kind=='arrow':points=[(x,y+h/2),(x+w*.45,y+h*.45),(x1,y+h/2)]
    else:points=[(x+w*t/16,y+h/2+(math.sin(t*math.pi/4)*h*.35 if kind=='wave' else 0)) for t in range(17)]
    strokes=[]
    for passn in range(2):
        pts=[[round(a+rng.uniform(-amplitude,amplitude),3),round(b+rng.uniform(-amplitude,amplitude),3)] for a,b in points]
        strokes.append(pts)
        if kind=='arrow':strokes.append([[x1-w*.14,y],[x1,y+h/2],[x1-w*.14,y1]])
    return strokes


def torn(rect,seed,teeth=18):
    rng=random.Random(seed);x,y,x1,y1=rect;w=x1-x;h=y1-y
    teeth=min(teeth,max(5,int(w/12)))
    return [[x+i*w/teeth,y+rng.uniform(0,min(4,h*.08))] for i in range(teeth+1)]+[[x1-i*w/teeth,y1-rng.uniform(0,min(4,h*.08))] for i in range(teeth+1)]


def halftone_paths(rect,spacing=14):
    """A scalable native dot field, one custom geometry rather than 100 shapes."""
    x,y,x1,y1=rect
    if spacing<8 or x1-x<80 or y1-y<120:raise ValueError('Halftone must be a substantial field, not edge residue')
    paths=[]
    for row in range(int((y1-y)/spacing)):
        for col in range(int((x1-x)/spacing)):
            cx=x+col*spacing+spacing/2;cy=y+row*spacing+spacing/2
            radius=spacing*.40*(1-row/max(1,(y1-y)/spacing))+.5
            paths.append([[cx+radius*math.cos(i*math.tau/12),cy+radius*math.sin(i*math.tau/12)] for i in range(13)])
    return paths


def stroke_segments(o):
    """Flatten the same cubic curves used by the native writer for glyph QA."""
    for pts in o['paths']:
        for i in range(1,len(pts)):
            b=pts[i-1];c=pts[i]
            if not o.get('smooth') or len(pts)<=3:
                yield b,c;continue
            a=pts[max(0,i-2)];d=pts[min(len(pts)-1,i+1)]
            c1=[b[j]+(c[j]-a[j])/6 for j in (0,1)];c2=[c[j]-(d[j]-b[j])/6 for j in (0,1)]
            prev=b
            for k in range(1,9):
                t=k/8;u=1-t
                now=[u**3*b[j]+3*u*u*t*c1[j]+3*u*t*t*c2[j]+t**3*c[j] for j in (0,1)]
                yield prev,now;prev=now

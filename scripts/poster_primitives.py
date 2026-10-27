"""Seeded editable DrawingML surfaces. No images or example artwork."""
import math
import random
import hashlib
from pptx.oxml.xmlchemy import OxmlElement
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
import riso_kit as rk


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


def bounds(paths,pad=0):
    pts=[v for p in paths for v in p]
    return [min(v[0] for v in pts)-pad,min(v[1] for v in pts)-pad,max(v[0] for v in pts)+pad,max(v[1] for v in pts)+pad]


def native_path(slide,o):
    """Cubic Bezier custom geometry, with editable control points in PowerPoint."""
    x,y,x1,y1=o['rect'];w=max(.1,x1-x);h=max(.1,y1-y)
    sh=rk.shape(slide,MSO_SHAPE.RECTANGLE,x,y,w,h,fill=o.get('fill'),line=o.get('line'),lw=o.get('line_width',1.5),rot=o.get('rotation',0),alpha=o.get('opacity'))
    sp=sh._element.spPr
    for node in list(sp):
        if node.tag.endswith(('prstGeom','custGeom')):sp.remove(node)
    geom=OxmlElement('a:custGeom')
    for tag in ('avLst','gdLst','ahLst','cxnLst'):geom.append(OxmlElement('a:'+tag))
    r=OxmlElement('a:rect')
    for k,v in zip(('l','t','r','b'),('0','0','w','h')):r.set(k,v)
    geom.append(r);lst=OxmlElement('a:pathLst');geom.append(lst)
    def pt(parent,a,b):
        node=OxmlElement('a:pt');node.set('x',str(round((a-x)*1000)));node.set('y',str(round((b-y)*1000)));parent.append(node)
    for pts in o['paths']:
        path=OxmlElement('a:path');path.set('w',str(round(w*1000)));path.set('h',str(round(h*1000)))
        path.set('fill','norm' if o.get('fill') else 'none');path.set('stroke','1' if o.get('line') else '0');lst.append(path)
        move=OxmlElement('a:moveTo');pt(move,*pts[0]);path.append(move)
        for i in range(1,len(pts)):
            if o.get('smooth') and len(pts)>3:
                a=pts[max(0,i-2)];b=pts[i-1];c=pts[i];d=pts[min(len(pts)-1,i+1)]
                seg=OxmlElement('a:cubicBezTo')
                pt(seg,b[0]+(c[0]-a[0])/6,b[1]+(c[1]-a[1])/6)
                pt(seg,c[0]-(d[0]-b[0])/6,c[1]-(d[1]-b[1])/6);pt(seg,*c)
            else:seg=OxmlElement('a:lnTo');pt(seg,*pts[i])
            path.append(seg)
        if o.get('closed'):path.append(OxmlElement('a:close'))
    sp.insert(0,geom);sh.name='art['+o['id']+']'
    from lxml import etree
    o['geometry_sha256']=hashlib.sha256(etree.tostring(geom,method='c14n',exclusive=True)).hexdigest()
    return sh


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


def planned_glyphs(o):
    import textmetrics as tm
    f=o['fit'];face=tm.font(f['font'],f['size'],f['bold'])
    x=o['rect'][0]+max(0,-min((face.getbbox(line)[0] for line in f['lines'] if line),default=0))+.5
    for j,line in enumerate(f['lines']):
        y=o['rect'][1]+j*f['pitch']+max(0,(f['pitch']-tm.line_height(f['font'],f['size'],f['bold']))/2)
        for i,ch in enumerate(line):
            if ch.isspace():continue
            a,b,c,d=face.getbbox(ch);dx=tm.advance(line[:i],f['font'],f['size'],f['bold'],f['spc'])+(f['spc'] if i else 0)
            yield (x+dx+a,y+b,x+dx+c,y+d)

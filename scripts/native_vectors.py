"""Shared DrawingML paths and measured glyph envelopes."""
import hashlib

def bounds(paths,pad=0):
    pts=[v for p in paths for v in p]
    return [min(v[0] for v in pts)-pad,min(v[1] for v in pts)-pad,max(v[0] for v in pts)+pad,max(v[1] for v in pts)+pad]


def native_path(slide,o):
    """Cubic Bezier custom geometry, with editable control points in PowerPoint."""
    from pptx.oxml.xmlchemy import OxmlElement
    from pptx.enum.shapes import MSO_SHAPE
    import riso_kit as rk

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

"""Rendered non-text semantic ink; card backings/garnish do not count."""
def measure(png,plan,background=None):
    from PIL import Image,ImageDraw
    import numpy as np
    img=Image.open(png).convert('RGB');img.thumbnail((1000,1000));w,h=img.size
    sx=w/plan['canvas']['width'];sy=h/plan['canvas']['height']
    if background:
        bg=np.asarray(Image.open(background).convert('RGB').resize((w,h))).astype('int16')
    else:bg=np.array([int(plan['ink_plan']['paper'][j:j+2],16) for j in (0,2,4)],dtype='int16')
    ink=np.abs(np.asarray(img).astype('int16')-bg).sum(axis=2)>45
    mask=Image.new('1',(w,h));draw=ImageDraw.Draw(mask)
    for o in plan['objects']:
        if o['kind']=='text' or o.get('micro') or o.get('role') not in ('data','relation'):continue
        if o['kind']=='path':
            for path in o['paths']:
                xy=[(x*sx,y*sy) for x,y in path]
                if o.get('fill'):draw.polygon(xy,fill=1)
                if o.get('line'):draw.line(xy,fill=1,width=max(1,round(o.get('line_width',1)*sx)))
        else:
            x,y,x1,y1=o['rect'];r=[x*sx,y*sy,x1*sx,y1*sy]
            draw.rectangle(r,fill=1 if o.get('fill') else None,outline=1,width=max(1,round(sx)))
    for o in plan['objects']:
        if o['kind']=='text':
            x,y,x1,y1=o['rect'];draw.rectangle([x*sx,y*sy,x1*sx,y1*sy],fill=0)
    semantic=np.asarray(mask,dtype=bool);actual=ink & semantic
    return dict(nontext_ink_ratio=round(float(actual.mean()),6),semantic_mask_ratio=round(float(semantic.mean()),6),page_nonpaper_ratio=round(float(ink.mean()),6),sample_dimensions=[w,h],threshold_rgb_sum=45,method='render minus background intersect native semantic fill/stroke mask, excluding text boxes, backings and garnish; downsampled to max 1000px')

"""Cheap plan wireframe and contact sheet; never a substitute for PPTX rendering."""
import argparse,json,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter

def wireframe(plan,path,width=650):
    start=time.perf_counter();scale=width/plan['canvas']['width'];height=round(plan['canvas']['height']*scale)
    im=Image.new('RGB',(width,height),'#fbf8ef');d=ImageDraw.Draw(im);font=ImageFont.load_default(size=11)
    for o in plan['objects']:
        if o.get('duplicate_of'):continue
        r=[v*scale for v in o['rect']]
        color='#af7147' if o['role']=='graphic' else '#99ada1' if o.get('layer')=='surface' else '#435c87'
        d.rectangle(r,outline=color,width=1)
        if o['kind']=='text':d.text((r[0]+2,r[1]+2),o['id'],fill='#253448',font=font)
    for n in plan['reading_order']:
        o=next(o for o in plan['objects'] if o['id']==n['objects'][0]);r=o['rect'];d.text((max(0,r[0]*scale-20),r[1]*scale),str(n['order']),fill='#ac382b',font=font)
    for gap in plan.get('voids',[]):d.rectangle([v*scale for v in gap['rect']],outline='red',width=3)
    im.save(path)
    return {'seconds':time.perf_counter()-start,'kind':'plan-wireframe','font_fit_verified':False,'path':str(path)}

def contact(png,path,label=''):
    im=Image.open(png).convert('RGB');full=im.copy();full.thumbnail((700,1000));thumb=im.resize((max(1,round(im.width*.1)),max(1,round(im.height*.1))),Image.Resampling.LANCZOS)
    out=Image.new('RGB',(full.width+thumb.width+36,max(full.height,thumb.height*2+80)+32),'white');d=ImageDraw.Draw(out)
    d.text((8,8),label,fill='black');out.paste(full,(0,32));out.paste(thumb,(full.width+18,32));out.paste(thumb.filter(ImageFilter.GaussianBlur(3)),(full.width+18,thumb.height+70));out.save(path)
    return str(path)

def draft(plan,path,width=850):
    """Low fidelity text/geometry preview. Never substitutes for a saved-PPTX render."""
    import textmetrics as tm
    start=time.perf_counter();scale=width/plan['canvas']['width']
    image=Image.new('RGB',(width,round(plan['canvas']['height']*scale)),'#'+plan['ink_plan']['paper'])
    draw=ImageDraw.Draw(image)
    for o in plan['objects']:
        r=[v*scale for v in o['rect']]
        if o['kind']=='text':
            f=o['fit'];font=tm.font(f['font'],max(1,round(f['size']*scale)),f['bold'])
            for i,line in enumerate(f['lines']):
                draw.text((r[0],r[1]+i*f['pitch']*scale),line,font=font,fill='#'+o['color'])
        elif o['kind']=='path':
            for points in o['paths']:
                xy=[(x*scale,y*scale) for x,y in points]
                if o.get('fill'):draw.polygon(xy,fill='#'+o['fill'])
                if o.get('line'):draw.line(xy,fill='#'+o['line'],width=max(1,round(o.get('line_width',1.5)*scale)))
        elif o.get('fill'):draw.rectangle(r,fill='#'+o['fill'])
    image.save(path)
    return dict(seconds=time.perf_counter()-start,kind='draft-text-and-geometry',saved_pptx_verified=False,path=str(path))

def variants_contact(files,path,labels=None,width=330):
    files=list(files);labels=labels or [Path(f).parent.name for f in files]
    images=[]
    for f in files:
        im=Image.open(f).convert('RGB');im.thumbnail((width,500));images.append(im)
    cols=min(3,len(images));rows=(len(images)+cols-1)//cols
    result=Image.new('RGB',(cols*(width+15),rows*535),'white');d=ImageDraw.Draw(result)
    for i,(im,label) in enumerate(zip(images,labels)):
        x=(i%cols)*(width+15);y=(i//cols)*535
        d.text((x+5,y+3),label,fill='black');result.paste(im,(x,y+25))
    result.save(path);return str(path)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();p=json.loads(Path(a.plan).read_text(encoding='utf-8'));print(json.dumps(wireframe(p,a.out)))

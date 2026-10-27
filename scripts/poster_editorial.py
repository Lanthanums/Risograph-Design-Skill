"""Measured information posters: shared content, distinct editorial compositions.

No generated copy or factual inference. The source order is preserved within
columns. Native rules, tabs and connectors encode actual module boundaries.
"""
import sys
sys.dont_write_bytecode = True
import riso_kit as rk
import typefit as tf


def compose(slide, content, theme, canvas, options, image_path=None):
    from poster_layouts import Typesetter, metadata
    setter = Typesetter(None, theme, canvas, content.get('text_bleed', []), options['alignment'])
    schedule=[]
    def place(role,f,x,y,width,display=False,index=None):
        schedule.append([role,f,x,y,width,display,index])
    x0,y0,x1,y1 = canvas.safe
    w,h = x1-x0,y1-y0
    short = min(canvas.width,canvas.height)
    gap = short*.019
    size = options.get('body_size', max(16, min(22,short*.019)))
    title_size = options.get('title_size',short*.095)
    composition = options['composition']
    if composition == 'auto': composition = 'rail' if content.get('key_number') else 'columns'
    cursor=y0
    structures=[]; diagrams=[]
    quiet_h=h*.10
    if options['graphic']=='band' or image_path:
        import place_decor as pd
        quiet_h=max(quiet_h,canvas.height*.10+pd.TEXT_PAD+pd.GRID)
    if options['footer_anchor']=='edge':
        # Edge footer splits the bottom whitespace. Keep one contiguous quiet
        # band above it, including the checker's text padding on both sides.
        import place_decor as pd
        quiet_h=max(quiet_h,canvas.height*.10+2*pd.TEXT_PAD+pd.GRID)
    def put(role,value,x,y,width,max_h,sz=None,bold=False,index=None,display=False):
        f=setter.measure(role,tf.source_text(value),width,max_h,sz or size,display,
                         short*.05 if display else 16,bold,index)
        place(role,f,x,y,width,display,index)
        return y+f.height
    header_graphic=None
    if options['graphic_position']=='beside_title' and (image_path or options['graphic']!='none'):
        title_w=w*.70-gap
        title_end=put('title',content['title'],x0,cursor,title_w,h*.30,title_size,True,display=True)
        header_h=max(title_end-y0,short*.26)
        header_graphic=(x0+w*.70,y0,x1,y0+header_h)
        cursor=y0+header_h+gap
    else:
        cursor=put('title',content['title'],x0,cursor,w,h*.24,title_size,True,display=True)+gap
    if content.get('subtitle'):
        cursor=put('subtitle',content['subtitle'],x0,cursor,w,h*.10,size*1.18)+gap
    meta=metadata(content)
    if meta:
        cursor=put('metadata',meta,x0,cursor,w,h*.10,size)+gap
    structures.append(('rule',x0,cursor,w,1.5))
    cursor+=gap
    # A deliberate quiet strip is reserved before any content. It is not
    # reclaimed by decoration or by fitting copy smaller than the reading floor.
    bottom=y1-quiet_h
    foot=[]
    for role in ('cta','footer'):
        if content.get(role):
            f=setter.measure(role,content[role],w,h*.10,size,minimum=16,bold=role=='cta')
            foot.append((role,f))
    bottom-=sum(f.height+gap for _,f in foot)
    modules=[]
    if content.get('body'): modules.append([('body',content['body'],False,None)])
    number=content.get('key_number')
    if number is not None:
        value=number.get('value') if isinstance(number,dict) else number
        label=number.get('label') if isinstance(number,dict) else None
        m=[('key_number',str(value),True,None)]
        if label: m.append(('key_number_label',label,False,None))
        modules.insert(0,m)
    quote=content.get('quote')
    if quote:
        m=[('quote',quote.get('text','') if isinstance(quote,dict) else quote,False,None)]
        attribution=quote.get('attribution') if isinstance(quote,dict) else content.get('attribution')
        if attribution:m.append(('attribution',attribution,False,None))
        modules.append(m)
    for i,b in enumerate(content.get('blocks',[])):
        m=[]
        if isinstance(b,str):m.append(('block',b,False,i))
        else:
            if b.get('title'):m.append(('block_title',b['title'],True,i))
            if b.get('text'):m.append(('block',b['text'],False,i))
        if m:modules.append(m)
    for i,row in enumerate(content.get('data',[])):
        modules.append([('block_title',str(row.get('value','')),True,i),
                        ('block',str(row.get('label','')),False,i)])
    # Relations use a compact full-width row rather than a tall list.
    relation_fits=[]
    relation_height=0
    chart=content.get('chart')
    chart_rows=[];chart_title=None
    if chart:
        if chart.get('title'):
            chart_title=setter.measure('chart_title',chart['title'],w,h*.1,size*1.15,minimum=16,bold=True)
            relation_height+=chart_title.height+gap
        for i,row in enumerate(chart['items']):
            label=setter.measure('chart_label',row['label'],w*.30,h*.1,size,minimum=16,index=i)
            value=setter.measure('chart_value',f"{row['value']:g}"+str(chart.get('unit','')),w*.16,h*.1,size,minimum=16,index=i)
            height=max(label.height,value.height)+gap*.6
            chart_rows.append((label,value,height))
            relation_height+=height
        relation_height+=gap
    for kind in ('comparison','process'):
        entries=content.get(kind,[])
        if not entries:continue
        if not 2<=len(entries)<=5:
            raise ValueError(f'explainer {kind}: use 2–5 nodes or allocate the supplied content to blocks')
        variant=options['process_style'] if kind=='process' else 'horizontal'
        node_w=w*.82 if variant=='vertical' else (w-gap*(len(entries)-1))/len(entries)
        fits=[]
        for i,entry in enumerate(entries):
            text='\n'.join(str(entry[k]) for k in ('label','text') if entry.get(k)) if isinstance(entry,dict) else entry
            try:
                fits.append(setter.measure(kind,text,node_w-gap,h*.20,size,minimum=16,index=i))
            except ValueError as exc:
                raise ValueError(f'explainer {kind}: {len(entries)} nodes leave {node_w-gap:.1f}pt outer text width per node. '
                                 'Use process_style vertical, fewer nodes, or allocate full detail to blocks. '+str(exc)) from exc
        hh=max(f.height for f in fits)+gap
        total_h=(hh+gap)*(len(fits)-1)+hh if variant=='vertical' else hh+gap*.5*(len(fits)-1) if variant=='steps' else hh
        relation_fits.append((kind,node_w,fits,hh,variant,total_h))
        relation_height+=total_h+gap*1.5
    body_bottom=bottom-relation_height
    columns=options['columns']
    if columns=='auto':columns=2 if len(modules)>1 else 1
    columns=min(columns,max(1,len(modules)))
    if composition=='ledger':columns=1
    widths=[w] if columns==1 else ([w*.34,w*.66-gap] if composition=='rail' else [(w-gap)/2]*2)
    xs=[x0] if columns==1 else [x0,x0+widths[0]+gap]
    def measure_module(module,width):
        fits=[]
        for role,value,bold,index in module:
            sz=size*2.25 if role=='key_number' else size*1.15 if bold else max(16,size*.82) if role=='attribution' else size
            fits.append((role,setter.measure(role,tf.source_text(value),width,body_bottom-cursor,sz,
                         minimum=16,bold=bold,index=index),index))
        return fits, sum(f.height for _,f,_ in fits)+gap*.35*max(0,len(fits)-1)+gap*1.25
    # Evaluate each possible contiguous split at actual column widths once.
    # Bounded by module count; never scan seeds/canvases or delete source roles.
    # A candidate failing in an UNUSED narrow column must not kill a wide-column
    # assignment. Cache each assigned width; select only feasible contiguous splits.
    measured={}
    def at(col,i):
        key=(col,i)
        if key not in measured:
            try: measured[key]=measure_module(modules[i],widths[col])
            except ValueError as exc: measured[key]=exc
        value=measured[key]
        if isinstance(value,Exception):raise value
        return value
    split=len(modules)
    if columns==2:
        choices=[];failures=[]
        for n in range(1,len(modules)):
            try:
                heights=[sum(at(0,i)[1] for i in range(n)),sum(at(1,i)[1] for i in range(n,len(modules)))]
                choices.append((max(heights),n))
            except ValueError as exc:failures.append(str(exc))
        if not choices:raise ValueError('explainer has no feasible column split: '+failures[0])
        split=min(choices)[1]
    ends=[cursor]*columns
    for i,module in enumerate(modules):
        col=0 if i<split else 1
        fits,hh=at(col,i)
        if ends[col]+hh-gap*.6>body_bottom:
            raise ValueError(f'explainer column {col+1}, module {i}: needs {ends[col]+hh-cursor:.1f}pt in '
                             f'{body_bottom-cursor:.1f}pt; choose columns/rail composition or adjust title allocation. '
                             'Preserve source facts; do not drop modules to make the build pass.')
        yy=ends[col]
        structures.append(('tab',xs[col],yy-4,min(24,widths[col]*.08),2))
        for role,f,index in fits:
            place(role,f,xs[col],yy,widths[col],False,index)
            yy+=f.height+gap*.35
        structures.append(('rule',xs[col],yy+gap*.2,widths[col],.6))
        ends[col]+=hh
    end=max(ends)
    chart_bars=[]
    if chart:
        yy=end+gap*.5
        if chart_title:
            place('chart_title',chart_title,x0,yy,w)
            yy+=chart_title.height+gap
        peak=max(row['value'] for row in chart['items']) or 1
        for i,(label,value,height) in enumerate(chart_rows):
            place('chart_label',label,x0,yy,w*.30,False,i)
            place('chart_value',value,x0+w*.84,yy,w*.16,False,i)
            width=w*.46*chart['items'][i]['value']/peak
            if width>0:chart_bars.append([x0+w*.34,yy+3,width,min(12,height-gap)])
            yy+=height
        end=yy+gap*.5
    for kind,node_w,fits,hh,variant,total_h in relation_fits:
        yy=end+gap*.5;nodes=[]
        for i,f in enumerate(fits):
            xx=x0 if variant=='vertical' else x0+i*(node_w+gap)
            ny=yy+i*(hh+gap) if variant=='vertical' else yy+i*gap*.5 if variant=='steps' else yy
            nodes.append([xx,ny,xx+node_w,ny+hh])
            place(kind,f,xx+gap*.5,ny+gap*.5,node_w-gap,False,i)
        diagrams.append({'kind':kind,'variant':variant,'nodes':nodes,'source_indices':list(range(len(fits))),
                         'edges':[[i,i+1] for i in range(len(fits)-1)] if kind=='process' else []})
        end=yy+total_h+gap
    # Reserve an honest graphic region from measured surplus. First use unused
    # column depth; otherwise insert a band. Never scale body copy to buy artwork.
    graphic_rect=None;image_rect=None
    graphic_reason='disabled' if options['graphic']=='none' else 'no measured room; use source diagram or revise allocations'
    if image_path or options['graphic']!='none':
        rooms=[]
        if options['graphic_position']=='auto' and columns==2:
            rooms=[(xs[c],ends[c]+gap,xs[c]+widths[c],max(ends)-gap) for c in range(columns)]
        rooms=[r for r in rooms if r[3]-r[1]>=short*.16 and (r[2]-r[0])*(r[3]-r[1])>=canvas.area*.035]
        room=header_graphic or max(rooms,key=lambda r:(r[2]-r[0])*(r[3]-r[1]),default=None)
        if room is None:
            band_h=min(short*.23,bottom-end-2*gap)
            if band_h>=short*.16:
                delta=band_h+2*gap
                after_title=options['graphic_position']!='after_content'
                at_y=cursor-gap if after_title else end
                room=(x0,at_y+gap,x1,at_y+gap+band_h)
                if after_title:
                    for r in schedule:
                        if r[3]>=cursor:r[3]+=delta
                    structures=[(k,x,y+delta if y>=cursor-gap else y,ww,hh) for k,x,y,ww,hh in structures]
                    chart_bars=[[x,y+delta,ww,hh] for x,y,ww,hh in chart_bars]
                    for d in diagrams:d['nodes']=[[a,b+delta,c,e+delta] for a,b,c,e in d['nodes']]
                end+=delta
        if room:
            if image_path:image_rect=room
            else:graphic_rect=room
            graphic_reason='measured illustration region; source copy and type size preserved'
        elif image_path or options['graphic']=='band':
            raise ValueError('explainer graphic/image needs a region at least 16% of the short side high; '
                             f'only {max(0,bottom-end-2*gap):.1f}pt surplus. Adjust columns/title allocation; retain source facts.')
    shift=min(h*.08,max(0,(bottom-end)*.30)) if options['vertical_alignment']=='balanced' else 0
    setter.slide=slide
    for role,f,x,y,width,display,index in schedule:
        setter.put_fit(role,f,x,y+shift,width,display,index)
    structures=[(k,x,y+shift,ww,hh) for k,x,y,ww,hh in structures]
    chart_bars=[[x,y+shift,ww,hh] for x,y,ww,hh in chart_bars]
    for d in diagrams:d['nodes']=[[a,b+shift,c,e+shift] for a,b,c,e in d['nodes']]
    if graphic_rect:graphic_rect=[graphic_rect[0],graphic_rect[1]+shift,graphic_rect[2],graphic_rect[3]+shift]
    if image_rect:
        image_rect=[image_rect[0],image_rect[1]+shift,image_rect[2],image_rect[3]+shift]
        if slide is not None:
            from pptx.util import Pt
            a,b,c,d=image_rect
            pic=slide.shapes.add_picture(image_path,Pt(a),Pt(b))
            scale=min((c-a)/pic.width.pt,(d-b)/pic.height.pt)
            pic.width=Pt(pic.width.pt*scale);pic.height=Pt(pic.height.pt*scale)
            pic.left=Pt(a+(c-a-pic.width.pt)/2);pic.top=Pt(b+(d-b-pic.height.pt)/2)
            pic.name='user-image[duotone]'
    body_end=end+shift
    foot_cursor=y1-sum(f.height for _,f in foot)-gap*max(0,len(foot)-1) if options['footer_anchor']=='edge' else body_end+gap
    for role,f in foot:
        setter.put_fit(role,f,x0,foot_cursor,w)
        foot_cursor+=f.height+gap
    if slide is not None:
        if options['structure']=='print':
            draw_print_marks(slide,theme,canvas)
        for i,(x,y,width,height) in enumerate(chart_bars):
            sh=rk.rect(slide,x,y,width,height,fill=theme.inkA if i%2==0 else theme.inkB)
            sh.name=f'information[chart]/bar={i}'
        for kind,x,y,width,height in structures:
            if options['structure']=='none':continue
            if options['structure']=='print' and kind=='rule' and height<1:
                sh=rk.dashed(slide,x,y,x+width,y,theme.title_back)
            else:
                sh=rk.rect(slide,x,y,width,height,fill=theme.front_ink if kind=='rule' else theme.inkA)
            sh.name='information[module]/'+kind
            if options['structure']=='print' and kind=='tab':
                sh=rk.rect(slide,x+width+4,y,width*.35,height,fill=theme.inkB)
                sh.name='information[module]/echo-tab'
        for diagram in diagrams:
            for i,(a,b,c,d) in enumerate(diagram['nodes']):
                sh=rk.rect(slide,a,b,c-a,d-b,fill=None,line=theme.inkA,lw=1)
                sh.name=f"information[{diagram['kind']}]/node={i}"
                # A two-ink cap anchors each source node without another text box.
                cap=rk.rect(slide,a,b-3,min((c-a)*.24,36),3,fill=theme.inkA if i%2==0 else theme.inkB)
                cap.name=f"information[{diagram['kind']}]/cap={i}"
            for a,b in diagram['edges']:
                from pptx.enum.shapes import MSO_CONNECTOR
                from pptx.util import Pt
                from pptx.dml.color import RGBColor
                first,second=diagram['nodes'][a],diagram['nodes'][b]
                vertical=diagram['variant']=='vertical'
                start=((first[0]+first[2])/2,first[3]) if vertical else (first[2],(first[1]+first[3])/2)
                stop=((second[0]+second[2])/2,second[1]) if vertical else (second[0],(second[1]+second[3])/2)
                sh=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Pt(start[0]),Pt(start[1]),Pt(stop[0]),Pt(stop[1]))
                sh.line.color.rgb=RGBColor.from_string(theme.inkA.lstrip('#'))
                from pptx.oxml.xmlchemy import OxmlElement
                arrow=OxmlElement('a:tailEnd');arrow.set('type','triangle')
                sh._element.spPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln').append(arrow)
                sh.name='information[process]/connector'
    return {'roles':setter.roles,'image_rect':image_rect,'role_demotions':[],'diagrams':diagrams,
            'graphic_rect':graphic_rect,'graphic_reason':graphic_reason,
            'layout':dict(options,columns=columns,composition=composition),'vertical_shift':shift,
            'reading_order':[{k:r[k] for k in ('role','block_index','order','rect','shapes')} for r in setter.roles],
            'chart':{'bars':chart_bars,'baseline':0,'unit':chart.get('unit','')} if chart else None,
            'protagonist':'title', 'capacity':{'body_height':body_bottom-cursor,'column_heights':[v-cursor for v in ends],
                                            'modules':len(modules),'quiet_reserved_height':quiet_h}}


def draw_print_marks(slide,theme,canvas):
    """Small editable registration crosses and two ink rails outside the copy.

    These are print furniture, not evidence and not a substitute for a figure.
    Insets adapt to custom safe margins; never cross the copy or page trim.
    """
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    x0,y0,x1,y1=canvas.safe
    margin=min(x0,y0,canvas.width-x1,canvas.height-y1)
    if margin<14:return
    radius=min(3.5,margin*.13)
    for x in (x0/2,(x1+canvas.width)/2):
        for y in (y0/2,(y1+canvas.height)/2):
            s=slide.shapes.add_shape(MSO_SHAPE.OVAL,Pt(x-radius),Pt(y-radius),Pt(2*radius),Pt(2*radius))
            s.fill.background();s.line.color.rgb=RGBColor.from_string(theme.title_front[1:]);s.line.width=Pt(.6)
            s.name='information[print]/registration-ring'
            for a,b,c,d in ((x-radius-2,y,x+radius+2,y),(x,y-radius-2,x,y+radius+2)):
                s=rk.rule(slide,a,b,c-a,theme.title_front,lw=.6) if b==d else rk.rect(slide,a,b,.6,d-b,fill=theme.title_front)
                s.name='information[print]/registration-axis'
    for i,color in enumerate((theme.inkA,theme.inkB)):
        s=rk.rect(slide,x0+i*27,y0/2-1,22,2,fill=color)
        s.name='information[print]/ink-rail'

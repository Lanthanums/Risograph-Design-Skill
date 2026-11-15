"""Shared native evidence forms: poster and deck use the same measured writer."""
import math
import typefit as tf
from glyphs import glyph,circle
from poster_primitives import bounds

FORMS=('text','big-number','stat-tile','pictogram-row','bar-compare','bar-vertical','line-chart','stat-row','ring','stacked-bar',
       'step-flow','before-after','versus','timeline','icon-bullet','pull-quote','stamp','ticket',
       'takeaway-list','key-statement','contrast-pair','concept-stack','hub-spoke',
       'definition-card','summary-box','keyword-band')

def render_module(index,m,rect,context,band=1,col=0):
    """Render editable evidence in a supplied rect; return objects + measured height."""
    rx,ry,x1,y1=rect;rw=x1-rx;rh=y1-ry
    p=context['plan'];objs=p['objects'];ink=p['ink_plan'];body=p['scale_ladder']['body']
    put=context['put'];box=context['rect'];path=context['path'];node=context['node']
    theme=context['theme'];H=p['canvas']['height'];dialect=p['dialect']
    mid=m['id'];base=f'modules.{index}';start=len(objs);visual=m.get('visual','text')
    if visual not in FORMS:raise ValueError('Unsupported visual '+visual)
    from auto_garnish import ICON_BY_TYPE
    d=dict(m.get('visual_data',{}));d.setdefault('icon','person' if d.get('unit') in ('people','participants','participant','人') else ICON_BY_TYPE.get(m.get('info_type'),'document'));pad=context.get('pad',10);tx=rx+pad;tw=rw-2*pad;yy=ry+context.get('top',8)
    headline=m.get('headline','') if m.get('render_heading',True) else ''
    part_to_whole = visual in ('ring', 'stacked-bar')
    percent_labels = part_to_whole and d.get('unit') in ('%', '％')
    chart = part_to_whole or visual in ('bar-compare', 'bar-vertical', 'line-chart')
    unit = d.get('unit', '') if chart and not percent_labels and m.get('render_unit_heading', True) else ''
    if unit:
        from chart_qa import unit_visible
        if not unit_visible(headline, unit):
            headline = f'{headline} ({unit})' if headline else unit
    if headline:
        ob=put(mid+'-heading',headline,tx,yy,tw,context.get('heading_size',25),base+'.headline','parallel_set',True,ink['main'][0]);yy=ob['rect'][3]+context.get('heading_gap',12)
        if unit:
            ob['chart_unit'] = unit
    vr=[tx,yy,tx+tw,ry+rh-10]
    # Chart points carry the unit the way the source parser states it, so the
    # saved point matches its atom whatever the case of the authored unit.
    point_unit=d.get('unit')
    if point_unit:
        from source_profile import quantity
        parsed=quantity('1'+str(point_unit));point_unit=parsed[1] if parsed else point_unit
    def val(suffix,value,xx,yy,width,size=body,bold=False,role='argument'):
        if role=='hero_stat' and dialect=='doodle':bold=False
        ob=put(mid+'-'+suffix,value,xx,yy,width,size,base+'.'+suffix,role,bold,ink['main'][0] if bold else None)
        if ob and suffix.endswith('.value') and visual in ('big-number','stat-tile','bar-compare','bar-vertical','line-chart','ring','stacked-bar','stat-row'):
            item=d.get('items',[])[int(suffix.split('.')[2])] if suffix.startswith('visual_data.items.') else d
            ob['data_label']=dict(atom=item.get('atom'),value=item.get('value',value),unit=d.get('unit',''))
        return ob
    if visual in ('big-number','stat-tile') and context.get('figure'):
        # The print poster sets its own figures: fitted numeral, unit, label.
        yy=context['figure'](m,d,mid,base,tx,yy,tw,bool(context.get('lead')))
    elif visual in ('big-number','stat-tile'):
        value=d.get('value','');label=d.get('label','')
        if d.get('unit') and d['unit'] not in label:label+=' ('+d['unit']+')'
        if not str(value) or not label:raise ValueError(mid+': statistic requires value + label')
        wide=tw>500;label_width=tw*.46 if wide else tw
        number=val('visual_data.value',value,tx,yy,label_width,body*context.get('stat_scale',4)*(1.25 if context.get('lead') else 1),True,'hero_stat')
        number['stat_tile']=True
        labelob=val('visual_data.label',label,tx,number['rect'][3]+3,label_width,body)
        yy=labelob['rect'][3]+12
        # A count uses exactly that many symbols; a percent uses a proportional
        # ring. No invented pictogram scale or additional factual label.
        raw=str(value).replace(',','')
        countable=d.get('unit','') in ('people','participants','participant','samples','sample','users','user','visits','visit','tools','tool','人','件','份','次','个','本','台','册','套','只','辆','户') or (p.get('evidence',{}).get('legacy') and not d.get('unit'))
        if wide and countable and raw.isdigit() and 1<=int(raw)<=40:
            n=int(raw);cols=min(8,n);size=min(48,(tw*.49)/cols-6)
            gx=tx+tw*.51;gy=number['rect'][1]
            for j in range(n):
                xx=gx+(j%cols)*(size+6);sy=gy+(j//cols)*(size+8)
                objs.append(glyph(d.get('icon','person'),[xx,sy,xx+size,sy+size],ink['main'][0],mid+'-count-'+str(j),number['id']))
            yy=max(yy,gy+math.ceil(n/cols)*(size+8)+10)
        elif wide and (raw.endswith('%') or d.get('unit')=='%') and 0<=float(raw.rstrip('%'))<=100:
            fraction=float(raw.rstrip('%'))/100;radius=72;cx=tx+tw*.76;sy=number['rect'][1]+radius
            for j,(frac_start,frac_end) in enumerate(((0,fraction),(fraction,1))):
                outer=[[cx+radius*math.cos(-math.pi/2+(frac_start+(frac_end-frac_start)*k/48)*math.tau),sy+radius*math.sin(-math.pi/2+(frac_start+(frac_end-frac_start)*k/48)*math.tau)] for k in range(49)]
                inner=[[cx+radius*.62*math.cos(-math.pi/2+(frac_start+(frac_end-frac_start)*k/48)*math.tau),sy+radius*.62*math.sin(-math.pi/2+(frac_start+(frac_end-frac_start)*k/48)*math.tau)] for k in range(48,-1,-1)]
                paths=[outer+inner]
                objs.append(dict(id=mid+'-proportion-'+str(j),kind='path',rect=bounds(paths),paths=paths,closed=True,fill=ink['main'][j],role='data',rotation=0,anchor=number['id']))
            yy=max(yy,sy+radius+12)
        else:
            size=28;gx=tx+tw-size;gy=number['rect'][1]+8
            if number['fit']['width']+size+12<tw:
                objs.append(glyph(d.get('icon','document'),[gx,gy,gx+size,gy+size],ink['main'][1],mid+'-glyph',number['id']))
        p['hero']['object_ids'].append(number['id'])
    elif visual=='pictogram-row':
        n=d.get('count');k=d.get('highlight',n)
        if not isinstance(n,int) or not 1<=n<=100 or not isinstance(k,int) or not 0<=k<=n:raise ValueError(mid+': count 1..100 and highlight 0..count required')
        cols=min(n,10);size=min((tw-10*(cols-1))/cols,55);pitch=size+10
        for j in range(n):
            gx=tx+(j%cols)*pitch;gy=yy+(j//cols)*(size+9)
            objs.append(glyph(d.get('icon','person'),[gx,gy,gx+size,gy+size],ink['main'][0] if j<k else ink['main'][1],mid+'-icon-'+str(j),mid+'-heading'))
        yy+=math.ceil(n/cols)*(size+9)+10
        if d.get('label'):yy=val('visual_data.label',d['label'],tx,yy,tw)['rect'][3]+10
    elif visual=='bar-compare':
        items=d.get('items',[]);peak=max((float(t['value']) for t in items),default=0)
        if peak<=0 or any(float(t['value'])<0 for t in items):raise ValueError(mid+': bars require nonnegative values and positive maximum')
        import textmetrics as tm
        from riso_kit import NO_WRAP
        heavy = dialect != 'doodle'
        face = context.get('heading_face', (theme.f_heading, True)) if heavy else (theme.f_body, False)
        value_width = max(70, max(tm.advance(str(item['value']), face[0], body, face[1]) for item in items)
                          * NO_WRAP['slack'] + NO_WRAP['pad_pt'] + 1)
        label_width = min(tw*.52, max(tm.advance(str(t['label']),theme.f_body,body) for t in items)*1.07+14) if context.get('compact_bars') else 0
        zero = tx + label_width + 12 if label_width else tx
        span = tx + tw - zero - value_width - (6 if label_width else 8)
        if span <= 0:
            raise ValueError(mid + ': chart values need more label width; use a full-width chart')
        if context.get('compact_bars'):
            # One line per bar: label column, bar from a common zero, value at its end.
            thickness=context.get('bar_thickness',18)
            for j,item in enumerate(items):
                label=val(f'visual_data.items.{j}.label',item['label'],tx,yy,label_width,body)
                line=label['fit']['pitch'];length=span*float(item['value'])/peak
                bar=box(mid+'-bar-'+str(j),[zero,yy+(line-thickness)/2,zero+length,yy+(line-thickness)/2+thickness],ink['main'][j%2],anchor=label['id'])
                bar['data_point']=dict(atom=item.get('atom'),value=item['value'],unit=point_unit,zero_origin=zero,scale=span/peak,axis='x')
                value=val(f'visual_data.items.{j}.value',item['value'],zero+length+8,yy,value_width,body,True,'hero_stat')
                yy=max(label['rect'][3],value['rect'][3])+body*.55
            items=[]
        for j,item in enumerate(items):
            label=val(f'visual_data.items.{j}.label',item['label'],tx,yy,tw,body);yy=label['rect'][3]+6
            length=span*float(item['value'])/peak
            thickness=context.get('bar_thickness',18)
            bar=box(mid+'-bar-'+str(j),[tx,yy+5,tx+length,yy+5+thickness],ink['main'][j%2],anchor=label['id'])
            bar['data_point']=dict(atom=item.get('atom'),value=item['value'],unit=point_unit,zero_origin=tx,scale=span/peak,axis='x')
            value=val(f'visual_data.items.{j}.value',item['value'],tx+length+8,yy,value_width,body,True,'hero_stat')
            yy=max(yy+thickness+12,value['rect'][3])+12
    elif visual in ('bar-vertical','line-chart'):
        items=d.get('items',[]);peak=max((float(t['value']) for t in items),default=0)
        if len(items)<2 or peak<=0 or any(float(t['value'])<0 for t in items):raise ValueError(mid+': chart needs nonnegative source values')
        # The print poster keeps a line of room above the plot for the value
        # labels and centres every label on its bar or point.
        centred=bool(context.get('compact_bars'));head=body*1.55 if centred else 0
        chart_h=context.get('chart_height',140);baseline=yy+head+chart_h;cell=tw/len(items);points=[]
        path(mid+'-zero-axis',[[[tx,baseline],[tx+tw,baseline]]],role='structure')
        def centre(ob,xx):
            width=ob['rect'][2]-ob['rect'][0];left=min(max(tx,xx-ob['fit']['width']/2),tx+tw-width)
            if len(ob['fit']['lines'])==1:ob['rect'][0]=left;ob['rect'][2]=left+width
        half=min(cell*.25,34) if centred else cell*.25
        for j,item in enumerate(items):
            xx=tx+cell*(j+.5);v=float(item['value']);top=baseline-chart_h*v/peak
            point=dict(atom=item.get('atom'),value=item['value'],unit=point_unit,zero_origin=baseline,scale=chart_h/peak,axis='y')
            if visual=='bar-vertical':
                ob=box(mid+'-bar-'+str(j),[xx-half,top,xx+half,baseline],ink['main'][j%2],anchor=mid+'-heading');ob['data_point']=point
            else:
                ob=path(mid+'-point-'+str(j),[circle(xx,top,4)],anchor=mid+'-heading');ob['data_point']=point;points.append([xx,top])
            value=val(f'visual_data.items.{j}.value',item['value'],xx-cell*.4,top-head if centred else max(yy-32,top-32),cell*.8,body,True,'hero_stat')
            label=val(f'visual_data.items.{j}.label',item['label'],xx-cell*.45,baseline+8,cell*.9,body)
            if centred:centre(value,xx);centre(label,xx)
        if points:path(mid+'-line',[points],anchor=mid+'-heading')
        yy=max(o['rect'][3] for o in objs[start:])+14
    elif visual=='stat-row':
        items=d.get('items',[])
        if not 1<=len(items)<=4:raise ValueError(mid+': stat-row supports 1..4 points')
        cell=tw/len(items)
        for j,item in enumerate(items):
            ob=val(f'visual_data.items.{j}.value',item['value'],tx+j*cell,yy,cell-12,body*3,True,'hero_stat')
            val(f'visual_data.items.{j}.label',item['label'],tx+j*cell,ob['rect'][3]+8,cell-12,body)
        yy=max(o['rect'][3] for o in objs[start:])+12
    elif visual in ('ring','stacked-bar'):
        items=d.get('items',[]);total=100 if d.get('unit') in ('%','％') else float(d.get('total',sum(float(t['value']) for t in items)))
        if total<=0 or any(float(t['value'])<0 for t in items):raise ValueError(mid+': positive part-whole total required')
        # The print poster keys every part: its own ink, a swatch, and the
        # legend beside a smaller ring instead of under it.
        keyed=bool(context.get('compact_bars'));tones=(ink['main'][0],ink['main'][1],ink['accent'],ink['body']) if keyed else ink['main']
        lx=tx;lw=tw;floor=yy
        if visual=='ring' and keyed:
            radius=min(66,tw*.19);cx=tx+radius+2;center_y=yy+radius+4;angle=-math.pi/2
            for j,item in enumerate(items):
                end=angle+float(item['value'])/total*math.tau
                if end-angle<1e-6:continue
                outer=[[cx+radius*math.cos(angle+(end-angle)*k/32),center_y+radius*math.sin(angle+(end-angle)*k/32)] for k in range(33)]
                inner=[[cx+radius*.56*math.cos(angle+(end-angle)*k/32),center_y+radius*.56*math.sin(angle+(end-angle)*k/32)] for k in range(32,-1,-1)]
                paths=[outer+inner];objs.append(dict(id=mid+'-ring-'+str(j),kind='path',rect=bounds(paths),paths=paths,closed=True,fill=tones[j%len(tones)],role='data',rotation=0,anchor=mid+'-heading'));angle=end
            floor=yy+radius*2+14;lx=tx+radius*2+26;lw=tw-radius*2-26;yy+=6
        elif visual=='ring':
            radius=min(110,tw*.26);cx=tx+radius+4;center_y=yy+radius+4;angle=-math.pi/2
            for j,item in enumerate(items):
                end=angle+float(item['value'])/total*math.tau
                outer=[[cx+radius*math.cos(angle+(end-angle)*k/32),center_y+radius*math.sin(angle+(end-angle)*k/32)] for k in range(33)]
                inner=[[cx+radius*.60*math.cos(angle+(end-angle)*k/32),center_y+radius*.60*math.sin(angle+(end-angle)*k/32)] for k in range(32,-1,-1)]
                paths=[outer+inner];objs.append(dict(id=mid+'-ring-'+str(j),kind='path',rect=bounds(paths),paths=paths,closed=True,fill=ink['main'][j%2],role='data',rotation=0,anchor=mid+'-heading'));angle=end
            yy+=radius*2+20
        else:
            px=tx
            for j,item in enumerate(items):
                thickness=max(35,context.get('bar_thickness',24)*1.5)
                width=tw*float(item['value'])/total;box(mid+'-part-'+str(j),[px,yy,px+width,yy+thickness],tones[j%len(tones)],anchor=mid+'-heading');px+=width
            yy+=thickness+13
        for j,item in enumerate(items):
            if keyed:
                box(mid+'-key-'+str(j),[lx,yy+body*.28,lx+body*.55,yy+body*.83],tones[j%len(tones)],anchor=mid+'-heading')
            inset=body*.9 if keyed else 0
            value = f"{item['value']}{d['unit']}" if percent_labels else item['value']
            ob=val(f'visual_data.items.{j}.value',value,lx+inset,yy,54 if keyed else 65,body,True,'hero_stat')
            if percent_labels:
                ob['chart_unit'] = d['unit']
            label=val(f'visual_data.items.{j}.label',item['label'],lx+inset+(54 if keyed else 75),yy,lw-inset-(54 if keyed else 75),body);yy=max(ob['rect'][3],label['rect'][3])+6
        yy=max(yy,floor)
    elif visual in ('step-flow','timeline'):
        items=d.get('items',[]);count=len(items)
        if not count:raise ValueError(mid+': sequence requires items')
        # mark_scale grows the numbered badge with the sheet; 1 keeps it as drawn.
        g=context.get('mark_scale',1);bx=17*g;br=16*g;inset=48*g
        horizontal=d.get('orientation','horizontal')=='horizontal' and tw/count>=140*g
        cell=tw/count if horizontal else tw
        label_height=max(tf.fit(str(item['label']),theme.f_heading,body,cell-inset,H,minimum=body,bold=True,ls=1.08).height for item in items) if horizontal else 0
        link_offset=max(36*g,label_height+12);body_offset=link_offset+14
        vertical_y=yy
        for j,item in enumerate(items):
            sx=tx+j*cell if horizontal else tx;sy=yy if horizontal else vertical_y
            step_start=len(objs)
            badge=path(mid+'-badge-'+str(j),[circle(sx+bx,sy+bx,br)],ink['main'][0],anchor=mid+'-heading')
            num=put(mid+'-order-'+str(j),str(j+1),sx+10*g,sy+4*g,25*g,round(18*g*2)/2,None,'navigation',True)
            # The outline badge encloses rather than crosses its number.
            if j<count-1:
                if horizontal:paths=[[[sx+bx,sy+link_offset],[sx+cell-8,sy+link_offset]],[[sx+cell-15,sy+link_offset-5],[sx+cell-8,sy+link_offset],[sx+cell-15,sy+link_offset+5]]]
                if horizontal:path(mid+'-connect-'+str(j),paths,anchor=num['id'])
            lab=val(f'visual_data.items.{j}.label',item['label'],sx+42*g if horizontal else sx+45*g,sy+4*g if horizontal else sy,cell-inset if horizontal else tw-45*g,body,True)
            detail_y=max(sy+body_offset,lab['rect'][3]+10)
            if item.get('value') is not None:
                detail_y=val(f'visual_data.items.{j}.value',item['value'],lab['rect'][0],detail_y,cell-inset if horizontal else tw-45*g,context.get('detail_size',16))['rect'][3]+6
            if item.get('text'):val(f'visual_data.items.{j}.text',item['text'],sx if horizontal else lab['rect'][0],detail_y,cell-16 if horizontal else tw-45*g,body)
            if not horizontal:
                vertical_y=max(o['rect'][3] for o in objs[step_start:])+22
                if j<count-1:
                    end=vertical_y-6
                    path(mid+'-connect-'+str(j),[[[sx+bx,sy+37*g],[sx+bx,end]],[[sx+bx-5,end-7],[sx+bx,end],[sx+bx+5,end-7]]],anchor=num['id'])
        yy=max(o['rect'][3] for o in objs[start:])+10
    elif visual in ('before-after','versus','contrast-pair') and d.get('items'):
        items=d.get('items',[])
        if len(items)!=2:raise ValueError(mid+': comparison requires exactly two items')
        divider_top=yy
        for j,item in enumerate(items):
            xx=tx+j*(tw/2+8);width=tw/2-20
            label=val(f'visual_data.items.{j}.label',item['label'],xx,yy,width,context.get('pair_size',25),True)
            val(f'visual_data.items.{j}.text',item.get('text',''),xx,label['rect'][3]+10,width,body)
        yy=max(o['rect'][3] for o in objs[start:])+10
        path(mid+'-divider',[[[tx+tw/2,divider_top],[tx+tw/2,yy]]],anchor=mid+'-heading')
    elif visual in ('icon-bullet','pull-quote','stamp'):
        size=34
        if visual=='icon-bullet':objs.append(glyph(d.get('icon','document'),[tx,yy,tx+size,yy+size],ink['main'][1],mid+'-glyph',mid+'-heading'))
        if d.get('items'):
            for j,item in enumerate(d['items']):
                label=val(f'visual_data.items.{j}.label',item['label'],tx+45,yy,tw-45,body,True);yy=label['rect'][3]+8
                if item.get('text'):yy=val(f'visual_data.items.{j}.text',item['text'],tx+45,yy,tw-45,body)['rect'][3]+10
    elif visual in ('takeaway-list','concept-stack','hub-spoke','keyword-band') and d.get('items'):
        for j,item in enumerate(d['items']):
            if visual=='takeaway-list':
                val('nav-'+str(j),str(j+1),tx,yy,32,body,True,'navigation')
            indent=40 if visual=='takeaway-list' else 0
            ob=val(f'visual_data.items.{j}.label',item['label'],tx+indent,yy,tw-indent,body,True)
            yy=ob['rect'][3]+context.get('item_gap',body*.65)
            if item.get('text'):yy=val(f'visual_data.items.{j}.text',item['text'],tx+indent,yy,tw-indent)['rect'][3]+12
            if visual in ('concept-stack','hub-spoke') and j<len(d['items'])-1:
                path(mid+'-relation-'+str(j),[[[tx+8,yy-9],[tx+8,yy+1]]],anchor=ob['id'])
                yy+=12
    quote_indent=0
    if visual=='pull-quote' and context.get('quote_mark') and str(m.get('body','')).lstrip()[:1] not in ('','"','\u201c','\u201d','\u300c',"'",'\u2018'):
        # Words given without marks get one printed opening mark beside them.
        mark_size=max(26*context.get('mark_scale',1),context.get('quote_size',26))*1.9;mark=put(mid+'-mark','\u201c',tx,yy-2,mark_size*.9,mark_size,None,'meta',True,ink['main'][0])
        quote_indent=mark['fit']['width']+10
    if m.get('body'):
        indent=45 if visual=='icon-bullet' and not d.get('items') else quote_indent
        for j,para in enumerate(str(m['body']).split('\n')):
            if not para.strip():continue
            g=context.get('mark_scale',1);size=(min(46*g,math.floor(body*1.9)) if context.get('lead') and len(para)<180 else min(40*g,body*1.6) if len(para)<180 else body*1.15) if visual=='key-statement' else max(26*g,context.get('quote_size',26)) if visual=='pull-quote' else body
            ob=put(mid+'-body-'+str(j),para,tx+indent,yy,tw-indent,size,base+'.body','argument',visual=='key-statement')
            ob['source_part']=j;yy=ob['rect'][3]+body*.6
        # one coverage source, multiple paragraphs
        p['content_roles']=[r for r in p['content_roles'] if r['source']!=base+'.body']
        p['content_roles'].append(dict(id=base+'.body',source=base+'.body',text=str(m['body']),role='argument'))
    if d.get('attribution'):yy=val('visual_data.attribution',d['attribution'],tx+quote_indent,yy,tw-quote_indent,context.get('detail_size',16))['rect'][3]+8
    if visual=='stamp':
        displayed=[o for o in objs[start:] if o['kind']=='text']
        if displayed:
            right=min(tx+tw,max(o['rect'][0]+o['fit']['width'] for o in displayed)+8)
            top=displayed[0]['rect'][1]-5;bottom=max(o['rect'][3] for o in displayed)+5
            path(mid+'-stamp',[[[tx-6,top],[right,top],[right,bottom],[tx-6,bottom],[tx-6,top]]],ink['main'][0],role='structure',anchor=displayed[0]['id'])
    members=objs[start:]
    bottom=max((o['rect'][3] for o in members),default=ry)
    if bottom>ry+rh+1:raise ValueError(f'{mid}: needs {bottom-ry:.1f}pt; allocated {rh:.1f}pt. Increase module weight or choose fewer columns; preserve copy.')
    node(mid,members,[rx,ry,rx+rw,ry+rh],band,col)
    from source_profile import TEXT_FORMS
    p['module_metrics'].append(dict(id=mid,level=m.get('level'),visual=visual,rect=[rx,ry,rx+rw,ry+rh],
                                    text_only=visual in TEXT_FORMS,weight=m.get('weight',1),group=m.get('group')))
    from evidence_style import apply as apply_style
    apply_style(p,start,m,[rx,ry,rx+rw,ry+rh],bottom)
    return dict(objects=objs[start:],height=bottom-ry)

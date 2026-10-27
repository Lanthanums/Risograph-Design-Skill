"""Small source-anchored native marks and measured coordination gates."""
import math,copy
from collections import Counter
import textmetrics as tm
from poster_primitives import planned_glyphs,bounds

def area(r):return max(0,r[2]-r[0])*max(0,r[3]-r[1])
def envelope(rs):return [min(r[0] for r in rs),min(r[1] for r in rs),max(r[2] for r in rs),max(r[3] for r in rs)]

def prepare_title(p):
 """Native single-line plates preserve the explicit baseline distance in LO.

 Short absolute paragraph line spacing changes LibreOffice's first baseline.
 Separate editable lines avoid that renderer-dependent shift while preserving
 exact source fragments and registration for every line.
 """
 objs=p['objects'];title=next(o for o in objs if o['id']=='title');f=title['fit'];lines=f['lines'];p['title_line_pitch']=f['pitch']
 natural=round(f['height']-(len(lines)-1)*f['pitch'],2);replacements=[]
 if len(lines)<2:
  for o in objs:
   if o['id'] in ('title','title-ink'):o['fit']['pitch']=natural
  return
 for i,line in enumerate(lines):
  o=copy.deepcopy(title);o['id']='title' if i==0 else 'title-line-'+str(i);o['text']=line;o['source_part']=i
  o['rect'][1]+=i*f['pitch'];o['rect'][3]=o['rect'][1]+natural
  o['fit'].update(text=line,lines=[line],pitch=natural,height=natural,width=tm.advance(line,f['font'],f['size'],f['bold']))
  dup=copy.deepcopy(o);dup.update(id=o['id']+'-ink',source=None,duplicate_of=o['id'],role='overprint',color=p['ink_plan']['main'][1]);dup['rect']=[v+1.5 for v in dup['rect']]
  replacements.extend([dup,o])
 index=objs.index(title);objs[:]=[o for o in objs if o['id'] not in ('title','title-ink')]
 objs[index-1:index-1]=replacements
 for o in objs:
  if o.get('role')=='graphic' and o.get('anchor')=='title':o['anchor']=replacements[-1]['id']
 for node in p['reading_order']:
  if node['region']=='title':node['objects']=[o['id'] for o in replacements if not o.get('duplicate_of')]

def add_micro(p,options=None):
 options=options or {}
 p['micro_enabled']=options.get('micro_elements',True)
 objs=p['objects'];ink=p['ink_plan'];W=p['canvas']['width'];H=p['canvas']['height'];safe=p['canvas']['safe']
 text=[o for o in objs if o['kind']=='text' and not o.get('duplicate_of') and o.get('source')]
 text=[o for o in text if o.get('source') not in options.get('micro_exclude',[])]
 title_lines=[o for o in text if o.get('source')=='title']
 if title_lines:
  last=max(title_lines,key=lambda o:o['rect'][1])
  text=[o for o in text if o.get('source')!='title' or o is last]
 if not options.get('micro_elements',True):text=[o for o in text if o.get('source','').endswith('.title')]
 priority=sorted(text,key=lambda o:(0 if o['id']=='title' else 1 if o.get('source','').endswith('.title') else 2 if o['role']=='hook' else 3))
 def append(o,target):
  o.update(micro=True,anchor=target['id'],role='emphasis',rotation=o.get('rotation',0));objs.append(o)
  return o
 # Highlighter strips sit on exact original first words; no generated labels.
 for i,target in enumerate(priority[:3]):
  f=target['fit'];line=f['lines'][0];words=line.split();phrase=line
  if not words:continue
  width=tm.advance(phrase,f['font'],f['size'],f['bold'],f.get('spc',0));height=3
  if width*height>W*H*.015:height=W*H*.015/max(1,width)
  face=tm.font(f['font'],f['size'],f['bold']);bb=face.getbbox(phrase);x=target['rect'][0]+.5;y=target['rect'][3]+2
  import layout as lay
  if any(lay.intersection([x,y,x+width+2,y+height],g) for other in objs if other['kind']=='text' for g in planned_glyphs(other)):continue
  o=append(dict(id='micro-highlight-'+str(i),kind='rect',rect=[x,y,x+width+2,y+height],fill=ink['accent'],vocabulary='highlight',source_phrase=phrase),target)
  objs.remove(o);objs.insert(objs.index(target),o);p['overlaps'].append(dict(objects=[o['id'],target['id']],reason='exact supplied phrase highlight',min_contrast=4.5))
 if not options.get('micro_elements',True):return
 # Distinct separators: a filled rule ending in a native diamond.
 candidates=[o for o in text if o.get('source') not in ('title','key_number','key_number.value') and o['role'] not in ('source','meta')][:3]
 for i,target in enumerate(candidates):
  r=target['rect'];length=min(r[2]-r[0],max(100,target['fit']['width']));y=r[3]+1
  append(dict(id='micro-rule-'+str(i),kind='rect',rect=[r[0],y,r[0]+length,y+4],fill=ink['accent'],vocabulary='separator'),target)
 # Two small corner marks at content anchors, not isolated page furniture.
 for i,target in enumerate(priority[:2]):
  r=target['rect'];x=min(safe[2]-24,r[0]+target['fit']['width']+10);gs=list(planned_glyphs(target));y=(min(g[1] for g in gs) if gs else r[1])+2
  if i==0:
   paths=[[[x,y+7],[x+14,y+7]],[[x+7,y],[x+7,y+14]]];kind='plus'
  else:
   paths=[]
   for row in range(3):
    for col in range(4):
     cx=x+col*5;cy=y+row*5;paths.append([[cx+1.1*math.cos(n*math.tau/8),cy+1.1*math.sin(n*math.tau/8)] for n in range(9)])
   kind='corner-dots'
  append(dict(id='micro-corner-'+str(i),kind='path',rect=bounds(paths,1),paths=paths,closed=i==1,fill=ink['accent'] if i else None,line=ink['main'][1] if not i else None,line_width=1.4,vocabulary=kind),target)
 for o in objs:
  if o.get('vocabulary')=='tape':o['micro']=True
 # Tiny documents still receive a bounded vocabulary at their source anchor.
 n=sum(bool(o.get('micro')) for o in objs)
 if n<6 and text:
  target=text[0];r=target['rect']
  for i in range(6-n):
   x=r[0]+i*22;y=r[3]+12
   append(dict(id='micro-dot-'+str(i),kind='rect',rect=[x,y,x+8,y+8],fill=ink['accent'],vocabulary='dot' if i<3 else 'square'),target)

def internal_void(p,region=None):
 """Largest axis-aligned empty rectangle inside the live content envelope.

 Text uses measured visible line envelopes. Margins and decoration do not
 manufacture occupancy. A 48-column grid conservatively bounds the evidence.
 """
 rects=[]
 for o in p['objects']:
  if o.get('duplicate_of'):continue
  if o.get('source') in ('title','subtitle'):continue
  if o['kind']=='text':
   glyphs=list(planned_glyphs(o))
   if glyphs:rects.append(envelope(glyphs))
  elif o['role'] in ('data','relation'):rects.append(o['rect'])
 if len(rects)<2:return dict(share=0,rect=None)
 content=region or envelope(rects);sx,sy,ex,ey=content
 cols,rows=48,64;dx=(ex-sx)/cols;dy=(ey-sy)/rows
 if dx<=0 or dy<=0:return dict(share=0,rect=None)
 occupied=[[False]*cols for _ in range(rows)]
 for a,b,c,d in rects:
  for y in range(max(0,int((b-sy)/dy)),min(rows,math.ceil((d-sy)/dy))):
   for x in range(max(0,int((a-sx)/dx)),min(cols,math.ceil((c-sx)/dx))):occupied[y][x]=True
 heights=[0]*cols;best=(0,None)
 for y in range(rows):
  heights=[0 if occupied[y][x] else heights[x]+1 for x in range(cols)];stack=[]
  for x,h in enumerate(heights+[0]):
   start=x
   while stack and stack[-1][1]>h:
    left,hh=stack.pop();value=(x-left)*hh
    # A ragged outer edge is a margin; a reserved hero band has explicit edges.
    if value>best[0] and (region is not None or 0<left and x<cols):best=(value,[sx+left*dx,sy+(y-hh+1)*dy,sx+x*dx,sy+(y+1)*dy])
    start=left
   if not stack or stack[-1][1]<h:stack.append((start,h))
 return dict(share=round(best[0]*dx*dy/(p['canvas']['width']*p['canvas']['height']),4),rect=best[1],method='48x64 largest empty rectangle; title/masthead, decorative marks and ragged outside margins excluded; explicit hero band retains its edges')

def assess(p):
 objs=p['objects'];by={o['id']:o for o in objs};page=p['canvas']['width']*p['canvas']['height'];body=p['scale_ladder']['body']
 title=by.get('title');micro=[o for o in objs if o.get('micro')];counts=Counter(o.get('vocabulary') for o in micro)
 accent=sum(area(o['rect']) for o in objs if o.get('fill')==p['ink_plan']['accent'])/page
 graphic=[o for o in objs if o['role']=='graphic'];garea=area(envelope([o['rect'] for o in graphic]))/page if graphic else 0
 stat=by.get('key_number.value',by.get('key_number'));hero_fill=None
 paper=by.get('paper-hero',by.get('paper-key_number'))
 if paper:
  members=[o for o in objs if (o.get('source') or '').startswith('key_number') and o['kind']=='text'];glyphs=[r for o in members for r in planned_glyphs(o)]
  if glyphs:hero_fill=area(envelope(glyphs))/max(1,area(paper['rect']))
 void=internal_void(p);fail=[];hero_void=None
 if graphic and p['archetype']=='numeral-hero' and stat:
  safe=p['canvas']['safe'];end=p['content_extent']['top']
  hero_void=internal_void(p,[safe[0],stat['rect'][1],safe[2],end])
  if hero_void['share']>.04:fail.append(f'Graphic hero band empty rectangle exceeds 4% page area: {hero_void["share"]:.4f}')
 title_ratio=title['fit']['size']/body if title else None
 leading=p.get('title_line_pitch',title['fit']['pitch'])/title['fit']['size'] if title else None
 if title and not 3<=title_ratio<=4:fail.append(f'Title/body ratio outside 3..4: {title_ratio:.3f}')
 if title and not .9<=leading<=1.12:fail.append(f'Title leading outside .9..1.12: {leading:.3f}')
 if p['archetype']=='numeral-hero' and (not stat or stat['fit']['size']<body*2.2 or stat['color']==p['ink_plan']['body']):fail.append('numeral-hero requires an independent primary numeral style')
 if p['archetype']=='numeral-hero' and stat and stat['fit']['size']/body>4.1:fail.append('Hero/body ratio exceeds 4.1')
 if hero_fill is not None and hero_fill<.5:fail.append(f'Hero occupied envelope below 50%: {hero_fill:.3f}')
 if garea>.06:fail.append(f'Graphic group exceeds 6%: {garea:.3f}')
 for o in graphic+micro:
  if o.get('anchor') not in by:fail.append('Missing content anchor: '+o['id'])
 if graphic:
  gr=envelope([o['rect'] for o in graphic]);anchor=by.get(graphic[0].get('anchor'))
  if anchor:
   ar=anchor['rect'];distance=math.hypot(max(0,gr[0]-ar[2],ar[0]-gr[2]),max(0,gr[1]-ar[3],ar[1]-gr[3]))
   if distance>36:fail.append(f'Graphic group more than 36pt from content anchor: {distance:.1f}')
 if micro and p.get('micro_enabled',True):
  if not 6<=len(micro)<=12:fail.append('Micro element count outside 6..12')
  if len(counts)<3:fail.append('Micro vocabulary has fewer than three types')
  if any(v>3 for v in counts.values()):fail.append('Non-number micro vocabulary repeated more than three times')
  if any(area(o['rect'])/page>.0151 for o in micro):fail.append('Micro element exceeds 1.5% page area')
  if accent<.001:fail.append(f'Accent area below calibrated safe-rule floor 0.1%: {accent:.4f}')
 if void['share']>.08:fail.append(f'Internal empty rectangle exceeds 8% page area: {void["share"]:.4f}')
 return dict(title_body_ratio=title_ratio,title_leading=leading,hero_fill=hero_fill,graphic_area=garea,micro_count=len(micro),micro_types=dict(counts),accent_area=accent,internal_void=void,graphic_hero_void=hero_void,fails=fail)

def finish_plan(p,options):
 p['coordination']=assess(p)
 p['coordination_policy']=dict(title_default_pt=64,title_body_band=[3,4],title_default_ratio=[3,4],hero_body_band=[2.2,4.1],leading_band=[.9,1.12],hero_occupied_envelope_min=.5,graphic_area_max=.06,micro_count=[6,12],micro_area_max=.015,accent_area_min=.001,internal_void_area_max=.08)
 p['spacing_policy']='bounded module gaps <=32pt, padding surplus <=8pt, compact footer and aligned column starts'

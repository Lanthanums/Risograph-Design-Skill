"""Measured poster QA and honest, hash-bound visual review artifacts.

No automatic rubric scores: review requires looking at PNG/thumbnail/blur.
"""
import argparse
from collections import Counter,deque
import hashlib
import json
import math
from pathlib import Path
import re
from PIL import Image,ImageFilter
import layout as lay
import textmetrics as tm
from poster_direction import contrast,digest

RUBRIC=['thumbnail_hero','hierarchy_scale','role_treatment','graphic_meaning','ink_accent_overprint','micro_print','rhythm_whitespace','grid_alignment','readability']

def rubric_for(dialect='swiss'):
    return RUBRIC+(['controlled_looseness'] if dialect!='swiss' else [])

def object_id(shape):
    m=re.match(r'art\[(.*?)\]',shape.name)
    return m.group(1) if m else None

def whitespace(rects,canvas):
    """Connected free regions on a 48x68 occupancy grid; location is retained."""
    cols,rows=48,68;dx=canvas.width/cols;dy=canvas.height/rows
    free={(c,r) for c in range(cols) for r in range(rows)}
    for x0,y0,x1,y1 in rects:
        for c in range(max(0,int(x0/dx)),min(cols,math.ceil(x1/dx))):
            for r in range(max(0,int(y0/dy)),min(rows,math.ceil(y1/dy))):free.discard((c,r))
    components=[]
    while free:
        first=min(free);free.remove(first);q=deque([first]);cells=[]
        while q:
            c,r=q.popleft();cells.append((c,r))
            for n in ((c-1,r),(c+1,r),(c,r-1),(c,r+1)):
                if n in free:free.remove(n);q.append(n)
        xs,ys=zip(*cells)
        components.append({'share':len(cells)/(cols*rows),'rect':[min(xs)*dx,min(ys)*dy,(max(xs)+1)*dx,(max(ys)+1)*dy],
                           'touches':[s for s,test in [('left',min(xs)==0),('right',max(xs)==cols-1),('top',min(ys)==0),('bottom',max(ys)==rows-1)] if test]})
    return sorted(components,key=lambda o:-o['share'])[:12]

def check_slide(slide,idx,canvas,p):
    modern=p.get('version') in ('3.5','3.6','3.7','3.8')
    regional=modern or p.get('dialect','swiss')!='swiss'
    fails=[];warns=[];texts=tm.audit(slide,mode='ink' if regional else 'box');by={o['id']:o for o in p['objects']}
    from poster_dialects import validate_plan
    if modern:
        from poster_flow import validate_reading,voids
        fails.extend(validate_reading(p))
    elif regional:fails.extend(validate_plan(p))
    shapes=list(slide.shapes)
    # Avoid repeating font/glyph walks for every surface/text pair.
    glyphs={object_id(t['shape']):tm.glyph_rects(t['shape']) for t in texts} if regional else {}
    shape_by={}
    for s in slide.shapes:
        id=object_id(s)
        if id:shape_by.setdefault(id,[]).append(s)
        elif s.name!='riso-paper[background]':fails.append('Unplanned object: '+s.name)
    if set(shape_by)!=set(by):fails.append('Plan/object inventory differs')
    if regional:
        from lxml import etree
        for oid,ss in shape_by.items():
            o=by.get(oid)
            if not o:continue
            for sh in ss:
                rot=(sh.rotation+180)%360-180
                if abs(rot-o.get('rotation',0))>.01:fails.append('Actual rotation differs from plan: '+oid)
                expected=list(o['rect'])
                if o['kind']=='text':
                    f=o['fit'];face=tm.font(f['font'],f['size'],f['bold'])
                    expected[0]+=max(0,-min((face.getbbox(line)[0] for line in f['lines'] if line),default=0))+.5
                if any(abs(a-b)>.1 for a,b in zip((sh.left.pt,sh.top.pt,sh.left.pt+sh.width.pt,sh.top.pt+sh.height.pt),expected)):fails.append('Actual geometry differs from plan: '+oid)
                if o['kind']=='path':
                    geom=sh._element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}custGeom')
                    if geom is None or hashlib.sha256(etree.tostring(geom,method='c14n',exclusive=True)).hexdigest()!=o.get('geometry_sha256'):fails.append('Native curve differs from plan: '+oid)
                    if o.get('line') and (sh.line.width is None or abs(sh.line.width.pt-o.get('line_width',1.5))>.01):fails.append('Actual stroke differs from plan: '+oid)
                    if o.get('opacity') is not None:
                        alpha=sh._element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill/{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr/{http://schemas.openxmlformats.org/drawingml/2006/main}alpha')
                        actual_alpha=int(alpha.get('val'))/1000 if alpha is not None else 100
                        if abs(actual_alpha-o['opacity'])>.01:fails.append('Actual opacity differs from plan: '+oid)
    declared={frozenset(o['objects']):o for o in p['overlaps']}
    pairs=[]
    actual_sizes=[];actual_colors={}
    for t in texts:
        id=object_id(t['shape']);o=by.get(id)
        if not o or o['kind']!='text':fails.append('Unplanned text');continue
        if not lay.inside(t['rect'],canvas.safe,tol=2):fails.append('Text outside safe bounds: '+id)
        if re.sub(r'\s+','',t['text'])!=re.sub(r'\s+','',o['text']):fails.append('Text differs from plan: '+id)
        for para in t['shape'].text_frame.paragraphs:
            for run in para.runs:
                if run.text:
                    size=run.font.size.pt if run.font.size else 0;actual_sizes.append(size)
                    if size<16:fails.append('Type below 16pt: '+id)
                    if not tm.resolve(run.font.name):fails.append('Unresolved font: '+str(run.font.name))
                    try:actual_colors[id]=str(run.font.color.rgb)
                    except Exception:fails.append('Unresolved text color: '+id)
        # Check no-wrap shape widths/height, using shared measured line records.
        for line in tm.line_records(t['shape']):
            width=sum(tm.advance(tx,opt['font'],opt['size'],opt['bold'],opt['spc']) for tx,opt in line['runs'])
            if width>t['shape'].width.pt+1:fails.append('Measured line exceeds frame: '+id)
        records=tm.line_records(t['shape'])
        if sum(r['h']+r['before']+r['after'] for r in records)>t['shape'].height.pt+2:fails.append('Measured text exceeds frame height: '+id)
    for i,t in enumerate(texts):
        aid=object_id(t['shape'])
        for other in texts[i+1:]:
            bid=object_id(other['shape'])
            if lay.intersection(t['rect'],other['rect']):
                if regional and (by.get(aid,{}).get('duplicate_of')==bid or by.get(bid,{}).get('duplicate_of')==aid):
                    original,duplicate=(by[bid],by[aid]) if by.get(aid,{}).get('duplicate_of')==bid else (by[aid],by[bid])
                    if original['text']!=duplicate['text'] or original['fit']!=duplicate['fit']:fails.append('Ink layer differs from source: '+duplicate['id'])
                    continue
                # Text/text overlap is not made readable merely by declaration.
                fails.append('Text collision: '+str(aid)+' / '+str(bid));pairs.append([aid,bid])
        if by.get(aid,{}).get('duplicate_of'):continue
        for zi,s in enumerate(shapes):
            bid=object_id(s)
            if bid==aid or s.name=='riso-paper[background]' or (s.has_text_frame and s.text_frame.text.strip()):continue
            if not lay.intersection(t['rect'],lay.obb(s)):continue
            if regional and by.get(bid,{}).get('kind')=='path' and not by[bid].get('fill'):
                from poster_primitives import stroke_segments
                hit=any(lay.segment_rect_distance(a,b,g)<=by[bid].get('line_width',1.5)/2+.5 for a,b in stroke_segments(by[bid]) for g in glyphs[aid])
                if hit:fails.append('Surface stroke crosses glyph: '+str(aid)+' / '+str(bid))
                continue
            pair=frozenset((aid,bid));declaration=declared.get(pair)
            if not declaration:fails.append('Undeclared text/shape overlap: '+str(aid)+' / '+str(bid));continue
            # A fully covering later native plate hides this plate from the text.
            # Check that visible plate in its own iteration; do not test occluded ink.
            covered=False
            for later in shapes[zi+1:]:
                lid=object_id(later)
                if lid in by and by[lid]['kind']=='rect' and lay.inside(lay.obb(s),lay.obb(later),tol=.1):
                    covered=True;break
            if covered:continue
            # Use actual fill/actual text, not a claimed metadata contrast score.
            try:
                bg=str(s.fill.fore_color.rgb)
                if regional and by.get(bid,{}).get('opacity') is not None:
                    alpha_node=s._element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill/{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr/{http://schemas.openxmlformats.org/drawingml/2006/main}alpha')
                    alpha=int(alpha_node.get('val'))/100000 if alpha_node is not None else 1
                    base=p['ink_plan']['paper']
                    bg=''.join(f'{round(int(bg[j:j+2],16)*alpha+int(base[j:j+2],16)*(1-alpha)):02X}' for j in (0,2,4))
            except Exception:fails.append('Overlap background cannot be checked: '+str(bid));continue
            if contrast(actual_colors.get(aid,'000000'),bg)<declaration.get('min_contrast',4.5):fails.append('Intentional overlap fails contrast: '+str(aid)+' / '+str(bid))
        if aid in by and not by[aid].get('duplicate_of') and contrast(actual_colors.get(aid,'000000'),by[aid].get('background',p['ink_plan']['paper']))<4.5:fails.append('Text/paper contrast too low: '+str(aid))
    # Coverage checks use original exact strings in plan, normalized only for wraps.
    coverage={}
    for o in sorted(p['objects'],key=lambda o:o.get('source_part',0)):
        if o['kind']=='text' and o.get('source'):coverage.setdefault(o['source'],[]).append(o['text'])
    for r in p['content_roles']:
        actual=''.join(coverage.get(r['source'],[]))
        if re.sub(r'\s+','',actual)!=re.sub(r'\s+','',r['text']):fails.append('Source coverage mismatch: '+r['source'])
    for issue in lay.measured_issues(slide):fails.append(issue)
    # Use current native object bounds for metrics, even after manual editing.
    for id,shapes in shape_by.items():
        if id not in by:continue
        rects_live=[lay.obb(s) for s in shapes]
        by[id]=dict(by[id],rect=[min(r[0] for r in rects_live),min(r[1] for r in rects_live),max(r[2] for r in rects_live),max(r[3] for r in rects_live)])
    if modern:
        live=dict(p,objects=list(by.values()))
        fails.extend(validate_reading(live))
        empty=voids(live)
        for gap in empty:
            if not gap['intentional']:fails.append('Middle-page void exceeds 8%: '+str(gap['rect'])+'; rerun poster_run --autofit')
        if not p.get('graphic_design',{}).get('recipe') and not p.get('hero',{}).get('object_ids'):warns.append('Flat composition: no graphic or hero')
        if not p.get('graphic_design',{}).get('recipe') and max((o['fit']['size'] for o in by.values() if o['kind']=='text' and o['role']=='hook'),default=0)<48:warns.append('Flat composition: typography hero below 48pt and no graphic; revise hierarchy')
        if len(p.get('micro_layer',[]))<3:warns.append('Flat composition: material layers missing')
    rects=[t['rect'] for t in texts]
    visible=[o for o in by.values() if o['kind']!='text']
    rects.extend(o['rect'] for o in visible if o['kind']!='halftone')
    components=whitespace(rects,canvas)
    sizes=[o['fit']['size'] for o in by.values() if o['kind']=='text']
    body_sizes=[o['fit']['size'] for o in by.values() if o['kind']=='text' and o['role']=='argument'] or [p['scale_ladder']['body']]
    body=min(body_sizes);maxfont=max(sizes,default=0)
    accent=sum(lay.area(o['rect']) for o in visible if o.get('fill')==p['ink_plan']['accent'])/canvas.area
    decoration=sum(lay.area(o['rect']) for o in visible if o['role'] in ('support','detail','emphasis') or o.get('layer')=='surface' and o.get('vocabulary') not in ('shadow','register'))/canvas.area
    if accent>p['constraints']['accent_cap']:fails.append('Accent exceeds archetype budget')
    if modern:
        # Paper backings are structural surfaces, not free decoration; assess
        # their contrast and glyph crossings above, not summed overlap area.
        decoration=sum(lay.area(o['rect']) for o in visible if o['role'] in ('support','detail','emphasis','graphic'))/canvas.area
    if decoration>p['constraints']['decor_cap']:fails.append('Decoration exceeds archetype budget')
    edge=max([o['rect'][3] for o in by.values() if o['kind']=='text' and o['role'] not in ('source','cta')],default=0)
    # Edge gutter and intentional quiet-region reporting, never total-whitespace quota.
    lowest=min([o['rect'][1] for o in by.values() if o['kind']=='text' and o['role'] in ('source','cta')]+[canvas.safe[3]])
    trailing=max(0,lowest-edge)/canvas.height
    if trailing>p['constraints']['max_edge_void']:warns.append(f'Large unused lower interval: {trailing:.1%}; revise content distribution')
    groups={}
    for o in by.values():
        if o['kind']=='text' and o['role']=='parallel_set':
            semantic_set=(o.get('source') or '').split('.')[0]
            groups.setdefault((semantic_set,round(o['rect'][0],1)),[]).append(o['rect'][2])
    deviations={str(k):round(max(v)-min(v),2) for k,v in groups.items()}
    if not regional and any(v>1 for v in deviations.values()):fails.append('Parallel module right edges differ')
    style_roles={}
    for role in ('hook','hero_stat','cta'):
        source_ids={r['source'] for r in p['content_roles'] if r['role']==role}
        objects=[o for o in by.values() if o['kind']=='text' and o.get('source') in source_ids]
        style_roles[role]={'present':bool(source_ids),'independent':bool(objects) and all(o['fit']['size']>body*1.1 or o['background']!=p['ink_plan']['paper'] for o in objects)}
    repeats=Counter(re.sub(r'-\d+$','',o['id']) for o in visible if not o.get('micro') and o['role'] not in ('structure','data','relation','overprint','surface','graphic'))
    if regional:
        mark_repeats=Counter((o.get('vocabulary'),o.get('anchor')) for o in visible if o.get('layer')=='surface')
        if any(n>2 for n in mark_repeats.values()):fails.append('Repeated surface at same content anchor')
    if any(n>p['constraints']['max_nonstructural_repeat'] for n in repeats.values()):fails.append('Nonstructural ornament repeats too often')
    if p.get('version')=='3.6':
        from poster_harmony import assess
        harmony=assess(dict(p,objects=list(by.values())))
        fails.extend(harmony['fails'])
    if p.get('mode')=='infographic':
        from infographic import assess
        measured=assess(dict(p,objects=list(by.values())))
        fails.extend(measured['fails']);warns.extend(measured['warnings'])
        from chart_qa import check as source_chart_check
        chart_check=source_chart_check(slide,p)
        fails.extend(chart_check['errors'])
    maxelement=max((lay.area(o['rect']) for o in by.values()),default=0)/canvas.area
    metrics={'max_body_type_ratio':round(maxfont/body,3),'max_element_area_share':round(maxelement,4),'accent_area_share':round(accent,4),
             'whitespace_components':components,'trailing_blank_share':round(trailing,4),'right_edge_deviation_pt':deviations,'decoration_repeats':dict(repeats),'role_styles':style_roles,
             'actual_type_sizes':sorted(set(actual_sizes),reverse=True),'measurement':'native object bounds; raster craft review is separate'}
    if p.get('mode')=='infographic':metrics['infographic']=measured
    return {'page':idx,'pass':not fails,'fails':sorted(set(fails)),'warns':sorted(set(warns)),'metrics':metrics,
            'tier':p['density'],'words':p['content_words'],'max_font':maxfont,'decor_count':len(visible),'decor_area':decoration,'chrome_count':0,'foci':1,
            'quiet_rect':components[0]['share'] if components else 0,'overlap_text':pairs,'overlap_chrome':[]}

def review_images(png,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    im=Image.open(png).convert('RGB');thumb=im.resize((max(1,round(im.width*.1)),max(1,round(im.height*.1))),Image.Resampling.LANCZOS)
    thumb.save(out/'thumbnail-10pct.png');thumb.filter(ImageFilter.GaussianBlur(3)).save(out/'blur.png')
    return {'render_sha256':hashlib.sha256(Path(png).read_bytes()).hexdigest(),'render_size':list(im.size),'thumbnail_size':list(thumb.size)}

def validate_review(review,provenance):
    if review.get('render_sha256')!=provenance['render_sha256']:raise ValueError('Visual review is stale for this PNG')
    scores=review.get('scores',{})
    modern=review.get('mode') in ('fast','audit')
    expected=RUBRIC if modern else rubric_for(review.get('dialect','swiss'))
    if set(scores)!=set(expected) or any(not isinstance(v,(float,int)) or isinstance(v,bool) or not 0<=v<=5 for v in scores.values()):raise ValueError('All applicable rubric scores in 0..5 required; controlled_looseness is N/A for swiss')
    weak=review.get('weaknesses',[])
    from poster_contract import validate_weaknesses
    errors=validate_weaknesses(weak,modern)
    if errors:raise ValueError('\n'.join(errors))
    if not review.get('reviewer') or not review.get('viewed',{}).get('full') or not review['viewed'].get('thumbnail') or not review['viewed'].get('blur'):raise ValueError('Reviewer and full/thumbnail/blur inspection required')
    return True

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--png',required=True);ap.add_argument('--out',required=True);ap.add_argument('--review');ap.add_argument('--scaffold',action='store_true');ap.add_argument('--dialect',choices=['swiss','collage','doodle']);ap.add_argument('--plan');ap.add_argument('--mode',choices=['fast','audit'],default='fast');a=ap.parse_args()
    provenance=review_images(a.png,a.out)
    plan=json.loads(Path(a.plan).read_text(encoding='utf-8')) if a.plan else {}
    dialect=plan.get('dialect') or a.dialect
    if plan and a.dialect and a.dialect!=plan.get('dialect'):raise ValueError('CLI dialect conflicts with plan; plan is the source of truth')
    if a.review:
        review=json.loads(Path(a.review).read_text(encoding='utf-8'))
        if review.get('plan_sha256') and not a.plan:raise ValueError('Hash-bound review requires --plan; do not omit the plan/PPTX checks')
        if plan.get('version')=='3.7' or review.get('plan_sha256'):
            if review.get('plan_sha256')!=hashlib.sha256(Path(a.plan).read_bytes()).hexdigest():raise ValueError('Visual review is stale for this plan')
            deck=Path(a.plan).with_name('poster.pptx')
            if not deck.exists() or review.get('pptx_sha256')!=hashlib.sha256(deck.read_bytes()).hexdigest():raise ValueError('Visual review is stale for this PPTX')
        if dialect and review.get('dialect') and review['dialect']!=dialect:raise ValueError('Review dialect conflicts with effective plan/CLI dialect')
        review.setdefault('dialect',dialect or 'swiss');validate_review(review,provenance);provenance['review_valid']=True
    else:
        dialect=dialect or 'swiss'
        provenance.update(review_valid=False,status='AWAITING_VISUAL_REVIEW',rubric=RUBRIC,dialect=dialect)
        template=dict(provenance,mode=a.mode,reviewer='',viewed=dict(full=False,thumbnail=False,blur=False),scores=dict.fromkeys(RUBRIC,None),weaknesses=[__import__('poster_contract').weakness_example()])
        if a.plan:
            template['plan_sha256']=hashlib.sha256(Path(a.plan).read_bytes()).hexdigest()
            deck=Path(a.plan).with_name('poster.pptx')
            if deck.exists():template['pptx_sha256']=hashlib.sha256(deck.read_bytes()).hexdigest()
        target=Path(a.out)/'review.json'
        if a.scaffold or not target.exists():target.write_text(json.dumps(template,ensure_ascii=False,indent=2),encoding='utf-8')
        from poster_preview import contact
        contact(a.png,Path(a.out)/'contact.png',dialect)
    (Path(a.out)/'review-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print(json.dumps(provenance,indent=2))
if __name__=='__main__':main()

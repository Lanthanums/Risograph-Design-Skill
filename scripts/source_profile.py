"""Deterministic bilingual source evidence with exact offsets and conservative units.

No labels/types supplied by an agent are trusted as proof. The profile records
exclusions and uncertainty; it does not establish external factual correctness.
"""
import argparse
import hashlib
import json
import math
import re
from collections import defaultdict

CN='零〇一二两三四五六七八九十百千万亿'
UNIT=r'%|％|percent\b|percentage points\b|kg\b|km\b|kWh\b|litres?\b|liters?\b|hours?\b|minutes?\b|people\b|participants?\b|samples?\b|users?\b|visits?\b|tools?\b|GBP\b|USD\b|EUR\b|公斤|千克|千米|公里|分钟|小时|平方米|人|元|吨|升|件|份|次|个|本|台|册|套|只|辆|户|条|项|种'
TOKEN=re.compile(rf'百分之[{CN}点\d.]+|[$£€¥￥]\s*\d[\d,]*(?:\.\d+)?|(?<![\w.])[+-]?\d[\d,]*(?:\.\d+)?[万亿]?(?:\s*(?:{UNIT}))?|[{CN}点]+(?:{UNIT})(?![A-Za-z])',re.I)

def cn_number(s):
    if re.fullmatch(r'\d+(?:\.\d+)?',s):return float(s)
    digits={c:i for i,c in enumerate('零一二三四五六七八九')};digits.update(〇=0,两=2)
    if '点' in s:
        left,right=s.split('点',1)
        return cn_number(left or '零')+float('0.'+''.join(str(digits[c]) for c in right))
    for unit,multiplier in [('亿',100000000),('万',10000)]:
        if unit in s:
            left,right=s.split(unit,1)
            return cn_number(left or '一')*multiplier+cn_number(right or '零')
    total=section=n=0
    for c in s:
        if c in digits:n=digits[c]
        elif c in '十百千':section+=(n or 1)*{'十':10,'百':100,'千':1000}[c];n=0
        elif c in '万亿':total+=(section+n)*{'万':10000,'亿':100000000}[c];section=n=0
        else:raise ValueError(s)
    return float(total+section+n)

def quantity(raw):
    compact=raw.replace(',','').replace(' ','').replace('％','%')
    if compact.startswith('百分之'):return cn_number(compact[3:]),'%'
    m=re.match(rf'([$£€¥￥])?([+-]?\d+(?:\.\d+)?[万亿]?|[{CN}点]+)(.*)',compact)
    if not m:return None
    raw=m[2]
    n=(float(raw[:-1])*{'万':10000,'亿':100000000}[raw[-1]]) if re.fullmatch(r'[+-]?\d+(?:\.\d+)?[万亿]',raw) else cn_number(raw) if re.search(f'[{CN}]',raw) else float(raw)
    unit=(m[1] or m[3]).lower()
    unit={'percent':'%','litres':'l','litre':'l','liters':'l','liter':'l','升':'l','公斤':'kg','千克':'kg'}.get(unit,unit)
    return n,unit

def quantities(s,atom,context=None):
    accepted=[];excluded=[]
    # Global identifiers/dates, including embedded tokens in phone strings.
    blocked=[]
    patterns=[(r'\b(?:19|20)\d{2}(?:[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?)?\b','year/date'),
              (r'\b\d{1,2}:\d{2}(?::\d{2})?\b','time'),
              (r'(?<!\d)(?:\+?\d[\d ()-]{6,}\d)(?!\d)','phone/identifier'),
              (r'\b(?:ID|tel|phone|ISBN|chapter|section|rank|ranking|no\.)\s*[:#.]?\s*[\d.-]+','identifier/rank/section'),
              (rf'第[\d{CN}]+[章节条名]|排名\s*[\d{CN}]+','section/rank'),
              (rf'(^|\n)\s*(?:\d+|[{CN}]+)[.)、．]\s*','enumeration'),
              (rf'(?:\d+|[{CN}]+)\s*(?:ways|tips|steps|suggestions|reasons|ideas|条建议|个建议|种方法|个方法|个步骤|条提示)\b?','list count'),
              (rf'(?:\d+|[{CN}]+)[个条项种点](?:建议|方面|观点|原因|理由|方法|步骤|提示|要点|问题|角度|层面|想法|办法|方式)','structural count'),
              (r'100\s*%\s*(?:committed|dedicated|ready|sure)|百分之百(?:投入|承诺|努力)','idiom')]
    for pattern,reason in patterns:
        # Python disallows optional zero-width assertions.
        pattern=pattern.replace(r'\b?',r'(?:\b|(?=[\u3400-\u9fff]))')
        for m in re.finditer(pattern,s,re.I):blocked.append((m.start(),m.end(),reason))
    for m in TOKEN.finditer(s):
        q=quantity(m[0]);reason=next((r for a,b,r in blocked if m.start()<b and m.end()>a),None)
        if q is None:continue
        number,unit=q
        if reason=='year/date' and unit:reason=None
        if context and not unit and reason in (None,'unqualified number (no measured unit)'):
            unit=quantity(str(number)+str(context['unit']))[1]
        if not reason and not unit:reason='unqualified number (no measured unit)'
        row=dict(raw=m[0],value=number,unit=unit,provenance=dict(atom=atom,start=m.start(),end=m.end(),quote=m[0]))
        if context:row['unit_provenance']=context
        if reason:excluded.append(dict(row,reason=reason))
        else:accepted.append(row)
    return accepted,excluded

def profile(atoms):
    rows=[];numeric=[];excluded=[];groups=defaultdict(list)
    for atom in atoms:
        s=str(atom.get('text',''));aid=atom['id'];qs,ex=quantities(s,aid,atom.get('unit_context'));numeric+=qs;excluded+=ex;tags=[]
        def tag(kind,strength,match=None):
            start,end=match.span() if match else (0,len(s))
            tags.append(dict(kind=kind,strength=strength,provenance=dict(atom=aid,start=start,end=end,quote=s[start:end])))
        for q in qs:
            tags.append(dict(kind='quantity',strength=.9,provenance=q['provenance'],value=q['value'],unit=q['unit']))
            groups[q['unit']].append(q)
        for kind,pat,strength in [('quote',r'[“"「].+?[”"」]',.85),('contrast',r'\b(?:but|however|whereas|unlike|versus)\b|但是|然而|而|相比',.75),
                                  ('definition',r'\b(?:is defined as|means|refers to|is a|is an)\b|是指|定义为|意味着|是一种|是一类',.8),
                                  ('sequence',r'\b(?:first|then|next|finally|before|after)\b|首先|然后|随后|最后|之前|之后',.8)]:
            match=re.search(pat,s,re.I)
            if match:tag(kind,strength,match)
        dates=[m for m in re.finditer(r'\b(?:19|20)\d{2}\b|\d{4}年',s) if not any(q['provenance']['start']<=m.start()<q['provenance']['end'] for q in qs)]
        if dates:tag('time_point',.7,dates[0])
        if len(dates)>=2:tag('time_sequence',.8)
        if len(dates)>=2 and len(qs)>=2:tag('time_series',.9)
        if not tags:tag('statement',.2)
        rows.append(dict(atom=aid,text=s,evidence=tags,quantities=qs,excluded=ex))
    comparable=[dict(unit=u,points=pts) for u,pts in sorted(groups.items()) if len(pts)>=2]
    part_whole=[]
    for group in comparable:
        if group['unit']=='%' and abs(sum(q['value'] for q in group['points'])-100)<=1:
            part_whole.append(dict(group,reason='source percentages sum to approximately 100'))
    for row in rows:
        qs=row['quantities'];s=next(a['text'] for a in atoms if a['id']==row['atom'])
        for q in qs:
            if q['unit']=='%' and 0<=q['value']<=100:
                part_whole.append(dict(unit='%',points=[q],reason='source percentage explicitly has denominator 100'))
        if len(qs)>=2 and re.search(r'\b(?:total|out of)\b|总(?:计|共|量)|其中',s,re.I):
            peak=max(q['value'] for q in qs)
            if peak>0 and len({q['unit'] for q in qs})==1 and abs(sum(q['value'] for q in qs)-2*peak)<.01:
                part_whole.append(dict(unit=qs[0]['unit'],points=qs,total=peak,reason='explicit source total with matching parts'))
    n=len(numeric);count=len(atoms)
    # Bounded saturation is monotone under added quantitative evidence. Atom
    # fraction is reported, not used as a denominator that dilutes real data.
    abundance=1-math.exp(-n/4)
    comparison=1-math.exp(-sum(len(g['points'])-1 for g in comparable)/4)
    composition=1-math.exp(-len(part_whole)/3)
    density=round(.7*abundance+.2*comparison+.1*composition,6)
    canonical=json.dumps(atoms,ensure_ascii=False,sort_keys=True).encode()
    return dict(version='1.0',atoms_sha256=hashlib.sha256(canonical).hexdigest(),atoms=rows,quantities=numeric,
                comparable_groups=comparable,part_whole=part_whole,data_density=density,
                components=dict(abundance=abundance,comparison=comparison,composition=composition,numeric_atoms=sum(bool(r['quantities']) for r in rows),atom_fraction=sum(bool(r['quantities']) for r in rows)/max(1,count)),
                reasons=[f'{n} qualified measurements',f'{len(comparable)} comparable unit groups',f'{len(excluded)} numeric tokens excluded'],excluded=excluded)

DATA_FORMS={'big-number','stat-tile','pictogram-row','bar-compare','bar-vertical','line-chart','ring','stacked-bar','stat-row'}
TEXT_FORMS={'text','key-statement','summary-box','definition-card','keyword-band','pull-quote','takeaway-list'}

def choose_form(module,prof):
    ids=set(module.get('atoms',[]));rs=[r for r in prof['atoms'] if r['atom'] in ids];qs=[q for r in rs for q in r['quantities']]
    kinds={t['kind'] for r in rs for t in r['evidence']}
    if 'time_series' in kinds:return 'line-chart'
    if 'time_sequence' in kinds and not qs:return 'timeline'
    if len(qs)>=2 and len({q['unit'] for q in qs})==1:return 'bar-vertical' if len(qs)>=4 else 'bar-compare'
    if qs:return 'stat-tile'
    if 'quote' in kinds:return 'pull-quote'
    if 'contrast' in kinds:return 'contrast-pair'
    if 'definition' in kinds:return 'definition-card'
    if 'sequence' in kinds:return 'takeaway-list'
    return 'key-statement' if module.get('level')==1 else 'summary-box'

def validate_module(m,prof):
    errors=[];warnings=[];ids=set(m.get('atoms',[]));rs=[r for r in prof['atoms'] if r['atom'] in ids]
    qs=[q for r in rs for q in r['quantities']];kinds={t['kind'] for r in rs for t in r['evidence']}
    v=m.get('visual') or choose_form(m,prof);d=m.get('visual_data',{});mid=m.get('id','?')
    def fail(reason):errors.append(mid+': fabricated_evidence: '+reason)
    if v in DATA_FORMS and not qs:fail('data form has no qualified source quantity')
    points=d.get('items',[]) if v in DATA_FORMS else []
    if v in ('bar-compare','bar-vertical','line-chart'):
        if len(qs)<2 or not any(len([q for q in qs if q['unit']==u])>=2 for u in {q['unit'] for q in qs}):fail('chart needs >=2 source quantities in the same unit')
        if not d.get('unit'):fail('chart unit is required')
        if v=='line-chart' and not ({'time_series','sequence'} & kinds):fail('line order is absent from source')
    if v=='pictogram-row':
        if not isinstance(d.get('count'),int) or not any(q['value']==d['count'] and q['value'].is_integer() for q in qs):fail('pictogram count must be a source integer')
    if v in ('ring','stacked-bar') and not any(set(p['provenance']['atom'] for p in g['points'])<=ids for g in prof['part_whole']):fail('part-whole relation absent from source')
    if v in ('ring','stacked-bar'):
        total=100 if d.get('unit')=='%' else d.get('total')
        if total is None or float(total)<=0:fail('non-percent part-whole needs an explicit source total')
        elif sum(float(i.get('value',0)) for i in d.get('items',[]))>float(total)+.01:fail('parts exceed source total')
        elif d.get('unit')!='%' and not any(q['value']==float(total) for q in qs):fail('total is absent from source')
    if v=='timeline' and not ({'sequence','time_series','time_sequence'} & kinds):fail('source does not establish sequence')
    if v=='step-flow' and 'sequence' not in kinds:fail('source does not establish process order')
    if v in ('contrast-pair','before-after','versus') and not ({'contrast','sequence'} & kinds):fail('source does not establish comparison')
    if v in ('hub-spoke','concept-stack') and not m.get('relationship_basis'):fail('relation needs an exact source phrase in relationship_basis')
    basis=m.get('relationship_basis')
    source='\n'.join(r['text'] for r in rs)
    if basis and basis not in source:fail('relationship_basis is not an exact source phrase')
    if v in ('takeaway-list','concept-stack','hub-spoke','keyword-band','contrast-pair','timeline','step-flow','before-after','versus'):
        original=source
        for item in d.get('items',[]):
            for field in ('label','text'):
                if item.get(field) and str(item[field]) not in original:fail('node/phrase must be exact bound source text')
        if v in ('timeline','step-flow'):
            positions=[original.find(str(item.get('label',''))) for item in d.get('items',[])]
            if positions!=sorted(positions):fail('sequence differs from source order')
    for point in points:
        q=quantity(str(point.get('value',''))+str(d.get('unit','')))
        if q and not any(abs(z['value']-q[0])<1e-9 and z['unit']==q[1] for z in qs):fail('chart point differs from source quantity/unit')
        if not point.get('atom') or point['atom'] not in ids:fail('every chart point needs a bound source atom')
        elif q and not any(z['provenance']['atom']==point['atom'] and abs(z['value']-q[0])<1e-9 and z['unit']==q[1] for z in qs):fail('point value differs from its named atom')
    if v in ('big-number','stat-tile'):
        q=quantity(str(d.get('value',''))+str(d.get('unit','')))
        if not q or not any(z['value']==q[0] and z['unit']==q[1] for z in qs):fail('hero value/unit differs from source')
    if qs and v not in DATA_FORMS:warnings.append(mid+': under-visualization: source measurements remain textual')
    if v in DATA_FORMS and prof['data_density']<.25:warnings.append(mid+': over-visualization: sparse source, inspect this data form')
    return errors,warnings

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--out');args=ap.parse_args()
    from pathlib import Path
    p=json.loads(Path(args.plan).read_text(encoding='utf-8-sig'));result=profile(p['atoms']);s=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:Path(args.out).write_text(s,encoding='utf-8')
    print(s);return 0

if __name__=='__main__':raise SystemExit(main())

"""Shared Stage 0: source inventory, coverage ledger, lint and deterministic conversion.

No model/network calls. --from-spec is a lossless migration scaffold, not a semantic
summarizer. Author adapted modules explicitly; every source atom remains in the ledger.
"""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

TYPES = ('statistic','claim','process_step','comparison','part_whole','timeline',
         'definition','quote','example','cta','logistics','source')
VISUALS = dict(statistic='big-number', claim='icon-bullet', process_step='step-flow',
               comparison='bar-compare', part_whole='stacked-bar', timeline='timeline',
               definition='icon-bullet', quote='pull-quote', example='icon-bullet',
               cta='stamp', logistics='ticket', source='ticket')
NUMBERS = re.compile(r'(?<!\w)[+-]?\d+(?:[,.]\d+)*(?:%|[A-Za-z]+)?')

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def words(s):
    return len(re.findall(r"[A-Za-z0-9_]+(?:[-’'][A-Za-z0-9_]+)*|[\u3400-\u9fff]",str(s)))

def text(value):
    if isinstance(value,dict):
        return '\n'.join(text(v) for k,v in value.items()
                         if k in ('headline','body','label','value','text','title','attribution','unit','items','steps','before','after','visual_data','count','highlight'))
    if isinstance(value,list):return '\n'.join(map(text,value))
    return str(value) if value is not None else ''

def leafs(value,path=''):
    if isinstance(value,dict):
        for k,v in value.items():yield from leafs(v,f'{path}.{k}' if path else k)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from leafs(v,f'{path}.{i}')
    elif value is not None and str(value).strip():yield path,str(value)

def inventory(spec):
    """One independently auditable source field per atom, preserving paragraphs."""
    atoms=[]
    for path,value in leafs(spec.get('content',spec.get('pages',spec))):
        if 'pages' in spec and any(part in ('archetype','color','size','pct','element_pool','reverse','offsets') for part in path.split('.')):continue
        root=path.split('.')[0]
        kind={'key_number':'statistic','data':'statistic','chart':'comparison',
              'process':'process_step','comparison':'comparison','quote':'quote',
              'cta':'cta','footer':'source','date':'logistics','venue':'logistics',
              'metadata':'logistics','attribution':'source','subtitle':'logistics'}.get(root,'claim')
        atom=dict(id=path,text=value,info_type=kind,
                  group=root if root in ('process','comparison','blocks','data') else None,
                  protected=[value] if kind=='quote' else [])
        if path.split('.')[-1] in ('value','count','pct','percentage'):
            parent=spec.get('content',spec.get('pages',spec))
            try:
                for part in path.split('.')[:-1]:parent=parent[int(part)] if isinstance(parent,list) else parent[part]
                if isinstance(parent,dict):
                    unit=parent.get('unit');unit_path=path.rsplit('.',1)[0]+'.unit'
                    if not unit:
                        from source_profile import UNIT
                        label=str(parent.get('label',''));match=re.search(r'(?:'+UNIT+r')',label,re.I)
                        if match:unit=match[0];unit_path=path.rsplit('.',1)[0]+'.label'
                    if not unit and root=='chart':
                        chart=spec.get('content',{}).get('chart',{});unit=chart.get('unit');unit_path='chart.unit'
                    if unit:atom['unit_context']=dict(unit=unit,atom=unit_path)
            except (KeyError,ValueError,IndexError,TypeError):pass
        atoms.append(atom)
    return atoms

def scaffold(spec,target='poster',copy_mode='verbatim'):
    atoms=inventory(spec)
    modules=[]
    # Migration stays editorial and lossless. It must not guess a shorter thesis,
    # invent assertions or claim to have deduplicated semantic facts.
    for i,a in enumerate(atoms):
        level=1 if a['id']=='title' else 4 if a['info_type'] in ('logistics','source') else 3
        modules.append(dict(id='m'+str(i),level=level,role=a['info_type'],info_type=a['info_type'],
                            visual='text',headline='',body=a['text'],weight=.25 if level==4 else 1,
                            group=a['group'],order=i,atoms=[a['id']]))
    return dict(schema_version='1.0',target=target,copy_mode=copy_mode,mode='editorial',
                purpose='standalone reading' if target=='poster' else 'accompany a talk',
                audience='source audience',thesis=spec.get('content',{}).get('title',spec.get('meta',{}).get('title','Source outline')),
                cta=spec.get('content',{}).get('cta',''),source=copy.deepcopy(spec),
                source_sha256=digest(spec),atoms=atoms,modules=modules,
                ledger=[dict(atom=a['id'],status='kept',into=[m['id']],reason='Lossless migration')
                        for a,m in zip(atoms,modules)])

def lint(plan):
    errors=[];warnings=[]
    if not isinstance(plan,dict):return dict(ok=False,errors=['plan must be an object'],warnings=[])
    for key in ('thesis','purpose','audience','copy_mode','source','source_sha256','atoms','modules','ledger'):
        if key not in plan:errors.append('missing '+key)
    if errors:return dict(ok=False,errors=errors,warnings=warnings)
    evidence=evidence_for(plan)
    from evidence_scale import scale
    from source_profile import validate_module,choose_form
    policy=scale(evidence['level'])
    modern='evidence' in plan
    if not modern:warnings.append('deprecated_v37: missing evidence computed automatically; legacy provenance is not certified')
    else:
        supplied=plan['evidence']
        if supplied.get('profile')!=evidence['profile']:errors.append('evidence profile is stale or modified')
        try:scale(supplied.get('level',evidence['profile']['data_density']))
        except (ValueError,TypeError):errors.append('evidence.level must be finite in [0,1]')
        if supplied.get('level',evidence['profile']['data_density'])!=evidence['profile']['data_density'] and not str(supplied.get('override_reason','')).strip():errors.append('evidence override requires override_reason')
    if plan['copy_mode'] not in ('adapt','verbatim'):errors.append('copy_mode must be adapt or verbatim')
    if digest(plan['source'])!=plan['source_sha256']:errors.append('source hash mismatch: restore original source')
    source_numbers=set(NUMBERS.findall('\n'.join(v for _,v in leafs(plan['source'].get('content',plan['source'].get('pages',plan['source']))))))
    for number in NUMBERS.findall(str(plan['thesis'])+' '+str(plan.get('cta',''))):
        if number not in source_numbers:errors.append('thesis/CTA contains unsourced number '+number)
    expected={a['id']:a for a in inventory(plan['source'])}
    atoms={a.get('id'):a for a in plan['atoms']}
    if len(atoms)!=len(plan['atoms']) or set(atoms)!=set(expected):errors.append('atom inventory must cover every original source field exactly once')
    for aid,a in atoms.items():
        if aid in expected and a.get('text')!=expected[aid]['text']:errors.append('source atom changed: '+aid)
        if a.get('info_type') not in TYPES:errors.append('unknown atom information type: '+str(aid))
    modules={m.get('id'):m for m in plan['modules']}
    if len(modules)!=len(plan['modules']):errors.append('duplicate module id')
    ledger={r.get('atom'):r for r in plan['ledger']}
    if len(ledger)!=len(plan['ledger']) or set(ledger)!=set(atoms):errors.append('ledger must cover every atom exactly once')
    for aid,row in ledger.items():
        status=row.get('status');targets=row.get('into',[])
        if isinstance(targets,str):targets=[targets]
        if status not in ('kept','merged','condensed','cut'):errors.append('invalid ledger status: '+str(aid))
        if status!='kept' and not row.get('reason'):errors.append('ledger reason required: '+str(aid))
        if status=='cut' and targets:errors.append('cut atom cannot have targets: '+str(aid))
        if status!='cut' and not targets:errors.append('retained atom has no destination: '+str(aid))
        if modern and plan['copy_mode']=='adapt' and evidence['level']<.5 and sum(words(a['text']) for a in plan['atoms'])>=140 and status!='cut' and aid!='title':
            layers=row.get('summary_layers',{})
            if not layers.get('l1') or not layers.get('l2') or not layers.get('l3'):errors.append(str(aid)+': text-rich adaptation needs ledger L1/L2/L3 summary_layers')
            for quote in layers.get('l3',[]):
                if quote not in atoms.get(aid,{}).get('text','') or not any(quote in text(modules[t]) for t in targets if t in modules):errors.append(str(aid)+': retained L3 sentence must occur in source and output')
        for mid in targets:
            if mid not in modules:errors.append('unknown destination: '+str(mid));continue
            if aid not in modules[mid].get('atoms',[]):errors.append('ledger/module binding differs: '+str(aid))
        if plan['copy_mode']=='verbatim':
            if status!='kept':errors.append('verbatim does not permit '+str(status))
            if aid in atoms and not any(atoms[aid]['text'] in text(modules[t]) for t in targets if t in modules):
                errors.append('verbatim atom missing or rewritten: '+str(aid))
    seen={};group_positions={}
    for i,m in enumerate(plan['modules']):
        mid=m.get('id','?');kind=m.get('info_type');level=m.get('level')
        if modern:
            effective=dict(m,_source_atoms=plan['atoms'])
            es,ws=validate_module(effective,evidence['profile']);errors.extend(es);warnings.extend(ws)
            if m.get('evidence_basis')!=module_basis(m,evidence['profile']):errors.append(mid+': evidence_basis differs from source profile')
        if kind not in TYPES:errors.append(mid+': unknown info_type')
        visual=m.get('visual') or (choose_form(m,evidence['profile']) if modern else VISUALS.get(kind,'text'))
        if level not in (1,2,3,4):errors.append(mid+': level must be 1..4')
        if not m.get('atoms'):errors.append(mid+': no source atoms')
        for aid in m.get('atoms',[]):
            if aid not in atoms:errors.append(mid+': unknown atom '+str(aid))
            elif mid not in ledger.get(aid,{}).get('into',[]):errors.append(mid+': reverse ledger binding missing '+aid)
        rendered=text(m);source='\n'.join(atoms[a]['text'] for a in m.get('atoms',[]) if a in atoms)
        numeric_copy=rendered+'\n'+str(m.get('notes',''))
        allowed=set(NUMBERS.findall(source))
        allowed.update(format(q['value'],'g') for r in evidence['profile']['atoms'] if r['atom'] in m.get('atoms',[]) for q in r['quantities'])
        derived={str(d.get('value')) for d in m.get('derived',[]) if d.get('reason') and d.get('expression')}
        for number in NUMBERS.findall(numeric_copy):
            if number not in allowed|derived:errors.append(mid+': unsourced number '+number)
        if kind=='statistic' and m.get('visual_data',{}).get('value') is not None:
            if str(m['visual_data']['value']) in NUMBERS.findall(str(m.get('body',''))):errors.append(mid+': statistic repeats its visual value in body copy')
        for aid in m.get('atoms',[]):
            for protected in atoms.get(aid,{}).get('protected',[]):
                if protected not in rendered:errors.append(mid+': protected quote/name changed: '+protected)
        fact=m.get('fact_key') or re.sub(r'\W+','',rendered.lower())
        if plan.get('target')=='deck' and plan.get('mode')=='editorial':
            fact=str(m.get('atoms',[''])[0]).split('.')[0]+':'+fact
        if fact and fact in seen:
            (warnings if plan['copy_mode']=='verbatim' else errors).append(mid+': duplicate fact with '+seen[fact])
        seen[fact]=mid
        if plan.get('mode')!='editorial' and kind=='statistic' and NUMBERS.search(rendered) and not (m.get('visual_data',{}).get('label') or re.search('[A-Za-z\u3400-\u9fff]',rendered)):
            errors.append(mid+': number requires a short label')
        if level==4 and (m.get('weight',.25)>.35 or m.get('visual') not in ('ticket','text')):
            errors.append(mid+': metadata must use footer weight <=.35')
        if m.get('group'):group_positions.setdefault(m['group'],[]).append(i)
        if m.get('parallel') and not m.get('group'):errors.append(mid+': parallel module requires group')
        if kind=='process_step' and m.get('order') is None:errors.append(mid+': process needs order')
    for group,pos in group_positions.items():
        if pos!=list(range(min(pos),max(pos)+1)):errors.append('group must be contiguous: '+group)
    l2=[m for m in plan['modules'] if m.get('level')==2]
    if plan.get('target')=='deck' and plan.get('mode')!='editorial':
        for m in plan['modules']:
            if m.get('level')==4:continue
            if not m.get('headline') and (not modern or m.get('level')!=3):errors.append(m['id']+': deck slide needs an assertion headline')
            if m.get('slide_kind','content') not in ('section','content'):errors.append(m['id']+': slide_kind must be section or content')
            if not isinstance(m.get('notes',''),str):errors.append(m['id']+': notes must be separate text')
    if plan.get('mode','infographic')=='infographic' and plan.get('target','poster')=='poster':
        low,high=policy['l2_range']
        if not low<=len(l2)<=high:(errors if modern else warnings).append(f'infographic requires {low}..{high} L2 modules at evidence={evidence["level"]:.3f}')
        if words(plan['thesis'])>policy['thesis_words']:(errors if modern else warnings).append('thesis exceeds evidence-scaled budget')
        for m in l2:
            if words(text(m))>policy['module_words']:(errors if modern else warnings).append(m['id']+': exceeds evidence-scaled L2 budget')
        from source_profile import TEXT_FORMS
        ratio=sum((m.get('visual') or (choose_form(m,evidence['profile']) if modern else VISUALS.get(m.get('info_type'),'text'))) in TEXT_FORMS for m in l2)/max(1,len(l2))
        if ratio>policy['text_fraction']:(errors if modern else warnings).append('text-only L2 ratio exceeds evidence-scaled allowance')
        count=words('\n'.join(text(m) for m in plan['modules'] if m.get('level')!=4))
        if not policy['word_budget'][0]<=count<=policy['word_budget'][1]:warnings.append(f'copy budget {count} words outside evidence-scaled {policy["word_budget"]}; preflight decides fit; do not pad copy')
        if sum(m.get('level')==1 for m in plan['modules'])>2:errors.append('L1 maximum is title + hero')
        if sum(m.get('level')==3 for m in plan['modules'])>8:errors.append('L3 maximum is 8 supporting modules')
    return dict(ok=not errors,errors=errors,warnings=warnings,source_sha256=plan['source_sha256'],plan_sha256=digest(plan),
                metrics=dict(atoms=len(atoms),modules=len(modules),l2=len(l2),evidence_level=evidence['level']),evidence=evidence,policy=policy)

def module_basis(m,prof):
    return [dict(atom=r['atom'],kinds=sorted({e['kind'] for e in r['evidence']}),
                 quantities=[q['provenance'] for q in r['quantities']]) for r in prof['atoms'] if r['atom'] in m.get('atoms',[])]

def evidence_for(plan):
    from source_profile import profile
    prof=profile(inventory(plan['source']))
    raw=plan.get('evidence',{});level=raw.get('level',prof['data_density'])
    # Keep lint aggregated for malformed levels; policy is computed safely.
    try:
        from evidence_scale import scale
        scale(level)
    except (ValueError,TypeError):level=prof['data_density']
    return dict(profile=prof,level=level,override_reason=raw.get('override_reason',''))

def annotate(plan):
    """Opt into v3.8 validation, preserving source atoms and source hash."""
    plan=copy.deepcopy(plan);plan['evidence']=evidence_for(plan)
    for m in plan['modules']:m['evidence_basis']=module_basis(m,plan['evidence']['profile'])
    if plan.get('copy_mode')=='adapt' and plan['evidence']['level']<.5 and sum(words(a['text']) for a in plan['atoms'])>=140:
        atoms={a['id']:a for a in plan['atoms']};modules={m['id']:m for m in plan['modules']}
        for row in plan['ledger']:
            if row['status']=='cut' or row['atom']=='title':continue
            targets=[modules[t] for t in row.get('into',[]) if t in modules]
            sentences=[s for s in re.split(r'(?<=[.!?。！？])\s*',atoms[row['atom']]['text']) if s.strip()]
            retained=next((s for s in sentences if any(s in text(m) for m in targets)),None)
            row.setdefault('summary_layers',dict(l1=plan['thesis'],l2=[m.get('headline') or m.get('body','') for m in targets],l3=[retained] if retained else []))
    return plan

def to_spec(plan):
    if plan.get('target') == 'deck':
        from deck_content_plan import to_spec as compile_deck
        return compile_deck(plan)
    result=lint(plan)
    if not result['ok']:raise ValueError('\n'.join(result['errors']))
    if plan.get('mode')=='editorial':
        spec=copy.deepcopy(plan['source'])
        if plan.get('target')=='poster':spec['mode']='editorial'
    else:
        content={'title':plan['thesis'],'modules':copy.deepcopy(plan['modules'])}
        for module in content['modules']:
            from source_profile import choose_form
            module.setdefault('visual',choose_form(module,result['evidence']['profile']) if 'evidence' in plan else VISUALS.get(module.get('info_type'),'text'))
            module['evidence_basis']=module_basis(module,result['evidence']['profile'])
            if module.get('group'):module['keep_together']=True
        spec=dict(artifact='poster',mode='infographic',content=content,canvas=copy.deepcopy(plan.get('canvas',{'preset':'a3_portrait'})),
                  meta=copy.deepcopy(plan.get('meta',{})),art_direction=copy.deepcopy(plan.get('art_direction',{})))
        spec['art_direction'].setdefault('archetype','auto')
        spec['art_direction'].setdefault('columns',2 if len(plan['modules'])>3 else 1)
        spec['art_direction'].setdefault('skeleton','bands')
    spec['content_plan']=dict(plan_sha256=digest(plan),source_sha256=plan['source_sha256'],
                              output_sha256=digest(spec.get('content',spec.get('pages'))))
    spec['evidence']=result['evidence']
    spec['evidence']['legacy']='evidence' not in plan
    if spec.get('mode') == 'infographic' and plan.get('target', 'poster') == 'poster':
        from evidence_scale import scale
        direction = spec['art_direction']
        if spec.get('meta', {}).get('lang') == 'en' and 'element_density' not in direction:
            direction.setdefault('ornament', 'focused')
        direction.setdefault('element_density', scale(result['evidence']['level'])['element_density'])
    return spec

def deck_outline(plan):
    """Compatibility alias for callers of the original unified compiler."""
    from deck_content_plan import deck_outline as compile_outline
    return compile_outline(plan)


def save(plan,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Content plan',plan['thesis'],'',f"Purpose: {plan['purpose']} · Audience: {plan['audience']}",
           f"Copy: {plan['copy_mode']} · CTA: {plan.get('cta','')}",'']
    lines += [f"- L{m['level']} {m['id']} · {m['info_type']} → {m['visual']}: {text(m)}" for m in plan['modules']]
    lines+=['','## Coverage ledger']+[f"- {r['atom']}: {r['status']} → {r.get('into',[])} ({r.get('reason','')})" for r in plan['ledger']]
    path.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')

def gate(spec,plan_path,skip=False,source_path=None):
    if skip:return dict(skipped=True,reason='explicit --skip-plan compatibility escape')
    import sys,os,shlex
    def command(*args):
        parts=[sys.executable,str(Path(__file__).resolve()),*map(str,args)]
        return '& '+' '.join("'"+s.replace("'","''")+"'" for s in parts) if os.name=='nt' else shlex.join(parts)
    repair=command('--from-spec',source_path or 'INPUT.json','--target','deck' if 'pages' in spec else 'poster','--out','content-plan.json','--to-spec','planned-spec.json')
    if not plan_path:raise ValueError('Stage 0 required. Run '+repair+'; then use --spec planned-spec.json --content-plan content-plan.json. Legacy escape: --skip-plan')
    plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig'));report=lint(plan)
    if not report['ok']:raise ValueError('Stage 0 lint failed:\n'+'\n'.join(report['errors'])+'\nRecheck: '+command('--plan',plan_path,'--lint'))
    binding=spec.get('content_plan',{})
    if binding.get('plan_sha256')!=digest(plan) or binding.get('output_sha256')!=digest(spec.get('content',spec.get('pages'))):
        raise ValueError('Stale/unbound content plan. Reconvert: '+command('--plan',plan_path,'--to-spec','planned-spec.json'))
    if spec.get('evidence') and spec['evidence']!={**report['evidence'],'legacy':'evidence' not in plan}:raise ValueError('Stale/unbound evidence profile')
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--from-spec');ap.add_argument('--plan');ap.add_argument('--out');ap.add_argument('--lint',action='store_true')
    ap.add_argument('--to-spec');ap.add_argument('--target',choices=['poster','deck'],default='poster')
    ap.add_argument('--annotate',action='store_true',help='compute evidence and opt into v3.8 semantic checks')
    ap.add_argument('--copy-mode',choices=['verbatim','adapt'],default='verbatim')
    args=ap.parse_args()
    if not args.from_spec and not args.plan:ap.error('--from-spec or --plan is required')
    plan=scaffold(json.loads(Path(args.from_spec).read_text(encoding='utf-8-sig')),args.target,args.copy_mode) if args.from_spec else json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
    if args.annotate:plan=annotate(plan)
    if args.out:save(plan,args.out)
    result=lint(plan);print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['ok']:return 1
    if args.to_spec:Path(args.to_spec).write_text(json.dumps(to_spec(plan),ensure_ascii=False,indent=2),encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())

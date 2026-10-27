"""Audit saved native chart values and zero-origin geometry against source atoms."""
import math,re
from source_profile import quantity,validate_module

def check(slide,plan):
    errors=[];checks=0;profile=plan.get('evidence',{}).get('profile',{})
    if not profile or plan.get('evidence',{}).get('legacy'):return dict(ok=True,checks=0,errors=[],status='LEGACY_UNVERIFIED')
    by={s.name:s for s in slide.shapes}
    for m in plan.get('source_modules',[]):
        es,_=validate_module(m,profile);errors+=es
    points=[o for o in plan['objects'] if o.get('data_point')]
    source=profile.get('quantities',[])
    for o in plan['objects']:
        d=o.get('data_label')
        if not d:continue
        checks+=1;q=quantity(str(d['value'])+str(d['unit']))
        if not q or not any(z['provenance']['atom']==d.get('atom') and z['value']==q[0] and z['unit']==q[1] for z in source):errors.append(o['id']+': data label has no matching source atom')
        shape=next((s for s in slide.shapes if s.name.startswith('art['+o['id']+']')),None)
        if not q or shape is None or not shape.has_text_frame or quantity(shape.text) is None or quantity(shape.text)[0]!=q[0]:errors.append(o['id']+': actual saved label differs from source')
    for o in points:
        d=o['data_point'];checks+=1
        if not any(q['provenance']['atom']==d.get('atom') and q['value']==float(d['value']) and q['unit']==d['unit'] for q in source):errors.append(o['id']+': saved point differs from source')
        shape=by.get('art['+o['id']+']')
        if shape is None:
            # Paths use the native_path shape naming convention.
            shape=next((s for s in slide.shapes if o['id'] in s.name),None)
        if shape is None:errors.append(o['id']+': chart shape missing');continue
        if '-bar-' in o['id']:
            got=shape.width.pt if d['axis']=='x' else shape.height.pt
            expected=float(d['value'])*d['scale']
            if abs(got-expected)>1:errors.append(o['id']+': bar length differs from value / zero baseline')
            origin=shape.left.pt if d['axis']=='x' else shape.top.pt+shape.height.pt
            if abs(origin-d['zero_origin'])>1:errors.append(o['id']+': bar baseline is not zero')
            thickness=shape.height.pt if d['axis']=='x' else shape.width.pt
            if thickness<8:errors.append(o['id']+': bar thickness below 8pt')
        module=o['id'].rsplit('-bar-',1)[0]
        if module!=o['id']:
            j=o['id'].rsplit('-bar-',1)[1]
            label=next((s for s in slide.shapes if f'art[{module}-visual_data.items.{j}.value]' in s.name),None)
            if label is None or not label.has_text_frame:errors.append(o['id']+': value label missing')
            elif quantity(label.text) is None or quantity(label.text)[0]!=float(d['value']):errors.append(o['id']+': saved value label differs from data')
    charts=[m for m in plan.get('source_modules',[]) if m.get('visual') in ('bar-compare','bar-vertical','line-chart','ring','stacked-bar','pictogram-row')]
    if len(charts)>1:errors.append('page has more than one chart; split evidence across pages')
    return dict(ok=not errors,checks=checks,errors=errors,status='SOURCE_CHECKED')

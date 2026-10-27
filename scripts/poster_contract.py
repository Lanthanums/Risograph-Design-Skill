"""Executable poster contract. CLI descriptions and examples use these definitions.

Semantic errors are aggregated; normalization never rewrites supplied content.
"""
import copy,difflib,math,re
from graphic_recipes import RECIPES

ROLES=('hook','hero_stat','parallel_set','argument','cta','facts','source','meta')
ALIASES={'headline-figure':'hero_stat','statement':'hook','action':'cta','heading':'title','body':'text','suggested_fix':'plan_revision'}
WEAKNESS_FIELDS=('location','observation','plan_revision')
def string(**kw):return dict(type='string',**kw)
def array(items,**kw):return dict(type='array',items=items,**kw)
def obj(properties,required=(),**kw):return dict(type='object',properties=properties,required=list(required),additionalProperties=False,**kw)
def union(*choices):return dict(anyOf=list(choices))
TEXT=string();TEXTS=union(TEXT,array(TEXT));NUMBER=union(TEXT,dict(type='number'))
PAIR=obj({'value':NUMBER,'label':TEXT})
QUOTE=obj({'text':TEXT,'attribution':TEXT})
BLOCK=obj({'title':TEXT,'text':TEXT})
STEP=obj({'label':TEXT,'text':TEXT})
CHART_ITEM=obj({'label':TEXT,'value':dict(type='number',minimum=0),'source':TEXT,'status':string(enum=['supplied','derived','unspecified']),'derivation':TEXT},('label','value'))
CONTENT={**{k:TEXT for k in ('title','subtitle','date','venue','cta','footer','attribution','full_bleed_reason')},
 'modules':array(dict(type='object')),
 'body':TEXTS,'blocks':array(union(TEXT,BLOCK)),'key_number':union(NUMBER,PAIR),'quote':union(TEXT,QUOTE),
 'metadata':union(TEXT,array(TEXT),dict(type='object',additionalProperties=NUMBER)),
 'data':array(PAIR),'process':array(union(TEXT,STEP)),'comparison':array(union(TEXT,STEP)),
 'chart':obj({'title':TEXT,'unit':TEXT,'items':array(CHART_ITEM,minItems=2,maxItems=6)},('items',)),
 'image':union(TEXT,obj({'path':TEXT},('path',))),'text_bleed':array(TEXT)}
META={k:{} for k in ('palette_hex','scale','reverse','family','calibrated_from_reference','from_content')}
META.update(lang=string(),palette=string(),seed=dict(type='integer'),dialect=union(string(enum=list('ABCDEF')),array(string(enum=list('ABCDEF')),minItems=1,maxItems=2)),
 elements=dict(type='boolean'),fonts=dict(type='object',additionalProperties=TEXT),print_grammar=string(enum=['none']),exclude_elements=array(TEXT),element_pool=array(TEXT),graphic_element=TEXT,
 graphic_recipe=string(enum=['auto','off','micro',*RECIPES]),topic_tags=array(TEXT))

# CONTROLS is populated from the maintained declaration below, never a CLI copy.
CONTROLS={
 'element_density':dict(type='enum',values=['sparse','normal','rich'],default='normal'),
 'micro_exclude':dict(type='array',default=[]),
 'keep_together':dict(type='array',default=[]),
 'archetype':dict(type='enum',values=['auto','type-hero','numeral-hero','diagram-hero','banded','staggered-modules','statement'],default='auto'),
 'dialect':dict(type='enum',values=['auto','swiss','collage','doodle'],default='auto'),
 'ink':dict(type='enum',values=['cobalt-vermilion','plum-ochre','teal-coral'],default='cobalt-vermilion'),
 'skeleton':dict(type='enum',values=['auto','bands','asymmetric-notes','central-orbit'],default='auto'),
 'body_size':dict(type='number',minimum=16,maximum=32,unit='pt',default='20; autofit floor 16'),
 'hero_share':dict(type='number',minimum=.18,maximum=.65,unit='safe page height fraction',default=.24),
 'columns':dict(type='integer',values=[1,2,3],default=2,scope='content columns, including blocks; never overridden by block count'),
 'looseness':dict(type='number',minimum=0,maximum=1,default='0 swiss; .65 collage/doodle'),
 'tiers':dict(type='object',values=['T1','T2','T3'],default={},scope='exact source path to user-approved hierarchy'),
 'title_size':dict(type='number',minimum=40,maximum=80,unit='pt',default=64),
 'title_leading':dict(type='number',minimum=.9,maximum=1.08,unit='font size fraction',default=.98),
 'micro_elements':dict(type='boolean',default=True),
 'autofit':dict(type='boolean',default=True),
 'intentional_voids':dict(type='array',default=[],scope='objects with rect [x,y,x1,y1] in pt and nonempty reason'),
 'title_lines':dict(type='array',scope='exact source fragments in original order'),
 'statement_lines':dict(type='array',scope='exact source quote fragments in original order'),
 'highlights':dict(type='array',scope='exact source, text, optional kind; no generated keywords'),
 'roles':dict(type='object',scope='exact source path to semantic role'),
 'micro_style':dict(type='enum',values=['label','stamp','badge'],default='label'),
 'revision':dict(type='integer',minimum=0,default=0),
 'review_changes':dict(type='array',default=[]),
 'annotations':dict(type='array',default=[],scope='source-exact phrases'),
 'colophon_source':dict(type='string',scope='exact supplied footer'),
 'source_document':dict(type='string',scope='original source text'),
 'surface_seed':dict(type='integer',default='meta.seed'),
 'halftone':dict(type='enum',values=['off','auto'],default='off'),
}
for _v in CONTROLS.values():_v['level']='art_direction'

def definition():
 art={}
 for k,v in CONTROLS.items():
  d=copy.deepcopy(v);d['type']='string' if d['type']=='enum' else d['type']
  if 'values' in d and d['type'] in ('string','integer'):d['enum']=d.pop('values')
  art[k]=d
 art['roles']=dict(type='object',additionalProperties=string(enum=list(ROLES)))
 art['tiers']=dict(type='object',additionalProperties=string(enum=['T1','T2','T3']))
 for k in ('title_lines','statement_lines'):art[k]=array(TEXT)
 art['highlights']=array(obj({'source':TEXT,'text':TEXT,'kind':string(enum=['highlight','circle','underline','wave','bracket'])},('source','text')))
 art['annotations']=array(obj({'source':TEXT,'text':TEXT},('source','text')))
 art['review_changes']=array(TEXT)
 art['intentional_voids']=array(obj({'rect':array(dict(type='number'),minItems=4,maxItems=4),'reason':TEXT},('rect','reason')))
 return obj({'artifact':string(enum=['poster']),'mode':string(enum=['infographic','editorial']),
   'content_plan':dict(type='object'),'evidence':dict(type='object'),'canvas':union(TEXT,dict(type='object')),'family':TEXT,'meta':obj(META),
   'content':obj(CONTENT,('title',)),'layout':dict(type='object'),'art_direction':obj(art),
   'brief':obj({k:{} for k in ('purpose','viewing_distance','audience','constraints','sources')})},('content',))

def hint(name,allowed):
 candidate=ALIASES.get(name)
 if candidate not in allowed:candidate=next(iter(difflib.get_close_matches(str(name),list(allowed),n=1,cutoff=.64)),None)
 return f'; did you mean {candidate}?' if candidate else ''

def _validate(value,d,path,errors):
 if 'anyOf' in d:
  alternatives=[]
  for choice in d['anyOf']:
   e=[];_validate(value,choice,path,e)
   if not e:return
   alternatives.append((choice,e))
  same=[e for c,e in alternatives if _is_type(value,c.get('type'))]
  errors.extend(min(same,key=len) if same else [f'{path}: expected one of '+', '.join(c.get('type','value') for c,e in alternatives)]);return
 t=d.get('type')
 if t and not _is_type(value,t):errors.append(f'{path}: expected {t}');return
 if 'enum' in d and value not in d['enum']:errors.append(f'{path}: allowed {d["enum"]}'+hint(value,d['enum']));return
 if t in ('number','integer'):
  if not math.isfinite(value):errors.append(f'{path}: must be finite')
  for k,fail in [('minimum',lambda a,b:a<b),('maximum',lambda a,b:a>b)]:
   if k in d and fail(value,d[k]):errors.append(f'{path}: {k} {d[k]}'+(' (nonnegative)' if k=='minimum' and d[k]==0 else ''))
 if t=='array':
  if len(value)<d.get('minItems',0) or len(value)>d.get('maxItems',math.inf):errors.append(f'{path}: item count outside {d.get("minItems",0)}..{d.get("maxItems","unbounded")}')
  for i,v in enumerate(value):_validate(v,d.get('items',{}),f'{path}.{i}',errors)
 if t=='object':
  props=d.get('properties',{});extra=d.get('additionalProperties',True)
  for k in d.get('required',[]):
   if k not in value:errors.append(f'{path}.{k}: required')
  for k,v in value.items():
   if k in props:_validate(v,props[k],f'{path}.{k}',errors)
   elif extra is False:errors.append(f'{path}.{k}: unknown field; allowed {list(props)}'+hint(k,props))
   elif isinstance(extra,dict):_validate(v,extra,f'{path}.{k}',errors)

def _is_type(v,t):
 return {'string':isinstance(v,str),'array':isinstance(v,list),'object':isinstance(v,dict),
 'number':isinstance(v,(int,float)) and not isinstance(v,bool),'integer':isinstance(v,int) and not isinstance(v,bool),'boolean':isinstance(v,bool),None:True}.get(t,False)

class ContractError(ValueError):
 def __init__(self,errors):self.errors=errors;super().__init__('Poster contract errors ('+str(len(errors))+'):\n'+'\n'.join('- '+x for x in errors))

def validate(spec):
 errors=[];_validate(spec,definition(),'spec',errors)
 if not isinstance(spec,dict):raise ContractError(errors)
 c=spec.get('content',{});a=spec.get('art_direction',{});m=spec.get('meta',{})
 if not isinstance(c,dict) or not isinstance(a,dict) or not isinstance(m,dict):raise ContractError(errors)
 if isinstance(c.get('title'),str) and not c['title'].strip():errors.append('content.title: supplied nonempty text required')
 # Source paths come from the same canonical leaf walker used by the planner.
 if not errors:
  from poster_direction import content_roles
  paths={r['source']:r['text'] for r in content_roles(c)}
  for key in ('roles','tiers'):
   for path in a.get(key,{}):
    if path not in paths:
     suggested=path.removeprefix('content.')
     errors.append(f'art_direction.{key}.{path}: unknown exact source path; available {list(paths)}'+(f'; did you mean {suggested}?' if suggested in paths else ''))
  for key in ('highlights','annotations'):
   for i,row in enumerate(a.get(key,[])):
    if row['source'] not in paths or not row['text'] or row['text'] not in paths[row['source']]:errors.append(f'art_direction.{key}.{i}: requires exact supplied source substring')
  for key,path in [('title_lines','title'),('statement_lines','quote.text' if isinstance(c.get('quote'),dict) else 'quote')]:
   if a.get(key) and re.sub(r'\s+','',''.join(a[key]))!=re.sub(r'\s+','',paths.get(path,'')):errors.append(f'art_direction.{key}: must preserve exact source and order')
 if a.get('colophon_source') is not None and a['colophon_source']!=c.get('footer'):errors.append('art_direction.colophon_source: must equal content.footer exactly; content.footer must exist when this field is supplied')
 if isinstance(c.get('chart'),dict):
  for i,row in enumerate(c['chart'].get('items',[])):
   if isinstance(row,dict) and row.get('status')=='derived' and not row.get('derivation'):errors.append(f'content.chart.items.{i}.derivation: derivation note required for derived values')
 if errors:raise ContractError(errors)
 return True

def canonical(spec):
 """Only normalize nonsemantic controls. All source content is untouched."""
 validate(spec);s=copy.deepcopy(spec);warnings=[]
 if 'art_direction' in s:
  a=s['art_direction'];c=s['content'];dialect=a.get('dialect','auto')
  if dialect=='auto':dialect='swiss' if c.get('chart') or len(c.get('data',[]))>2 else 'doodle' if c.get('process') else 'collage' if c.get('blocks') or c.get('quote') else 'swiss'
  if dialect=='swiss' and a.get('looseness',0)!=0:
   warnings.append('swiss looseness clamped to 0 (requested '+str(a['looseness'])+')');a['looseness']=0
  if 'colophon_source' not in a and 'footer' in c:a['colophon_source']=c['footer']
 return s,warnings

def example():
 return {'artifact':'poster','canvas':{'preset':'a3_portrait'},'family':'explainer','meta':{'lang':'en','seed':1,'graphic_recipe':'micro'},
 'art_direction':{'archetype':'auto','roles':{'title':'hook','key_number.value':'hero_stat','blocks.0.text':'parallel_set','body':'argument','cta':'cta','date':'facts','footer':'source','metadata.0':'meta'},'tiers':{'title':'T1','key_number.value':'T1','metadata.0':'T3'}},
 'content':{'title':'Supplied title','subtitle':'Supplied context','body':['Supplied paragraph.','Supplied qualification.'],
 'key_number':{'value':'2','label':'Supplied count'},'quote':{'text':'Supplied quotation.','attribution':'Supplied author'},
 'blocks':[{'title':'Supplied heading','text':'Supplied explanation.'}],'data':[{'value':'2','label':'Supplied evidence'}],
 'process':[{'label':'Supplied step','text':'Supplied action.'}],'comparison':[{'label':'Supplied option','text':'Supplied distinction.'}],
 'chart':{'title':'Supplied comparison','unit':'Supplied unit','items':[{'label':'Supplied A','value':1},{'label':'Supplied B','value':2}]},
 'date':'Supplied date','venue':'Supplied venue','metadata':['Supplied metadata'],'attribution':'Supplied credit','cta':'Supplied next step.','footer':'Supplied source.'}}

def describe_spec():
 d=definition()
 return dict(contract=d,content=d['properties']['content'],meta=d['properties']['meta'],art_direction=CONTROLS,
  roles=list(ROLES),source_paths={'examples':['title','key_number.value','blocks.0.title','metadata.0'],'prefix':'No content. prefix; use exact leaf paths'},
  dialect_constraints={'swiss':{'looseness':'finite 0..1 accepted, clamped to 0 with warning'},'all':{'colophon_source':'If supplied, exactly content.footer; footer must then exist. If omitted, derived from existing footer.'}},
  optional_content_variants={'legacy_image':{'image':{'path':'supplied-image.png'},'full_bleed_reason':'Supplied reason','text_bleed':[]}},
  review={'weakness_fields':list(WEAKNESS_FIELDS),'example':weakness_example()},example=example())

def weakness_example():return {'location':'REPLACE: exact object or region','observation':'REPLACE after inspecting the rendered image','plan_revision':'REPLACE: concrete revision to the source spec controls'}

def validate_weaknesses(weak,modern=True):
 errors=[]
 if not isinstance(weak,list):return ['weaknesses must be an array']
 if (modern and len(weak)>5) or (not modern and len(weak)<5):errors.append('weaknesses count: fast/audit allows 0–5; legacy requires at least five')
 for i,w in enumerate(weak):
  if not isinstance(w,dict):errors.append(f'weaknesses.{i}: must be an object');continue
  missing=[k for k in WEAKNESS_FIELDS if not isinstance(w.get(k),str) or not w[k].strip()]
  if missing:errors.append(f'weaknesses.{i}: missing nonempty keys {missing}'+(' ; did you mean plan_revision instead of suggested_fix?' if 'suggested_fix' in w else ''))
  if any(str(v).startswith('REPLACE') for v in w.values()):errors.append(f'weaknesses.{i}: replace the example after inspection, or remove it if there is no observed weakness')
 return errors

def documentation():
 import json
 return '# Poster contract (generated)\n\nGenerated from `scripts/poster_contract.py`; edit the executable definitions, then regenerate.\n\n'+\
 'The schema is a valid synthetic example, not supplied factual copy. Replace every placeholder with source text. '+\
 'Optional image/full-bleed fields require the legacy image route; they cannot be combined with modern vector posters.\n\n'+\
 '```json\n'+json.dumps(describe_spec(),ensure_ascii=False,indent=2)+'\n```\n'

if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 ap=argparse.ArgumentParser();ap.add_argument('--write-doc');args=ap.parse_args()
 if args.write_doc:Path(args.write_doc).write_text(documentation(),encoding='utf-8')
 else:print(json.dumps(describe_spec(),ensure_ascii=False,indent=2))

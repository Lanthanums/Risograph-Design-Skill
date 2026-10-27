"""Measured runtime provenance; no font files or evaluation copy in the package."""
import hashlib,struct
from pathlib import Path
from functools import lru_cache

def engine_version(root=None):
 """Packaging errors must be visible without crashing the audit writer."""
 root=Path(root) if root else Path(__file__).resolve().parents[1]
 try:
  value=(root/'VERSION').read_text(encoding='utf-8').strip()
  if not value:raise ValueError('empty VERSION')
  return value
 except (OSError,ValueError) as exc:
  import warnings
  warnings.warn('Package VERSION unavailable; manifest records unknown: '+str(exc))
  return 'unknown'

def renderer_version(binary):
 """Read the installed build ID without starting a GUI or blocking cache hits."""
 if not binary:return 'UNVERIFIED: renderer unavailable'
 for filename in ('version.ini','versionrc'):
  path=Path(binary).parent/filename
  if path.is_file():
   for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
    if line.startswith('buildid='):return 'LibreOffice buildid '+line.split('=',1)[1]
 return 'UNVERIFIED: installed build metadata unavailable'

def font_version(path,index=0):
 """Read OpenType name ID 5, including collection face offsets, with stdlib."""
 try:
  return font_details(path,index)['version']
 except (OSError,ValueError,TypeError):return 'UNVERIFIED'

def font_details(path,index=0):
 path=Path(path);stamp=path.stat()
 digest,version=_font_details(str(path.resolve()),stamp.st_mtime_ns,stamp.st_size,index)
 return dict(sha256=digest,version=version)

@lru_cache(maxsize=128)
def _font_details(path,stamp,size,index):
 b=Path(path).read_bytes()
 version='name ID 5 unavailable'
 try:
  offset=struct.unpack_from('>I',b,12+index*4)[0] if b[:4]==b'ttcf' else 0
  count=struct.unpack_from('>H',b,offset+4)[0]
  for i in range(count):
   tag,_,start,_=struct.unpack_from('>4sIII',b,offset+12+i*16)
   if tag!=b'name':continue
   _,n,strings=struct.unpack_from('>HHH',b,start)
   for j in range(n):
    platform,encoding,language,name,length,relative=struct.unpack_from('>HHHHHH',b,start+6+j*12)
    if name==5:
     version=b[start+strings+relative:start+strings+relative+length].decode('utf-16-be' if platform in (0,3) else 'mac_roman',errors='replace')
     break
 except (ValueError,struct.error):version='UNVERIFIED'
 return hashlib.sha256(b).hexdigest(),version

def fonts(plan):
 import textmetrics as tm
 rows=[]
 for family,bold in sorted({(o['fit']['font'],o['fit']['bold']) for o in plan.get('objects',[]) if o['kind']=='text'}):
  path=tm.resolve(family,bold);index=tm._faces.get((family,bool(bold)),0)
  rows.append(dict(family=family,bold=bold,path=path,face_index=index,**(font_details(path,index) if path else dict(version='UNRESOLVED',sha256=None))))
 return rows

def presentation_fonts(deck):
 """Include fonts from compatible deck archetypes as well as evidence pages."""
 import zipfile
 import xml.etree.ElementTree as ET
 families=set()
 with zipfile.ZipFile(deck) as archive:
  for name in archive.namelist():
   if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
    for element in ET.fromstring(archive.read(name)).iter():
     family=element.get('typeface')
     if family and not family.startswith('+'):families.add(family)
 objects=[dict(kind='text',fit=dict(font=family,bold=bold)) for family in families for bold in (False,True)]
 return fonts(dict(objects=objects))

def profile(capabilities):
 """Explicit observed capabilities, never a brand or model-name lookup."""
 seconds=capabilities.get('command_timeout_seconds',60);images=capabilities.get('can_view_images',False);jobs=capabilities.get('background_jobs',False)
 return dict(planning='synchronous; no render',rendering='single foreground command' if seconds>=180 else 'one background job; poll returned job ID' if jobs else 'external render required: command timeout too short',review='inspect full/thumbnail/blur contact' if images else 'human image inspection required; do not claim visual approval',capabilities=capabilities)

def trial_template():
 return dict(schema_version='1.0',calls=[],failures=[dict(call_index=None,error='',cause='',calls_to_resolve=None,skill_defect=False)],doc_mismatch=[],deviations=[],engine_seconds=None,wall_seconds=None,call_count=None,profile=profile(dict(can_view_images=False,command_timeout_seconds=60,background_jobs=False)),independent_agent=False)

if __name__=='__main__':
 import argparse,json
 ap=argparse.ArgumentParser();ap.add_argument('--template',action='store_true');ap.add_argument('--capabilities');a=ap.parse_args()
 print(json.dumps(profile(json.loads(Path(a.capabilities).read_text(encoding='utf-8'))) if a.capabilities else trial_template(),indent=2))

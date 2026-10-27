"""Reproducible complete-command cold/warm/cache benchmark (no network)."""
import argparse,json,os,platform,subprocess,sys,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for arg in ('spec','plan','content-plan'):ap.add_argument('--'+arg)
    ap.add_argument('--target',choices=['poster','deck'],default='poster');ap.add_argument('--out',required=True)
    ap.add_argument('--draft',action='store_true');ap.add_argument('--repeats',type=int,default=3)
    a=ap.parse_args()
    if not (a.plan or a.spec):ap.error('--plan or --spec required')
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);rows=[]
    runner=Path(__file__).with_name(a.target+'_run.py');output=out/'output'
    base=[sys.executable,str(runner),'--out',str(output),'--draft' if a.draft else '--auto','--system']
    for k in ('spec','plan','content_plan'):
        if getattr(a,k):base+=['--'+k.replace('_','-'),str(Path(getattr(a,k)).resolve())]
    for name,mode in [('cold','audit'),('warm','audit')]+[(f'hit-{i+1}','fast') for i in range(a.repeats)]:
        command=base+['--mode',mode];start=time.perf_counter();result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=600);wall=time.perf_counter()-start
        summary=json.loads((output/'summary.json').read_text(encoding='utf-8')) if (output/'summary.json').is_file() else {}
        (out/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        rows.append(dict(state=name,wall_seconds=round(wall,4),exit_code=result.returncode,status=summary.get('status'),cache=summary.get('cache'),engine_seconds=summary.get('engine_seconds'),stages=summary.get('stages'),command=command))
        report=dict(platform=platform.platform(),python=sys.version,renderer=os.environ.get('RISOSLIDES_SOFFICE'),sample_count=len(rows),cold_definition='fresh command and output; OS/font caches uncontrolled, persistent renderer profile may already be warm',runs=rows)
        (out/'bench.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(name,rows[-1]['wall_seconds'],rows[-1]['status'],rows[-1]['cache'],flush=True)
    lines=['| state | command wall s | engine s | cache | status |','|---|---:|---:|---|---|']+[f'| {r["state"]} | {r["wall_seconds"]} | {r["engine_seconds"]} | {r["cache"]} | {r["status"]} |' for r in rows]
    (out/'bench.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return int(any(r['exit_code'] for r in rows))

if __name__=='__main__':raise SystemExit(main())

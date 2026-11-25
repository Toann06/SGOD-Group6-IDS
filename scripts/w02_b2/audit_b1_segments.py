"""Stream all four CSVs, compare B1 gap segmentation with known tail range."""
import json
from pathlib import Path
from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import SHARED_TAIL_TS_START, SHARED_TAIL_TS_END, SHARED_TAIL_SOURCES

root=Path.cwd()
report={}
for name in sorted(SHARED_TAIL_SOURCES):
    previous=None
    segment=0
    rows=tail_rows=mismatch=tail_attacks=0
    gaps=[]
    for df in load_csv_chunk(root/name, chunksize=50000):
        ts=df.timestamp
        delta=ts.diff()
        if previous is not None: delta.iloc[0]=ts.iloc[0]-previous
        boundary=delta.gt(1.0)|delta.lt(0)
        ids=boundary.cumsum()+segment
        for i in df.index[boundary]:
            gaps.append({'source_line':int(df.loc[i,'source_line']), 'timestamp':float(ts.loc[i]), 'delta':float(delta.loc[i])})
        segment=int(ids.iloc[-1]); previous=float(ts.iloc[-1])
        tail=ts.between(SHARED_TAIL_TS_START,SHARED_TAIL_TS_END)
        rows+=len(df); tail_rows+=int(tail.sum()); mismatch+=int(((ids==0)!=~tail).sum()); tail_attacks+=int((tail & df.label.eq(1)).sum())
    report[name]={'parsed_rows':rows,'tail_rows':tail_rows,'gaps':gaps,'segment0_vs_non_tail_mismatches':mismatch,'tail_attack_rows':tail_attacks,'passed':rows>0 and tail_rows==891068 and mismatch==0 and tail_attacks==0}
    print(name,report[name],flush=True)
result={'scope':'Full parsed four CSVs; gap/tail equivalence only, not full leakage audit','files':report,'passed':all(x['passed'] for x in report.values())}
out=root/'outputs/w02_b2/b1_segment_audit.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS' if result['passed'] else 'FAIL',out)
raise SystemExit(0 if result['passed'] else 1)

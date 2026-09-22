"""U17: 한 Claude 세션 기록(jsonl)에서 olla 사용·큰 파일 통째 읽기·훅 흔적을 센다. 사용: python session_olla_audit.py <세션.jsonl>"""
import json,sys,os,re,collections
from pathlib import Path
rows=[json.loads(l) for l in open(sys.argv[1],encoding="utf-8")]
tools=collections.Counter(); olla=collections.Counter(); reads=[]; prompts=0; hint=0; blocks=0
first=last=None
for r in rows:
    ts=r.get("timestamp"); 
    if ts: first=first or ts; last=ts
    m=r.get("message") or {}; c=m.get("content")
    if r.get("type")=="user" and (isinstance(c,str) or (isinstance(c,list) and not any(isinstance(b,dict) and b.get("type")=="tool_result" for b in c))) and not r.get("isMeta"):
        prompts+=1
    s=json.dumps(r,ensure_ascii=False)
    if "olla (local model" in s: hint+=1
    if '"decision": "block"' in s or "Final report has" in s: blocks+=1
    if r.get("type")=="assistant" and isinstance(c,list):
        for b in c:
            if b.get("type")!="tool_use": continue
            n=b["name"]; tools[n]+=1; inp=b.get("input",{})
            cmd=inp.get("command","") if isinstance(inp.get("command"),str) else ""
            for k in ("digest","ask","edit","find","route","estimate","stats"):
                if re.search(rf"\bolla {k}\b",cmd): olla[k]+=1
            if n=="Read":
                p=inp.get("file_path",""); whole=not(inp.get("offset") or inp.get("limit"))
                try: size=os.path.getsize(p)
                except OSError: size=-1
                reads.append((round(size/3) if size>0 else None, whole, Path(p).name))
big_whole=[r for r in reads if r[0] and r[0]>=3000 and r[1]]
print(json.dumps({"span":[first,last],"prompts":prompts,"tool_calls":sum(tools.values()),"top_tools":tools.most_common(8),
 "olla_calls":dict(olla),"plan_hints_seen":hint,"stop_blocks":blocks,"reads":len(reads),
 "big_whole_reads(>=3k tok)":len(big_whole),"big_whole_tokens":sum(r[0] for r in big_whole),
 "examples":sorted(big_whole,reverse=True)[:6]},ensure_ascii=False,indent=1))

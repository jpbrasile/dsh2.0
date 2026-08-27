import json, os, glob
B = os.path.join(os.path.expanduser("~"), "tools/aider-bench/aider/tmp.benchmarks/pi_D_t1_dflash2")
print(f"{'exercice':34s} {'joue':5s} {'verdict':8s} {'stub intact dans src/main':26s} {'tests tombes sur le stub'}")
print("-"*104)
for f in sorted(glob.glob(os.path.join(B, "*/exercises/practice/*/src/main"))):
    ex = f.replace(B+os.sep,"").replace("\\","/").replace("/exercises/practice/","/").replace("/src/main","")
    stub = False
    for r,_,fs in os.walk(f):
        for n in fs:
            try: 
                if "Please implement" in open(os.path.join(r,n),encoding="utf-8",errors="ignore").read(): stub=True
            except Exception: pass
    if not stub: continue
    rec = os.path.join(B, ex.split("/")[0], "exercises/practice", ex.split("/")[1], ".dsh.results.json")
    if not os.path.isfile(rec):
        print(f"{ex:34s} {'NON':5s} {'-':8s} {'oui (jamais joue)':26s} -")
        continue
    d = json.load(open(rec, encoding="utf-8"))
    tours = d.get("turns") or []
    ok = tours[-1].get("ok") if tours else None
    err = (tours[-1].get("erreurs") or "") if tours else ""
    n = err.count("Please implement")
    print(f"{ex:34s} {'oui':5s} {str(ok):8s} {'oui':26s} {n if n else 0}")

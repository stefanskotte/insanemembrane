"""Report remaining wiggles: chains of >= MIN_RUN consecutive short (< SHORT mm) top-copper pieces.
Usage: python wiggles.py <scan-data dir>"""
import json, sys, numpy as np
from collections import defaultdict
SHORT, MIN_RUN = 1.0, 3
R = json.load(open(f"{sys.argv[1]}/routing.json"))
k = lambda p: (round(p[0], 4), round(p[1], 4))
by = defaultdict(list)
for t in R["tracks"]:
    if t["layer"] == "F.Cu" and len(t["pts"]) == 2:
        by[t["net"]].append((np.array(t["pts"][0]), np.array(t["pts"][1])))
found = []
for net, segs in by.items():
    adj = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        adj[k(p)].append(i); adj[k(q)].append(i)
    short = {i for i, (p, q) in enumerate(segs) if np.hypot(*(q - p)) < SHORT}
    seen = set()
    for s in short:
        if s in seen: continue
        comp, st = set(), [s]
        while st:
            i = st.pop()
            if i in comp: continue
            comp.add(i)
            for e in (k(segs[i][0]), k(segs[i][1])):
                if len(adj[e]) == 2:
                    st += [j for j in adj[e] if j in short and j not in comp]
        seen |= comp
        if len(comp) >= MIN_RUN:
            c = np.mean([segs[i][0] for i in comp], axis=0)
            found.append((net, round(c[0], 1), round(c[1], 1), len(comp)))
print(len(found), "wiggly runs (>= %d consecutive pieces shorter than %.1f mm)" % (MIN_RUN, SHORT))
for f in sorted(found, key=lambda f: -f[3]): print("  net %s at (%s, %s): %d pieces" % f)

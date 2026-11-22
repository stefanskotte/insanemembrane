"""Summarise a kicad-cli DRC json: counts per type and a few examples with positions."""
import json, sys
from collections import defaultdict
d = json.load(open(sys.argv[1]))
nshow = int(sys.argv[2]) if len(sys.argv) > 2 else 3
by = defaultdict(list)
for v in d.get("violations", []):
    by[v["type"]].append(v)
for t, vs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(f"== {t}: {len(vs)}")
    for v in vs[:nshow]:
        items = "; ".join(f"{i['description'][:70]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v["items"])
        print(f"   {v['description'][:60]} | {items}")
u = d.get("unconnected_items", [])
print(f"== unconnected: {len(u)}")
for v in u[:nshow]:
    print("   " + "; ".join(f"{i['description'][:60]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v["items"]))

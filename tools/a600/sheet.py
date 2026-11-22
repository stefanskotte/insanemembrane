"""Close-up sheet (front | back) of given front-frame points with bridges drawn. Usage: sheet.py <scan-data> <out.png> x,y x,y ..."""
import cv2, json, sys, numpy as np
PX = 600 / 25.4
D, out = sys.argv[1], sys.argv[2]
pts = [tuple(map(float, a.split(","))) for a in sys.argv[3:]]
f = cv2.imread(f"{D}/../scan-front-stitched.png"); b = cv2.imread(f"{D}/../scan-back-mirrored-into-front-frame.png")
J = json.load(open(f"{D}/jumpers.json"))["jumpers"]
R = int(__import__("os").environ.get("R", 12)); tiles = []
for k, (x, y) in enumerate(pts):
    x0, y0, s = int((x - R) * PX), int((y - R) * PX), int(2 * R * PX)
    row = []
    for im in (f, b):
        c = np.full((s, s, 3), 255, np.uint8)
        sub = im[max(0, y0):y0 + s, max(0, x0):x0 + s]
        c[max(0, -y0):max(0, -y0) + sub.shape[0], max(0, -x0):max(0, -x0) + sub.shape[1]] = sub
        for j in J:
            cv2.polylines(c, [((np.array(j["path"]) - [x - R, y - R]) * PX).astype(np.int32)], False, (0, 0, 255), 3)
        cv2.circle(c, (int(R * PX), int(R * PX)), 30, (255, 0, 255), 4)
        for g in range(0, 2 * R + 1, 2):
            cv2.line(c, (int(g * PX), 0), (int(g * PX), 8), (0, 0, 0), 2); cv2.line(c, (0, int(g * PX)), (8, int(g * PX)), (0, 0, 0), 2)
        row.append(c)
    t = cv2.resize(np.hstack(row), None, fx=0.3, fy=0.3)
    cv2.putText(t, f"{k} ({x:.1f},{y:.1f})", (5, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    tiles.append(t)
while len(tiles) % 2: tiles.append(np.full_like(tiles[0], 255))
cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)]))

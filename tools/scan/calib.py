"""Find printed-ruler ticks in each scan and measure px/mm along both axes."""
import sys
import cv2
import numpy as np

NOM = 600 / 25.4  # nominal px per mm


def tick_lines(gray, axis):
    """axis=0: ruler runs along y (ticks are horizontal lines) -> score columns.
    Returns list of (column index, power) sorted by power."""
    g = 255.0 - gray.astype(np.float32)
    prof = g if axis == 0 else g.T  # rows = position along ruler, cols = candidate lines
    prof = prof - prof.mean(axis=0, keepdims=True)
    n = prof.shape[0]
    spec = np.abs(np.fft.rfft(prof, axis=0))
    f = np.fft.rfftfreq(n)
    band = (f > 1 / 25.0) & (f < 1 / 22.5)
    power = spec[band].max(axis=0) / (spec[1:].sum(axis=0) + 1)
    return power


def ticks_from_profile(p):
    """p: darkness profile along ruler. Return sub-pixel centres of 1 mm ticks."""
    p = np.convolve(p, np.ones(3) / 3, mode="same")
    thr = (p.max() + np.median(p)) / 2
    on = p > thr
    centres = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            w = p[i:j] - np.median(p)
            if 2 <= j - i <= 12:
                centres.append(i + (w * np.arange(j - i)).sum() / w.sum())
            i = j
        else:
            i += 1
    return np.array(centres)


def fit(centres):
    """Assign integer mm indices and fit px = a + b*mm; return b, residual, n."""
    if len(centres) < 20:
        return None
    d = np.diff(centres)
    keep = [centres[0]]
    idx = [0]
    for c in centres[1:]:
        k = idx[-1] + round((c - keep[-1]) / NOM)
        if k > idx[-1]:
            keep.append(c); idx.append(k)
    keep, idx = np.array(keep), np.array(idx)
    b, a = np.polyfit(idx, keep, 1)
    res = keep - (a + b * idx)
    # reject outliers once
    m = np.abs(res) < 3 * res.std() + 0.5
    b, a = np.polyfit(idx[m], keep[m], 1)
    res = keep[m] - (a + b * idx[m])
    return b, res.std(), m.sum(), idx[m].max() - idx[m].min()


def analyse(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    out = []
    for axis, name in ((0, "Y (along scan length)"), (1, "X (across scan width)")):
        power = tick_lines(img, axis)
        # candidate lines: local maxima groups
        order = np.argsort(power)[::-1]
        used = []
        for c in order[:400]:
            if any(abs(c - u) < 80 for u in used):
                continue
            used.append(c)
            prof = 255.0 - (img[:, c] if axis == 0 else img[c, :]).astype(np.float32)
            # average a few adjacent lines for robustness
            lo, hi = max(c - 3, 0), c + 4
            prof = 255.0 - (img[:, lo:hi].mean(1) if axis == 0 else img[lo:hi, :].mean(0))
            r = fit(ticks_from_profile(prof))
            if r and r[3] > 80 and r[1] < 1.5:
                out.append((name, c, r))
            if len(used) >= 6:
                break
    return out


for p in sys.argv[1:]:
    print(p)
    for name, c, (b, sd, n, span) in analyse(p):
        print(f"  {name:24s} line@{c:5d}  {b:.4f} px/mm = {b*25.4:.2f} dpi  "
              f"({(b/NOM-1)*100:+.2f}% vs 600)  ticks={n} span={span}mm  resid={sd:.2f}px")

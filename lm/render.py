import io, numpy as np
from PIL import Image

def png(v, layer, thr=3.0):
    """Turn a 2-D array into a transparent PNG that the map drapes over the area."""
    
    ok = np.isfinite(v); rgba = np.zeros(v.shape + (4,), np.uint8)
    if layer in ("z", "t", "delta"):                       # diverging: blue = lower, red = higher
        vmax = 4.0 if layer in ("z", "t") else (max(float(np.nanpercentile(np.abs(v[ok]), 98)), 1e-6) if ok.any() else 1.0)
        t = np.clip(np.nan_to_num(v) / vmax, -1, 1)
        lo = (thr / vmax) if layer in ("z", "t") else 0.05
        al = np.clip((np.abs(t) - lo) / max(1 - lo, 1e-6), 0, 1)
        pos = t > 0
        rgba[..., 0] = np.where(pos, 178, 33); rgba[..., 1] = np.where(pos, 24, 102); rgba[..., 2] = np.where(pos, 43, 172)
        rgba[..., 3] = (al * 220 * ok).astype(np.uint8)
    else:                                              # sequential
        lo, hi = np.nanpercentile(v[ok], [2, 98]) if ok.any() else (0, 1)
        t = np.clip((np.nan_to_num(v) - lo) / max(hi - lo, 1e-9), 0, 1)[..., None]
        rgba[..., :3] = (np.array([255, 255, 204]) + (np.array([12, 44, 132]) - np.array([255, 255, 204])) * t).astype(np.uint8)
        rgba[..., 3] = (200 * ok).astype(np.uint8)
    buf = io.BytesIO(); Image.fromarray(rgba, "RGBA").save(buf, "PNG"); return buf.getvalue()
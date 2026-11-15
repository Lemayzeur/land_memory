import glob, numpy as np
fs = sorted(glob.glob("cache/granules/*.npz")); print(len(fs), "saved files")
for f in fs:
    z = np.load(f); out = []
    for k in ("hh", "hv"):
        a = z[k]; ok = np.isfinite(a) & (a > 1e-4)
        out.append(f"{k.upper()}: {100 * ok.mean():.0f}% valid, mean {10 * np.log10(np.nanmean(a[ok])) if ok.any() else float('nan'):.1f} dB")
    print(f[-16:-4], z["hh"].shape, " | ".join(out))
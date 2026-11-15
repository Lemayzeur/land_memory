import numpy as np

# peer group keys
LC_NAMES = {
    10: "Tree cover", 
    20: "Shrubland", 
    30: "Grassland", 
    40: "Cropland", 
    50: "Built-up",
    60: "Bare", 
    80: "Water", 
    90: "Wetland", 
    95: "Mangroves"
}

RADAR_NAMES = {
    0: "Low HV (smooth/open)", 
    1: "Mid HV", 
    2: "High HV (dense vegetation)"
}

def api_series(rain_mm, k):
    """Antecedent Precipitation Index: API(t) = P(t) + k*API(t-1). A rain-history index, NOT soil moisture."""
    r = np.nan_to_num(np.asarray(rain_mm, float)); api = np.zeros(len(r))
    for t in range(len(r)): api[t] = r[t] + (k * api[t - 1] if t else 0.0)
    return api

def fit_all(x, Y, min_n=6):
    """For EVERY cell fit  
    backscatter(dB) = a + b*API.  
    Y: (dates, cells), NaN = no data.
    b = response slope, se = its standard error, sd = residual scatter, r2 = strength, n = valid observations."""
    ok = np.isfinite(Y)
    n = ok.sum(0)
    with np.errstate(all="ignore"):
        mx = np.where(ok, x[:, None], 0).sum(0) / n
        dx = np.where(ok, x[:, None] - mx, 0); my = np.where(ok, Y, 0).sum(0) / n
        dy = np.where(ok, Y - my, 0); sxx = (dx ** 2).sum(0)
        b = (dx * dy).sum(0) / sxx; a = my - b * mx
        sse = (np.where(ok, Y - (a + b * x[:, None]), 0) ** 2).sum(0)
        sd = np.sqrt(sse / (n - 2)); se = sd / np.sqrt(sxx); r2 = 1 - sse / (dy ** 2).sum(0)
    bad = (n < min_n) | ~(sxx > 1e-9)
    for v in (a, b, se, sd, r2):
        v[bad] = np.nan
    return dict(a=a, b=b, se=se, sd=sd, r2=r2, n=n, mx=mx, sxx=sxx)

def temporal(x, Y, j, valid):
    """DIRECTION A: location vs its OWN history. Fit on every other valid date, predict observation j,
    return expected, residual and a standardised residual (uses the prediction interval, so thin histories give wide limits)."""
    nan = np.full(Y.shape[1], np.nan)
    if not valid[j]: return dict(exp=nan, obs=nan, resid=nan, t=nan)
    use = valid.copy(); use[j] = False
    f = fit_all(x[use], Y[use])
    with np.errstate(all="ignore"):
        exp = f["a"] + f["b"] * x[j]
        sdp = f["sd"] * np.sqrt(1 + 1 / f["n"] + (x[j] - f["mx"]) ** 2 / f["sxx"])
        res = Y[j] - exp
    return dict(exp=exp, obs=Y[j], resid=res, t=res / np.maximum(sdp, 1e-9))

def make_groups(kind, lc, hv):
    """Peer groups = 'similar places'. Land cover is a first, broad grouping, not proof of identical conditions."""
    
    if kind == "landcover" and lc is not None:
        g = lc.copy()
        g[np.isin(g, (50, 80))] = -1
        return g, LC_NAMES
    
    if kind == "radar":
        with np.errstate(all="ignore"): 
            m = np.nanmean(hv, 0)
        g = np.digitize(m, np.nanquantile(m, [1 / 3, 2 / 3]))
        g[~np.isfinite(m)] = -1
        return g, RADAR_NAMES
    
    return np.zeros(hv.shape[1], int), {0: "All cells"}

def peer_z(b, se, groups, min_px=5):
    """DIRECTION B: robust z of each slope vs 
    the MEDIAN slope of its peer group; 
    denominator never below the cell's own se."""
    z = np.full(b.shape, np.nan)
    med = np.full(b.shape, np.nan)

    for g in np.unique(groups):
        i = (groups == g) & np.isfinite(b)
        if g < 0 or i.sum() < min_px: 
            continue
        m = np.median(b[i])
        mad = 1.4826 * np.median(np.abs(b[i] - m))
        med[i] = m
        z[i] = (b[i] - m) / np.maximum(np.maximum(mad, se[i]), 1e-9)

    return z, med
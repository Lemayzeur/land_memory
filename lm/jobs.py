"""Jobs. SLOW step = acquire data once (minutes, or instant if precomputed). FAST step = analysis (milliseconds, on every slider)."""
import threading, uuid, json, os, hashlib, pickle, datetime as dt, collections, numpy as np
from . import config as C, nisar, ancillary as anc, demo, model as M

JOBS, BYKEY = {}, {}
KS = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95] # for the k-sensitivity table

class NoData(Exception):
    pass

def grid(b):
    w, s, e, n = b
    nx = int(min(300, max(20, (e - w) * 111320 * np.cos(np.radians((s + n) / 2)) / C.TARGET_M)))
    ny = int(min(300, max(20, (n - s) * 110540 / C.TARGET_M)))
    while nx * ny > C.MAX_PIXELS: nx, ny = int(nx * .9), int(ny * .9)
    return nx, ny

# ---------- precomputed cache (Option A in the design document) ----------
def _cpath(p):
    key = json.dumps({k: p.get(k) for k in ("bbox", "maturity", "track", "rain")}, sort_keys=True)
    return os.path.join(C.CACHE_DIR, hashlib.md5(key.encode()).hexdigest()[:12] + ".pkl")

def _save(p, D):
    os.makedirs(C.CACHE_DIR, exist_ok=True); pickle.dump(D, open(_cpath(p), "wb"))

def _new(status="running"):
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = dict(id=jid, status=status, progress=0, log=[], diag=[], error=None, data=None, cache={}); return jid

def start(p):
    path = _cpath(p)
    if not p.get("demo") and os.path.exists(path) and not p.get("refresh"):
        # precomputed analysis exists: load instantly
        jid = _new("done"); D = pickle.load(open(path, "rb"))
        D["source"] = "precomputed analysis (built " + dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M") + ")"
        JOBS[jid].update(data=D, progress=100, log=["Loaded precomputed analysis from disk"]); return jid
    
    if p.get("cache_only"):
        return None
    
    key = json.dumps({k: p.get(k) for k in ("bbox", "maturity", "track", "rain", "demo")}, sort_keys=True)
    if key in BYKEY and JOBS[BYKEY[key]]["status"] in ("running", "done"):
        return BYKEY[key]
    
    jid = _new(); BYKEY[key] = jid
    threading.Thread(target=_run, args=(JOBS[jid], p), daemon=True).start()
    return jid

def _say(J, msg, prog=None):
    J["log"].append(msg)
    if prog is not None: J["progress"] = prog

def _run(J, p):
    try:
        b = p["bbox"]; nx, ny = grid(b)
        if p.get("demo"):
            _say(J, "DEMO mode: generating synthetic data", 30); D = demo.make(b, nx, ny); D["source"] = "synthetic demo data"
        else:
            _say(J, "Searching ASF for NISAR GCOV", 5)

            # TODO: build the search
            grans, J["diag"] = nisar.search(b, p.get("maturity", "mature"))
            if not grans: raise NoData("No NISAR GCOV granules found for this area and filter.")
            tr = nisar.tracks(grans); J["tracks"] = tr
            key = p.get("track") or tr[0]["key"]
            sel = [g for g in grans if "|".join((g["track"], g["dir"], g["frame"])) == key]
            mode = collections.Counter(g["mode"] for g in sel).most_common(1)[0][0]
            sel = [g for g in sel if g["mode"] == mode]                              # one acquisition configuration only
            if C.MAX_DATES: sel = sel[-C.MAX_DATES:]
            if len(sel) < 6: raise NoData(f"Only {len(sel)} dates on this track (need at least 6). Try another track, area, or maturity.")
            token = p.get("token") or C.EDL_TOKEN
            if not token: raise NoData("No Earthdata token. Set EDL_TOKEN in .env (see .env.example) or paste one in the Data panel.")
            _say(J, f"Reading {len(sel)} NISAR files (HH/HV), this takes a few minutes", 10)
            ok, hh, hv, skipped = nisar.read_stack(sel, b, nx, ny, token, lambda i, n_: _say(J, f"read {i}/{n_}", 10 + 60 * i / n_))
            if len(ok) < 6: raise NoData(f"Only {len(ok)} files could be read. " + "; ".join(skipped[:3]))
            _say(J, "Getting rainfall", 75)
            rain, label = anc.rain_daily(b, (ok[0]["date"] - dt.timedelta(days=31)).date(), ok[-1]["date"].date(), p.get("rain", "imerg"))
            _say(J, "Getting land cover", 90)
            try: lc = anc.landcover(b, nx, ny)
            except Exception as ex: lc = None; _say(J, f"Land cover unavailable ({type(ex).__name__}); choose another peer option")
            D = dict(dates=[g["date"] for g in ok], hh=hh, hv=hv, lc=lc, rain=rain, rain_label=label, skipped=skipped,
                     maturity=[g["maturity"] for g in ok], crid=[g["crid"] for g in ok], source="computed on demand just now")
        d0 = min(D["dates"]).date() - dt.timedelta(days=30); d1 = max(D["dates"]).date()
        days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
        D["rain_arr"] = np.array([D["rain"].get(str(d), np.nan) for d in days]); D["rain_start"] = d0    # missing stays NaN
        D.update(bbox=b, nx=nx, ny=ny, demo=bool(p.get("demo")))
        if not p.get("demo"): _save(p, D)
        J["data"] = D; J["status"] = "done"; J["progress"] = 100; _say(J, "Done", 100)
    except NoData as ex:
        J["status"] = "nodata"; J["error"] = str(ex)
    except Exception as ex:
        J["status"] = "error"; J["error"] = f"{type(ex).__name__}: {ex}"

# ---------- fast analysis ----------
def _api_at_dates(D, k):
    full = M.api_series(D["rain_arr"], k)
    gap = M.gap_flags(D["rain_arr"])
    idx = [min(max((d.date() - D["rain_start"]).days - 1, 0), len(full) - 1) for d in D["dates"]]   # rain up to the day BEFORE the pass
    api = full[idx].astype(float)
    api[gap[idx]] = np.nan
    return api, idx, full, gap

def analysis(J, pol, k, peers, di):
    key = (pol, round(k, 3), peers, di)
    if key in J["cache"]:
        return J["cache"][key]
    D = J["data"]
    api, _, _, _ = _api_at_dates(D, k)
    valid = np.isfinite(api); Y = D[pol]
    fit = M.fit_all(api[valid], Y[valid])
    groups, names = M.make_groups(peers, D["lc"], D["hv"])
    z, med = M.peer_z(fit["b"], fit["se"], groups)
    T = M.temporal(api, Y, di, valid)
    with np.errstate(all="ignore"):
        mean = np.nanmean(Y, 0)
    J["cache"][key] = dict(api=api, valid=valid, groups=groups, names=names, z=z, med=med, mean=mean, tz=T["t"], **fit)
    return J["cache"][key]

def summary(J, k, peers, di, thr):
    A = analysis(J, "hh", k, peers, di); ok = np.isfinite(A["b"])
    f = lambda v: round(100 * float(np.mean(np.abs(v[np.isfinite(v)]) >= thr)), 1) if np.isfinite(v).any() else None
    return dict(cells=int(ok.sum()), peer_flag=f(A["z"]), temporal_flag=f(A["tz"]), r2=round(float(np.nanmedian(A["r2"])), 2) if ok.any() else None,
                nobs=int(np.nanmedian(A["n"][ok])) if ok.any() else 0)

def pixel_report(J, i, k, peers, di, sc):
    """Everything the five dashboard sections need for ONE cell."""
    D = J["data"]; r, c = divmod(i, D["nx"]); w, s, e, n = D["bbox"]
    api, idx, full, gap = _api_at_dates(D, k); days = [D["rain_start"] + dt.timedelta(days=q) for q in range(len(full))]
    out = dict(ok=True, lon=w + (c + .5) / D["nx"] * (e - w), lat=n - (r + .5) / D["ny"] * (n - s), cell_m=D["cell_m"],
               land=M.LC_NAMES.get(int(D["lc"][i]), "Unknown") if D["lc"] is not None else "Unavailable",
               days=[str(d) for d in days], rain=[None if np.isnan(v) else round(float(v), 1) for v in D["rain_arr"]],
               api=[None if g else round(float(v), 1) for v, g in zip(full, gap)],
               acq=[dict(date=f"{d:%Y-%m-%d %H:%M}Z", api=None if np.isnan(a) else round(float(a), 1), used=bool(np.isfinite(a)),
                         hh=None if np.isnan(D["hh"][j, i]) else round(float(D["hh"][j, i]), 2),
                         hv=None if np.isnan(D["hv"][j, i]) else round(float(D["hv"][j, i]), 2)) for j, (d, a) in enumerate(zip(D["dates"], api))], pol={})
    A0 = analysis(J, "hh", k, peers, di); valid = A0["valid"]
    prev = float(np.percentile(api[valid], {"dry": 10, "mod": 50, "wet": 90}[sc["prev"]]))
    for pol in ("hh", "hv"):
        A = analysis(J, pol, k, peers, di)
        if not np.isfinite(A["b"][i]): out["pol"][pol] = None; continue
        g = int(A["groups"][i]); same = (A["groups"] == g) & np.isfinite(A["b"]); cnt, edges = np.histogram(A["b"][same], bins=16)
        T = M.temporal(A["api"], D[pol], di, A["valid"])
        S = M.scenario(A["a"][i], A["b"][i], A["sd"][i], A["se"][i], prev, k, sc["rain_mm"], sc["change"], sc["dry"])
        sens = []
        for kk in KS:
            ak, _, _, gp = _api_at_dates(D, kk); v = np.isfinite(ak); f = M.fit_all(ak[v], D[pol][v][:, [i]])
            sens.append(dict(k=kk, b=None if np.isnan(f["b"][0]) else round(float(f["b"][0]), 4), r2=None if np.isnan(f["r2"][0]) else round(float(f["r2"][0]), 2)))
        out["pol"][pol] = dict(a=float(A["a"][i]), b=float(A["b"][i]), se=float(A["se"][i]), sd=float(A["sd"][i]), r2=float(A["r2"][i]), n=int(A["n"][i]),
            z=None if np.isnan(A["z"][i]) else float(A["z"][i]), med=None if np.isnan(A["med"][i]) else float(A["med"][i]), peer=A["names"].get(g, str(g)), peers_n=int(same.sum()),
            hist=dict(edges=[float(x) for x in edges], counts=[int(x) for x in cnt]),
            temporal=dict(exp=None if np.isnan(T["exp"][i]) else float(T["exp"][i]), obs=None if np.isnan(T["obs"][i]) else float(T["obs"][i]),
                          resid=None if np.isnan(T["resid"][i]) else float(T["resid"][i]), t=None if np.isnan(T["t"][i]) else float(T["t"][i])),
            sens=sens, twin={q: float(v) for q, v in S.items()})
    if out["pol"]["hh"] is None and out["pol"]["hv"] is None:
        return dict(ok=False, msg="Not enough valid dates or peers here (masked cell, rain gaps, or too few similar cells).")
    m = out["pol"]["hh"] or out["pol"]["hv"]; n_ = m["n"]
    out["confidence"] = "Low (fewer than 8 observations)" if n_ < 8 else "Moderate (8 to 14 observations)" if n_ < 15 else "Higher (15+ observations)"
    out["peer"] = m["peer"]
    out["peers_n"] = m["peers_n"]
    a = (k * prev + sc["rain_mm"]) * k ** sc["dry"]
    out["twin"] = dict(api_prev=prev, api_after=a)
    return out

def meta(J):
    print("getting meta")
    out = dict(id=J["id"], status=J["status"], progress=J["progress"], log=J["log"][-6:], diag=J["diag"], error=J["error"], tracks=J.get("tracks", []))
    print("J[DATA]", J['data'])
    D = J["data"]
    if D:
        D["cell_m"] = round((D["bbox"][2] - D["bbox"][0]) * 111320 * np.cos(np.radians((D["bbox"][1] + D["bbox"][3]) / 2)) / D["nx"])
        r = D["rain_arr"]; t0 = D["rain_start"]
        def win(d, n): 
            i = (d.date() - t0).days
            v = r[max(i - n, 0): max(i, 0)]
            return None if np.isnan(v).any() else round(float(v.sum()), 1)
        out.update(bbox=D["bbox"], nx=D["nx"], ny=D["ny"], demo=D["demo"], source=D["source"], rain_label=D["rain_label"], skipped=D["skipped"], cell_m=D["cell_m"],
                   dates=[dict(date=f"{d:%Y-%m-%d %H:%M}Z", maturity=m, crid=c, r1=win(d, 1), r3=win(d, 3), r7=win(d, 7), r30=win(d, 30))
                          for d, m, c in zip(D["dates"], D["maturity"], D["crid"])],
                   rain_missing=int(np.isnan(r).sum()), mixed=len(set(D["maturity"])) > 1 or len(set(D["crid"])) > 1)
    return out
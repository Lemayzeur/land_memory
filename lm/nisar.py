"""Finding and reading NISAR GCOV (HHHH, HVHV) from ASF. Search tries several ways and REPORTS what it found."""
import re, datetime as dt, numpy as np
from concurrent.futures import ThreadPoolExecutor
from . import config as C

NAME = re.compile(r"NISAR_L2_[A-Z]{2}_GCOV_(\d{3})_(\d{3})_([AD])_(\d{3})_\d{4}_(\w{4})_[AD]_(\d{8})T(\d{6})_\d{8}T\d{6}_(X\d{5}|P\d{5})")
RANK = {
    "VALIDATED": 3, 
    "PROVISIONAL": 2, 
    "BETA": 1
}

def maturity(url):  # collection names: ..._BETA_V1, ..._PROVISIONAL_V1, validated has no maturity word
    return "BETA" if "_BETA_" in url else "PROVISIONAL" if "_PROVISIONAL_" in url else "VALIDATED"

def wkt(b, pad=0):
    w, s, e, n = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

def _query(b, pad, level, start, end=None):
    import asf_search as asf
    kw = dict(maxResults=500, intersectsWith=wkt(b, pad), start=start, end=end or dt.datetime.utcnow(), dataset=["NISAR"])
    if level: kw["processingLevel"] = ["GCOV"]
    res = asf.search(opts=asf.ASFSearchOptions(**kw))
    urls = res.find_urls(extension=".h5", pattern=r"^(?!.*QA_STATS).*", directAccess=False)
    return len(res), [u for u in urls if "_GCOV_" in u]

def search(bbox, mode="mature"):
    """Returns (granules, diagnostics). 
    Tries: strict filter -> no product filter -> area padded 0.5 deg."""
    start = C.START_PROV if mode != "all" else C.START_ANY
    diag, urls = [], []
    for label, pad, level in (("strict GCOV search", 0, True), ("search without product filter", 0, False),
                              ("area padded by 0.5 deg", 0.5, False)):
        try:
            n, urls = _query(bbox, pad, level, start)
            diag.append(f"{label}: {n} results, {len(urls)} GCOV files")
        except Exception as ex:
            diag.append(f"{label}: ERROR {type(ex).__name__}: {str(ex)[:150]}"); urls = []
        if urls: break
    best = {}
    for u in urls:
        m = NAME.search(u)
        if not m: continue
        cyc, trk, d, frm, mode_, day, hms, crid = m.groups()
        mat = maturity(u)
        if mode == "validated" and mat != "VALIDATED": continue
        if mode == "mature" and mat == "BETA": continue
        g = dict(url=u, track=trk, dir=d, frame=frm, mode=mode_, crid=crid, maturity=mat,
                 date=dt.datetime.strptime(day + hms, "%Y%m%d%H%M%S"))
        k = (cyc, trk, d, frm)                      # one acquisition: keep best maturity, then newest CRID
        if k not in best or (RANK[mat], crid) > (RANK[best[k]["maturity"]], best[k]["crid"]): best[k] = g
    diag.append(f"after maturity filter ({mode}) and de-duplication: {len(best)} acquisitions")
    return sorted(best.values(), key=lambda g: g["date"]), diag

def tracks(grans):
    t = {}
    for g in grans: 
        t.setdefault((g["track"], g["dir"], g["frame"]), []).append(g)
    return sorted([dict(key="|".join(k), label=f"track {k[0]} {('asc' if k[1]=='A' else 'desc')} frame {k[2]} · {len(v)} dates "
                        f"({min(x['date'] for x in v):%b %d}–{max(x['date'] for x in v):%b %d}) · {'/'.join(sorted({x['maturity'] for x in v}))}",
                        n=len(v)) for k, v in t.items()], key=lambda d: -d["n"])

def count_recent(bbox):
    """Quick coverage count for the scan button."""
    try:
        return len(search(bbox, "mature")[0])
    except Exception:
        return -1

def to_grid(da, epsg, bbox, nx, ny):
    """Clip to the area, block-average to ~TARGET_M (in LINEAR power), reproject to the output lon/lat grid."""
    import rioxarray  # noqa
    from rasterio.transform import from_bounds
    from rasterio.enums import Resampling
    w, s, e, n = bbox
    da = da.rename({"yCoordinates": "y", "xCoordinates": "x"}).rio.write_crs(epsg).rio.write_nodata(np.nan)
    da = da.rio.clip_box(minx=w - .02, miny=s - .02, maxx=e + .02, maxy=n + .02, crs="EPSG:4326")
    f = max(1, int(round(C.TARGET_M / abs(float(da.x[1] - da.x[0])))))
    da = da.coarsen(y=f, x=f, boundary="trim").mean().compute()
    return da.rio.reproject("EPSG:4326", transform=from_bounds(w, s, e, n, nx, ny), shape=(ny, nx),
                            resampling=Resampling.average).values.astype("float64")

def read_one(g, bbox, nx, ny, token):
    import fsspec, xarray as xr
    fs = fsspec.filesystem("http", headers={"Authorization": f"Bearer {token}"}, block_size=16 * 512 * 512)
    with fs.open(g["url"], "rb") as fh:
        tree = xr.open_datatree(fh, engine="h5netcdf", decode_timedelta=False, phony_dims="access", chunks="auto")
        ds = tree["/science/LSAR/GCOV/grids/frequencyA"].to_dataset()
        epsg = int(np.asarray(ds["projection"].attrs["epsg_code"]).item())
        return [to_grid(ds[p], epsg, bbox, nx, ny) if p in ds else np.full((ny, nx), np.nan) for p in ("HHHH", "HVHV")]

def read_stack(grans, bbox, nx, ny, token, progress):
    """Reads files in parallel (3 at a time). Returns dates, HH dB, HV dB, skipped list."""
    def work(g):
        try:
            return g, read_one(g, bbox, nx, ny, token)
        except Exception as ex:
            return g, ex
    ok, hh, hv, skipped = [], [], [], []
    with ThreadPoolExecutor(3) as ex:
        for i, (g, r) in enumerate(ex.map(work, grans)):
            if isinstance(r, Exception):
                skipped.append(f"{g['date']:%Y-%m-%d}: {type(r).__name__} {str(r)[:100]}")
            else:
                ok.append(g); hh.append(r[0].ravel()); hv.append(r[1].ravel())
            progress(i + 1, len(grans))
    db = lambda L: 10 * np.log10(np.where(np.array(L) > 1e-4, np.array(L), np.nan))
    return ok, db(hh), db(hv), skipped
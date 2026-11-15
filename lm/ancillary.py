import datetime as dt
import numpy as np
import os

from . import config as C

from dotenv import load_dotenv

load_dotenv()


def rain_daily(bbox, start, end, source="imerg"):
    """Returns ({'YYYY-MM-DD': mm}, label). 
    IMERG first (NASA); falls back to Open-Meteo/ERA5."""
    note = ""
    if source == "imerg":
        try: 
            return _imerg(bbox, start, end), "NASA GPM IMERG V07 daily"
        except Exception as ex: 
            note = f" (IMERG failed: {type(ex).__name__}: {str(ex)[:80]})"
            print(note)
    return _openmeteo(bbox, start, end), "Open-Meteo ERA5 reanalysis" + note

def _imerg(bbox, start, end):
    import earthaccess, xarray as xr
    w, s, e, n = bbox
    m = .1
    if not (os.getenvt("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD")): 
        raise RuntimeError("Earthdata username/password not set in .env")
    
    earthaccess.login(strategy="environment")
    res = earthaccess.search_data(
        short_name="GPM_3IMERGDL", 
        version="07", temporal=(str(start), str(end)),
        bounding_box=(w - m, s - m, e + m, n + m)
    )
    out = {}
    for f in earthaccess.open(res):                   # lazy remote read: only the small box is transferred
        d = xr.open_dataset(f, engine="h5netcdf")
        p = d["precipitation"].sel(lon=slice(w - m, e + m), lat=slice(s - m, n + m)).mean().item()
        out[str(d["time"].values.ravel()[0])[:10]] = float(p)
    if not out: 
        raise RuntimeError("no IMERG files returned")
    return out

def _openmeteo(bbox, start, end):
    import requests
    end = min(end, dt.date.today() - dt.timedelta(days=5))        # archive lags ~5 days
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=30, params=dict(
        latitude=(bbox[1] + bbox[3]) / 2, longitude=(bbox[0] + bbox[2]) / 2, start_date=str(start), end_date=str(end),
        daily="precipitation_sum", timezone="UTC"))
    j = r.json()["daily"]
    return {t: float(v) for t, v in zip(j["time"], j["precipitation_sum"]) if v is not None}   # None stays MISSING

def landcover(bbox, nx, ny):
    """Dominant ESA WorldCover class per output pixel (tile chosen from the area centre; areas crossing a tile edge may fail)."""
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling
    w, s, e, n = bbox
    la, lo = int(np.floor((s + n) / 6) * 3), int(np.floor((w + e) / 6) * 3)
    tile = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
    url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    with rasterio.open(url) as src:
        arr = src.read(1, window=from_bounds(w, s, e, n, src.transform), out_shape=(ny, nx), resampling=Resampling.mode)
    return arr.ravel().astype(int)
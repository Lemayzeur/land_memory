"""Synthetic data so the dashboard works with no accounts or network. 
Always labelled DEMO in the UI."""
import datetime as dt, numpy as np
from .model import api_series

def make(bbox, nx, ny):
    rng = np.random.default_rng(7); P = nx * ny
    start = dt.date(2026, 6, 1)
    r = rng.exponential(1, 163) * (rng.random(163) < .35) * 14
    rain = {str(start + dt.timedelta(d)): float(v) for d, v in enumerate(r)}
    for miss in (45, 46): rain.pop(str(start + dt.timedelta(miss)))      # simulated missing rain days
    dates = [dt.datetime(2026, 6, 17, 2, 46) + dt.timedelta(days=12 * i) for i in range(12)]
    yy, xx = np.mgrid[0:ny, 0:nx]; fx, fy = xx / nx, yy / ny
    lc = np.where(fy < .3, 10, np.where(fx > .65, 30, 40)).ravel()            # tree / grass / cropland
    slope = np.select([lc == 10, lc == 30], [.012, .02], .03)
    blob = (((fx - .3) ** 2 + (fy - .65) ** 2) < .012) | (((fx - .8) ** 2 + (fy - .2) ** 2) < .006)
    slope = np.where(blob.ravel(), slope * 2.6, slope)                         # planted "unusual" areas
    api = api_series(r, .85)[[(d.date() - start).days - 1 for d in dates]]
    mk = lambda base, s: base + np.outer(api, s) + rng.normal(0, .6, (len(dates), P))
    hh, hv = mk(-8, slope), mk(-15, slope * .5)
    chg = ((fx > .45) & (fx < .6) & (fy > .35) & (fy < .5)).ravel()               # planted BEHAVIOUR CHANGE on the last date
    hh[-1, chg] += 3.5; hv[-1, chg] += 2.0
    return dict(dates=dates, hh=hh, hv=hv, lc=lc, rain=rain,
                rain_label="synthetic rain", maturity=["DEMO"] * 12, crid=["-"] * 12, skipped=[])
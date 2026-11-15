"""Run ONCE before the presentation to build the real analysis and save it to cache/.
    python precompute.py                                   (default area)
    python precompute.py "Dhaka area, Bangladesh (small, fast)"
    python precompute.py all                               (default area + Dhaka + Merced, one after another)
The dashboard then opens each saved area instantly and labels it 'precomputed analysis'."""
import sys, time
from lm import jobs, config as C
names = sys.argv[1:] or [C.DEFAULT_AREA]
if names == ["all"]: names = [C.DEFAULT_AREA, "Dhaka area, Bangladesh (small, fast)", "Merced farmland, California (small, fast)"]
for name in names:
    print(f"\n===== {name} =====")
    J = jobs.JOBS[jobs.start(dict(bbox=C.PRESETS[name], maturity="mature", track="", rain="imerg", demo=False, refresh=True))]
    while J["status"] == "running": print(f"{J['progress']:.0f}%  {J['log'][-1]}"); time.sleep(3)
    print(J["status"], J["error"] or "saved to cache/"); print("\n".join(J["diag"]))
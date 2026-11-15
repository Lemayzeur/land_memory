import sys, time
from lm import jobs, config as C
name = sys.argv[1] if len(sys.argv) > 1 else C.DEFAULT_AREA
jid = jobs.start(dict(bbox=C.PRESETS[name], maturity="mature", track="", rain="imerg", demo=False, refresh=True))
J = jobs.JOBS[jid]
while J["status"] == "running": print(f"{J['progress']:.0f}%  {J['log'][-1]}"); time.sleep(3)
print(J["status"], J["error"] or "saved to cache/"); print("\n".join(J["diag"]))
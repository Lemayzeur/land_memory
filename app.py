import numpy as np
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, Response, render_template
from lm import jobs, nisar, config as C
# , render, model as M, 

app = Flask(__name__)

f = lambda name, d: float(request.args.get(name, d))

@app.get("/")
def index(): return render_template("index.html")

@app.get("/test/config")
def config(): 
    print("HELLO")
    return jsonify(presets=C.PRESETS, has_token=bool(C.EDL_TOKEN), max_side=C.MAX_SIDE_DEG, default=C.DEFAULT_AREA)

@app.post("/test/search")                       # quick: which NISAR files exist here?
def search():
    p = request.get_json()
    try: grans, diag = nisar.search(p["bbox"], p.get("maturity", "mature"))
    except Exception as ex: return jsonify(count=0, tracks=[], diag=[f"{type(ex).__name__}: {ex}"])
    return jsonify(count=len(grans), tracks=nisar.tracks(grans), diag=diag)

@app.get("/test/scan")                          # which preset areas have NISAR data right now?
def scan():
    with ThreadPoolExecutor(6) as ex:
        return jsonify(list(ex.map(lambda kv: (kv[0], nisar.count_recent(kv[1])), C.PRESETS.items())))

@app.post("/test/jobs")
def new_job(): return jsonify(id=jobs.start(request.get_json()))

@app.get("/test/jobs/<jid>")
def status(jid): return jsonify(jobs.meta(jobs.JOBS[jid]))

if __name__ == "__main__": 
    app.run(debug=False, threaded=True, port=5000)


import numpy as np
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, Response, render_template
from lm import jobs, nisar, render, config as C, model as M

app = Flask(__name__)

f = lambda name, d: float(request.args.get(name, d))

@app.get("/")
def index(): 
    return render_template("index.html")

@app.get("/test/config")
def config(): 
    print("HELLO")
    return jsonify(presets=C.PRESETS, has_token=bool(C.EDL_TOKEN), max_side=C.MAX_SIDE_DEG, default=C.DEFAULT_AREA)

@app.post("/test/search")
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
def new_job():
    return jsonify(id=jobs.start(request.get_json()))

@app.get("/test/jobs/<jid>")
def status(jid):
    return jsonify(jobs.meta(jobs.JOBS[jid]))

def args():
    J = jobs.JOBS[request.view_args["jid"]]; D = J["data"]; di = int(f("di", -1)); di = di + len(D["dates"]) if di < 0 else di
    sc = dict(rain_mm=f("rain_mm", 50), prev=request.args.get("prev", "mod"), dry=int(f("dry", 0)),
              change=f("change", 0) / 100 if request.args.get("scn") == "changed" else 0.0)
    return J, f("k", .85), request.args.get("peers", "landcover"), di, sc

@app.get("/api/jobs/<jid>/overlay.png")
def overlay(jid):
    J, k, peers, di, sc = args(); D = J["data"]; layer = request.args.get("layer", "z"); pol = request.args.get("pol", "hh")
    A = jobs.analysis(J, pol, k, peers, di)
    if layer == "delta":
        prev = np.percentile(A["api"][A["valid"]], {"dry": 10, "mod": 50, "wet": 90}[sc["prev"]])
        S = M.scenario(A["a"], A["b"], A["sd"], A["se"], prev, k, sc["rain_mm"], sc["change"], sc["dry"]); v = S["scn"] - S["ref"]
    else: v = {"z": A["z"], "t": A["tz"], "b": A["b"], "mean": A["mean"], "n": A["n"].astype(float)}[layer]
    return Response(render.png(np.asarray(v).reshape(D["ny"], D["nx"]), layer, f("thr", 3)), mimetype="image/png")

@app.get("/api/jobs/<jid>/summary")
def summary(jid):
    J, k, peers, di, _ = args(); return jsonify(jobs.summary(J, k, peers, di, f("thr", 3)))


@app.get("/api/jobs/<jid>/pixel")
def pixel(jid):
    J, k, peers, di, sc = args(); D = J["data"]; w, s, e, n = D["bbox"]
    c = int((f("lon", 0) - w) / (e - w) * D["nx"]); r = int((n - f("lat", 0)) / (n - s) * D["ny"])
    if not (0 <= c < D["nx"] and 0 <= r < D["ny"]): return jsonify(ok=False, msg="Outside the analysed area")
    return jsonify(jobs.pixel_report(J, r * D["nx"] + c, k, peers, di, sc))

if __name__ == "__main__": 
    app.run(debug=False, threaded=True, port=5000)


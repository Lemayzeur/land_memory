import numpy as np
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, Response, render_template
from lm import jobs, nisar, render, model as M, config as C

app = Flask(__name__)

f = lambda name, d: float(request.args.get(name, d))

@app.get("/")
def index(): return render_template("index.html")
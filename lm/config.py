import os, datetime as dt
from dotenv import load_dotenv

load_dotenv()

EDL_TOKEN = os.getenv("EDL_TOKEN", "") 

# FROM THI
START_PROV = dt.datetime(2026, 6, 17)           
START_ANY = dt.datetime(2025, 8, 1) 

# largest drawn area (protects the server)
MAX_SIDE_DEG = 0.8       

# output pixel size and cap
TARGET_M, MAX_PIXELS = 250, 60000               

# Are of interest for the demo
PRESETS = {                                
    "Artibonite, Haiti": [-72.9, 19.0, -72.3, 19.5],
    "Artibonite valley, Haiti (small, fast)": [-72.75, 19.10, -72.45, 19.35],
     # "Dhaka, Bangladesh": [],
    "Afar, Ethiopia (NISAR Cookbook test area)": [40.91, 12.39, 41.89, 13.25],
    "Central Valley, California": [-121.5, 36.5, -120.5, 37.4],
    "Mekong Delta, Vietnam": [105.0, 9.5, 106.2, 10.5],
    "Nile Delta, Egypt": [30.5, 30.5, 31.8, 31.5],
    "Punjab, India": [74.0, 30.5, 75.2, 31.5],

    "Dhaka area, Bangladesh (small, fast)": [90.25, 23.65, 90.55, 23.95],
    "Merced farmland, California (small, fast)": [-120.6, 37.15, -120.3, 37.4],
}

DEFAULT_AREA = "Artibonite, Haiti"
DEFAULT_AREA = "Artibonite valley, Haiti (small, fast)"
READ_WORKERS = 4  # NISAR files read in parallel
MAX_DATES = 0  # 0 = use all dates; e.g. 8 = only the latest 8 (faster build, thinner history)

# DJANGO STyle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CACHE_DIR = os.path.join(ROOT, "cache")
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
    "Afar, Ethiopia (NISAR Cookbook test area)": [40.91, 12.39, 41.89, 13.25],
    "Central Valley, California": [-121.5, 36.5, -120.5, 37.4],
    "Mekong Delta, Vietnam": [105.0, 9.5, 106.2, 10.5],
    "Nile Delta, Egypt": [30.5, 30.5, 31.8, 31.5],
    "Punjab, India": [74.0, 30.5, 75.2, 31.5]
}
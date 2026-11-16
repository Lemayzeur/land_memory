
# LAND MEMORY

  

**Learning how landscapes respond to rain, using NASA NISAR radar.**

  

LAND MEMORY is a web dashboard built for the NASA Space Apps Challenge. For every small square of land, it learns how satellite radar changes after rainfall, then flags squares that behave differently from their own past or from similar places. A Scenario Explorer lets you ask what-if questions about rainfall.

  
- **Live website:** [https://landmemory.pythonanywhere.com/](https://landmemory.pythonanywhere.com/)
- **30-second video:** [https://vimeo.com/1247139551](https://vimeo.com/1247139551)

> **Important:** Radar backscatter is not a direct measure of soil moisture or flooding. An unusual result means "look here", not "this is why". The Scenario Explorer is a simple statistical model, not a validated forecast.
  

## What it does

  

-  **Explore:** pick an area (start: Artibonite, Haiti) or draw your own, then click any map cell.

-  **History:** rain, a rain-history index (API), and NISAR HH/HV radar on each date. Missing rain is never treated as zero.

-  **Behavior:** fits `backscatter (dB) = a + b × API` for HH and HV, with uncertainty, R², and sensitivity to the API decay `k`.

-  **Unusual:** two checks. (A) this cell vs. its own history, (B) this cell vs. similar places (same land cover).

-  **Scenario Explorer** (the "Twin" tab): choose rainfall (0 to 150 mm), previous conditions, dry days, and normal or changed landscape, and see the estimated HH/HV response.

-  **Honest labels:** the top banner says whether data is synthetic demo, precomputed, or computed on demand.


## Example: Artibonite valley, Haiti

Our precomputed demo uses 11 NISAR passes (June to October 2026) on one track, averaged to 250 m cells, paired with NASA GPM IMERG daily rainfall. We compared each cell's latest pass (30 October 2026) with its own history, and its radar response with other cropland cells.

| Result (HH, flag threshold 3) | Value |
|---|---|
| Cells analysed | 13,860 |
| Typical number of observations per cell | 11 |
| Cells flagged vs. their own history | 5.3% |
| Cells flagged vs. similar places | 1.8% |

The flagged cells cluster in a block near the western coast and a patch in the north-east. We treat them as places to inspect, not as confirmed change. Possible explanations include standing water, vegetation change, a large rain just before the pass, or processing differences (the dashboard warns that our passes mix provisional and validated NISAR processing). Field data would be needed to confirm any of these.


## Data sources

  

| Data | Source | Needs |
|---|---|---|
| NISAR L-band GCOV (HH, HV), Provisional and Validated, Version 1 | NASA / ISRO, via ASF DAAC | Earthdata token |
| Daily rainfall: GPM IMERG Late Run V07 (GPM_3IMERGDL) | NASA GES DISC | Earthdata login |
| Rainfall fallback (optional, not used for the Haiti results): Open-Meteo ERA5 | Open-Meteo | none |
| Land cover: ESA WorldCover 10 m 2021 | ESA | none |
| Base map and libraries | OpenStreetMap, MapLibre GL JS, Chart.js (CDN) | internet |

NISAR BETA products are excluded by default because they are not fully calibrated.


## Requirements

  

- Python 3.10 or newer
- Internet connection (map tiles and libraries load from the web)
- A free [NASA Earthdata](https://urs.earthdata.nasa.gov) account (only for real data)

  

## Install

  

```bash

git  clone https://github.com/Lemayzeur/land_memory.git 
# or git@github.com:Lemayzeur/land_memory.git over SSH

cd  land_memory

python  -m  venv  .venv

source  .venv/bin/activate  # Windows: .venv\Scripts\activate

pip  install  -r  requirements.txt

```

  

## Set your credentials

  

```bash

cp  .env.example  .env  # Windows: copy .env.example .env

```

  

Open `.env` and replace the placeholders:

  

```

EDL_TOKEN=PASTE_YOUR_EARTHDATA_BEARER_TOKEN_HERE

EARTHDATA_USERNAME=PASTE_YOUR_EARTHDATA_USERNAME_HERE

EARTHDATA_PASSWORD=PASTE_YOUR_EARTHDATA_PASSWORD_HERE

```

  

-  **Token:** [urs.earthdata.nasa.gov/profile](https://urs.earthdata.nasa.gov/profile) → *Generate Token* (tokens expire, so regenerate if downloads fail).

- Username and password are only used for IMERG rainfall. Without them, the app falls back to Open-Meteo and says so.

-  **Never commit `.env`.** It is already in `.gitignore`.

  **Makesure you Authorize NASA GES DISC for your profile**

1.  Open your [NASA Earthdata account profile](https://urs.earthdata.nasa.gov/profile).
2.  Find the Applications or Authorized Applications section.
3.  Look for **NASA GESDISC DATA ARCHIVE**.
4.  Authorize it if it is not already authorized.

No credentials? Skip this step. The dashboard still works with demo data.

  

## Run

  

```bash

python  app.py

```

  

Open <http://localhost:5000>.

  

- With no saved real analysis, the dashboard opens with clearly labeled **synthetic demo data**. You can also click **Instant demo** at any time.

- With a saved analysis, it opens that one automatically (green banner, "precomputed analysis").

  

## Build a real analysis (do this before a presentation)

  

Reading NISAR files over the internet is slow (many minutes to about an hour). Build once, then the dashboard opens instantly:

  

```bash

python  precompute.py  # default: Artibonite valley, Haiti (small, fast)

python  precompute.py  "Dhaka area, Bangladesh (small, fast)"  # a named preset

python  precompute.py  all  # default + Dhaka + Merced, one after another

```

You can update the config to precompute your own locations.

  

- Finished files are saved in `cache/granules/`, so a stopped or failed run continues where it left off.

- The terminal prints `start`, `done`, or `FAIL` for each file.

- Settings are in `lm/config.py`: `MAX_DATES` (use only the latest N dates for a faster build), `READ_WORKERS`, `TARGET_M` (cell size), and the preset areas.

  

Check that the saved data is real and displays:

  

```bash

python  check_cache.py  # checks the individual saved NISAR files

```

  

## Using the dashboard

  

| Where | What it does |
|---|---|
| **Left: Area** | Choose a preset or **Draw area on map** (up to 0.8° per side). |
| **Left: Data** | Data maturity, orbit track, rain source, **Find NISAR data** (quick search), **Build analysis** (slow, or instant if saved), **Scan preset areas** (which have data now). |
| **Left: Map and model** | Map layer, observation to test, HH/HV, peer grouping, API decay `k`, flag threshold, opacity. |
| **Map** | Colored overlay for the chosen layer. Click a cell to inspect it. |
| **Right: 1 Explore** | Land cover, peers, observation counts, confidence. |
| **Right: 2 History** | Rain, API, and radar dots (hollow = excluded, red triangle = missing rain). |
| **Right: 3 Behavior** | The fitted equations, R², and sensitivity to `k`. |
| **Right: 4 Unusual** | Expected vs. observed (own history) and slope vs. similar places. |
| **Right: 5 Twin** | Scenario Explorer: rainfall, previous conditions, dry days, scenario, and a map layer for the simulated change. |
| **Top: About & limits** | Plain-language limits of the method. |

  

Preset areas: Artibonite (small and large), Afar Ethiopia, Dhaka area, Merced farmland, Central Valley California, Mekong Delta, Nile Delta, Punjab. Use **Scan preset areas** to see which currently have NISAR data. The preset boxes are approximate, so check them on the map.

  

## Project structure

  

```

app.py Flask server (routes only)

precompute.py build and save real analyses

check_cache.py verify the saved NISAR files

lm/config.py settings, presets, credentials loader

lm/model.py the science: API, regression, own-history and peer checks, scenario

lm/nisar.py ASF search and NISAR GCOV reading

lm/ancillary.py rainfall and land cover

lm/jobs.py background jobs, cache, fast re-analysis

lm/render.py map overlay images

lm/demo.py synthetic demo data

templates/ static/ the web page (HTML, CSS, JavaScript)

cache/ saved results (not committed)

```

  

## Troubleshooting

  

-  **Map stays empty:** open the browser console (F12). A 404 on `/api/jobs/...` usually means the page and server routes do not match. Hard-refresh with `Ctrl+Shift+R`.

-  **No granules found:** click **Find NISAR data** and read the log. It shows what each search returned. Try another maturity, area, or **Scan preset areas**.

-  **`dask` or `MissingCRS` errors:**  `pip install dask` and update to the latest code.

-  **Build seems stuck:** watch the terminal for `start` and `done` lines. A stalled connection times out after 2 minutes and retries once.

-  **Credentials:** values starting with `PASTE_` are treated as "not set".

  

## Limitations

  

- NISAR repeats about every 12 days and calibrated data starts in June 2026, so histories are short. The confidence label reflects this.

- Rainfall is about 10 km resolution; cells are about 250 m. Land cover is a broad grouping.

- The NISAR quality mask layer and a full noise-floor treatment are not yet used.

- The Digital Twin is a statistical prototype, not a physical water model, and is not validated.

- Provisional and validated NISAR products may differ. Mixed versions can look like change.

  

## License

  

**MIT License**

  

## Acknowledgments

  

University of Missouri-Columbia (Institute of Data Science and Informatics, College of Agriculture, Food and Natural Resources), NASA and ISRO (NISAR), ASF DAAC, NASA GPM IMERG, ESA WorldCover, OpenStreetMap contributors, MapLibre GL JS, Chart.js.

  

## AI assistance disclosure

  

Parts of this project's code, structure, and documentation were written and improved with **Claude**, an AI assistant made by Anthropic, including code improvement, debugging, and drafting this README. AI-generated code can contain mistakes. The team is responsible for the final content and results.

## References

[1] NASA/JPL/NISAR. (2026). *NISAR Provisional Geocoded Polarimetric Covariance Product (Version 1)* [Data set]. NASA Alaska Satellite Facility Distributed Active Archive Center. https://doi.org/10.5067/NIL2GCOV-P1. Date accessed: 2026-11-15.
[2] NASA/JPL/NISAR. (2026). *NISAR Geocoded Polarimetric Covariance Product (Version 1, validated)* [Data set]. NASA Alaska Satellite Facility Distributed Active Archive Center. https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gcov-v1-1. Date accessed: 2026-11-15.
[3] Huffman, G.J., et al. *GPM IMERG Late Precipitation L3 1 day 0.1 degree x 0.1 degree V07 (GPM_3IMERGDL)* [Data set]. NASA GES DISC. https://doi.org/10.5067/GPM/IMERGDL/DAY/07. Date accessed: 2026-11-15.
[4] Zanaga, D., et al. (2022). *ESA WorldCover 10 m 2021 v200* [Data set]. European Space Agency. https://esa-worldcover.org/en/data-access.
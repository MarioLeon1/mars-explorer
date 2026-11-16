# Investigación de fuentes de datos y toolchain (2026-11-16)

> Informe generado durante la fase de planificación. [LIVE] = verificado con petición HTTP real ese día; [DOC] = solo documentado.

## raw-images

# Perseverance raw images: verified interfaces (checked live 2026-11-16, ~16:25 UTC, from PowerShell 5.1)

## Verdict
- **Primary source: the legacy `mars.nasa.gov/rss/api` raw_images JSON feed.** I verified it live (HTTP 200). It has not moved to science.nasa.gov, and the official raw-images page still calls it. Its newest data is sol 2031, taken 2026-11-06 and received 2026-11-06T15:59:53Z. It holds 1,055,868 images in total, of which 579,518 are `Full`.
- **Fallback for science-grade 3D: the PDS Imaging Node** at planetarydata.jpl.nasa.gov. I verified it live (HTTP 200, `Access-Control-Allow-Origin: *`). It has the real XYZ, RNG, UVW and slope products plus meshes. Its coverage stops far behind the raw feed: the directory listings end at **sol 658**, with directories dated 2023-03.
- **api.nasa.gov `mars-photos` does not work.** I tested it live and every endpoint returns **404**. Do not use it.
- **science.nasa.gov raw-images page: not verified.** The TLS connection was dropped from PowerShell 5.1, even with TLS 1.2 forced. The working feed is on mars.nasa.gov anyway.

---

## 1. Raw image JSON feed (primary): verified live, HTTP 200

**Base URL:** `https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json`

The page `https://mars.nasa.gov/mars2020/multimedia/raw-images/` returned 200. Its React bundle `/js/raw-images/m20/static/js/main.1a396d7e.chunk.js` builds `/rss/api/?feed=raw_images&category=mars2020,ingenuity&feedtype=json&ver=1.2&num=...`.

**Response headers:**
- `Content-Type: application/json;charset=UTF-8`
- `Access-Control-Allow-Origin: *`, so a browser can call it directly.
- `Cache-Control: max-age=60`, served through CloudFront.
- There are no rate-limit headers and no API key. Throttle yourself and cache on the backend.

### Query parameters (each one tested)
| Param | Meaning / verified behaviour |
|---|---|
| `num` | Page size. **Capped at 100**: `num=1000` came back with `per_page=100` and 100 items, about 217 KB. |
| `page` | Zero-based. Past the end you get `images: []`. Sol 2000 Full has 33 items, so page 5 at 100 per page was empty. |
| `order` | `sol+desc` or `sol+asc`. The site's own sort string is `sol desc,instrument_sort asc,sample_type_sort asc, date_taken desc`. |
| `search` | Camera filter: pipe-separated and starting with a pipe, e.g. `search=\|NAVCAM_LEFT` or `search=\|FRONT_HAZCAM_LEFT_A\|FRONT_HAZCAM_LEFT_B`. URL-encoded, the pipe is `%7C`. |
| `condition_2` | Lower bound in the form `<value>:<field>:gte`. `condition_2=1990:sol:gte` worked. `condition_2=2026-11-01:date_taken:gte` worked and returned 6 items. **The `date_received` conditions were ignored** in every format I tried. |
| `condition_3` | Upper bound: `<value>:sol:lte` worked. The site code also uses `<list>:sol:in`. |
| `extended` | Facets, comma-terminated: `sample_type::full,` (the site default), `sample_type::thumbnail,`, `product_type::raw,` / `product_type::color,`, and `product_id::ecv,` for movie frames. |
| `id` | Detail for a single image: `&id=<imageid>`. Returns `{"image":[...],"type":"mars2020-imagedetail-1.1"}` with extra keys `link_related_sol`, `json_link_related_sol` and `link_related_camera`. |
| `sol` | `&sol=2000` returns that whole sol unpaginated (`type: mars2020-images-1.1`) and has no `total_results`. |
| `ver=1.2&latest=true` | Returns `latest`, `latest_sol=2031`, `latest_sols`, `new_count`, `sol_count`, `total=1055868`, `type: mars2020-latest-images-1.1`. Useful for incremental sync. |

`category=ingenuity` also works: 14,553 results, camera HELI_NAV.

**Top-level fields in a list response:** `images[]`, `per_page`, `page`, `total_results` (count after filters), `total_images` (1,055,868), `mission`, `type="mars2020-images-list-1.1"`.

### Working examples (each returned 200 today)
```
# Latest full-frame images, newest first
https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&num=100&page=0&order=sol+desc&extended=sample_type::full,

# NAVCAM_LEFT, sols 1990-2000 (total_results=250)
https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&num=100&page=0&order=sol+desc&search=|NAVCAM_LEFT&condition_2=1990:sol:gte&condition_3=2000:sol:lte&extended=sample_type::full,

# Front Hazcam left (A or B), sols 1500-1502 (6 results)
...&search=|FRONT_HAZCAM_LEFT_A|FRONT_HAZCAM_LEFT_B&condition_2=1500:sol:gte&condition_3=1502:sol:lte&extended=sample_type::full,

# Single image
https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&id=NLG_2000_0844480656_659ECM_N0910970NCAM00500_00_2I4J
```

### Fields in each image (from a live MCZ_LEFT record, sol 2024)
```
imageid: "ZL0_2024_0846622583_145EBY_N0930000ZCAM10058_1100LMJ"
sol: 2024 (int)   site: 93 (int)   drive: "0" (string)
attitude: "(0.682313,0.00347943,0.0627555,0.728354)"   # rover quaternion, string
date_taken_utc: "2026-10-30T09:21:53.576"   (no Z)
date_taken_mars: "Sol-02024M13:10:59.198"
date_received: "2026-11-04T03:39:55Z"
title, caption, credit: "NASA/JPL-Caltech/ASU"
sample_type: "Full" | "Thumbnail"
link (HTML page), json_link (detail JSON)
camera: { instrument: "MCZ_LEFT", filter_name: "ZCAM_L0_RGB" (or "UNK"),
          camera_model_type: "CAHV"|"CAHVOR"|"CAHVORE",
          camera_model_component_list: "(..);(..);..",
          camera_position: "(x,y,z)", camera_vector: "(x,y,z)" or "UNK" }
image_files: { small: ..._320.jpg, medium: ..._800.jpg, large: ..._1200.jpg, full_res: ...png }
extended: { mastAz: "-32.6592", mastEl: "-58.9315", sclk: "846622598.406",
            scaleFactor: "1" (or "UNK"), xyz: "(83.3992,-48.0124,-8.55903)",
            subframeRect: "(1,1,1648,1200)", dimension: "(1648,1200)" }
```

Corrections to what the task assumed:
- There is **no `extended.filter` or `extended.sample_type`**. The filter is `camera.filter_name` and `sample_type` sits at the top level.
- All numeric extended values are **strings**, and "UNK" values occur. Tuples come as strings like `"(a,b,c)"`, so they need parsing.
- `xyz` is often `(0.0,0.0,0.0)`.
- Thumbnail records are tiny, e.g. `dimension (80,60)`. Thumbnail imageids carry `_T` in place of `_N`.
- `sample_type` values: I observed only `Full` and `Thumbnail`. The site exposes only those two plus movie frames (`product_id::ecv`). Treat other values, such as Partial, as possible but not observed.

### Camera instrument IDs (taken from the official page's JS filter config)
- **Engineering:** NAVCAM_LEFT, NAVCAM_RIGHT, FRONT_HAZCAM_LEFT_A, FRONT_HAZCAM_LEFT_B, FRONT_HAZCAM_RIGHT_A, FRONT_HAZCAM_RIGHT_B, REAR_HAZCAM_LEFT, REAR_HAZCAM_RIGHT, CACHECAM
- **Science:** MCZ_LEFT, MCZ_RIGHT, SKYCAM, PIXL_MCC, SHERLOC_WATSON, SHERLOC_ACI, SUPERCAM_RMI
- **EDL:** EDL_PUCAM1, EDL_PUCAM2, EDL_DDCAM, EDL_RUCAM, EDL_RDCAM, LCAM
- **Ingenuity** (`category=ingenuity`): HELI_NAV, HELI_RTE

The UI groups each Hazcam side's A and B units: `FRONT_HAZCAM_LEFT_A|FRONT_HAZCAM_LEFT_B`.

---

## 2. api.nasa.gov Mars Rover Photos: dead (verified live)
- `GET https://api.nasa.gov/mars-photos/api/v1/rovers/perseverance/latest_photos?api_key=DEMO_KEY` returned **404**. `/rovers/perseverance/photos?sol=100`, `/manifests/perseverance` and `/rovers` also returned 404.
- The gateway itself is up: APOD with DEMO_KEY returned 200, and the 404 carried `X-Ratelimit-Limit: 10` (the DEMO_KEY limit) and `Via: heroku-router`.
- The old mirror `https://mars-photos.herokuapp.com/api/v1/...` also returned 404.
- The upstream project, github.com/corincerami/mars-photo-api, was archived on 2025-10-08.

---

## 3. PDS Imaging Node (3D and terrain fallback): verified live
- `https://pds-imaging.jpl.nasa.gov/data/mars2020/` redirects to **`https://planetarydata.jpl.nasa.gov/img/data/mars2020/`** (200).
- **Bundles listed:** mars2020_{navcam,hazcam,mastcamz,cachecam,edlcam}_ops_{raw,calibrated} plus the 3D/terrain bundles:
  - mars2020_navcam_ops_{stereo,mesh,mosaic}
  - mars2020_hazcam_ops_{stereo,mesh,mosaic}
  - mars2020_mastcamz_ops_{stereo,mesh,mosaic}
  - mars2020_mastcamz_sci_calibrated, mars2020_helicam, mars2020_imgops, m2020_edlcam_raw, superseded/
- **Directory layout:** `<bundle>/data/sol/NNNNN/ids/rdr/ncam/`. Each bundle also has `bundle.xml` and `data/collection_data_inventory.csv`.
- **Verified listing:** `https://planetarydata.jpl.nasa.gov/img/data/mars2020/mars2020_navcam_ops_stereo/data/sol/00076/ids/rdr/ncam/` holds 3,862 entries: `.IMG` products with PDS4 `.xml` labels.
- **Product-type codes found** (characters 24-26 of the filename):
  - Geometry: **XYZ, XYR, XYM, MXY, XRZ, XRR**
  - Range: **RNG, RNR**
  - Surface normals: **UVW, UVS**
  - Slope and terrain: **SLP, SHD, SMG, SNT, SRD**
  - Disparity: DSP, DSR, DFF, MDS
  - Also: ARK, GR*/GU* (roughness/reachability), RUC/RUF/RUS
- **Example file:** a HEAD on `.../NLF_0076_0673685057_120XYZLN0032430NCAM00603_0A00LLJ02.IMG` returned 200, **236,011,520 bytes**, `Access-Control-Allow-Origin: *`. These files are large binary IMG (VICAR/PDS4), so convert them on the backend.
- **Coverage:** the navcam raw, stereo and mesh listings all end at **sol 00658**. mastcamz_ops_calibrated ends at 00089.
- **The server soft-404s.** Missing paths, e.g. `sol/02000/` or `sol/99999/`, return **200 with the bundle index page**. Check for the listing content rather than the status code.
- **Not checked:** the file formats inside the mesh bundle. The sol 76 path I guessed was empty.

---

## 4. Image file hosting: verified live
- `HEAD https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/02000/ids/edr/browse/ncam/NLG_2000_0844480656_659ECM_N0910970NCAM00500_00_2I4J01.png` returned **200**:
  - `Content-Type: image/png`
  - `Content-Length: 114829`
  - `Server: AmazonS3` through CloudFront, with ETag, Last-Modified and `Accept-Ranges: bytes`
- The `_1200.jpg` version returned 200, `image/jpg` (non-standard type), 9,982 bytes.
- **No `Access-Control-Allow-Origin` on the image files**, even when the request sent an Origin header. A plain `<img>` hotlink works, and there was no Referer blocking. However, drawing these images to a canvas or using them as WebGL textures (three.js) will **taint the canvas or fail**.
  - Proxy or cache the images through the Python backend for any pixel or 3D work.
  - The JSON feed and the PDS files do send `ACAO *`.
- **URL pattern:** `/mars2020-raw-images/pub/ods/surface/sol/{SSSSS}/ids/edr/browse/{ncam|zcam|scam|fcam|...}/{imageid}01{.png|_320.jpg|_800.jpg|_1200.jpg}`. Use the URLs from `image_files` rather than building them yourself.

---

## Limitations
- The raw images are **uncalibrated browse products**: they may be stretched, subframed or downsampled (`scaleFactor`). They are fine for display but not for measurement.
- Real 3D comes only from PDS, and PDS lags heavily (sol 658 against 2031 in the live feed). A cheaper option for the live feed is per-image camera pose: `camera_model_component_list` (CAHV/CAHVOR/CAHVORE), `camera_position`, `attitude`, `site`/`drive` and `mastAz`/`mastEl`.
- The feed is undocumented, with no SLA or key. Field names have been stable since 2021 (`type` reads `-1.1`), but keep a defensive parser.
- Pages are at most 100 items. Use sol windows plus `latest=true` for incremental sync.
- Filtering on `date_received` does not work. Filter on sol or `date_taken` instead.

## Attribution
- Show each image's own **`credit`** field. Values seen: `NASA/JPL-Caltech` (Navcam/Hazcam), `NASA/JPL-Caltech/ASU` (Mastcam-Z), `NASA/JPL-Caltech/LANL/CNES/IRAP` (SuperCam RMI).
- A generic line: "Images courtesy NASA/JPL-Caltech. Raw images from the Mars 2020 Perseverance mission."
- For PDS products, cite "NASA PDS Imaging Node / JPL" and the bundle's DOI or URN.
- NASA imagery is generally not copyrighted (see the JPL image-use policy at jpl.nasa.gov/imagepolicy). Do not imply NASA endorsement and do not use NASA logos.

Sources: [corincerami/mars-photo-api (archived)](https://www.github.com/corincerami/mars-photo-api), [PDS Mars 2020 volumes page](https://pds-imaging.jpl.nasa.gov/volumes/mars2020.html), plus the live requests listed above.

---

## terrain-traverse

# Mars Explorer: real Jezero terrain and Perseverance position data (research for planning, 2026-11-16)

Everything marked **LIVE** I requested myself today from this machine with PowerShell `Invoke-WebRequest -UseBasicParsing` (GET, HEAD, or a byte-range request) and got the response shown. Everything marked **DOC** I only found in documentation and did not check.

## 1. Rover positions (real, per sol)

### 1a. MMGIS "Where is the rover" GeoJSON — LIVE, all HTTP 200, served from AmazonS3

| URL | Size | Last-Modified | Content |
|---|---|---|---|
| `https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json` | 603 KB | 28 Oct 2026 | 708 Point features, sols 13 to **2022**; layer name `M20_waypoints_sol2022_all` |
| `https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json` | 1.72 MB | 28 Oct 2026 | 559 LineString features; CRS `urn:ogc:def:crs:OGC:1.3:CRS84`; coordinates are `[lon, lat, elev]` |
| `https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints_current.json` | 939 B | — | A single feature: the latest position |

- **Other URLs:**
  - `science.nasa.gov/mmgis-maps/...` failed (the connection was closed).
  - `.../M20/config.json` returned **403**.
- **Waypoint properties (real excerpt, latest point):**
  - `RMC "93_0"`, `site 93`, `drive 0`, `sol 2022`
  - `easting 4342256.503`, `northing 1092764.278`
  - `elev_geoid -1936.37`, `elev_radii -9999.0`, `radius -9999.0`
  - `lon 77.23322287`, `lat 18.43559434`
  - `roll 5.58`, `pitch 4.69`, `yaw 93.97`, `yaw_rad`, `tilt 7.29`
  - `dist_m 22.061`, `dist_total_m 45245.71`, `dist_km`, `dist_mi`
  - `final "y"`, `Note "End-of-drive localization"`
  - `images[]`: a panorama with `url "Layers/mosaics/N_LRGB_2022_..._CYL_...jpg"`, `rows`, `columns`, `azmin`, `azmax`, `elmin`, `elmax`
- **Traverse properties:** `sol`, `fromRMC`, `toRMC`, `length` (m), `SCLK_START`, `SCLK_END`.
- **Data quirks:**
  - 96 of the 708 waypoints have `elev_radii` and `radius` set to `-9999`. `elev_geoid` is always filled.
  - Some sols appear more than once (mid-drive and end-of-drive fixes).
- **Projection (I derived this from the data):**
  - `northing = R·lat_rad` and `easting = R·cos(18.4663°)·lon_rad`, with R = 3,396,190 m.
  - So easting/northing are in an **equirectangular projection with a standard parallel of 18.4663°**. That is not the grid the USGS products use (true-scale latitude 0°). Use `lon`/`lat`, or the matching PLACES DEM in 1b.
- **CORS:** no `Access-Control-Allow-Origin` header without an `Origin` header. With `Origin: http://localhost:5173` it returns `ACAO: *`, so a browser can fetch it directly. I would still cache it in the backend.
- **Rate limits and terms:** none documented. It is an unofficial ops-visualization endpoint, so it may move without notice. Credit NASA/JPL-Caltech.

### 1b. PDS "PLACES" (Position Localization and Attitude Correction Estimate Storage) bundle — official archive, LIVE, HTTP 200

Base: `https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/` (Release 16; covers sols 0 to 1897 according to the PDS page).

- **Localization tables:**
  - `data_localizations/best_interp.csv` (8.68 MB). The last row is sol 1897.
  - `best_tactical.csv` (171 KB)
  - `telemetry.csv` (16.1 MB)
- **CSV columns (real header):** `frame, site, drive, pose, landing_x, landing_y, landing_z, northing, easting, planetocentric_latitude, planetodetic_latitude, longitude, elevation, map_pixel_line, map_pixel_sample, dem_pixel_line, dem_pixel_sample, roll, pitch, yaw, quat_s, quat_v1..v3, areoid, radius, sclk, sol`
- **`data_maps/m20_orbital_dem.img` (324.5 MB)** with a PDS4 label `m20_orbital_dem.xml`:
  - 14800 × 5480 px, IEEE754 MSB float32, behind a combined ODL3 + VICAR header (data starts at offset 118400).
  - Equirectangular, standard parallel 18.4663, sphere R = 3396.19 km, **1 m/px**.
  - Bounds: lon 77.2089 to 77.4722, lat 18.4158 to 18.5082; easting 4340890 to 4355690, northing 1091590 to 1097070.
  - **This is the same grid as the MMGIS easting/northing.** The CSV even includes `dem_pixel_line`/`dem_pixel_sample`.
  - The rover's whole traverse to date fits inside it (waypoint lon range 77.2179 to 77.4631, lat 18.4200 to 18.4997).
- **`data_maps/m20_orbital_map.img` (3.89 GB):** 3-band uint8, 59200 × 21920 px. That works out to 0.25 m/px; I inferred this from the pixel ratio.
- `data_orbital/orbital_N_metadata.csv`: per-site metadata.
- **This is the best single real-data backbone** for positions plus terrain in one coordinate frame. The PDS release lags: it ends at sol 1897, while MMGIS reaches sol 2022.

## 2. HiRISE DTMs over Jezero

### 2a. Single-pair DTM product from the HiRISE PDS (the classic `IMG` format)

- **Product:** `DTEEC_023524_1985_023379_1985_U01` ("Proposed Landing Site in Jezero Crater"), 1.00 m/post, center 18.3°N 77.53°E. Product page (DOC): https://www.uahirise.org/dtm/ESP_023524_1985
- **Files (HEAD, LIVE, all 200 with `Accept-Ranges: bytes`)** under `https://hirise-pds.lpl.arizona.edu/PDS/DTM/ESP/ORB_023500_023599/ESP_023524_1985_ESP_023379_1985/`:

| File | Size |
|---|---|
| `DTEEC_023524_1985_023379_1985_U01.IMG` | 667.8 MB |
| `ESP_023524_1985_RED_C_01_ORTHO.JP2` | 56.8 MB |
| `ESP_023524_1985_RED_A_01_ORTHO.JP2` | 730.1 MB |

### 2b. The same HiRISE DTMs as Cloud-Optimized GeoTIFFs (recommended)

- **STAC search (LIVE):** `POST https://stac.astrogeology.usgs.gov/api/search` with `{"collections":["mro_hirise_socet_dtms"],"bbox":[77.2,18.3,77.6,18.6]}` returned 6 DTMs, all about 1.015 m GSD:
  - `DTEEC_048842_1985_048908_1985_U01`: 158.1 MB COG
  - `DTEEC_045994_1985_046060_1985_U01`: 149.8 MB COG
  - `DTEEC_023524_1985_023379_1985_U01`: 273.4 MB COG
  - `DTEEC_023247_1985_022957_1985_U01`
  - `DTEEC_022680_1985_022746_1985_A01`
  - `DTEEC_002387_1985_003798_1985_A01`
- **Path pattern:** `https://astrogeo-ard.s3-us-west-2.amazonaws.com/mars/mro/hirise/controlled/dtm/<PAIR>/<DTEEC_id>.tif`
  - Each pair also has `_hillshade.tif`, `*_ORTHO.tif`, `DTFEC_*.tif` (figure of merit) and `provenance.txt`.
- **Verified for `DTEEC_023524_...`:** BigTIFF header containing `LAYOUT=IFDS_BEFORE_DATA`, so it is a real COG. CRS text is "Mars (2015) - Sphere / Ocentric / Equirectangular". Hillshade 212.2 MB; RED_C ortho 123.9 MB; RED_A ortho 1670.5 MB. `ACAO: *`.
- **Caveats:**
  - **None of these 6 DTMs covers the rover's current position** (lon 77.233). Their western edge is about lon 77.34. Use them for the delta and crater-floor demo areas.
  - A bbox-only search with no `collections` filter also returns lunar products (Kaguya, LOLA). Always pass `collections`.

### 2c. USGS Mars 2020 TRN mosaics — LIVE HEAD, all 200

Credit: Fergason et al. 2020, DOI 10.5066/P9REJ9JN, CC0.

| File | Size |
|---|---|
| `https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif` | **1754.3 MB** |
| `https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif` | **7017.6 MB** |
| `https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif` | **9.2 MB** |
| `https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif` | **34.6 MB** |

- The HiRISE DTM is also mirrored at `https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/...` (200, same size).
- **What I read from the raw TIFF tags (LIVE byte-range requests, 206):**
  - **HiRISE DTM:** 21400 × 21488 px, 1 m, float32, uncompressed, *striped (1 row per strip), not a COG*. Lon 77.2229 to 77.5840, lat 18.3068 to 18.6693.
    - 664 of the 708 waypoints fall inside it.
    - Sols around 1815 to 1856 went slightly west of it (lon about 77.218).
    - The current position (77.2332) is about 0.6 km inside the western edge.
  - **CTX DTM:** 1596 × 1512 px at 20 m. Lon 77.16 to 77.70, lat 18.21 to 18.72. GCS_Mars_2000_Sphere, true-scale latitude 0.
- **Mars Sample Return TRN mosaic (2025, DOI 10.5066/P13CPYYU, CC0):** extends west onto the crater rim; built from 8 HiRISE stereo pairs. Zip only, LIVE HEAD 200:
  - `https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/Mars/MSR_TRN_HiRISE_soc_003_USGS_release_aug2024/MSR_TRN_HiRISE_soc_003_USGS_release_aug2024_mosaics.zip`: **5214.8 MB**. Contains the 1 m DTM, the 1 m confidence map and the 0.25 m ortho mosaic; equirectangular, true-scale latitude 0 (per the readme, LIVE).
  - The `..._images.zip` is 12959.5 MB.

## 3. Global coarse fallback (USGS) — LIVE HEAD, 200

| File | Size |
|---|---|
| `https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif` | 2027.3 MB |
| `https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif` | 10857.1 MB |

- Both support HTTP Range requests, so GDAL `/vsicurl/` can read a Jezero window without downloading the whole file. That is acceptable for these, but slow because they are not COGs.
- **For the regional fallback, the 9.2 MB CTX 20 m DTM is far more practical** than either global file.

## 4. Python tooling on Windows (LIVE, PyPI JSON API)

- **rasterio 1.5.2** (released 2026-09-30, `requires_python >=3.12`) ships **win_amd64 wheels for cp312, cp313, cp314 and cp315**, about 29 to 30 MB each with GDAL bundled. **`pip install rasterio` works on Windows with Python 3.12 or 3.13 without a separate GDAL install.**
- **numpy 2.5.5:** win wheels for cp312 and up. **scikit-image 0.26.0:** cp311 to cp314.
- **No Windows wheels:** the PyPI `gdal` package (3.13.3) ships none, so avoid it and use rasterio's bundled GDAL. **rio-cogeo 7.0.4** is pure Python. I could not read the PyPI JSON for **pyproj** (empty response); unverified.
- **Likely to work, not tested locally:** reading `/vsicurl/` COGs in windows, and the GDAL PDS4/VICAR/PDS3 drivers for `m20_orbital_dem.xml` and `DTEEC_*.IMG`. As a fallback for the PLACES DEM, read it with `numpy.fromfile(offset=118400, dtype='>f4').reshape(5480,14800)`.
- **Coordinate systems:**
  - Everything is on the Mars 2000 / IAU sphere, R = 3396190 m, planetocentric, east-positive.
  - USGS products use equirectangular with true-scale latitude 0 (`Eqc_latTs0_lon0`).
  - MMGIS and PLACES use equirectangular with standard parallel 18.4663.
  - To convert between them, go through lon/lat; there are no EPSG codes. Use a proj4/WKT string such as `+proj=eqc +lat_ts=18.4663 +lon_0=0 +R=3396190 +units=m`, or IAU_2015 codes via pyproj.
  - At about 1 m/px, slope from `np.gradient` is straightforward.
  - **Elevation datums differ.** MMGIS `elev_geoid` and the PLACES `elevation` are relative to the areoid, while the USGS DTMs use "MOLAtopography_DeltaGeoid". Expect offsets of a few metres; align by sampling the DTM at the waypoints.

## 5. Navcam stereo products in PDS (LIVE)

- **Bundle:** `https://planetarydata.jpl.nasa.gov/img/data/mars2020/mars2020_navcam_ops_stereo/data/sol/<SOL>/ids/rdr/ncam/` (also `hazcam_ops_stereo`, `navcam_ops_mesh`, `mastcamz_ops_stereo`).
- **Product types on sol 658:**
  - XYZ (point cloud; 14.1 MB per frame)
  - RNG (range)
  - **SLP (slope; 4.7 MB per frame)**
  - RUF/RUS/RUC (roughness)
  - UVW (surface normals)
  - SHD, MXY, XYM/XYR, DSP/DFF/DSR, GRA/GRC/GRN, among others
- **Format:** PDS4 XML label with VICAR `.IMG`, in camera/site frames, not map-projected. They do give real local slope and heightmaps around the rover, but you must project them to a grid yourself (XYZ, site frame, PLACES pose).
- **Release lag:** on this host's directory listing, the bundles stop at **sol 658**. The PDS Imaging Node says Release 16 (sols 1740 to 1859) was published in Aug 2026, so newer sols are elsewhere or not indexed here. I did not resolve this.
- **Verdict:** stretch goal only.

## Recommendation for the Terrain & Navigation module

1. **Rover overlay:** use the MMGIS `M20_traverse.json` and `M20_waypoints.json`, fetched and cached by the backend (refresh daily, keyed on Last-Modified), with the PDS PLACES `best_interp.csv` as the stable archival source. Both are real, per sol, and in lon/lat.
2. **Terrain for cost maps:** the **PLACES `m20_orbital_dem.img`** (325 MB, 1 m, covers the whole traverse, in the same grid as the waypoints).
   - Preprocess once in Python into 256 or 512 px tiles: elevation, slope, and a cost raster. Ship tiles as PNG or float32 binaries, roughly tens of MB per crater-floor area.
   - Alternative: the USGS TRN HiRISE DTM (1.75 GB, CC0) or windowed COG reads of the individual `DTEEC` DTMs (150 to 270 MB each) for demo areas.
   - For the western rim beyond lon 77.209, use the MSR mosaic (5.2 GB zip).
3. **Context and fallback:** the CTX 20 m DTM (9.2 MB) and 6 m ortho (34.6 MB) for the whole-crater view; global MOLA 463 m only for zoomed-out display.
4. **Basemap imagery:** downsample the TRN 25 cm ortho (7 GB) or `m20_orbital_map.img` (3.9 GB) to tiles offline. Never ship them raw.

### Honest limitations

- **Resolution:** 1 m orbital posts miss rocks and sand ripples smaller than about 1 m, which are exactly what the rover's own hazard detection avoids. Cost maps will be plausible but not the real ops cost maps; those are not public.
- **Freshness:** MMGIS is about 3 weeks behind (sol 2022, last modified Oct 28). PDS PLACES lags by months (sol 1897).
- **Endpoint stability:** the MMGIS endpoint is undocumented and may move. The `science.nasa.gov` mirror did not respond, and `config.json` returns 403.
- **Two projections and vertical datums** must be reconciled; I documented the parameters above.
- **Download sizes** are large (0.3 to 7 GB). Do the processing offline in a one-time ingest script and do not commit the raw rasters.
- **Attribution:**
  - "NASA/JPL-Caltech" (MMGIS, PLACES, Navcam)
  - "NASA/JPL/University of Arizona" (HiRISE)
  - "USGS Astrogeology", CC0 (TRN/MSR mosaics, MOLA/HRSC blend)

Sources:
- https://www.uahirise.org/dtm/ESP_023524_1985
- https://stac.astrogeology.usgs.gov/docs/data/mars/hirise_dtms/
- https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-hirise-dtm-mosaic
- https://www.usgs.gov/data/mars-sample-return-hirise-mosaics-terrain-relative-navigation
- https://pds-geosciences.wustl.edu/missions/mars2020/places.htm
- https://pds-imaging.jpl.nasa.gov/
- https://an.rsl.wustl.edu/help/Content/Data%20releases.htm

---

## video-media

# Mars Explorer: research on Perseverance video and frame sequences (2026-11-16)

Legend: **[LIVE]** means I made a real HTTP request today and show the status and actual fields. **[DOC]** means I only found it documented.

---

## 1. NASA Image and Video Library API (images-api.nasa.gov)

**No API key is needed.** This is not api.nasa.gov, so the DEMO_KEY quotas don't apply. The API response says nothing about rate limits and I found none documented. Responses carry `Cache-Control: public, max-age=300` and `Access-Control-Allow-Origin: *`, sit behind CloudFront and only allow GET.

### Endpoints
| Endpoint | Status | Notes |
|---|---|---|
| `GET https://images-api.nasa.gov/search?q=perseverance&media_type=video` | **[LIVE] 200** | `collection.metadata.total_hits = 146`. Has a `collection.links[rel=next]` link to `&page=2`. |
| Search params: `q`, `media_type` (image\|video\|audio), `year_start`, `nasa_id`, `page`, `page_size` | **[LIVE]** | `page_size=5` returned 5 items. `q=perseverance landing descent&year_start=2021` returned 8 hits. `nasa_id=` returns exactly 1 item. Other documented params (`center`, `keywords`, `title`, `description`) are **[DOC]** in https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf (that PDF returned 200 today). |
| `GET https://images-api.nasa.gov/asset/{nasa_id}` | **[LIVE] 200** | Returns `collection.items[].href`: `~orig.mp4`, `~large.mp4`, `~medium.mp4`, `~mobile.mp4`, `~preview.mp4`, `~small.mp4`, `.srt` or `.vtt`, `metadata.json`, and keyframe JPGs `~thumb_1..5.jpg`, `~small_N`, `~medium_N`, `~large_N`. |
| `https://images-assets.nasa.gov/video/{nasa_id}/collection.json` (this is the `href` of each search item) | **[LIVE] 200** | A bare JSON array of the same asset URLs. |
| `GET https://images-api.nasa.gov/metadata/{nasa_id}` | **[LIVE] 200** | `{"location": ".../metadata.json"}`. That file holds EXIF/XMP data such as `QuickTime:Duration`, `QuickTime:ImageWidth/Height`, `QuickTime:VideoFrameRate`, `File:FileSize`, `AVAIL:Center`, `AVAIL:Title`. |
| `GET https://images-api.nasa.gov/captions/{nasa_id}` | **[LIVE] 200** | `{"location": ".../....srt"}` |

**Search item fields [LIVE]:** `items[].href` (the collection.json), `items[].data[0]` with `nasa_id`, `title`, `description`, `description_508`, `keywords[]`, `center`, `date_created`, `media_type`, `album[]` (for example `"Mars_2020_Perseverance"`), `location`, `photographer`, `secondary_creator`. Also `items[].links[]` with `href`, `rel` (preview\|alternate\|captions), `render`, `width`, `height`, `size`.

### Implementation gotchas (all verified live)
- **Asset hrefs come back as `http://`.** http answers with a 301 redirect to https, so rewrite them to `https://` yourself.
- **Not every video has every rendition.** "Ingenuity Third Flight MastcamZ Video" has no `~large.mp4`. Pick the best rendition from the asset list; never build the filename yourself.
- **`nasa_id` can contain spaces and Unicode.** Example: the U+2019 apostrophe in `Rover’s`. Percent-encode it with UTF-8 (`EscapeDataString` / `urllib.parse.quote`). A wrongly decoded id gave **403**; the correct encoding gave 200.
- **The JSON has no charset.** Content-Type is `application/json` with no charset, and PowerShell 5.1 decodes it as Latin-1, which garbles the text. Python `requests` `.json()` handles UTF-8 correctly.
- **MP4 headers.** A HEAD request on the mp4 gave `200 video/mp4` and `Accept-Ranges: bytes` but **no `Access-Control-Allow-Origin`**. A plain `<video src>` works; fetch/canvas pixel reads from JS would be blocked by CORS.

### Verified genuine Perseverance videos
| nasa_id | Content | Verified |
|---|---|---|
| `JPL-20210222-M2020f-0001-Perseverance Rover’s Descent and Touchdown on Mars` | **EDL onboard camera views** (the real landing video) | HEAD `~large.mp4`: 200, 135,524,266 B. `~mobile.mp4`: 9,052,641 B. metadata.json: 3840x2160, 30 fps, 0:03:25. Has `.srt`. |
| `JPL-20210425-TECHf-0001-Ingenuity Third Flight MastcamZ Video` | **Ingenuity flight 3 filmed by Mastcam-Z** (sol 64) | 200. 1280x720, 0:01:16. Renditions: orig/medium/mobile/preview/small. Credit in the description: "NASA/JPL-Caltech/ASU/MSSS". |
| `JPL-20210419-TECHf-0001-First Video of NASA’s Ingenuity Mars Helicopter in Flight` | Ingenuity flight 1 | Found in search [LIVE]. I did not fetch its assets. |
| `JPL-20210222-M2020f-0002-NASA’S Perseverance Rover’s First 360 View of Mars` | Navcam panorama video | Found in search [LIVE]. |
| `JPL-20210222-M2020f-0003a/b-M2020_Audio_*`, `JPL-20210506-Listen to NASA’s Ingenuity Helicopter…` | Real Mars audio with video | Found in search [LIVE]. |

Many of the 146 hits are explainers, animations or press clips, such as "Preparing to Land Perseverance" (testing on Earth) or launch videos. Curate an allowlist of `nasa_id`s; don't show search results unfiltered as "rover video".

---

## 2. Frame sequences in the raw-images feed (mars.nasa.gov)

**[LIVE] 200**:
```
https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&num=100&page=0&order=sol+desc
  &search=|NAVCAM_LEFT                       (instrument filter, pipe-prefixed)
  &condition_2=2024:sol:gte&condition_3=2024:sol:lte   (sol range)
  &extended=sample_type::full,               (accepted; returned Full only)
```
- **Top level:** `total_results` (579,518 unfiltered), `total_images` (1,055,868), `page`, `per_page`, `type` (`mars2020-images-list-1.1`), `images[]`.
- **Per image:** `imageid`, `sol`, `site`, `drive`, `sample_type` (Full\|Thumbnail…), `date_taken_utc`, `date_taken_mars` (`Sol-02024M12:32:11.849`), `date_received`, `caption`, `credit`, `title`, `link`, `json_link`, `attitude`.
  - `camera{instrument, filter_name, camera_model_type, camera_model_component_list, camera_position, camera_vector}`
  - `extended{sclk, mastAz, mastEl, dimension, subframeRect, scaleFactor, xyz}`
  - `image_files{small(_320.jpg), medium(_800.jpg), large(_1200.jpg), full_res(.png)}`
- **Response headers:** feed has `ACAO: *` and `Cache-Control: max-age=60`. Image files: HEAD gave 200, but `image/jpg`/`image/png` with **no ACAO**. That's fine for `<img>`; for canvas or encoding work, proxy them through the Python backend. I found no documented rate limit, so cache aggressively.
- **The feed is current.** The newest image is sol 2031 (2026-11-06).

### How to identify a "movie" sequence
**Captions are generic boilerplate and never contain "movie"**, and there is **no sequence_id field**. Parse `imageid` instead:

`NLG_2024_0846620206_694ECM_N0930000NCAM00518_00_2I3J`

Split on `_`. Segment [4] is `N` + site(3) + drive(4) + **sequence id** (9 characters, for example `NCAM00518`, `ZCAM08024`, `LVS_0`…).

To find a movie:
1. Group by (sol, instrument, sequence id).
2. Sort by `extended.sclk`.
3. **Keep only groups with constant `mastAz`/`mastEl`** (fixed pointing) and short, regular sclk gaps.

Varying pointing means it's a **mosaic**, not a movie. That's a real trap: sol 64 `ZCAM08024` has 64 frames, but it's a mosaic with 64 different az/el pairs.

### Verified sequences for frame-by-frame replay [LIVE]
| Sequence | Frames | Timing | Pointing | Verdict |
|---|---|---|---|---|
| **Sol 0, `LCAM` (Lander Vision System camera), seq `LVS_0…`** | **87** (`total_results=87`), 1024x1024 | sclk 666952774.1 → 666952960.9 (~187 s), gaps 1–3.4 s | Looks down during descent | **Best: a real EDL descent sequence.** First frame: `https://mars.nasa.gov/mars2020-raw-images/pub/ods/surface/sol/00000/ids/edr/browse/edl/ELM_0000_0666952774_666ECM_N0000001LVS_04000_0000LUJ00.png` (HEAD 200, 189 KB). **Caveat:** `date_taken_utc` says 2021-02-28, which is wrong (the landing was 2021-02-18). Order and time frames by `sclk`, not UTC. |
| **Sol 2024, NAVCAM_LEFT `NCAM00520`** | 21, 1280x960 | LMST 12:28:07 → 12:29:29 (~4 s cadence) | Fixed at az 95.41 / el 0.72 (horizon) | Fixed horizon movie, very likely a dust-devil watch (my inference, not stated in the caption). |
| Sol 2024, NAVCAM_LEFT `NCAM00518` | 8 | ~25 s cadence, 12:32 → 12:35 LMST | Fixed at az −90.49 / el 29.67 (sky) | Sky or cloud movie (inferred). |
| Sol 0, `EDL_DDCAM` | 2 on sol 0 (more on sols 627/636) | — | — | Too few frames on sol 0 to replay. |
| Sol 64, MCZ_RIGHT `ZCAM03117` / `ZCAM03118` | 24 each, over ~4 h | Alternates between 2 pointings | — | Repeated monitoring shots, not a movie. The Ingenuity flight 3 video frames themselves did **not** show up as an obvious fixed-pointing burst in the MCZ_RIGHT feed. Use the Image Library mp4 for that flight. |

---

## 3. Other official sources
- **NASA SVS** (`https://svs.gsfc.nasa.gov/api/search/?search=perseverance&limit=3`): **[LIVE] 200**, a stable JSON API. Fields: `count`, `next`, `results[]` with `id`, `url`, `result_type`, `release_date`, `title`, `description`. A detail lookup (`https://svs.gsfc.nasa.gov/api/4878`) returned `main_image`, `main_video` and `main_credits`. Only 22 hits, mostly Goddard content unrelated to Perseverance, so it's low value here.
- **JPL video pages** (`https://www.jpl.nasa.gov/videos/`) and the raw-images gallery page: **[LIVE] 200 HTML** only, with no public JSON API. Don't scrape them. The same JPL videos are in the Image Library under `JPL-*-M2020f-*` / `JPL-*-TECHf-*` nasa_ids.
- **PDS Imaging Node** (calibrated archives): **[DOC] only**, not checked today.

---

## 4. Media usage guidelines
Source: https://www.nasa.gov/nasa-brand-center/images-and-media/ (**[LIVE] 200**, text pulled from the page).
- NASA images, audio and video "generally are not subject to copyright in the United States". They may be used for educational or informational purposes, including Internet web pages and personal web pages.
- "NASA content used in a factual manner that does not imply endorsement may be used without needing explicit permission. NASA should be acknowledged as the source."
- The NASA insignia, logotype and identifiers are not in the public domain. Don't use the logo, the "meatball" or the worm, and don't style the app to look official.
- Third-party copyrighted items are marked as such. Commercial or promotional use featuring NASA logos or employees needs clearance.
- **Attribution in practice:** show each item's own credit string. The raw feed has a `credit` field, for example "NASA/JPL-Caltech/ASU" (Mastcam-Z) or "NASA/JPL-Caltech/LANL/CNES/IRAP" (SuperCam). Image Library descriptions end with "Credit: NASA/JPL-Caltech[/ASU/MSSS]". Add a footer disclaimer: "Not affiliated with or endorsed by NASA/JPL."

---

## Recommendations for the Mission Replay module

**A. Genuine video** (from the Image Library):
- Keep a curated allowlist of `nasa_id`s, starting with the EDL descent video, Ingenuity flight 3 by Mastcam-Z, the first Ingenuity flight video and the Mars audio clips.
- On the backend, call `/asset/{id}`, rewrite hrefs to https, and choose the rendition in this order: `~large` → `~medium` → `~mobile`.
- Serve it with `<video>` plus the `.srt`/`.vtt` track. Store `title`, `description`, `date_created` and the parsed credit.
- Label it "Official NASA/JPL video".

**B. Frame-sequence replay** (from the raw feed):
- The backend ingests by sol + instrument, parses the sequence id from `imageid`, and groups and sorts by `sclk`.
- Flag a group as a "movie" when it has at least 5 frames, a single (az, el) within about 0.01°, and an sclk gap under about 60 s.
- The frontend plays the `large` (1200 px) JPGs on a canvas or img flipbook, with real-time spacing taken from the sclk deltas.
- Label it "Reconstructed from raw images, not a NASA video".
- **Demo seeds:**
  - Sol 0 LCAM: 87 EDL frames, the hero example.
  - Sol 2024 `NCAM00520`: 21 Navcam frames at the horizon.
  - Sol 2024 `NCAM00518`: 8 sky frames.
- Raw images lack CORS headers, so proxy and cache them through the Python backend if the canvas needs pixel access or you export GIFs. Also cache the feed, since its `max-age` is 60 s and there's no documented rate limit.


---

## toolchain

# Toolchain research for Mars Explorer (checked 2026-11-16)

**How to read this:** **[LIVE]** means I queried it today with a real HTTP request (Invoke-RestMethod/WebRequest, HTTP 200). **[DOC]** means I only found it in documentation or search results and did not verify it live. Nothing was installed and nothing was written to the project folder.

## 1. Python

**Latest releases [LIVE]** (python.org API `/api/v2/downloads/release/`, all dated 2026-10-25):
- 3.15.2 (newest)
- 3.14.10
- 3.13.18
- 3.12.16

**Windows wheel coverage, latest version of each package [LIVE]** (PyPI JSON `https://pypi.org/pypi/<pkg>/json` and PEP 691 simple API):

| pkg | latest | requires_python | win_amd64 wheels |
|---|---|---|---|
| numpy | 2.5.5 (2026-11-15) | >=3.12 | cp312–cp315 |
| opencv-python | 5.0.0.93 | >=3.6 | cp37-abi3, so any version |
| scikit-image | 0.26.0 | >=3.11 | cp311–cp314; **cp315 only as 0.27.0rc1** |
| torch (PyPI) | 2.15.0 (2026-10-28) | >=3.11 | cp311–cp315 (+3.14t/3.15t), **CPU-only, ~121 MB** |
| torchvision | 0.29.2 | `!=3.14.1,>=3.10` | py3-none-win_amd64 |
| rasterio | 1.5.2 | >=3.12 | cp312–cp315 |
| shapely | 2.2.0 | >=3.11 | cp311–cp315 |
| pyproj | 3.8.0 | – | cp315 wheel present |
| fastapi | 0.163.1 (2026-11-15) | >=3.11 | pure-python |
| pydantic | 2.14.3 | >=3.10 | (v2 line) |
| uvicorn | 0.54.0 | >=3.10 | pure |
| sam2 (PyPI) | 1.1.0 (2024-12) | >=3.10 | stale |

**Recommendation: Python 3.13 (3.13.18).** It has stable wheels for every package above, and it is the lowest-risk choice for older ML repos such as SAM2 and AI4Mars training code. Python 3.14.10 also works today, but avoid 3.14.1 because torchvision excludes it. Avoid 3.15: scikit-image has no stable cp315 wheel yet.

**winget packages [LIVE]** (checked in the microsoft/winget-pkgs manifest folders):
- `Python.Python.3.13` (latest manifest 3.13.17)
- `Python.Python.3.14` (3.14.10)
- `Python.PythonInstallManager` (26.4.240.0), the new `py install` manager

You don't need either of these if you use uv.

**uv vs venv/pip: use uv.**
- uv 0.13.8 [LIVE]: GitHub release published 2026-11-12, PyPI `uv` 0.13.8, winget manifest `astral-sh.uv` 0.13.8.
- uv installs Python itself (`uv python install 3.13`), so the MS Store stub problem goes away.
- It has a lockfile (`uv.lock`) and is much faster with the 2 GB torch wheel.
- [DOC] uv supports `--torch-backend` / `[tool.uv.index]` pinning for PyTorch indexes.

```powershell
winget install --id astral-sh.uv -e
uv python install 3.13
uv init --python 3.13 backend; cd backend
uv add fastapi uvicorn pydantic numpy opencv-python scikit-image rasterio shapely pyproj anthropic
```

## 2. PyTorch on RTX 5070 (sm_120)

**What each CUDA index has [LIVE]** (from the `https://download.pytorch.org/whl/<cuXXX>/torch/` listings):
- **cu132**: torch **2.15.0**+cu132, win_amd64 for cp312–cp315 (+t). torchvision 0.29.2+cu132 is py3-none-win_amd64.
- **cu130**: newest is torch 2.14.1+cu130.
- **cu126**: newest is torch 2.14.1+cu126. **No Blackwell support** [DOC]: cu126 builds lack sm_120.
- **cu128 and cu129**: no torch 2.13–2.15 Windows wheels listed.
- **cu131**: HTTP 403.

**Wheel size [LIVE]:** `torch-2.15.0+cu132-cp313-cp313-win_amd64.whl` returned HEAD 200 with Content-Length about **2011 MB**. The cu130 2.14.1 wheel is about 1898 MB.

**Blackwell support [DOC]:** sm_120 has been supported in the CUDA 12.8+ builds since torch 2.7. CUDA 13.x needs an R580+ driver, and your driver 616.92 meets that. I did not run `torch.cuda.get_arch_list()` because nothing was installed. Verify after install with:

```powershell
uv run python -c "import torch;print(torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_capability(),torch.cuda.get_arch_list())"
```

Expect `(12, 0)` and `sm_120` in the arch list.

**Install command:**
```powershell
uv pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cu132
```

For a uv project, pin it in `pyproject.toml` instead:
```toml
[[tool.uv.index]]
name = "pytorch-cu132"
url = "https://download.pytorch.org/whl/cu132"
explicit = true
[tool.uv.sources]
torch = { index = "pytorch-cu132" }
torchvision = { index = "pytorch-cu132" }
```

**Risk:** a plain `pip install torch` pulls the CPU-only PyPI wheel without any error.

## 3. Node and frontend

**Node.js [LIVE]** (`https://nodejs.org/dist/index.json`):
- Active LTS is **v26.13.1 "Lithium"** (2026-11-10).
- v24.22.3 "Krypton" is the older LTS line.
- v27 is still alpha.
- winget manifest `OpenJS.NodeJS.LTS` is at 26.13.1.

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

**npm package versions [LIVE]** (`https://registry.npmjs.org/<pkg>/latest`):

| package | version |
|---|---|
| vite | **8.3.8** |
| @vitejs/plugin-react | 6.3.0 |
| react | **19.3.1** |
| typescript | **7.0.2** |
| three | **0.187.0** |
| @react-three/fiber | **9.8.2** (the R3F 9 line targets React 19) |
| @react-three/drei | 10.7.9 |
| ol (OpenLayers) | **10.11.0** |
| leaflet | 1.9.4 |
| deck.gl | 9.4.1 |
| proj4 | 2.23.0 |
| geotiff | 3.0.5 |
| @anthropic-ai/sdk | 1.8.0 |

**TypeScript 7 risk [DOC]:** TS 7 is the native-port compiler. Some plugins or tools may still expect the TS 5.x JS API. If tooling breaks, pin `typescript@5` for type-check plugins.

**Map library: use OpenLayers.**
- It handles arbitrary projections through `ol/proj` + `proj4.defs()` and `register(proj4)`. You can define a Mars equirectangular or Jezero local CRS (IAU_2015:49900 family) with a custom extent and no Earth assumptions.
- It reads Cloud Optimized GeoTIFFs directly with `ol/source/GeoTIFF` (built on geotiff.js) and supports `ImageStatic` for PNG plus bounds.
- Leaflet only supports custom CRS through the Proj4Leaflet plugin, and its 1.9.4 line has not changed in a long time.
- deck.gl is Web-Mercator/WGS84-centric. A non-geographic `OrthographicView` is possible, but there is no proper Mars CRS support.
- Use three.js / R3F separately for 3D terrain meshes from DEMs.

## 4. Git for Windows

**Versions [LIVE]:**
- Upstream GitHub release is **v2.56.1.windows.1** (2026-11-10).
- The winget manifest `Git.Git` is still at 2.56.0.4, so it lags slightly. Either is fine.

```powershell
winget install --id Git.Git -e --source winget
```

**Recommended installer options [DOC]** (standard Git for Windows choices):
- Default editor: VS Code (or another editor you already use).
- Initial branch name: `main`.
- PATH: "Git from the command line and also from 3rd-party software".
- HTTPS: Windows Secure Channel.
- Line endings: "Checkout Windows-style, commit Unix-style" (`core.autocrlf=true`), or add a `.gitattributes` with `* text=auto eol=lf`.
- Credential helper: Git Credential Manager.
- Enable symlinks.

## 5. Terrain segmentation models

**AI4Mars dataset [LIVE]** (Zenodo API `https://zenodo.org/api/records/15995036`):
- Title "AI4Mars: A Dataset for Terrain-Aware Autonomous Driving on Mars", version 0.6, DOI 10.5281/zenodo.15995036.
- **License: cc-by-4.0** (the NASA/data.gov catalog says the license is "not specified"; Zenodo is authoritative).
- Files:
  - `ai4mars-dataset-merged-0.6.zip`: 15.12 GiB, https://zenodo.org/api/records/15995036/files/ai4mars-dataset-merged-0.6.zip/content
  - `ai4mars-labels-unmerged.zip`: 1.46 GiB
- [DOC] Contents: about 35K images from Curiosity (NAVCAM), Opportunity and Spirit, and about 326K crowd labels. Classes are soil, bedrock, sand, big rock, plus null=255, stored as pixel values 0–3.
- There is **no Perseverance imagery** in the dataset, so expect a domain gap.
- Attribution: cite Swan et al., CVPRW 2021 (doi:10.1109/CVPRW53098.2021.00226).
- [LIVE] An unofficial Hugging Face mirror, `hassanjbara/AI4MARS`, is labeled cc0-1.0. Prefer Zenodo, and don't rely on the mirror's license.

**SAM variants [LIVE]:**
- `facebookresearch/sam2`: Apache-2.0, last push 2026-05. HF `facebook/sam2.1-hiera-large` is Apache-2.0, not gated, with an 856 MB checkpoint (`sam2.1_hiera_large.pt` / safetensors). `sam2.1-hiera-small` is also available.
- `facebookresearch/sam3`: actively maintained (last push 2026-11-13). The HF `facebook/sam3` model is **gated (manual approval), license "other"**.
- `segment-anything` (v1): Apache-2.0, last push 2024-09. The PyPI `segment-anything` package is still at 1.0 from 2023.
- **Prefer loading through `transformers`**: both HF SAM 2.1 models list the transformers library. The `sam2` repo's custom CUDA extension is fragile to build on Windows.

**Pretrained Mars terrain weights [LIVE]** (HF search for "ai4mars" / "mars segmentation"):
- Only toy or zero-download repos exist, e.g. `SaketR1/ai4mars` and `Mirali33/mars-bench-*` (crater/boulder/cone tasks, orbital).
- **I found no credible pretrained AI4Mars rover-terrain weights. Plan to fine-tune yourself.** A reasonable path is a SegFormer-B2 or DeepLabv3+ (torchvision / timm) on AI4Mars; [DOC] the paper reports more than 96% accuracy with DeepLabv3.

**Feasibility on 12 GB VRAM:**
- SAM 2.1 hiera-large image inference: about 3–5 GB in fp16/bf16. Fine.
- Fine-tuning SegFormer-B2/DeepLabv3+ at 512px: batch 8–16 with AMP. Fine.
- Fine-tuning SAM2-L fully is not practical; use the small/base model, or train only the decoder or a LoRA.
- Plan for about 40 GB of disk for the dataset (zip plus extracted).

## 6. ROS 2 / Gazebo on native Windows

**Verdict: use WSL2 (Ubuntu 26.04) or skip ROS entirely.**
- [DOC] ROS 2 **Lyrical Luth** (LTS, supported to May 2031) lists Windows 11 amd64 as Tier 1. It needs the VS2022 toolchain and is a painful native install.
- [DOC] **Gazebo Jetty** on Windows is "experimental" via conda-forge/Pixi, with known runtime issues: server and GUI can't run in one command.
- WSL2 with WSLg plus the NVIDIA GPU works for Gazebo.
- For a portfolio web app, a three.js rover sim is far cheaper. Treat ROS as optional and out of scope.

## 7. Anthropic Claude API (optional assistant)

**Packages [LIVE]:**
- Python package **`anthropic` 2.8.0** (PyPI, 2026-11-10, requires >=3.10).
- JS package `@anthropic-ai/sdk` 1.8.0.

**Usage pattern:**
```python
import anthropic
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY env var
msg = client.messages.create(model="claude-sonnet-5-5", max_tokens=16000,
        messages=[{"role":"user","content":"..."}])
print(msg.content[0].text)
```

**Model ids and pricing** (from the skill's model table, cached 2026-11-03; not verified live):

| model id | input $/1M tokens | output $/1M tokens |
|---|---|---|
| `claude-opus-5-5` | $4 | $20 |
| `claude-sonnet-5-5` | $2 | $10 |
| `claude-haiku-5-5` | $0.10 | $0.50 |

**API-level gotchas:**
- Use `thinking={"type":"adaptive"}`. `budget_tokens` and `thinking: disabled` return a 400 on the 5.5 models.
- Assistant prefill returns a 400.
- Opus 5.5's default effort is `medium`; set `output_config={"effort": ...}` explicitly.
- Check `stop_reason == "refusal"`.

**Cost and key handling:**
- A paid API key from platform.claude.com/console is required, billed per token. This is separate from any Claude.ai subscription.
- Keep the key server-side in FastAPI. Never ship it to the frontend.
- Haiku 5.5 is the cheap default for a chat assistant. Use prompt caching for the static mission-context system prompt.

## Key risks
1. A plain `pip install torch` installs the CPU build. Always use the cu132 index. The wheel is about 2 GB, so expect long installs and cache use.
2. CUDA indexes keep changing: cu128/cu129 Windows wheels are gone for current torch, and cu131 returns 403. Pin the exact version and index in `pyproject.toml`.
3. Python 3.15 is too new because scikit-image has no stable cp315 wheel. Avoid 3.14.1 for torchvision.
4. TypeScript 7 may break some ecosystem tooling.
5. The AI4Mars domain gap (Curiosity/MER, not Perseverance) and its 15 GB size. Attribution (cc-by-4.0 plus the paper citation) is required.
6. The SAM 3 weights are gated and under a non-Apache license. The `sam2` package's CUDA extension may not build on Windows, so prefer `transformers`.
7. The winget `Git.Git` manifest lags the upstream release (2.56.0.4 vs 2.56.1).
8. The MS Store `python.exe` stub can shadow the real interpreter. Disable it in Settings > Apps > Advanced app settings > App execution aliases, or rely on uv's managed Python.

## All install commands in one place
```powershell
winget install --id Git.Git -e --source winget
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
uv python install 3.13
# in backend project:
uv pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cu132
# frontend:
npm create vite@latest frontend -- --template react-ts
npm i three @react-three/fiber @react-three/drei ol proj4 geotiff
```

## Sources
- [AI4Mars on Zenodo](https://zenodo.org/records/15995036)
- [AI4Mars on data.nasa.gov](https://data.nasa.gov/dataset/ai4mars-a-dataset-for-terrain-aware-autonomous-driving-on-mars)
- [AI4Mars Hugging Face mirror](https://huggingface.co/datasets/hassanjbara/AI4MARS)
- [AI4Mars paper (CVPRW 2021)](https://mlanthology.org/cvprw/2021/swan2021cvprw-ai4mars)
- [ROS 2 Lyrical supported platforms](https://docs.ros.org/en/lyrical/Releases/lyrical/supported-platforms.html)
- [Gazebo getting started](https://gazebosim.org/docs/all/getstarted/)
- [Gazebo Jetty conda-forge packages](https://discourse.openrobotics.org/t/gazebo-jetty-conda-forge-packages-are-available/50596)
- [PyTorch get started](https://pytorch.org/get-started/locally/)
- Live endpoints queried: pypi.org JSON and simple API, download.pytorch.org/whl/*, nodejs.org/dist/index.json, registry.npmjs.org, python.org/api/v2, api.github.com (repos and microsoft/winget-pkgs manifests), zenodo.org/api, huggingface.co/api.
# data/ — local only

Everything in this folder except this README is **gitignored**. It is created by the ingestion
CLI (`cd backend; uv run mars-ingest seed`) and can be deleted at any time and rebuilt.

```
data/
├── mars.db                                   SQLite: image metadata, file cache index,
│                                             rover localizations, ingest runs, feed status
└── images/m2020/sol_<sol:05d>/<image_id>/
    ├── small.jpg                             NASA 320 px rendition
    ├── large.jpg                             NASA 1200 px rendition
    ├── full_res.png                          only with --full-res or when requested by the UI
    └── metadata.json                         the original NASA record, verbatim
terrain/m20_orbital_dem.img (+ .xml label)    PDS PLACES 1 m orbital DEM (324.5 MB)
derived/vision/<analysis>/*.png               perception overlay layers (cache)
derived/terrain/<map>/*.png                   terrain map layers (cache)
```

All images are raw, uncalibrated browse products from the NASA Mars 2020 raw-images feed.
Credit: NASA/JPL-Caltech (and ASU for Mastcam-Z). See each `metadata.json` for its `credit`.

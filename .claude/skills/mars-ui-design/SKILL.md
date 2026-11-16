---
name: mars-ui-design
description: Use when building or changing Mars Explorer frontend screens, panels, charts or design-system components (frontend/src/design-system, frontend/src/modules), or when reviewing the visual quality of the UI.
---

# Mars Explorer UI design

## Identity
Dark flight-operations console: restrained, precise, imagery-first. Not a generic dashboard.
- Tokens only (`design-system/tokens.css`); never hard-code colours in components.
- `--accent` (Mars oxide) sparingly: active nav, the single data series, key figures.
- `--signal` (cyan) **only** for selection and live/current state.
- Status colours (`--ok/--warn/--danger`) only for state, always with text.
- IBM Plex Sans for UI; IBM Plex Mono + tabular numbers for every number, id, coordinate.
- Section labels: 11px uppercase, letter-spacing .08em, `--text-2`.
- 1px borders, 2–4px radius, no drop shadows, no decorative gradients (image vignette only).
- 4px spacing grid; motion ≤150ms and disabled under `prefers-reduced-motion`.

## Integrity in the UI
- Every data object shows a `ProvenanceBadge`. Simulated = violet + dashed + hatched + the word
  SIMULATED (never colour-only).
- Missing → `—` (use `lib/format.ts`), never `0`.
- No invented telemetry (battery, power, temperatures). State limits next to the data.
- Planned modules show their scope honestly; never mock data that looks finished.

## Charts
- Load the `dataviz` skill first. Single series → no legend, title names it.
- 2px lines, recessive grid, ≥8px hover markers, crosshair + tooltip on hover.
- Equal axis scale for any map-like plot; say "schematic" when it is not a measured map.

## Layout & states
- Must work at 1440×900 and 1280×720 (panels scroll internally; no truncated values).
- Every async panel: skeleton → data | ErrorState (with retry / exact command) | EmptyState.

## Verify visually
Run backend + `npm run dev`, then screenshot with headless Edge and look at it:
```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu `
  --hide-scrollbars --user-data-dir=<scratch>\edge --window-size=1440,900 `
  --virtual-time-budget=10000 --screenshot=<scratch>\shot.png http://localhost:5173/
```
Use `Start-Process ... -Wait` with a separate `--user-data-dir`, or the screenshot may silently not
be written. Check 1280×720 too.

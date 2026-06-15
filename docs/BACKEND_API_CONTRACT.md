# Backend API Contract

## Scope

This document records the minimum JSON contract that the local Flask backend must
return for the LIBS rare-earth detection web app. The goal is to keep
`backend/pipeline.py` and `web_app/app.js` aligned while the research scripts are
being converted into Ubuntu-safe, side-effect-free backend logic.

The Flask route layer must not directly import these research scripts:

- `research/legacy_algorithms/Elements_detectation.py`
- `research/legacy_algorithms/Wavelet_peakfinding.py`
- `research/legacy_algorithms/Identification_Matrix.py`
- `MultiPeakfit/Gaussfit.py`

They can be used as algorithm references only. Backend payloads should come from
clean functions under `backend/` or from service-safe logic inside
`backend/pipeline.py`.

## Top-Level Response

`POST /api/pipeline/run` returns:

| Field | Type | Notes |
| --- | --- | --- |
| `filename` | string | Uploaded filename or selected local sample name. |
| `stages` | array | Six ordered stage objects. |
| `result_csv` | string | CSV text with `element,detected,confidence`. |
| `notes` | array | Short backend implementation notes. |

The stage order is fixed:

```text
raw -> peak -> match -> temperature -> fit -> result
```

Each stage object must include:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | One of the six fixed stage ids. |
| `title` | string | Display title used by the UI. |
| `status` | string | Usually `done` for current synchronous runs. |
| `summary` | string | Human-readable summary for the stage strip. |
| `data` | object | Stage-specific structured payload. |
| `parameters` | object | Optional algorithm/config details. |

## Stage Data

### `raw`

Minimum `data` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `filename` | string | Source name. |
| `point_count` | number | Parsed valid wavelength-intensity rows. |
| `x_min` | number | Minimum wavelength. |
| `x_max` | number | Maximum wavelength. |
| `y_min` | number | Raw minimum intensity. |
| `y_max` | number | Raw maximum intensity. |
| `preview` | array | Downsampled points, each `{x, y}`. |

### `peak`

Minimum `data` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `peak_count` | number | Total detected candidate peaks. |
| `peaks` | array | Up to 80 peak objects. |

Each peak should include `wavelength`, `intensity`, `index`, and `prominence`.

Minimum `parameters` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `method` | string | Detection method, such as CWT ridge or fallback find_peaks. |
| `max_peaks` | number | Current UI/API cap. |
| `pywt_available` | boolean | Whether PyWavelets was available. |

### `match`

Minimum `data` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `base_candidates` | array | Ranked matrix/base element candidates. |
| `matrix_elements` | array | Elements used for rare-earth line conflict filtering. |
| `spectral_matches` | array | Rare-earth line matches for plotting and tables. |
| `rare_earth_distances` | object | Distance summary keyed by rare-earth element. |
| `confidence_calculation` | object | Ion-level confidence / intensity-comb payload for drawing and numeric probes. |

Each `spectral_matches` item should include:

| Field | Type | Notes |
| --- | --- | --- |
| `element` | string | Base rare-earth element, such as `Yb`. |
| `ion` | string | Ion label, such as `YbII`. |
| `wavelength` | number | Theoretical wavelength. |
| `status` | string | `enabled`, `blocked`, or `review`. |
| `delta_nm` | number | Absolute theory/experiment wavelength delta. |
| `matched_peak` | object | Experimental peak `{wavelength, intensity}`. |
| `confidence` | number | Element confidence used for ranking. |
| `reason` | string | Short explanation. |

`confidence_calculation` exposes the numerical payload needed to explain the
confidence calculation and to draw the intensity-comb views. It must preserve
the existing `spectral_matches`, `rare_earth_distances`, `base_candidates`, and
`result_csv` compatibility fields.

Minimum `confidence_calculation` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `formula` | object | Human/debug-readable formula notes for theoretical comb generation, Hungarian assignment, Euclidean distance, Boltzmann fit, and exponential mapping. |
| `temperature_gate` | object | Gate used by confidence and representative selection; currently `5000 <= T <= 20000 K`. |
| `scope_nm` | number | Rare-earth matching tolerance, currently `0.2`. |
| `total_count` | number | Total ion items considered before any payload cap. |
| `omitted_count` | number | Count omitted by payload cap; currently `0` because all rare-earth ions are returned. |
| `parity_gap` | array | Known algorithm parity gaps recorded but not changed in this slice. |
| `items` | array | Ion-level comb and confidence rows. |

Each `confidence_calculation.items` row includes:

| Field | Type | Notes |
| --- | --- | --- |
| `element` | string | Base element, such as `Yb`. |
| `ion` | string | Ion label, such as `YbII`. |
| `confidence` | number | Ion-level confidence from the documented distance/T/R2 gate. |
| `element_confidence` | number | Existing element-level confidence used by result ranking. |
| `distance` | number | Euclidean distance between matched normalized theoretical and experimental combs. |
| `temperature` | number | Boltzmann-fit temperature from matched experimental intensities. |
| `r2` | number | Boltzmann-fit R2. |
| `line_count` | number | Count of globally assigned matched experimental peaks. |
| `all_theoretical_comb` | array | All line-switch-enabled theoretical comb teeth for the ion. |
| `matched_theoretical_comb` | array | Matched theoretical comb after missing teeth are removed and the remaining teeth are renormalized. |
| `matched_experimental_comb` | array | Matched experimental comb paired to `matched_theoretical_comb` and renormalized independently. |
| `raw_peak_marks` | object | Plot marks for the original spectrum + theory-line + selected-peak explanation view. |
| `normalization` | object | Explicit sums and bases used for all/matched theoretical and matched experimental normalization. |
| `representative_selection` | object | Whether this ion represents its element, plus `valid_temperature`, `best_r2`, and a short reason. |

Each `all_theoretical_comb` row includes:

```text
wavelength, intensity, normalized_intensity, A, E, g, enabled, status, matched, review
```

`status` is `enabled` for teeth with a selected experimental peak and `review`
for currently unmatched theoretical teeth. The line-switch-filtered library has
already removed disabled/conflicting lines before this payload is built.

Each `matched_theoretical_comb` row includes:

```text
wavelength, intensity, normalized_intensity, matched_idx, A, E, g
```

Each `matched_experimental_comb` row includes:

```text
wavelength, intensity, normalized_intensity, delta_nm, matched_idx, theoretical_wavelength
```

For matched combs, non-empty `normalized_intensity` values should sum to about
`1`; empty matched arrays have normalized sum `0`. Missing theoretical comb
teeth are not kept as zero entries in `matched_theoretical_comb`; they remain
visible in `all_theoretical_comb` with `status=review`.

`raw_peak_marks` must include:

| Field | Type | Notes |
| --- | --- | --- |
| `theoretical_wavelengths` | array | Light-blue theory-line positions for the original-spectrum explanation view. |
| `selected_experimental_peaks` | array | Red selected experimental peaks with `wavelength`, `intensity`, `theoretical_wavelength`, and `delta_nm`. |
| `spectrum_source` | string | Notes that the black raw spectrum line comes from the raw stage preview/full parsed spectrum. |

Current known matching parity gap:

```text
backend cost = abs(delta_nm) - 0.03 * experimental_intensity
original reference default = alpha * abs(delta_nm) - beta * experimental_intensity, alpha=1.0, beta=1.0
```

This contract records the gap in `confidence_calculation.parity_gap`; it does
not change the matching weight.

### `temperature`

This stage must preserve the multi-start T-iteration payload.

Minimum `data` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `trace` | array | Trace for the selected/best start. |
| `starts` | array | All start trajectories. |
| `best_start_index` | number | Index of the globally selected start. |
| `best_score` | number | Best score across all starts. |
| `temperature` | number | Final selected electron temperature. |

Each `starts` item should include:

| Field | Type |
| --- | --- |
| `start_index` | number |
| `initial_temperature` | number |
| `final_temperature` | number |
| `best_score` | number |
| `best_candidate` | string |
| `best_confidence` | number |
| `best_r2` | number |
| `selected` | boolean |
| `trace` | array |

Each trace item should include:

| Field | Type |
| --- | --- |
| `iteration` | number |
| `temperature` | number |
| `target_temperature` | number |
| `candidate` | string |
| `confidence` | number |
| `r2` | number |
| `score` | number |
| `delta` | number |

### `fit`

Minimum fields returned by `backend/pipeline.py`:

| Field | Type | Notes |
| --- | --- | --- |
| `target` | string or null | Ion selected for local fitting. |
| `target_element` | string or null | Rare-earth element selected for fitting. |
| `requested_fit_target` | object or null | Optional user/API-requested fit target, normalized for echo/debugging. |
| `window_nm` | array or null | Local fitting window `[left, right]`. |
| `fit_candidates` | array | Ordered fitted component candidates: target rare-earth line followed by up to two strongest local matrix lines. |
| `components` | array | Current compact Gaussian component summary. |
| `rms` | number or null | Local fit RMS. |
| `before_confidence` | number | Confidence before fit boost. |
| `after_confidence` | number | Fit-stage diagnostic confidence only; final result must not directly boost from this value. |
| `raw_points` | array | Real local spectrum points `{x, y}` from the fit window. |
| `component_curves` | array | Gaussian component curves sampled by the backend. |
| `sum_fit_points` | array | Backend-sampled Gaussian sum fit points. |
| `fitted_peaks` | array | Fitted peak markers from fitted parameters. |
| `local_extrema` | array | Real local maxima from the local spectrum window. |
| `residual_points` | array | `raw - sum_fit` residual points. |
| `baseline` | number or null | Fitted or fallback local baseline. |
| `component_count` | number | Number of fitted components. |
| `fallback_reason` | string or null | Explanation when fitting or payload generation is incomplete. |
| `real_multipeak_fit` | boolean | Whether curve fitting succeeded. |
| `parity_gap` | array | Known fit-stage parity caveats for this sample, if any. |
| `confidence_rescue` | object | Final-result rescue diagnostics from fitted-peak append + confidence recompute. |

The frontend must not silently synthesize a full multi-peak fitting plot from
only `components`. `web_app/app.js` should draw backend-provided `raw_points`,
`component_curves`, `sum_fit_points`, `fitted_peaks`, `fit_candidates`, and
`local_extrema`.

Each `fit_candidates` item includes:

```text
source, element, label, center, line_intensity, line_type, rank
```

For the validated RRE sample, the expected normal overlap structure is:

```text
target rare-earth candidate + up to two matrix candidates
```

When `real_multipeak_fit` is true, `component_count`,
`component_curves.length`, and `fitted_peaks.length` should match
`fit_candidates.length`, and their centers should align in order.

Each `component_curves` item includes compact component parameters plus `points`:

```text
source, element, label, rank, center, amplitude, sigma, points
```

Each `fitted_peaks` item includes:

```text
label, wavelength, intensity, amplitude, sigma
```

`confidence_rescue` records whether fitted peaks affected final detection:

| Field | Type | Notes |
| --- | --- | --- |
| `applied` | boolean | True only when final results used recomputed rescue confidence. |
| `reason` | string | Example: `coarse_confidence_not_zero`, `no_fit_target`, or `fitted_peak_append_recompute`. |
| `target_element` | string or null | Rare-earth element considered for rescue. |
| `base_confidence` | number | Confidence before fitted-peak rescue. |
| `recomputed_confidence` | number or null | Confidence after appending target fitted peaks and recomputing. |
| `appended_peak_count` | number | Count of target fitted peaks appended for recompute. |
| `appended_peaks` | array | Appended fitted peak summaries. |

### `result`

Minimum `data` fields:

| Field | Type | Notes |
| --- | --- | --- |
| `rare_earth_results` | array | Ordered rare-earth confidence results. |
| `detection_threshold` | number | Threshold used for `detected`. |

Each rare-earth result should include `element`, `detected`, `confidence`,
`temperature`, `r2`, and `matched`.

## Local Development Guarantees

- `GET /api/samples` must include `RREs/070101_95.csv`.
- The browser page opened from `file://` must still call
  `http://127.0.0.1:5000/api/...` through `resolveApiUrl()`.
- Backend CORS must keep local `file://` and local static-page development usable.
- Flask job storage is currently in memory; restarting Flask invalidates old job
  ids and old CSV download links.

## Baseline Verification

Run these commands after backend contract changes:

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
```

For samples where no rare-earth fit target is expected, keep the field contract
strict but allow empty plot payload rows:

```bash
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

Run a focused sample probe:

```bash
python3 - <<'PY'
from pathlib import Path
from backend.pipeline import run_pipeline

path = Path('RREs/070101_95.csv')
result = run_pipeline(path.read_text(encoding='utf-8', errors='ignore'), path.name)
print([stage['id'] for stage in result['stages']])
print(sorted(next(stage for stage in result['stages'] if stage['id'] == 'temperature')['data'].keys()))
print(sorted(next(stage for stage in result['stages'] if stage['id'] == 'fit')['data'].keys()))
PY
```

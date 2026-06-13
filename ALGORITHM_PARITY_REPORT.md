# Algorithm Parity Report

## Summary

- overall_status: partial
- highest_risk_stage: peak / matching numeric parity and result rescue fixture coverage
- samples_tested:
  - `RREs/070101_95.csv`
  - `Broaden_research/PureSample_Spectrum/Fe1.asc`

This audit was read-only for implementation code. No backend or frontend code was changed.

The current Web backend is not just the old fixed `0.9 nm` + `curve_fit` wrapper at runtime: `backend/pipeline.py` delegates fit work to `backend/multipeak_fit.py`, which includes dynamic minima windows, CWT FWHM estimation, fixed-center Gaussian components, ratio candidates, and `L-BFGS-B`.

However, the backend still cannot be called fully algorithm-parity complete. Several stages are service-safe rewrites with source-level similarity but missing numeric equivalence tests against side-effect-free extractions of the original scripts. The earlier direct fit confidence boost in `_final_results()` has been replaced with a `confidence_rescue` path: fitted target peaks are appended only for original-style zero-confidence rescue, then confidence is recomputed through the existing matching/confidence function. This removes the direct boost shortcut, but still needs dedicated fixtures for zero-confidence rescue cases and broader peak/matching numeric parity tests.

## User Correction: Multi-Element Fit Candidate Set

The original multi-peak fitting behavior is more specific than "fit the selected rare-earth peak":

- In `Elements_detectation.py:1431`, the original code builds `lines_in_window` from **all current rock/matrix main elements** (`elements_rockmain`) whose line wavelengths fall inside the extracted local window.
- In `Elements_detectation.py:1455`, it selects the top two strongest matrix lines with `lines_in_window.nlargest(2, "LineIntensity")`.
- In `Elements_detectation.py:1542-1543`, it builds `manual_peak_wl = [target rare-earth wavelength] + strongest_lines`.
- Therefore the intended multi-peak component set is normally **three candidate centers** when two strong matrix overlap lines exist: one target rare-earth line plus two strongest matrix lines in that local window.
- This is what makes the plot a true overlapping / multi-element fit. A plot with only one target rare-earth Gaussian, or with matrix components that are not derived from the top two strongest local matrix lines, is not faithful to the original method.

The Web backend currently has a related helper, `backend/multipeak_fit.py:351`, that reads matrix line centers and returns `limit=2`; `backend/multipeak_fit.py:457-465` then appends those two candidates to the target candidate. That is close to the source rule, but the next implementation slice should make this explicit and testable:

- expose the exact selected fit centers in the fit payload: target rare-earth center plus the two strongest matrix centers, including `source`, `element`, `line_type`, `line_intensity`, and `rank`;
- assert that when two matrix lines exist in the window, `component_count == 3` and the three fitted component curves are drawn;
- add an element/fit-target option so the user can choose which rare-earth element/line is being fit, rather than only fitting the backend's automatically selected highest-confidence target;
- preserve original line-source modes: `coarse_matched` and `normalized_pure_element`, because original `MultiPeakFit()` can fit different target elements in the rescue flow.

## Implementation Handoff: Candidate Payload Slice, 2026-06-04

This slice implemented only the multi-peak fit candidate payload and minimal fit-target selection API. It did not change the front-end visual effects and did not implement the original rescue + recompute-confidence workflow.

Validated sample: `RREs/070101_95.csv`.

- Fit window: `[274.298, 275.253]` nm.
- Target candidate: `source=normalized_pure_element`, `element=Yb`, `label=YbII`, `center=275.0477`, `line_intensity=0.069972`, `line_type=Rareearth_pt3 relative intensity`, `rank=0`.
- Top two matrix candidates from `RockBaseElemLines/Linespectrum` inside the fit window:
  - `source=matrix`, `element=Mn`, `label=MnII`, `center=275.0125`, `line_intensity=608.3`, `line_type=Mn II (8.9e-1)`, `rank=1`.
  - `source=matrix`, `element=Mn`, `label=MnII`, `center=274.8702`, `line_intensity=135.1`, `line_type=Mn II (8.9e-1)`, `rank=2`.
- Two matrix lines were found, so the expected component count is target + matrix candidates = `3`.
- Verified alignment: `component_count=3`, `fit_candidate_count=3`, `component_curves=3`, `fitted_peaks=3`, and component centers were `[275.0477, 275.0125, 274.8702]`, matching `fit_candidates` order.
- Minimal target selection support now accepts `fit_target`, plus alias fields `fit_target_element`, `fit_target_ion`, `fit_target_wavelength`, and `fit_target_source`. A pipeline self-test covers a requested `coarse_matched` target source for `YbII 328.937 nm`.
- Non-rare-earth sample `Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit` remains an explicit empty fit with `fallback_reason=no_enabled_matched_peak`.

Remaining gaps:

- Original `Elements_detectation.py:1945` rescue behavior is still not complete: fitted peak candidates are not appended into the peak list and rare-earth confidence is not recomputed from those fitted candidates.
- The Web UI still does not expose a full interactive fit-target picker; this slice only added backend/API payload support.
- Numeric equivalence against a side-effect-free extraction of the original `Elements_detectation.py` + `MultiPeakfit/Gaussfit.py` path is still unverified.

## Stage Matrix

| Stage | Original Reference | Web Module | Parity Status | Evidence | Remaining Risk |
| --- | --- | --- | --- | --- | --- |
| Raw spectrum parsing | `Elements_detectation.py:771` loads first two columns with pandas and passes raw `intensity_sum` into peak detection and matching. | `backend/spectrum.py:41` parses first two numeric columns, sorts by wavelength, drops duplicate wavelengths, returns raw `y` plus `y_normalized`; `backend/pipeline.py:520` uses normalized intensity for peak detection and downstream peak intensity. | needs_parity_test | Focused probe used full parsed arrays, not preview. `raw.preview` is only emitted in stage payload. | Sorting/deduping are defensible IO cleanup, but subtract-min/range normalization is not a pure scale transform when baseline is nonzero. It can alter peak ratios, Boltzmann slope inputs, and fit amplitudes versus the original raw-intensity path. Need a regression test comparing raw versus normalized peak lists and confidence values. |
| Peak detection | `Wavelet_peakfinding.py:146` uses `pywt.cwt(..., "mexh")`, scales `1..10`, `neighbor=4`, `min_length=3`, fixed `coeffi_threshold=700` in main flow (`Elements_detectation.py:1751`). | `backend/pipeline.py:462` uses CWT ridge detection with scales `1..10`, neighbor `4`, min length `3`; fallback to `scipy.signal.find_peaks` only if CWT fails. | needs_parity_fix_or_justification | Required probes reported `peak_method CWT ridge peak detection`; RRE peak count `77`, Fe peak count `80`. `pywt` is installed (`1.8.0`). | Backend uses a dynamic percentile/energy threshold, not the original fixed `coeffi_threshold=700`. Because backend also runs on normalized intensity, this may be an intended adaptation, but it is not proven equivalent. Need a side-effect-free original CWT probe and peak-position diff test. |
| Line database and line switch | `Elements_Combfact.py:39`, `:151` calculate Boltzmann relative intensity, use every second row, convert Angstrom to nm and cm^-1 to eV, and apply line-switch/conflict logic. | `backend/line_database.py:50`, `:71`, `:89`, `:145` implement conflict parsing, relative intensity, cached CSV load, Angstrom-to-nm and cm^-1-to-eV conversion. | source_parity_partial | Line probe loaded `Elements_database@10000`: `28` ions / `226` lines. `Rareearth_pt3@10431.75 line_switch`: `21` ions / `143` lines; `include_matrix`: `21` ions / `159` lines. Sample rows for `FeI`, `SiI`, `YbII` showed converted nm/eV values. | The formula and row-selection logic match the source structure, but this audit did not run a row-by-row pandas-vs-backend diff for every ion. Need a fixture test for several ions and both line-switch modes. |
| Matching, Boltzmann, confidence | `Elements_detectation.py:355` uses Hungarian weighted matching with `cost = alpha*diff - beta*exp_intensity`; `:450` computes normalized vector distance, Boltzmann T/R2, and `exp(-4.5*distance/R2)` confidence. | `backend/pipeline.py:123` implements Hungarian matching, `:82` Boltzmann fit, `:171` confidence aggregation. | needs_parity_test | Formula-level overlap exists: Hungarian assignment, vector normalization, Euclidean distance, Boltzmann `ln(I*wl/(g*A))`, and `exp(-4.5*distance/R2)` are present. | Backend matching cost uses `diff - 0.03*experimental_intensity`, not original default `diff - 1.0*experimental_intensity`. This may compensate for normalized intensity, but it is a formula change. Backend also uses the selected temperature iteration payload for matrix candidates rather than recomputing base confidence at final `db_temperature` with `scope=0.2` as in `Elements_detectation.py:1776`. |
| Temperature iteration | Original functions: `_candidate_score()` and `_pick_target_temperature()` at `Elements_detectation.py:828`; `T_iteration_single()` / `T_iteration()` at `:855` and `:964`; main call at `:1757` uses `max_iterations=12`, `tolerance=1e-5`, `candidate_mode="alterable"`, `t_min=5000`, `t_max=20000`, `multistart_count=10`, `alpha=0.35`, `top_k=3`. | `backend/pipeline.py:268`, `:272`, `:290`, `:382` implement score, Top-K softmax target temperature, damping, multi-start, and selected start payload. | runtime_parity_for_selection | Focused probe: RRE starts `10`, selected count `1`, `best_start_index=2`, `best_score=0.9837`, max start score `0.9837`; Fe starts `10`, selected count `1`, `best_start_index=2`, `best_score=-0.0413`, max start score `-0.0413`. Parameters in code match the original main call. | Selection rule is validated: selected start is the global highest score. Remaining gap: original recomputes CWT peaks inside each iteration from raw signal; backend reuses a precomputed normalized peak list. Need a test proving this does not change T iteration outputs. |
| Multi-peak fitting | `MultiPeakfit/Gaussfit.py:28` CWT FWHM estimator; `:181` fixed-mu Gaussian sum; `:240` ratio candidates; `:301` `L-BFGS-B`; `Elements_detectation.py:1231` `MultiPeakFit()` builds matrix-overlap candidates; `:1431` searches all matrix lines in the local window; `:1455` selects the two strongest matrix lines; `:1542` builds target rare-earth line plus those matrix lines; `:1578` calls CWT FWHM + `GaussMultiPeakFitter`. | `backend/multipeak_fit.py:64` dynamic minima window; `:111` CWT FWHM estimator; `:190` fixed-center fitter; `:247` ratio candidates; `:262` `L-BFGS-B`; `:351` matrix line centers with `limit=2`; `:564` service-safe fit summary. | candidate_payload_slice_done | RRE focused probe: window `[274.298, 275.253]`; `fit_candidates` were target `YbII 275.0477` plus matrix `MnII 275.0125` and `MnII 274.8702`; `component_count=3`, `component_curves=3`, `fitted_peaks=3`, centers aligned in candidate order, `fallback_reason=None`, `real_multipeak_fit=True`. | Candidate payload and minimal fit-target API are now explicit for the validated sample. Remaining risk is not this candidate set slice; it is rescue + recompute confidence, broader fixture coverage, and no full UI target picker. |
| Final result | `Elements_detectation.py:1945` appends fitted peak candidates and recomputes rare-earth confidence after multi-peak rescue. | `backend/pipeline.py` now builds `fit.data.confidence_rescue`; `_final_results()` only applies recomputed rescue confidence when `confidence_rescue.applied=True`, and no longer uses `after_confidence` as a direct boost. | service_safe_partial | Focused probe on `RREs/070101_95.csv`: fit `before_confidence=0.0779`, `after_confidence=0.2706`, `confidence_rescue.reason=coarse_confidence_not_zero`, final Yb confidence `0.0779`. Fe sample remains `未检出`. | Direct boost is removed, but a dedicated fixture is still needed where a rare earth has coarse confidence `<=0.01`, fitted target peaks are appended, and recomputed confidence changes the final decision. |

## Simplification Findings

| Severity | Location | Simplification | Why It Matters | Required Fix |
| --- | --- | --- | --- | --- |
| Medium | `backend/pipeline.py:_fit_confidence_rescue` and `_final_results()` | The direct `after_confidence` boost has been removed. The backend now appends target fitted peaks and recomputes confidence only for zero-confidence rescue, but no zero-confidence rescue fixture has locked the exact numeric behavior yet. | The current RRE fixture verifies non-rescue behavior, not the original rescue branch where fitted peaks should change confidence. | Add a fixed fixture or synthetic focused probe where `coarse_confidence <= 0.01`, fitted target peaks are appended, and recomputed confidence is compared against the expected matching/confidence path. |
| Resolved for this slice | `Elements_detectation.py:1431`, `:1455`, `:1542`; `backend/multipeak_fit.py:351`, `:503`, `:564`; `backend/contract_probe.py:111` | The original fit candidate set is target rare-earth line plus the two strongest matrix lines in the local window. The backend now exposes this as `fit_candidates` and validates component/curve/fitted-peak center alignment. | The visible Gaussian components can now be traced back to concrete candidate lines instead of only visual appearance. | Keep the regression probe. Future work should use the same candidate payload when implementing fitted-peak rescue and recomputed confidence. |
| High | `backend/pipeline.py:123` | Weighted Hungarian cost uses `diff - 0.03 * experimental_intensity`; original default weighted matcher uses `alpha*diff - beta*exp_intensity` with beta default `1.0`. | Candidate matching can change, especially when multiple peaks fall within tolerance. That changes distance, temperature, confidence, and fit target. | Add a unit fixture with known theory/experiment peaks that compares backend assignment against a side-effect-free extraction of `match_spectral_lines_weighted()`. If `0.03` is intentional because intensity is normalized, record the derived equivalence and lock it in a test. |
| High | `backend/pipeline.py:462` | CWT ridge threshold is dynamic percentile-based; original main flow uses fixed `coeffi_threshold=700` with raw signal. | Peak set is the input to every later stage. Small peak-list differences can cascade through matching and final detection. | Add an original-style CWT function without top-level file reads, run peak-position diffs for `RREs/070101_95.csv` and `Fe1.asc`, and choose whether to restore fixed-threshold behavior or explicitly parameterize normalized-threshold behavior. |
| Medium | `backend/spectrum.py:60` and `backend/pipeline.py:520` | Backend sorts/dedupes and uses subtract-min/range-normalized intensity for algorithmic peak intensity. | Sorting is fine if original data are sorted; dedupe can remove real repeated wavelengths. Normalization with baseline subtraction is not equivalent to raw intensity for Boltzmann and fit unless proven. | Add a regression probe that reports `y_min/y_max`, repeated wavelength count, raw-vs-normalized peak list, and confidence delta. If normalization is only for display, use raw intensity in algorithm stages. |
| Medium | `backend/pipeline.py:890` | Backend uses temperature-iteration selected payload for base candidates. Original main flow recomputes base element confidence at final `db_temperature` after T iteration. | The selected payload may correspond to the pre-update temperature of the last iteration, not exactly the final `db_temperature`. Matrix elements can change, affecting line switch and fit candidates. | After selecting final temperature, reload matrix database at that temperature and recompute base confidence with the original main-flow scope. Add a test that catches matrix element changes. |
| Medium | `backend/pipeline.py:686` | `_fit_summary()` returns immediately to `backend.multipeak_fit`, but old fixed `0.9 nm` + `curve_fit` implementation remains below the return as unreachable code. | Current runtime path is safe, but the dead block is a maintenance hazard: future edits may revive the simplified implementation accidentally. | Remove the unreachable block in a separate cleanup slice after adding a regression test that asserts no `curve_fit` path is used for fit stage. |
| Low | `backend/line_database.py:89` | Loader appears formula-compatible, but no full row-by-row parity diff was run against `Elements_Combfact.py`. | A header/encoding/odd-even row mismatch can silently change line candidates. | Add deterministic fixtures for `FeI`, `SiI`, `YbII` covering default, line-switch, and include-matrix modes. |

## Numeric Probes

Required commands:

```text
node web_app/app.js
exit 0, no output

python3 -m compileall -q backend
exit 0, no output

python3 backend/pipeline.py
exit 0, no output
```

Contract probe, RRE sample:

```text
python3 -m backend.contract_probe RREs/070101_95.csv
contract ok
stage_ids: raw, peak, match, temperature, fit, result
temperature: starts=10, selected_count=1, best_score=0.9837, temperature=10431.75
fit: target=YbII, raw_points=97, component_curves=3, sum_fit_points=97,
     fitted_peaks=3, local_extrema=1, fallback_reason=null
confidence_rescue: applied=false, reason=coarse_confidence_not_zero,
     base_confidence=0.0779, recomputed_confidence=null
result Yb confidence: 0.0779
result_summary: Yb
```

Contract probe, Fe sample:

```text
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
contract ok
stage_ids: raw, peak, match, temperature, fit, result
temperature: starts=10, selected_count=1, best_score=-0.0413, temperature=20000.0
fit: target=null, raw_points=0, component_curves=0, sum_fit_points=0,
     fitted_peaks=0, local_extrema=0, fallback_reason=no_enabled_matched_peak
result_summary: 未检出
```

Focused probe:

```text
SAMPLE RREs/070101_95.csv
stage_ids ['raw', 'peak', 'match', 'temperature', 'fit', 'result']
peak_count 77
peak_method CWT ridge peak detection
temperature_starts 10
selected_count 1
best_start_index 2
best_score 0.9837
max_start_score 0.9837
start_scores [
  (0, 5000.0, 10410.12, 0.9835, False),
  (1, 6666.67, 10420.94, 0.9831, False),
  (2, 8333.33, 10431.75, 0.9837, True),
  (3, 10000.0, 10442.65, 0.9833, False),
  (4, 11666.67, 10453.62, 0.9698, False),
  (5, 13333.33, 10464.22, 0.9694, False),
  (6, 15000.0, 10474.62, 0.969, False),
  (7, 16666.67, 10484.91, 0.9686, False),
  (8, 18333.33, 10495.12, 0.9682, False),
  (9, 20000.0, 10505.27, 0.9678, False)
]
fit_window_nm [274.298, 275.253]
fit_component_count 3
fit_counts {'raw_points': 97, 'component_curves': 3, 'sum_fit_points': 97, 'fitted_peaks': 3, 'local_extrema': 1}
fit_target YbII
fallback_reason None
real_multipeak_fit True
result_summary Yb
detected [('Yb', 0.2706)]
```

```text
SAMPLE Broaden_research/PureSample_Spectrum/Fe1.asc
stage_ids ['raw', 'peak', 'match', 'temperature', 'fit', 'result']
peak_count 80
peak_method CWT ridge peak detection
temperature_starts 10
selected_count 1
best_start_index 2
best_score -0.0413
max_start_score -0.0413
fit_window_nm None
fit_component_count 0
fit_counts {'raw_points': 0, 'component_curves': 0, 'sum_fit_points': 0, 'fitted_peaks': 0, 'local_extrema': 0}
fit_target None
fallback_reason no_enabled_matched_peak
real_multipeak_fit False
result_summary 未检出
detected []
```

Line database probe:

```text
Elements_database@10000 ions 28 lines 226
Rareearth_pt3@10431.75 line_switch Yb matrix ions 21 lines 143
Rareearth_pt3@10431.75 include_matrix ions 21 lines 159
```

Bad import probe:

```text
backend/app.py bad_imports []
backend/contract_probe.py bad_imports []
backend/line_database.py bad_imports []
backend/multipeak_fit.py bad_imports []
backend/pipeline.py bad_imports []
backend/samples.py bad_imports []
backend/spectrum.py bad_imports []
```

## Regression Tests Added Or Needed

Added in this audit:

- No code tests were added. This window intentionally did not modify backend or frontend implementation.

Already present and run:

- `node web_app/app.js`
- `python3 -m compileall -q backend`
- `python3 backend/pipeline.py`
- `python3 -m backend.contract_probe RREs/070101_95.csv`
- `python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit`

Needed next:

- Peak parity test: side-effect-free original `wavelet_peak_detection()` versus backend `detect_peaks()` on `RREs/070101_95.csv` and `Fe1.asc`, reporting count and first 20 wavelength deltas.
- Matching parity test: original `match_spectral_lines_weighted()` cost behavior versus backend `_match_spectral_lines_weighted()`, including ambiguous overlapping peaks.
- Line database parity test: pandas original loader versus `backend.line_database.load_line_database()` for `FeI`, `SiI`, `YbII`, default / line-switch / include-matrix modes.
- Temperature parity test: verify final selected start is highest score, and verify base candidates after final-temperature recomputation match the original main flow.
- Multi-peak parity test: assert dynamic window is used, `ratio_candidates` are evaluated, `L-BFGS-B` is used, component count includes target plus matrix overlap candidates, and no fixed `curve_fit` path can be selected.
- Final-result parity test: replace or guard fit confidence boost with original-style fitted-peak append and confidence recomputation, then lock final detection results on fixed fixtures.

## Prompt For Next Implementation Window

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。本窗口只做“多峰拟合候选集合与元素选择”的最小修复 slice，不要改前端特效，不要重构无关阶段。

背景重点：
用户指出原代码的多峰拟合不是只拟合一个稀土峰。参考 Elements_detectation.py：
- 1431 行附近：在局部拟合窗口内，从所有 elements_rockmain 的 RockBaseElemLines/Linespectrum 谱线中筛选 lines_in_window。
- 1455 行附近：用 lines_in_window.nlargest(2, "LineIntensity") 取窗口内强度最高的两条基体谱线。
- 1542-1543 行附近：manual_peak_wl = [目标稀土谱线 wl_value] + strongest_lines。
所以正常有两条强基体线时，Gaussian components 应该是三条绿线：目标稀土线 + 两条最强基体重叠线。这才是原方法意义上的多元素/重叠峰拟合。

当前要求：
1. 先读 ALGORITHM_PARITY_REPORT.md 的 “User Correction: Multi-Element Fit Candidate Set”。
2. 不要直接 import Elements_detectation.py 或 MultiPeakfit/Gaussfit.py 到 Flask。
3. 在 backend/multipeak_fit.py 中保留服务化实现，但明确输出 fit_candidates：
   - target rare-earth candidate；
   - local window 内 LineIntensity 最高的最多两条 matrix candidates；
   - 每条 candidate 包含 source、element、label、center、line_intensity、line_type、rank。
4. component_curves/fitted_peaks 必须与 fit_candidates 对齐；如果窗口里确有两条 matrix candidates，component_count 应为 3。
5. 增加一个元素/拟合目标选项：允许前端或 API 指定要拟合的 rare-earth element/ion/line，不能只自动选择最高 confidence target。先做最小 API/payload 支持即可，前端复杂 UI 可以后置。
6. 保留原 source modes 的语义：coarse_matched 与 normalized_pure_element，至少在 payload 中能看出 candidate 来自哪里。
7. 加回归测试或 probe，打印 target candidate、top two matrix candidates、component_count、fit window、component centers；不要用“图看起来像”作为一致性证据。

必须验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

完成后更新 ALGORITHM_PARITY_REPORT.md 或新增一个小 handoff，说明：
- 实际选中的三类 candidate；
- 是否有两条 matrix lines；
- component_count 是否等于 target + matrix candidates；
- 仍未完成的 rescue + recompute confidence 工作。
```

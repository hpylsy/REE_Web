from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.signal import argrelextrema


FIT_WINDOW_FALLBACK_HALF_WIDTH_NM = 0.9
ROCK_LINE_DIR = Path("RockBaseElemLines") / "Linespectrum"


def _points_payload(x_values, y_values, x_key="x", y_key="y", max_points=900):
    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(y_values, dtype=float)
    if x_arr.size == 0 or y_arr.size == 0:
        return []

    size = min(x_arr.size, y_arr.size)
    x_arr = x_arr[:size]
    y_arr = y_arr[:size]
    if size > max_points:
        idx = np.linspace(0, size - 1, max_points).astype(int)
        x_arr = x_arr[idx]
        y_arr = y_arr[idx]

    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    return [
        {
            x_key: round(float(x_value), 6),
            y_key: round(float(y_value), 6),
        }
        for x_value, y_value in zip(x_arr[valid], y_arr[valid])
    ]


def _local_extrema_payload(x_values, y_values, limit=18):
    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(y_values, dtype=float)
    if x_arr.size < 3 or y_arr.size < 3:
        return []

    size = min(x_arr.size, y_arr.size)
    extrema = []
    for idx in range(1, size - 1):
        y_value = y_arr[idx]
        if not math.isfinite(float(y_value)):
            continue
        if y_value > y_arr[idx - 1] and y_value > y_arr[idx + 1]:
            extrema.append(
                {
                    "wavelength": round(float(x_arr[idx]), 6),
                    "intensity": round(float(y_value), 6),
                }
            )

    extrema.sort(key=lambda row: (-row["intensity"], row["wavelength"]))
    return sorted(extrema[:limit], key=lambda row: row["wavelength"])


def extract_spectrum_between_minima(x_values, y_values, center_wavelength, ratio=1.0):
    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(y_values, dtype=float)
    valid = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[valid]
    y_arr = y_arr[valid]
    if x_arr.size < 3:
        return x_arr, y_arr, None, None

    order = np.argsort(x_arr)
    x_arr = x_arr[order]
    y_arr = y_arr[order]

    center = float(center_wavelength)
    local_minima = np.where((y_arr[1:-1] <= y_arr[:-2]) & (y_arr[1:-1] <= y_arr[2:]))[0] + 1
    if local_minima.size == 0:
        return x_arr, y_arr, float(x_arr[0]), float(x_arr[-1])

    left_candidates = local_minima[x_arr[local_minima] < center]
    right_candidates = local_minima[x_arr[local_minima] > center]
    peak_left_idx = int(left_candidates[-1]) if left_candidates.size else 0
    peak_right_idx = int(right_candidates[0]) if right_candidates.size else x_arr.size - 1
    if peak_left_idx > peak_right_idx:
        peak_left_idx, peak_right_idx = peak_right_idx, peak_left_idx

    peak_region = np.arange(peak_left_idx, peak_right_idx + 1)
    peak_idx = int(peak_region[np.argmax(y_arr[peak_region])])
    valley_limit = float(y_arr[peak_idx]) * float(ratio)

    left_idx = 0
    for idx in left_candidates[::-1]:
        if y_arr[idx] <= valley_limit:
            left_idx = int(idx)
            break

    right_idx = x_arr.size - 1
    for idx in right_candidates:
        if y_arr[idx] <= valley_limit:
            right_idx = int(idx)
            break

    if left_idx > right_idx:
        left_idx, right_idx = right_idx, left_idx

    return x_arr[left_idx : right_idx + 1], y_arr[left_idx : right_idx + 1], float(x_arr[left_idx]), float(x_arr[right_idx])


class CWTPeakFWHMEstimator:
    def __init__(self, wavelength, intensity, scale=0.48, threshold=0.01):
        self.wavelength = np.asarray(wavelength, dtype=float)
        self.intensity = np.asarray(intensity, dtype=float)
        self.scale = float(scale)
        self.threshold = float(threshold)

    @staticmethod
    def mexican_hat_wavelet(points, scale):
        amplitude = 2 / (np.sqrt(3 * scale) * (np.pi**0.25))
        scale_square = scale**2
        x_values = np.linspace(-points // 2, points // 2, points)
        return amplitude * (1 - x_values**2 / scale_square) * np.exp(-(x_values**2) / (2 * scale_square))

    def cwt_second_derivative(self):
        points = min(200, self.intensity.size)
        if points < 3:
            points = 3
        if points % 2 == 0:
            points -= 1
        wavelet = self.mexican_hat_wavelet(points, self.scale)
        return np.convolve(self.intensity, wavelet, mode="same")

    def find_peaks_from_second_derivative(self, cwt_data):
        minima = argrelextrema(np.asarray(cwt_data, dtype=float), np.less)[0]
        if minima.size == 0:
            return minima
        min_value = float(np.min(cwt_data))
        if min_value == 0:
            return minima
        selected = [idx for idx in minima if abs(float(cwt_data[idx])) > self.threshold * abs(min_value)]
        return np.asarray(selected, dtype=int)

    @staticmethod
    def remove_edge_artifacts(cwt_data, minima_indices):
        maxima_indices = argrelextrema(np.asarray(cwt_data, dtype=float), np.greater)[0]
        valid_minima = []
        for idx, minimum in enumerate(np.asarray(minima_indices, dtype=int)):
            has_left = np.any(maxima_indices < minimum)
            has_right = np.any(maxima_indices > minimum)
            if idx == 0 and not has_left:
                continue
            if idx == len(minima_indices) - 1 and not has_right:
                continue
            valid_minima.append(int(minimum))
        return np.asarray(valid_minima, dtype=int)

    @staticmethod
    def estimate_fwhm(cwt_data, peak_indices, wavelength):
        cwt_arr = np.asarray(cwt_data, dtype=float)
        wavelength_arr = np.asarray(wavelength, dtype=float)
        size = min(cwt_arr.size, wavelength_arr.size)
        if size == 0:
            return np.array([], dtype=float)

        cwt_arr = cwt_arr[:size]
        wavelength_arr = wavelength_arr[:size]
        peak_indices = np.asarray(peak_indices, dtype=int)
        peak_indices = peak_indices[(peak_indices >= 0) & (peak_indices < size)]

        fwhm_values = []
        for idx in peak_indices:
            left = int(idx)
            while left > 1 and cwt_arr[left - 1] > cwt_arr[left]:
                left -= 1
            right = int(idx)
            while right < size - 2 and cwt_arr[right + 1] > cwt_arr[right]:
                right += 1
            fwhm_values.append(0.7 * abs(float(wavelength_arr[right] - wavelength_arr[left])))
        return np.asarray(fwhm_values, dtype=float)

    def cwt_peak_detection(self):
        cwt_data = self.cwt_second_derivative()
        peaks = self.find_peaks_from_second_derivative(cwt_data)
        peaks = self.remove_edge_artifacts(cwt_data, peaks)
        fwhm = self.estimate_fwhm(cwt_data, peaks, self.wavelength)
        return peaks, fwhm, cwt_data


class FixedCenterGaussianFitter:
    def __init__(self, wavelength, intensity, centers, fwhm_selected, selected_idx):
        self.wavelength = np.asarray(wavelength, dtype=float)
        self.intensity = np.asarray(intensity, dtype=float)
        self.centers = np.asarray(centers, dtype=float)
        self.fwhm_selected = np.asarray(fwhm_selected, dtype=float)
        self.selected_idx = np.asarray(selected_idx, dtype=int)
        self.fitted_params = []
        self.component_fits = []
        self.total_fit = np.zeros_like(self.wavelength, dtype=float)
        self.best_ratio = None
        self.rms = None

    @staticmethod
    def gaussian(x_values, amplitude, center, sigma):
        return float(amplitude) * np.exp(-0.5 * ((x_values - float(center)) / max(abs(float(sigma)), 1e-6)) ** 2)

    def gaussian_sum_fixed_mu(self, x_values, amplitudes, sigmas):
        total = np.zeros_like(x_values, dtype=float)
        for amplitude, center, sigma in zip(amplitudes, self.centers, sigmas):
            total += self.gaussian(x_values, amplitude, center, sigma)
        return total

    def fit(self):
        x_full = self.wavelength
        y_full = self.intensity
        if x_full.size < 3 or self.centers.size == 0:
            return self

        order = np.argsort(x_full)
        peak_height_upper = np.interp(self.centers, x_full[order], y_full[order])
        valid_peak = np.isfinite(self.centers) & np.isfinite(peak_height_upper)
        self.centers = self.centers[valid_peak]
        peak_height_upper = peak_height_upper[valid_peak]
        if self.centers.size == 0:
            return self

        x_span = float(np.nanmax(x_full) - np.nanmin(x_full))
        sigma_min = max(x_span / (len(x_full) * 10.0), 1e-4)
        sigma_max = 0.12
        if sigma_max <= sigma_min:
            sigma_max = sigma_min * 10.0

        amp_upper = np.maximum(peak_height_upper, 1e-8)
        amp_init = amp_upper * 0.8
        sigma_default = max(x_span / (8.0 * max(self.centers.size, 1)), sigma_min)
        if self.fwhm_selected.size == self.centers.size:
            sigma_init = np.clip(self.fwhm_selected / 2.35482, sigma_min, sigma_max)
        else:
            sigma_init = np.full(self.centers.size, sigma_default, dtype=float)

        initial = np.concatenate([amp_init, sigma_init])
        bounds = [(0.0, float(value)) for value in amp_upper] + [(sigma_min, sigma_max)] * self.centers.size

        best_solution = None
        best_rms = np.inf
        best_ratio = None
        for ratio in np.arange(0.0, 1.0001, 0.05):
            fit_mask = self._ratio_fit_mask(ratio)
            x_fit = x_full[fit_mask]
            y_fit = y_full[fit_mask]
            if x_fit.size < 3:
                x_fit = x_full
                y_fit = y_full

            def objective(params):
                count = self.centers.size
                amplitudes = params[:count]
                sigmas = params[count:]
                predicted = self.gaussian_sum_fixed_mu(x_fit, amplitudes, sigmas)
                return float(np.sqrt(np.mean((y_fit - predicted) ** 2)))

            result = minimize(
                objective,
                x0=initial,
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": 20000, "ftol": 1e-12},
            )
            if not result.success:
                continue

            count = self.centers.size
            predicted_full = self.gaussian_sum_fixed_mu(x_full, result.x[:count], result.x[count:])
            full_rms = float(np.sqrt(np.mean((y_full - predicted_full) ** 2)))
            if full_rms < best_rms:
                best_rms = full_rms
                best_solution = result.x.copy()
                best_ratio = float(ratio)

        if best_solution is None:
            return self

        count = self.centers.size
        amplitudes = best_solution[:count]
        sigmas = best_solution[count:]
        self.fitted_params = []
        self.component_fits = []
        self.total_fit = np.zeros_like(x_full, dtype=float)
        for amplitude, center, sigma in zip(amplitudes, self.centers, sigmas):
            self.fitted_params.append((float(amplitude), float(center), float(sigma)))
            component = self.gaussian(x_full, amplitude, center, sigma)
            self.component_fits.append(component)
            self.total_fit += component
        self.best_ratio = best_ratio
        self.rms = best_rms
        return self

    def _ratio_fit_mask(self, ratio):
        if self.fwhm_selected.size != self.centers.size or self.selected_idx.size != self.centers.size:
            return np.ones_like(self.wavelength, dtype=bool)

        valid_idx = self.selected_idx[(self.selected_idx >= 0) & (self.selected_idx < self.wavelength.size)]
        if valid_idx.size != self.centers.size:
            return np.ones_like(self.wavelength, dtype=bool)

        peak_order = np.argsort(self.wavelength[valid_idx])
        ordered_idx = valid_idx[peak_order]
        ordered_fwhm = self.fwhm_selected[peak_order]
        left_mu = float(self.wavelength[ordered_idx[0]])
        right_mu = float(self.wavelength[ordered_idx[-1]])
        left_fwhm = float(ordered_fwhm[0])
        right_fwhm = float(ordered_fwhm[-1])
        if left_mu > right_mu:
            left_mu, right_mu = right_mu, left_mu
            left_fwhm, right_fwhm = right_fwhm, left_fwhm
        return (self.wavelength >= left_mu - ratio * left_fwhm) & (self.wavelength <= right_mu + ratio * right_fwhm)


def _read_rock_line_rows(path):
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"):
        try:
            with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
                return list(csv.reader(handle))
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.reader(handle))


def _first_numeric(values):
    for index, value in values:
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return index, number
    return None, None


def _rock_line_file(rock_line_dir, element):
    base = str(element).strip()
    candidates = [base, base.upper(), base.lower(), base.capitalize()]
    for candidate in candidates:
        path = rock_line_dir / f"{candidate}.csv"
        if path.is_file():
            return path
    return None


def _matrix_line_centers(root_dir, matrix_elements, left_nm, right_nm, limit=2):
    root = Path(root_dir) if root_dir is not None else Path.cwd()
    rock_line_dir = root / ROCK_LINE_DIR
    rows = []
    for element in matrix_elements or []:
        path = _rock_line_file(rock_line_dir, element)
        if path is None:
            continue
        csv_rows = _read_rock_line_rows(path)
        if not csv_rows:
            continue
        header = csv_rows[0]
        for row in csv_rows[1:]:
            try:
                wavelength = float(str(row[0]).strip())
            except (IndexError, TypeError, ValueError):
                continue
            if not (left_nm <= wavelength <= right_nm):
                continue
            column_index, intensity = _first_numeric(enumerate(row[1:4], start=1))
            if intensity is None:
                continue
            line_type = str(header[column_index]).strip() if column_index is not None and column_index < len(header) else ""
            label = str(element)
            if column_index is not None and column_index < len(header):
                label = header[column_index].split("(")[0].replace(" ", "")
            rows.append(
                {
                    "source": "matrix",
                    "element": str(element).strip(),
                    "label": label,
                    "center": float(wavelength),
                    "line_intensity": float(intensity),
                    "line_type": line_type or label,
                }
            )

    rows.sort(key=lambda row: (-row["line_intensity"], row["center"], row["label"]))
    return rows[:limit]


def _dedupe_candidates(candidates, min_separation_nm=0.01):
    deduped = []
    removed = []
    for row in candidates:
        center = float(row["center"])
        if any(abs(center - float(existing["center"])) < min_separation_nm for existing in deduped):
            removed.append(row)
            continue
        deduped.append(row)
    return deduped, removed


def _normalize_identifier(value):
    return str(value or "").strip().replace(" ", "").upper()


def _as_finite_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _jsonable_fit_target(fit_target):
    if not fit_target:
        return None
    if not isinstance(fit_target, dict):
        return {"value": str(fit_target)}
    result = {}
    for key in ("element", "ion", "wavelength", "source"):
        if key in fit_target and fit_target[key] is not None:
            result[key] = fit_target[key]
    return result


def _target_source(fit_target, default="normalized_pure_element"):
    if isinstance(fit_target, dict):
        source = str(fit_target.get("source") or "").strip()
        if source:
            return source
    return default


def _select_target_match(matches, fit_target=None):
    matched = [row for row in matches if row.get("matched_peak")]
    if fit_target:
        request = fit_target if isinstance(fit_target, dict) else {"element": str(fit_target)}
        requested_element = _normalize_identifier(request.get("element"))
        requested_ion = _normalize_identifier(request.get("ion"))
        requested_wavelength = _as_finite_float(request.get("wavelength"))

        candidates = []
        for row in matched:
            if requested_element and _normalize_identifier(row.get("element")) != requested_element:
                continue
            if requested_ion and _normalize_identifier(row.get("ion")) != requested_ion:
                continue
            wavelength = _as_finite_float(row.get("wavelength"))
            wavelength_delta = abs(wavelength - requested_wavelength) if wavelength is not None and requested_wavelength is not None else 0.0
            if requested_wavelength is not None and wavelength_delta > 0.05:
                continue
            candidates.append((wavelength_delta, row))

        if not candidates and requested_wavelength is not None:
            relaxed = []
            for row in matched:
                if requested_element and _normalize_identifier(row.get("element")) != requested_element:
                    continue
                if requested_ion and _normalize_identifier(row.get("ion")) != requested_ion:
                    continue
                wavelength = _as_finite_float(row.get("wavelength"))
                if wavelength is None:
                    continue
                relaxed.append((abs(wavelength - requested_wavelength), row))
            candidates = [item for item in relaxed if item[0] <= 0.25]

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0],
                0 if item[1].get("status") == "enabled" else 1,
                -float(item[1].get("confidence", 0.0)),
                -float(item[1].get("matched_peak", {}).get("intensity", 0.0)),
            )
        )
        return candidates[0][1]

    enabled = [row for row in matched if row.get("status") == "enabled"]
    return max(enabled, key=lambda row: (row.get("confidence", 0.0), row["matched_peak"]["intensity"]), default=None)


def _target_candidate(target, fit_target=None):
    line_intensity = _as_finite_float(target.get("line_intensity"))
    if line_intensity is None:
        line_intensity = float(target["matched_peak"]["intensity"])
    return {
        "source": _target_source(fit_target),
        "element": target["element"],
        "label": target["ion"],
        "center": round(float(target.get("wavelength") or target["matched_peak"]["wavelength"]), 4),
        "line_intensity": round(float(line_intensity), 6),
        "line_type": str(target.get("line_type") or "rare_earth_theoretical"),
        "rank": 0,
        "matched_peak_wavelength": round(float(target["matched_peak"]["wavelength"]), 4),
        "matched_peak_intensity": round(float(target["matched_peak"]["intensity"]), 6),
    }


def _fit_candidates(target, matrix_elements, left_nm, right_nm, root_dir=None, fit_target=None):
    candidates = [_target_candidate(target, fit_target=fit_target)]
    matrix_rows = _matrix_line_centers(root_dir, matrix_elements, float(left_nm), float(right_nm), limit=2)
    for rank, row in enumerate(matrix_rows, start=1):
        candidates.append(
            {
                "source": row["source"],
                "element": row["element"],
                "label": row["label"],
                "center": round(float(row["center"]), 4),
                "line_intensity": round(float(row["line_intensity"]), 6),
                "line_type": row["line_type"],
                "rank": rank,
            }
        )
    candidates, removed = _dedupe_candidates(candidates)
    parity_gap = []
    if len(matrix_rows) < 2:
        parity_gap.append(f"matrix_candidates_found={len(matrix_rows)}")
    if removed:
        parity_gap.append(f"deduped_candidate_count={len(removed)}")
    return candidates, parity_gap


def _fallback_window(x_values, y_values, center):
    x_arr = np.asarray(x_values, dtype=float)
    y_arr = np.asarray(y_values, dtype=float)
    mask = (x_arr >= center - FIT_WINDOW_FALLBACK_HALF_WIDTH_NM) & (x_arr <= center + FIT_WINDOW_FALLBACK_HALF_WIDTH_NM)
    return (
        x_arr[mask],
        y_arr[mask],
        float(center - FIT_WINDOW_FALLBACK_HALF_WIDTH_NM),
        float(center + FIT_WINDOW_FALLBACK_HALF_WIDTH_NM),
    )


def _empty_fit(reason):
    return {
        "target": None,
        "target_element": None,
        "requested_fit_target": None,
        "window_nm": None,
        "fit_candidates": [],
        "components": [],
        "rms": None,
        "before_confidence": 0.0,
        "after_confidence": 0.0,
        "real_multipeak_fit": False,
        "raw_points": [],
        "component_curves": [],
        "sum_fit_points": [],
        "fitted_peaks": [],
        "local_extrema": [],
        "residual_points": [],
        "baseline": None,
        "component_count": 0,
        "fallback_reason": reason,
        "parity_gap": [],
    }


def fit_summary(spectrum, matches, matrix_elements=(), root_dir=None, fit_target=None):
    target = _select_target_match(matches, fit_target=fit_target)
    if target is None:
        result = _empty_fit("fit_target_not_found" if fit_target else "no_enabled_matched_peak")
        result["requested_fit_target"] = _jsonable_fit_target(fit_target)
        return result

    x_values = np.asarray(spectrum["x"], dtype=float)
    y_values = np.asarray(spectrum["y_normalized"], dtype=float)
    theoretical_center = float(target.get("wavelength") or target["matched_peak"]["wavelength"])
    experimental_center = float(target["matched_peak"]["wavelength"])

    x_fit, y_fit, left_nm, right_nm = extract_spectrum_between_minima(x_values, y_values, theoretical_center, ratio=1.0)
    fallback_reason = None
    if x_fit.size < 8 or left_nm is None or right_nm is None:
        x_fit, y_fit, left_nm, right_nm = _fallback_window(x_values, y_values, experimental_center)
        fallback_reason = "minima_window_fallback"
    if x_fit.size < 8:
        candidates, parity_gap = _fit_candidates(target, matrix_elements, float(left_nm), float(right_nm), root_dir=root_dir, fit_target=fit_target)
        result = _empty_fit("insufficient_fit_window_points")
        result.update(
            {
                "target": target["ion"],
                "target_element": target["element"],
                "requested_fit_target": _jsonable_fit_target(fit_target),
                "window_nm": [round(float(left_nm), 3), round(float(right_nm), 3)],
                "fit_candidates": candidates,
                "before_confidence": round(float(target.get("confidence", 0.0)), 4),
                "fallback_reason": "insufficient_fit_window_points",
                "parity_gap": parity_gap,
            }
        )
        return result

    baseline = float(np.percentile(y_fit, 10))
    fit_y = np.maximum(y_fit - baseline, 0.0)
    fit_candidates, parity_gap = _fit_candidates(target, matrix_elements, float(left_nm), float(right_nm), root_dir=root_dir, fit_target=fit_target)
    centers = np.asarray([row["center"] for row in fit_candidates], dtype=float)

    selected_idx = np.asarray([int(np.argmin(np.abs(x_fit - center))) for center in centers], dtype=int)
    estimator = CWTPeakFWHMEstimator(x_fit, fit_y, scale=0.48, threshold=0.01)
    _, _, cwt_data = estimator.cwt_peak_detection()
    fwhm_selected = estimator.estimate_fwhm(cwt_data, selected_idx, x_fit)

    fitter = FixedCenterGaussianFitter(x_fit, fit_y, centers, fwhm_selected, selected_idx).fit()
    real_fit = bool(fitter.fitted_params) and len(fitter.fitted_params) == len(fit_candidates)
    if not real_fit:
        fallback_reason = fallback_reason or "minimize_failed"
        fallback_params = []
        fallback_curves = []
        total_fit = np.zeros_like(x_fit, dtype=float)
        for candidate in fit_candidates:
            center = float(candidate["center"])
            peak_height = max(0.0, float(np.interp(center, x_fit, fit_y)))
            sigma = 0.08
            fallback_params.append((peak_height, center, sigma))
            component = FixedCenterGaussianFitter.gaussian(x_fit, peak_height, center, sigma)
            fallback_curves.append(component)
            total_fit += component
        fitter.fitted_params = fallback_params
        fitter.component_fits = fallback_curves
        fitter.total_fit = total_fit
        fitter.rms = float(np.sqrt(np.mean((fit_y - fitter.total_fit) ** 2)))

    components = []
    component_curves = []
    for index, (amplitude, center, sigma) in enumerate(fitter.fitted_params):
        candidate = fit_candidates[index] if index < len(fit_candidates) else _target_candidate(target, fit_target=fit_target)
        component = {
            "source": candidate["source"],
            "element": candidate["element"],
            "label": candidate["label"],
            "rank": candidate["rank"],
            "center": round(float(center), 4),
            "amplitude": round(float(amplitude), 4),
            "sigma": round(float(abs(sigma)), 4),
        }
        components.append(component)
        curve_y = fitter.component_fits[index] if index < len(fitter.component_fits) else FixedCenterGaussianFitter.gaussian(x_fit, amplitude, center, sigma)
        component_curves.append({**component, "points": _points_payload(x_fit, curve_y)})

    sum_fit = baseline + np.asarray(fitter.total_fit, dtype=float)
    residual = y_fit - sum_fit
    rms = float(np.sqrt(np.mean(residual**2)))
    before_confidence = float(target.get("confidence", 0.0))
    fit_boost = max(0.0, 0.2 * (1.0 - min(rms * 8.0, 1.0)))

    fitted_peaks = [
        {
            "label": component["label"],
            "wavelength": component["center"],
            "intensity": round(float(baseline + component["amplitude"]), 6),
            "amplitude": component["amplitude"],
            "sigma": component["sigma"],
        }
        for component in components
    ]

    return {
        "target": target["ion"],
        "target_element": target["element"],
        "requested_fit_target": _jsonable_fit_target(fit_target),
        "window_nm": [round(float(left_nm), 3), round(float(right_nm), 3)],
        "fit_candidates": fit_candidates,
        "components": components,
        "rms": round(float(rms), 5),
        "before_confidence": round(before_confidence, 4),
        "after_confidence": round(float(min(0.99, before_confidence + fit_boost)), 4),
        "real_multipeak_fit": real_fit,
        "raw_points": _points_payload(x_fit, y_fit),
        "component_curves": component_curves,
        "sum_fit_points": _points_payload(x_fit, sum_fit),
        "fitted_peaks": fitted_peaks,
        "local_extrema": _local_extrema_payload(x_fit, y_fit),
        "residual_points": _points_payload(x_fit, residual),
        "baseline": round(float(baseline), 6),
        "component_count": len(components),
        "fallback_reason": fallback_reason,
        "parity_gap": parity_gap,
    }

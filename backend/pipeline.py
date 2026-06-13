from __future__ import annotations

import csv
import copy
import io
import math
import re
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from scipy.optimize import linear_sum_assignment

try:
    import pywt
except ImportError:  # pragma: no cover - depends on the local scientific stack
    pywt = None

try:
    from backend.line_database import load_line_database as _load_line_database
    from backend.multipeak_fit import fit_summary as _multipeak_fit_summary
    from backend.samples import list_sample_files
    from backend.spectrum import parse_spectrum_text
except ModuleNotFoundError:
    from line_database import load_line_database as _load_line_database
    from multipeak_fit import fit_summary as _multipeak_fit_summary
    from samples import list_sample_files
    from spectrum import parse_spectrum_text


ROOT_DIR = Path(__file__).resolve().parents[1]
ELEMENTS_DB_DIR = ROOT_DIR / "Elements_database"
RARE_EARTH_DB_DIR = ROOT_DIR / "Rareearth_pt3"
KB_EV = 8.617330350e-5
RARE_EARTH_ORDER = ["Y", "Eu", "Lu", "Er", "Ho", "Yb", "La", "Tm", "Tb", "Sm", "Pr", "Ce", "Nd", "Dy", "Gd"]
MATRIX_ELEMENT_ORDER = ["Si", "Fe", "Al", "Ca", "Mg", "Na", "K", "Ti", "Mn", "Ni"]

STAGES = [
    ("raw", "原始光谱"),
    ("peak", "寻峰结果"),
    ("match", "谱线匹配"),
    ("temperature", "温度迭代"),
    ("fit", "多峰拟合"),
    ("result", "检测结果"),
]

RARE_EARTH_LINES = [
    {"element": "Pr", "ion": "Pr II", "wl": 422.30, "conflict": "Fe"},
    {"element": "Yb", "ion": "Yb II", "wl": 516.96, "conflict": None},
    {"element": "La", "ion": "La II", "wl": 529.60, "conflict": "Si"},
    {"element": "Eu", "ion": "Eu II", "wl": 642.10, "conflict": None},
    {"element": "Nd", "ion": "Nd II", "wl": 760.20, "conflict": None},
    {"element": "Tb", "ion": "Tb II", "wl": 432.80, "conflict": "Fe"},
]


def _base_element_name(ion_name):
    return re.sub(r"(III|II|IV|VI|V|I)$", "", str(ion_name)).strip()


def _normalize_vector(values):
    values = np.asarray(values, dtype=float)
    total = float(np.sum(values))
    return values / total if total > 0 else values


def _safe_linear_polyfit(energy, y_values):
    energy = np.asarray(energy, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    if energy.size < 2 or y_values.size < 2 or energy.size != y_values.size:
        return None
    if not (np.isfinite(energy).all() and np.isfinite(y_values).all()):
        return None
    if np.unique(energy).size < 2:
        return None
    try:
        return np.polyfit(energy, y_values, 1)
    except (np.linalg.LinAlgError, RuntimeWarning, ValueError):
        return None


def _boltzmann_fit(intensity, wavelength, transition_probability, degeneracy, energy):
    intensity = np.asarray(intensity, dtype=float)
    wavelength = np.asarray(wavelength, dtype=float)
    transition_probability = np.asarray(transition_probability, dtype=float)
    degeneracy = np.asarray(degeneracy, dtype=float)
    energy = np.asarray(energy, dtype=float)

    mask = (
        np.isfinite(intensity)
        & np.isfinite(wavelength)
        & np.isfinite(transition_probability)
        & np.isfinite(degeneracy)
        & np.isfinite(energy)
        & (intensity > 0)
        & (wavelength > 0)
        & (transition_probability > 0)
        & (degeneracy > 0)
    )
    intensity = intensity[mask]
    wavelength = wavelength[mask]
    transition_probability = transition_probability[mask]
    degeneracy = degeneracy[mask]
    energy = energy[mask]

    if energy.size < 2:
        return 0.0, 0.0

    y_values = np.log(intensity * wavelength / (degeneracy * transition_probability))
    fit = _safe_linear_polyfit(energy, y_values)
    if fit is None:
        return 0.0, 0.0

    slope, intercept = fit
    temperature = -1.0 / (slope * KB_EV) if slope != 0 else 0.0
    predicted = slope * energy + intercept
    ss_res = float(np.sum((y_values - predicted) ** 2))
    ss_tot = float(np.sum((y_values - np.mean(y_values)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    return float(temperature), float(r2)


def _match_spectral_lines_weighted(theoretical_wavelength, theoretical_intensity, experimental_wavelength, experimental_intensity, scope=0.2):
    theoretical_wavelength = np.asarray(theoretical_wavelength, dtype=float)
    theoretical_intensity = np.asarray(theoretical_intensity, dtype=float)
    experimental_wavelength = np.asarray(experimental_wavelength, dtype=float)
    experimental_intensity = np.asarray(experimental_intensity, dtype=float)

    if theoretical_wavelength.size == 0 or experimental_wavelength.size == 0:
        return np.array([]), np.array([]), [], [], np.array([], dtype=int)

    theoretical_count = theoretical_wavelength.size
    experimental_count = experimental_wavelength.size
    matrix_size = max(theoretical_count, experimental_count)
    big_cost = 1e6
    cost = np.full((matrix_size, matrix_size), big_cost, dtype=float)

    for i in range(theoretical_count):
        for j in range(experimental_count):
            diff = abs(theoretical_wavelength[i] - experimental_wavelength[j])
            if diff <= scope:
                cost[i, j] = diff - 0.03 * experimental_intensity[j]

    row_ind, col_ind = linear_sum_assignment(cost)
    theoretical_vector = []
    experimental_vector = []
    matched_theoretical = []
    matched_experimental = []
    matched_theoretical_idx = []

    for row_idx, col_idx in zip(row_ind, col_ind):
        if row_idx < theoretical_count and col_idx < experimental_count and cost[row_idx, col_idx] < big_cost:
            theoretical_vector.append(theoretical_intensity[row_idx])
            experimental_vector.append(experimental_intensity[col_idx])
            matched_theoretical.append((float(theoretical_wavelength[row_idx]), float(theoretical_intensity[row_idx])))
            matched_experimental.append((float(experimental_wavelength[col_idx]), float(experimental_intensity[col_idx])))
            matched_theoretical_idx.append(row_idx)
        elif row_idx < theoretical_count:
            theoretical_vector.append(0.0)
            experimental_vector.append(0.0)

    return (
        np.asarray(theoretical_vector, dtype=float),
        np.asarray(experimental_vector, dtype=float),
        matched_theoretical,
        matched_experimental,
        np.asarray(matched_theoretical_idx, dtype=int),
    )


def _compute_element_confidence(elements, peak_wavelength, peak_intensity, scope=0.2, return_line_payload=False):
    element_distance = {}
    element_temperature = {}
    element_r2 = {}
    element_linecounts = {}
    line_payload = {}

    for ion_name, element_data in elements.items():
        matrix = np.asarray(element_data["data"], dtype=float)
        theoretical_wavelength = matrix[:, 0]
        theoretical_intensity = matrix[:, 1]
        transition_probability = matrix[:, 2]
        energy = matrix[:, 3]
        degeneracy = matrix[:, 4]

        theoretical_vector, experimental_vector, matched_theoretical, matched_experimental, matched_idx = _match_spectral_lines_weighted(
            theoretical_wavelength,
            theoretical_intensity,
            peak_wavelength,
            peak_intensity,
            scope=scope,
        )
        theoretical_norm = _normalize_vector(theoretical_vector)
        experimental_norm = _normalize_vector(experimental_vector)
        if theoretical_norm.size == 0 or experimental_norm.size == 0:
            distance = 1e4
        else:
            distance = float(np.sqrt(np.sum((theoretical_norm - experimental_norm) ** 2)))
            if distance == 0:
                distance = 1e4

        if matched_idx.size >= 2 and matched_experimental:
            matched_wavelength = theoretical_wavelength[matched_idx]
            matched_intensity = np.asarray([item[1] for item in matched_experimental], dtype=float)
            temperature, r2 = _boltzmann_fit(
                matched_intensity,
                matched_wavelength,
                transition_probability[matched_idx],
                degeneracy[matched_idx],
                energy[matched_idx],
            )
        else:
            temperature, r2 = 0.0, 0.0

        base_name = _base_element_name(ion_name)
        element_distance.setdefault(base_name, []).append(distance)
        element_temperature.setdefault(base_name, []).append(temperature)
        element_r2.setdefault(base_name, []).append(r2)
        element_linecounts.setdefault(base_name, []).append(len(matched_experimental))
        line_payload[ion_name] = {
            "base": base_name,
            "distance": distance,
            "temperature": temperature,
            "r2": r2,
            "line_count": len(matched_experimental),
            "all_theoretical": [
                {
                    "wavelength": float(theoretical_wavelength[index]),
                    "intensity": float(theoretical_intensity[index]),
                    "A": float(transition_probability[index]),
                    "E": float(energy[index]),
                    "g": float(degeneracy[index]),
                }
                for index in range(theoretical_wavelength.size)
            ],
            "matched_theoretical": matched_theoretical,
            "matched_experimental": matched_experimental,
            "matched_idx": matched_idx.tolist(),
        }

    final_distance = {}
    final_temperature = {}
    final_r2 = {}
    final_linecount = {}
    confidence = {}

    for base_name, distances in element_distance.items():
        distance_arr = np.asarray(distances, dtype=float)
        final_distance[base_name] = float(np.min(distance_arr)) if np.min(distance_arr) < 47.13333 else float(np.mean(distance_arr))

        candidates = []
        for temperature, r2, line_count in zip(
            element_temperature.get(base_name, []),
            element_r2.get(base_name, []),
            element_linecounts.get(base_name, []),
        ):
            if temperature > 0:
                candidates.append((float(temperature), float(r2), int(line_count)))

        if candidates:
            best_temperature, best_r2, best_linecount = max(candidates, key=lambda item: item[1])
        else:
            best_temperature, best_r2, best_linecount = 0.0, 0.0, 0

        final_temperature[base_name] = best_temperature
        final_r2[base_name] = best_r2
        final_linecount[base_name] = best_linecount
        if final_distance[base_name] < 10000 and best_r2 > 0 and 5000 <= best_temperature <= 20000:
            confidence[base_name] = float(np.exp(-4.5 * final_distance[base_name] / max(best_r2, 1e-9)))
        else:
            confidence[base_name] = 0.0

    if return_line_payload:
        return final_distance, final_temperature, final_r2, confidence, final_linecount, line_payload
    return final_distance, final_temperature, final_r2, confidence, final_linecount


def _candidate_score(confidence, r2):
    return float(confidence) - 0.35 * abs(float(r2) - 1.0)


def _pick_target_temperature(confidence, temperatures, r2_values, top_k=3):
    if not confidence:
        return 10000.0, []
    ranked = sorted(confidence.items(), key=lambda item: item[1], reverse=True)
    top_items = ranked[: max(1, min(top_k, len(ranked)))]
    scores = np.asarray([_candidate_score(score, r2_values.get(element, 0.0)) for element, score in top_items], dtype=float)
    candidate_temperatures = np.asarray([float(temperatures.get(element, 0.0)) for element, _ in top_items], dtype=float)
    valid = np.isfinite(candidate_temperatures) & (candidate_temperatures > 0)
    if not np.any(valid):
        return 10000.0, [element for element, _ in top_items]
    scores = scores[valid]
    candidate_temperatures = candidate_temperatures[valid]
    shifted = scores - np.max(scores)
    weights = np.exp(shifted)
    weights = weights / max(float(np.sum(weights)), 1e-12)
    return float(np.sum(weights * candidate_temperatures)), [element for element, _ in top_items]


def _temperature_iteration_single(
    peak_wavelength,
    peak_intensity,
    initial_temperature,
    max_iterations=12,
    tolerance=1e-5,
    t_min=5000.0,
    t_max=20000.0,
    alpha=0.35,
    top_k=3,
):
    temperature = float(np.clip(float(initial_temperature), t_min, t_max))
    trace = []
    final_payload = None
    best_state = {
        "score": -math.inf,
        "candidate": None,
        "confidence": 0.0,
        "r2": 0.0,
    }
    stable_rounds = 0

    for iteration in range(max_iterations):
        elements = _load_line_database(ELEMENTS_DB_DIR, temperature)
        distances, temperatures, r2_values, confidence, linecounts, line_payload = _compute_element_confidence(
            elements,
            peak_wavelength,
            peak_intensity,
            scope=0.3,
            return_line_payload=True,
        )
        final_payload = (distances, temperatures, r2_values, confidence, linecounts, line_payload)
        if not confidence:
            break

        valid_candidates = {
            element: value
            for element, value in confidence.items()
            if float(temperatures.get(element, 0.0)) > 0 and float(r2_values.get(element, 0.0)) != 1.0
        }
        candidate_pool = valid_candidates if valid_candidates else confidence
        target_temperature, ranked = _pick_target_temperature(candidate_pool, temperatures, r2_values, top_k=top_k)
        top_candidate = ranked[0] if ranked else max(candidate_pool, key=candidate_pool.get)
        candidate_confidence = float(confidence.get(top_candidate, 0.0)) if top_candidate else 0.0
        candidate_r2 = float(r2_values.get(top_candidate, 0.0)) if top_candidate else 0.0
        current_score = _candidate_score(candidate_confidence, candidate_r2) if top_candidate else 0.0

        if current_score > best_state["score"]:
            best_state = {
                "score": current_score,
                "candidate": top_candidate,
                "confidence": candidate_confidence,
                "r2": candidate_r2,
            }

        previous_temperature = temperature
        temperature = float(np.clip((1.0 - alpha) * temperature + alpha * target_temperature, t_min, t_max))
        delta = abs(temperature - previous_temperature)
        trace.append(
            {
                "iteration": iteration,
                "temperature": round(temperature, 2),
                "target_temperature": round(float(target_temperature), 2),
                "candidate": top_candidate,
                "confidence": round(candidate_confidence, 4),
                "r2": round(candidate_r2, 4),
                "score": round(float(current_score), 4),
                "delta": round(delta, 4),
            }
        )

        if delta / max(abs(temperature), 1e-12) < tolerance:
            stable_rounds += 1
        else:
            stable_rounds = 0
        if stable_rounds >= 2:
            break

    if final_payload is None:
        final_payload = ({}, {}, {}, {}, {}, {})
    return {
        "initial_temperature": float(initial_temperature),
        "final_temperature": temperature,
        "best_score": best_state["score"],
        "best_candidate": best_state["candidate"],
        "best_confidence": best_state["confidence"],
        "best_r2": best_state["r2"],
        "trace": trace,
        "payload": final_payload,
    }


def _temperature_multistart_iteration(
    peak_wavelength,
    peak_intensity,
    t_min=5000.0,
    t_max=20000.0,
    multistart_count=10,
    max_iterations=12,
    tolerance=1e-5,
    alpha=0.35,
    top_k=3,
):
    initial_points = np.linspace(float(t_min), float(t_max), max(1, int(multistart_count))).tolist()
    raw_starts = [
        _temperature_iteration_single(
            peak_wavelength,
            peak_intensity,
            initial_temperature,
            max_iterations=max_iterations,
            tolerance=tolerance,
            t_min=t_min,
            t_max=t_max,
            alpha=alpha,
            top_k=top_k,
        )
        for initial_temperature in initial_points
    ]

    best_index = 0
    best_score = -math.inf
    for index, start in enumerate(raw_starts):
        score = float(start["best_score"])
        if math.isfinite(score) and score > best_score:
            best_score = score
            best_index = index

    if not math.isfinite(best_score):
        best_score = 0.0

    starts = []
    for index, start in enumerate(raw_starts):
        score = float(start["best_score"]) if math.isfinite(float(start["best_score"])) else 0.0
        starts.append(
            {
                "start_index": index,
                "initial_temperature": round(float(start["initial_temperature"]), 2),
                "final_temperature": round(float(start["final_temperature"]), 2),
                "best_score": round(score, 4),
                "best_candidate": start["best_candidate"],
                "best_confidence": round(float(start["best_confidence"]), 4),
                "best_r2": round(float(start["best_r2"]), 4),
                "selected": index == best_index,
                "trace": start["trace"],
            }
        )

    selected = raw_starts[best_index] if raw_starts else {
        "final_temperature": 10000.0,
        "trace": [],
        "payload": ({}, {}, {}, {}, {}, {}),
    }
    return {
        "temperature": float(selected["final_temperature"]),
        "trace": selected["trace"],
        "starts": starts,
        "best_start_index": int(best_index),
        "best_score": round(float(best_score), 4),
        "payload": selected["payload"],
        "parameters": {
            "t_min": float(t_min),
            "t_max": float(t_max),
            "multistart_count": len(starts),
            "iterations": int(max_iterations),
            "tolerance": float(tolerance),
            "candidate_mode": "alterable",
            "top_k": int(top_k),
            "alpha": float(alpha),
        },
    }


def _cwt_peak_detection(wavelength, intensity, max_peaks=80):
    if pywt is None:
        return None

    signal = np.asarray(intensity, dtype=float)
    wavelength = np.asarray(wavelength, dtype=float)
    scales = np.arange(1, 11)
    coefficients, _ = pywt.cwt(signal, scales, "mexh")
    n_scales, n_points = coefficients.shape
    max_index = np.zeros_like(coefficients, dtype=int)

    for scale_idx in range(n_scales - 1, -1, -1):
        row = coefficients[scale_idx]
        max_index[scale_idx, 1:-1] = ((row[1:-1] > row[:-2]) & (row[1:-1] > row[2:])).astype(int)

    ridges = []
    neighbor = 4
    min_length = 3
    energy_threshold = max(0.01, float(np.nanpercentile(np.abs(coefficients), 92)) * 0.35)
    for start_pos in np.where(max_index[-1] == 1)[0]:
        ridge = [[n_scales - 1, int(start_pos)]]
        previous_pos = int(start_pos)
        for scale_idx in range(n_scales - 2, -1, -1):
            candidates = [
                pos
                for pos in range(max(1, previous_pos - neighbor), min(n_points - 1, previous_pos + neighbor + 1))
                if max_index[scale_idx, pos] == 1
            ]
            if not candidates:
                break
            next_pos = min(candidates, key=lambda pos: abs(pos - previous_pos))
            ridge.append([scale_idx, int(next_pos)])
            previous_pos = int(next_pos)
        if len(ridge) >= min_length:
            ridge_coeffs = [coefficients[scale_idx, pos_idx] for scale_idx, pos_idx in ridge]
            if float(np.max(ridge_coeffs)) > energy_threshold:
                ridges.append(ridge)

    peak_indices = []
    for ridge in ridges:
        _, pos_idx = min(ridge, key=lambda item: item[0])
        left = max(0, int(pos_idx) - 5)
        right = min(signal.size - 1, int(pos_idx) + 5)
        local_idx = int(np.argmax(signal[left : right + 1]) + left)
        if local_idx not in peak_indices:
            peak_indices.append(local_idx)

    if not peak_indices:
        return None

    peak_indices = np.asarray(peak_indices, dtype=int)
    if peak_indices.size > max_peaks:
        strongest = np.argsort(signal[peak_indices])[-max_peaks:]
        peak_indices = peak_indices[strongest]
    peak_indices = peak_indices[np.argsort(wavelength[peak_indices])]
    return peak_indices


def detect_peaks(spectrum, max_peaks=80):
    x = np.asarray(spectrum["x"], dtype=float)
    y = np.asarray(spectrum["y_normalized"], dtype=float)
    method = "CWT ridge peak detection"
    peak_idx = _cwt_peak_detection(x, y, max_peaks=max_peaks)
    prominences = np.zeros(0)

    if peak_idx is None or peak_idx.size == 0:
        method = "scipy.signal.find_peaks fallback"
        distance = max(3, int(x.size / 500))
        prominence = max(0.025, float(np.std(y)) * 0.45)
        peak_idx, props = find_peaks(y, distance=distance, prominence=prominence)
        prominences = props.get("prominences", np.zeros(peak_idx.size))

    if peak_idx.size == 0:
        local = np.where((y[1:-1] > y[:-2]) & (y[1:-1] > y[2:]) & (y[1:-1] > 0.15))[0] + 1
        peak_idx = local
        method = "local maxima fallback"
        prominences = np.zeros(local.size)

    if peak_idx.size > max_peaks:
        strongest = np.argsort(y[peak_idx])[-max_peaks:]
        peak_idx = peak_idx[strongest]
        prominences = prominences[strongest] if prominences.size else np.zeros(peak_idx.size)

    order = np.argsort(x[peak_idx]) if peak_idx.size else np.array([], dtype=int)
    peak_idx = peak_idx[order]
    prominences = prominences[order] if prominences.size else np.zeros(peak_idx.size)

    peaks = []
    for idx, prominence_value in zip(peak_idx, prominences):
        peaks.append(
            {
                "index": int(idx),
                "wavelength": float(x[idx]),
                "intensity": float(y[idx]),
                "prominence": float(prominence_value),
            }
        )
    return peaks, method


def _nearest_peak(peaks, target_wl):
    if not peaks:
        return None, None
    nearest = min(peaks, key=lambda peak: abs(peak["wavelength"] - target_wl))
    return nearest, abs(nearest["wavelength"] - target_wl)


def _rank_base_candidates(confidence, distances, temperatures, r2_values, linecounts, limit=8):
    rows = []
    for element in sorted(confidence):
        rows.append(
            {
                "element": element,
                "confidence": round(float(confidence.get(element, 0.0)), 4),
                "distance": round(float(distances.get(element, 10000.0)), 4),
                "temperature": round(float(temperatures.get(element, 0.0)), 2),
                "r2": round(float(r2_values.get(element, 0.0)), 4),
                "matched": int(linecounts.get(element, 0)),
            }
        )

    preferred_order = {element: index for index, element in enumerate(MATRIX_ELEMENT_ORDER)}
    rows.sort(key=lambda row: (-row["confidence"], -row["matched"], preferred_order.get(row["element"], 999), row["element"]))
    return rows[:limit]


def _round_or_none(value, digits=6):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return round(numeric, digits)


def _sum_intensity(rows):
    total = 0.0
    for row in rows:
        try:
            value = float(row.get("intensity", 0.0) if isinstance(row, dict) else row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(value) and value > 0:
            total += value
    return float(total)


def _normalized_intensity(value, total):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    if total > 0 and math.isfinite(numeric):
        return round(float(numeric / total), 8)
    return 0.0


def _item_confidence(distance, temperature, r2, t_min=5000.0, t_max=20000.0):
    distance = float(distance)
    temperature = float(temperature)
    r2 = float(r2)
    if distance < 10000 and r2 > 0 and t_min <= temperature <= t_max:
        return float(np.exp(-4.5 * distance / max(r2, 1e-9)))
    return 0.0


def _representative_selection_map(line_payload, t_min=5000.0, t_max=20000.0):
    grouped = {}
    for ion_name, payload in line_payload.items():
        base_name = payload.get("base") or _base_element_name(ion_name)
        grouped.setdefault(base_name, []).append((ion_name, payload))

    selected_by_base = {}
    for base_name, rows in grouped.items():
        valid_rows = []
        for ion_name, payload in rows:
            temperature = float(payload.get("temperature", 0.0))
            r2 = float(payload.get("r2", 0.0))
            if t_min <= temperature <= t_max and r2 > 0:
                valid_rows.append((ion_name, payload))
        if valid_rows:
            selected_ion, _selected_payload = max(
                valid_rows,
                key=lambda row: (
                    float(row[1].get("r2", 0.0)),
                    int(row[1].get("line_count", 0)),
                    -float(row[1].get("distance", 10000.0)),
                ),
            )
            selected_by_base[base_name] = selected_ion

    selections = {}
    for ion_name, payload in line_payload.items():
        base_name = payload.get("base") or _base_element_name(ion_name)
        temperature = float(payload.get("temperature", 0.0))
        r2 = float(payload.get("r2", 0.0))
        line_count = int(payload.get("line_count", 0))
        valid_temperature = bool(t_min <= temperature <= t_max and r2 > 0)
        selected = selected_by_base.get(base_name) == ion_name
        if selected:
            reason = "valid_temperature_best_r2"
        elif valid_temperature:
            reason = "valid_temperature_not_best_r2"
        elif line_count < 2:
            reason = "insufficient_matched_lines_for_boltzmann"
        elif temperature <= 0:
            reason = "no_valid_boltzmann_temperature"
        elif temperature < t_min or temperature > t_max:
            reason = "out_of_temperature_gate"
        else:
            reason = "non_positive_r2"
        selections[ion_name] = {
            "selected": selected,
            "valid_temperature": valid_temperature,
            "best_r2": selected,
            "reason": reason,
            "rule": "select ions with 5000 <= T <= 20000 K, then choose the largest R2 per element",
        }
    return selections


def _normalization_note(all_sum, matched_theoretical_sum, matched_experimental_sum):
    def row(sum_value, basis):
        return {
            "basis": basis,
            "sum": round(float(sum_value), 8),
            "empty_behavior": "empty comb returns [] and normalized sum 0",
        }

    return {
        "all_theoretical": row(
            all_sum,
            "sum of all line-switch-enabled theoretical relative intensities for the ion",
        ),
        "matched_theoretical": row(
            matched_theoretical_sum,
            "sum of matched theoretical comb teeth after missing teeth are removed",
        ),
        "matched_experimental": row(
            matched_experimental_sum,
            "sum of globally assigned experimental peak intensities paired to matched theoretical teeth",
        ),
    }


def _build_confidence_calculation(line_payload, confidence, scope_nm=0.2):
    selections = _representative_selection_map(line_payload)
    items = []

    for ion_name, payload in line_payload.items():
        base_name = payload.get("base") or _base_element_name(ion_name)
        all_theoretical_raw = list(payload.get("all_theoretical") or [])
        matched_theoretical_raw = list(payload.get("matched_theoretical") or [])
        matched_experimental_raw = list(payload.get("matched_experimental") or [])
        matched_idx = [int(index) for index in payload.get("matched_idx", [])]
        matched_idx_set = set(matched_idx)

        all_sum = _sum_intensity(all_theoretical_raw)
        matched_theoretical_sum = _sum_intensity(matched_theoretical_raw)
        matched_experimental_sum = _sum_intensity(matched_experimental_raw)

        all_theoretical_comb = []
        for index, row in enumerate(all_theoretical_raw):
            intensity = float(row.get("intensity", 0.0))
            matched = index in matched_idx_set
            all_theoretical_comb.append(
                {
                    "wavelength": _round_or_none(row.get("wavelength"), 6),
                    "intensity": _round_or_none(intensity, 8),
                    "normalized_intensity": _normalized_intensity(intensity, all_sum),
                    "A": _round_or_none(row.get("A"), 8),
                    "E": _round_or_none(row.get("E"), 8),
                    "g": _round_or_none(row.get("g"), 8),
                    "enabled": True,
                    "status": "enabled" if matched else "review",
                    "matched": matched,
                    "review": None if matched else "missing_experimental_peak",
                }
            )

        matched_theoretical_comb = []
        matched_experimental_comb = []
        selected_experimental_peaks = []
        for pair_index, (theoretical, experimental) in enumerate(zip(matched_theoretical_raw, matched_experimental_raw)):
            theoretical_wavelength = float(theoretical[0])
            theoretical_intensity = float(theoretical[1])
            experimental_wavelength = float(experimental[0])
            experimental_intensity = float(experimental[1])
            delta_nm = abs(theoretical_wavelength - experimental_wavelength)
            matched_line_idx = matched_idx[pair_index] if pair_index < len(matched_idx) else None
            line_meta = (
                all_theoretical_raw[matched_line_idx]
                if isinstance(matched_line_idx, int) and 0 <= matched_line_idx < len(all_theoretical_raw)
                else {}
            )
            matched_theoretical_comb.append(
                {
                    "wavelength": round(theoretical_wavelength, 6),
                    "intensity": round(theoretical_intensity, 8),
                    "normalized_intensity": _normalized_intensity(theoretical_intensity, matched_theoretical_sum),
                    "matched_idx": matched_line_idx,
                    "A": _round_or_none(line_meta.get("A"), 8),
                    "E": _round_or_none(line_meta.get("E"), 8),
                    "g": _round_or_none(line_meta.get("g"), 8),
                }
            )
            experimental_row = {
                "wavelength": round(experimental_wavelength, 6),
                "intensity": round(experimental_intensity, 8),
                "normalized_intensity": _normalized_intensity(experimental_intensity, matched_experimental_sum),
                "delta_nm": round(delta_nm, 6),
                "matched_idx": matched_line_idx,
                "theoretical_wavelength": round(theoretical_wavelength, 6),
            }
            matched_experimental_comb.append(experimental_row)
            selected_experimental_peaks.append(
                {
                    "wavelength": experimental_row["wavelength"],
                    "intensity": experimental_row["intensity"],
                    "theoretical_wavelength": experimental_row["theoretical_wavelength"],
                    "delta_nm": experimental_row["delta_nm"],
                    "matched_idx": matched_line_idx,
                }
            )

        distance = float(payload.get("distance", 10000.0))
        temperature = float(payload.get("temperature", 0.0))
        r2 = float(payload.get("r2", 0.0))
        item_confidence = _item_confidence(distance, temperature, r2)
        items.append(
            {
                "element": base_name,
                "ion": ion_name,
                "confidence": round(float(item_confidence), 4),
                "element_confidence": round(float(confidence.get(base_name, 0.0)), 4),
                "distance": round(distance, 4),
                "temperature": round(temperature, 2),
                "r2": round(r2, 4),
                "line_count": int(payload.get("line_count", 0)),
                "all_theoretical_comb": all_theoretical_comb,
                "matched_theoretical_comb": matched_theoretical_comb,
                "matched_experimental_comb": matched_experimental_comb,
                "raw_peak_marks": {
                    "spectrum_source": "raw stage preview/full parsed spectrum provides the black spectrum line",
                    "theoretical_wavelengths": [
                        {
                            "wavelength": row["wavelength"],
                            "normalized_intensity": row["normalized_intensity"],
                            "status": row["status"],
                            "matched": row["matched"],
                        }
                        for row in all_theoretical_comb
                    ],
                    "selected_experimental_peaks": selected_experimental_peaks,
                },
                "normalization": _normalization_note(all_sum, matched_theoretical_sum, matched_experimental_sum),
                "representative_selection": selections.get(ion_name, {"selected": False, "reason": "not_evaluated"}),
            }
        )

    items.sort(
        key=lambda item: (
            not item.get("representative_selection", {}).get("selected", False),
            -float(item.get("confidence", 0.0)),
            -int(item.get("line_count", 0)),
            item.get("ion", ""),
        )
    )
    return {
        "formula": {
            "theoretical_comb": "relative intensity is computed from A, g, E and electron temperature T by backend.line_database, then normalized by ion",
            "matching": "Hungarian global assignment within scope_nm; missing theoretical teeth are removed before matched-comb normalization",
            "distance": "sqrt(sum((matched_theoretical_comb.normalized_intensity - matched_experimental_comb.normalized_intensity)^2))",
            "confidence": "exp(-4.5 * distance / max(R2, 1e-9)) when distance < 10000, R2 > 0, and T is inside the temperature gate; otherwise 0",
            "boltzmann": "R2 and T come from ln(I * wavelength / (g * A)) versus E using matched experimental intensities",
        },
        "temperature_gate": {
            "min_k": 5000.0,
            "max_k": 20000.0,
            "inclusive": True,
            "applies_to": ["representative_selection", "confidence"],
        },
        "scope_nm": float(scope_nm),
        "total_count": len(items),
        "omitted_count": 0,
        "parity_gap": [
            {
                "stage": "matching_weight",
                "status": "recorded_not_changed_in_this_slice",
                "backend": "cost = abs(delta_nm) - 0.03 * experimental_intensity",
                "reference": "Elements_detectation.match_spectral_lines_weighted default cost = alpha * abs(delta_nm) - beta * experimental_intensity, alpha=1.0, beta=1.0",
            }
        ],
        "items": items,
    }


def _build_spectral_matches(line_payload, confidence, max_items=40):
    matches = []
    for ion_name, payload in line_payload.items():
        base_name = payload["base"]
        matched_theoretical = payload["matched_theoretical"]
        matched_experimental = payload["matched_experimental"]
        for theoretical, experimental in zip(matched_theoretical, matched_experimental):
            theoretical_wl, theoretical_intensity = theoretical
            experimental_wl, experimental_intensity = experimental
            delta = abs(float(theoretical_wl) - float(experimental_wl))
            element_confidence = float(confidence.get(base_name, 0.0))
            matches.append(
                {
                    "element": base_name,
                    "ion": ion_name,
                    "wavelength": round(float(theoretical_wl), 4),
                    "line_intensity": round(float(theoretical_intensity), 6),
                    "line_type": "Rareearth_pt3 relative intensity",
                    "status": "enabled" if element_confidence > 0 else "review",
                    "delta_nm": round(delta, 4),
                    "matched_peak": {
                        "wavelength": round(float(experimental_wl), 4),
                        "intensity": round(float(experimental_intensity), 4),
                    },
                    "confidence": round(element_confidence, 4),
                    "reason": "Rareearth_pt3 谱线库 + 匈牙利匹配",
                }
            )

    matches.sort(key=lambda row: (-row["confidence"], row["delta_nm"], -row["matched_peak"]["intensity"], row["ion"]))
    return matches[:max_items]


def _gaussian_sum_fixed_center(x_values, *params):
    component_count = (len(params) - 1) // 2
    baseline = params[-1]
    y_values = np.full_like(x_values, baseline, dtype=float)
    centers = _gaussian_sum_fixed_center.centers
    for idx in range(component_count):
        amplitude = params[idx * 2]
        sigma = max(abs(params[idx * 2 + 1]), 1e-6)
        center = centers[idx]
        y_values += amplitude * np.exp(-0.5 * ((x_values - center) / sigma) ** 2)
    return y_values


_gaussian_sum_fixed_center.centers = np.array([], dtype=float)


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

    extrema = []
    size = min(x_arr.size, y_arr.size)
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


def _gaussian_component_values(x_values, center, amplitude, sigma):
    sigma = max(float(abs(sigma)), 1e-6)
    return float(amplitude) * np.exp(-0.5 * ((x_values - float(center)) / sigma) ** 2)


def _fit_summary(spectrum, matches, matrix_elements=(), fit_target=None):
    return _multipeak_fit_summary(spectrum, matches, matrix_elements=matrix_elements, root_dir=ROOT_DIR, fit_target=fit_target)

    enabled = [row for row in matches if row["status"] == "enabled" and row["matched_peak"]]
    target = max(enabled, key=lambda row: (row.get("confidence", 0.0), row["matched_peak"]["intensity"]), default=None)
    if target is None:
        return {
            "target": None,
            "target_element": None,
            "window_nm": None,
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
            "fallback_reason": "no_enabled_matched_peak",
        }

    x = np.asarray(spectrum["x"], dtype=float)
    y = np.asarray(spectrum["y_normalized"], dtype=float)
    center = float(target["matched_peak"]["wavelength"])
    window_half_width = 0.9
    mask = (x >= center - window_half_width) & (x <= center + window_half_width)
    real_fit = False
    x_fit = x[mask]
    y_fit = y[mask]
    baseline = None
    fitted = np.array([], dtype=float)
    fallback_reason = None

    if x_fit.size >= 1:
        baseline = float(np.percentile(y_fit, 10))

    if x_fit.size >= 8:
        center_candidates = [
            float(row["matched_peak"]["wavelength"])
            for row in enabled
            if abs(float(row["matched_peak"]["wavelength"]) - center) <= window_half_width
        ]
        centers = np.asarray(sorted(set(round(value, 4) for value in center_candidates))[:3], dtype=float)
        if centers.size == 0:
            centers = np.asarray([center], dtype=float)

        _gaussian_sum_fixed_center.centers = centers
        baseline_guess = baseline if baseline is not None else 0.0
        p0 = []
        lower = []
        upper = []
        for fit_center in centers:
            amplitude_guess = max(0.02, float(np.interp(fit_center, x_fit, y_fit) - baseline_guess))
            p0.extend([amplitude_guess, 0.08])
            lower.extend([0.0, 0.01])
            upper.extend([1.5, 1.5])
        p0.append(baseline_guess)
        lower.append(0.0)
        upper.append(1.0)

        try:
            params, _ = curve_fit(
                _gaussian_sum_fixed_center,
                x_fit,
                y_fit,
                p0=np.asarray(p0, dtype=float),
                bounds=(np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)),
                maxfev=5000,
            )
            fitted = _gaussian_sum_fixed_center(x_fit, *params)
            rms = float(np.sqrt(np.mean((y_fit - fitted) ** 2)))
            baseline = float(params[-1])
            components = []
            for idx, fit_center in enumerate(centers):
                components.append(
                    {
                        "label": target["ion"] if abs(fit_center - center) < 1e-6 else "overlap",
                        "center": round(float(fit_center), 4),
                        "amplitude": round(float(params[idx * 2]), 4),
                        "sigma": round(float(abs(params[idx * 2 + 1])), 4),
                    }
                )
            real_fit = True
        except (RuntimeError, ValueError):
            rms = None
            components = []
            fallback_reason = "curve_fit_failed"
    else:
        rms = None
        components = []
        fallback_reason = "insufficient_fit_window_points"

    if not components:
        components = [
            {
                "label": target["ion"],
                "center": round(center, 4),
                "amplitude": round(float(target["matched_peak"]["intensity"]), 4),
                "sigma": 0.08,
            }
        ]
        if fallback_reason is None:
            fallback_reason = "fallback_component_only"

    baseline_for_plot = 0.0 if baseline is None else float(baseline)
    component_curves = []
    sum_fit = np.full_like(x_fit, baseline_for_plot, dtype=float)
    if x_fit.size:
        for component in components:
            curve_y = _gaussian_component_values(
                x_fit,
                component["center"],
                component["amplitude"],
                component["sigma"],
            )
            sum_fit += curve_y
            component_curves.append(
                {
                    "label": component["label"],
                    "center": component["center"],
                    "amplitude": component["amplitude"],
                    "sigma": component["sigma"],
                    "points": _points_payload(x_fit, curve_y),
                }
            )

    if real_fit and fitted.size == x_fit.size:
        sum_fit = fitted

    fitted_peaks = [
        {
            "label": component["label"],
            "wavelength": component["center"],
            "intensity": round(float(baseline_for_plot + component["amplitude"]), 6),
            "amplitude": component["amplitude"],
            "sigma": component["sigma"],
        }
        for component in components
    ]
    residual = y_fit - sum_fit if x_fit.size and sum_fit.size == y_fit.size else np.array([], dtype=float)

    before_confidence = float(target.get("confidence", 0.0))
    fit_boost = 0.0 if rms is None else max(0.0, 0.2 * (1.0 - min(rms * 8.0, 1.0)))
    return {
        "target": target["ion"],
        "target_element": target["element"],
        "window_nm": [round(center - window_half_width, 3), round(center + window_half_width, 3)],
        "components": components,
        "rms": None if rms is None else round(float(rms), 5),
        "before_confidence": round(before_confidence, 4),
        "after_confidence": round(float(min(0.99, before_confidence + fit_boost)), 4),
        "real_multipeak_fit": real_fit,
        "raw_points": _points_payload(x_fit, y_fit),
        "component_curves": component_curves,
        "sum_fit_points": _points_payload(x_fit, sum_fit),
        "fitted_peaks": fitted_peaks,
        "local_extrema": _local_extrema_payload(x_fit, y_fit),
        "residual_points": _points_payload(x_fit, residual),
        "baseline": None if baseline is None else round(float(baseline), 6),
        "component_count": len(components),
        "fallback_reason": fallback_reason,
    }


def _filter_elements_by_base(elements, base_elements):
    wanted = {str(element).strip().upper() for element in base_elements if str(element).strip()}
    if not wanted:
        return {}
    return {
        ion_name: element_data
        for ion_name, element_data in elements.items()
        if _base_element_name(ion_name).upper() in wanted
    }


def _target_fitted_peak_rows(fit_summary):
    target_element = str(fit_summary.get("target_element") or "").strip()
    if not target_element:
        return []

    rows = []
    fit_candidates = fit_summary.get("fit_candidates") or []
    fitted_peaks = fit_summary.get("fitted_peaks") or []
    for candidate, fitted_peak in zip(fit_candidates, fitted_peaks):
        if str(candidate.get("source") or "").strip().lower() == "matrix":
            continue
        if str(candidate.get("element") or "").strip() != target_element:
            continue
        try:
            wavelength = float(candidate.get("center"))
            amplitude = float(fitted_peak.get("amplitude"))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(wavelength) and math.isfinite(amplitude) and amplitude > 0):
            continue
        rows.append(
            {
                "label": str(candidate.get("label") or fitted_peak.get("label") or fit_summary.get("target") or target_element),
                "wavelength": wavelength,
                "intensity": amplitude,
                "source": str(candidate.get("source") or ""),
            }
        )
    return rows


def _append_fitted_peak_candidates(peak_wavelength, peak_intensity, fitted_peak_rows):
    peak_wavelength = np.asarray(peak_wavelength, dtype=float)
    peak_intensity = np.asarray(peak_intensity, dtype=float)
    valid_peak = np.isfinite(peak_wavelength) & np.isfinite(peak_intensity)
    base_wavelength = peak_wavelength[valid_peak]
    base_intensity = peak_intensity[valid_peak]

    append_wavelength = []
    append_intensity = []
    for row in fitted_peak_rows:
        try:
            wavelength = float(row["wavelength"])
            intensity = float(row["intensity"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(wavelength) and math.isfinite(intensity) and intensity > 0:
            append_wavelength.append(wavelength)
            append_intensity.append(intensity)

    if not append_wavelength:
        return base_wavelength, base_intensity
    return (
        np.concatenate([base_wavelength, np.asarray(append_wavelength, dtype=float)]),
        np.concatenate([base_intensity, np.asarray(append_intensity, dtype=float)]),
    )


def _fit_confidence_rescue(final_temperature, matrix_elements, peak_wavelength, peak_intensity, fit_summary, confidence):
    target_element = fit_summary.get("target_element")
    if not target_element:
        return {"applied": False, "reason": "no_fit_target", "target_element": None}

    base_confidence = float(confidence.get(target_element, 0.0))
    result = {
        "applied": False,
        "reason": None,
        "target_element": target_element,
        "base_confidence": round(base_confidence, 4),
        "recomputed_confidence": None,
        "appended_peak_count": 0,
        "appended_peaks": [],
    }

    if base_confidence > 0.01:
        result["reason"] = "coarse_confidence_not_zero"
        return result

    fitted_peak_rows = _target_fitted_peak_rows(fit_summary)
    result["appended_peak_count"] = len(fitted_peak_rows)
    result["appended_peaks"] = [
        {
            "label": row["label"],
            "wavelength": round(float(row["wavelength"]), 4),
            "intensity": round(float(row["intensity"]), 6),
            "source": row["source"],
        }
        for row in fitted_peak_rows
    ]
    if not fitted_peak_rows:
        result["reason"] = "no_target_fitted_peaks"
        return result

    refit_database = _load_line_database(
        RARE_EARTH_DB_DIR,
        final_temperature,
        main_elements=matrix_elements,
        line_switch=False,
        include_matrix=True,
    )
    target_database = _filter_elements_by_base(refit_database, [target_element])
    if not target_database:
        result["reason"] = "target_database_empty"
        return result

    corrected_wavelength, corrected_intensity = _append_fitted_peak_candidates(peak_wavelength, peak_intensity, fitted_peak_rows)
    _distances, rescue_temperatures, rescue_r2, rescue_confidence, rescue_linecounts = _compute_element_confidence(
        target_database,
        corrected_wavelength,
        corrected_intensity,
        scope=0.2,
    )
    if target_element not in rescue_confidence:
        result["reason"] = "target_confidence_missing"
        return result

    result.update(
        {
            "applied": True,
            "reason": "fitted_peak_append_recompute",
            "recomputed_confidence": round(float(rescue_confidence.get(target_element, 0.0)), 4),
            "temperature": round(float(rescue_temperatures.get(target_element, 0.0)), 2),
            "r2": round(float(rescue_r2.get(target_element, 0.0)), 4),
            "matched": int(rescue_linecounts.get(target_element, 0)),
        }
    )
    return result


def _final_results(confidence, temperatures, r2_values, linecounts, fit_summary):
    rows = []
    confidence_rescue = fit_summary.get("confidence_rescue") or {}
    rescue_target = confidence_rescue.get("target_element") if confidence_rescue.get("applied") else None
    for element in RARE_EARTH_ORDER:
        element_confidence = float(confidence.get(element, 0.0))
        element_temperature = float(temperatures.get(element, 0.0))
        element_r2 = float(r2_values.get(element, 0.0))
        element_linecount = int(linecounts.get(element, 0))
        if rescue_target == element:
            element_confidence = float(confidence_rescue.get("recomputed_confidence") or 0.0)
            element_temperature = float(confidence_rescue.get("temperature") or element_temperature)
            element_r2 = float(confidence_rescue.get("r2") or element_r2)
            element_linecount = int(confidence_rescue.get("matched") or element_linecount)
        rows.append(
            {
                "element": element,
                "detected": bool(element_confidence >= 0.05),
                "confidence": round(float(min(element_confidence, 0.99)), 4),
                "temperature": round(float(element_temperature), 2),
                "r2": round(float(element_r2), 4),
                "matched": int(element_linecount),
            }
        )
    return rows


def _result_csv(final_results):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["element", "detected", "confidence"])
    for row in final_results:
        writer.writerow([row["element"], int(row["detected"]), f'{row["confidence"]:.4f}'])
    return output.getvalue()


def _fit_result_payload_from_context(context, fit_target=None):
    fit_summary = _fit_summary(
        context["spectrum"],
        context["spectral_matches"],
        matrix_elements=context["matrix_elements"],
        fit_target=fit_target,
    )
    fit_summary = dict(fit_summary)
    fit_summary["confidence_rescue"] = _fit_confidence_rescue(
        context["final_temperature"],
        context["matrix_elements"],
        context["peak_wavelength"],
        context["peak_intensity"],
        fit_summary,
        context["rare_confidence"],
    )
    final_results = _final_results(
        context["rare_confidence"],
        context["rare_temperatures"],
        context["rare_r2"],
        context["rare_linecounts"],
        fit_summary,
    )
    csv_text = _result_csv(final_results)
    fit_stage = {
        "id": "fit",
        "title": "多峰拟合",
        "status": "done",
        "summary": "已执行局部 Gaussian 多峰拟合" if fit_summary["real_multipeak_fit"] else "无可稳定拟合目标峰",
        "data": fit_summary,
        "parameters": {
            "model": "fixed-center Gaussian CWT/L-BFGS-B window fit",
            "real_multipeak_fit": fit_summary["real_multipeak_fit"],
            "fit_target": fit_summary.get("requested_fit_target"),
        },
    }
    result_stage = {
        "id": "result",
        "title": "检测结果",
        "status": "done",
        "summary": ", ".join(row["element"] for row in final_results if row["detected"]) or "未检出",
        "data": {"rare_earth_results": final_results, "detection_threshold": 0.05},
    }
    return fit_summary, final_results, csv_text, fit_stage, result_stage


def refit_pipeline_result(result, context, fit_target=None):
    updated = copy.deepcopy(result)
    _fit_summary_payload, _final_results_payload, csv_text, fit_stage, result_stage = _fit_result_payload_from_context(context, fit_target=fit_target)
    stages = updated.get("stages") or []
    for index, stage in enumerate(stages):
        if stage.get("id") == "fit":
            stages[index] = fit_stage
        elif stage.get("id") == "result":
            stages[index] = result_stage
    updated["result_csv"] = csv_text
    return updated


def run_pipeline_with_context(text, filename="uploaded-spectrum", fit_target=None):
    spectrum = parse_spectrum_text(text, filename)
    peaks, peak_method = detect_peaks(spectrum)
    peak_wavelength = np.asarray([peak["wavelength"] for peak in peaks], dtype=float)
    peak_intensity = np.asarray([peak["intensity"] for peak in peaks], dtype=float)

    temperature_result = _temperature_multistart_iteration(peak_wavelength, peak_intensity)
    final_temperature = temperature_result["temperature"]
    main_payload = temperature_result["payload"]
    main_distances, main_temperatures, main_r2, main_confidence, main_linecounts, _main_line_payload = main_payload
    base_candidates = _rank_base_candidates(main_confidence, main_distances, main_temperatures, main_r2, main_linecounts)
    matrix_elements = [row["element"] for row in base_candidates if row["confidence"] >= 0.02][:6]

    rare_earth_database = _load_line_database(
        RARE_EARTH_DB_DIR,
        final_temperature,
        main_elements=matrix_elements,
        line_switch=True,
    )
    rare_distances, rare_temperatures, rare_r2, rare_confidence, rare_linecounts, rare_line_payload = _compute_element_confidence(
        rare_earth_database,
        peak_wavelength,
        peak_intensity,
        scope=0.2,
        return_line_payload=True,
    )
    spectral_matches = _build_spectral_matches(rare_line_payload, rare_confidence)
    confidence_calculation = _build_confidence_calculation(rare_line_payload, rare_confidence, scope_nm=0.2)
    context = {
        "spectrum": spectrum,
        "spectral_matches": spectral_matches,
        "matrix_elements": matrix_elements,
        "final_temperature": final_temperature,
        "peak_wavelength": peak_wavelength,
        "peak_intensity": peak_intensity,
        "rare_confidence": rare_confidence,
        "rare_temperatures": rare_temperatures,
        "rare_r2": rare_r2,
        "rare_linecounts": rare_linecounts,
    }
    _fit_summary_payload, _final_results_payload, csv_text, fit_stage, result_stage = _fit_result_payload_from_context(context, fit_target=fit_target)

    stages = [
        {
            "id": "raw",
            "title": "原始光谱",
            "status": "done",
            "summary": f'{spectrum["point_count"]} 个有效采样点',
            "data": {
                "filename": filename,
                "point_count": spectrum["point_count"],
                "x_min": spectrum["x_min"],
                "x_max": spectrum["x_max"],
                "y_min": spectrum["y_min"],
                "y_max": spectrum["y_max"],
                "preview": spectrum["preview"],
            },
        },
        {
            "id": "peak",
            "title": "寻峰结果",
            "status": "done",
            "summary": f"检测到 {len(peaks)} 个候选峰",
            "data": {"peak_count": len(peaks), "peaks": peaks[:80]},
            "parameters": {"method": peak_method, "max_peaks": 80, "pywt_available": pywt is not None},
        },
        {
            "id": "match",
            "title": "谱线匹配",
            "status": "done",
            "summary": f'{sum(1 for row in spectral_matches if row["status"] == "enabled")} 条稀土谱线匹配',
            "data": {
                "base_candidates": base_candidates,
                "matrix_elements": matrix_elements,
                "spectral_matches": spectral_matches,
                "rare_earth_distances": {key: round(float(value), 4) for key, value in rare_distances.items()},
                "confidence_calculation": confidence_calculation,
            },
            "parameters": {
                "line_database": "Elements_database/Rareearth_pt3",
                "match_tolerance_nm": 0.2,
                "matrix_match_tolerance_nm": 0.3,
                "conflict_filter": True,
            },
        },
        {
            "id": "temperature",
            "title": "温度迭代",
            "status": "done",
            "summary": f'{final_temperature:.0f} K / 评分 {temperature_result["best_score"]:.3f}',
            "data": {
                "trace": temperature_result["trace"],
                "starts": temperature_result["starts"],
                "best_start_index": temperature_result["best_start_index"],
                "best_score": temperature_result["best_score"],
                "temperature": round(float(final_temperature), 2),
            },
            "parameters": temperature_result["parameters"],
        },
        fit_stage,
        result_stage,
    ]

    result = {
        "filename": filename,
        "stages": stages,
        "result_csv": csv_text,
        "notes": [
            "后端已在 Ubuntu 环境接入真实光谱读取、CWT/后备寻峰、Elements_database/Rareearth_pt3 本地谱线库、匈牙利谱线匹配、Boltzmann 温度/R2 和置信度计算。",
            "未直接 import 研究脚本中的顶层执行文件，避免 Windows 绝对路径和绘图副作用影响 Flask 服务。",
        ],
    }
    return result, context


def run_pipeline(text, filename="uploaded-spectrum", fit_target=None):
    result, _context = run_pipeline_with_context(text, filename=filename, fit_target=fit_target)
    return result


def _run_self_tests():
    from pathlib import Path

    def stage_by_id(result, stage_id):
        return next(stage for stage in result["stages"] if stage["id"] == stage_id)

    def assert_keys(mapping, keys):
        missing = set(keys) - set(mapping)
        assert not missing, f"missing contract keys: {sorted(missing)}"

    sample_path = Path("Broaden_research/PureSample_Spectrum/Fe1.asc")
    text = sample_path.read_text(encoding="utf-8", errors="ignore")

    spectrum = parse_spectrum_text(text, sample_path.name)
    assert spectrum["point_count"] > 1000
    assert spectrum["x"][0] < spectrum["x"][-1]
    assert spectrum["y_max"] > spectrum["y_min"]

    result = run_pipeline(text, sample_path.name)
    assert [stage["id"] for stage in result["stages"]] == [
        "raw",
        "peak",
        "match",
        "temperature",
        "fit",
        "result",
    ]
    assert result["stages"][0]["status"] == "done"
    assert result["stages"][1]["data"]["peak_count"] > 0

    raw_stage = stage_by_id(result, "raw")
    assert_keys(raw_stage["data"], {"filename", "point_count", "x_min", "x_max", "y_min", "y_max", "preview"})
    assert raw_stage["data"]["preview"]

    peak_stage = stage_by_id(result, "peak")
    assert_keys(peak_stage["data"], {"peak_count", "peaks"})
    assert_keys(peak_stage["parameters"], {"method", "max_peaks", "pywt_available"})

    match_stage = stage_by_id(result, "match")
    assert_keys(match_stage["data"], {"base_candidates", "matrix_elements", "spectral_matches", "rare_earth_distances", "confidence_calculation"})
    assert_keys(match_stage["parameters"], {"line_database", "match_tolerance_nm", "matrix_match_tolerance_nm", "conflict_filter"})
    confidence_calculation = match_stage["data"]["confidence_calculation"]
    assert_keys(confidence_calculation, {"formula", "temperature_gate", "scope_nm", "items", "total_count", "omitted_count"})
    assert confidence_calculation["items"]
    assert any(item["all_theoretical_comb"] for item in confidence_calculation["items"])
    first_confidence_item = confidence_calculation["items"][0]
    assert_keys(
        first_confidence_item,
        {
            "element",
            "ion",
            "confidence",
            "distance",
            "temperature",
            "r2",
            "line_count",
            "all_theoretical_comb",
            "matched_theoretical_comb",
            "matched_experimental_comb",
            "raw_peak_marks",
            "normalization",
            "representative_selection",
        },
    )

    temperature_stage = stage_by_id(result, "temperature")
    assert temperature_stage["id"] == "temperature"
    assert_keys(temperature_stage["data"], {"trace", "starts", "best_start_index", "best_score", "temperature"})
    assert_keys(temperature_stage["parameters"], {"t_min", "t_max", "multistart_count", "iterations", "tolerance", "candidate_mode", "top_k", "alpha"})
    assert len(temperature_stage["data"]["starts"]) > 1
    assert any(start["selected"] for start in temperature_stage["data"]["starts"])
    assert temperature_stage["parameters"]["iterations"] == 12
    assert temperature_stage["parameters"]["multistart_count"] == 10
    assert temperature_stage["parameters"]["t_min"] == 5000.0
    assert temperature_stage["parameters"]["t_max"] == 20000.0
    assert temperature_stage["parameters"]["tolerance"] == 1e-5
    assert temperature_stage["parameters"]["candidate_mode"] == "alterable"

    fit_stage = stage_by_id(result, "fit")
    assert_keys(
        fit_stage["data"],
        {
            "target",
            "target_element",
            "requested_fit_target",
            "window_nm",
            "fit_candidates",
            "components",
            "rms",
            "before_confidence",
            "after_confidence",
            "real_multipeak_fit",
            "raw_points",
            "component_curves",
            "sum_fit_points",
            "fitted_peaks",
            "local_extrema",
            "residual_points",
            "baseline",
            "component_count",
            "fallback_reason",
            "parity_gap",
            "confidence_rescue",
        },
    )
    assert_keys(fit_stage["parameters"], {"model", "real_multipeak_fit"})

    result_stage = stage_by_id(result, "result")
    assert_keys(result_stage["data"], {"rare_earth_results", "detection_threshold"})
    assert result_stage["data"]["rare_earth_results"]
    assert result["result_csv"].startswith("element,detected,confidence")

    samples = list_sample_files()
    sample_paths = {sample["path"] for sample in samples}
    sample_roots = {path.split("/")[0] for path in sample_paths}
    assert "RREs/070101_95.csv" in sample_paths
    assert {"RREs", "GBW", "Broaden_research"}.issubset(sample_roots)

    rre_path = Path("RREs/070101_95.csv")
    rre_text = rre_path.read_text(encoding="utf-8", errors="ignore")
    rre_result = run_pipeline(rre_text, rre_path.name)
    rre_match_stage = stage_by_id(rre_result, "match")
    rre_confidence_calculation = rre_match_stage["data"]["confidence_calculation"]
    ybii_confidence_item = next(item for item in rre_confidence_calculation["items"] if item["ion"] == "YbII")
    assert ybii_confidence_item["representative_selection"]["selected"]
    assert ybii_confidence_item["all_theoretical_comb"]
    assert len(ybii_confidence_item["matched_theoretical_comb"]) == len(ybii_confidence_item["matched_experimental_comb"])
    assert len(ybii_confidence_item["raw_peak_marks"]["selected_experimental_peaks"]) == len(ybii_confidence_item["matched_experimental_comb"])
    assert abs(sum(row["normalized_intensity"] for row in ybii_confidence_item["matched_theoretical_comb"]) - 1.0) < 5e-3
    assert abs(sum(row["normalized_intensity"] for row in ybii_confidence_item["matched_experimental_comb"]) - 1.0) < 5e-3
    rre_fit_stage = stage_by_id(rre_result, "fit")
    assert rre_fit_stage["data"]["target_element"] == "Yb"
    assert rre_fit_stage["data"]["fit_candidates"]
    assert rre_fit_stage["data"]["components"]
    assert len(rre_fit_stage["data"]["raw_points"]) >= 8
    assert rre_fit_stage["data"]["component_curves"]
    assert len(rre_fit_stage["data"]["sum_fit_points"]) >= 8
    assert rre_fit_stage["data"]["fitted_peaks"]
    assert rre_fit_stage["data"]["local_extrema"]
    rre_window = rre_fit_stage["data"]["window_nm"]
    assert rre_window and (rre_window[1] - rre_window[0]) < 1.3
    rre_candidates = rre_fit_stage["data"]["fit_candidates"]
    assert rre_fit_stage["data"]["component_count"] == len(rre_candidates)
    assert len(rre_fit_stage["data"]["component_curves"]) == len(rre_candidates)
    assert len(rre_fit_stage["data"]["fitted_peaks"]) == len(rre_candidates)
    assert [row["center"] for row in rre_candidates] == [row["center"] for row in rre_fit_stage["data"]["component_curves"]]
    assert [row["center"] for row in rre_candidates] == [row["wavelength"] for row in rre_fit_stage["data"]["fitted_peaks"]]
    assert len([row for row in rre_candidates if row["source"] == "matrix"]) == 2
    assert rre_fit_stage["data"]["component_count"] == 3
    assert rre_fit_stage["data"]["confidence_rescue"]["reason"] == "coarse_confidence_not_zero"
    rre_result_stage = stage_by_id(rre_result, "result")
    rre_yb = next(row for row in rre_result_stage["data"]["rare_earth_results"] if row["element"] == "Yb")
    assert rre_yb["confidence"] == rre_fit_stage["data"]["before_confidence"]

    requested_result = run_pipeline(
        rre_text,
        rre_path.name,
        fit_target={"element": "Yb", "ion": "YbII", "wavelength": 328.937, "source": "coarse_matched"},
    )
    requested_fit_stage = stage_by_id(requested_result, "fit")
    requested_candidates = requested_fit_stage["data"]["fit_candidates"]
    assert requested_fit_stage["data"]["requested_fit_target"]["source"] == "coarse_matched"
    assert requested_candidates[0]["source"] == "coarse_matched"
    assert requested_candidates[0]["element"] == "Yb"
    assert abs(requested_candidates[0]["center"] - 328.937) < 1e-4

    direct_boost_rows = _final_results(
        {"Yb": 0.01},
        {"Yb": 10000.0},
        {"Yb": 0.8},
        {"Yb": 3},
        {"target_element": "Yb", "after_confidence": 0.7},
    )
    direct_boost_yb = next(row for row in direct_boost_rows if row["element"] == "Yb")
    assert direct_boost_yb["confidence"] == 0.01, "final results must not directly use fit after_confidence as a boost"

    rescue_rows = _final_results(
        {"Yb": 0.0},
        {"Yb": 10000.0},
        {"Yb": 0.0},
        {"Yb": 1},
        {
            "target_element": "Yb",
            "after_confidence": 0.7,
            "confidence_rescue": {
                "applied": True,
                "target_element": "Yb",
                "recomputed_confidence": 0.23,
                "temperature": 12345.0,
                "r2": 0.67,
                "matched": 4,
            },
        },
    )
    rescue_yb = next(row for row in rescue_rows if row["element"] == "Yb")
    assert rescue_yb["confidence"] == 0.23
    assert rescue_yb["temperature"] == 12345.0
    assert rescue_yb["r2"] == 0.67
    assert rescue_yb["matched"] == 4


if __name__ == "__main__":
    _run_self_tests()

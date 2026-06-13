from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from backend.pipeline import run_pipeline
except ModuleNotFoundError:
    from pipeline import run_pipeline


STAGE_ORDER = ["raw", "peak", "match", "temperature", "fit", "result"]

TOP_LEVEL_KEYS = {"filename", "stages", "result_csv", "notes"}
STAGE_KEYS = {"id", "title", "status", "summary", "data"}

STAGE_DATA_KEYS = {
    "raw": {"filename", "point_count", "x_min", "x_max", "y_min", "y_max", "preview"},
    "peak": {"peak_count", "peaks"},
    "match": {
        "base_candidates",
        "matrix_elements",
        "spectral_matches",
        "rare_earth_distances",
        "confidence_calculation",
    },
    "temperature": {"trace", "starts", "best_start_index", "best_score", "temperature"},
    "fit": {
        "target",
        "target_element",
        "window_nm",
        "components",
        "rms",
        "before_confidence",
        "after_confidence",
        "raw_points",
        "component_curves",
        "sum_fit_points",
        "fitted_peaks",
        "fit_candidates",
        "local_extrema",
        "residual_points",
        "baseline",
        "component_count",
        "fallback_reason",
        "real_multipeak_fit",
    },
    "result": {"rare_earth_results", "detection_threshold"},
}

STAGE_PARAMETER_KEYS = {
    "peak": {"method", "max_peaks", "pywt_available"},
    "match": {"line_database", "match_tolerance_nm", "matrix_match_tolerance_nm", "conflict_filter"},
    "temperature": {"t_min", "t_max", "multistart_count", "iterations", "top_k", "alpha"},
    "fit": {"model", "real_multipeak_fit"},
}


class ContractError(AssertionError):
    """Raised when a backend response violates the documented API contract."""


def _require_mapping(value, label):
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _require_sequence(value, label):
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    return value


def _require_keys(mapping, keys, label):
    missing = sorted(set(keys) - set(mapping))
    if missing:
        raise ContractError(f"{label} missing keys: {missing}")


def _stage_map(result):
    stages = _require_sequence(result.get("stages"), "result.stages")
    stage_ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
    if stage_ids != STAGE_ORDER:
        raise ContractError(f"stage order mismatch: expected {STAGE_ORDER}, got {stage_ids}")
    return {stage["id"]: stage for stage in stages}


def _validate_point_rows(rows, label, min_rows=1):
    rows = _require_sequence(rows, label)
    if len(rows) < min_rows:
        raise ContractError(f"{label} must contain at least {min_rows} row(s)")
    first = _require_mapping(rows[0], f"{label}[0]")
    _require_keys(first, {"x", "y"}, f"{label}[0]")


def _validate_temperature_stage(stage):
    data = stage["data"]
    starts = _require_sequence(data.get("starts"), "temperature.data.starts")
    if not starts:
        raise ContractError("temperature.data.starts must not be empty")
    selected_count = sum(1 for start in starts if isinstance(start, dict) and start.get("selected"))
    if selected_count != 1:
        raise ContractError(f"temperature.data.starts must mark exactly one selected start, got {selected_count}")
    first_trace = _require_sequence(starts[0].get("trace"), "temperature.data.starts[0].trace")
    if not first_trace:
        raise ContractError("temperature.data.starts[0].trace must not be empty")
    _require_keys(
        _require_mapping(first_trace[0], "temperature.data.starts[0].trace[0]"),
        {"iteration", "temperature", "target_temperature", "candidate", "confidence", "r2", "score", "delta"},
        "temperature.data.starts[0].trace[0]",
    )


def _normalized_sum(rows, label):
    if not rows:
        return 0.0
    values = []
    for index, row in enumerate(rows):
        row = _require_mapping(row, f"{label}[{index}]")
        if "normalized_intensity" not in row:
            raise ContractError(f"{label}[{index}] missing normalized_intensity")
        value = row.get("normalized_intensity")
        if value is None:
            return None
        try:
            values.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ContractError(f"{label}[{index}].normalized_intensity must be numeric or null") from exc
    return sum(values)


def _validate_normalized_comb(rows, label):
    total = _normalized_sum(rows, label)
    if total is None:
        return
    if rows and abs(float(total) - 1.0) > 5e-3:
        raise ContractError(f"{label} normalized_intensity sum must be close to 1, got {total:.6f}")
    if not rows and total != 0.0:
        raise ContractError(f"{label} empty normalized_intensity sum must be 0")


def _validate_confidence_calculation(stage):
    data = stage["data"]
    calculation = _require_mapping(data.get("confidence_calculation"), "match.data.confidence_calculation")
    _require_keys(
        calculation,
        {"formula", "temperature_gate", "scope_nm", "items", "total_count", "omitted_count"},
        "match.data.confidence_calculation",
    )
    _require_mapping(calculation.get("formula"), "match.data.confidence_calculation.formula")
    _require_mapping(calculation.get("temperature_gate"), "match.data.confidence_calculation.temperature_gate")
    items = _require_sequence(calculation.get("items"), "match.data.confidence_calculation.items")
    if not items:
        raise ContractError("match.data.confidence_calculation.items must not be empty")
    if not any(item.get("all_theoretical_comb") for item in items if isinstance(item, dict)):
        raise ContractError("at least one confidence_calculation item must include all_theoretical_comb")

    for index, raw_item in enumerate(items):
        item = _require_mapping(raw_item, f"match.data.confidence_calculation.items[{index}]")
        _require_keys(
            item,
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
            f"match.data.confidence_calculation.items[{index}]",
        )
        all_theoretical = _require_sequence(
            item.get("all_theoretical_comb"),
            f"match.data.confidence_calculation.items[{index}].all_theoretical_comb",
        )
        if all_theoretical:
            _require_keys(
                _require_mapping(all_theoretical[0], f"match.data.confidence_calculation.items[{index}].all_theoretical_comb[0]"),
                {"wavelength", "intensity", "normalized_intensity", "A", "E", "g", "status"},
                f"match.data.confidence_calculation.items[{index}].all_theoretical_comb[0]",
            )
        matched_theoretical = _require_sequence(
            item.get("matched_theoretical_comb"),
            f"match.data.confidence_calculation.items[{index}].matched_theoretical_comb",
        )
        matched_experimental = _require_sequence(
            item.get("matched_experimental_comb"),
            f"match.data.confidence_calculation.items[{index}].matched_experimental_comb",
        )
        if matched_theoretical or matched_experimental:
            if len(matched_theoretical) != len(matched_experimental):
                raise ContractError(
                    "matched_theoretical_comb and matched_experimental_comb must have the same length "
                    f"for item {item.get('ion')}: {len(matched_theoretical)} != {len(matched_experimental)}"
                )
            _require_keys(
                _require_mapping(matched_theoretical[0], f"match.data.confidence_calculation.items[{index}].matched_theoretical_comb[0]"),
                {"wavelength", "intensity", "normalized_intensity", "matched_idx"},
                f"match.data.confidence_calculation.items[{index}].matched_theoretical_comb[0]",
            )
            _require_keys(
                _require_mapping(matched_experimental[0], f"match.data.confidence_calculation.items[{index}].matched_experimental_comb[0]"),
                {"wavelength", "intensity", "normalized_intensity", "delta_nm"},
                f"match.data.confidence_calculation.items[{index}].matched_experimental_comb[0]",
            )
        _validate_normalized_comb(
            matched_theoretical,
            f"match.data.confidence_calculation.items[{index}].matched_theoretical_comb",
        )
        _validate_normalized_comb(
            matched_experimental,
            f"match.data.confidence_calculation.items[{index}].matched_experimental_comb",
        )
        raw_peak_marks = _require_mapping(
            item.get("raw_peak_marks"),
            f"match.data.confidence_calculation.items[{index}].raw_peak_marks",
        )
        theoretical_wavelengths = _require_sequence(
            raw_peak_marks.get("theoretical_wavelengths"),
            f"match.data.confidence_calculation.items[{index}].raw_peak_marks.theoretical_wavelengths",
        )
        selected_peaks = _require_sequence(
            raw_peak_marks.get("selected_experimental_peaks"),
            f"match.data.confidence_calculation.items[{index}].raw_peak_marks.selected_experimental_peaks",
        )
        if all_theoretical and not theoretical_wavelengths:
            raise ContractError(f"raw_peak_marks.theoretical_wavelengths must be drawable for item {item.get('ion')}")
        if matched_experimental and not selected_peaks:
            raise ContractError(f"raw_peak_marks.selected_experimental_peaks must be drawable for item {item.get('ion')}")
        if selected_peaks:
            _require_keys(
                _require_mapping(selected_peaks[0], f"match.data.confidence_calculation.items[{index}].raw_peak_marks.selected_experimental_peaks[0]"),
                {"wavelength", "intensity", "theoretical_wavelength", "delta_nm"},
                f"match.data.confidence_calculation.items[{index}].raw_peak_marks.selected_experimental_peaks[0]",
            )


def _validate_fit_stage(stage, require_fit_plot_payload):
    data = stage["data"]
    fit_candidates = _require_sequence(data.get("fit_candidates"), "fit.data.fit_candidates")
    if not fit_candidates and not data.get("fallback_reason"):
        raise ContractError("fit.data.fallback_reason must explain an empty fit_candidates payload")
    if not require_fit_plot_payload:
        return
    _validate_point_rows(data.get("raw_points"), "fit.data.raw_points", min_rows=8)
    _validate_point_rows(data.get("sum_fit_points"), "fit.data.sum_fit_points", min_rows=8)
    if not fit_candidates:
        raise ContractError("fit.data.fit_candidates must not be empty")
    first_candidate = _require_mapping(fit_candidates[0], "fit.data.fit_candidates[0]")
    _require_keys(
        first_candidate,
        {"source", "element", "label", "center", "line_intensity", "line_type", "rank"},
        "fit.data.fit_candidates[0]",
    )
    component_curves = _require_sequence(data.get("component_curves"), "fit.data.component_curves")
    if not component_curves:
        raise ContractError("fit.data.component_curves must not be empty")
    first_curve = _require_mapping(component_curves[0], "fit.data.component_curves[0]")
    _require_keys(first_curve, {"label", "center", "amplitude", "sigma", "points"}, "fit.data.component_curves[0]")
    _validate_point_rows(first_curve.get("points"), "fit.data.component_curves[0].points", min_rows=8)
    fitted_peaks = _require_sequence(data.get("fitted_peaks"), "fit.data.fitted_peaks")
    if not fitted_peaks:
        raise ContractError("fit.data.fitted_peaks must not be empty")
    _require_keys(
        _require_mapping(fitted_peaks[0], "fit.data.fitted_peaks[0]"),
        {"label", "wavelength", "intensity", "amplitude", "sigma"},
        "fit.data.fitted_peaks[0]",
    )
    if data.get("target") and data.get("real_multipeak_fit"):
        expected_count = len(fit_candidates)
        if data.get("component_count") != expected_count:
            raise ContractError(f"fit.data.component_count must equal fit_candidates length: {data.get('component_count')} != {expected_count}")
        if len(component_curves) != expected_count:
            raise ContractError(f"fit.data.component_curves length must equal fit_candidates length: {len(component_curves)} != {expected_count}")
        if len(fitted_peaks) != expected_count:
            raise ContractError(f"fit.data.fitted_peaks length must equal fit_candidates length: {len(fitted_peaks)} != {expected_count}")

        candidate_centers = [round(float(row["center"]), 4) for row in fit_candidates]
        curve_centers = [round(float(row["center"]), 4) for row in component_curves]
        peak_centers = [round(float(row["wavelength"]), 4) for row in fitted_peaks]
        if curve_centers != candidate_centers:
            raise ContractError(f"fit.data.component_curves centers must align with fit_candidates: {curve_centers} != {candidate_centers}")
        if peak_centers != candidate_centers:
            raise ContractError(f"fit.data.fitted_peaks centers must align with fit_candidates: {peak_centers} != {candidate_centers}")
    local_extrema = _require_sequence(data.get("local_extrema"), "fit.data.local_extrema")
    if not local_extrema:
        raise ContractError("fit.data.local_extrema must not be empty")
    _require_keys(
        _require_mapping(local_extrema[0], "fit.data.local_extrema[0]"),
        {"wavelength", "intensity"},
        "fit.data.local_extrema[0]",
    )


def validate_pipeline_result(result, require_fit_plot_payload=False):
    result = _require_mapping(result, "result")
    _require_keys(result, TOP_LEVEL_KEYS, "result")
    stages = _stage_map(result)

    for stage_id in STAGE_ORDER:
        stage = _require_mapping(stages[stage_id], f"stage.{stage_id}")
        _require_keys(stage, STAGE_KEYS, f"stage.{stage_id}")
        data = _require_mapping(stage.get("data"), f"stage.{stage_id}.data")
        _require_keys(data, STAGE_DATA_KEYS[stage_id], f"stage.{stage_id}.data")
        if stage_id in STAGE_PARAMETER_KEYS:
            parameters = _require_mapping(stage.get("parameters"), f"stage.{stage_id}.parameters")
            _require_keys(parameters, STAGE_PARAMETER_KEYS[stage_id], f"stage.{stage_id}.parameters")

    _validate_point_rows(stages["raw"]["data"].get("preview"), "raw.data.preview", min_rows=1)
    _validate_confidence_calculation(stages["match"])
    _validate_temperature_stage(stages["temperature"])
    _validate_fit_stage(stages["fit"], require_fit_plot_payload)
    if not str(result.get("result_csv", "")).startswith("element,detected,confidence"):
        raise ContractError("result.result_csv must start with element,detected,confidence")
    return stages


def probe_sample(sample_path, require_fit_plot_payload=True):
    path = Path(sample_path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    result = run_pipeline(text, path.name)
    stages = validate_pipeline_result(result, require_fit_plot_payload=require_fit_plot_payload)
    fit_data = stages["fit"]["data"]
    match_data = stages["match"]["data"]
    temperature_data = stages["temperature"]["data"]
    result_summary = stages["result"]["summary"]
    fit_candidates = fit_data.get("fit_candidates", [])
    component_centers = [row.get("center") for row in fit_data.get("component_curves", [])]
    confidence_items = match_data.get("confidence_calculation", {}).get("items", [])
    target_confidence_item = next(
        (item for item in confidence_items if item.get("representative_selection", {}).get("selected")),
        max(confidence_items, key=lambda item: item.get("confidence", 0.0), default=None),
    )
    return {
        "sample": str(path),
        "stage_ids": [stage["id"] for stage in result["stages"]],
        "match": {
            "confidence_item_count": len(confidence_items),
            "confidence_total_count": match_data.get("confidence_calculation", {}).get("total_count"),
            "confidence_omitted_count": match_data.get("confidence_calculation", {}).get("omitted_count"),
            "target_confidence_item": None
            if target_confidence_item is None
            else {
                "ion": target_confidence_item.get("ion"),
                "element": target_confidence_item.get("element"),
                "selected": target_confidence_item.get("representative_selection", {}).get("selected"),
                "confidence": target_confidence_item.get("confidence"),
                "distance": target_confidence_item.get("distance"),
                "temperature": target_confidence_item.get("temperature"),
                "r2": target_confidence_item.get("r2"),
                "line_count": target_confidence_item.get("line_count"),
                "all_theoretical_count": len(target_confidence_item.get("all_theoretical_comb", [])),
                "matched_theoretical_count": len(target_confidence_item.get("matched_theoretical_comb", [])),
                "matched_experimental_count": len(target_confidence_item.get("matched_experimental_comb", [])),
                "raw_mark_count": len(target_confidence_item.get("raw_peak_marks", {}).get("selected_experimental_peaks", [])),
            },
        },
        "temperature": {
            "starts": len(temperature_data["starts"]),
            "selected_count": sum(1 for start in temperature_data["starts"] if start.get("selected")),
            "best_score": temperature_data["best_score"],
            "temperature": temperature_data["temperature"],
        },
        "fit": {
            "target": fit_data.get("target"),
            "target_candidate": fit_candidates[0] if fit_candidates else None,
            "matrix_candidates": [row for row in fit_candidates if row.get("source") == "matrix"][:2],
            "raw_points": len(fit_data.get("raw_points", [])),
            "fit_window": fit_data.get("window_nm"),
            "component_count": fit_data.get("component_count"),
            "fit_candidate_count": len(fit_candidates),
            "component_centers": component_centers,
            "component_curves": len(fit_data.get("component_curves", [])),
            "sum_fit_points": len(fit_data.get("sum_fit_points", [])),
            "fitted_peaks": len(fit_data.get("fitted_peaks", [])),
            "local_extrema": len(fit_data.get("local_extrema", [])),
            "fallback_reason": fit_data.get("fallback_reason"),
        },
        "result_summary": result_summary,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate the backend pipeline JSON contract.")
    parser.add_argument("sample", nargs="?", default="RREs/070101_95.csv", help="Spectrum sample path to run through backend.pipeline.run_pipeline")
    parser.add_argument(
        "--allow-empty-fit",
        action="store_true",
        help="Only require fit keys, not non-empty plot payload rows. Useful for non-rare-earth samples.",
    )
    args = parser.parse_args(argv)

    try:
        summary = probe_sample(args.sample, require_fit_plot_payload=not args.allow_empty_fit)
    except Exception as exc:
        print(f"contract failed: {exc}", file=sys.stderr)
        return 1

    print("contract ok")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

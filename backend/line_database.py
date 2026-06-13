from __future__ import annotations

import csv
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

try:
    from backend.spectrum import _as_float
except ModuleNotFoundError:
    from spectrum import _as_float


KB_EV = 8.617330350e-5


def _safe_row_float(row, index):
    if index >= len(row):
        return None
    return _as_float(row[index])


def _read_csv_rows(path):
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin1"):
        try:
            with path.open("r", encoding=encoding, errors="strict", newline="") as handle:
                return list(csv.reader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        rows = list(csv.reader(handle))
    if rows:
        return rows
    if last_error is not None:
        raise last_error
    return rows


def _split_elements(cell_value):
    text = str(cell_value or "").strip().upper()
    if not text:
        return []
    return [token for token in re.split(r"[,\s;/|+]+", text) if token]


def _line_enabled(row, main_elements, line_switch, include_matrix):
    enable_flag = str(row[8]).strip().upper() if len(row) > 8 else ""
    conflict_flag = row[9] if len(row) > 9 else ""
    base_enabled = enable_flag in {"", "Y"}

    if not main_elements:
        return base_enabled

    normalized_main = {str(element).strip().upper() for element in main_elements}
    conflict_tokens = _split_elements(conflict_flag)
    has_conflict_flag = bool(conflict_tokens)
    has_matrix_conflict = any(token in normalized_main for token in conflict_tokens)
    has_non_matrix_conflict = any(token not in normalized_main for token in conflict_tokens)

    if include_matrix:
        return base_enabled or has_matrix_conflict
    if line_switch:
        return (base_enabled or (has_conflict_flag and has_non_matrix_conflict)) and not has_matrix_conflict
    return base_enabled


def _relative_intensity(wavelength, transition_probability, energy, degeneracy, temperature):
    wavelength = np.asarray(wavelength, dtype=float)
    transition_probability = np.asarray(transition_probability, dtype=float)
    energy = np.asarray(energy, dtype=float)
    degeneracy = np.asarray(degeneracy, dtype=float)

    population = degeneracy * np.exp(-energy / (KB_EV * max(float(temperature), 1e-9)))
    partition = float(np.sum(population))
    if partition <= 0 or not math.isfinite(partition):
        weights = transition_probability * np.maximum(degeneracy, 1.0)
        total = float(np.sum(weights))
        return weights / total if total > 0 else np.zeros_like(wavelength)

    values = (transition_probability * population) / (partition * np.maximum(wavelength, 1e-9))
    total = float(np.sum(values))
    return values / total if total > 0 else values


@lru_cache(maxsize=128)
def _load_line_database_cached(folder_path, temperature_key, main_elements_key=(), line_switch=False, include_matrix=False):
    folder = Path(folder_path)
    temperature = float(temperature_key)
    main_elements = tuple(main_elements_key)
    elements = {}

    if not folder.exists():
        return elements

    for file_path in sorted(folder.glob("*.csv")):
        ion_name = file_path.stem
        rows = _read_csv_rows(file_path)
        numeric_rows = []
        for row in rows:
            wavelength_angstrom = _safe_row_float(row, 1)
            transition_probability = _safe_row_float(row, 2)
            energy_cm = _safe_row_float(row, 3)
            degeneracy = _safe_row_float(row, 7)
            if wavelength_angstrom is None or transition_probability is None or energy_cm is None or degeneracy is None:
                continue
            numeric_rows.append((row, wavelength_angstrom, transition_probability, energy_cm, degeneracy))

        wavelength = []
        transition_probability = []
        energy = []
        degeneracy = []
        for row, wavelength_angstrom, aki, energy_cm, g_value in numeric_rows[1::2]:
            if not _line_enabled(row, main_elements, line_switch, include_matrix):
                continue
            wavelength_nm = wavelength_angstrom * 0.1
            energy_ev = energy_cm * 1.2398e-4
            if not (200 <= wavelength_nm <= 900):
                continue
            if aki <= 0 or g_value <= 0:
                continue
            wavelength.append(wavelength_nm)
            transition_probability.append(aki)
            energy.append(energy_ev)
            degeneracy.append(g_value)

        if not wavelength:
            continue

        wavelength_arr = np.asarray(wavelength, dtype=float)
        aki_arr = np.asarray(transition_probability, dtype=float)
        energy_arr = np.asarray(energy, dtype=float)
        g_arr = np.asarray(degeneracy, dtype=float)
        rel_intensity = _relative_intensity(wavelength_arr, aki_arr, energy_arr, g_arr, temperature)
        matrix = np.column_stack((wavelength_arr, rel_intensity, aki_arr, energy_arr, g_arr))
        order = np.argsort(matrix[:, 0], kind="mergesort")
        elements[ion_name] = {"data": matrix[order]}

    return elements


def load_line_database(folder_path, temperature, main_elements=(), line_switch=False, include_matrix=False):
    rounded_temperature = round(float(temperature), 2)
    main_elements_key = tuple(sorted({str(element) for element in main_elements}))
    return _load_line_database_cached(str(Path(folder_path).resolve()), rounded_temperature, main_elements_key, line_switch, include_matrix)

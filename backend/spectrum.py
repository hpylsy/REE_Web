from __future__ import annotations

import math

import numpy as np


def _as_float(token):
    try:
        value = float(token.strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _numeric_values(line):
    normalized = (
        line.replace(",", " ")
        .replace(";", " ")
        .replace("\t", " ")
        .replace("\ufeff", " ")
    )
    values = []
    for token in normalized.split():
        value = _as_float(token)
        if value is not None:
            values.append(value)
    return values


def _downsample_xy(x, y, max_points=1200):
    if x.size <= max_points:
        idx = np.arange(x.size)
    else:
        idx = np.linspace(0, x.size - 1, max_points).astype(int)
    return [{"x": float(x[i]), "y": float(y[i])} for i in idx]


def parse_spectrum_text(text, filename="uploaded-spectrum"):
    rows = []
    for line in text.splitlines():
        values = _numeric_values(line)
        if len(values) < 2:
            continue
        x_value = values[0]
        y_value = values[1]
        rows.append((x_value, y_value))

    if len(rows) < 8:
        raise ValueError("光谱有效数值行不足，至少需要 8 行波长-强度数据")

    data = np.asarray(rows, dtype=float)
    valid_mask = np.isfinite(data[:, 0]) & np.isfinite(data[:, 1])
    data = data[valid_mask]
    if data.shape[0] < 8:
        raise ValueError("光谱有效数值行不足，至少需要 8 行波长-强度数据")

    order = np.argsort(data[:, 0], kind="mergesort")
    x = data[order, 0]
    y = data[order, 1]

    unique_mask = np.concatenate([[True], np.diff(x) > 0])
    x = x[unique_mask]
    y = y[unique_mask]
    if x.size < 8:
        raise ValueError("光谱波长列有效点不足")

    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_range = y_max - y_min if y_max != y_min else 1.0
    y_normalized = (y - y_min) / y_range

    return {
        "filename": filename,
        "point_count": int(x.size),
        "x": x.tolist(),
        "y": y.tolist(),
        "y_normalized": y_normalized.tolist(),
        "x_min": float(x[0]),
        "x_max": float(x[-1]),
        "y_min": y_min,
        "y_max": y_max,
        "preview": _downsample_xy(x, y_normalized),
    }

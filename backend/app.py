from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    from backend.pipeline import list_sample_files, refit_pipeline_result, run_pipeline_with_context
except ModuleNotFoundError:
    from pipeline import list_sample_files, refit_pipeline_result, run_pipeline_with_context


ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT_DIR / "web_app"
JOBS = {}
JOB_CONTEXTS = {}

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")


@app.after_request
def add_local_development_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _read_allowed_workspace_file(relative_path: str):
    path = (ROOT_DIR / relative_path).resolve()
    if not path.is_relative_to(ROOT_DIR):
        raise ValueError("sample_path 必须位于当前工作区内")
    if not path.is_file():
        raise FileNotFoundError(f"找不到光谱文件: {relative_path}")
    return path.read_text(encoding="utf-8", errors="ignore"), path.name


def _fit_target_from_mapping(mapping):
    raw_target = mapping.get("fit_target") if mapping is not None else None
    fit_target = {}

    if isinstance(raw_target, dict):
        fit_target.update(raw_target)
    elif isinstance(raw_target, str) and raw_target.strip():
        text = raw_target.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            fit_target["element"] = text
        else:
            if isinstance(parsed, dict):
                fit_target.update(parsed)
            else:
                fit_target["element"] = str(parsed)

    aliases = {
        "fit_target_element": "element",
        "fit_target_ion": "ion",
        "fit_target_wavelength": "wavelength",
        "fit_target_source": "source",
    }
    for source_key, target_key in aliases.items():
        value = mapping.get(source_key) if mapping is not None else None
        if value not in (None, ""):
            fit_target[target_key] = value

    if "wavelength" in fit_target:
        try:
            fit_target["wavelength"] = float(fit_target["wavelength"])
        except (TypeError, ValueError) as exc:
            raise ValueError("fit_target_wavelength 必须是数字") from exc

    cleaned = {key: value for key, value in fit_target.items() if value not in (None, "")}
    return cleaned or None


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _realtime_port_record(path: Path, source: str, by_id: Path | None = None):
    serial_path = by_id or path
    target = _safe_resolve(path)
    serial_path_text = str(serial_path)
    record = {
        "path": serial_path_text,
        "label": serial_path_text,
        "source": source,
        "target": str(target),
        "accessible": os.access(serial_path, os.R_OK | os.W_OK),
    }
    if by_id is not None:
        record["by_id"] = str(by_id)
        record["label"] = f"{by_id.name} -> {target}"
    return record


def list_realtime_ports(dev_root: Path = Path("/dev")):
    ports_by_target = {}

    for source, pattern in (("ttyUSB", "ttyUSB*"), ("ttyACM", "ttyACM*")):
        for path in sorted(dev_root.glob(pattern)):
            if not path.exists():
                continue
            target_key = str(_safe_resolve(path))
            ports_by_target[target_key] = _realtime_port_record(path, source)

    by_id_dir = dev_root / "serial" / "by-id"
    if by_id_dir.is_dir():
        for by_id in sorted(by_id_dir.iterdir()):
            target = _safe_resolve(by_id)
            target_key = str(target)
            ports_by_target[target_key] = _realtime_port_record(target, "by-id", by_id=by_id)

    return sorted(ports_by_target.values(), key=lambda port: port["label"])


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "libs-rre-backend"})


@app.get("/api/samples")
def samples():
    return jsonify({"samples": list_sample_files(ROOT_DIR)})


@app.get("/api/realtime/ports")
def realtime_ports():
    ports = list_realtime_ports()
    message = f"检测到 {len(ports)} 个采集板候选端口" if ports else "未检测到采集板端口"
    return jsonify({"ports": ports, "count": len(ports), "message": message})


@app.post("/api/pipeline/run")
def run_detection_pipeline():
    filename = "uploaded-spectrum"
    fit_target = None

    try:
        if request.files.get("file") is not None:
            file_obj = request.files["file"]
            filename = file_obj.filename or filename
            text = file_obj.read().decode("utf-8", errors="ignore")
            fit_target = _fit_target_from_mapping(request.form)
        else:
            payload = request.get_json(silent=True) or {}
            fit_target = _fit_target_from_mapping(payload)
            if payload.get("sample_path"):
                text, filename = _read_allowed_workspace_file(str(payload["sample_path"]))
            elif payload.get("text"):
                text = str(payload["text"])
                filename = str(payload.get("filename") or filename)
            else:
                return jsonify({"error": "请上传 file，或提供 sample_path/text"}), 400

        result, context = run_pipeline_with_context(text, filename, fit_target=fit_target)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    job_id = uuid.uuid4().hex
    result["job_id"] = job_id
    JOBS[job_id] = result
    JOB_CONTEXTS[job_id] = context
    return jsonify(result)


@app.get("/api/pipeline/<job_id>")
def get_pipeline_result(job_id):
    result = JOBS.get(job_id)
    if result is None:
        return jsonify({"error": "job_id 不存在或服务已重启"}), 404
    return jsonify(result)


@app.post("/api/pipeline/<job_id>/fit")
def rerun_pipeline_fit(job_id):
    result = JOBS.get(job_id)
    context = JOB_CONTEXTS.get(job_id)
    if result is None or context is None:
        return jsonify({"error": "job_id 不存在、服务已重启，或缺少可复用的拟合上下文"}), 404

    try:
        mapping = request.get_json(silent=True) if request.is_json else request.form
        fit_target = _fit_target_from_mapping(mapping or {})
        updated = refit_pipeline_result(result, context, fit_target=fit_target)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    updated["job_id"] = job_id
    JOBS[job_id] = updated
    return jsonify(updated)


@app.get("/api/pipeline/<job_id>/result.csv")
def get_pipeline_csv(job_id):
    result = JOBS.get(job_id)
    if result is None:
        return jsonify({"error": "job_id 不存在或服务已重启"}), 404
    return Response(
        result["result_csv"],
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rareearth_detection_result.csv"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

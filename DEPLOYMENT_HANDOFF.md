# LIBS Rare Earth Web App Deployment Handoff

## Current Deployment

- Server: Aliyun ECS, Ubuntu 22.04, public IP `8.134.144.84`
- Public URL: `http://8.134.144.84`
- App directory: `/opt/rre-libs`
- Python venv: `/opt/rre-libs/.venv`
- Runtime user: `rre-libs`
- WSGI entry: `backend.app:app`
- Production backend bind: `127.0.0.1:5000`
- Public entry: Nginx port `80` -> `http://127.0.0.1:5000`

Do not expose port `5000` publicly. The Flask `app.run(... debug=True)` block in `backend/app.py` remains a local debug entry only.

## Uploaded Runtime Data

The deployed slice includes the code and data needed for current validation and first external use:

- `backend/`
- `web_app/`
- `Elements_database/`
- `Rareearth_pt3/`
- `RockBaseElemLines/`
- `Broaden_research/PureSample_Spectrum/`
- `MultiPeakfit/`
- `Fe-Ni_Spec/`
- `RREs/070101_95.csv`
- `RREs/Readme.md`
- `GBW/*.csv`

The full local `RREs/` directory was not uploaded. Only the current validation sample `RREs/070101_95.csv` is on the server.

## Service

Systemd service:

```bash
/etc/systemd/system/rre-libs.service
```

Common commands:

```bash
systemctl status rre-libs
systemctl restart rre-libs
systemctl stop rre-libs
journalctl -u rre-libs --no-pager -n 80
```

Service summary:

```ini
WorkingDirectory=/opt/rre-libs
ExecStart=/opt/rre-libs/.venv/bin/gunicorn -w 1 -b 127.0.0.1:5000 --timeout 180 backend.app:app
User=rre-libs
Restart=always
```

The server has about 2 vCPU / 2 GiB RAM, so deployment currently uses one Gunicorn worker.

## Nginx

Nginx site config:

```bash
/etc/nginx/sites-available/rre-libs
/etc/nginx/sites-enabled/rre-libs
```

Common commands:

```bash
nginx -t
systemctl reload nginx
tail -n 80 /var/log/nginx/error.log
```

The deployed server block listens on `80` with:

- `server_name 8.134.144.84`
- `client_max_body_size 50m`
- proxy timeouts set to `180s`
- `proxy_pass http://127.0.0.1:5000`

Existing `jackhuang.online` Nginx config was left untouched.

## Dependencies

Installed in `/opt/rre-libs/.venv`:

```bash
flask numpy scipy PyWavelets gunicorn
```

Do not install `SimspecGen/requirements.txt` as the Web app dependency set unless future runtime imports prove it is needed.

## Self-Test Commands

Run on the server:

```bash
cd /opt/rre-libs
.venv/bin/python -m compileall -q backend
.venv/bin/python backend/pipeline.py
.venv/bin/python -m backend.contract_probe RREs/070101_95.csv
.venv/bin/python -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

Health checks:

```bash
curl http://127.0.0.1:5000/api/health
curl http://8.134.144.84/api/health
```

Expected health response:

```json
{"service":"libs-rre-backend","status":"ok"}
```

## Latest Validation

Date: `2026-06-05 CST`

- Local release validation passed:
  - `node web_app/app.js`
  - `python3 -m compileall -q backend`
  - `python3 backend/pipeline.py`
  - `python3 -m backend.contract_probe RREs/070101_95.csv`
  - `python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit`
- Server backend self-tests passed with the same contract probe results:
  - `RREs/070101_95.csv`: result summary `Yb`, selected confidence item `YbII`, confidence `0.0779`, matched `5/6`, fit components `3`.
  - `Broaden_research/PureSample_Spectrum/Fe1.asc`: result summary `未检出`, fallback `no_enabled_matched_peak`.
- Public API validation passed:
  - `curl http://8.134.144.84/api/health`
  - `POST http://8.134.144.84/api/pipeline/run` with `RREs/070101_95.csv`
  - multipart upload of local `Fe1.asc`
  - CSV result endpoint returned `element,detected,confidence`.
- Browser validation passed at `http://8.134.144.84`:
  - initial page loads and import button is enabled.
  - actual browser API requests went to `http://8.134.144.84/api/pipeline/run`, not `127.0.0.1:5000`.
  - uploading `RREs/070101_95.csv` returned result `Yb`.
  - confidence stage showed `21/21` items and `YbII confidence 0.0779, matched 5/6`.
  - CSV, JSON, and summary export actions produced filenames.
  - uploading local `Fe1.asc` returned `未检出`.

Screenshot evidence saved locally:

```bash
/tmp/rre_public_initial.png
/tmp/rre_public_rre_result.png
/tmp/rre_public_confidence.png
/tmp/rre_public_fe_upload_result.png
```

## Known Limitations

- `job_id` results are stored in process memory; service restart invalidates old jobs and old CSV links.
- Current deployment is temporary HTTP only, with no HTTPS and no authentication.
- 1 Mbps bandwidth may make page load and especially large spectrum uploads slow.
- Only a minimal sample subset was uploaded, not the full local `RREs/` dataset.
- Aliyun security group should keep `80` open for external users and should not expose `5000`; `22` should be restricted to trusted sources when convenient.
- Headless Chrome validation emitted WebGL context warnings for the Three.js temperature view on this local GPU/headless environment; the deployment validation did not find failed API requests or JS exceptions.

## Next Work

Do not continue UI optimization or serial/RJ45 real-time acquisition in this deployment slice. Hand the next UI work back to the UI window, starting from `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md` Slice 1, "Offline Source UX Cleanup".

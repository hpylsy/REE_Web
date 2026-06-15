# REE Web Development Runbook

本文档给后续接手 `web_app` 的开发窗口使用。它不是产品说明书，而是开发、验证、排错和服务器同步的操作例程。

当前项目目录：

```bash
/home/hpy/RREdetectation-MultiPeakFit
```

## 1. 接手前先读

按这个顺序读，不要只看 README：

1. `web_app/app.js`
2. `web_app/index.html`
3. `web_app/styles.css`
4. `BACKEND_API_CONTRACT.md`
5. `HCI_INTERACTION_ROADMAP.md`
6. `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md`
7. `DEPLOYMENT_HANDOFF.md`
8. `progress.md` 尾部最近 150-250 行

开发判断以真实代码、运行结果、contract probe 和浏览器截图为准。旧 handoff 只能当历史背景，不能替代当前代码状态。

## 2. 硬边界

Web 改动默认优先只碰：

```bash
web_app/app.js
web_app/index.html
web_app/styles.css
```

普通 UI/HCI 切片不要超过 3 个业务文件。能只改 `web_app/app.js` 时优先只改它。

不要做这些事：

- 不改 backend 算法。
- 不改数据库和谱线数据文件。
- 不改 API 路径。
- 不改 stage id。
- 不改七个主阶段名：原始光谱、寻峰结果、谱线匹配、温度迭代、多峰拟合、置信度计算、检测结果。
- 不改检测数值。
- 不改 `confidence_calculation` payload。
- 不用前端 heuristics 推断 `fit.confidenceRescue`；它只能来自后端 payload normalization。
- `buildExportPayload()` 既有字段不能重命名、删除或改变含义；需要扩展时只能 append-only。
- 界面文案不要把系统写成 AI；继续用“系统 / 算法 / 工作站 / 操作者”。

## 3. 本地启动

推荐本地 HTTP 方式：

```bash
cd /home/hpy/RREdetectation-MultiPeakFit
python3 backend/app.py
```

打开：

```text
http://127.0.0.1:5000
```

如果只想避免 Flask debug reloader，可以用：

```bash
python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
```

`file://` 打开 `web_app/index.html` 也能调本地 API，但前提是 `127.0.0.1:5000` 的 Flask 服务正在运行。优先用 HTTP 页面验收，只有离线报告或 file fallback 相关任务才专门测 `file://`。

## 4. 端口 5000 被占用

先查，不要直接 kill：

```bash
pgrep -af "python3 backend/app.py|backend/app.py|gunicorn|5000"
ss -ltnp | grep ':5000' || true
```

如果确认是本项目旧 Flask 进程，再正常停止：

```bash
kill <PID>
```

不要用 `kill -9` 作为第一选择。停止后再确认：

```bash
pgrep -af "python3 backend/app.py|backend/app.py"
```

常见现象：

- 页面跑出来的是旧代码。
- `/api/pipeline/run` 缺少新字段，例如 `confidence_calculation`。
- Selenium 截图和当前源码不一致。

这类情况通常是 5000 端口上还挂着旧 Flask 进程。先清进程，再用当前工作区重启。

## 5. Web 自检

前端自检入口：

```bash
node web_app/app.js
```

`runSelfTests()` 在 `web_app/app.js` 里。Web 改动必须尽量先补自检，再改实现。常见要覆盖：

- stage id 和阶段顺序没有变。
- `stageRows()` / `resultRows()` / `parameterRows()` 的关键字段还在。
- `buildExportPayload()` 旧字段还在。
- canvas 文案、坐标、标签不遮挡。
- `confidenceRescue` 不被前端推断。
- HCI review band 只作为 UI 标注，不改原始 confidence。

如果 `node web_app/app.js` 因旧断言失败，不要直接删断言。先读失败信息和附近代码，确认是需求变化、测试过期，还是新改动破坏了已有行为。

## 6. 后端契约回归

Web 改动也要跑：

```bash
python3 -m backend.contract_probe RREs/070101_95.csv
```

期望至少看到：

```text
contract ok
```

这条命令用于确认前端依赖的后端阶段和 payload 没被牵连。它不是算法完全等价测试，但对 Web 回归很有价值。

如果动了 Python 模块或怀疑 backend 受影响，再跑：

```bash
python3 -m compileall -q backend
python3 backend/pipeline.py
```

## 7. 空白和文件边界检查

每轮收尾跑：

```bash
git diff --check -- web_app/index.html web_app/app.js web_app/styles.css
git diff --name-only -- web_app/index.html web_app/app.js web_app/styles.css
git diff --stat -- web_app/index.html web_app/app.js web_app/styles.css
```

注意：这个工作区历史上出现过 `.git/` 状态不可靠的情况。不要只靠 `git status` 判断任务完成，必须结合实际命令、截图和文件内容。

## 8. 浏览器验收

可见布局、canvas、导出、日志、交互类改动都要用浏览器验收。当前本机稳妥路径是 Chrome + Selenium；不要假设 Node Playwright 可用。

基本流程：

```bash
python3 backend/app.py
```

另开脚本用 Selenium 打开：

```text
http://127.0.0.1:5000
```

至少检查：

- 页面能加载。
- 示例样本库能加载。
- 能提交检测任务。
- 能跑到检测结果。
- 改动涉及的阶段截图无遮挡、无横向溢出、无文本压叠。
- 底部证据日志没有压住主要内容。

常用溢出检查：

```js
const body = document.documentElement;
const log = document.querySelector(".event-log");
({
  pageOverflow: Math.max(0, body.scrollWidth - body.clientWidth),
  logOverflow: log ? Math.max(0, log.scrollWidth - log.clientWidth) : 0
})
```

截图建议放 `/tmp`，文件名写清日期和阶段，例如：

```bash
/tmp/rre-result-layout-confidence-label-20260615.png
/tmp/rre-evidence-log-complete-20260614.png
```

验收后停止 Flask，并确认没有残留进程。

## 9. 前端结构速查

`web_app/app.js` 里常用区域：

- `PROCESS_STAGES`：七个阶段定义，stage id 不要改。
- `normalizeBackendResult()`：后端 payload 到 `appState` 的入口。
- `normalizeConfidenceCalculation()`：`confidence_calculation` 归一化。
- `confidenceTrustSummary()`：置信度阶段的前端复核摘要。
- `resultDecisionSummary()`：检测结果阶段的候选结论、证据强弱、复核点。
- `stageExplanationRows()`：每阶段“输入 / 系统处理 / 输出证据 / 复核风险”。
- `stageRows()`：阶段证据表。
- `resultRows()`：右侧复核摘要。
- `parameterRows()`：参数确认。
- `drawRaw()` / `drawPeaks()` / `drawSpectralMatch()` / `drawTemperature()` / `drawFit()` / `drawConfidenceCalculation()` / `drawResult()`：主画布渲染。
- `pushLog()` / `normalizeEvidenceLogEntry()` / `stageEvidenceLogEntry()`：证据日志。
- `buildExportPayload()`：导出 JSON/HTML 的基础 payload，旧字段必须保留。
- `runSelfTests()`：前端自检。

## 10. HCI 文案规则

界面是 LIBS 稀土检测工作站，不写成 AI 产品。

推荐用语：

- 系统
- 算法
- 工作站
- 操作者
- 系统证据
- 复核点
- 导出前确认
- 候选结论
- 证据强弱

避免用语：

- AI 认为
- AI 诊断
- 自动判定无误
- 最终正确结论
- 绝对可靠

风险类文案只写“复核点 / 风险 / 待确认”，不要写成“算法错误”。前端 review reasons 是复核提示，不是后端诊断结论。

## 11. 置信度和结果页规则

置信度阶段必须保留原始 confidence 数值。review band 只是前端 UI 分层：

- `confidence >= 0.70`：证据较强
- `confidence >= 0.30`：待复核
- `confidence < 0.30`：证据不足

不要把 review band 写回 payload，不要改变原始 confidence。

`confidenceTrustSummary()` 的复核原因只能来自现有 payload 可读信息，例如：

- 置信度低
- distance 偏大
- R2 偏低
- 温度不在明确 gate 内
- 匹配谱线不足
- matched/all 比例偏低
- 该 ion 不是 representative
- 无 `confidence_calculation.items`

temperature gate 只有能解析出明确上下界时才判断越界。

## 12. 导出规则

当前导出入口包括 CSV、JSON、摘要、HTML 报告。任何导出字段变更都要遵守：

- 旧字段不删。
- 旧字段不重命名。
- 旧字段含义不变。
- 新字段只能 append-only。

如果新增 evidence chain 导出，要确认：

- `buildExportPayload()` 旧字段仍存在。
- 新字段是数组。
- HTML report 仍是单文件静态 HTML。
- 不引入外部脚本或 CDN。

## 13. 服务器 / VPS / ECS 当前记录

最近记录中的公网部署是阿里云 ECS，不是本机：

- 公网地址：`http://8.134.144.84`
- 服务器系统：Ubuntu 22.04
- 目录：`/opt/rre-libs`
- venv：`/opt/rre-libs/.venv`
- systemd：`rre-libs.service`
- WSGI：`backend.app:app`
- Gunicorn：`127.0.0.1:5000`
- 公网入口：Nginx `80 -> 127.0.0.1:5000`

如果后面迁到新加坡 VPS，先把这些项目重新核对一遍，不要照抄旧 IP：

```bash
pwd
ls -la /opt/rre-libs
systemctl status rre-libs
journalctl -u rre-libs --no-pager -n 80
ss -ltnp
nginx -t
tail -n 80 /var/log/nginx/error.log
curl http://127.0.0.1:5000/api/health
curl http://<公网IP>/api/health
```

生产上不要公开 5000 端口。安全组 / 防火墙只需要对外开放 80，SSH 22 限制可信来源更稳。

## 14. 同步到服务器

先本地验证，再同步。不要在服务器上直接改业务代码。

本地必跑：

```bash
node web_app/app.js
python3 -m backend.contract_probe RREs/070101_95.csv
git diff --check -- web_app/index.html web_app/app.js web_app/styles.css
```

同步前先 dry-run，看真实差异：

```bash
rsync -avcn web_app/app.js web_app/index.html web_app/styles.css <user>@<host>:/opt/rre-libs/web_app/
```

确认只包含本次需要的文件后再同步：

```bash
rsync -avc web_app/app.js web_app/index.html web_app/styles.css <user>@<host>:/opt/rre-libs/web_app/
```

如果只改了 `app.js`，就只同步 `app.js`。

服务器上重启：

```bash
sudo systemctl restart rre-libs
sudo systemctl is-active rre-libs
sudo journalctl -u rre-libs --no-pager -n 80
```

公网验证：

```bash
curl http://<公网IP>/api/health
```

浏览器打开公网地址，确认 API 请求走同源 `/api/...`，不要请求浏览器用户自己的 `127.0.0.1:5000`。

## 15. 服务器常见报错

### 15.1 公网页面请求 `127.0.0.1:5000`

症状：

- 公网页面能打开，但检测失败。
- 浏览器 Network 里请求 `http://127.0.0.1:5000/api/pipeline/run`。

原因：

- `resolveApiUrl()` 逻辑退回了本地调试路径。

处理：

- 公网 `http://` / `https://` 页面应该请求同源 `/api/...`。
- `file://` 页面才应该指向 `http://127.0.0.1:5000/api/...`。
- 修完后同步 `web_app/app.js`，重启服务，浏览器强刷。

### 15.2 `502 Bad Gateway`

先查 Gunicorn：

```bash
systemctl status rre-libs
journalctl -u rre-libs --no-pager -n 120
ss -ltnp | grep ':5000' || true
```

再查 Nginx：

```bash
nginx -t
tail -n 120 /var/log/nginx/error.log
```

常见原因：

- `rre-libs` 没启动。
- Python 依赖缺失。
- `/opt/rre-libs` 目录不完整。
- Nginx proxy_pass 指向错端口。

### 15.3 `504 Gateway Timeout` 或检测很久不返回

先看 service 日志：

```bash
journalctl -u rre-libs --no-pager -n 120
```

确认 Nginx 和 Gunicorn timeout。当前记录里都设为 `180s`。大文件和 1 Mbps 带宽会慢，先用 `RREs/070101_95.csv` 验证基本链路。

### 15.4 上传失败或 `413 Request Entity Too Large`

查 Nginx 配置是否有：

```nginx
client_max_body_size 50m;
```

改后：

```bash
nginx -t
systemctl reload nginx
```

### 15.5 `/vendor/three.min.js` 404 或温度 3D 不显示

服务器检查：

```bash
ls -lh /opt/rre-libs/web_app/vendor/three.min.js
curl -I http://<公网IP>/vendor/three.min.js
```

如果文件存在但浏览器仍慢，可能只是首次加载慢。当前实现会后台预加载 Three.js，后续还可考虑缓存头或压缩，但不要改成外部 CDN。

### 15.6 `/api/samples` 为空或样本缺失

服务器当前不是完整数据集，只上传了最小验证数据。检查：

```bash
find /opt/rre-libs/RREs -maxdepth 2 -type f | head
ls -lh /opt/rre-libs/RREs/070101_95.csv
```

如果需要更多样本，先确认数据量和带宽，再同步对应目录。不要误以为本地完整 `RREs/` 已经在服务器上。

### 15.7 `ModuleNotFoundError`

进入服务器目录和 venv：

```bash
cd /opt/rre-libs
. .venv/bin/activate
python -m compileall -q backend
python -m backend.contract_probe RREs/070101_95.csv
```

当前 Web app 依赖记录：

```bash
flask numpy scipy PyWavelets gunicorn
```

不要直接安装 `SimspecGen/requirements.txt` 当 Web app 依赖集，除非有实际 import 证明需要。

### 15.8 新加坡 VPS 访问慢或打不开

先分层检查：

```bash
ping <公网IP>
curl -I http://<公网IP>/
curl http://<公网IP>/api/health
ssh <user>@<公网IP>
```

服务器内检查：

```bash
ss -ltnp
systemctl status nginx
systemctl status rre-libs
ufw status
```

云平台检查：

- 安全组是否开放 80。
- 是否把 5000 暴露到公网；不要暴露。
- 公网 IP 是否是当前机器。
- DNS 是否指向旧机器。

如果页面能打开但检测失败，优先看浏览器 Network 的 API URL 和 `journalctl -u rre-libs`。

## 16. 常见本地报错

### 16.1 `node web_app/app.js` 报某 helper 未定义

通常是前端 helper 顺序或重命名漏改。用：

```bash
rg -n "helperName" web_app/app.js
```

确认定义和调用都在。不要删自检绕过。

### 16.2 contract probe 报 `No module named backend.contract_probe`

确认当前目录：

```bash
pwd
ls backend/contract_probe.py
```

必须在 `/home/hpy/RREdetectation-MultiPeakFit` 根目录跑：

```bash
python3 -m backend.contract_probe RREs/070101_95.csv
```

### 16.3 浏览器截图和源码不一致

常见原因：

- Flask 旧进程未停。
- 浏览器缓存。
- 服务跑的不是当前工作区。

处理：

```bash
pgrep -af "backend/app.py|gunicorn"
pwd
```

重启 Flask 后浏览器强刷。

### 16.4 Headless Chrome WebGL warning

温度 3D 页面在 headless 环境可能出现 WebGL context warning。只要没有 failed API request、没有 JS exception、canvas 非空并且交互/动画检查通过，可以记录为环境 warning。

### 16.5 Playwright 不可用

当前环境更稳的是 `google-chrome` + Selenium。不要在没有安装 Node Playwright 的情况下硬切验证工具。

## 17. 最小开发循环

普通 Web 修复建议按这个节奏：

1. 读相关代码和现有自检。
2. 写一个能失败的 `runSelfTests()` 断言。
3. 跑 `node web_app/app.js`，确认 RED。
4. 最小改实现。
5. 跑 `node web_app/app.js`，确认 GREEN。
6. 跑 `python3 -m backend.contract_probe RREs/070101_95.csv`。
7. 跑 `git diff --check -- web_app/index.html web_app/app.js web_app/styles.css`。
8. 如果改 UI/canvas/layout，跑 Flask + Chrome/Selenium 截图。
9. 交付时列出文件、验证命令、截图路径、未触碰边界。

## 18. 交付模板

每次 Web 改动交付至少包含：

```text
改动文件：
- web_app/app.js

改动内容：
- ...

验证：
- node web_app/app.js：通过
- python3 -m backend.contract_probe RREs/070101_95.csv：contract ok
- git diff --check -- web_app/index.html web_app/app.js web_app/styles.css：通过
- Chrome/Selenium 截图：/tmp/...

边界：
- 未改 backend / API / stage id / 检测数值
- 未改 confidence_calculation payload
- 未新增前端 confidenceRescue 推断
- buildExportPayload 旧字段保持
```

## 19. 关键资料索引

- `BACKEND_API_CONTRACT.md`：前后端 payload 契约。
- `HCI_INTERACTION_ROADMAP.md`：HCI 改造顺序和边界。
- `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md`：页面工作流和实时采集架构。
- `DEPLOYMENT_HANDOFF.md`：公网部署记录。
- `HANDOFF_NEXT_WINDOW.md`：历史接手提示和启动方式。
- `COORDINATOR_HANDOFF.md`：多窗口统筹和派发模板。
- `progress.md`：历史操作日志和验证证据。

如果这些文档和当前代码冲突，以当前代码、contract probe、浏览器截图为准。

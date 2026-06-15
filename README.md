# LIBS 稀土元素检测工作站

本项目用于 LIBS 光谱的稀土元素自动识别与复核展示。当前 Web 版本把原始光谱、寻峰、谱线匹配、温度迭代、多峰拟合、置信度计算和检测结果组织成一个工作站界面，方便操作者查看系统证据、复核低置信或重叠谱线，并导出检测结果。

> 界面中的“系统 / 算法 / 工作站”表示程序生成的证据；最终样本来源、参数、复核点和报告导出仍需要操作者确认。

## 在线访问

当前演示部署地址：

```text
http://8.134.144.84
```

说明：

- 当前是 HTTP 演示部署，没有 HTTPS 和登录鉴权。
- 公网入口由 Nginx 代理到服务器本机 `127.0.0.1:5000`，不要直接访问或暴露 5000 端口。
- 公网样本库是部署用的最小数据集，不一定包含本地完整数据。

## 功能概览

Web 工作站包含七个主阶段：

1. 原始光谱：解析波长-强度数据并预览光谱。
2. 寻峰结果：生成候选峰。
3. 谱线匹配：匹配稀土谱线、基体重叠和低置信谱线。
4. 温度迭代：展示温度多起点迭代和收敛证据。
5. 多峰拟合：对目标窗口进行 Gaussian 多峰分解。
6. 置信度计算：展示原始 confidence、证据强弱、distance、T gate、R2、matched/all 和复核原因。
7. 检测结果：展示候选结论、证据强弱、复核点、导出确认和稀土结果明细。

支持的导出：

- CSV
- JSON
- 文本摘要
- HTML 单文件报告

## 本地快速开始

### 方式 A：Windows 一键启动

Windows 用户进入项目根目录后，可以直接运行：

```powershell
.\deploy_windows.ps1
```

脚本会自动：

- 创建 `.venv`
- 安装 Web 运行依赖
- 检查示例样本库
- 启动本地服务
- 调用接口做烟测
- 打开浏览器

只做预检、不启动服务：

```powershell
.\deploy_windows.ps1 -SmokeOnly
```

指定端口：

```powershell
.\deploy_windows.ps1 -Port 5050
```

不自动打开浏览器：

```powershell
.\deploy_windows.ps1 -NoBrowser
```

### 方式 B：Linux / macOS 手动启动

进入项目根目录，例如：

```bash
cd RREdetectation-MultiPeakFit
```

建议创建虚拟环境：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install flask numpy scipy PyWavelets
```

启动后端和 Web 页面：

```bash
python3 backend/app.py
```

打开浏览器：

```text
http://127.0.0.1:5000
```

如果只想用无 reloader 的稳定本地服务：

```bash
python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
```

## 使用流程

1. 打开页面。
2. 在左侧“操作者确认”中选择来源：
   - 离线分析：打开本地光谱或加载示例样本库。
   - 实时采集：当前是采集板工作流占位，未声明真实采集已完成。
3. 点击“重新加载示例样本库”，选择一个示例样本。
4. 点击“开始检测”。
5. 等待系统证据流程完成。
6. 在顶部阶段条或左侧流程列表切换阶段，查看每一步的证据：
   - 图谱主视图
   - 阶段证据表
   - 右侧当前证据、参数确认、复核摘要
   - 底部证据日志
7. 在“检测结果”阶段确认候选结论、证据强弱和复核点。
8. 通过右上角“导出”菜单导出 CSV、JSON、摘要或 HTML 报告。

## 支持的数据入口

本地 Web 支持：

- 示例样本库
- 单个光谱文件
- 文件夹导入

常见光谱格式由后端解析器处理，具体以 `backend/spectrum.py` 当前实现为准。

部署服务器上的样本库可能比本地少。若公网样本列表为空或缺失样本，先检查服务器是否同步了对应数据目录。

## 验证命令

前端和 Web/HCI 改动后，至少运行：

```bash
node web_app/app.js
python3 -m backend.contract_probe RREs/070101_95.csv
git diff --check -- web_app/index.html web_app/app.js web_app/styles.css
```

如果修改了后端 Python 模块，再运行：

```bash
python3 -m compileall -q backend
python3 backend/pipeline.py
```

如果修改了页面布局、canvas 绘制或导出交互，建议启动 Flask 后用 Chrome/Selenium 截图验收，确认没有遮挡、横向溢出或文本压叠。

## 常见问题

### 端口 5000 被占用

先查占用：

```bash
pgrep -af "python3 backend/app.py|backend/app.py|gunicorn|5000"
ss -ltnp | grep ':5000' || true
```

如果确认是本项目旧 Flask 进程，再正常停止：

```bash
kill <PID>
```

不要优先使用 `kill -9`。

### 页面打开了但检测失败

先检查后端是否正常：

```bash
curl http://127.0.0.1:5000/api/health
```

期望返回：

```json
{"service":"libs-rre-backend","status":"ok"}
```

再检查浏览器 Network 中 API 请求是否正确：

- 本地 HTTP 页面应该请求 `/api/...`。
- `file://` 页面会请求 `http://127.0.0.1:5000/api/...`。
- 公网页面应该请求同源公网 `/api/...`，不应该请求用户电脑自己的 `127.0.0.1:5000`。

### 运行 contract probe 报 `No module named backend.contract_probe`

确认你在项目根目录运行：

```bash
pwd
ls backend/contract_probe.py
python3 -m backend.contract_probe RREs/070101_95.csv
```

### 温度 3D 页面在 headless 环境有 WebGL warning

headless Chrome 可能输出 WebGL context warning。只要页面没有 JavaScript 异常、API 请求成功、canvas 非空且交互正常，可以记录为环境 warning。

## 阿里云部署说明

当前演示部署记录：

- 公网地址：`http://8.134.144.84`
- 远端目录：`/opt/rre-libs`
- Web 目录：`/opt/rre-libs/web_app`
- systemd 服务：`rre-libs.service`
- Gunicorn 监听：`127.0.0.1:5000`
- Nginx 入口：公网 80 端口代理到 `127.0.0.1:5000`

常用远端检查：

```bash
ssh root@8.134.144.84 'systemctl is-active rre-libs'
ssh root@8.134.144.84 'journalctl -u rre-libs --no-pager -n 80'
curl http://8.134.144.84/api/health
```

前端文件同步示例：

```bash
rsync -avc web_app/app.js root@8.134.144.84:/opt/rre-libs/web_app/app.js
ssh root@8.134.144.84 'systemctl restart rre-libs'
```

同步后建议校验公网文件哈希：

```bash
sha256sum web_app/app.js
curl -fsS http://8.134.144.84/app.js -o /tmp/rre-public-app.js
sha256sum /tmp/rre-public-app.js
```

更完整的部署和排错步骤见：

- `docs/DEPLOYMENT_HANDOFF.md`
- `docs/WEB_APP_DEVELOPMENT_RUNBOOK.md`

## 开发约束

Web/HCI 改动默认优先只改：

```text
web_app/app.js
web_app/index.html
web_app/styles.css
```

重要边界：

- 不改后端算法、数据库、API 路径、stage id 和检测数值。
- 不改 `confidence_calculation` payload。
- `fit.confidenceRescue` 只能来自后端 payload normalization，不能在前端推断。
- `buildExportPayload()` 既有字段不能删除、重命名或改变含义；需要扩展时只能 append-only。
- 界面文案继续使用“系统 / 算法 / 工作站 / 操作者”，不要把当前系统写成 AI。

## 相关文档

- `docs/BACKEND_API_CONTRACT.md`：前后端接口和 payload 契约。
- `docs/DEPLOYMENT_HANDOFF.md`：公网部署记录。
- `docs/WEB_APP_DEVELOPMENT_RUNBOOK.md`：Web 开发、验证、排错和部署例程。
- `docs/internal/HCI_INTERACTION_ROADMAP.md`：Web HCI 改造路线。
- `docs/internal/UI_WORKFLOW_ARCHITECTURE_HANDOFF.md`：页面工作流和实时采集架构。
- `docs/internal/ALGORITHM_PARITY_REPORT.md`：原算法与 Web 后端服务化实现的差异审计。

## 项目结构

```text
backend/                    Flask API 和服务化算法实现
web_app/                    Web 工作站前端
RandomSpectrum_av2/Pt2/     Windows 一键部署随仓库携带的示例样本库
RREs/                       合同探针使用的最小真实样本
docs/                       接口契约、部署和开发例程文档
docs/internal/              HCI 路线、交接记录和算法审计材料
research/legacy_algorithms/ 原始研究脚本和旧算法参考代码
deploy_windows.ps1          Windows 本地一键启动脚本
```

`research/legacy_algorithms/` 中的脚本保留原始研究代码形态，包含 Windows 路径、顶层执行或绘图副作用，当前 Web 后端不会直接 import 这些文件。Windows 部署运行的是 `backend/` 和 `web_app/`，不要为了启动 Web 去改这些旧脚本的路径。

## 历史遗留问题

早期 README 记录过两个待研究问题：

1. 模拟光谱强度中 A 参数没有充分发挥作用。
2. 粒子判断判据仍需进一步明确。

这些问题属于算法研究和原始模型层面，不应在 Web/HCI 改动中顺手改动。

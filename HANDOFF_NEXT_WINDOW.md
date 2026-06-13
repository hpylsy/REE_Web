# Handoff: LIBS 稀土检测 Web 应用

> 统筹窗口接手请先读 `COORDINATOR_HANDOFF.md`。本文件是总入口，但部分历史段落可能落后于 `progress.md` 末尾和真实代码；继续任务时必须 code/runtime/progress-first。

## 当前状态

截至 2026-06-04，当前工作区已经完成从静态前端原型到本地 Flask 后端真实算法 wrapper 的接入，并完成前后端端到端验证。

项目根目录：

```bash
/home/hpy/RREdetectation-MultiPeakFit
```

当前主要入口：

- 前端页面：`web_app/index.html`
- 前端逻辑：`web_app/app.js`
- 前端样式：`web_app/styles.css`
- 后端 API：`backend/app.py`
- 后端算法 wrapper：`backend/pipeline.py`
- 持久计划：`task_plan.md`
- 发现记录：`findings.md`
- 进度记录：`progress.md`

推荐打开方式：

```text
http://127.0.0.1:5000
```

`file:///home/hpy/RREdetectation-MultiPeakFit/web_app/index.html` 现在也能调用后端，但前提是 Flask 服务在 `127.0.0.1:5000` 运行。

## 启动方式

在项目根目录运行：

```bash
python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
```

然后浏览器打开：

```text
http://127.0.0.1:5000
```

如果端口 5000 被占用，先查：

```bash
ps -ef | rg 'backend\.app|app\.run|flask|python3 -c from backend'
```

不要直接 `kill -9` 不明进程，先确认是不是当前项目的 Flask。

## 已完成功能

### 前端

- 左侧项目/流程栏、中央六阶段图表、右侧检查器、底部事件日志。
- 六阶段顺序动画：
  1. 原始光谱
  2. 寻峰结果
  3. 谱线匹配
  4. 温度迭代
  5. 多峰拟合
  6. 检测结果
- 打开本地光谱文件：`.asc`、`.csv`、`.txt`、`.tsv`。
- 开始检测：调用 Flask `/api/pipeline/run`。
- 停止/复位。
- 导出后端返回的结果 CSV。
- 顶部菜单已变成真实下拉菜单：
  - 文件：打开光谱、导出 CSV、导出 JSON、复位当前任务。
  - 运行：开始检测、停止/复位、重新运行。
  - 视图：切换六阶段、显示/隐藏检查器、显示/隐藏事件日志、恢复默认布局。
  - 报告：导出结果 CSV、完整 JSON、阶段摘要 txt。
- 快捷键：
  - `Ctrl+O`：打开光谱。
  - `Ctrl+Enter`：开始检测。

### 后端

Flask API：

- `GET /`
- `GET /api/health`
- `GET /api/samples`
- `POST /api/pipeline/run`
- `GET /api/pipeline/<job_id>`
- `GET /api/pipeline/<job_id>/result.csv`

后端算法 wrapper 已接入：

- 光谱文本解析。
- CWT ridge peak detection。
- 没有 `pywt` 时 fallback 到 `scipy.signal.find_peaks`。
- `Elements_database/` 和 `Rareearth_pt3/` 本地 CSV 谱线库解析。
- 谱线开关和基体冲突过滤。
- 匈牙利谱线匹配。
- Boltzmann 温度和 R2。
- 稀土置信度计算。
- 局部 fixed-center Gaussian 多峰拟合。
- 六阶段结构化 JSON。
- 结果 CSV。

## 重要注意点

### 1. 用户系统是 Ubuntu

不要引入 Windows-only 假设，不要依赖：

- `D:\LIBS\...`
- PowerShell
- Windows path separator
- Windows-only 编码/命令

当前研究脚本里有很多 Windows 绝对路径，只能作为算法参考，不能直接在 Flask 中运行。

### 2. 不要直接 import 带顶层副作用的研究脚本

这些文件有顶层读文件、Windows 路径或绘图副作用，直接 import 到后端容易炸：

- `Elements_detectation.py`
- `Wavelet_peakfinding.py`
- `Identification_Matrix.py`
- `MultiPeakfit/Gaussfit.py`

当前策略是：在 `backend/pipeline.py` 中封装可服务化的核心算法逻辑，而不是直接 import 顶层研究脚本。

### 3. “后端失败”常见原因

如果页面显示“后端失败”，先查：

```bash
python3 - <<'PY'
from urllib.request import Request, urlopen
import json

with urlopen('http://127.0.0.1:5000/api/health', timeout=5) as response:
    print('health', response.status, response.read().decode())

req = Request(
    'http://127.0.0.1:5000/api/pipeline/run',
    data=json.dumps({'sample_path': 'RREs/070101_95.csv'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urlopen(req, timeout=15) as response:
    body = json.loads(response.read().decode())
    print('run', response.status, body['filename'], body['stages'][5]['summary'])
PY
```

已修复过一个具体 bug：

- 页面从 `file://.../web_app/index.html` 打开时，旧代码会请求 `file:///api/pipeline/run`。
- 现在 `web_app/app.js` 的 `resolveApiUrl()` 会在非 5000 来源下自动请求 `http://127.0.0.1:5000/api/...`。
- `backend/app.py` 已加本地开发 CORS header。

如果用户仍看到旧错误，让他先强制刷新：

```text
Ctrl + F5
```

### 4. Flask job 仍是内存存储

`backend/app.py` 里的 `JOBS = {}` 是内存字典。

影响：

- Flask 重启后旧 `job_id` 失效。
- 旧 CSV 下载链接失效。

如果后续要更像正式工具，优先考虑把 job 结果写到本地 `runs/` 或 `outputs/` 目录。

### 5. 前端默认样本仍写死

无上传文件时，前端默认跑：

```text
RREs/070101_95.csv
```

位置在 `web_app/app.js` 的 `requestBackendRun()`。

后续建议接 `/api/samples` 做样本选择下拉，而不是继续写死。

### 6. 当前不是生产部署

当前 Flask 启动方式是开发服务器，仅适合本机演示/调试。

不要把它描述为生产部署完成。

### 7. 当前算法是可服务化核心链路，不是完整研究脚本逐行搬运

已经接入核心链路，但没有原样搬入：

- 研究脚本里的全部打印分支。
- 绘图分支。
- 自动温度敏感元素标注完整流程。
- 所有多峰补救细节。

下个窗口如果继续算法精修，必须先明确是“服务化核心算法继续完善”，还是“重构研究脚本为可导入模块”。

## 已验证命令

基础验证：

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
```

后端 API 验证：

```bash
python3 - <<'PY'
from urllib.request import Request, urlopen
import json

with urlopen('http://127.0.0.1:5000/api/health', timeout=5) as response:
    print(response.status, response.read().decode())

req = Request(
    'http://127.0.0.1:5000/api/pipeline/run',
    data=json.dumps({'sample_path': 'RREs/070101_95.csv'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urlopen(req, timeout=15) as response:
    body = json.loads(response.read().decode())
    print(response.status, body['stages'][1]['parameters']['method'], body['stages'][5]['summary'])
PY
```

预期核心输出：

```text
200 CWT ridge peak detection Yb
```

Playwright 端到端曾验证：

- `http://127.0.0.1:5000` 打开后点击开始，完成，结果 `Yb`。
- `file:///.../web_app/index.html` 打开后点击开始，完成，结果 `Yb`。
- 上传 `Broaden_research/PureSample_Spectrum/Fe1.asc`，完成，结果 `无`。
- 菜单导出 CSV/JSON/摘要均能下载文件。
- 移动端菜单和结果柱图已验证。

## 建议下一步

当前 UI 和操作架构的下一步以 `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md` 为准：

1. 先做当前页面 UI/操作逻辑优化，尤其是离线文件来源语义。当前“选择”下拉来自 `/api/samples` 的工作区枚举，会显示用户未导入的 `GBW` / `RREs` 文件；后续应改为默认只显示用户导入的文件或导入文件夹内的文件。`/api/samples` 只能作为显式“示例样本库”入口，不应自动混入“已导入”列表。
2. 再做页面布局优化：桌面保持工作站密度，移动端优先显示 active chart/result，把 inspector、阶段数据表和日志收进 tabs/drawer。特别注意当前主图顶部四行堆叠过高的问题：全局菜单/工具栏、当前阶段标题状态、7 步阶段条、图表工具/状态行不能都作为高占用常驻横条压在 canvas 上方。
3. 置信度计算 / 强度梳 UI 已完成；后续布局优化必须把新增的第 6 阶段也纳入桌面/移动端截图验收。
4. 最后再做架构 UI：`离线分析` 与 `实时采集` 是同级 source mode。实时采集内部是一个采集板工作流：Web 通过串口或本地 bridge 控制延时/采集板，光谱仪通过 RJ45 接在采集板上，Web 上的 IP/端口用于配置采集板绑定光谱仪，不是浏览器直接连接光谱仪。

实时采集注意：

- 采集板通信可能走 Web Serial 或后端/local bridge，具体取决于浏览器、file:///公网 HTTP 场景和采集板协议；当前用户只要求 UI 里有串口识别/插拔/授权状态，不要求写具体识别函数。
- RJ45/IP 是采集板到光谱仪的连接配置；不要把它设计成浏览器直接对光谱仪开 raw TCP。
- 在知道真实采集板协议前，不要假装实现连接、绑定或采集；先做清晰 UI 状态机和 API 契约。

旧的样本选择器建议已经过期，且与用户最新交互预期相反。不要再复制“启动时调用 `/api/samples` 并展示 RREs/GBW/Broaden_research 样本”的提示词作为 UI 方向。

优先级从高到低：

1. 后端工程化整理：用户认为原作者脚本太乱，必须先把后端整理成适配 Ubuntu 和 Web 前后端接口的服务化算法层。单独 handoff 见 `BACKEND_REFACTOR_HANDOFF.md`。
2. 多峰拟合 payload 重做：当前拟合图无法复现图二，根因是后端没有返回 `raw_points`、`component_curves`、`sum_fit_points`、`fitted_peaks`、`local_extrema` 等前端绘图数据。
3. 温度迭代阶段复核：`progress.md` 后续记录显示多起点 T-iteration 已实现；后端整理时要保持 `starts/trace/score/best_start_index` 等 payload，不要退回单条二维 trace。历史 handoff 见 `TEMPERATURE_ITERATION_HANDOFF.md`。
4. 持久化 job：把每次检测结果写入 `runs/<timestamp>-<sample>/result.json` 和 `result.csv`。
5. 增加后端错误详情展示：把 traceback 的安全摘要写入 UI 日志或后端日志文件。
6. 增加报告导出能力：可先导出 HTML 报告，再考虑 PDF。
7. 算法校准：对不同样本验证置信度阈值 `0.05` 是否合理，尤其是 RRE 随机样本中多元素高置信度情况。

## 下个窗口推荐提示词

页面 UI 和采集架构方向请优先复制 `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md`
里的具体 slice prompt。若当前 UI/离线来源/布局/置信度阶段已由其它窗口完成，
当前最建议做该文档中的 Prompt 4：`Source Mode Architecture UI`，但必须按
“采集板串口控制 + 光谱仪 RJ45/IP 绑定”的统一实时采集工作流执行。

最小统筹接手提示词：

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

先阅读：
- COORDINATOR_HANDOFF.md
- HANDOFF_NEXT_WINDOW.md
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- progress.md 尾部至少 260 行
- BACKEND_API_CONTRACT.md

当前重点不是继续让 /api/samples 自动填满样本选择器。用户已经明确：选择框默认只应显示用户导入的文件，或导入文件夹内的文件；未导入的工作区 GBW/RREs 文件不应自动出现。/api/samples 只能作为显式“示例样本库”入口。

页面架构方向：
1. 先做当前页面 UI/操作逻辑优化。
2. 再做 `离线分析` 和 `实时采集` 同级 source mode。
3. 实时采集下不要再分成两个并列采集源。正确模型是：Web 串口/bridge 控制采集板，采集板通过 RJ45 连接光谱仪，Web 的 IP/端口输入用于配置采集板绑定光谱仪。
4. 真实通信要等采集板 API/设备协议明确后再做；当前先做 UI 状态机和串口识别 UI 壳，不要写 Web Serial 函数，不要假装可以识别真实串口或采集。

硬约束：
1. 用户系统是 Ubuntu。
2. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask。
3. Web 适配不能简化原算法。
4. 默认一个实现 slice 不超过 3 个修改文件。
5. UI 任务必须给 HTTP/file://、桌面/移动端截图。
6. 根目录不是 git 仓库，不能依赖 git diff。

当前基础验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

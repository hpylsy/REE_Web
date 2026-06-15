# Handoff: Ubuntu/Web 场景后端工程化整理

## 任务目标

把当前 LIBS 稀土检测 Web 应用的后端整理成适合 Ubuntu 本地运行、适合 Flask 前后端交互、适合复现研究脚本关键可视化效果的服务化算法层。

这不是简单把原作者脚本 import 进 Flask。当前原作者脚本里有 Windows 绝对路径、顶层读文件、顶层绘图和隐式全局状态，直接接 Web 会导致接口不稳定，也会让 `温度迭代`、`多峰拟合` 这类效果无法可靠复现。

本任务的核心是先整理后端边界，再复现算法效果：

- 后端必须能在 Ubuntu 上从项目根目录稳定启动。
- Flask API 只依赖干净的后端模块，不 import 带顶层副作用的研究脚本。
- 每个算法阶段都返回前端可直接绘图的结构化数据，而不是只返回打印文本或最终分数。
- 温度迭代和多峰拟合必须保留足够中间数据，支撑前端做用户要的图形展示。
- 研究脚本只作为算法参考，逐步抽取成无副作用的函数或类。
- 服务化迁移必须与原研究方法保持功能一致；不能为了 Web 适配把高精度算法换成简化版。

## 算法一致性硬约束

当前项目是高精度 LIBS 稀土检测场景，一点算法差异都可能改变识别结果。后端 Web 适配只能改变接口形态、路径处理、顶层副作用隔离和绘图 payload，不能擅自简化核心数值方法。

必须保持一致的内容包括：

- 光谱解析后进入算法的原始数值精度。
- CWT 寻峰核心方法、关键参数和 fallback 条件。
- 谱线库读取、单位换算、line switch 和基体冲突过滤。
- 匈牙利匹配、距离计算、Boltzmann 拟合、R2 和置信度公式。
- T-iteration 多起点、Top-K、score、阻尼更新、全局最佳选择。
- 多峰拟合的动态窗口、局部极值/FWHM、候选分量中心、优化器、目标函数和边界。
- 最终检测阈值、fit boost 和 CSV 导出前的结果判定。

如果某阶段暂时不能做到与原代码功能一致，必须：

1. 在代码 payload 或文档中标明 `fallback_reason` 或 `parity_gap`。
2. 在 `progress.md` 记录这是简化/临时代替，不得写成“已复现原算法”。
3. 新增或保留防回退测试，避免之后误把简化实现当成正式实现。
4. 给出恢复到原方法的最小修复 slice。

专门的监督/测试任务见：

```bash
ALGORITHM_PARITY_AUDIT_HANDOFF.md
```

## 当前状态

项目根目录：

```bash
/home/hpy/RREdetectation-MultiPeakFit
```

当前主要文件：

- `backend/app.py`: Flask API，负责路由、样本读取、内存 job。
- `backend/pipeline.py`: 当前所有服务化算法 wrapper 都在这里，文件已经超过 1100 行。
- `web_app/index.html`: 前端页面。
- `web_app/styles.css`: 前端样式。
- `web_app/app.js`: 前端状态机、API 调用、Canvas 绘图。

当前已能跑通的启动命令：

```bash
python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
```

当前核心验证命令：

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
```

当前 API：

- `GET /`
- `GET /api/health`
- `GET /api/samples`
- `POST /api/pipeline/run`
- `GET /api/pipeline/<job_id>`
- `GET /api/pipeline/<job_id>/result.csv`

页面从 `file://` 打开时也应能调用 `http://127.0.0.1:5000/api/...`，这个逻辑在前端 `resolveApiUrl()` 和后端 CORS 中。

## 必须遵守的约束

### 默认沟通

- 默认中文回复。
- 用户系统是 Ubuntu。
- 不要基于 README 猜状态，先读真实代码、运行命令和现有 handoff。

### 不要直接 import 的文件

这些研究脚本不能直接 import 到 Flask：

- `Elements_detectation.py`
- `Wavelet_peakfinding.py`
- `Identification_Matrix.py`
- `MultiPeakfit/Gaussfit.py`

原因：

- 有 Windows 绝对路径，例如 `D:\LIBS\...`。
- 有顶层读文件。
- 有顶层执行、绘图或 `plt.show()`。
- 有大量打印式流程和隐式全局状态，不适合作为 Web API 边界。

如果需要复现其中逻辑，只能把纯算法部分抽取到新的干净模块，或在 `backend/pipeline.py` 里先小步重写 wrapper。重写后的逻辑必须用审计或数值探针证明与原方法一致，不能只证明“接口能跑通”。

### 修改范围控制

仓库规则要求：

- 写代码前先说明要改哪里、怎么验证。
- 如果需求有歧义，先问少量高价值问题。
- 一次实现默认不要超过 3 个修改文件；如果需要超过 3 个文件，先拆成多个 slice。

这个整理任务会天然超过 3 个文件，所以必须拆阶段做，不要一次性大搬家。

## 为什么必须先整理后端

用户当前关注的是“能不能复现原作者图中的真实算法效果”。现状的问题不是前端 Canvas 画得不够花，而是后端输出的数据不够。

### 温度迭代保留和复核

`progress.md` 后续记录显示，当前温度阶段已经做过多起点 T-iteration 改造。后端整理时不要把这个 payload 拆坏，也不要退回成单条二维温度 trace。

用户要保留的是多起点 T-iteration：

- 多个初始温度同时出发。
- 每个起点经过迭代。
- 每轮有 candidate、target temperature、updated temperature、confidence、R2、score。
- 最后按全局最高 score 收敛到一个最优点。
- 前端当前已有伪 3D 展示记录；后端整理时重点是保持字段稳定。

如果后端整理后只返回最终温度或单条 trace，前端会重新失去用户要的多起点收敛过程。

温度迭代单独 handoff 见：

```bash
TEMPERATURE_ITERATION_HANDOFF.md
```

### 多峰拟合问题

用户要的是类似 `MultiPeakfit/Gaussfit.py` 中 `GaussMultiPeakFitter.plot()` 的效果：

- 蓝色原始局部光谱 `wl-int`。
- 绿色 Gaussian component curves。
- 橙色虚线 Gaussian sum fit。
- 绿色 fitted peaks。
- 红色 local extrema。
- 坐标轴 `Wavelength (nm)` 和 `Relative Intensity`。
- 图例包含 `wl-int`、`Gaussian Components`、`Gaussian Sum Fit`、`Fitted Peaks`、`Local Extrema`。

当前后端 `_fit_summary()` 只返回 `components`、`rms` 和置信度，前端只能自己合成一条平滑 Gaussian 曲线。以 `RREs/070101_95.csv` 为例，当前 fit payload 只有 1 个 component：

```text
target: YbII
window_nm: [273.995, 275.795]
components_count: 1
components: [{'label': 'YbII', 'center': 274.895, 'amplitude': 0.0182, 'sigma': 0.1425}]
```

当前缺少图二所需字段：

- `raw_points`
- `component_curves`
- `sum_fit_points`
- `fitted_peaks`
- `local_extrema`
- `residual_points`
- `baseline`

所以必须先让后端阶段返回可视化数据，前端才可能画出目标图。

## 推荐后端目标结构

不要第一步就做完全重构。推荐先按下面目标拆分，但每个 slice 控制在 3 个文件内。

最终后端可以整理成：

```text
backend/
  app.py                  Flask 路由层，只做 HTTP、样本读取、job 管理
  pipeline.py             六阶段编排层，组合各算法模块并生成 API payload
  spectrum.py             光谱解析、排序、去重、归一化、下采样
  samples.py              本地样本枚举和安全路径读取
  line_database.py        Elements_database/Rareearth_pt3 谱线库读取、缓存、谱线开关
  matching.py             匈牙利匹配、基体识别、稀土谱线匹配 payload
  temperature.py          Boltzmann 拟合、多起点 T-iteration payload
  multipeak_fit.py        Ubuntu-safe 多峰拟合、局部极值、拟合曲线 payload
  schemas.py              可选：阶段 payload/dataclass/字段说明
```

但实现顺序不要一口气拆这么多。优先拆对当前目标最致命的部分。

## 推荐实施阶段

### Slice 0: 状态复核，不改代码

先确认当前真实状态，不要信旧 handoff 的“下一步”：

```bash
sed -n '1,220p' HANDOFF_NEXT_WINDOW.md
sed -n '1,260p' task_plan.md
sed -n '1,320p' findings.md
tail -240 progress.md
sed -n '1,260p' BACKEND_REFACTOR_HANDOFF.md
sed -n '1,260p' TEMPERATURE_ITERATION_HANDOFF.md

rg -n "def parse_spectrum_text|def detect_peaks|def _load_line_database|def _temperature|def _fit_summary|def run_pipeline|def list_sample_files" backend/pipeline.py
rg -n "drawTemperature|drawFit|normalizeBackendResult|resolveApiUrl" web_app/app.js
```

然后运行：

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
```

### Slice 1: 后端契约文档和测试探针

目标：先固定 API 阶段输出契约，避免重构时前端被打断。注意：字段契约只证明 Web payload 完整，不证明算法与原方法一致；算法一致性必须由 `ALGORITHM_PARITY_AUDIT_HANDOFF.md` 中的审计和数值对照补充。

建议修改文件不超过 3 个：

- 新增或更新一个后端契约文档，例如 `BACKEND_API_CONTRACT.md`。
- 在 `backend/pipeline.py` 的 `__main__` 自检里增加关键字段断言，或新增轻量测试脚本。
- 更新 `progress.md`。

契约至少定义六阶段字段：

- `raw.preview`
- `peak.peaks`
- `match.spectral_matches`
- `temperature.trace` 和 `temperature.starts`
- `fit.raw_points`、`fit.component_curves`、`fit.sum_fit_points`、`fit.fitted_peaks`、`fit.local_extrema`
- `result.rare_earth_results`

验证：

```bash
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 - <<'PY'
from pathlib import Path
from backend.pipeline import run_pipeline
p = Path('RREs/070101_95.csv')
result = run_pipeline(p.read_text(encoding='utf-8', errors='ignore'), p.name)
print([stage['id'] for stage in result['stages']])
print(next(stage for stage in result['stages'] if stage['id'] == 'fit')['data'].keys())
PY
```

### Slice 2: 抽出光谱和样本 IO

目标：把最稳定、风险最小的 IO 逻辑先从 `backend/pipeline.py` 拆出来，为后续算法拆分减负。

建议改动：

- 新增 `backend/spectrum.py`：移动 `parse_spectrum_text()`、`_numeric_values()`、`_downsample_xy()` 等无算法副作用函数。
- 新增 `backend/samples.py`：移动 `list_sample_files()` 和安全样本路径辅助逻辑。
- 更新 `backend/pipeline.py` 或 `backend/app.py` 的 import。

验收标准：

- `/api/samples` 仍返回 `RREs/070101_95.csv`。
- 上传文件、内置样本、`file://` 页面调用都不破。
- `run_pipeline()` 输出字段不变。

### Slice 3: 抽出谱线库和匹配

目标：把谱线库读取、谱线开关、基体/稀土匹配从编排层拆出来，形成可测试函数。

建议文件：

- `backend/line_database.py`
- `backend/matching.py`
- `backend/pipeline.py`

验收标准：

- `RREs/070101_95.csv` 仍检出 `Yb`。
- `Broaden_research/PureSample_Spectrum/Fe1.asc` 仍未检出稀土或保持当前可解释结果。
- 谱线匹配阶段的前端图仍可画。

### Slice 4: 复核温度迭代可视化 payload

目标：确认后端温度阶段继续返回多起点、每轮 score、全局最佳点；如果整理过程中发现现有实现不稳定，再小步修正。

参考：

- `TEMPERATURE_ITERATION_HANDOFF.md`
- `Elements_detectation.py` 中 `_candidate_score()`、`_pick_target_temperature()`、`T_iteration_single()`、`T_iteration()`

输出字段建议：

```python
{
    "trace": [...],              # 全部起点合并轨迹或 selected 起点轨迹
    "starts": [
        {
            "start_index": 0,
            "initial_temperature": 5000.0,
            "final_temperature": 8420.0,
            "best_score": 0.73,
            "best_candidate": "Fe",
            "best_confidence": 0.81,
            "best_r2": 0.68,
            "selected": False,
            "trace": [...]
        }
    ],
    "best_start_index": 3,
    "best_score": 0.86,
    "temperature": 9670.0
}
```

验收标准：

- 前端可以画多起点收敛，而不是单条二维温度线。
- 后端单测或自检能证明 `starts` 不为空，且只有一个 `selected=True`。

### Slice 5: 重做多峰拟合为图二 payload

目标：不直接 import `MultiPeakfit/Gaussfit.py`，但复现其服务化结果结构和图形效果。这里的“复现”必须包括关键数值路径，不只是返回能画图的 Gaussian 曲线。

参考：

- `MultiPeakfit/Gaussfit.py` 中 `GaussMultiPeakFitter.fit()` 和 `plot()`。
- `Elements_detectation.py` 中 `MultiPeakFit(...)` 对 `GaussMultiPeakFitter` 的调用方式。

后端输出字段建议：

```python
{
    "target": "YbII",
    "target_element": "Yb",
    "window_nm": [273.995, 275.795],
    "raw_points": [{"x": 273.995, "y": 0.02}, ...],
    "component_curves": [
        {
            "label": "YbII",
            "center": 274.895,
            "amplitude": 0.0182,
            "sigma": 0.1425,
            "points": [{"x": 273.995, "y": 0.001}, ...]
        }
    ],
    "sum_fit_points": [{"x": 273.995, "y": 0.021}, ...],
    "fitted_peaks": [{"wavelength": 274.895, "intensity": 0.0182, "label": "YbII"}],
    "local_extrema": [{"wavelength": 274.88, "intensity": 0.024}],
    "residual_points": [{"x": 273.995, "y": -0.001}],
    "baseline": 0.004,
    "rms": 0.00434,
    "real_multipeak_fit": True,
    "component_count": 2
}
```

实现要点：

- 后端必须返回真实局部窗口 `raw_points`。
- `component_curves` 和 `sum_fit_points` 应由后端拟合参数采样得到，前端只负责画。
- `local_extrema` 用局部窗口内的真实谱线极值，不要用理论谱线冒充。
- `fitted_peaks` 使用拟合参数中的中心和幅值。
- 多峰拟合不得退回固定 `±0.9 nm` 窗口 + `curve_fit` 单峰/少峰简化实现，除非明确标记为 fallback 并有自检阻止它覆盖真实路径。
- 需要对照 `GaussMultiPeakFitter.fit()`、`CWTPeakFWHMEstimator`、`MultiPeakFit(...)` 的动态窗口、FWHM、ratio candidates、L-BFGS-B 和重叠线候选逻辑。
- 如果只有一个 component，summary 应写成“局部 Gaussian 单峰拟合”，不要误导成重叠峰分解。
- 若没有稳定拟合，返回空数组和明确 fallback reason，不要让前端合成假图。

验收标准：

- `RREs/070101_95.csv` 的 fit stage 至少包含 `raw_points`、`sum_fit_points`、`component_curves`、`local_extrema`。
- 前端 `多峰拟合` 图能画出蓝色原始谱线、绿色分量、橙色虚线总拟合、红色极值点和绿色拟合峰点。
- 桌面和移动端截图都能看清局部拟合窗口。

### Slice 6: 前端只消费后端 payload

目标：前端不再凭 `components` 自己伪造多峰图，也不在温度阶段伪造算法轨迹。

建议改动：

- `web_app/app.js` 的 `normalizeBackendResult()` 保留后端新增字段。
- `drawTemperature()` 画 `starts/trace/score`。
- `drawFit()` 画 `raw_points/component_curves/sum_fit_points/fitted_peaks/local_extrema`。

验收标准：

- `node web_app/app.js` pass。
- Flask 跑起来后，Playwright 验证桌面和移动端。
- CSV/JSON/摘要导出仍可用。

### Slice 7: 原算法一致性审计

目标：让一个独立窗口监督和测试 Web 后端是否偏离原研究方法，尤其防止“为了适配 Web 写了简化版”。

参考：

- `ALGORITHM_PARITY_AUDIT_HANDOFF.md`
- `BACKEND_API_CONTRACT.md`
- 原研究脚本：`Elements_detectation.py`、`Wavelet_peakfinding.py`、`Identification_Matrix.py`、`MultiPeakfit/Gaussfit.py`

验收标准：

- 生成 `ALGORITHM_PARITY_REPORT.md`。
- 每个阶段都有 Original Reference、Web Module、Parity Status、Evidence、Remaining Risk。
- 所有简化点都有 severity、location、why it matters、required fix。
- 至少运行 `backend.contract_probe` 的 RRE 和 Fe 样本。
- 如果发现简化实现，不直接修大块代码，先提出最小修复 slice。

## 每次实现后的固定验证

后端基础：

```bash
python3 -m compileall -q backend
python3 backend/pipeline.py
```

前端基础：

```bash
node web_app/app.js
```

API smoke：

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
with urlopen(req, timeout=20) as response:
    body = json.loads(response.read().decode())
    print('run', response.status, body['filename'], body['stages'][5]['summary'])
    fit = next(stage for stage in body['stages'] if stage['id'] == 'fit')
    print('fit keys', sorted(fit['data'].keys()))
PY
```

样本覆盖：

```bash
python3 - <<'PY'
from pathlib import Path
from backend.pipeline import run_pipeline

samples = [
    Path('RREs/070101_95.csv'),
    Path('GBW/GBW07106.csv'),
    Path('Broaden_research/PureSample_Spectrum/Fe1.asc'),
]

for path in samples:
    result = run_pipeline(path.read_text(encoding='utf-8', errors='ignore'), path.name)
    summary = next(stage for stage in result['stages'] if stage['id'] == 'result')['summary']
    print(path, '=>', summary)
PY
```

## 判断是否完成

不能只说“代码拆了”。完成标准是：

- Flask 还能启动。
- `file://` 页面仍能调用后端。
- `/api/samples` 还能列出本地样本。
- `RREs/070101_95.csv` 还能跑完整六阶段。
- 后端阶段 payload 比原来更适合前端画图。
- 温度和多峰拟合不再依赖前端伪造算法数据。
- 原研究脚本没有被直接 import 到 Flask。

## 给下个窗口的完整提示词

可以直接复制下面这段给新的 Codex 窗口：

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务，优先做“Ubuntu/Web 场景后端工程化整理”，不要先急着改前端特效。

先阅读项目根目录这些文件，不要从 README 猜状态：
- BACKEND_REFACTOR_HANDOFF.md
- HANDOFF_NEXT_WINDOW.md
- task_plan.md
- findings.md
- progress.md
- TEMPERATURE_ITERATION_HANDOFF.md

当前用户判断：原作者代码太乱，有 Windows 绝对路径、顶层读文件/绘图副作用，很难抽象接口，导致 Web 应用无法复现原有效果；这对应用很致命。因此目标是把后端整理成适配 Ubuntu、本地 Flask 前后端场景、可返回前端绘图 payload 的服务化算法层。

重要约束：
1. 默认中文回复。
2. 用户系统是 Ubuntu。
3. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask。
4. 这些研究脚本只能作为算法参考；需要把纯算法逻辑抽到 backend 下的无副作用模块，或先在 backend/pipeline.py 中服务化重写。
5. 当前可运行入口是 backend/app.py 和 backend/pipeline.py，前端主要是 web_app/app.js。
6. 页面从 file:// 打开也必须能调用 http://127.0.0.1:5000/api/...，不要破坏 resolveApiUrl() 和后端 CORS。
7. 一次实现默认不要超过 3 个修改文件；如果必须超过，先拆 slice。
8. 写代码前先用简短中文说明要改哪里、怎么验证；如果我明确说“开始做/改吧”，就直接做当前 slice，不要反复问同不同意。

请先做 Slice 0：真实状态复核，不改代码：
- 运行 rg 定位 backend/pipeline.py 中 parse_spectrum_text、detect_peaks、_load_line_database、_temperature、_fit_summary、run_pipeline、list_sample_files。
- 运行 node web_app/app.js、python3 -m compileall -q backend、python3 backend/pipeline.py。
- 用 RREs/070101_95.csv 跑 run_pipeline，打印六阶段 id、temperature data keys、fit data keys。

复核后给出最小可执行的后端整理计划。优先建议先做契约和多峰拟合 payload，因为当前多峰拟合图无法复现图二的根因是后端没有返回 raw_points/component_curves/sum_fit_points/fitted_peaks/local_extrema。

当前启动命令：
python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"

当前基础验证命令：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
```

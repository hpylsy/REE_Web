# Handoff: LIBS Web 应用统筹窗口

## 角色定位

这个窗口的职责不是继续抢具体功能实现，而是统领整个 LIBS 稀土检测 Web 应用任务：

- 读真实代码、运行结果和 `progress.md`，判断当前项目到底做到哪一步。
- 把用户的新需求拆成适合独立窗口完成的最小 slice。
- 给具体实现窗口写清楚目标、边界、文件范围、验证命令和可复制提示词。
- 审核其它窗口交回来的结果是否满足用户目标，尤其是否破坏算法一致性、Web 端兼容性或现有接口。
- 维护根目录 handoff、progress 和审计文档，让后续窗口不会从过期状态继续。

统筹窗口可以做小型文档更新和必要的状态复核；除非用户明确要求，否则不要直接展开大规模实现。具体编码任务尽量交给专门窗口，并要求它们完成验证。

## 当前项目原则

### 以真实代码和运行态为准

用户明确不希望只信 README 或旧 Markdown。统筹窗口判断状态时优先级如下：

1. 当前源码和运行命令。
2. `progress.md` 末尾最近记录。
3. 专项 handoff 和 report。
4. `HANDOFF_NEXT_WINDOW.md`、`task_plan.md`、`findings.md` 的早期信息。
5. README 或旧导出文档。

`HANDOFF_NEXT_WINDOW.md` 是入口文档，但其中部分历史段落可能过期。例如样本选择器、温度迭代、多峰拟合和图表缩放都经历过后续改动。继续任务前必须先看 `progress.md` 尾部和真实代码。

### 默认中文和 Ubuntu

- 默认中文回复。
- 用户系统是 Ubuntu。
- 不要引入 Windows-only 假设，不要依赖 PowerShell 或 `D:\LIBS\...`。
- 研究脚本里的 Windows 绝对路径和顶层读文件/绘图副作用必须隔离。

### 不直接 import 有副作用研究脚本

这些脚本不能直接 import 到 Flask runtime：

- `Elements_detectation.py`
- `Wavelet_peakfinding.py`
- `Identification_Matrix.py`
- `MultiPeakfit/Gaussfit.py`

它们是算法来源和审计对照，不是 Web 后端可直接依赖的模块。正确路线是抽取或重写无副作用的等价实现，并用测试证明与原方法一致。

### 防止“Web 适配 = 算法简化”

这是高精度检测场景。统筹窗口必须反复检查：

- Web 适配只能改变接口、路径、副作用隔离和 payload 结构。
- 不能擅自简化寻峰、谱线匹配、温度迭代、多峰拟合或最终判定逻辑。
- 不能用“图像看起来像”“RRE 样本能出 Yb”证明算法一致。
- 字段契约只能证明 payload 完整，不证明算法与原方法一致。

算法一致性专门看：

```bash
ALGORITHM_PARITY_AUDIT_HANDOFF.md
ALGORITHM_PARITY_REPORT.md
```

## 当前状态快照

以下状态来自近期 `progress.md` 和当前代码搜索，后续仍需复核：

- 后端已从单个 wrapper 逐步拆出：
  - `backend/app.py`
  - `backend/pipeline.py`
  - `backend/spectrum.py`
  - `backend/samples.py`
  - `backend/line_database.py`
  - `backend/multipeak_fit.py`
  - `backend/contract_probe.py`
- 温度迭代已对齐原主流程实际调用参数：
  - `max_iterations=12`
  - `tolerance=1e-5`
  - `multistart_count=10`
  - `candidate_mode="alterable"`
  - `t_min=5000`
  - `t_max=20000`
  - `alpha=0.35`
  - `top_k=3`
- 温度图已做 Three.js 本地化、固定右侧温度色标、中文标签、滚轮缩放、起始温度标签避让。
- 多峰拟合已新增 `backend/multipeak_fit.py`，服务化迁移动态窗口、CWT FWHM、固定中心 Gaussian、ratio candidates、L-BFGS-B 和基体重叠线候选。
- `ALGORITHM_PARITY_REPORT.md` 当前结论仍是 `overall_status: partial`；多峰拟合候选 payload 和 direct result boost 已处理，最高风险转为 zero-confidence rescue fixture 覆盖、寻峰/匹配数值 parity、raw/normalized 输入差异。
- 前端 `web_app/app.js` 已出现通用 chart zoom/lens 相关 helper 和工具栏，用于原始光谱、寻峰结果、谱线匹配的局部放大；但继续相关 UI 前仍要用 Playwright 或截图实际验收。

## 现有关键文档

### 总入口

- `HANDOFF_NEXT_WINDOW.md`  
  总入口和启动命令。注意部分内容可能落后于 `progress.md`。

### 统筹和任务拆分

- `COORDINATOR_HANDOFF.md`  
  当前文档，供下一任统筹窗口接手。
- `task_plan.md`
- `findings.md`
- `progress.md`

### 后端和契约

- `BACKEND_REFACTOR_HANDOFF.md`  
  后端工程化整理方向，包含算法一致性硬约束。
- `BACKEND_API_CONTRACT.md`  
  后端六阶段 JSON 字段契约。
- `ALGORITHM_PARITY_AUDIT_HANDOFF.md`  
  专门审计算法是否简化的窗口提示。
- `ALGORITHM_PARITY_REPORT.md`  
  当前算法一致性审计结果、风险和下一步建议。

### 历史专项

- `TEMPERATURE_ITERATION_HANDOFF.md`  
  温度迭代多起点任务历史 handoff。当前实现已经继续演进，不能只看这份文档判断现状。
- `BACKEND_REFACTOR_HANDOFF.md` 中的部分旧 slice 也可能已被后续窗口完成，继续前看 `progress.md` 末尾。

## 当前优先风险

按重要性排序：

1. 原算法一致性仍是最大风险。  
   direct `after_confidence` result boost 已从 `_final_results()` 移除；当前缺的是 zero-confidence rescue fixture，证明 `base_confidence <= 0.01` 时 append target fitted peak 后 recomputed confidence 路径真的覆盖原式 rescue。

2. 多峰拟合候选集合需要继续守住。  
   `fit_candidates` 已暴露并由 `contract_probe` 校验：目标稀土线 + 局部窗口内最多两条最强 matrix line，component/fitted peak centers 必须与 candidate 顺序对齐。后续不要重复实现候选 payload，重点是防回退和 UI 验收。

3. 寻峰和匹配仍需原方法数值对照。  
   CWT threshold、归一化强度、Hungarian cost 权重都可能改变后续结果。需要侧重“数值 diff 测试”，不是只看最终元素。

4. 前三阶段放大镜/局部缩放已进入代码，但必须 Web 验收。  
   重点看移动端是否误触发整页缩放、inset 是否遮挡高峰、坐标是否可读、导出是否未破坏。

5. 文档状态有历史层叠。  
   新窗口容易被早期 handoff 的旧建议带偏。统筹窗口要主动指出哪个文档是历史，哪个文档是当前事实。

## 统筹窗口工作流

### 接到用户新需求时

1. 先判断这是实现任务、审计任务、UI 任务、后端任务还是文档交接任务。
2. 读取最相关的文档和真实代码，不要从旧 README 猜。
3. 如果是大任务，拆成一个窗口能完成的最小 slice。
4. 写清楚：
   - 目标
   - 禁止事项
   - 需要先读的文件
   - 代码定位
   - 修改文件上限
   - 验证命令
   - 成功标准
   - 可复制提示词
5. 如果用户只是要交接或提示词，不要直接改业务代码。

### 审核其它窗口结果时

要求它们至少提供：

- 修改文件列表。
- 关键代码定位。
- 运行过的命令。
- Playwright/截图证据，如果是 UI。
- 样本探针输出，如果是算法。
- 是否改变 API payload。
- 是否直接 import 了研究脚本。
- 是否新增了防回退测试。

统筹窗口应重点复核：

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

如果涉及 Web 端：

- 桌面 Playwright 截图。
- 移动端 Playwright 截图。
- `file://` 打开页面仍能通过 `resolveApiUrl()` 调 Flask。
- 导出 CSV/JSON/摘要未破坏。

如果涉及算法：

- 不接受只给最终 `Yb` 的结果。
- 要看峰数、温度 starts、fit component count、candidate centers、confidence 变化。
- 对照 `ALGORITHM_PARITY_REPORT.md` 中的风险项。

## 给具体实现窗口的提示词模板

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做一个明确 slice：<写清楚任务名>。不要扩展到无关功能。

先阅读：
- COORDINATOR_HANDOFF.md
- HANDOFF_NEXT_WINDOW.md
- progress.md
- BACKEND_API_CONTRACT.md
- ALGORITHM_PARITY_REPORT.md
- <本任务相关专项文档>

重要约束：
1. 用户系统是 Ubuntu。
2. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask。
3. Web 适配不能简化原算法。若算法和原代码不同，必须标明 parity gap，并给测试证据。
4. 一次实现默认不要超过 3 个修改文件；如果必须超过，先拆 slice。
5. 页面从 file:// 打开仍必须能调用 http://127.0.0.1:5000/api/...。
6. 不要用“图像看起来像”或“RRE 样本能出 Yb”作为算法一致性证据。

代码定位：
- <列出相关函数和文件>

预期修改：
- <列出最多 3 个文件>

必须验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

如果是 UI 任务，还要用 Playwright 验证桌面和移动端，并保存截图路径。

完成后请更新 progress.md，说明：
- 修改了哪些文件；
- 为什么这么改；
- 跑了哪些验证；
- 仍有哪些风险。
```

## 建议下一批窗口

### 窗口 A: Zero-confidence fit rescue fixture

目标：

- 构造或找到 `base_confidence <= 0.01` 的稀土样本/fixture。
- 验证 `fit.data.confidence_rescue.applied=True` 时，target fitted peak append 后 recomputed confidence/T/R2/matched 进入最终结果。
- 不再改 `fit_candidates` 结构，除非 contract probe 先证明它回退了。

### 窗口 B: 寻峰/匹配数值 parity 测试

目标：

- 抽取 side-effect-free 的原 CWT/匹配公式探针。
- 对 `RREs/070101_95.csv`、`Fe1.asc` 做 peak list 和 matching assignment diff。
- 判断当前 normalized/dynamic threshold 是否可以接受，或需要恢复原方法参数。

### 窗口 C: 原始光谱/寻峰/谱线匹配放大镜验收和打磨

目标：

- 复核当前 `chartZoom`、lens、toolbar 是否已覆盖三阶段。
- 用 Playwright 验证桌面/移动端。
- 检查 inset 遮挡强峰时是否自动避让或 dock。
- 确认 wheel/pointer 只缩放图表，不缩放页面。

### 窗口 D: 文档消歧和总 handoff 更新

目标：

- 把 `HANDOFF_NEXT_WINDOW.md` 中过期段落替换成当前状态。
- 将 `ALGORITHM_PARITY_REPORT.md`、`BACKEND_API_CONTRACT.md`、`COORDINATOR_HANDOFF.md` 设为入口。
- 减少下个窗口被旧“样本选择器未完成”等历史文字带偏的概率。

## 本次交接确认

交接时间：2026-06-04。

当前窗口的后续职责应当收敛为“统筹、拆分、验收、记录”，而不是亲自承接所有实现。后续如果用户提出具体功能，统筹窗口先做三件事：

1. 用 `progress.md` 尾部和真实代码确认状态。
2. 判断任务属于算法 parity、后端接口、前端 UI、验证验收还是文档消歧。
3. 输出一个可交给专门窗口的最小 slice，默认最多改 3 个文件，并写清楚验收证据。

不要把其它窗口的口头结论直接转述为“已完成”。统筹窗口必须要求对方给出至少一种可复核证据：

- 算法任务：`contract_probe` 输出、focused numeric probe、候选峰/峰位/置信度差异。
- UI 任务：桌面和移动端 Playwright 截图路径、交互行为验证、`file://` 调 Flask 验证。
- 后端接口任务：`BACKEND_API_CONTRACT.md` 对齐情况、字段新增/删除说明、基础验证命令输出。
- 文档任务：修改文件列表、旧信息删除或打标的位置、下一窗口可复制提示词。

特别注意：当前根目录不是 git 仓库，不能依赖 `git diff` 判断变更；要用文件内容、运行命令和 `progress.md` 记录来判断。

## 立即可派发的专项提示词

下面这些提示词用于把具体工作交给其它窗口。统筹窗口可以按用户当前优先级复制其中一个，不要一次性让单个窗口做完所有方向。

### Prompt 1: Zero-confidence fit rescue fixture

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做“zero-confidence fit rescue fixture”的最小验证/测试 slice，不要改温度 3D 图、放大镜 UI 或无关前端效果。

先阅读：
- COORDINATOR_HANDOFF.md
- progress.md 尾部至少 260 行
- ALGORITHM_PARITY_REPORT.md，重点看 Final result 和 Simplification Findings
- BACKEND_API_CONTRACT.md 的 fit stage
- backend/multipeak_fit.py
- backend/pipeline.py 中 _fit_confidence_rescue()、_final_results()、run_pipeline()
- Elements_detectation.py 中 MultiPeakFit、拟合峰 rescue 和 recompute confidence 相关位置
- MultiPeakfit/Gaussfit.py 中 CWT FWHM、fixed-center Gaussian、ratio candidates、L-BFGS-B 逻辑

硬约束：
1. 不要直接 import Elements_detectation.py 或 MultiPeakfit/Gaussfit.py 到 Flask。
2. Web 适配不能把原算法简化成固定窗口、单峰 curve_fit 或 direct confidence boost。
3. 一次默认不要超过 3 个修改文件；如果需要新增 fixture、contract_probe、report 都要改，先说明文件范围。
4. 不能用“图像看起来像”或“RRE 样本仍然检出 Yb”作为 parity 证据。

当前重点：
- `fit_candidates` 已经暴露，RRE 样本当前为 target `YbII 275.0477` + matrix `MnII 275.0125` + `MnII 274.8702`，component/fitted peaks 与 candidate centers 对齐。
- `_final_results()` 不再直接使用 `after_confidence`，而是只在 `fit.data.confidence_rescue.applied=True` 时采用 recomputed confidence。
- 现在缺的是 zero-confidence rescue fixture：证明 `base_confidence <= 0.01` 时 append target fitted peak 后 recomputed confidence 进入最终结果。

建议最小目标：
1. 找一个真实样本或构造最小 focused fixture，使某个稀土 `base_confidence <= 0.01` 且有可用 target fitted peak。
2. 运行 `_fit_confidence_rescue()` 或 `run_pipeline()`，确认 `confidence_rescue.applied=True`、`reason=fitted_peak_append_recompute`。
3. 打印 appended peak centers、base confidence、recomputed confidence、final result confidence/T/R2/matched。
4. 如果只能做合成 focused probe，必须在 ALGORITHM_PARITY_REPORT.md 标明真实样本覆盖仍缺失。

必须验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

完成后更新 progress.md，并给出：
- 修改文件列表；
- rescue fixture/probe 的实际输出摘要；
- final result 是否只采用 recomputed confidence，而非 `after_confidence`；
- zero-confidence rescue 是否仍有真实样本覆盖 gap；
- 下一步最小修复建议。
```

### Prompt 2: 寻峰与谱线匹配数值 parity 审计

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做“寻峰与谱线匹配数值 parity 审计”，优先只读分析和 probe，不要改 UI，不要重构后端。

先阅读：
- COORDINATOR_HANDOFF.md
- ALGORITHM_PARITY_AUDIT_HANDOFF.md
- ALGORITHM_PARITY_REPORT.md
- progress.md 尾部至少 260 行
- backend/spectrum.py
- backend/pipeline.py 中 detect_peaks、_match_spectral_lines_weighted、_compute_element_confidence、run_pipeline
- Wavelet_peakfinding.py
- Identification_Matrix.py
- Elements_detectation.py 中 peakfinding、match_spectral_lines_weighted、compute_element_confidence、主流程参数

硬约束：
1. 不要直接 import Wavelet_peakfinding.py、Identification_Matrix.py、Elements_detectation.py 到 Flask runtime。
2. 可以写临时/测试 probe 抽取无副作用公式，但要明确不把有副作用脚本挂进 backend/app.py。
3. 审计重点是数值路径，不是最终 UI 好不好看。
4. 不接受只报告 “result_summary: Yb”。

审计问题：
- 后端是否使用 raw intensity 还是 normalized intensity 进入 CWT、匹配、Boltzmann 和 confidence？
- CWT threshold 是否偏离原主流程固定 coeffi_threshold=700？
- Hungarian cost 中 intensity 权重是否偏离原默认 beta=1.0？
- 后端 peak list、match assignments、confidence 是否与原方法可解释一致？

最低输出：
- RREs/070101_95.csv 的 peak_count、前 20 个 peak wavelength、与原式 probe 的差异。
- Broaden_research/PureSample_Spectrum/Fe1.asc 的同类结果。
- 至少一个 ambiguous matching fixture 或真实窗口，比较 backend assignment 与原式 cost assignment。
- 明确结论：acceptable_adapter / needs_parity_fix / insufficient_evidence。

基础验证：
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

完成后更新 ALGORITHM_PARITY_REPORT.md 或新增 focused audit note，并更新 progress.md。
```

### Prompt 3: 原始光谱/寻峰/谱线匹配放大镜 Web 验收

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做“原始光谱、寻峰结果、谱线匹配三阶段的放大镜/横轴局部缩放 Web 验收和最小打磨”。不要改后端算法，不要改温度 3D 图。

先阅读：
- COORDINATOR_HANDOFF.md
- progress.md 尾部至少 260 行
- web_app/app.js 中 drawRaw、drawPeaks、drawSpectralMatch、createDefaultChartZoom、resolveSpectrumChartWindow、spectrumInsetLayout、spectrumZoomEmphasis、chart zoom 事件绑定
- web_app/index.html 中 #chart-zoom-toolbar
- web_app/styles.css 中 chart-zoom-toolbar、is-chart-zooming、is-match-zooming
- BACKEND_API_CONTRACT.md，确认前端仍用后端 payload，不伪造算法结果

用户要求：
- 原始光谱、寻峰结果、谱线匹配都能局部横轴放大。
- 放大后谱线、峰标记、标签自动变粗/变大，便于展示细节。
- 谱线匹配效果可参考当前 match 界面，但要有坐标轴、刻度和局部 inset。
- 移动端不能因为双指或滚轮操作把整个 Web 页面放大/滚动，而应优先作用在图表控件内。
- 放大镜所在位置如果有很高谱线，不能遮挡关键峰；要有自动避让或 dock 策略。

验收要求：
1. 启动 Flask：
   python3 -c "from backend.app import app; app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
2. Playwright 桌面尺寸 1440x1000：
   - 选择 RREs/070101_95.csv；
   - 运行检测；
   - 依次进入原始光谱、寻峰结果、谱线匹配；
   - 操作局部窗口宽度、+/-、鼠标/触控定位；
   - 保存截图路径。
3. Playwright 移动尺寸 390x844：
   - 重复三阶段；
   - 验证页面没有被整页缩放，图表控件仍能操作；
   - 保存截图路径。
4. 验证 file:// 打开 web_app/index.html 时仍能调用 http://127.0.0.1:5000/api/...。
5. 验证导出 CSV、JSON、摘要没有被破坏。

基础命令：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv

如果只发现小 UI 问题，默认最多改 web_app/app.js、web_app/styles.css、progress.md 三个文件。完成后更新 progress.md，列出截图路径和仍未验收的浏览器/手势。
```

### Prompt 4: 统筹窗口接手

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用统筹任务。

你的角色不是直接抢具体功能实现，而是统领整个项目：读真实代码和 progress，判断状态，拆分任务，给其它窗口写可执行提示词，审核它们的结果是否跑偏，并维护 handoff 文档。

默认中文回复。用户系统是 Ubuntu。用户不希望只信 README 或旧 Markdown，必须 code/runtime/progress-first。

先阅读：
- COORDINATOR_HANDOFF.md
- progress.md 尾部至少 260 行
- ALGORITHM_PARITY_REPORT.md
- ALGORITHM_PARITY_AUDIT_HANDOFF.md
- BACKEND_REFACTOR_HANDOFF.md
- BACKEND_API_CONTRACT.md
- HANDOFF_NEXT_WINDOW.md
- task_plan.md
- findings.md

然后用真实代码复核当前状态：
find backend -maxdepth 1 -type f -name '*.py' -printf '%f\n' | sort
rg -n "def _fit_summary|from backend.multipeak_fit|_temperature_multistart_iteration|multistart_count|candidate_mode|contract_probe|fit_candidates|after_confidence" backend/*.py
rg -n "drawRaw|drawPeaks|drawSpectralMatch|chartZoom|lens|zoom|temperatureFrontIterationZ|wheel" web_app/app.js web_app/index.html web_app/styles.css

硬约束：
1. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask。
2. Web 适配不能简化原算法。接口/payload 可以变，核心数值路径不能擅自换简化版。
3. 一次给实现窗口的任务要收窄到一个 slice，默认不超过 3 个修改文件。
4. 对算法任务，必须要求 contract_probe 和 focused numeric probe，不能只看最终检测元素。
5. 对 UI 任务，必须要求桌面和移动端 Playwright 截图，并确认 file:// 调 Flask 未破坏。
6. 如果用户只要“方案/提示词/交接”，不要直接改业务代码。
7. 根目录不是 git 仓库，不能依赖 git diff；用文件内容、运行结果和 progress.md 判断状态。

当前重点风险：
- ALGORITHM_PARITY_REPORT.md 显示 overall_status 仍是 partial；direct result boost 已移除，但 zero-confidence rescue fixture 仍缺。
- 多峰拟合 `fit_candidates` 已暴露并由 contract probe 校验，后续重点是防回退和 UI/表格验收，不要重复做候选 payload。
- 寻峰和匹配仍需原方法数值 parity 测试。
- 原始光谱/寻峰/谱线匹配放大镜功能已有代码迹象，但需要 Web 端验收和遮挡处理复核。
- HANDOFF_NEXT_WINDOW.md 里部分历史内容可能过期，继续任务前以 progress.md 末尾和真实代码为准。

常用基础验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

你的输出应优先是：状态判断、下一步 slice、给具体窗口的可复制提示词、验收标准。只有用户明确让你实现时，才进入代码修改。
```

## 给下一任统筹窗口的完整提示词

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用统筹任务。

你的角色不是直接抢具体功能实现，而是统领整个项目：读真实代码和 progress，判断状态，拆分任务，给其它窗口写可执行提示词，审核它们的结果是否跑偏，并维护 handoff 文档。

默认中文回复。用户系统是 Ubuntu。用户不希望只信 README 或旧 Markdown，必须 code/runtime/progress-first。

先阅读这些文件：
- COORDINATOR_HANDOFF.md
- progress.md 尾部至少 260 行
- ALGORITHM_PARITY_REPORT.md
- ALGORITHM_PARITY_AUDIT_HANDOFF.md
- BACKEND_REFACTOR_HANDOFF.md
- BACKEND_API_CONTRACT.md
- HANDOFF_NEXT_WINDOW.md
- task_plan.md
- findings.md

然后用真实代码复核当前状态：
find backend -maxdepth 1 -type f -name '*.py' -printf '%f\n' | sort
rg -n "def _fit_summary|from backend.multipeak_fit|_temperature_multistart_iteration|multistart_count|candidate_mode|contract_probe" backend/*.py
rg -n "drawRaw|drawPeaks|drawSpectralMatch|chartZoom|lens|zoom|temperatureFrontIterationZ|wheel" web_app/app.js web_app/index.html web_app/styles.css

硬约束：
1. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask。
2. Web 适配不能简化原算法。接口/payload 可以变，核心数值路径不能擅自换简化版。
3. 一次给实现窗口的任务要收窄到一个 slice，默认不超过 3 个修改文件。
4. 对算法任务，必须要求 contract_probe 和 focused numeric probe，不能只看最终检测元素。
5. 对 UI 任务，必须要求桌面和移动端 Playwright 截图，并确认 file:// 调 Flask 未破坏。
6. 如果用户只要“方案/提示词/交接”，不要直接改业务代码。

当前重点风险：
- ALGORITHM_PARITY_REPORT.md 显示 overall_status 仍是 partial；direct result boost 已移除，但 zero-confidence rescue fixture 仍缺。
- 多峰拟合 `fit_candidates` 已暴露并由 contract probe 校验，后续重点是防回退和 UI/表格验收，不要重复做候选 payload。
- 寻峰和匹配仍需原方法数值 parity 测试。
- 原始光谱/寻峰/谱线匹配放大镜功能已有代码迹象，但需要 Web 端验收和遮挡处理复核。
- HANDOFF_NEXT_WINDOW.md 里部分历史内容可能过期，继续任务前以 progress.md 末尾和真实代码为准。

常用基础验证：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

你的输出应优先是：状态判断、下一步 slice、给具体窗口的可复制提示词、验收标准。只有用户明确让你实现时，才进入代码修改。
```

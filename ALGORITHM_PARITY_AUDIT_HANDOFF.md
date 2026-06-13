# Handoff: 原算法一致性审计与防简化测试

## 任务目标

专门监督和测试 Web 适配后的后端算法是否偏离原研究代码，避免为了接 Flask/API 或前端绘图而把高精度 LIBS 稀土检测流程简化成“看起来能跑”的版本。

本任务不是继续开发新功能，而是做算法一致性审计：

- 找出 Web 后端里哪些地方是服务化迁移，哪些地方只是简化替代。
- 对照原研究代码的关键算法路径，确认 Web 实现是否保留同等数值逻辑。
- 对已经简化的部分打标：`acceptable_adapter`、`needs_parity_fix`、`intentional_visual_only`。
- 补充可运行测试，防止后续代码退回到简化版本。
- 输出审计报告，指出每个阶段是否与原方法一致、证据是什么、还差什么。

## 最高优先级原则

这是高精度检测场景，不允许“结果差不多”“先用简化版占位”“前端看起来像”这种判断进入算法层。

Web 适配只能改变：

- 输入输出封装。
- 文件路径处理。
- 顶层副作用隔离。
- 绘图数据结构化。
- Flask/API payload 形态。
- Ubuntu 下可运行的依赖边界。

Web 适配不能擅自改变：

- 寻峰核心方法和关键参数。
- 谱线库读取规则和谱线筛选规则。
- 匈牙利匹配/距离计算/置信度计算方法。
- Boltzmann 温度拟合和 T-iteration 评分/更新逻辑。
- 多峰拟合窗口选择、候选峰中心、FWHM 估计、优化器、目标函数和边界条件。
- 检测阈值、置信度 boost 或最终判定逻辑。

如果因为原脚本有 Windows 路径、顶层读文件或绘图副作用而不能直接 import，正确做法是抽取或重写无副作用的等价实现，并用测试证明行为一致；不是换成更简单的算法。

## 当前必须警惕的问题

之前已经发生过简化风险：

- 当前后端早期 wrapper 曾用固定 `0.9 nm` 窗口和 `curve_fit` 做局部 fixed-center Gaussian 拟合。
- 这种实现能让前端画出 Gaussian，但并不等价于 `MultiPeakfit/Gaussfit.py` 里的动态窗口、FWHM、ratio candidates 和 L-BFGS-B 多峰拟合策略。
- 进度记录里后续已经新增 `backend/multipeak_fit.py`，尝试迁移原 `Gaussfit.py` / `Elements_detectation.py` 的关键无副作用逻辑，并加入防回退断言。

审计窗口必须重新从真实代码验证，不要只信进度记录：

```bash
rg -n "fixed 0.9|window_half_width|curve_fit|FixedCenterGaussianFitter|ratio_candidates|CWTPeakFWHMEstimator|extract_spectrum_between_minima|component_count" backend Elements_detectation.py MultiPeakfit/Gaussfit.py
```

如果 `backend/pipeline.py` 里仍保留旧 `_fit_summary()` 或旧 `curve_fit` 分支，要确认运行时到底调用的是哪个实现。不能只看文件里存在新模块就认为已生效。

## 不要直接 import 的研究脚本

这些脚本有 Windows 路径、顶层读文件、绘图或执行副作用，不要直接 import 到 Flask：

- `Elements_detectation.py`
- `Wavelet_peakfinding.py`
- `Identification_Matrix.py`
- `MultiPeakfit/Gaussfit.py`

但它们是算法一致性审计的主要对照来源。审计时可以读取源码、复制关键公式、抽取无副作用函数、用子进程/AST/文本方式分析；不要让 Flask runtime 依赖它们的顶层执行。

## 必读文件

先读这些项目文档：

```bash
sed -n '1,260p' BACKEND_REFACTOR_HANDOFF.md
sed -n '1,260p' BACKEND_API_CONTRACT.md
sed -n '1,260p' HANDOFF_NEXT_WINDOW.md
sed -n '1,260p' task_plan.md
sed -n '1,360p' findings.md
tail -260 progress.md
```

再读当前后端代码：

```bash
find backend -maxdepth 1 -type f -name '*.py' -print | sort
rg -n "def parse_spectrum_text|def detect_peaks|def _compute_element_confidence|def _temperature|def _fit_summary|run_pipeline|contract_probe|multipeak|line_database" backend/*.py
```

再读原研究代码关键位置：

```bash
rg -n "CWT|find_peaks|ridge|T_iteration|T_iteration_single|_candidate_score|_pick_target_temperature|MultiPeakFit|GaussMultiPeakFitter|CWTPeakFWHMEstimator|gaussian_sum_fixed_mu|L-BFGS-B|ratio_candidates|line_switch|Hungarian|linear_sum_assignment|Boltzmann|confidence" Elements_detectation.py Wavelet_peakfinding.py Identification_Matrix.py MultiPeakfit/Gaussfit.py
```

## 审计范围

### 1. 光谱解析

审计问题：

- Web 后端是否保留原始波长/强度数值精度？
- 排序、去重、归一化是否改变算法输入？
- 下采样 preview 是否只用于前端显示，不能进入真实算法计算？

必须验证：

- 后端算法计算使用完整解析数组，而不是 `preview`。
- 原始强度和归一化强度分别用于正确阶段，不能混用。

### 2. 寻峰

对照来源：

- `Wavelet_peakfinding.py`
- `Elements_detectation.py` 中 CWT/寻峰相关调用。

审计问题：

- Web 后端 CWT ridge peak detection 是否与原脚本方法一致？
- `pywt` 缺失 fallback 是否只在依赖不可用时使用？
- fallback 输出是否被明确标记，不能伪装成原算法。
- 峰数、峰位、prominence 或强度排序是否与原方法接近。

最低测试：

- 真实样本 `RREs/070101_95.csv`。
- 实验室样本 `Broaden_research/PureSample_Spectrum/Fe1.asc`。
- 至少输出峰数、前 20 个峰位差异。

### 3. 谱线库和谱线开关

对照来源：

- `Elements_Combfact.py`
- `Lineswitch.py`
- `Elements_detectation.py`
- `Elements_database/`
- `Rareearth_pt3/`

审计问题：

- CSV 列读取是否与原代码一致？
- 波长单位 Å 到 nm 转换是否一致？
- 能级 cm^-1 到 eV 转换是否一致？
- line switch、基体冲突过滤、主元素相关逻辑是否一致？
- 是否有为简化而跳过奇偶行、冲突列、低强度过滤的行为？

最低测试：

- 统计每个谱线库加载的 ion 数、line 数。
- 对若干 ion 输出前 10 条 wavelength/intensity/energy，与原代码或手工读取对照。

### 4. 匹配和置信度

对照来源：

- `Identification_Matrix.py`
- `Elements_detectation.py`

审计问题：

- 匈牙利匹配 cost、scope、强度权重是否与原代码一致？
- matrix/base element 与 rare earth 的匹配 scope 是否被简化？
- 置信度公式是否一致？
- R2、linecount、distance 的元素聚合是否一致？

最低测试：

- 固定样本输出 `base_candidates`、`matrix_elements`、`spectral_matches`。
- 与原算法参考输出做字段级对照；没有可运行原脚本时，至少做公式级对照报告。

### 5. 温度迭代

对照来源：

- `Elements_detectation.py` 中 `_candidate_score()`、`_pick_target_temperature()`、`T_iteration_single()`、`T_iteration()`。
- `TEMPERATURE_ITERATION_HANDOFF.md`。

审计问题：

- 是否仍是多起点 T-iteration？
- 起点数量、范围、迭代次数、Top-K、alpha、tolerance、candidate mode 是否与原方法一致或有明确说明？
- score 公式是否一致？
- final temperature 是不是全局最高 score 的起点，而不是固定第一个起点或最后一轮温度？

最低测试：

```bash
python3 -m backend.contract_probe RREs/070101_95.csv
```

并额外打印：

- starts 数量。
- 每个 start 的 initial/final/best_score/best_candidate。
- selected count 必须等于 1。
- selected start 必须是最高 best_score。

### 6. 多峰拟合

对照来源：

- `MultiPeakfit/Gaussfit.py`
- `Elements_detectation.py` 中 `MultiPeakFit(...)`。
- `backend/multipeak_fit.py`。

审计问题：

- 是否使用动态窗口，而不是固定 `±0.9 nm`？
- 是否使用局部极小值截窗或等价策略？
- 是否估计 CWT FWHM？
- 是否使用固定中心 Gaussian 多峰拟合？
- 是否使用 `scipy.optimize.minimize(..., method="L-BFGS-B")` 和 ratio candidates 动态窗口搜索？
- 是否包含目标稀土线和基体重叠线候选中心？
- 前端 payload 是否来自后端拟合结果，而不是前端用 `components` 伪造？

最低测试：

```bash
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

对 `RREs/070101_95.csv` 至少要求：

- `component_count >= 2`，否则疑似退回单峰简化。
- `raw_points` 非空。
- `component_curves` 非空。
- `sum_fit_points` 非空。
- `fitted_peaks` 非空。
- `local_extrema` 非空。
- `window_nm` 不是固定宽度 `1.8 nm` 的旧窗口。

### 7. 最终检测结果

审计问题：

- fit boost 是否与原方法一致？
- final result 是否因为前端展示需要而改变 threshold？
- `detected` 判定是否保持原逻辑？
- CSV 输出是否只是导出格式，不影响检测结果。

## 输出报告格式

审计完成后新增或更新一个报告，例如：

```bash
ALGORITHM_PARITY_REPORT.md
```

建议结构：

```markdown
# Algorithm Parity Report

## Summary
- overall_status: pass / partial / fail
- highest_risk_stage:
- samples_tested:

## Stage Matrix
| Stage | Original Reference | Web Module | Parity Status | Evidence | Remaining Risk |
| --- | --- | --- | --- | --- | --- |

## Simplification Findings
| Severity | Location | Simplification | Why It Matters | Required Fix |
| --- | --- | --- | --- | --- |

## Numeric Probes
粘贴关键样本的峰数、温度 starts、fit component count、result summary。

## Regression Tests Added
列出新增/已运行的命令。
```

## 允许和不允许的结论

允许：

- “这个模块是服务化重写，但公式、参数和候选集合与原方法一致，证据是...”
- “这个地方仍是简化版，风险是...，必须修。”
- “这里因为原脚本依赖顶层文件/绘图不能直接运行，所以目前只做源码级对照，还缺数值对照。”

不允许：

- “看起来差不多。”
- “前端图像已经像了，所以算法没问题。”
- “原脚本太乱，所以用更简单方法代替。”
- “这个样本能出 Yb，所以一致。”

## 给专门审计窗口的提示词

可以直接复制下面这段给新的 Codex 窗口：

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。本窗口只做“原算法一致性审计与防简化测试”，不要开发新功能，不要改前端特效。

背景：
用户担心某些 Web 适配把原作者高精度算法简化成后端 wrapper。对于 LIBS 稀土检测，一点点算法差异可能改变结果，所以必须监督适配后的代码是否偏离原研究方法或做了简化。

默认中文回复。先阅读：
- ALGORITHM_PARITY_AUDIT_HANDOFF.md
- BACKEND_REFACTOR_HANDOFF.md
- BACKEND_API_CONTRACT.md
- HANDOFF_NEXT_WINDOW.md
- task_plan.md
- findings.md
- progress.md

重要约束：
1. 用户系统是 Ubuntu。
2. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask，它们有 Windows 路径、顶层读文件或绘图副作用。
3. 但这些研究脚本是算法一致性对照来源，必须读取源码并对照公式、参数、候选集合和优化流程。
4. Web 适配只能改变接口、路径、副作用隔离和 payload 结构；不能擅自简化寻峰、谱线匹配、温度迭代、多峰拟合或最终判定逻辑。
5. 如果发现简化实现，要明确标注位置、风险、与原方法差异和需要修复的测试。
6. 不要用“结果看起来一样”“前端图像像了”“RREs 样本能出 Yb”作为一致性证据。

请先做只读审计，不改代码：
- 用 rg 定位 backend 当前实际运行的寻峰、谱线库、匹配、温度、多峰拟合实现。
- 用 rg 定位原研究脚本对应实现。
- 对照每个阶段：原方法、Web 模块、是否简化、证据、风险。
- 特别检查多峰拟合是否真的使用动态窗口、CWT FWHM、L-BFGS-B、ratio candidates 和基体重叠线候选，而不是固定窗口 + curve_fit 单峰。
- 特别检查温度迭代是否仍是多起点，并且 selected start 是全局最高 score。

必须运行：
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

建议额外运行 focused probe，打印：
- 六阶段 stage id。
- peak count。
- temperature starts、selected_count、best_start_index、每个 start 的 best_score。
- fit window_nm、component_count、raw_points/component_curves/sum_fit_points/fitted_peaks/local_extrema 数量。
- result summary。

完成后新增 `ALGORITHM_PARITY_REPORT.md`，报告格式：
1. Summary：overall_status、highest_risk_stage、samples_tested。
2. Stage Matrix：Stage / Original Reference / Web Module / Parity Status / Evidence / Remaining Risk。
3. Simplification Findings：Severity / Location / Simplification / Why It Matters / Required Fix。
4. Numeric Probes：贴关键命令输出摘要。
5. Regression Tests Added Or Needed。

如果需要修代码，先停下来列出最小修复 slice，不要直接改。这个窗口的第一目标是监督和测试，不是继续开发。
```

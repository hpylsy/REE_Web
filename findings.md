# Findings & Decisions

## Requirements
- 默认中文沟通。
- 用户要把当前 LIBS 稀土元素识别工作区做成 Web 端应用。
- 布局参考手绘图：左侧控制区，右侧六个可视化流程框。
- 六个流程框具有顺序性：上一框处理完成后再传给下一框。
- 需要肉眼可见进程处理顺序。
- 用户后续补充要求：调用 skill，先设定目标，然后写任务流程，分点完成，不追求一个窗口实现。
- 当前阶段应先规划和分阶段推进，而不是直接把真实算法和 Web UI 一次性全部塞进一个实现窗口。

## Research Findings
- 工作区是研究型脚本工程，不是标准 Python 包。
- 核心识别脚本是 `Elements_detectation.py`，包含 CWT 寻峰、基体元素识别、谱线开关、稀土置信度计算、多峰拟合补救和温度扫描/迭代分支。
- 模拟光谱生成器在 `SimspecGen/`，核心是 `SimspecGen/Gen.py` 和 `SimspecGen/simLIBS/simulation.py`。
- 许多脚本存在 Windows 绝对路径，例如 `D:\LIBS\RREdetectation\...`，当前 Linux 工作区不能直接运行这些路径。
- 一些模块有顶层读文件或执行逻辑，例如 `Wavelet_peakfinding.py`、`Identification_Matrix.py`、`MultiPeakfit/Gaussfit.py`，直接 import 可能触发副作用。
- 当前已存在静态 Web 原型：`web_app/index.html`、`web_app/styles.css`、`web_app/app.js`。
- 用户明确系统是 Ubuntu；后端不能依赖 Windows 绝对路径、PowerShell 或 Windows-only 启动方式。
- Ubuntu 当前已安装 `PyWavelets`，后端可优先走 CWT 脊线寻峰；代码仍保留 `scipy.signal.find_peaks` 后备路径。
- `Elements_database/` 和 `Rareearth_pt3/` 本地 CSV 可在后端用标准库解析，不需要把 Flask 服务强绑定到 `pandas`。
- `backend/pipeline.py` 当前已封装真实算法链：光谱解析、CWT/后备寻峰、谱线库加载、谱线开关、匈牙利匹配、Boltzmann 温度/R2、稀土置信度和局部 Gaussian 多峰拟合。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 第一版先保持静态前端 | 已满足“六框顺序流转”的可视化需求，同时避免真实算法路径问题阻塞 UI 验证。 |
| 把后端接入拆为后续阶段 | 真实算法需要先处理路径、导入副作用和接口数据结构。 |
| 规划文件放在项目根目录 | planning-with-files 技能要求项目目录保存 `task_plan.md`、`findings.md`、`progress.md`。 |
| 每阶段保留可验证输出 | 用户要求分点完成，后续每个阶段都要有明确完成证据。 |
| 后端不直接 import 顶层研究脚本 | 多个研究脚本在 import 时读 Windows 路径或执行绘图；后端用可导入 wrapper 复刻核心算法，避免 Ubuntu Flask 服务启动失败。 |
| 后端样本路径以项目根目录为基准 | Flask 可以从任意 cwd 启动，`/api/samples` 不再受当前工作目录影响。 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 算法脚本不适合直接接 Web | 先做静态原型；后续 Phase 3 专门拆算法边界。 |
| 当前环境没有 Playwright/Puppeteer/Selenium npm 包 | 使用 Node 状态机自检、HTML 解析、Chrome headless 截图作为轻量验证。 |
| `backend/app.py` 直接从 `/tmp` 启动曾找不到 `backend` 包 | 增加脚本模式导入后备路径，验证 `timeout 2 python3 backend/app.py` 可进入 Flask 服务。 |

## Resources
- `web_app/index.html`: 当前 Web 原型页面结构。
- `web_app/styles.css`: 当前 Web 原型样式和响应式布局。
- `web_app/app.js`: 六阶段状态机、模拟图表、导入和导出交互。
- `Elements_detectation.py`: 后续真实算法接入的主要来源。
- `Elements_Combfact.py`: 谱线库构建和谱线开关逻辑来源。
- `Wavelet_peakfinding.py`: CWT 脊线寻峰逻辑来源。
- `MultiPeakfit/Gaussfit.py`: 多峰拟合逻辑来源。
- `SimspecGen/`: 模拟光谱生成器来源。

## Visual/Browser Findings
- 用户手绘图表达为左侧控制区 + 右侧六个处理框，控制区包含 Import、Scan、Output、Back 等按钮。
- 六个框中包含类似原始光谱、寻峰结果、强度/置信度柱图、多峰拟合曲线和最终结果列表的可视化。
- Chrome headless 桌面截图显示当前 Web 原型具备左侧控制面板、顶部 1-6 节点、右侧六张卡片。
- Chrome headless 移动端截图显示控制面板在顶部、流程框纵向堆叠，未见明显文字或按钮重叠。

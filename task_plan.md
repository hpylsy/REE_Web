# Task Plan: LIBS Web Workflow Application

## Goal
把当前 LIBS 稀土元素识别原型整理成可逐步交付的 Web 端应用：先有清晰的六阶段可视化流程，再分阶段接入真实算法、后端接口、验证和交付，不追求一个窗口内一次性完成全部功能。

## Current Phase
Phase 6

## Phases

### Phase 1: Frontend Workflow Prototype
- [x] 建立 Web 端基本布局，贴近用户草图：左侧控制区，右侧六个流程框。
- [x] 六个框按顺序流转，上一阶段完成后再进入下一阶段。
- [x] 使用模拟数据展示原始光谱、寻峰、基体识别、谱线开关、多峰拟合和稀土识别结果。
- [x] 做基础桌面和移动端渲染验证。
- **Status:** complete

### Phase 2: Persistent Planning And Scope Control
- [x] 启用 planning-with-files 技能。
- [x] 明确目标、阶段和约束，写入 `task_plan.md`。
- [x] 把已发现的项目事实和风险写入 `findings.md`。
- [x] 把当前进度和验证结果写入 `progress.md`。
- **Status:** complete

### Phase 3: Algorithm Boundary Extraction
- [x] 梳理现有算法中可复用的纯函数：光谱读取、CWT 寻峰、谱线库加载、置信度计算、多峰拟合。
- [x] 识别并隔离顶层执行副作用和 Windows 绝对路径。
- [x] 设计一个最小 Python 服务接口输入/输出格式。
- [x] 在不破坏现有研究脚本的前提下，规划并实现可导入的后端算法 wrapper。
- **Status:** complete

### Phase 4: Backend API Prototype
- [x] 选择轻量后端方案，优先 Flask 或 FastAPI。
- [x] 实现上传光谱文件接口。
- [x] 实现六阶段状态输出接口，先接模拟后端，后接真实算法。
- [x] 给每一阶段输出结构化结果，供前端逐框显示。
- **Status:** complete

### Phase 5: Frontend-Backend Integration
- [x] 将当前静态模拟数据替换为 API 返回数据。
- [x] 保留六阶段顺序动画，改为按后端返回的阶段 summary 和 data 推进。
- [x] 显示每一阶段的真实图表和结果摘要。
- [x] 处理失败、取消、重新运行和导出结果。
- **Status:** complete

### Phase 6: Verification And Delivery
- [x] 对前端状态机、后端接口和端到端流程分别验证。
- [x] 用至少一个本地 CSV 光谱样例跑通流程。
- [x] 记录已验证项、未验证项和后续工作。
- [x] 按阶段交付，不把未完成后端包装成已完成产品。
- **Status:** complete

## Key Questions
1. 第一轮真实后端接入要先接哪一个阶段：只接光谱读取/寻峰，还是一次接完整 `Elements_detectation.py` 流程？
2. 真实算法是否允许重构为可导入模块，还是必须保留现有脚本并通过子进程调用？
3. Web 端最终是本地单机工具，还是需要部署给多人访问？
4. 输出结果是否只需要置信度 CSV，还是要包含每阶段图表、日志和可解释谱线匹配详情？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 先完成静态 Web 原型 | 用户要求先有图一布局和肉眼可见的六阶段顺序流程；静态原型能先确定交互和布局。 |
| 使用 planning-with-files 做持久化任务流程 | 用户明确要求调用 skill、设定目标、写任务流程并分点完成。 |
| 后续不追求一个窗口内实现全部功能 | 真实算法存在路径硬编码、顶层执行副作用和浏览器抓取依赖，分阶段接入风险更低。 |
| 当前不直接运行 `Elements_detectation.py` | 脚本含 Windows 绝对路径和顶层执行逻辑，直接运行在当前 Ubuntu 工作区不可靠。 |
| 后端算法 wrapper 直接复用核心算法思想而不是 import 顶层研究脚本 | `Wavelet_peakfinding.py`、`Identification_Matrix.py`、`MultiPeakfit/Gaussfit.py` 都有顶层读文件或绘图副作用；后端改为在 `backend/pipeline.py` 内封装 CWT、谱线库、匈牙利匹配、Boltzmann 和 Gaussian 拟合。 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `PROCESS_STAGES is not defined` | 1 | 这是 TDD 红灯验证，随后实现状态机并用 `node web_app/app.js` 验证通过。 |
| Chrome VAAPI version warning | 1 | 属于 headless Chrome GPU 视频加速提示，不影响页面截图渲染。 |
| `ModuleNotFoundError: No module named 'backend'` | 1 | 修复 `backend/app.py` 脚本模式导入，支持从 Ubuntu 任意 cwd 直接启动后端。 |
| `/api/samples` 从非项目目录启动时返回 0 个样本 | 1 | `list_sample_files()` 改为以项目根目录为基准解析样本路径。 |
| 后台 `nohup` Flask 进程在工具命令结束后被回收 | 1 | 改用持久 exec 会话运行 Flask，并用真实 HTTP 请求验证。 |

## Notes
- 每完成一个阶段都更新 `task_plan.md` 和 `progress.md`。
- 每发现影响设计或算法接入的事实，都更新 `findings.md`。
- 修改代码前遵守项目 AGENTS 规则：先说明计划，获得用户确认；一次实现默认不超过三个修改文件，除非用户明确批准。
- 当前 Web 原型已接真实后端，但 job 仍存于 Flask 内存；服务重启会丢失旧 `job_id`。

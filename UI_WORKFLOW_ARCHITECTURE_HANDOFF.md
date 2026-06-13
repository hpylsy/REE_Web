# UI Workflow And Acquisition Architecture Handoff

## Purpose

This document is the handoff for the next UI and interaction-architecture work
on the LIBS rare-earth detection workstation.

The immediate goal is not to add acquisition-board communication code yet. The
correct order is:

1. Clean up the current page UI and operation logic for the existing offline
   spectrum-file workflow.
2. Then add a top-level acquisition-mode architecture where offline file
   analysis and real-time spectrum acquisition are separate, same-rank modes.
3. Only after the architecture is clear, implement the concrete acquisition
   board protocol: Web-to-board serial communication plus spectrometer RJ45/IP
   binding through the board.

Do not mix the real-time acquisition controls into the current "open spectrum
file" control. The user explicitly wants these as parallel entry modes.
Also do not present serial and RJ45 as two independent acquisition sources. In
the real device layout, Web talks to the delay/acquisition board through serial,
and the spectrometer is connected to that board through RJ45.

## Current State From Code

Current UI entry points:

- `web_app/index.html` has one hidden file input `#spectrum-file` and one
  button `data-action="import"` labelled `打开光谱`.
- `web_app/app.js` calls `loadSampleOptions()` on page startup.
- `loadSampleOptions()` fetches `/api/samples`, and `backend/samples.py`
  enumerates workspace directories such as `GBW`, `RREs`,
  `Broaden_research/PureSample_Spectrum`, `MultiPeakfit`, and `Fe-Ni_Spec`.
- Therefore the current left-side sample selector shows backend-enumerated
  repository files, not only files imported by the user.
- `requestBackendRun()` already supports two execution paths:
  - uploaded `File` through `FormData`;
  - backend workspace `sample_path` through JSON.

Current backend state relevant to later UI:

- `match.data.confidence_calculation` is already available.
- The payload includes `all_theoretical_comb`, `matched_theoretical_comb`,
  `matched_experimental_comb`, `raw_peak_marks`, formula notes, and
  representative selection details.
- The confidence-comb UI should use this payload directly; it should not ask a
  future backend window to re-invent the same fields.

Current page-level UI audit findings:

- Desktop has enough width but too many always-visible regions:
  workflow list, step strip, main plot, inspector, table, and log compete for
  attention.
- The chart area itself now loses too much vertical space to stacked header
  rows: global toolbar/menu, current-view header, seven-step strip, and the
  chart tool/status row. The user specifically called out the four-row top area
  above the plot as visually poor and too tall.
- Mobile first viewport is dominated by toolbar/project/process/config panels;
  the active chart starts too low.
- Result stage spends too much plot area on a sparse confidence bar chart while
  repeating the same conclusion in the table and inspector.
- Temperature and fit stages are useful but need more plot-first space.
- Fit candidate text wraps too aggressively on mobile.
- The current sample selector semantics are unclear because it shows files the
  user did not import.

## Target Product Model

Use a clear top-level mode model:

```text
Analysis Mode
├── Offline Spectrum Data
│   ├── Open files
│   ├── Open folder
│   └── Optional explicit sample library
└── Real-Time Acquisition
    └── Acquisition Board Workflow
        ├── Web-to-board serial communication
        ├── Spectrometer RJ45/IP binding configured from Web
        └── Single/delayed spectrum capture
```

The two analysis modes are same-rank choices:

- Offline spectrum data is for existing `.asc`, `.csv`, `.txt`, `.tsv` files.
- Real-time acquisition is for controlling the delay/acquisition board, binding
  the RJ45-connected spectrometer through that board, collecting a spectrum, and
  then running the same downstream pipeline.

Do not design real-time acquisition as a small option inside the file-import
dropdown. It should be a parallel source mode with its own connection state,
configuration, acquisition controls, and error model.

Device topology:

```text
Browser UI
  -> serial link or local bridge
    -> delay/acquisition board
      -> RJ45
        -> spectrometer
```

The IP/port fields in the Web UI are not for the browser to open a raw RJ45/TCP
connection to the spectrometer. They are operator-facing settings sent to the
acquisition board, so the spectrometer can be bound without using a screen on
the board.

## Recommended UI Direction

### Page Structure

Desktop should be a dense workstation:

- Top toolbar: mode switch, run state, primary commands.
- The chart header should be compact. Do not keep menu/header/stage strip/chart
  controls as four separate full-width rows above the canvas; merge or collapse
  them so the plot gets the vertical space.
- Left sidebar: source/mode setup and pipeline configuration.
- Center: active stage plot as the primary visual.
- Right or bottom drawer: details, parameters, evidence, and logs.
- Details should be tabbed or collapsible, not all visible at once.

Mobile should be guided review mode:

- First viewport after run should prioritize active stage chart/result.
- Source setup, pipeline steps, and config should collapse into drawers or
  compact summary bands.
- Tables should become cards or compact lists when columns wrap too much.

### Operation Model

Do not let "Open spectrum", "sample selector", and "start" carry three
different meanings. Use source-first logic:

1. Choose analysis mode.
2. Configure source.
3. Validate source readiness.
4. Run pipeline.
5. Review stages and export.

Suggested UI labels:

- `离线分析`
- `实时采集`
- `打开文件`
- `打开文件夹`
- `已导入`
- `示例样本库` only if an explicit sample-library entry is kept
- `采集板串口`
- `光谱仪 IP`
- `绑定光谱仪`
- `单次采集`
- `延时采集`

### Offline Mode Rules

Initial offline state:

- The imported file selector is empty or disabled.
- It must not show `GBW` / `RREs` / workspace files unless the user explicitly
  loads a sample library.
- Start should be disabled or should show a clear "请先导入光谱文件或文件夹"
  message.

Open files:

- Support one or multiple spectrum files.
- The selector lists only user-selected files.
- Running uploads the selected `File` through `FormData`.

Open folder:

- Use browser directory upload (`webkitdirectory multiple`) for the UI slice.
- Filter to `.asc`, `.csv`, `.txt`, `.tsv`.
- The selector lists only files inside the imported folder, preferably using
  `webkitRelativePath`.
- Running uploads the selected `File`, not a local absolute path.

Sample library:

- Keep `/api/samples` available for development or demos.
- Do not call it automatically at startup.
- If exposed in UI, make it a separate explicit action named `加载示例样本库`.
- Clearly mark sample-library entries as examples, not imported files.

### Real-Time Acquisition Mode Rules

Real-time mode should own its controls. It should not reuse the offline file
selector. It is one acquisition-board source with two configuration regions,
not two alternative acquisition sources.

Board serial panel:

- COM/port selector UI or manual port status.
- Baud rate.
- Data bits / parity / stop bits if needed.
- Serial timeout.
- Serial detection UI shell: unavailable / permission needed / port detected /
  disconnected.
- Request/select port and refresh-port buttons may exist as disabled or
  "not wired yet" controls in the UI architecture slice.
- Connection/protocol controls should remain disabled placeholders until the
  acquisition-board protocol is known.
- A clear note if Web Serial API is unavailable in the browser.

Spectrometer binding panel:

- Spectrometer IP address.
- Spectrometer port.
- Protocol/device model field if known later.
- Send/apply binding to the acquisition board.
- Test binding/read status through the board.
- Binding status and last error.

Acquisition panel:

- Single acquisition.
- Delayed acquisition.
- Delay time/count/interval settings, depending on the board protocol.
- Stop acquisition.
- Use captured spectrum for analysis.

Connection/acquisition states:

- `board_disconnected`
- `serial_unavailable`
- `serial_permission_needed`
- `serial_port_detected`
- `serial_port_disconnected`
- `board_connecting` (future protocol slice)
- `board_connected` (future protocol slice)
- `spectrometer_unbound`
- `spectrometer_binding`
- `spectrometer_bound`
- `acquiring`
- `capture_complete`
- `ready_for_analysis`
- `error`

Captured spectrum preview:

- timestamp
- point count
- wavelength range
- intensity range
- raw data buffer availability
- board/spectrometer metadata if available

Implementation note:

- The browser should not directly open a raw RJ45/TCP connection to the
  spectrometer. RJ45/IP settings are sent to the acquisition board through the
  serial path or through a local/backend bridge.
- Do not invent the acquisition-board protocol in the UI architecture slice.
  First build the UI state model and service contract placeholder.
- The first UI slice should include the serial detection view, but it should not
  wire concrete serial functions unless the user explicitly asks for that slice.
  Do not call Web Serial APIs, do not send board commands, do not bind the
  spectrometer, and do not claim acquisition works.
- For browser-side serial, Web Serial is available only in Chromium-based secure
  contexts. The deployed public HTTP page and `file://` page are not reliable
  final assumptions for Web Serial. A local/backend bridge may be more reliable
  on Ubuntu.

## Architecture Layers

Keep these boundaries explicit:

```text
UI source mode
  -> source adapter
    -> spectrum payload
      -> existing pipeline run
        -> existing stage/result rendering
```

Source adapters:

- `offline-file`: selected browser `File`.
- `offline-folder-file`: selected browser `File` from an imported folder.
- `sample-library`: backend `sample_path`, explicit dev/demo action only.
- `acquisition-board`: captured spectrum text/array produced by the acquisition
  board after Web-to-board serial communication and RJ45 spectrometer binding.

The downstream pipeline should receive a common spectrum input once acquisition
has produced data. Avoid branching algorithm code by acquisition source.

## Implementation Order

### Slice 1: Offline Source UX Cleanup

Purpose:

- Fix the current misleading sample selector.
- Make imported files and imported folders the only default items in the
  selector.

Files:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

Do not modify backend files in this slice.

Success criteria:

- Initial page does not show `GBW` / `RREs` workspace files.
- User can import one file, run it, and export results.
- User can import multiple files, switch the selected imported file, run it, and
  export results.
- User can import a folder, see only spectrum files from that folder, switch
  among them, and run selected files.
- `file://.../web_app/index.html` still calls Flask for pipeline run.

### Slice 2: Page Layout And Stage Review Cleanup

Purpose:

- Make the active chart/result the main focus.
- Reduce duplicate navigation and repeated details.
- Improve mobile review flow.

Files:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

Do not change backend payloads.

Success criteria:

- Desktop keeps chart-first layout while preserving stage navigation.
- The area above the active plot is no longer a four-row stack. On desktop,
  current stage/status, stage navigation, and chart controls should fit into at
  most two compact rows, with low-priority details moved to drawer/tabs.
- Mobile first viewport after run shows the active stage sooner.
- On mobile, stage navigation and chart controls are collapsed or wrapped into a
  compact pattern; they must not push the chart far below the first viewport.
- Inspector/table/log are tabs or collapsible details, not all fighting for
  space.
- Fit candidate/component text is readable without huge table rows.
- Result stage prioritizes detected-first summary and optional full REE table.

### Slice 3: Confidence Calculation / Intensity Comb UI

Purpose:

- Use the existing `match.data.confidence_calculation` payload to render the
  algorithm explanation views from the project documents.

Files:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

Do not change backend files.

Success criteria:

- Draw the theoretical comb view.
- Draw original spectrum + theoretical line marks + selected experimental
  peaks.
- Draw matched stick spectrum:
  - all theoretical: light blue
  - matched theoretical: blue
  - matched experimental: red
- Allow selecting the ion/item.
- Show confidence formula, distance, T, R2, line count, and representative
  selection reason.

### Slice 4: Source Mode Architecture UI

Purpose:

- Add same-rank `离线分析` and `实时采集` source modes.
- Keep real-time acquisition separated from file import.

Files:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

Do not implement acquisition-board transport yet.

Success criteria:

- Source mode segmented control exists.
- Offline controls only show in offline mode.
- Real-time controls only show in real-time mode.
- Real-time mode shows one acquisition-board workflow, with separate sections
  for board serial connection, spectrometer RJ45/IP binding, acquisition
  controls, and captured spectrum preview.
- The UI does not imply that the browser directly controls the spectrometer over
  RJ45.
- Start/run behavior remains correct for offline mode.

### Slice 5: Acquisition API Contract

Purpose:

- Define the backend/local-service contract for acquired spectra.
- Decide whether Web-to-board serial communication should be browser-side
  Web Serial or backend/local-service bridged.

Files:

- `ACQUISITION_API_CONTRACT.md`
- optionally `BACKEND_API_CONTRACT.md`
- `progress.md`

This is a documentation/contract slice unless the user explicitly asks for code.

Success criteria:

- Contract defines source session, connect/disconnect, acquire, cancel, and
  pipeline handoff.
- Contract distinguishes Web Serial constraints from backend/local bridge.
- Contract states that spectrometer RJ45/IP settings are sent to the
  acquisition board; the browser is not expected to directly speak raw TCP to
  the spectrometer.

### Slice 6: Serial Detection UI Shell

Purpose:

- Add the UI needed for serial plug-in recognition without implementing the
  actual detection functions yet. The page should show where COM/port status,
  authorization, plug/unplug, and unavailable states will appear.

Likely files:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

Do not call `navigator.serial`, do not open a port, and do not write any serial
helpers in this slice. Do not send serial commands. Do not implement connect,
bind, acquire, or delayed acquisition beyond disabled placeholders.

Success criteria:

- Real-time acquisition mode includes a visible "采集板串口识别" section.
- The section has status UI for `serial_unavailable`,
  `serial_permission_needed`, `serial_port_detected`, and
  `serial_port_disconnected`.
- The section has COM/port selector UI, request/select-port button UI, and
  refresh-port button UI, but these controls are clearly disabled/not wired yet.
- The page does not call Web Serial APIs and does not pretend a real serial
  device has been detected.
- Offline analysis still works.

### Slice 7: Acquisition Board Protocol Contract

Purpose:

- Define the actual acquisition-board serial protocol after the user provides
  board command/response details.

This slice needs:

- command for setting spectrometer IP/port;
- command for testing spectrometer binding;
- command for single acquisition;
- command for delayed acquisition;
- response format and sample raw spectrum.

Do not invent protocol behavior.

### Slice 8: Spectrometer Binding And Capture Prototype

Purpose:

- Implement spectrometer RJ45/IP binding through the acquisition board and one
  real capture path only after the board protocol is known.

This slice needs:

- acquisition-board command for setting spectrometer IP/port;
- board response format;
- acquisition command and delayed acquisition parameters;
- sample data.

Do not invent protocol behavior.

## Verification Rules

Common checks after UI work:

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
python3 -m backend.contract_probe RREs/070101_95.csv
python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit
```

Required UI evidence:

- desktop screenshot at `1440x1000`;
- mobile screenshot at `390x844`;
- HTTP page run through Flask;
- `file://` page still calls Flask API;
- no horizontal overflow on mobile;
- no controls covering the primary chart.

For architecture-only slices:

- Provide screenshots of UI states even if transport is stubbed.
- Explicitly state which controls are disabled placeholders.
- Do not claim real acquisition works until a real or simulated instrument
  protocol has been tested.

## Prompt 1: Offline Source UX Cleanup

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做 Slice 1：离线光谱来源 UI 清理。目标是修正当前“选择”下拉框自动显示 GBW/RREs 等未导入工作区文件的问题。不要改后端算法，不要改温度迭代，不要改多峰拟合，不要做串口/RJ45 实时采集。最多修改 3 个文件：
- web_app/index.html
- web_app/app.js
- web_app/styles.css

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- progress.md 尾部
- web_app/index.html 中 #spectrum-file、#sample-select、工具栏按钮
- web_app/app.js 中 loadSampleOptions()、renderSampleSelect()、sampleSelect change、fileInput change、requestBackendRun()、startPipeline()
- backend/app.py 中 /api/pipeline/run，确认 FormData file 上传已存在
- backend/samples.py，确认 /api/samples 是工作区样本枚举，不是用户导入历史

实现要求：
1. 页面启动时不要自动调用 /api/samples 填充选择框。
2. 初始下拉框显示“未导入文件”或禁用，不能出现 GBW/RREs/Broaden_research 等未导入文件。
3. “打开光谱”支持选择一个或多个 .asc/.csv/.txt/.tsv 文件。
4. 新增“打开文件夹”入口，使用 webkitdirectory multiple，过滤可用光谱文件。
5. 下拉框只显示用户本次导入的文件或文件夹内可用文件。
6. 切换下拉框时切换当前 selected File；运行时走 FormData 上传，不走 sample_path。
7. /api/samples 可以保留给后续“示例样本库”，但本 slice 不要自动使用。
8. file:// 打开 web_app/index.html 时仍必须能调用 Flask API。

自测要求：
- node web_app/app.js 增加或更新断言：
  - 初始状态不会渲染自动样本库；
  - 导入文件列表会去重并过滤无效扩展名；
  - 文件夹导入使用相对路径 label；
  - requestBackendRun 对导入文件走 FormData；
  - resolveApiUrl 的 file:// 行为未破坏。

验证命令：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- python3 -m backend.contract_probe RREs/070101_95.csv
- python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

UI 验收：
- 启动 Flask。
- HTTP 页面：初始不出现 GBW/RREs；导入单文件后可运行；导入多文件后可切换运行；导入文件夹后只显示该文件夹内光谱。
- file:// 页面：导入文件后仍可调用 Flask 并完成运行。
- 保存 desktop 1440x1000 和 mobile 390x844 截图。

完成后更新 progress.md，写清修改文件、截图路径、验证命令摘要、是否保留 /api/samples 作为显式示例库入口。
```

## Prompt 2: Page Layout And Stage Review Cleanup

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做 Slice 2：当前页面 UI 和操作逻辑优化。前提是离线来源选择已经清理完成。不要做串口/RJ45，不要改后端算法，不要改后端 payload。最多修改 3 个文件：
- web_app/index.html
- web_app/app.js
- web_app/styles.css

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- progress.md 尾部 UI/UX Audit 和最新 UI 改动
- web_app/index.html 当前布局
- web_app/styles.css 响应式布局
- web_app/app.js 中 render()、stageRows()、parameterRows()、resultRows()、chartRenderers、菜单/阶段导航

目标：
1. 桌面保持工作站密度，但让 active chart/result 成为主视觉。
2. 移动端让运行后的第一屏更快看到当前阶段图表，而不是被项目、流程、配置占满。
3. 减少重复导航：左侧流程、顶部 step strip、菜单三者不要全部同等抢注意力。
4. 重点优化主图顶部四行堆叠：全局菜单/工具栏、当前阶段标题状态、7 步阶段条、图表工具/状态行不能都作为高占用常驻横条压在 canvas 上方。桌面应合并到最多两行紧凑工具区；移动端应折叠成 stage selector / chart tools drawer / compact chips。
5. inspector、阶段数据表、event log 改为 tabs、drawer 或可折叠详情，避免全部常驻。
6. fit 候选和 component 信息改成紧凑结构化列表，不要让长文本把移动端表格撑得很高。
7. result 阶段优先显示 detected-first summary，完整 REE 表格作为详情。

不要做：
- 不要改变六阶段后端顺序。
- 不要删除导出 CSV/JSON/摘要能力。
- 不要修改温度 3D 算法或多峰拟合数据结构。
- 不要引入外部 CDN 依赖。

验证：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- python3 -m backend.contract_probe RREs/070101_95.csv
- python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

Playwright/Chrome 验收：
- HTTP desktop 1440x1000：跑 RREs/070101_95.csv，截 raw/match/temperature/fit/result。
- HTTP mobile 390x844：跑同一样本，确认无横向溢出，主图不被控件遮挡。
- 对比截图中 plot 顶部占高：桌面不能再出现四个高占用横向区域连续压住主图；移动端第一屏应能更早看到 active chart/result。
- file:// 页面：导入文件并运行，确认仍调用 Flask。

完成后更新 progress.md，记录截图路径和仍需架构层优化的问题。
```

## Prompt 3: Confidence Calculation / Intensity Comb UI

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做 Slice 3：置信度计算 / 强度梳 UI。后端已经有 match.data.confidence_calculation，不要再改后端字段。最多修改 3 个文件：
- web_app/index.html
- web_app/app.js
- web_app/styles.css

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- BACKEND_API_CONTRACT.md 中 confidence_calculation
- progress.md 尾部 Match Payload: Confidence Calculation / Intensity Comb
- Elements_detectation.py 中 compute_element_confidence_shape 的 plot=True 画图逻辑
- 元素识别流程.docx 和 结题验收书4_20.docx 中图1/图2/图3
- web_app/app.js 中 normalize backend result、drawSpectralMatch、chartRenderers、stageRows/resultRows

目标：
1. 新增“置信度计算”视图或在谱线匹配阶段下新增明确子视图。
2. 画理论强度梳：all_theoretical_comb 浅蓝 stick。
3. 画原始光谱筛峰解释图：原始光谱黑线 + raw_peak_marks.theoretical_wavelengths 浅蓝竖线 + selected_experimental_peaks 红点。
4. 画 Matched Stick Spectrum：
   - All Theoretical: light blue
   - Matched Theoretical: blue
   - Matched Experimental: red
5. 允许选择 ion/item，默认选择 representative_selection.selected=true 且 confidence 最高的 item。
6. 显示 confidence、distance、T、R2、line_count、formula、normalization、representative_selection reason。
7. 移动端图例不能遮挡主要 stick。

验证：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- python3 -m backend.contract_probe RREs/070101_95.csv
- python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

UI 验收：
- HTTP desktop/mobile：跑 RREs/070101_95.csv，进入置信度计算视图，保存截图。
- file:// 页面：同样确认可调用 Flask。
- 检查 YbII item 的 all/matched/raw marks 是否出图。

完成后更新 progress.md。
```

## Prompt 4: Source Mode Architecture UI

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做 Slice 4：新增“离线分析 / 实时采集”同级模式的架构 UI。不要实现真实串口通信，不要实现 RJ45 网络协议，不要改后端算法。最多修改 3 个文件：
- web_app/index.html
- web_app/app.js
- web_app/styles.css

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- progress.md 尾部
- web_app 当前导入/运行/渲染逻辑

架构要求：
1. 页面提供顶层 source mode：离线分析、实时采集。
2. 离线分析显示打开文件、打开文件夹、已导入文件选择等离线控件。
3. 实时采集显示独立控件，不复用离线文件 selector。
4. 实时采集不是“串口采集”和“RJ45 光谱仪”两个并列来源；它是一个采集板工作流：
   - Web 通过串口或本地 bridge 与延时/采集板通信。
   - 光谱仪通过 RJ45 接在采集板上。
   - Web 上的 IP/端口设置用于发给采集板，让采集板绑定光谱仪，不是浏览器直接 TCP 连光谱仪。
5. 实时采集 UI shell 分成四块：
   - 采集板串口识别 UI：Web Serial 可用性提示、请求/选择串口按钮占位、已授权串口列表占位、插入/拔出状态文案；本 slice 不写具体识别函数。
   - 光谱仪绑定：IP、端口、协议/设备型号占位、发送绑定、测试绑定、绑定状态。
   - 采集控制：单次采集、延时采集、停止采集、使用本次采集分析。
   - 光谱预览：采集时间、点数、波长范围、强度范围、原始数据是否可用。
6. 当前 slice 中实时采集控件可以是 disabled placeholder，但状态必须清楚，不得假装可采集。
7. 离线分析原有运行流程必须不被破坏。

必须写清 UI 文案：
- 实时采集尚未连接设备时，开始分析不可用。
- 采集完成后，后续应把 captured spectrum 交给同一 pipeline。
- 光谱仪 RJ45/IP 设置是发送给采集板的绑定参数，不是浏览器直接连光谱仪。
- Web Serial 在公网 HTTP、非 Chromium 环境可能不可用；本 slice 只需要有对应 UI 文案，不调用 Web Serial API。
- 当前只要求 UI 上有串口插入/授权/不可用状态的位置，不要求写具体识别函数，也不允许发送采集板命令。
- 在真实采集板协议明确前，不要假装连接、绑定或采集已经可用。

验证：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- python3 -m backend.contract_probe RREs/070101_95.csv
- python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

UI 验收：
- HTTP desktop/mobile：切换离线分析和实时采集，确认控件互不混淆。
- 离线分析仍可导入文件并运行。
- 实时采集模式显示采集板串口识别、光谱仪 IP 绑定和采集控制；串口识别只做 UI shell，不调用 Web Serial、不发送协议命令，也不会误触发后端 pipeline。
- file:// 页面仍可运行离线分析。
- 保存 desktop/mobile 截图。

完成后更新 progress.md。
```

## Prompt 5: Acquisition API Contract

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做 Slice 5：实时采集 API/服务契约设计，不写业务代码。新增或更新文档即可，默认不超过 3 个 Markdown 文件。

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- BACKEND_API_CONTRACT.md
- backend/app.py 当前 /api/pipeline/run
- web_app/app.js 当前 source mode UI 状态

目标：
1. 新增 ACQUISITION_API_CONTRACT.md。
2. 明确真实设备拓扑：
   - Browser UI
   - Web Serial 或 backend/local bridge
   - 延时/采集板
   - RJ45
   - 光谱仪
3. 定义一个实时采集 source adapter：acquisition-board，不要拆成 serial-source 和 rj45-source。
4. 定义状态机：
   - board_disconnected
   - serial_unavailable
   - serial_permission_needed
   - serial_port_detected
   - serial_port_disconnected
   - board_connecting
   - board_connected
   - spectrometer_unbound
   - spectrometer_binding
   - spectrometer_bound
   - acquiring
   - capture_complete
   - ready_for_analysis
   - error
5. 定义动作：
   - list serial ports / request port
   - observe serial connect/disconnect
   - connect board
   - disconnect board
   - configure board serial
   - set spectrometer endpoint: ip/port/protocol
   - bind/test spectrometer through board
   - acquire once
   - acquire delayed
   - stop acquisition
   - run pipeline from captured spectrum
6. 明确 captured spectrum 的统一数据格式：
   - filename/source label
   - wavelength/intensity text 或 arrays
   - point_count
   - timestamp
   - device metadata
7. 明确 Web Serial 与 backend/local bridge 的取舍。
8. 明确光谱仪 RJ45/IP 参数由 Web 发送给采集板，由采集板连接光谱仪；浏览器不直接对光谱仪开 raw TCP。
9. 给后续 acquisition-board serial prototype 和 spectrometer binding/capture prototype 各写一个最小实现提示词。

完成后更新 progress.md，记录只改文档、没有实现真实采集。
```

## Prompt 6: Serial Detection UI Shell Only

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务。默认中文回复。

本窗口只做“实时采集里的串口插入/授权识别 UI shell”最小 slice。不要写具体识别函数，不要调用 Web Serial API，不要写采集板通信协议，不要发送串口命令，不要实现光谱仪 RJ45 绑定，不要实现采集，不要改后端算法。最多修改 3 个文件：
- web_app/index.html
- web_app/app.js
- web_app/styles.css

先阅读：
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- progress.md 尾部
- web_app 当前 source mode / realtime UI 代码

目标：
1. 在实时采集模式中显示“采集板串口识别”区域。
2. UI 上要有状态 badge/文案，覆盖：
   - 当前浏览器或页面来源不支持串口识别
   - 等待授权串口
   - 已识别到串口
   - 串口已断开
   - 后续需要 HTTPS/localhost 或 backend/local bridge
3. UI 上要有“选择/授权串口”“刷新串口列表”按钮，但按钮必须是 disabled、not wired、或只显示“待接入”，不能调用 `navigator.serial.requestPort()`。
4. UI 上要有 COM/端口选择控件或列表占位，但列表可以为空态/假数据占位；不能调用 `navigator.serial.getPorts()`。
5. UI 上要有插入/拔出状态的位置，但不能监听 `navigator.serial` 的 `connect` / `disconnect` 事件。
6. UI 只能展示端口可见、已授权、已断开等未来状态，不要 `port.open()`，不要 `writer.write()`，不要发任何采集板命令。
7. “开始分析”仍不可用于实时采集，除非未来有 captured spectrum；本 slice 不得误触发 `/api/pipeline/run`。
8. 离线分析原有导入文件、导入文件夹、示例样本库运行流程必须不破坏。

状态建议：
- serial_unavailable
- serial_permission_needed
- serial_port_detected
- serial_port_disconnected
- error

验证：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- python3 -m backend.contract_probe RREs/070101_95.csv
- python3 -m backend.contract_probe Broaden_research/PureSample_Spectrum/Fe1.asc --allow-empty-fit

Playwright/Chrome 验收：
- HTTP desktop/mobile：切换到实时采集，保存串口识别区域截图。
- UI 显示串口识别区域、状态 badge、端口列表/选择占位、选择/授权按钮占位、刷新按钮占位。
- 证明没有调用 `navigator.serial.requestPort()`、`navigator.serial.getPorts()`、`port.open()` 或 `writer.write()`；可以用代码搜索和 Playwright 控制台错误检查作为证据。
- 离线分析仍可导入 RREs/070101_95.csv 并完成检测。
- file:// 页面仍可运行离线分析；若 Web Serial 不可用，只能显示不可用提示，不能影响离线流程。

完成后更新 progress.md，记录修改文件、验证命令、截图路径。不要声称已经能识别真实串口、控制采集板或采集光谱。
```

# HCI Interaction Roadmap For LIBS Rare-Earth Workstation

## Scope

This roadmap records the HCI refinement sequence for the LIBS rare-earth
detection workstation after the first GitHub backup.

Selected directions from the previous review:

1. Make the result page decision-oriented: the first thing users see should be
   the detection conclusion and review priority, not only intermediate charts.
2. Explain each pipeline stage through input, processing, output, and risk.
3. Turn confidence into calibrated trust, not a bare number.
7. Upgrade event logs into a traceable evidence chain.
9. Clarify the human-machine responsibility split in the interface language.

Hard boundary for this roadmap:

- Do not change algorithm behavior while doing the first HCI slice.
- Do not change backend API paths, stage ids, result numbers, or database files.
- Keep `buildExportPayload()` append-only if report export is touched later.
- `fit.confidenceRescue` must only come from backend payload normalization, not
  frontend heuristics.
- Keep the product model from `UI_WORKFLOW_ARCHITECTURE_HANDOFF.md`: offline
  analysis and real-time acquisition are same-rank modes; real-time acquisition
  is one acquisition-board workflow, not separate serial and RJ45 sources.

## Implementation Order

### 1. Human-Machine Responsibility Language

Corresponds to recommendation 9.

Do this first because it is the conceptual frame for every later UI change. The
current system already has pipeline stages, offline/real-time modes, parameters,
confidence, fit, export, and logs. Before adding heavier UI, the page should
make one thing explicit: the machine proposes structured evidence, and the human
operator remains responsible for source selection, parameter confirmation,
review decisions, and report export.

Primary changes:

- Adjust labels, short descriptions, empty states, status messages, and panel
  headings.
- Make "human action" and "machine computation" visible without adding a large
  tutorial block.
- Prefer professional workstation wording over marketing copy.
- Keep layout changes minimal.

Why first:

- Lowest algorithm risk.
- Gives the later result page, confidence, stage explanation, and evidence log a
  common language.
- Good first task for a new window because it can be constrained to the Web
  files and verified quickly.

Acceptance:

- A user can tell which actions require human confirmation.
- A user can tell which outputs are machine-generated evidence.
- Existing pipeline run, stage contract, and export behavior are unchanged.

### 2. Decision-Oriented Result Page

Corresponds to recommendation 1.

After the responsibility language is clear, redesign the result stage so it
answers the operator's practical question first: what was detected, how strong
is the evidence, what needs review, and what should be exported.

Primary changes:

- Promote the final detected rare-earth element(s), confidence/trust status, and
  review reason above repeated tables.
- Show "machine conclusion" and "human review needed" as separate concepts.
- Keep links or controls that let the user jump back to supporting stages.

Why second:

- It is the most visible user-value improvement.
- It depends on the responsibility wording to avoid pretending the machine is an
  unquestionable authority.

Acceptance:

- The result stage is understandable before reading the inspector table.
- Low-confidence or conflict-heavy results are framed as review tasks.
- Existing numerical values and CSV/report payloads are preserved.

### 3. Calibrated Trust Layer For Confidence

Corresponds to recommendation 3.

Once the result page uses review-oriented language, make confidence readable as
trust evidence. Do not hide the numeric value, but surround it with calibration:
threshold band, reason, matched evidence count, temperature/R2 limits, and
conflict/missing-line warnings when available.

Primary changes:

- Map raw confidence into review bands such as "strong evidence", "needs
  review", and "weak evidence" only as UI interpretation.
- Show the reason behind the band using existing backend payload fields.
- Keep the exact confidence number visible.

Why third:

- The result page needs this to avoid a misleading single-score UI.
- It should reuse current `confidence_calculation` and fit payloads rather than
  asking backend to invent new fields first.

Acceptance:

- Numeric confidence remains visible and unchanged.
- Trust band wording never claims more certainty than the backend evidence
  supports.
- No frontend-only rescue inference is introduced.

### 4. Stage Input / Processing / Output / Risk Explanations

Corresponds to recommendation 2.

After the result and confidence model are clearer, enrich each stage with a
compact explanation of what entered the stage, what the machine did, what came
out, and what risk remains for the human to inspect.

Primary changes:

- Add compact stage metadata panels or inspector sections.
- Use the existing stage contract: raw, peak, match, temperature, fit,
  confidence, result.
- Avoid textbook explanations; each note should describe this run's evidence
  where possible.

Why fourth:

- It needs the responsibility language and trust wording to stay concise.
- It should not compete with the result page for first attention.

Acceptance:

- Every stage has an input, machine process, output, and review/risk statement.
- The statements are connected to available data, not generic HCI prose.
- The chart remains the primary visual in stage views.

### 5. Traceable Evidence Chain

Corresponds to recommendation 7.

Do this after the earlier layers stabilize. A traceable evidence chain is larger
than a log rename: it should connect source, parameters, stage outputs, fit
decisions, confidence calculation, operator review, and export.

Primary changes:

- Rework logs into evidence records with timestamp/source/stage/action/evidence.
- Add filters or grouping by stage and decision.
- Preserve enough information for report export and later experiment audit.

Why fifth:

- It has the highest information-architecture surface area.
- It may touch export payload and therefore must respect append-only report
  contract.
- It should be designed around the final result/trust/stage model rather than
  invented first.

Acceptance:

- The event/evidence area answers "why did this result happen?"
- Exported report can include the evidence chain without breaking old fields.
- Users can distinguish machine evidence from human confirmation.

## Suggested Small Milestones

1. Responsibility copy and minimal UI hooks.
2. Result stage decision summary.
3. Confidence trust bands and reasons.
4. Stage explanation cards or inspector sections.
5. Evidence-chain log model and report integration.

Keep each milestone to at most three business files unless a later task
explicitly approves a broader slice. For Web-only work, prefer:

- `web_app/index.html`
- `web_app/app.js`
- `web_app/styles.css`

## Baseline Verification Commands

Use these commands before claiming a Web/HCI slice is complete:

```bash
node web_app/app.js
python3 -m backend.contract_probe RREs/070101_95.csv
```

If the task changes backend-facing code or Python modules:

```bash
python3 -m compileall -q backend
python3 backend/pipeline.py
```

If the task changes visible layout:

```bash
python3 backend/app.py
```

Then open the local Flask page in Chrome and capture/check at least the desktop
first viewport. For mobile-sensitive changes, also check a narrow viewport.

## First Task Prompt For A New Window

Copy this prompt into the new window:

```text
你在 /home/hpy/RREdetectation-MultiPeakFit 工作。目标是完成 HCI 改造第 1 刀：重写/调整前端界面中的“人-机器职责分工”表达，让 LIBS 稀土检测工作站更像一个人机协作工作台，而不是单纯算法展示页。

先读：
- HCI_INTERACTION_ROADMAP.md
- UI_WORKFLOW_ARCHITECTURE_HANDOFF.md
- web_app/index.html
- web_app/app.js 中与 source mode、stage、result、status/log 文案相关的区域
- web_app/styles.css 中相关布局样式，只有需要支撑文案布局时才改

硬约束：
- 只改 web_app/index.html、web_app/app.js、web_app/styles.css，最多 3 个业务文件。
- 不改 backend、算法、数据库、导出 payload 字段名。
- 不改 buildExportPayload() 既有字段；如果碰到导出，只允许 append-only。
- 不改变检测结果数值、阶段 contract、API 路径。
- fit.confidenceRescue 只能来自 backend payload normalization，不能用前端 heuristics 推断。
- 保持离线/实时采集的现有架构：离线分析和实时采集并列；实时采集是 acquisition-board workflow，不要拆成串口/RJ45 两个并列来源。
- 保持中文界面。

任务内容：
1. 在现有 UI 文案和局部布局中明确区分：
   - 人负责：选择来源、确认参数、选择拟合目标、复核低置信/重叠证据、导出报告。
   - 机器负责：解析光谱、寻峰、谱线匹配、温度迭代、多峰拟合、置信度计算。
2. 优先调整信息架构/标签/说明文案/状态文案，不做大视觉重构。
3. 避免新增显眼教程段落；文案要像专业工作站里的状态/职责提示，而不是产品说明书。
4. 修改前先说明计划，修改后列出具体改动文件。

验证：
- node web_app/app.js
- python3 -m backend.contract_probe RREs/070101_95.csv
- 如改了布局，启动 Flask 并用 Chrome 截桌面首屏，确认没有遮挡/溢出。

交付：
- 列出改动文件。
- 说明哪些文案体现了人机职责分工。
- 给出验证命令和结果。
```

## GitHub Backup Baseline

Initial backup target:

```text
git@github.com:hpylsy/REE_Web.git
```

The backup intentionally prioritizes algorithm, backend, Web app, databases
needed by the pipeline, and small validation samples. Bulky generated corpora,
presentation files, office documents, debug folders, and local editor/agent
state are excluded through `.gitignore`.

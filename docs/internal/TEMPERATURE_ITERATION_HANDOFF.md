# Handoff: T-iteration 多起点温度迭代 3D/伪 3D 展示

## 任务目标

把 Web 应用里的第 4 阶段 `温度迭代` 从当前的单条二维温度轨迹，改成符合项目算法说明的 `T-iteration` 多起点收敛展示：

- 多个初始温度起点同时开始。
- 每个起点经过若干轮 Top-K + 阻尼更新。
- 每轮都有候选元素、目标温度、更新后温度、置信度、R2 和综合 score。
- 最后按全局最高 score 选出最终电子温度。
- 前端主图最好做成 3D 或伪 3D：`Multiple Start`、`Iteration`、`Score` 三个维度，突出最终最高分点。

用户已经明确：`谱线匹配` 当前优化效果可以，`温度迭代` 不对。不要继续做普通二维温度折线。

## 当前重要约束

- 默认中文回复。
- 用户系统是 Ubuntu。
- 不要直接 import 下列研究脚本到 Flask：
  - `Elements_detectation.py`
  - `Wavelet_peakfinding.py`
  - `Identification_Matrix.py`
  - `MultiPeakfit/Gaussfit.py`
- 原因：这些研究脚本里有 Windows 绝对路径、顶层读文件、绘图或执行副作用。
- 后端服务化算法边界在 `backend/pipeline.py`，应继续在这里实现 wrapper 逻辑。
- 用户已要求“这种明确的问题不要反复问同不同意”。下个窗口可以短计划后直接实现，但尽量把实现控制在 3 个文件内：
  - `backend/pipeline.py`
  - `web_app/app.js`
  - `progress.md`
- 若必须改第 4 个文件，例如 `web_app/styles.css`，先说明为什么必须超过 3 文件。

## 先读文件

下个窗口开始时先读：

```bash
sed -n '1,220p' HANDOFF_NEXT_WINDOW.md
sed -n '1,260p' task_plan.md
sed -n '1,320p' findings.md
tail -220 progress.md
sed -n '1,260p' TEMPERATURE_ITERATION_HANDOFF.md
```

再读关键代码：

```bash
nl -ba Elements_detectation.py | sed -n '826,1002p'
nl -ba backend/pipeline.py | sed -n '470,530p;838,912p'
nl -ba web_app/app.js | sed -n '845,910p;1005,1015p;1054,1092p'
```

## 文档依据

用户给出的文本文件：

- `光溯稀土创意组计划书_盲审版.doc`
- `结题验收书4_20.docx`
- `元素识别流程.docx`

这些文档里对温度迭代的描述与用户给的图一致。核心含义：

- 温度迭代算法是全局多起点阻尼优化得分。
- 在合理电子温度区间中选多个起点，防止陷入局部最优。
- 每个起点迭代若干轮。
- 每轮根据基体元素置信度 Top-K，并结合 Boltzmann 拟合 R2 作为评分依据。
- 用 softmax 加权获得目标温度。
- 用阻尼系数更新当前温度。
- 最后比较每个起点的最终得分，选出全局最高分对应的电子温度。

可用下面命令重新抽取文档文本，不要依赖 `/tmp` 旧文件：

```bash
rm -rf /tmp/rre_doc_extract
mkdir -p /tmp/rre_doc_extract
libreoffice --headless --convert-to docx --outdir /tmp/rre_doc_extract 光溯稀土创意组计划书_盲审版.doc
cp 结题验收书4_20.docx /tmp/rre_doc_extract/结题验收书4_20.docx
cp 元素识别流程.docx /tmp/rre_doc_extract/元素识别流程.docx
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

out_dir = Path('/tmp/rre_doc_extract')
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
for path in out_dir.glob('*.docx'):
    texts = []
    with ZipFile(path) as zf:
        names = [
            n for n in zf.namelist()
            if n.startswith('word/') and n.endswith('.xml') and (
                'document.xml' in n or 'footnotes.xml' in n or 'endnotes.xml' in n
            )
        ]
        for name in names:
            root = ET.fromstring(zf.read(name))
            for para in root.findall('.//w:p', ns):
                parts = [node.text or '' for node in para.findall('.//w:t', ns)]
                text = ''.join(parts).strip()
                if text:
                    texts.append(text)
    txt_path = out_dir / (path.stem + '.txt')
    txt_path.write_text('\n'.join(texts), encoding='utf-8')
    print(txt_path)
PY
rg -n "T-iteration|T_iteration|温度迭代|多起点|置信度|评分|收敛|Boltzmann|电子温度|Top-K|TOP-K|Softmax|softmax" /tmp/rre_doc_extract/*.txt
```

## 代码现状

### 研究脚本已有完整思想

`Elements_detectation.py` 里已有多起点 T-iteration 逻辑：

- `Elements_detectation.py:828` `_candidate_score(confidence, r2)`
- `Elements_detectation.py:833` `_pick_target_temperature(...)`
- `Elements_detectation.py:855` `T_iteration_single(...)`
- `Elements_detectation.py:964` `T_iteration(...)`

但不要直接 import 它。只能参考逻辑，继续在 `backend/pipeline.py` 里服务化实现。

### 当前后端只做了单起点

`backend/pipeline.py` 当前温度逻辑：

- `backend/pipeline.py:470` `_candidate_score(confidence, r2)`
- `backend/pipeline.py:474` `_pick_target_temperature(...)`
- `backend/pipeline.py:492` `_temperature_iteration(...)`
- `backend/pipeline.py:839` 调用 `_temperature_iteration(...)`
- `backend/pipeline.py:905` 返回 temperature stage

当前 `_temperature_iteration()` 固定从 `10000 K` 开始，只返回一条 trace：

```python
final_temperature, temperature_trace, main_payload = _temperature_iteration(peak_wavelength, peak_intensity)
```

这不符合多起点展示。

### 当前前端只画二维温度折线

`web_app/app.js` 当前温度图：

- `web_app/app.js:845` `drawTemperature(canvas, appState)`
- `web_app/app.js:1009` 温度表格 rows
- `web_app/app.js:1058` 温度参数 rows
- `web_app/app.js:1088` 温度结果 rows

当前图只是：

- x: iteration
- y: temperature
- bar: confidence
- label: candidate

它不是用户要的 `Multiple Start / Iteration / Score` 展示。

## 推荐后端实现

在 `backend/pipeline.py` 中新增多起点版本，不直接改成 import 研究脚本：

```python
def _temperature_iteration_single(
    peak_wavelength,
    peak_intensity,
    initial_temperature,
    max_iterations=10,
    t_min=5000.0,
    t_max=20000.0,
    alpha=0.35,
    top_k=3,
):
    ...

def _temperature_multistart_iteration(
    peak_wavelength,
    peak_intensity,
    t_min=5000.0,
    t_max=20000.0,
    multistart_count=7,
    max_iterations=10,
    alpha=0.35,
    top_k=3,
):
    ...
```

保留现有 helper：

- `_load_line_database(ELEMENTS_DB_DIR, temperature)`
- `_compute_element_confidence(...)`
- `_pick_target_temperature(...)`
- `_candidate_score(...)`

每轮 trace 建议至少包含：

```python
{
    "iteration": iteration,
    "temperature": round(temperature, 2),
    "target_temperature": round(target_temperature, 2),
    "candidate": top_candidate,
    "confidence": round(candidate_confidence, 4),
    "r2": round(candidate_r2, 4),
    "score": round(current_score, 4),
    "delta": round(abs(temperature - previous_temperature), 4),
}
```

每个起点建议包含：

```python
{
    "start_index": index,
    "initial_temperature": round(t0, 2),
    "final_temperature": round(final_t, 2),
    "best_score": round(best_score, 4),
    "best_candidate": best_candidate,
    "best_confidence": round(best_confidence, 4),
    "best_r2": round(best_r2, 4),
    "selected": index == best_index,
    "trace": trace,
}
```

temperature stage 建议返回：

```python
{
    "id": "temperature",
    "title": "温度迭代",
    "status": "done",
    "summary": f"{final_temperature:.0f} K / score {best_score:.3f}",
    "data": {
        "trace": best_trace,
        "starts": start_payloads,
        "temperature": round(final_temperature, 2),
        "best_start_index": best_index,
        "best_score": round(best_score, 4),
    },
    "parameters": {
        "t_min": 5000.0,
        "t_max": 20000.0,
        "multistart_count": len(start_payloads),
        "iterations": max_iterations,
        "top_k": top_k,
        "alpha": alpha,
    },
}
```

后续 rare earth 谱线库仍使用这个 `final_temperature`：

```python
rare_earth_database = _load_line_database(
    RARE_EARTH_DB_DIR,
    final_temperature,
    main_elements=matrix_elements,
    line_switch=True,
)
```

## 推荐前端实现

在 `web_app/app.js` 中：

1. `normalizeBackendResult()` 解析 `temperature.data.starts`。
2. `buildDemoState()` 也补一个 demo `temperatureStarts`，保持 `node web_app/app.js` 自测可运行。
3. 替换 `drawTemperature()`：
   - 第一版建议用 Canvas 伪 3D，不急着引 Three.js。
   - x 轴：Iteration。
   - y 轴：Multiple Start。
   - z/高度/颜色：Score。
   - 每个起点一条轨迹或半透明面片。
   - 最高分起点用金色点/箭头突出。
   - 标题可显示 `T-iteration`、`best T`、`best score`。
4. `stageRows("temperature")` 改为按起点列摘要：
   - 起点温度
   - 最终温度
   - best score
   - best candidate
   - selected
5. `parameterRows("temperature")` 显示：
   - 起点范围
   - 起点数量
   - Top-K
   - 阻尼系数
6. `resultRows("temperature")` 显示：
   - 最优起点
   - 收敛温度
   - best score

## 伪 3D 绘图建议

不引 Three.js 的情况下，可以用一个投影函数：

```js
function projectTIterationPoint(iteration, startIndex, score, scale) {
  const x = scale.originX + iteration * scale.iterX + startIndex * scale.skewX;
  const y = scale.originY - score * scale.scoreY + startIndex * scale.startY;
  return { x, y };
}
```

视觉策略：

- 背景画 3D box/grid。
- 每个 start 画一条折线，颜色按最终 score 由灰/蓝到金色。
- selected start 加粗。
- 每轮点大小按 confidence 或 score 缩放。
- 最高分点画金色圆点和 `best` 标签。
- 移动端减少标签，只保留 best 标签和轴标签。

## 自测建议

先补红灯断言：

```js
assert(appState.temperatureStarts.length >= 3, "temperature stage should expose multiple starts");
assert(appState.temperatureStarts.some((row) => row.selected), "temperature stage should mark the selected global best start");
```

后端补自测：

```python
result = run_pipeline(text, sample_path.name)
temperature_stage = next(stage for stage in result["stages"] if stage["id"] == "temperature")
assert len(temperature_stage["data"]["starts"]) >= 3
assert any(row["selected"] for row in temperature_stage["data"]["starts"])
assert "best_score" in temperature_stage["data"]
```

## 验证命令

基础验证：

```bash
node web_app/app.js
python3 -m compileall -q backend
python3 backend/pipeline.py
```

API 验证：

```bash
python3 - <<'PY'
from urllib.request import Request, urlopen
import json

req = Request(
    'http://127.0.0.1:5000/api/pipeline/run',
    data=json.dumps({'sample_path': 'RREs/070101_95.csv'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urlopen(req, timeout=60) as response:
    body = json.loads(response.read().decode())

stage = next(item for item in body['stages'] if item['id'] == 'temperature')
print(response.status)
print(stage['summary'])
print('starts', len(stage['data'].get('starts', [])))
print('best', stage['data'].get('best_start_index'), stage['data'].get('best_score'), stage['data'].get('temperature'))
PY
```

Playwright 验证：

- 打开 `http://127.0.0.1:5000`
- 选择 `RREs/070101_95.csv`
- 点击开始
- 等待完成
- 点击 `温度迭代`
- 截图 plot panel，确认是多起点 T-iteration 3D/伪 3D 图，不是单条二维折线。
- 移动端重复一次，确认标签不重叠。

## 可复制给下个窗口的提示词

```text
请接续 /home/hpy/RREdetectation-MultiPeakFit 的 LIBS 稀土检测 Web 应用任务，单独完成 `温度迭代` 阶段改造。

先读：
- HANDOFF_NEXT_WINDOW.md
- task_plan.md
- findings.md
- progress.md
- TEMPERATURE_ITERATION_HANDOFF.md

重点：谱线匹配图当前效果可以，不要继续改谱线匹配。现在要修的是第 4 阶段 `温度迭代`。

用户指出：温度迭代应该是多个初始温度起点开始，每个起点经过 Top-K + 阻尼迭代，最后按全局最高 score 收敛到一个最优点；展示效果参考 T-iteration 图：Multiple Start、Iteration、Score 三个维度，最好做成 3D 或伪 3D。

先在代码里看：
- Elements_detectation.py:826-1002：研究脚本里的 _candidate_score、_pick_target_temperature、T_iteration_single、T_iteration，多起点逻辑在这里，但不要直接 import 这个脚本。
- backend/pipeline.py:470-530 和 838-912：当前 Flask wrapper 只做了单起点 `_temperature_iteration()`，API 只返回一条 trace。
- web_app/app.js:845-910、1005-1015、1054-1092：当前前端只画二维温度折线和单条 trace 表格。

约束：
1. 默认中文回复。
2. 用户系统是 Ubuntu。
3. 不要直接 import Elements_detectation.py、Wavelet_peakfinding.py、Identification_Matrix.py、MultiPeakfit/Gaussfit.py 到 Flask，它们有 Windows 路径/顶层读文件/绘图副作用。
4. 在 backend/pipeline.py 中服务化实现多起点 wrapper，复用已有 `_load_line_database`、`_compute_element_confidence`、`_pick_target_temperature`、`_candidate_score`。
5. 尽量只改 backend/pipeline.py、web_app/app.js、progress.md。若必须超过 3 个文件，先说明原因。
6. 用户已经明确不要反复问“同不同意”；这个任务方向已确定，可以短计划后直接实现。

实现目标：
- 后端新增多起点温度迭代数据，temperature stage 返回 `data.starts`、`data.best_start_index`、`data.best_score`、`data.temperature`。
- 每个 start 包含 initial_temperature、final_temperature、best_score、best_candidate、best_confidence、best_r2、selected、trace。
- 每轮 trace 包含 iteration、temperature、target_temperature、candidate、confidence、r2、score、delta。
- 前端 normalizeBackendResult 解析 `temperatureStarts`。
- drawTemperature 改成 T-iteration 3D/伪 3D 展示：x=Iteration，y=Multiple Start，z/颜色=Score，最高分点高亮。
- 温度阶段表格改成多起点摘要，结果摘要显示最优起点、收敛温度、best score。

验证：
- node web_app/app.js
- python3 -m compileall -q backend
- python3 backend/pipeline.py
- API 跑 RREs/070101_95.csv，确认 temperature stage 有 starts 且有 selected start。
- Playwright 桌面和移动端：选择 RREs/070101_95.csv，运行完成，点击温度迭代，截图确认不是单条二维折线，而是多起点 T-iteration 3D/伪 3D 展示。
```

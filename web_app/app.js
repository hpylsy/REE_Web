const PROCESS_STAGES = [
  {
    id: "raw",
    title: "原始光谱",
    shortLabel: "原始光谱",
    detail: "系统解析波长-强度输入",
    duration: 900,
    tableCaption: "来源确认与光谱解析状态",
  },
  {
    id: "peak",
    title: "寻峰结果",
    shortLabel: "寻峰结果",
    detail: "算法寻峰与峰位校正",
    duration: 1200,
    tableCaption: "算法寻峰候选列表",
  },
  {
    id: "match",
    title: "谱线匹配",
    shortLabel: "谱线匹配",
    detail: "算法匹配理论线与实验峰",
    duration: 1300,
    tableCaption: "谱线匹配、低置信与重叠证据",
  },
  {
    id: "temperature",
    title: "温度迭代",
    shortLabel: "温度迭代",
    detail: "算法迭代电子温度",
    duration: 1100,
    tableCaption: "温度迭代证据",
  },
  {
    id: "fit",
    title: "多峰拟合",
    shortLabel: "多峰拟合",
    detail: "算法分解重叠峰",
    duration: 1500,
    tableCaption: "多峰拟合证据",
  },
  {
    id: "confidence",
    title: "置信度计算",
    shortLabel: "置信度计算",
    detail: "系统计算置信度证据",
    duration: 1000,
    tableCaption: "强度梳与置信度计算明细",
  },
  {
    id: "result",
    title: "检测结果",
    shortLabel: "检测结果",
    detail: "候选结论与待复核证据",
    duration: 900,
    tableCaption: "候选结论与导出前复核",
  },
];

const DEFAULT_SAMPLE_PATH = "RREs/070101_95.csv";
const THREE_JS_LOCAL_URL = "./vendor/three.min.js";
const THREE_JS_CDN_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js";
const THREE_JS_URLS = [THREE_JS_LOCAL_URL, THREE_JS_CDN_URL];
const TEMPERATURE_THREE_CANVAS_CLASS = "temperature-3d-canvas";
const TEMPERATURE_CURVE_COLORS = [0x0072b2, 0xd55e00, 0x009e73, 0xcc79a7, 0x56b4e9, 0xe69f00, 0x6a4c93, 0x8f6b32, 0x2f4858];
const FIT_COMPONENT_COLORS = ["#2f9e44", "#37b24d", "#69db7c", "#8ce99a", "#b2f2bb"];
const CONFIDENCE_COMB_COLORS = {
  allTheoretical: "#8fd3f4",
  matchedTheoretical: "#006bb6",
  matchedExperimental: "#d43d51",
};
const SPECTRUM_ZOOM_STAGE_IDS = new Set(["raw", "peak", "match"]);
const CHART_ZOOM_MIN_WIDTH_NM = 4;
const CHART_ZOOM_MAX_WIDTH_NM = 180;
const CHART_ZOOM_DEFAULT_WIDTHS_NM = {
  raw: 48,
  peak: 28,
  match: 37,
};
const MATCH_ZOOM_MIN_WIDTH_NM = CHART_ZOOM_MIN_WIDTH_NM;
const MATCH_ZOOM_MAX_WIDTH_NM = CHART_ZOOM_MAX_WIDTH_NM;
const MATCH_ZOOM_DEFAULT_WIDTH_NM = CHART_ZOOM_DEFAULT_WIDTHS_NM.match;
const AUTO_FIT_TARGET_LABEL = "自动";
const SOURCE_MODE_LABELS = {
  offline: "离线分析",
  realtime: "实时采集",
};
const SOURCE_MODE_HINTS = {
  offline: "操作者选择本地光谱或示例样本库；系统解析后进入同一检测流程。",
  realtime: "操作者确认采集板与光谱仪参数；采集到光谱后再交给算法流程。",
};
const SERIAL_UI_STATES = {
  serial_unavailable: {
    label: "不支持串口识别",
    message: "当前环境不能识别采集板端口；请检查 HTTPS/localhost 或本地 bridge。",
  },
  serial_permission_needed: {
    label: "参数未确认",
    message: "请由操作者确认采集板端口、光谱仪 IP 和端口参数。",
  },
  serial_port_detected: {
    label: "参数已确认",
    message: "参数已记录；等待采集板 bridge 或串口协议接入。",
  },
  serial_port_disconnected: {
    label: "串口已断开",
    message: "采集板端口状态需复核；当前不监听串口事件。",
  },
  not_wired: {
    label: "待接入",
    message: "采集板通信协议待接入，暂不能产生实时光谱。",
  },
};
const TEMPERATURE_COLOR_STOPS = [
  { at: 0.0, rgb: [43, 101, 177] },
  { at: 0.28, rgb: [55, 162, 167] },
  { at: 0.5, rgb: [122, 182, 72] },
  { at: 0.74, rgb: [240, 182, 74] },
  { at: 1.0, rgb: [200, 75, 49] },
];
const TEMPERATURE_AUTO_ROTATE = false;
const TEMPERATURE_INITIAL_YAW = -0.16;
const TEMPERATURE_INITIAL_PITCH = -0.04;
const SPECTRUM_FILE_EXTENSIONS = new Set([".asc", ".csv", ".txt", ".tsv"]);

function sourceModeRunDisabledReason({ sourceMode = "offline", hasOfflineSource = false, isRunning = false, hasCapturedSpectrum = false } = {}) {
  if (isRunning) {
    return "检测进行中";
  }
  if (sourceMode === "realtime") {
    return hasCapturedSpectrum ? "" : "实时采集尚未产生光谱数据";
  }
  return hasOfflineSource ? "" : "请先打开光谱或文件夹";
}

function normalizeRealtimeParameters({ serialPort = "", spectrometerIp = "", spectrometerPort = "" } = {}) {
  const ip = String(spectrometerIp || "").trim();
  const portText = String(spectrometerPort || "").trim();
  const serial = String(serialPort || "").trim();
  const octets = ip.split(".");
  const port = Number(portText);

  if (
    octets.length !== 4 ||
    octets.some((octet) => !/^\d{1,3}$/.test(octet) || Number(octet) < 0 || Number(octet) > 255)
  ) {
    return { ok: false, error: "光谱仪 IP 格式不正确", serialPort: serial, spectrometerIp: ip, spectrometerPort: portText };
  }
  if (!/^\d+$/.test(portText) || !Number.isInteger(port) || port < 1 || port > 65535) {
    return { ok: false, error: "端口必须是 1-65535 的整数", serialPort: serial, spectrometerIp: ip, spectrometerPort: portText };
  }
  return { ok: true, serialPort: serial, spectrometerIp: ip, spectrometerPort: port };
}

function normalizeRealtimePorts(payload = {}) {
  const rawPorts = Array.isArray(payload.ports) ? payload.ports : [];
  const seen = new Set();
  const ports = [];

  rawPorts.forEach((rawPort) => {
    const path = String(rawPort && rawPort.path ? rawPort.path : "").trim();
    if (!path || seen.has(path)) {
      return;
    }
    seen.add(path);
    ports.push({
      path,
      label: String(rawPort && rawPort.label ? rawPort.label : path).trim() || path,
      source: String(rawPort && rawPort.source ? rawPort.source : "").trim(),
      byId: String(rawPort && rawPort.by_id ? rawPort.by_id : "").trim(),
      target: String(rawPort && rawPort.target ? rawPort.target : "").trim(),
      accessible: Boolean(rawPort && rawPort.accessible),
    });
  });

  const message =
    typeof payload.message === "string" && payload.message.trim()
      ? payload.message.trim()
      : ports.length > 0
        ? `检测到 ${ports.length} 个采集板候选端口`
        : "未检测到采集板端口";

  return { ports, count: ports.length, message };
}

function realtimePortSelectRows({ ports = [], loading = false, error = "" } = {}) {
  if (loading) {
    return [{ value: "", label: "正在识别采集板端口...", disabled: true }];
  }
  if (error) {
    return [{ value: "", label: "端口识别失败", disabled: true }];
  }
  if (!ports.length) {
    return [{ value: "", label: "未检测到采集板端口", disabled: true }];
  }
  return ports.map((port) => ({
    value: port.path,
    label: port.label || port.path,
    disabled: false,
  }));
}

function resolveApiUrl(path, locationLike = typeof window !== "undefined" ? window.location : { protocol: "http:", hostname: "127.0.0.1", port: "5000" }) {
  if (locationLike.protocol === "http:" || locationLike.protocol === "https:") {
    return path;
  }
  return `http://127.0.0.1:5000${path}`;
}

function createPipelineModel() {
  const stages = PROCESS_STAGES.map((stage, index) => ({
    ...stage,
    state: index === 0 ? "active" : "waiting",
    progress: 0,
    summary: index === 0 ? "等待检测" : "未开始",
  }));

  return {
    stages,
    activeIndex: 0,
    selectedIndex: 0,
    isComplete: false,
    reset() {
      this.activeIndex = 0;
      this.selectedIndex = 0;
      this.isComplete = false;
      this.stages.forEach((stage, index) => {
        stage.state = index === 0 ? "active" : "waiting";
        stage.progress = 0;
        stage.summary = index === 0 ? "等待检测" : "未开始";
      });
    },
    setActiveProgress(progress) {
      if (this.activeIndex < 0 || this.activeIndex >= this.stages.length) {
        return;
      }
      this.stages[this.activeIndex].progress = Math.max(0, Math.min(100, progress));
    },
    completeCurrentStage(summary) {
      if (this.activeIndex < 0 || this.activeIndex >= this.stages.length) {
        return;
      }
      const current = this.stages[this.activeIndex];
      current.state = "done";
      current.progress = 100;
      current.summary = summary || "处理完成";

      const nextIndex = this.activeIndex + 1;
      if (nextIndex < this.stages.length) {
        this.activeIndex = nextIndex;
        this.selectedIndex = nextIndex;
        const next = this.stages[nextIndex];
        next.state = "active";
        next.progress = 0;
        next.summary = "等待执行";
      } else {
        this.activeIndex = this.stages.length;
        this.selectedIndex = this.stages.length - 1;
        this.isComplete = true;
      }
    },
    selectStage(index) {
      const bounded = Math.max(0, Math.min(this.stages.length - 1, index));
      this.selectedIndex = bounded;
    },
  };
}

function generateSpectrum(pointCount = 260) {
  const peaks = [
    { center: 324, height: 0.78, width: 2.4 },
    { center: 397, height: 0.38, width: 3.6 },
    { center: 421, height: 0.56, width: 2.8 },
    { center: 516, height: 0.92, width: 3.2 },
    { center: 589, height: 0.46, width: 2.3 },
    { center: 642, height: 0.62, width: 3.0 },
    { center: 760, height: 0.34, width: 4.2 },
  ];
  const data = [];
  for (let i = 0; i < pointCount; i += 1) {
    const x = 260 + (540 * i) / (pointCount - 1);
    const baseline = 0.04 + 0.018 * Math.sin(i * 0.12) + 0.012 * Math.sin(i * 0.43);
    const peakValue = peaks.reduce((sum, peak) => {
      const d = (x - peak.center) / peak.width;
      return sum + peak.height * Math.exp(-0.5 * d * d);
    }, 0);
    const shoulder = 0.15 * Math.exp(-0.5 * Math.pow((x - 530) / 25, 2));
    data.push({ x, y: baseline + shoulder + peakValue });
  }
  return data;
}

function parseCsvSpectrum(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const parsed = [];
  for (const line of lines) {
    const parts = line
      .replace(/,|;|\t|\ufeff/g, " ")
      .split(/\s+/)
      .map((part) => Number(part.trim()));
    const numeric = parts.filter((value) => Number.isFinite(value));
    if (numeric.length >= 2) {
      parsed.push({ x: numeric[0], y: numeric[1] });
    }
  }
  if (parsed.length < 8) {
    return null;
  }
  const yMax = Math.max(...parsed.map((point) => point.y));
  const yMin = Math.min(...parsed.map((point) => point.y));
  const scale = yMax - yMin || 1;
  return parsed.map((point) => ({ x: point.x, y: (point.y - yMin) / scale }));
}

function findDemoPeaks(spectrum) {
  const peaks = [];
  for (let i = 2; i < spectrum.length - 2; i += 1) {
    const p = spectrum[i];
    if (
      p.y > spectrum[i - 1].y &&
      p.y > spectrum[i + 1].y &&
      p.y > spectrum[i - 2].y &&
      p.y > spectrum[i + 2].y &&
      p.y > 0.23
    ) {
      const last = peaks[peaks.length - 1];
      if (!last || Math.abs(last.x - p.x) > 12) {
        peaks.push(p);
      } else if (p.y > last.y) {
        peaks[peaks.length - 1] = p;
      }
    }
  }
  return peaks.slice(0, 10);
}

function buildDemoState() {
  const spectrum = generateSpectrum();
  return {
    spectrum,
    peaks: findDemoPeaks(spectrum),
    baseCandidates: [
      { element: "Si", confidence: 0.91, distance: 0.08, matched: 7, t: 10180, r2: 0.96 },
      { element: "Al", confidence: 0.78, distance: 0.12, matched: 5, t: 9870, r2: 0.93 },
      { element: "Fe", confidence: 0.63, distance: 0.18, matched: 4, t: 10640, r2: 0.89 },
      { element: "Ca", confidence: 0.36, distance: 0.31, matched: 3, t: 9420, r2: 0.72 },
    ],
    spectralMatches: [
      { element: "Pr II", wl: 422.3, status: "enabled", reason: "实验峰匹配", expWl: 421.9, expInt: 0.58 },
      { element: "Tb II", wl: 432.8, status: "blocked", reason: "与 Fe 基体线冲突", expWl: 432.7, expInt: 0.28 },
      { element: "Yb II", wl: 516.96, status: "enabled", reason: "强峰匹配", expWl: 516.7, expInt: 0.96 },
      { element: "La II", wl: 529.6, status: "blocked", reason: "与 Si/Fe 重叠", expWl: 530.1, expInt: 0.42 },
      { element: "Eu II", wl: 642.1, status: "enabled", reason: "无基体冲突", expWl: 642.2, expInt: 0.62 },
      { element: "Nd II", wl: 760.2, status: "review", reason: "低强度低置信", expWl: 760.1, expInt: 0.34 },
    ],
    confidenceCalculation: normalizeConfidenceCalculation({
      formula: { confidence: "exp(-4.5 * distance / max(R2, 1e-9))" },
      temperature_gate: { min_k: 5000, max_k: 20000 },
      scope_nm: 0.2,
      total_count: 2,
      omitted_count: 0,
      items: [
        {
          element: "Yb",
          ion: "YbII",
          confidence: 0.73,
          distance: 0.08,
          temperature: 10320,
          r2: 0.96,
          line_count: 3,
          all_theoretical_comb: [
            { wavelength: 516.96, intensity: 0.62, normalized_intensity: 0.62, A: 1, E: 4.2, g: 4, status: "enabled", matched: true },
            { wavelength: 529.6, intensity: 0.26, normalized_intensity: 0.26, A: 1, E: 4.6, g: 4, status: "enabled", matched: true },
            { wavelength: 589.3, intensity: 0.12, normalized_intensity: 0.12, A: 1, E: 5.1, g: 2, status: "review", matched: false },
          ],
          matched_theoretical_comb: [
            { wavelength: 516.96, intensity: 0.62, normalized_intensity: 0.7, matched_idx: 0 },
            { wavelength: 529.6, intensity: 0.26, normalized_intensity: 0.3, matched_idx: 1 },
          ],
          matched_experimental_comb: [
            { wavelength: 516.7, intensity: 0.96, normalized_intensity: 0.7, delta_nm: 0.26, theoretical_wavelength: 516.96 },
            { wavelength: 530.1, intensity: 0.42, normalized_intensity: 0.3, delta_nm: 0.5, theoretical_wavelength: 529.6 },
          ],
          raw_peak_marks: {
            theoretical_wavelengths: [
              { wavelength: 516.96, normalized_intensity: 0.62, status: "enabled", matched: true },
              { wavelength: 529.6, normalized_intensity: 0.26, status: "enabled", matched: true },
              { wavelength: 589.3, normalized_intensity: 0.12, status: "review", matched: false },
            ],
            selected_experimental_peaks: [
              { wavelength: 516.7, intensity: 0.96, theoretical_wavelength: 516.96, delta_nm: 0.26 },
              { wavelength: 530.1, intensity: 0.42, theoretical_wavelength: 529.6, delta_nm: 0.5 },
            ],
          },
          representative_selection: { selected: true, valid_temperature: true, best_r2: true, reason: "valid_temperature_best_r2" },
        },
      ],
    }),
    temperatureIterations: [
      { iteration: 0, temperature: 8420, targetTemperature: 9060, candidate: "Si", confidence: 0.61, r2: 0.82, score: 0.547, delta: 1420 },
      { iteration: 1, temperature: 9560, targetTemperature: 11680, candidate: "Al", confidence: 0.72, r2: 0.9, score: 0.685, delta: 1140 },
      { iteration: 2, temperature: 10180, targetTemperature: 11330, candidate: "Si", confidence: 0.91, r2: 0.96, score: 0.896, delta: 620 },
      { iteration: 3, temperature: 10320, targetTemperature: 10580, candidate: "Si", confidence: 0.9, r2: 0.95, score: 0.883, delta: 140 },
    ],
    temperatureStarts: [
      {
        startIndex: 0,
        initialTemperature: 5000,
        finalTemperature: 8780,
        bestScore: 0.58,
        bestCandidate: "Mg",
        bestConfidence: 0.64,
        bestR2: 0.88,
        selected: false,
        trace: [
          { iteration: 0, temperature: 6250, targetTemperature: 8570, candidate: "Mg", confidence: 0.48, r2: 0.72, score: 0.382, delta: 1250 },
          { iteration: 1, temperature: 7560, targetTemperature: 9990, candidate: "Mg", confidence: 0.61, r2: 0.84, score: 0.554, delta: 1310 },
          { iteration: 2, temperature: 8780, targetTemperature: 11050, candidate: "Al", confidence: 0.66, r2: 0.83, score: 0.6, delta: 1220 },
        ],
      },
      {
        startIndex: 1,
        initialTemperature: 10000,
        finalTemperature: 10320,
        bestScore: 0.896,
        bestCandidate: "Si",
        bestConfidence: 0.91,
        bestR2: 0.96,
        selected: true,
        trace: [
          { iteration: 0, temperature: 8420, targetTemperature: 9060, candidate: "Si", confidence: 0.61, r2: 0.82, score: 0.547, delta: 1420 },
          { iteration: 1, temperature: 9560, targetTemperature: 11680, candidate: "Al", confidence: 0.72, r2: 0.9, score: 0.685, delta: 1140 },
          { iteration: 2, temperature: 10180, targetTemperature: 11330, candidate: "Si", confidence: 0.91, r2: 0.96, score: 0.896, delta: 620 },
          { iteration: 3, temperature: 10320, targetTemperature: 10580, candidate: "Si", confidence: 0.9, r2: 0.95, score: 0.883, delta: 140 },
        ],
      },
      {
        startIndex: 2,
        initialTemperature: 15000,
        finalTemperature: 11940,
        bestScore: 0.73,
        bestCandidate: "Fe",
        bestConfidence: 0.78,
        bestR2: 0.86,
        selected: false,
        trace: [
          { iteration: 0, temperature: 13980, targetTemperature: 12080, candidate: "Fe", confidence: 0.52, r2: 0.8, score: 0.45, delta: 1020 },
          { iteration: 1, temperature: 12840, targetTemperature: 10720, candidate: "Fe", confidence: 0.69, r2: 0.84, score: 0.634, delta: 1140 },
          { iteration: 2, temperature: 11940, targetTemperature: 10270, candidate: "Si", confidence: 0.78, r2: 0.86, score: 0.731, delta: 900 },
        ],
      },
    ],
    bestTemperatureStartIndex: 1,
    temperatureBestScore: 0.896,
    temperatureParameters: { t_min: 5000, t_max: 20000, multistart_count: 3, iterations: 4, top_k: 3, alpha: 0.35 },
    targetTemperature: 10320,
    matchTolerance: 0.2,
    conflictTolerance: 0.15,
    fitWindow: { left: 510, right: 548, target: 516.96, rms: 0.018 },
    fitBeforeConfidence: 0.0,
    fitAfterConfidence: 0.73,
    fitCandidates: [],
    fitRawPoints: [],
    fitComponentCurves: [],
    fitSumFitPoints: [],
    fitFittedPeaks: [],
    fitLocalExtrema: [],
    fitResidualPoints: [],
    fitBaseline: null,
    fitFallbackReason: null,
    fitConfidenceRescue: null,
    fitComponents: [
      { label: "Yb II", center: 516.96, height: 0.72, width: 3.8, color: "#557a9b" },
      { label: "Si I", center: 529.6, height: 0.58, width: 4.4, color: "#7d8790" },
      { label: "Fe I", center: 538.2, height: 0.32, width: 5.2, color: "#9a8a5d" },
    ],
    fitMarkers: [516.96, 529.6, 538.2],
    rareEarthResults: [
      { name: "Pr", detected: true, confidence: 0.86 },
      { name: "Yb", detected: true, confidence: 0.73 },
      { name: "Eu", detected: true, confidence: 0.58 },
      { name: "Nd", detected: false, confidence: 0.24 },
      { name: "Tb", detected: false, confidence: 0.05 },
      { name: "La", detected: false, confidence: 0.0 },
    ],
    importedName: "模拟光谱",
    fileStatus: "内置样例",
    pointCount: spectrum.length,
    peakMethod: "demo local maxima",
    matchParameters: {},
    fitModel: "Gaussian",
    realMultipeakFit: false,
    detectionThreshold: 0.5,
    matrixElements: ["Si", "Al", "Fe"],
    chartZoom: createDefaultChartZoom("raw"),
    chartCursor: null,
    matchZoom: createDefaultMatchZoom(),
    stageSummaries: {},
    resultCsv: "",
    jobId: null,
  };
}

function stageMapFromBackend(result) {
  return Object.fromEntries((result.stages || []).map((stage) => [stage.id, stage]));
}

function normalizeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function finiteNumberOrNull(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function fileNameFromPath(path) {
  const text = String(path || "").replace(/\\/g, "/");
  return text.split("/").filter(Boolean).at(-1) || text || "未命名样本";
}

function normalizeSampleList(payload) {
  const rows = Array.isArray(payload) ? payload : payload && Array.isArray(payload.samples) ? payload.samples : [];
  const seen = new Set();
  return rows
    .map((row) => {
      const path = String(row && row.path ? row.path : "").trim().replace(/\\/g, "/");
      if (!path || seen.has(path)) {
        return null;
      }
      seen.add(path);
      const group = path.split("/").filter(Boolean)[0] || "样本";
      return {
        path,
        name: String((row && row.name) || fileNameFromPath(path)),
        group,
        size: normalizeNumber(row && row.size),
        label: `${group} / ${String((row && row.name) || fileNameFromPath(path))}`,
      };
    })
    .filter(Boolean);
}

function fileExtension(name) {
  const normalized = String(name || "").trim().toLowerCase();
  const dotIndex = normalized.lastIndexOf(".");
  return dotIndex >= 0 ? normalized.slice(dotIndex) : "";
}

function isSpectrumFile(file) {
  return SPECTRUM_FILE_EXTENSIONS.has(fileExtension(file && file.name));
}

function normalizedBrowserRelativePath(file) {
  return String((file && file.webkitRelativePath) || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean)
    .join("/");
}

function importedFileKey(file) {
  const relativePath = normalizedBrowserRelativePath(file);
  if (relativePath) {
    return `path:${relativePath}`;
  }
  const name = String((file && file.name) || "unnamed-spectrum");
  const size = normalizeNumber(file && file.size);
  const lastModified = normalizeNumber(file && file.lastModified);
  return `file:${name}|${size}|${lastModified}`;
}

function importedFileLabel(file) {
  return normalizedBrowserRelativePath(file) || String((file && file.name) || "未命名光谱");
}

function importedFileRunDisabledReason(importedFile) {
  if (!importedFile) {
    return "请先打开光谱或文件夹";
  }
  if (importedFile.previewStatus === "invalid_spectrum") {
    return "请选择原始光谱文件";
  }
  if (importedFile.previewStatus === "read_error") {
    return "本地读取失败";
  }
  return "";
}

function normalizeImportedFiles(files, existingFiles = []) {
  const seen = new Set();
  const rows = [];

  function addFile(entry) {
    const file = entry && entry.file ? entry.file : entry;
    if (!file || !isSpectrumFile(file)) {
      return;
    }
    const key = entry && entry.key ? String(entry.key) : importedFileKey(file);
    if (!key || seen.has(key)) {
      return;
    }
    seen.add(key);
    rows.push({
      key,
      file,
      name: String(file.name || "未命名光谱"),
      label: entry && entry.label ? String(entry.label) : importedFileLabel(file),
      size: normalizeNumber(file.size),
    });
  }

  Array.from(existingFiles || []).forEach(addFile);
  Array.from(files || []).forEach(addFile);
  return rows;
}

function findImportedFileByKey(importedFiles, key) {
  return (Array.isArray(importedFiles) ? importedFiles : []).find((file) => file.key === key) || null;
}

function importedSelectRows(importedFiles) {
  const rows = Array.isArray(importedFiles) ? importedFiles : [];
  if (rows.length === 0) {
    return [{ key: "", value: "", label: "未导入文件", file: null, disabled: true }];
  }
  return rows.map((file) => ({
    key: file.key,
    value: file.key,
    label: file.label,
    file: file.file,
    disabled: false,
  }));
}

function nextImportedFilesForSource(files, existingFiles = [], sourceType = "file") {
  if (sourceType === "folder") {
    return normalizeImportedFiles(files);
  }
  return normalizeImportedFiles(files, existingFiles);
}

function sampleLibrarySelectRows(samples) {
  const rows = Array.isArray(samples) ? samples : [];
  if (rows.length === 0) {
    return [{ value: "", label: "未加载示例样本库", path: "", disabled: true }];
  }
  return [
    { value: "", label: "选择示例样本", path: "", disabled: false },
    ...rows.map((sample) => ({
      value: sample.path,
      label: `示例 / ${sample.label}`,
      path: sample.path,
      disabled: false,
    })),
  ];
}

function buildSampleLibraryRequestPayload(samplePath, fitTargetValue = "") {
  const path = String(samplePath || "").trim();
  if (!path) {
    return null;
  }
  return buildPipelineRunPayload(path, fitTargetValue);
}

function findSampleByPath(samples, path) {
  return samples.find((sample) => sample.path === path) || null;
}

function chooseSamplePath(samples, preferredPath = DEFAULT_SAMPLE_PATH) {
  if (findSampleByPath(samples, preferredPath)) {
    return preferredPath;
  }
  return samples.length > 0 ? samples[0].path : preferredPath;
}

function sampleNameForPath(samples, path) {
  const sample = findSampleByPath(samples, path);
  return sample ? sample.name : fileNameFromPath(path);
}

function normalizeFitTargetValue(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

function parseFitTargetValue(value) {
  if (!value) {
    return null;
  }
  try {
    const target = JSON.parse(value);
    if (!target || typeof target !== "object") {
      return null;
    }
    const wavelength = normalizeNumber(target.wavelength, NaN);
    if (!Number.isFinite(wavelength)) {
      return null;
    }
    return {
      element: String(target.element || "").trim(),
      ion: String(target.ion || "").trim(),
      wavelength,
      source: String(target.source || "coarse_matched").trim() || "coarse_matched",
    };
  } catch (error) {
    return null;
  }
}

function fitTargetLabel(target) {
  if (!target) {
    return AUTO_FIT_TARGET_LABEL;
  }
  const element = target.element && target.element !== target.ion ? ` / ${target.element}` : "";
  return `${target.ion}${element} · ${target.wavelength.toFixed(4)} nm`;
}

function buildFitTargetOptions(appState, selectedValue = "") {
  const options = [{ value: "", label: AUTO_FIT_TARGET_LABEL, target: null }];
  const seen = new Set([""]);
  const matches = Array.isArray(appState.spectralMatches) ? appState.spectralMatches : [];

  matches
    .filter((line) => line.element && Number.isFinite(line.wl))
    .forEach((line) => {
      const target = {
        element: line.baseElement || line.element.replace(/\s*(III|II|IV|VI|V|I)$/i, ""),
        ion: line.element,
        wavelength: Number(line.wl.toFixed(4)),
        source: "coarse_matched",
      };
      const value = normalizeFitTargetValue(target);
      if (seen.has(value)) {
        return;
      }
      seen.add(value);
      const delta = Number.isFinite(line.deltaNm) ? ` · Δ ${line.deltaNm.toFixed(4)}` : "";
      options.push({
        value,
        label: `${fitTargetLabel(target)}${delta}`,
        target,
      });
    });

  const selectedTarget = parseFitTargetValue(selectedValue);
  if (selectedValue && selectedTarget && !seen.has(selectedValue)) {
    options.push({ value: selectedValue, label: fitTargetLabel(selectedTarget), target: selectedTarget });
  }
  return options;
}

function buildPipelineRunPayload(samplePath, fitTargetValue = "") {
  const payload = { sample_path: samplePath || DEFAULT_SAMPLE_PATH };
  const fitTarget = parseFitTargetValue(fitTargetValue);
  if (fitTarget) {
    payload.fit_target = fitTarget;
  }
  return payload;
}

function buildUploadedFileRequestBody(selectedFile, fitTargetValue = "", FormDataClass = typeof FormData !== "undefined" ? FormData : null) {
  if (!selectedFile) {
    return null;
  }
  const runDisabledReason = selectedFile.file ? importedFileRunDisabledReason(selectedFile) : "";
  if (runDisabledReason) {
    return null;
  }
  const file = selectedFile.file || selectedFile;
  if (!FormDataClass) {
    throw new Error("当前环境不支持 FormData");
  }
  const body = new FormDataClass();
  body.append("file", file);
  const fitTarget = parseFitTargetValue(fitTargetValue);
  if (fitTarget) {
    body.append("fit_target", JSON.stringify(fitTarget));
  }
  return body;
}

function shouldAutoRunAfterFitTargetChange({ isRunning, hasFitOptions, selectedValue }) {
  return !isRunning && hasFitOptions && Boolean(selectedValue);
}

function shouldUseFitOnlyRun({ jobId, isRunning, selectedValue }) {
  return !isRunning && Boolean(jobId) && Boolean(selectedValue);
}

function normalizeTemperatureTrace(trace) {
  return (Array.isArray(trace) ? trace : []).map((row) => ({
    iteration: normalizeNumber(row.iteration),
    temperature: normalizeNumber(row.temperature),
    targetTemperature: normalizeNumber(row.target_temperature, normalizeNumber(row.targetTemperature)),
    candidate: row.candidate || "无",
    confidence: normalizeNumber(row.confidence),
    r2: normalizeNumber(row.r2),
    score: normalizeNumber(row.score, normalizeNumber(row.confidence) - 0.35 * Math.abs(normalizeNumber(row.r2) - 1)),
    delta: normalizeNumber(row.delta),
  }));
}

function normalizeTemperatureStart(start, index) {
  const trace = normalizeTemperatureTrace(start.trace);
  const lastTracePoint = trace.at(-1) || {};
  return {
    startIndex: normalizeNumber(start.start_index, normalizeNumber(start.startIndex, index)),
    initialTemperature: normalizeNumber(start.initial_temperature, normalizeNumber(start.initialTemperature)),
    finalTemperature: normalizeNumber(start.final_temperature, normalizeNumber(start.finalTemperature, lastTracePoint.temperature)),
    bestScore: normalizeNumber(start.best_score, normalizeNumber(start.bestScore)),
    bestCandidate: start.best_candidate || start.bestCandidate || lastTracePoint.candidate || "无",
    bestConfidence: normalizeNumber(start.best_confidence, normalizeNumber(start.bestConfidence, lastTracePoint.confidence)),
    bestR2: normalizeNumber(start.best_r2, normalizeNumber(start.bestR2, lastTracePoint.r2)),
    selected: Boolean(start.selected),
    trace,
  };
}

function normalizeFitPoint(point) {
  return {
    x: normalizeNumber(point.x, normalizeNumber(point.wavelength)),
    y: normalizeNumber(point.y, normalizeNumber(point.intensity)),
  };
}

function normalizeFitPoints(points) {
  return (Array.isArray(points) ? points : [])
    .map(normalizeFitPoint)
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
}

function normalizeFitMarker(point) {
  return {
    label: point.label || "fit",
    wavelength: normalizeNumber(point.wavelength, normalizeNumber(point.x)),
    intensity: normalizeNumber(point.intensity, normalizeNumber(point.y)),
    amplitude: normalizeNumber(point.amplitude),
    sigma: normalizeNumber(point.sigma),
  };
}

function normalizeLocalExtremum(point) {
  return {
    wavelength: normalizeNumber(point.wavelength, normalizeNumber(point.x)),
    intensity: normalizeNumber(point.intensity, normalizeNumber(point.y)),
  };
}

function normalizeFitComponentCurve(curve, index) {
  return {
    label: curve.label || `Component ${index + 1}`,
    center: normalizeNumber(curve.center),
    height: normalizeNumber(curve.amplitude),
    width: Math.max(0.01, normalizeNumber(curve.sigma, 0.08)),
    color: FIT_COMPONENT_COLORS[index % FIT_COMPONENT_COLORS.length],
    points: normalizeFitPoints(curve.points),
  };
}

function normalizeFitCandidate(candidate, index) {
  return {
    source: candidate.source || (index === 0 ? "normalized_pure_element" : "matrix"),
    element: candidate.element || "",
    label: candidate.label || `候选 ${index + 1}`,
    center: normalizeNumber(candidate.center, normalizeNumber(candidate.wavelength)),
    lineIntensity: normalizeNumber(candidate.line_intensity, normalizeNumber(candidate.lineIntensity)),
    lineType: candidate.line_type || candidate.lineType || "",
    rank: normalizeNumber(candidate.rank, index),
  };
}

function normalizeFitConfidenceRescue(rescue) {
  if (!rescue || typeof rescue !== "object") {
    return null;
  }
  const appendedPeaks = (Array.isArray(rescue.appended_peaks) ? rescue.appended_peaks : Array.isArray(rescue.appendedPeaks) ? rescue.appendedPeaks : []).map((peak) => ({
    label: peak.label || "",
    wavelength: finiteNumberOrNull(peak.wavelength ?? peak.x),
    intensity: finiteNumberOrNull(peak.intensity ?? peak.y),
    amplitude: finiteNumberOrNull(peak.amplitude),
    sigma: finiteNumberOrNull(peak.sigma),
  }));
  return {
    applied: Boolean(rescue.applied),
    reason: rescue.reason || "",
    targetElement: rescue.target_element || rescue.targetElement || null,
    baseConfidence: normalizeNumber(rescue.base_confidence ?? rescue.baseConfidence),
    recomputedConfidence: finiteNumberOrNull(rescue.recomputed_confidence ?? rescue.recomputedConfidence),
    appendedPeakCount: normalizeNumber(rescue.appended_peak_count ?? rescue.appendedPeakCount, appendedPeaks.length),
    appendedPeaks,
  };
}

function normalizeCombRow(row) {
  return {
    wavelength: normalizeNumber(row && row.wavelength),
    intensity: normalizeNumber(row && row.intensity),
    normalizedIntensity: normalizeNumber(row && (row.normalized_intensity ?? row.normalizedIntensity)),
    status: (row && row.status) || "review",
    matched: Boolean(row && row.matched),
    matchedIdx: row && row.matched_idx !== undefined ? normalizeNumber(row.matched_idx) : null,
    theoreticalWavelength: normalizeNumber(row && (row.theoretical_wavelength ?? row.theoreticalWavelength)),
    deltaNm: normalizeNumber(row && (row.delta_nm ?? row.deltaNm)),
    A: normalizeNumber(row && row.A),
    E: normalizeNumber(row && row.E),
    g: normalizeNumber(row && row.g),
  };
}

function normalizeExperimentalPeak(row) {
  return {
    wavelength: normalizeNumber(row && row.wavelength),
    intensity: normalizeNumber(row && row.intensity),
    theoreticalWavelength: normalizeNumber(row && (row.theoretical_wavelength ?? row.theoreticalWavelength)),
    deltaNm: normalizeNumber(row && (row.delta_nm ?? row.deltaNm)),
    matchedIdx: row && row.matched_idx !== undefined ? normalizeNumber(row.matched_idx) : null,
  };
}

function confidenceSelectionReason(selection) {
  const reason = String((selection && selection.reason) || "");
  const labels = {
    valid_temperature_best_r2: "T 门内且 R2 最高，选为代表粒子",
    valid_temperature_not_best_r2: "T 门内，但不是该元素 R2 最高粒子",
    insufficient_matched_lines_for_boltzmann: "匹配线不足，无法稳定计算 Boltzmann T/R2",
    no_valid_boltzmann_temperature: "未得到有效 Boltzmann 温度",
    out_of_temperature_gate: "T 不在 5000-20000 K 门限内",
    non_positive_r2: "R2 非正，置信度置零",
  };
  return labels[reason] || reason || "未参与代表粒子选择";
}

function normalizeConfidenceItem(item, index) {
  const rawPeakMarks = item && item.raw_peak_marks ? item.raw_peak_marks : {};
  const allTheoreticalComb = (Array.isArray(item && item.all_theoretical_comb) ? item.all_theoretical_comb : []).map(normalizeCombRow);
  const matchedTheoreticalComb = (Array.isArray(item && item.matched_theoretical_comb) ? item.matched_theoretical_comb : []).map(normalizeCombRow);
  const matchedExperimentalComb = (Array.isArray(item && item.matched_experimental_comb) ? item.matched_experimental_comb : []).map(normalizeCombRow);
  const theoreticalWavelengths = (Array.isArray(rawPeakMarks.theoretical_wavelengths) ? rawPeakMarks.theoretical_wavelengths : []).map(normalizeCombRow);
  const selectedExperimentalPeaks = (Array.isArray(rawPeakMarks.selected_experimental_peaks) ? rawPeakMarks.selected_experimental_peaks : []).map(normalizeExperimentalPeak);
  const representativeSelection = item && item.representative_selection ? item.representative_selection : {};
  return {
    index,
    element: (item && item.element) || "",
    ion: (item && item.ion) || `ion-${index + 1}`,
    label: `${(item && item.ion) || `ion-${index + 1}`} ${(item && item.element) || ""}`.trim(),
    confidence: normalizeNumber(item && item.confidence),
    elementConfidence: normalizeNumber(item && (item.element_confidence ?? item.elementConfidence)),
    distance: normalizeNumber(item && item.distance),
    temperature: normalizeNumber(item && item.temperature),
    r2: normalizeNumber(item && item.r2),
    lineCount: normalizeNumber(item && (item.line_count ?? item.lineCount)),
    allTheoreticalComb,
    matchedTheoreticalComb,
    matchedExperimentalComb,
    rawPeakMarks: {
      theoreticalWavelengths,
      selectedExperimentalPeaks,
      spectrumSource: rawPeakMarks.spectrum_source || "",
    },
    normalization: (item && item.normalization) || {},
    representativeSelection: {
      selected: Boolean(representativeSelection.selected),
      validTemperature: Boolean(representativeSelection.valid_temperature ?? representativeSelection.validTemperature),
      bestR2: Boolean(representativeSelection.best_r2 ?? representativeSelection.bestR2),
      reason: representativeSelection.reason || "",
      rule: representativeSelection.rule || "",
      label: confidenceSelectionReason(representativeSelection),
    },
  };
}

function defaultConfidenceItem(items) {
  const candidates = items
    .filter((item) => item.lineCount > 0 && item.matchedTheoreticalComb.length && item.matchedExperimentalComb.length)
    .sort((left, right) => right.confidence - left.confidence || right.lineCount - left.lineCount || left.ion.localeCompare(right.ion));
  return candidates[0] || items[0] || null;
}

function normalizeConfidenceCalculation(payload) {
  const rawItems = Array.isArray(payload && payload.items) ? payload.items : [];
  const items = rawItems.map(normalizeConfidenceItem);
  const selectedItem = defaultConfidenceItem(items);
  return {
    formula: (payload && payload.formula) || {},
    temperatureGate: (payload && payload.temperature_gate) || {},
    scopeNm: normalizeNumber(payload && payload.scope_nm, 0.2),
    totalCount: normalizeNumber(payload && payload.total_count, items.length),
    omittedCount: normalizeNumber(payload && payload.omitted_count),
    parityGap: Array.isArray(payload && payload.parity_gap) ? payload.parity_gap : [],
    items,
    selectedIon: selectedItem ? selectedItem.ion : "",
    selectedItem,
  };
}

function selectedConfidenceItem(confidenceCalculation) {
  const calculation = confidenceCalculation || { items: [] };
  return (
    calculation.items.find((item) => item.ion === calculation.selectedIon) ||
    defaultConfidenceItem(calculation.items) ||
    null
  );
}

function confidenceIonOptionLabel(item) {
  if (!item) {
    return "无";
  }
  const selectedMark = item.representativeSelection && item.representativeSelection.selected ? "代表" : "备选";
  const matched = `${item.matchedTheoreticalComb.length}/${item.allTheoreticalComb.length}`;
  return `${item.ion} / ${item.element || "未知"} · conf ${item.confidence.toFixed(4)} · ${matched} · ${selectedMark}`;
}

function syncSelectedConfidenceIon(confidenceCalculation, selectedIon = "") {
  const calculation = confidenceCalculation || { items: [] };
  if (!calculation.items.length) {
    calculation.selectedIon = "";
    calculation.selectedItem = null;
    return null;
  }
  const nextItem =
    calculation.items.find((item) => item.ion === selectedIon) ||
    calculation.items.find((item) => item.ion === calculation.selectedIon) ||
    defaultConfidenceItem(calculation.items);
  calculation.selectedIon = nextItem ? nextItem.ion : "";
  calculation.selectedItem = nextItem || null;
  return nextItem || null;
}

function normalizeBackendResult(result) {
  const stages = stageMapFromBackend(result);
  const raw = stages.raw || {};
  const peak = stages.peak || {};
  const match = stages.match || {};
  const temperature = stages.temperature || {};
  const fit = stages.fit || {};
  const detection = stages.result || {};

  const rawData = raw.data || {};
  const peakData = peak.data || {};
  const matchData = match.data || {};
  const temperatureData = temperature.data || {};
  const fitData = fit.data || {};
  const resultData = detection.data || {};

  const spectrum = (rawData.preview || []).map((point) => ({
    x: normalizeNumber(point.x),
    y: normalizeNumber(point.y),
  }));
  const drawableSpectrum = spectrum.length >= 2 ? spectrum : generateSpectrum();

  const peaks = (peakData.peaks || []).map((item) => ({
    x: normalizeNumber(item.wavelength),
    y: normalizeNumber(item.intensity),
    index: normalizeNumber(item.index),
    prominence: normalizeNumber(item.prominence),
  }));

  const baseCandidates = (matchData.base_candidates || []).map((row) => ({
    element: row.element || "未知",
    confidence: normalizeNumber(row.confidence),
    distance: normalizeNumber(row.distance),
    matched: normalizeNumber(row.matched),
    temperature: normalizeNumber(row.temperature),
    t: normalizeNumber(row.temperature),
    r2: normalizeNumber(row.r2),
  }));

  const spectralMatches = (matchData.spectral_matches || []).map((line) => {
    const matchedPeak = line.matched_peak || {};
    return {
      element: line.ion || line.element || "未知谱线",
      baseElement: line.element || "",
      wl: normalizeNumber(line.wavelength),
      status: line.status || "review",
      reason: line.reason || "",
      expWl: normalizeNumber(matchedPeak.wavelength, normalizeNumber(line.wavelength)),
      expInt: normalizeNumber(matchedPeak.intensity),
      confidence: normalizeNumber(line.confidence),
      deltaNm: normalizeNumber(line.delta_nm),
    };
  });
  const confidenceCalculation = normalizeConfidenceCalculation(matchData.confidence_calculation || {});

  const backendTemperatureStarts = Array.isArray(temperatureData.starts) ? temperatureData.starts : [];
  const temperatureStarts = backendTemperatureStarts.map((start, index) => normalizeTemperatureStart(start, index));
  const bestTemperatureStartIndex = normalizeNumber(temperatureData.best_start_index, temperatureStarts.findIndex((start) => start.selected));
  let selectedTemperatureStart =
    temperatureStarts.find((start) => start.selected) ||
    temperatureStarts.find((start) => start.startIndex === bestTemperatureStartIndex) ||
    temperatureStarts[bestTemperatureStartIndex] ||
    temperatureStarts[0] ||
    null;
  let temperatureIterations = selectedTemperatureStart && selectedTemperatureStart.trace.length ? selectedTemperatureStart.trace : normalizeTemperatureTrace(temperatureData.trace);
  if (temperatureIterations.length === 0) {
    temperatureIterations.push({
      iteration: 0,
      temperature: normalizeNumber(temperatureData.temperature, 10000),
      targetTemperature: normalizeNumber(temperatureData.temperature, 10000),
      candidate: "无",
      confidence: 0,
      r2: 0,
      score: 0,
      delta: 0,
    });
  }
  if (temperatureStarts.length === 0) {
    temperatureStarts.push({
      startIndex: 0,
      initialTemperature: temperatureIterations[0].temperature,
      finalTemperature: normalizeNumber(temperatureData.temperature, temperatureIterations.at(-1).temperature),
      bestScore: normalizeNumber(temperatureData.best_score),
      bestCandidate: temperatureIterations.at(-1).candidate,
      bestConfidence: temperatureIterations.at(-1).confidence,
      bestR2: temperatureIterations.at(-1).r2,
      selected: true,
      trace: temperatureIterations,
    });
    selectedTemperatureStart = temperatureStarts[0];
  }

  const windowNm = Array.isArray(fitData.window_nm) && fitData.window_nm.length === 2 ? fitData.window_nm : [0, 1];
  const fitRawPoints = normalizeFitPoints(fitData.raw_points);
  const fitComponentCurves = (Array.isArray(fitData.component_curves) ? fitData.component_curves : []).map((curve, index) => normalizeFitComponentCurve(curve, index));
  const fitSumFitPoints = normalizeFitPoints(fitData.sum_fit_points);
  const fitFittedPeaks = (Array.isArray(fitData.fitted_peaks) ? fitData.fitted_peaks : []).map(normalizeFitMarker);
  const fitCandidates = (Array.isArray(fitData.fit_candidates) ? fitData.fit_candidates : [])
    .map((candidate, index) => normalizeFitCandidate(candidate, index))
    .filter((candidate) => Number.isFinite(candidate.center));
  const fitLocalExtrema = (Array.isArray(fitData.local_extrema) ? fitData.local_extrema : []).map(normalizeLocalExtremum);
  const fitResidualPoints = normalizeFitPoints(fitData.residual_points);
  const baselineNumber = Number(fitData.baseline);
  const fitBaseline = Number.isFinite(baselineNumber) ? baselineNumber : null;
  const fitComponents = (fitData.components || []).map((component, index) => ({
    label: component.label || `Component ${index + 1}`,
    center: normalizeNumber(component.center),
    height: normalizeNumber(component.amplitude),
    width: Math.max(0.01, normalizeNumber(component.sigma, 0.08)),
    color: FIT_COMPONENT_COLORS[index % FIT_COMPONENT_COLORS.length],
  }));
  if (fitComponents.length === 0 && spectralMatches.length > 0) {
    fitComponents.push({
      label: spectralMatches[0].element,
      center: spectralMatches[0].expWl,
      height: spectralMatches[0].expInt,
      width: 0.08,
      color: FIT_COMPONENT_COLORS[0],
    });
  }

  const rareEarthResults = (resultData.rare_earth_results || []).map((row) => ({
    name: row.element || row.name || "未知",
    detected: Boolean(row.detected),
    confidence: normalizeNumber(row.confidence),
    temperature: normalizeNumber(row.temperature),
    r2: normalizeNumber(row.r2),
    matched: normalizeNumber(row.matched),
  }));

  return {
    spectrum: drawableSpectrum,
    peaks,
    baseCandidates,
    spectralMatches,
    confidenceCalculation,
    temperatureIterations,
    temperatureStarts,
    bestTemperatureStartIndex: selectedTemperatureStart ? selectedTemperatureStart.startIndex : bestTemperatureStartIndex,
    temperatureBestScore: normalizeNumber(temperatureData.best_score, selectedTemperatureStart ? selectedTemperatureStart.bestScore : 0),
    temperatureParameters: temperature.parameters || {},
    targetTemperature: normalizeNumber(temperatureData.temperature, temperatureIterations.at(-1).temperature),
    matchTolerance: normalizeNumber((match.parameters || {}).match_tolerance_nm, 0.2),
    conflictTolerance: 0.15,
    fitWindow: {
      left: normalizeNumber(windowNm[0]),
      right: normalizeNumber(windowNm[1], normalizeNumber(windowNm[0]) + 1),
      target: normalizeNumber(
        fitData.fitted_peaks && fitData.fitted_peaks[0] ? fitData.fitted_peaks[0].wavelength : fitData.components && fitData.components[0] ? fitData.components[0].center : windowNm[0],
      ),
      rms: normalizeNumber(fitData.rms),
    },
    fitBeforeConfidence: normalizeNumber(fitData.before_confidence),
    fitAfterConfidence: normalizeNumber(fitData.after_confidence),
    fitRawPoints,
    fitComponentCurves,
    fitSumFitPoints,
    fitFittedPeaks,
    fitCandidates,
    fitLocalExtrema,
    fitResidualPoints,
    fitBaseline,
    fitFallbackReason: fitData.fallback_reason || null,
    fitConfidenceRescue: normalizeFitConfidenceRescue(fitData.confidence_rescue),
    fitComponents,
    fitMarkers: fitFittedPeaks.length ? fitFittedPeaks.map((peak) => peak.wavelength) : fitComponents.map((component) => component.center),
    rareEarthResults,
    importedName: result.filename || rawData.filename || "后端光谱",
    fileStatus: "后端结果",
    pointCount: normalizeNumber(rawData.point_count, drawableSpectrum.length),
    peakMethod: (peak.parameters || {}).method || "后端寻峰",
    matchParameters: match.parameters || {},
    fitModel: (fit.parameters || {}).model || "Gaussian",
    realMultipeakFit: Boolean(fitData.real_multipeak_fit),
    detectionThreshold: normalizeNumber(resultData.detection_threshold, 0.05),
    matrixElements: matchData.matrix_elements || baseCandidates.map((row) => row.element),
    stageSummaries: Object.fromEntries(Object.values(stages).map((stage) => [stage.id, stage.summary || "处理完成"])),
    resultCsv: result.result_csv || "",
    jobId: result.job_id || null,
  };
}

function applyPipelineResult(appState, result) {
  const previousConfidenceIon = appState.confidenceCalculation && appState.confidenceCalculation.selectedIon;
  Object.assign(appState, normalizeBackendResult(result));
  syncSelectedConfidenceIon(appState.confidenceCalculation, previousConfidenceIon);
}

function stageSummary(stageId, appState) {
  if (appState.stageSummaries && appState.stageSummaries[stageId]) {
    return appState.stageSummaries[stageId];
  }
  const peakCount = appState.peaks.length;
  const highMatrix = appState.baseCandidates
    .filter((row) => row.confidence > 0.6)
    .map((row) => row.element)
    .join(", ");
  const enabledCount = appState.spectralMatches.filter((line) => line.status === "enabled").length;
  const blockedCount = appState.spectralMatches.filter((line) => line.status === "blocked").length;
  const selectedTemperatureStart = appState.temperatureStarts.find((start) => start.selected) || appState.temperatureStarts[0];
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const detected = appState.rareEarthResults
    .filter((row) => row.detected)
    .map((row) => row.name)
    .join(", ");

  return {
    raw: `系统已解析 ${appState.importedName}`,
    peak: `算法检测到 ${peakCount} 个候选峰`,
    match: `算法证据: 基体 ${highMatrix || "无"}，稀土匹配 ${enabledCount} 条，重叠待复核 ${blockedCount} 条`,
    temperature: `算法从起点 #${selectedTemperatureStart ? selectedTemperatureStart.startIndex + 1 : 1} 收敛 ${appState.targetTemperature.toFixed(0)} K，评分 ${normalizeNumber(appState.temperatureBestScore).toFixed(3)}`,
    fit: `算法拟合后置信度 ${appState.fitAfterConfidence.toFixed(2)}`,
    confidence: confidenceItem
      ? `系统证据 ${confidenceItem.ion} 置信度 ${confidenceItem.confidence.toFixed(4)}，匹配 ${confidenceItem.matchedTheoreticalComb.length}/${confidenceItem.allTheoreticalComb.length}`
      : "无置信度计算 payload",
    result: `候选结论: ${detected || "无"}，待复核后导出`,
  }[stageId];
}

function disposeTemperatureThreeCanvas(canvas) {
  const host = canvas && canvas.parentElement;
  const threeCanvas = host ? host.querySelector(`.${TEMPERATURE_THREE_CANVAS_CLASS}`) : null;
  if (threeCanvas && typeof threeCanvas.__disposeTemperatureScene === "function") {
    threeCanvas.__disposeTemperatureScene();
  }
  if (threeCanvas && threeCanvas.parentElement) {
    threeCanvas.parentElement.removeChild(threeCanvas);
  }
}

function restoreMainCanvas(canvas) {
  disposeTemperatureThreeCanvas(canvas);
  if (canvas) {
    canvas.style.display = "block";
    canvas.dataset.chartMode = "2d";
  }
}

function getCanvasMetrics(canvas) {
  restoreMainCanvas(canvas);
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

function clearCanvas(ctx, width, height) {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
}

function drawAxes(ctx, width, height, labelY = "Intensity", padOverride = {}) {
  const pad = { left: 48, right: 18, top: 22, bottom: 34, ...padOverride };
  ctx.strokeStyle = "#c2c8cf";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, height - pad.bottom);
  ctx.lineTo(width - pad.right, height - pad.bottom);
  ctx.stroke();

  ctx.fillStyle = "#5f6a75";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(labelY, 10, 20);
  ctx.fillText("nm", width - 38, height - 10);
  return pad;
}

function plotLine(ctx, data, pad, width, height, color = "#253241", lineWidth = 2) {
  const xs = data.map((point) => point.x);
  const ys = data.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xScale = (width - pad.left - pad.right) / (maxX - minX || 1);
  const yScale = (height - pad.top - pad.bottom) / (maxY - minY || 1);

  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  data.forEach((point, index) => {
    const x = pad.left + (point.x - minX) * xScale;
    const y = height - pad.bottom - (point.y - minY) * yScale;
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  return { minX, maxX, minY, maxY, xScale, yScale };
}

function fitLegendLayout(ctx, width, height, plotPad, items) {
  const labelWidth = Math.max(...items.map((item) => ctx.measureText(item.label).width));
  const boxWidth = Math.min(Math.max(116, labelWidth + 36), width < 620 ? 150 : 168);
  const boxHeight = 12 + items.length * 18;
  const side = width >= 720;
  return {
    side,
    x: side ? width - plotPad.right + 18 : Math.max(plotPad.left + 8, width - plotPad.right - boxWidth - 8),
    y: side ? plotPad.top + 6 : plotPad.top + 8,
    width: boxWidth,
    height: boxHeight,
  };
}

function truncateCanvasText(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) {
    return text;
  }
  let next = String(text);
  while (next.length > 4 && ctx.measureText(`${next}...`).width > maxWidth) {
    next = next.slice(0, -1);
  }
  return `${next}...`;
}

function drawFitLegend(ctx, layout, items) {
  ctx.save();
  ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
  ctx.strokeStyle = "#d8dee5";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.rect(layout.x, layout.y, layout.width, layout.height);
  ctx.fill();
  ctx.stroke();
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  items.forEach((item, index) => {
    const y = layout.y + 18 + index * 18;
    ctx.strokeStyle = item.color;
    ctx.fillStyle = item.color;
    ctx.lineWidth = item.dashed ? 1.8 : 2;
    ctx.setLineDash(item.dashed ? [5, 4] : []);
    if (item.marker) {
      ctx.beginPath();
      ctx.arc(layout.x + 12, y - 4, 4, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.moveTo(layout.x + 7, y - 4);
      ctx.lineTo(layout.x + 20, y - 4);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.fillStyle = "#34414d";
    ctx.fillText(item.label, layout.x + 28, y);
  });
  ctx.restore();
}

function fitTickValues(minValue, maxValue, count = 5) {
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
    return [];
  }
  if (minValue === maxValue) {
    return [minValue];
  }
  const ticks = [];
  const steps = Math.max(1, count - 1);
  for (let index = 0; index <= steps; index += 1) {
    ticks.push(minValue + ((maxValue - minValue) * index) / steps);
  }
  return ticks;
}

function formatFitAxisTick(value, span, axis) {
  if (axis === "x") {
    if (Math.abs(span) < 2) {
      return value.toFixed(3);
    }
    if (Math.abs(span) < 20) {
      return value.toFixed(2);
    }
    return value.toFixed(1);
  }
  const absValue = Math.abs(value);
  if (absValue < 1) {
    return Math.abs(span) < 0.1 ? value.toFixed(4) : value.toFixed(3);
  }
  if (absValue < 10) {
    return value.toFixed(2);
  }
  return value.toFixed(0);
}

function drawFitAxisTicks(ctx, pad, width, height, bounds, project) {
  const plotRight = width - pad.right;
  const plotBottom = height - pad.bottom;
  const plotWidth = plotRight - pad.left;
  const xTicks = fitTickValues(bounds.minX, bounds.maxX, width < 620 ? 4 : plotWidth < 760 ? 5 : 6);
  const yTicks = fitTickValues(bounds.minY, bounds.maxY, height < 360 ? 4 : 5);
  ctx.save();
  ctx.font = width < 620 ? "10px system-ui, sans-serif" : "11px system-ui, sans-serif";
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(194, 200, 207, 0.45)";
  ctx.fillStyle = "#5f6a75";

  xTicks.forEach((tick, index) => {
    const pos = project({ x: tick, y: bounds.minY });
    ctx.beginPath();
    ctx.moveTo(pos.x, pad.top);
    ctx.lineTo(pos.x, plotBottom);
    ctx.stroke();
    ctx.strokeStyle = "#aeb7c1";
    ctx.beginPath();
    ctx.moveTo(pos.x, plotBottom);
    ctx.lineTo(pos.x, plotBottom + 4);
    ctx.stroke();
    ctx.strokeStyle = "rgba(194, 200, 207, 0.45)";
    ctx.textAlign = index === 0 ? "left" : index === xTicks.length - 1 ? "right" : "center";
    ctx.textBaseline = "top";
    const labelX = index === 0 ? pos.x + 2 : index === xTicks.length - 1 ? pos.x - 2 : pos.x;
    ctx.fillText(formatFitAxisTick(tick, bounds.maxX - bounds.minX, "x"), labelX, plotBottom + 7);
  });

  yTicks.forEach((tick) => {
    const pos = project({ x: bounds.minX, y: tick });
    ctx.beginPath();
    ctx.moveTo(pad.left, pos.y);
    ctx.lineTo(plotRight, pos.y);
    ctx.stroke();
    ctx.strokeStyle = "#aeb7c1";
    ctx.beginPath();
    ctx.moveTo(pad.left - 4, pos.y);
    ctx.lineTo(pad.left, pos.y);
    ctx.stroke();
    ctx.strokeStyle = "rgba(194, 200, 207, 0.45)";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(formatFitAxisTick(tick, bounds.maxY - bounds.minY, "y"), pad.left - 8, pos.y);
  });
  ctx.restore();
}

function spectrumBounds(spectrum) {
  const xs = spectrum.map((point) => point.x).filter((value) => Number.isFinite(value));
  if (xs.length === 0) {
    return { minX: 200, maxX: 900 };
  }
  return { minX: Math.min(...xs), maxX: Math.max(...xs) };
}

function clampNumber(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function isSpectrumZoomStage(stageId) {
  return SPECTRUM_ZOOM_STAGE_IDS.has(stageId);
}

function defaultChartZoomWidth(stageId, fullSpan = Number.POSITIVE_INFINITY) {
  const desired = CHART_ZOOM_DEFAULT_WIDTHS_NM[stageId] || CHART_ZOOM_DEFAULT_WIDTHS_NM.match;
  if (!Number.isFinite(fullSpan) || fullSpan <= 0) {
    return desired;
  }
  const minWidth = Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan);
  const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
  return clampNumber(desired, minWidth, maxWidth);
}

function createDefaultChartZoom(stageId = "raw") {
  const normalizedStageId = isSpectrumZoomStage(stageId) ? stageId : "raw";
  return {
    enabled: true,
    mode: "lens",
    stageId: normalizedStageId,
    centerNm: null,
    widthNm: defaultChartZoomWidth(normalizedStageId),
    minX: null,
    maxX: null,
    selectedFeatureId: null,
    lens: {
      enabled: true,
      anchor: "auto",
      pinned: false,
      rect: null,
    },
  };
}

function createDefaultMatchZoom() {
  return {
    ...createDefaultChartZoom("match"),
    mode: "manual",
    pinnedLineId: null,
  };
}

function localMaximumFeatures(spectrum, limit = 8) {
  const rows = [];
  for (let index = 1; index < spectrum.length - 1; index += 1) {
    const point = spectrum[index];
    if (point.y >= spectrum[index - 1].y && point.y >= spectrum[index + 1].y) {
      rows.push({
        id: `raw-${index}`,
        kind: "spectrum",
        x: normalizeNumber(point.x),
        y: normalizeNumber(point.y),
        label: `${normalizeNumber(point.x).toFixed(2)} nm`,
        priority: normalizeNumber(point.y),
      });
    }
  }
  if (rows.length === 0 && spectrum.length) {
    const maxPoint = spectrum.slice().sort((left, right) => normalizeNumber(right.y) - normalizeNumber(left.y))[0];
    rows.push({
      id: "raw-max",
      kind: "spectrum",
      x: normalizeNumber(maxPoint.x),
      y: normalizeNumber(maxPoint.y),
      label: `${normalizeNumber(maxPoint.x).toFixed(2)} nm`,
      priority: normalizeNumber(maxPoint.y),
    });
  }
  return rows
    .filter((row) => Number.isFinite(row.x) && Number.isFinite(row.y))
    .sort((left, right) => right.priority - left.priority)
    .slice(0, limit);
}

function spectrumFeaturesForStage(stageId, appState) {
  if (stageId === "peak") {
    return appState.peaks
      .map((peak, index) => ({
        id: `peak-${index}`,
        kind: "peak",
        x: normalizeNumber(peak.x),
        y: normalizeNumber(peak.y),
        label: `Peak ${index + 1}`,
        priority: normalizeNumber(peak.prominence, normalizeNumber(peak.y)),
        peak,
      }))
      .filter((feature) => Number.isFinite(feature.x) && Number.isFinite(feature.y));
  }
  if (stageId === "match") {
    return appState.spectralMatches
      .map((line, index) => ({
        id: `match-${index}`,
        kind: "match",
        x: normalizeNumber(line.wl),
        y: normalizeNumber(line.expInt),
        label: `${line.element} ${normalizeNumber(line.wl).toFixed(1)}`,
        priority: spectralLinePriority(line),
        line,
      }))
      .filter((feature) => Number.isFinite(feature.x));
  }
  return localMaximumFeatures(appState.spectrum, 8);
}

function selectSpectrumAutoWindow(stageId, appState, features, bounds) {
  if (stageId === "match") {
    return selectSpectralMatchWindow(appState.spectrum, appState.spectralMatches);
  }
  const fullSpan = bounds.maxX - bounds.minX || 1;
  const widthNm = defaultChartZoomWidth(stageId, fullSpan);
  const sorted = features
    .filter((feature) => feature.x >= bounds.minX && feature.x <= bounds.maxX)
    .sort((left, right) => right.priority - left.priority);
  const center = sorted.length ? sorted[0].x : bounds.minX + fullSpan / 2;
  const halfWidth = Math.min(fullSpan, widthNm) / 2;
  const minX = clampNumber(center - halfWidth, bounds.minX, bounds.maxX - halfWidth * 2);
  return {
    minX,
    maxX: Math.min(bounds.maxX, minX + halfWidth * 2),
  };
}

function resolveSpectrumChartWindow(stageId, appState, chartZoom = createDefaultChartZoom(stageId)) {
  const normalizedStageId = isSpectrumZoomStage(stageId) ? stageId : "raw";
  const bounds = spectrumBounds(appState.spectrum);
  const fullSpan = bounds.maxX - bounds.minX || 1;
  const features = spectrumFeaturesForStage(normalizedStageId, appState);
  const activeZoom =
    chartZoom && chartZoom.stageId === normalizedStageId
      ? chartZoom
      : {
          ...createDefaultChartZoom(normalizedStageId),
          centerNm: null,
          widthNm: defaultChartZoomWidth(normalizedStageId, fullSpan),
        };
  const explicitMin = finiteNumberOrNull(activeZoom.minX);
  const explicitMax = finiteNumberOrNull(activeZoom.maxX);
  const minWidth = Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan);
  const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
  let widthNm =
    explicitMin !== null && explicitMax !== null && explicitMax > explicitMin
      ? explicitMax - explicitMin
      : normalizeNumber(activeZoom.widthNm, defaultChartZoomWidth(normalizedStageId, fullSpan));
  widthNm = clampNumber(widthNm, minWidth, maxWidth);

  const autoWindow = selectSpectrumAutoWindow(normalizedStageId, appState, features, bounds);
  const selectedFeature =
    features.find((feature) => feature.id === activeZoom.selectedFeatureId) ||
    features
      .filter((feature) => feature.x >= autoWindow.minX && feature.x <= autoWindow.maxX)
      .sort((left, right) => right.priority - left.priority)[0] ||
    null;

  let centerNm = finiteNumberOrNull(activeZoom.centerNm);
  if (centerNm === null) {
    centerNm = selectedFeature ? selectedFeature.x : (autoWindow.minX + autoWindow.maxX) / 2;
  }

  if (widthNm >= fullSpan) {
    centerNm = bounds.minX + fullSpan / 2;
  } else {
    centerNm = clampNumber(centerNm, bounds.minX + widthNm / 2, bounds.maxX - widthNm / 2);
  }

  return {
    minX: centerNm - widthNm / 2,
    maxX: centerNm + widthNm / 2,
    mode: activeZoom.mode || "lens",
    autoWindow,
    bounds,
    features,
    selectedFeature,
    zoomFactor: fullSpan / (widthNm || 1),
  };
}

function selectSpectralMatchWindow(spectrum, matches) {
  const bounds = spectrumBounds(spectrum);
  const fullSpan = bounds.maxX - bounds.minX || 1;
  const wavelengths = matches
    .map((line) => normalizeNumber(line.wl, Number.NaN))
    .filter((value) => Number.isFinite(value) && value >= bounds.minX && value <= bounds.maxX)
    .sort((a, b) => a - b);

  if (wavelengths.length === 0) {
    return bounds;
  }

  const matchedSpan = wavelengths[wavelengths.length - 1] - wavelengths[0];
  if (matchedSpan <= Math.min(240, fullSpan * 0.45)) {
    const pad = Math.max(8, matchedSpan * 0.12);
    return {
      minX: Math.max(bounds.minX, wavelengths[0] - pad),
      maxX: Math.min(bounds.maxX, wavelengths[wavelengths.length - 1] + pad),
    };
  }

  const targetSpan = Math.min(220, Math.max(90, fullSpan * 0.32));
  let best = { start: wavelengths[0], count: 0, center: wavelengths[0] };
  wavelengths.forEach((start) => {
    const end = start + targetSpan;
    const inside = wavelengths.filter((value) => value >= start && value <= end);
    const count = inside.length;
    const center = inside.length ? (inside[0] + inside[inside.length - 1]) / 2 : start + targetSpan / 2;
    const plotCenter = bounds.minX + fullSpan / 2;
    if (count > best.count || (count === best.count && Math.abs(center - plotCenter) < Math.abs(best.center - plotCenter))) {
      best = { start, count, center };
    }
  });

  const minX = Math.max(bounds.minX, best.center - targetSpan / 2);
  const maxX = Math.min(bounds.maxX, best.center + targetSpan / 2);
  return { minX, maxX };
}

function defaultSpectralMatchCenter(matches, windowBounds) {
  const focusMatches = matches
    .filter((line) => line.wl >= windowBounds.minX && line.wl <= windowBounds.maxX)
    .sort((a, b) => spectralLinePriority(b) - spectralLinePriority(a));
  return focusMatches.length ? focusMatches[0].wl : (windowBounds.minX + windowBounds.maxX) / 2;
}

function resolveSpectralMatchWindow(spectrum, matches, matchZoom = createDefaultMatchZoom()) {
  const bounds = spectrumBounds(spectrum);
  const fullSpan = bounds.maxX - bounds.minX || 1;
  const autoWindow = selectSpectralMatchWindow(spectrum, matches);
  const mode = "manual";

  const explicitMin = finiteNumberOrNull(matchZoom.minX);
  const explicitMax = finiteNumberOrNull(matchZoom.maxX);
  let widthNm =
    explicitMin !== null && explicitMax !== null && explicitMax > explicitMin
      ? explicitMax - explicitMin
      : normalizeNumber(matchZoom.widthNm, MATCH_ZOOM_DEFAULT_WIDTH_NM);
  const minWidth = Math.min(MATCH_ZOOM_MIN_WIDTH_NM, fullSpan);
  const maxWidth = Math.max(minWidth, Math.min(MATCH_ZOOM_MAX_WIDTH_NM, fullSpan));
  widthNm = clampNumber(widthNm, minWidth, maxWidth);

  let centerNm = finiteNumberOrNull(matchZoom.centerNm);
  if (centerNm === null) {
    centerNm = defaultSpectralMatchCenter(matches, autoWindow);
  }

  centerNm = clampNumber(centerNm, bounds.minX + widthNm / 2, bounds.maxX - widthNm / 2);
  return {
    minX: centerNm - widthNm / 2,
    maxX: centerNm + widthNm / 2,
    mode,
    autoWindow,
    bounds,
    zoomFactor: fullSpan / (widthNm || 1),
  };
}

function spectralZoomEmphasis(bounds, windowBounds) {
  const fullSpan = Math.max(1, normalizeNumber(bounds.maxX) - normalizeNumber(bounds.minX));
  const visibleSpan = Math.max(0.001, normalizeNumber(windowBounds.maxX) - normalizeNumber(windowBounds.minX));
  const zoomFactor = Math.max(1, fullSpan / visibleSpan);
  const logBoost = Math.log2(zoomFactor);
  return {
    zoomFactor,
    lineWidthMultiplier: Math.min(3.2, 1 + logBoost * 0.38),
    pointRadiusMultiplier: Math.min(2.6, 1 + logBoost * 0.28),
    labelFontSize: Math.round(Math.min(15, 10 + logBoost * 0.9)),
    labelRowHeight: Math.round(Math.min(20, 15 + logBoost * 0.7)),
  };
}

function spectrumZoomEmphasis(bounds, windowBounds) {
  return spectralZoomEmphasis(bounds, windowBounds);
}

function rectOverlapArea(left, right) {
  const x1 = Math.max(left.x, right.x);
  const y1 = Math.max(left.y, right.y);
  const x2 = Math.min(left.x + left.width, right.x + right.width);
  const y2 = Math.min(left.y + left.height, right.y + right.height);
  return Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
}

function baseSpectrumInsetSize(width, height, pad) {
  const availableWidth = Math.max(120, width - pad.left - pad.right - 20);
  const availableHeight = Math.max(110, height - pad.top - pad.bottom - 18);
  const compact = width < 620;
  const insetWidth = Math.min(availableWidth, Math.max(compact ? 238 : 300, width * (compact ? 0.68 : 0.58)));
  const insetHeight = Math.min(availableHeight, Math.max(compact ? 176 : 210, height * (height < 420 ? 0.6 : 0.56)));
  return { insetWidth, insetHeight, compact };
}

function spectrumInsetLayout(width, height, pad, hazards = []) {
  const { insetWidth, insetHeight } = baseSpectrumInsetSize(width, height, pad);
  const left = pad.left + 10;
  const right = width - pad.right - insetWidth;
  const top = pad.top + 10;
  const bottom = height - pad.bottom - insetHeight - 10;
  const candidates = [
    { x: right, y: top, preference: 0 },
    { x: left, y: top, preference: 10 },
    { x: right, y: bottom, preference: 14 },
    { x: left, y: bottom, preference: 18 },
  ].map((candidate) => ({
    ...candidate,
    x: clampNumber(candidate.x, pad.left + 4, width - pad.right - insetWidth),
    y: clampNumber(candidate.y, pad.top + 4, height - pad.bottom - insetHeight),
    width: insetWidth,
    height: insetHeight,
  }));
  const scored = candidates
    .map((candidate) => {
      const collisionScore = (Array.isArray(hazards) ? hazards : []).reduce((score, hazard) => {
        const area = rectOverlapArea(candidate, hazard);
        return score + area * normalizeNumber(hazard.weight, 1);
      }, 0);
      return {
        ...candidate,
        score: collisionScore + candidate.preference,
      };
    })
    .sort((a, b) => a.score - b.score);
  const best = scored[0] || candidates[0];
  return {
    x: best.x,
    y: best.y,
    width: insetWidth,
    height: insetHeight,
    pad: {
      left: width < 620 ? 30 : 36,
      right: 10,
      top: width < 620 ? 44 : 52,
      bottom: width < 620 ? 28 : 32,
    },
  };
}

function spectralInsetLayout(width, height, pad) {
  return spectrumInsetLayout(width, height, pad, []);
}

function compressSpectralIntensity(value) {
  const number = Math.max(0, normalizeNumber(value));
  return Math.sqrt(number);
}

function spectralIntensityReference(spectrum) {
  const values = spectrum
    .map((point) => normalizeNumber(point.y))
    .filter((value) => value > 0)
    .sort((left, right) => left - right);
  if (values.length === 0) {
    return 1;
  }
  const index = Math.min(values.length - 1, Math.max(0, Math.floor((values.length - 1) * 0.985)));
  return Math.max(0.05, values[index]);
}

function createSpectralOverviewTransform(spectrum) {
  const reference = spectralIntensityReference(spectrum);
  return (value) => compressSpectralIntensity(clampNumber(normalizeNumber(value) / reference, 0, 1));
}

function spectrumWindowPoints(spectrum, minX, maxX) {
  const inside = spectrum.filter((point) => point.x >= minX && point.x <= maxX);
  if (inside.length >= 2) {
    return inside;
  }
  return spectrum;
}

function plotLineInWindow(ctx, data, pad, width, height, windowBounds, color = "#253241", lineWidth = 2, options = {}) {
  const yTransform = typeof options.yTransform === "function" ? options.yTransform : (value) => value;
  const rows = spectrumWindowPoints(data, windowBounds.minX, windowBounds.maxX).map((point) => ({
    ...point,
    y: yTransform(point.y),
  }));
  const ys = rows.map((point) => point.y);
  const minX = windowBounds.minX;
  const maxX = windowBounds.maxX;
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xScale = (width - pad.left - pad.right) / (maxX - minX || 1);
  const yScale = (height - pad.top - pad.bottom) / (maxY - minY || 1);

  ctx.save();
  ctx.beginPath();
  ctx.rect(pad.left, pad.top, width - pad.left - pad.right, height - pad.top - pad.bottom);
  ctx.clip();
  if (options.fillColor && rows.length) {
    ctx.fillStyle = options.fillColor;
    ctx.globalAlpha = options.fillAlpha === undefined ? 0.12 : options.fillAlpha;
    ctx.beginPath();
    rows.forEach((point, index) => {
      const x = pad.left + (point.x - minX) * xScale;
      const y = height - pad.bottom - (point.y - minY) * yScale;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    const lastPoint = rows[rows.length - 1];
    const firstPoint = rows[0];
    ctx.lineTo(pad.left + (lastPoint.x - minX) * xScale, height - pad.bottom);
    ctx.lineTo(pad.left + (firstPoint.x - minX) * xScale, height - pad.bottom);
    ctx.closePath();
    ctx.fill();
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.globalAlpha = options.alpha === undefined ? 1 : options.alpha;
  ctx.beginPath();
  rows.forEach((point, index) => {
    const x = pad.left + (point.x - minX) * xScale;
    const y = height - pad.bottom - (point.y - minY) * yScale;
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx.restore();

  return { minX, maxX, minY, maxY, xScale, yScale };
}

function niceTickStep(rawStep) {
  const exponent = Math.floor(Math.log10(Math.max(0.0001, rawStep)));
  const base = Math.pow(10, exponent);
  const fraction = rawStep / base;
  if (fraction <= 1) {
    return base;
  }
  if (fraction <= 2) {
    return 2 * base;
  }
  if (fraction <= 5) {
    return 5 * base;
  }
  return 10 * base;
}

function tickDecimals(step) {
  if (step >= 10) {
    return 0;
  }
  if (step >= 1) {
    return 1;
  }
  if (step >= 0.1) {
    return 2;
  }
  return 3;
}

function drawSpectralXAxis(ctx, plot, scale, options = {}) {
  const span = scale.maxX - scale.minX || 1;
  const targetTicks = options.targetTicks || Math.max(3, Math.min(8, Math.floor((plot.right - plot.left) / 86)));
  const step = niceTickStep(span / targetTicks);
  const first = Math.ceil(scale.minX / step) * step;
  const decimals = tickDecimals(step);
  const ticks = [];

  ctx.save();
  ctx.strokeStyle = options.color || "#9faab5";
  ctx.fillStyle = options.textColor || "#4f5b67";
  ctx.lineWidth = options.lineWidth || 1;
  ctx.font = options.font || "11px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let value = first; value <= scale.maxX + step * 0.25; value += step) {
    if (value < scale.minX - step * 0.25) {
      continue;
    }
    const x = plot.left + (value - scale.minX) * scale.xScale;
    if (x < plot.left - 0.5 || x > plot.right + 0.5) {
      continue;
    }
    ticks.push(value);
    ctx.beginPath();
    ctx.moveTo(x, plot.bottom);
    ctx.lineTo(x, plot.bottom + (options.tickLength || 5));
    ctx.stroke();
    ctx.fillText(value.toFixed(decimals), x, plot.bottom + (options.labelOffset || 8));
  }
  ctx.textAlign = "right";
  ctx.fillText("nm", plot.right, plot.bottom + (options.unitOffset || 24));
  ctx.restore();

  return ticks;
}

function spectralLineStyle(line, emphasis = null) {
  const lineMultiplier = emphasis && emphasis.lineWidthMultiplier ? emphasis.lineWidthMultiplier : 1;
  const pointMultiplier = emphasis && emphasis.pointRadiusMultiplier ? emphasis.pointRadiusMultiplier : 1;
  if (line.status === "blocked") {
    return { color: "#d43d51", dash: [6, 4], width: 1.35 * lineMultiplier, pointRadius: 3.1 * pointMultiplier, alpha: 0.82, label: "基体重叠" };
  }
  if (line.status === "review") {
    return { color: "#d99000", dash: [2, 3], width: 1.3 * lineMultiplier, pointRadius: 3.4 * pointMultiplier, alpha: 0.86, label: "低置信" };
  }
  return { color: "#006bb6", dash: [], width: 1.7 * lineMultiplier, pointRadius: 4.1 * pointMultiplier, alpha: 0.9, label: "稀土匹配" };
}

function spectralLinePriority(line) {
  const statusScore = line.status === "enabled" ? 3 : line.status === "review" ? 2 : 1;
  const intensityScore = normalizeNumber(line.expInt);
  const deltaScore = Math.max(0, 0.2 - Math.abs(normalizeNumber(line.deltaNm)));
  return statusScore * 10 + intensityScore * 3 + deltaScore;
}

function chooseVisibleSpectralLabels(matches, width) {
  const maxLabels = width < 620 ? 7 : width < 920 ? 9 : 12;
  return matches
    .slice()
    .sort((a, b) => spectralLinePriority(b) - spectralLinePriority(a))
    .slice(0, maxLabels)
    .sort((a, b) => a.wl - b.wl);
}

function selectHighlightedSpectralMatches(matches, width) {
  const maxHighlights = width < 620 ? 3 : width < 920 ? 4 : 5;
  return matches
    .slice()
    .sort((a, b) => spectralLinePriority(b) - spectralLinePriority(a))
    .slice(0, maxHighlights)
    .sort((a, b) => a.wl - b.wl);
}

function layoutSpectralLabels(matches, scale, pad, width, options = {}) {
  const rows = options.rows || 4;
  const lastRightByRow = Array.from({ length: rows }, () => -Infinity);
  const minGap = options.minGap || 8;
  const labelTop = options.labelTop === undefined ? 18 : options.labelTop;
  const rowHeight = options.rowHeight || 16;
  const leftBound = options.leftBound || pad.left;
  const rightBound = options.rightBound || width - 24;
  return matches
    .map((line) => {
      const x = pad.left + (line.wl - scale.minX) * scale.xScale;
      const text = `${line.element} ${line.wl.toFixed(1)}`;
      const boxWidth = Math.max(46, Math.min(112, text.length * 6.2 + 14));
      const labelX = Math.max(leftBound + boxWidth / 2, Math.min(rightBound - boxWidth / 2, x));
      let row = -1;
      for (let index = 0; index < rows; index += 1) {
        if (labelX - boxWidth / 2 > lastRightByRow[index] + minGap) {
          row = index;
          break;
        }
      }
      if (row < 0) {
        return null;
      }
      lastRightByRow[row] = labelX + boxWidth / 2;
      return {
        line,
        x,
        labelX,
        labelY: labelTop + row * rowHeight,
        row,
        text,
        boxWidth,
      };
    })
    .filter(Boolean);
}

function spectralEvidenceLane(line) {
  if (line.status === "blocked") {
    return 1;
  }
  if (line.status === "review") {
    return 2;
  }
  return 0;
}

function drawSpectralEvidenceTicks(ctx, matches, scale, plot, options = {}) {
  const highlighted = options.highlighted || new Set();
  const compact = Boolean(options.compact);
  const baseY = plot.bottom - (options.bottomOffset || (compact ? 5 : 6));
  const laneStep = options.laneStep || (compact ? 4 : 5);
  const tickHeight = options.tickHeight || (compact ? 13 : 18);
  const tickWidth = options.tickWidth || (compact ? 1.15 : 1.35);
  const pointRadius = options.pointRadius || (compact ? 1.8 : 2.1);

  ctx.save();
  ctx.lineCap = "round";
  matches.forEach((line) => {
    if (options.hideHighlighted && highlighted.has(line)) {
      return;
    }
    const x = plot.left + (line.wl - scale.minX) * scale.xScale;
    if (x < plot.left || x > plot.right) {
      return;
    }
    const style = spectralLineStyle(line);
    const lane = spectralEvidenceLane(line);
    const y2 = baseY - lane * laneStep;
    const isHighlighted = highlighted.has(line);
    const y1 = Math.max(plot.top + 2, y2 - tickHeight - (isHighlighted ? 3 : 0));
    ctx.globalAlpha = isHighlighted ? options.highlightAlpha || 0.72 : options.alpha || 0.36;
    ctx.strokeStyle = style.color;
    ctx.fillStyle = style.color;
    ctx.lineWidth = isHighlighted ? tickWidth + 0.6 : tickWidth;
    ctx.setLineDash(line.status === "review" ? [1, 3] : []);
    ctx.beginPath();
    ctx.moveTo(x, y1);
    ctx.lineTo(x, y2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(x, y2, isHighlighted ? pointRadius + 0.5 : pointRadius, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function drawSpectralLegend(ctx, x, y, width) {
  const items = [
    { status: "enabled" },
    { status: "blocked" },
    { status: "review" },
  ].map((line) => spectralLineStyle(line));
  const compact = width < 620;
  const itemWidth = compact ? 82 : 104;
  const boxWidth = compact ? itemWidth : itemWidth * items.length + 14;
  const boxHeight = compact ? 62 : 28;

  ctx.save();
  ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
  ctx.strokeStyle = "rgba(159, 170, 181, 0.8)";
  ctx.lineWidth = 1;
  ctx.fillRect(x, y - boxHeight + 6, boxWidth, boxHeight);
  ctx.strokeRect(x, y - boxHeight + 6, boxWidth, boxHeight);
  items.forEach((style, index) => {
    const itemX = compact ? x + 8 : x + 8 + index * itemWidth;
    const itemY = compact ? y - boxHeight + 18 + index * 18 : y - 12;
    ctx.setLineDash(style.dash);
    ctx.strokeStyle = style.color;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(itemX, itemY);
    ctx.lineTo(itemX + 24, itemY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = style.color;
    ctx.beginPath();
    ctx.arc(itemX + 12, itemY, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#34414d";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(style.label, itemX + 31, itemY);
  });
  ctx.restore();
  return { width: boxWidth, height: boxHeight };
}

function spectrumScaleForPlot(spectrum, plot, windowBounds, options = {}) {
  const yTransform = typeof options.yTransform === "function" ? options.yTransform : (value) => normalizeNumber(value);
  const rows = spectrumWindowPoints(spectrum, windowBounds.minX, windowBounds.maxX)
    .map((point) => ({
      x: normalizeNumber(point.x),
      y: yTransform(point.y),
      rawY: normalizeNumber(point.y),
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const extraY = (options.extraY || [])
    .map((value) => (typeof value === "number" ? yTransform(value) : yTransform(value && value.y)))
    .filter((value) => Number.isFinite(value));
  let minY = Math.min(...rows.map((point) => point.y), ...extraY);
  let maxY = Math.max(...rows.map((point) => point.y), ...extraY);
  if (!Number.isFinite(minY) || !Number.isFinite(maxY) || minY === maxY) {
    minY = 0;
    maxY = 1;
  }
  if (options.includeZero !== false) {
    minY = Math.min(0, minY);
  }
  const yPad = (maxY - minY || 1) * (options.yPadding === undefined ? 0.08 : options.yPadding);
  minY -= yPad;
  maxY += yPad;
  return {
    minX: windowBounds.minX,
    maxX: windowBounds.maxX,
    minY,
    maxY,
    xScale: (plot.right - plot.left) / (windowBounds.maxX - windowBounds.minX || 1),
    yScale: (plot.bottom - plot.top) / (maxY - minY || 1),
    rows,
    yTransform,
  };
}

function projectSpectrumValue(x, y, scale, plot, yTransform = scale.yTransform || ((value) => value)) {
  return {
    x: plot.left + (x - scale.minX) * scale.xScale,
    y: plot.bottom - (yTransform(y) - scale.minY) * scale.yScale,
  };
}

function drawSpectrumLine(ctx, rows, plot, scale, color = "#253241", lineWidth = 2, options = {}) {
  if (!rows || rows.length < 2) {
    return;
  }
  ctx.save();
  ctx.beginPath();
  ctx.rect(plot.left, plot.top, plot.right - plot.left, plot.bottom - plot.top);
  ctx.clip();
  if (options.fillColor) {
    ctx.fillStyle = options.fillColor;
    ctx.globalAlpha = options.fillAlpha === undefined ? 0.1 : options.fillAlpha;
    ctx.beginPath();
    rows.forEach((point, index) => {
      const pos = projectSpectrumValue(point.x, point.y, scale, plot, (value) => value);
      if (index === 0) {
        ctx.moveTo(pos.x, pos.y);
      } else {
        ctx.lineTo(pos.x, pos.y);
      }
    });
    const lastPoint = rows.at(-1);
    const firstPoint = rows[0];
    ctx.lineTo(plot.left + (lastPoint.x - scale.minX) * scale.xScale, plot.bottom);
    ctx.lineTo(plot.left + (firstPoint.x - scale.minX) * scale.xScale, plot.bottom);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.globalAlpha = options.alpha === undefined ? 1 : options.alpha;
  ctx.setLineDash(options.dash || []);
  ctx.beginPath();
  rows.forEach((point, index) => {
    const pos = projectSpectrumValue(point.x, point.y, scale, plot, (value) => value);
    if (index === 0) {
      ctx.moveTo(pos.x, pos.y);
    } else {
      ctx.lineTo(pos.x, pos.y);
    }
  });
  ctx.stroke();
  ctx.restore();
}

function tickValues(minValue, maxValue, targetTicks) {
  const span = maxValue - minValue || 1;
  const step = niceTickStep(span / Math.max(1, targetTicks));
  const first = Math.ceil(minValue / step) * step;
  const ticks = [];
  for (let value = first; value <= maxValue + step * 0.25; value += step) {
    if (value >= minValue - step * 0.25) {
      ticks.push(value);
    }
  }
  return { ticks, step };
}

function drawSpectrumAxes(ctx, plot, scale, options = {}) {
  const compact = Boolean(options.compact);
  const xTickData = tickValues(scale.minX, scale.maxX, options.targetXTicks || (compact ? 4 : 7));
  const yTickData = tickValues(scale.minY, scale.maxY, options.targetYTicks || (compact ? 3 : 5));
  const xDecimals = tickDecimals(xTickData.step);
  const yDecimals = tickDecimals(yTickData.step);

  ctx.save();
  ctx.strokeStyle = options.gridColor || "#e1e5ea";
  ctx.fillStyle = options.textColor || "#4f5b67";
  ctx.lineWidth = 1;
  ctx.font = options.font || (compact ? "10px system-ui, sans-serif" : "11px system-ui, sans-serif");
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  xTickData.ticks.forEach((value) => {
    const x = plot.left + (value - scale.minX) * scale.xScale;
    if (x < plot.left - 0.5 || x > plot.right + 0.5) {
      return;
    }
    ctx.beginPath();
    ctx.moveTo(x, plot.top);
    ctx.lineTo(x, plot.bottom + 5);
    ctx.stroke();
    ctx.fillText(value.toFixed(xDecimals), x, plot.bottom + 8);
  });
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  yTickData.ticks.forEach((value) => {
    const y = plot.bottom - (value - scale.minY) * scale.yScale;
    if (y < plot.top - 0.5 || y > plot.bottom + 0.5) {
      return;
    }
    ctx.beginPath();
    ctx.moveTo(plot.left - 5, y);
    ctx.lineTo(plot.right, y);
    ctx.stroke();
    ctx.fillText(value.toFixed(yDecimals), plot.left - 8, y);
  });
  ctx.strokeStyle = options.axisColor || "#9faab5";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(plot.left, plot.top);
  ctx.lineTo(plot.left, plot.bottom);
  ctx.lineTo(plot.right, plot.bottom);
  ctx.stroke();
  if (options.xLabel !== "") {
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#34414d";
    ctx.font = compact ? "11px system-ui, sans-serif" : "12px system-ui, sans-serif";
    ctx.fillText(options.xLabel || "Wavelength (nm)", (plot.left + plot.right) / 2, plot.bottom + (compact ? 36 : 40));
  }
  if (options.yLabel !== "") {
    if (typeof ctx.translate === "function" && typeof ctx.rotate === "function") {
      ctx.save();
      ctx.translate(plot.left - (compact ? 42 : 50), (plot.top + plot.bottom) / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#34414d";
      ctx.font = compact ? "11px system-ui, sans-serif" : "12px system-ui, sans-serif";
      ctx.fillText(options.yLabel || "Intensity", 0, 0);
      ctx.restore();
    } else {
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(options.yLabel || "Intensity", plot.left - (compact ? 42 : 50), plot.top - 8);
    }
  }
  ctx.restore();
  return { xTicks: xTickData.ticks, yTicks: yTickData.ticks };
}

function nearestSpectrumPoint(spectrum, wavelength) {
  if (!spectrum.length) {
    return null;
  }
  return spectrum.reduce((best, point) => {
    if (!best) {
      return point;
    }
    return Math.abs(point.x - wavelength) < Math.abs(best.x - wavelength) ? point : best;
  }, null);
}

function spectrumCoordinateText(stageId, appState, wavelength) {
  const point = nearestSpectrumPoint(appState.spectrum, wavelength);
  const intensity = point ? normalizeNumber(point.y) : 0;
  const prefix = stageId === "match" ? "RI" : "I";
  return `${wavelength.toFixed(2)} nm · ${prefix} ${intensity.toFixed(3)}`;
}

function drawSpectrumCoordinateReadout(ctx, plot, stageId, appState, windowBounds) {
  const cursor =
    appState.chartCursor && appState.chartCursor.stageId === stageId
      ? appState.chartCursor
      : { wavelength: (windowBounds.minX + windowBounds.maxX) / 2 };
  const label = `${cursor.active ? "坐标" : "中心"} ${spectrumCoordinateText(stageId, appState, cursor.wavelength)}`;
  ctx.save();
  ctx.font = "11px system-ui, sans-serif";
  const boxWidth = Math.min(plot.right - plot.left - 12, ctx.measureText(label).width + 18);
  const x = plot.right - boxWidth - 4;
  const y = Math.max(6, plot.top - 27);
  ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
  ctx.strokeStyle = "#d1d8df";
  ctx.lineWidth = 1;
  ctx.fillRect(x, y, boxWidth, 21);
  ctx.strokeRect(x, y, boxWidth, 21);
  ctx.fillStyle = "#34414d";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(truncateCanvasText(ctx, label, boxWidth - 12), x + boxWidth / 2, y + 10.5);
  ctx.restore();
}

function spectrumInsetHazards(stageId, appState, scale, plot) {
  const features = spectrumFeaturesForStage(stageId, appState)
    .slice()
    .sort((left, right) => right.priority - left.priority)
    .slice(0, stageId === "raw" ? 5 : 10);
  return features
    .map((feature) => {
      const pos = projectSpectrumValue(feature.x, feature.y, scale, plot);
      if (pos.x < plot.left || pos.x > plot.right || pos.y < plot.top || pos.y > plot.bottom) {
        return null;
      }
      const width = stageId === "match" ? 94 : 78;
      const height = stageId === "match" ? 58 : 48;
      return {
        x: pos.x - width / 2,
        y: pos.y - height / 2,
        width,
        height,
        weight: 1 + Math.max(0, feature.priority) * (stageId === "match" ? 0.45 : 3.5),
      };
    })
    .filter(Boolean);
}

function drawSpectrumFocusOverlay(ctx, plot, scale, windowBounds, inset) {
  const focusLeft = clampNumber(plot.left + (windowBounds.minX - scale.minX) * scale.xScale, plot.left, plot.right);
  const focusRight = clampNumber(plot.left + (windowBounds.maxX - scale.minX) * scale.xScale, plot.left, plot.right);
  const focusWidth = Math.max(5, focusRight - focusLeft);
  const focusX = focusWidth <= 5 ? clampNumber((focusLeft + focusRight) / 2 - 2.5, plot.left, plot.right - 5) : focusLeft;
  const insetAttachX = inset.x < (plot.left + plot.right) / 2 ? inset.x + inset.width : inset.x;

  ctx.save();
  ctx.fillStyle = "rgba(0, 107, 182, 0.07)";
  ctx.strokeStyle = "rgba(0, 107, 182, 0.78)";
  ctx.lineWidth = 1.4;
  ctx.setLineDash([5, 4]);
  ctx.fillRect(focusX, plot.top, focusWidth, plot.bottom - plot.top);
  ctx.strokeRect(focusX, plot.top, focusWidth, plot.bottom - plot.top);
  ctx.setLineDash([4, 4]);
  ctx.globalAlpha = 0.64;
  ctx.beginPath();
  ctx.moveTo(focusX + (insetAttachX <= inset.x ? 0 : focusWidth), plot.top);
  ctx.lineTo(insetAttachX, inset.y + inset.height);
  ctx.moveTo(focusX + (insetAttachX <= inset.x ? 0 : focusWidth), plot.bottom);
  ctx.lineTo(insetAttachX, inset.y);
  ctx.stroke();
  ctx.restore();
}

function visibleSpectrumFeatures(stageId, appState, windowBounds, limit) {
  return spectrumFeaturesForStage(stageId, appState)
    .filter((feature) => feature.x >= windowBounds.minX && feature.x <= windowBounds.maxX)
    .sort((left, right) => right.priority - left.priority)
    .slice(0, limit);
}

function layoutSpectrumFeatureLabels(features, scale, plot, inset, emphasis, options = {}) {
  const rows = options.rows || 3;
  const lastRightByRow = Array.from({ length: rows }, () => -Infinity);
  const minGap = options.minGap || 6;
  const rowHeight = emphasis.labelRowHeight || 16;
  const labelTop = options.labelTop || inset.y + 20;
  const leftBound = inset.x + 6;
  const rightBound = inset.x + inset.width - 6;
  return features
    .map((feature) => {
      const pos = projectSpectrumValue(feature.x, feature.y, scale, plot);
      const text = feature.kind === "peak" ? `${feature.label} ${feature.x.toFixed(2)}` : feature.label;
      const boxWidth = Math.max(54, Math.min(128, text.length * 6.2 + 16));
      const labelX = clampNumber(pos.x, leftBound + boxWidth / 2, rightBound - boxWidth / 2);
      let row = -1;
      for (let index = 0; index < rows; index += 1) {
        if (labelX - boxWidth / 2 > lastRightByRow[index] + minGap) {
          row = index;
          break;
        }
      }
      if (row < 0) {
        return null;
      }
      lastRightByRow[row] = labelX + boxWidth / 2;
      return {
        feature,
        markerX: pos.x,
        markerY: pos.y,
        labelX,
        labelY: labelTop + row * rowHeight,
        boxWidth,
        text,
      };
    })
    .filter(Boolean);
}

function drawSpectrumFeatureLabels(ctx, labels, color, emphasis) {
  ctx.save();
  labels.forEach((label) => {
    const labelHeight = emphasis.labelFontSize + 6;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    ctx.moveTo(label.markerX, label.markerY);
    ctx.lineTo(label.labelX, label.labelY + labelHeight);
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
    ctx.fillRect(label.labelX - label.boxWidth / 2, label.labelY, label.boxWidth, labelHeight);
    ctx.strokeRect(label.labelX - label.boxWidth / 2, label.labelY, label.boxWidth, labelHeight);
    ctx.fillStyle = "#24313e";
    ctx.font = `${emphasis.labelFontSize}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(label.text, label.labelX, label.labelY + emphasis.labelFontSize + 1);
  });
  ctx.restore();
}

function drawSpectrumOverviewFeatures(ctx, stageId, appState, scale, plot, width) {
  if (stageId === "match") {
    const allMatches = appState.spectralMatches.filter((line) => line.wl >= scale.minX && line.wl <= scale.maxX);
    drawSpectralEvidenceTicks(ctx, allMatches, scale, plot, {
      compact: width < 620,
      alpha: 0.4,
      tickHeight: width < 620 ? 14 : 20,
      tickWidth: width < 620 ? 1.1 : 1.25,
    });
    return;
  }

  const features = visibleSpectrumFeatures(stageId, appState, { minX: scale.minX, maxX: scale.maxX }, stageId === "raw" ? 3 : 40);
  ctx.save();
  features.forEach((feature, index) => {
    const pos = projectSpectrumValue(feature.x, feature.y, scale, plot);
    const isPrimary = index === 0;
    ctx.strokeStyle = stageId === "peak" ? "rgba(0, 95, 142, 0.45)" : "rgba(83, 96, 109, 0.4)";
    ctx.fillStyle = stageId === "peak" ? "#005f8e" : "#53606d";
    ctx.lineWidth = isPrimary ? 1.4 : 1;
    if (stageId === "peak") {
      ctx.beginPath();
      ctx.moveTo(pos.x, Math.max(plot.top, pos.y - 14));
      ctx.lineTo(pos.x, plot.bottom);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, isPrimary ? 3.8 : 2.7, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function drawSpectrumInset(ctx, stageId, appState, inset, windowBounds, emphasis, width) {
  ctx.save();
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "#6f7a85";
  ctx.lineWidth = 1.2;
  ctx.fillRect(inset.x, inset.y, inset.width, inset.height);
  ctx.strokeRect(inset.x, inset.y, inset.width, inset.height);
  ctx.fillStyle = "#263542";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillText("局部放大", inset.x + 8, inset.y + 13);
  if (inset.width >= 230) {
    ctx.fillStyle = "#5f6a75";
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${windowBounds.minX.toFixed(2)}-${windowBounds.maxX.toFixed(2)} nm`, inset.x + inset.width - 8, inset.y + 13);
  }

  const insetPlot = {
    left: inset.x + inset.pad.left,
    top: inset.y + inset.pad.top,
    right: inset.x + inset.width - inset.pad.right,
    bottom: inset.y + inset.height - inset.pad.bottom,
  };
  const windowMatches = appState.spectralMatches.filter((line) => line.wl >= windowBounds.minX && line.wl <= windowBounds.maxX);
  const windowFeatures = visibleSpectrumFeatures(stageId, appState, windowBounds, stageId === "raw" ? 1 : width < 620 ? 4 : 7);
  const insetScale = spectrumScaleForPlot(appState.spectrum, insetPlot, windowBounds, {
    extraY: stageId === "match" ? windowMatches.map((line) => line.expInt) : windowFeatures.map((feature) => feature.y),
    includeZero: true,
    yPadding: 0.1,
  });
  drawSpectrumAxes(ctx, insetPlot, insetScale, {
    compact: width < 620,
    targetXTicks: width < 620 ? 3 : 5,
    targetYTicks: 3,
    xLabel: "",
    yLabel: "",
    font: width < 620 ? "9px system-ui, sans-serif" : "10px system-ui, sans-serif",
  });

  drawSpectrumLine(ctx, insetScale.rows, insetPlot, insetScale, "#253241", 1.45 * emphasis.lineWidthMultiplier);

  if (stageId === "match") {
    const highlightedMatches = selectHighlightedSpectralMatches(windowMatches, inset.width);
    const highlightedSet = new Set(highlightedMatches);
    drawSpectralEvidenceTicks(ctx, windowMatches, insetScale, insetPlot, {
      compact: width < 620,
      highlighted: highlightedSet,
      hideHighlighted: true,
      alpha: 0.3,
      tickHeight: width < 620 ? 15 : 19,
      tickWidth: width < 620 ? 1 : 1.15,
      bottomOffset: width < 620 ? 5 : 7,
    });
    highlightedMatches.forEach((line) => {
      const x = insetPlot.left + (line.wl - insetScale.minX) * insetScale.xScale;
      if (x < insetPlot.left || x > insetPlot.right) {
        return;
      }
      const style = spectralLineStyle(line, emphasis);
      ctx.save();
      ctx.globalAlpha = style.alpha;
      ctx.setLineDash(style.dash);
      ctx.strokeStyle = style.color;
      ctx.lineWidth = style.width;
      ctx.beginPath();
      ctx.moveTo(x, insetPlot.top);
      ctx.lineTo(x, insetPlot.bottom);
      ctx.stroke();
      ctx.restore();

      const expY = clampNumber(insetPlot.bottom - (line.expInt - insetScale.minY) * insetScale.yScale, insetPlot.top + 5, insetPlot.bottom - 5);
      ctx.fillStyle = style.color;
      ctx.beginPath();
      ctx.arc(x, expY, style.pointRadius, 0, Math.PI * 2);
      ctx.fill();
    });
    const labelLayout = layoutSpectralLabels(
      highlightedMatches,
      insetScale,
      { left: insetPlot.left, top: insetPlot.top },
      inset.x + inset.width,
      {
        rows: width < 620 ? 2 : 3,
        labelTop: inset.y + 20,
        rowHeight: emphasis.labelRowHeight,
        leftBound: inset.x + 6,
        rightBound: inset.x + inset.width - 6,
        minGap: 4,
      },
    );
    labelLayout.forEach((label) => {
      const style = spectralLineStyle(label.line, emphasis);
      const labelHeight = emphasis.labelFontSize + 6;
      ctx.strokeStyle = style.color;
      ctx.lineWidth = Math.max(1, style.width * 0.45);
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(label.x, insetPlot.top);
      ctx.lineTo(label.labelX, label.labelY + labelHeight);
      ctx.stroke();
      ctx.fillStyle = "rgba(255, 255, 255, 0.94)";
      ctx.fillRect(label.labelX - label.boxWidth / 2, label.labelY, label.boxWidth, labelHeight);
      ctx.strokeStyle = style.color;
      ctx.strokeRect(label.labelX - label.boxWidth / 2, label.labelY, label.boxWidth, labelHeight);
      ctx.fillStyle = "#24313e";
      ctx.font = `${emphasis.labelFontSize}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(label.text, label.labelX, label.labelY + emphasis.labelFontSize + 1);
    });
    ctx.restore();
    return;
  }

  const markerColor = stageId === "peak" ? "#005f8e" : "#53606d";
  ctx.save();
  windowFeatures.forEach((feature, index) => {
    const pos = projectSpectrumValue(feature.x, feature.y, insetScale, insetPlot);
    const radius = (stageId === "peak" ? 3.7 : 4.2) * emphasis.pointRadiusMultiplier;
    ctx.strokeStyle = markerColor;
    ctx.fillStyle = markerColor;
    ctx.lineWidth = Math.max(1.2, 1.2 * emphasis.lineWidthMultiplier);
    if (stageId === "peak" || index === 0) {
      ctx.beginPath();
      ctx.moveTo(pos.x, Math.max(insetPlot.top, pos.y - 18 * emphasis.pointRadiusMultiplier));
      ctx.lineTo(pos.x, insetPlot.bottom);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();

  const labels = layoutSpectrumFeatureLabels(windowFeatures, insetScale, insetPlot, inset, emphasis, {
    rows: width < 620 ? 2 : 3,
    labelTop: inset.y + 20,
  });
  drawSpectrumFeatureLabels(ctx, labels, markerColor, emphasis);
  ctx.restore();
}

function drawSpectrumChart(canvas, appState, stageId) {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  const compact = width < 620;
  const pad = {
    left: compact ? 54 : 64,
    right: compact ? 24 : 28,
    top: compact ? 38 : 36,
    bottom: compact ? 58 : 64,
  };
  const plot = {
    left: pad.left,
    top: pad.top,
    right: width - pad.right,
    bottom: height - pad.bottom,
  };
  const zoom =
    appState.chartZoom && appState.chartZoom.stageId === stageId
      ? appState.chartZoom
      : stageId === "match" && appState.matchZoom
        ? appState.matchZoom
        : createDefaultChartZoom(stageId);
  const windowBounds = resolveSpectrumChartWindow(stageId, appState, zoom);
  const yTransform = stageId === "match" ? createSpectralOverviewTransform(appState.spectrum) : (value) => normalizeNumber(value);
  const overviewScale = spectrumScaleForPlot(appState.spectrum, plot, windowBounds.bounds, {
    yTransform,
    includeZero: true,
    yPadding: stageId === "match" ? 0.05 : 0.08,
  });
  const hazards = spectrumInsetHazards(stageId, appState, overviewScale, plot);
  const inset = spectrumInsetLayout(width, height, pad, hazards);
  const emphasis = spectrumZoomEmphasis(windowBounds.bounds, windowBounds);
  if (appState.chartZoom && appState.chartZoom.stageId === stageId && appState.chartZoom.lens) {
    appState.chartZoom.lens.rect = { x: inset.x, y: inset.y, width: inset.width, height: inset.height };
  }

  drawSpectrumAxes(ctx, plot, overviewScale, {
    compact,
    xLabel: "Wavelength (nm)",
    yLabel: stageId === "match" ? "Relative Intensity" : "Intensity",
    targetXTicks: compact ? 4 : 8,
    targetYTicks: compact ? 3 : 5,
  });
  drawSpectrumLine(ctx, overviewScale.rows, plot, overviewScale, stageId === "match" ? "#53606d" : "#253241", stageId === "raw" ? 1.6 : 1.25, {
    alpha: stageId === "match" ? 0.9 : 1,
    fillColor: stageId === "match" ? "#53606d" : null,
    fillAlpha: 0.08,
  });
  drawSpectrumOverviewFeatures(ctx, stageId, appState, overviewScale, plot, width);
  drawSpectrumFocusOverlay(ctx, plot, overviewScale, windowBounds, inset);
  drawSpectrumInset(ctx, stageId, appState, inset, windowBounds, emphasis, width);
  drawSpectrumCoordinateReadout(ctx, plot, stageId, appState, windowBounds);
}

function drawConfidenceRawPeakMarks(ctx, plot, scale, item) {
  if (!ctx || !plot || !scale || !item) {
    return;
  }
  const theoretical = item.rawPeakMarks ? item.rawPeakMarks.theoreticalWavelengths : [];
  const experimental = item.rawPeakMarks ? item.rawPeakMarks.selectedExperimentalPeaks : [];
  theoretical.forEach((point) => {
    const x = plot.left + (point.wavelength - scale.minX) * scale.xScale;
    if (x < plot.left || x > plot.right) {
      return;
    }
    ctx.strokeStyle = point.matched ? CONFIDENCE_COMB_COLORS.matchedTheoretical : CONFIDENCE_COMB_COLORS.allTheoretical;
    ctx.lineWidth = point.matched ? 1.8 : 1.1;
    ctx.beginPath();
    ctx.moveTo(x, plot.top);
    ctx.lineTo(x, plot.bottom);
    ctx.stroke();
  });
  experimental.forEach((point) => {
    const x = plot.left + (point.wavelength - scale.minX) * scale.xScale;
    if (x < plot.left || x > plot.right) {
      return;
    }
    ctx.fillStyle = CONFIDENCE_COMB_COLORS.matchedExperimental;
    ctx.beginPath();
    ctx.arc(x, plot.bottom - 12, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawMatchedStickSpectrum(ctx, plot, item) {
  if (!ctx || !plot || !item) {
    return;
  }
  const sticks = [...item.matchedTheoreticalComb, ...item.matchedExperimentalComb];
  const wavelengths = sticks.map((point) => point.wavelength).filter(Number.isFinite);
  if (wavelengths.length === 0) {
    return;
  }
  const minX = Math.min(...wavelengths);
  const maxX = Math.max(...wavelengths);
  const xScale = (plot.right - plot.left) / (maxX - minX || 1);
  function drawStick(point, color, yBase, maxHeight) {
    const x = plot.left + (point.wavelength - minX) * xScale;
    const height = normalizeNumber(point.normalizedIntensity) * maxHeight;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, yBase);
    ctx.lineTo(x, yBase - height);
    ctx.stroke();
  }
  item.matchedTheoreticalComb.forEach((point) => drawStick(point, CONFIDENCE_COMB_COLORS.matchedTheoretical, plot.bottom - 6, (plot.bottom - plot.top) * 0.38));
  item.matchedExperimentalComb.forEach((point) => drawStick(point, CONFIDENCE_COMB_COLORS.matchedExperimental, plot.top + (plot.bottom - plot.top) * 0.48, (plot.bottom - plot.top) * 0.34));
}

function drawRaw(canvas, appState) {
  drawSpectrumChart(canvas, appState, "raw");
}

function drawPeaks(canvas, appState) {
  drawSpectrumChart(canvas, appState, "peak");
}

function drawSpectralMatch(canvas, appState) {
  drawSpectrumChart(canvas, appState, "match");
}

function confidenceItemWavelengthWindow(item, spectrum) {
  const spectrumWindow = spectrumBounds(spectrum);
  const values = [
    ...(item.allTheoreticalComb || []).map((row) => row.wavelength),
    ...(item.matchedTheoreticalComb || []).map((row) => row.wavelength),
    ...(item.matchedExperimentalComb || []).map((row) => row.wavelength),
    ...((item.rawPeakMarks && item.rawPeakMarks.selectedExperimentalPeaks) || []).map((row) => row.wavelength),
  ].filter(Number.isFinite);
  if (!values.length) {
    return spectrumWindow;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = Math.max(1, maxValue - minValue);
  const pad = Math.max(1.5, span * 0.14);
  return {
    minX: Math.max(spectrumWindow.minX, minValue - pad),
    maxX: Math.min(spectrumWindow.maxX, maxValue + pad),
  };
}

function drawConfidenceLegend(ctx, plot, compact) {
  const items = [
    { label: compact ? "All" : "All Theoretical", color: CONFIDENCE_COMB_COLORS.allTheoretical },
    { label: compact ? "Theo" : "Matched Theoretical", color: CONFIDENCE_COMB_COLORS.matchedTheoretical },
    { label: compact ? "Exp" : "Matched Experimental", color: CONFIDENCE_COMB_COLORS.matchedExperimental },
  ];
  ctx.save();
  ctx.font = compact ? "10px system-ui, sans-serif" : "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  let x = plot.left;
  const y = plot.top - (compact ? 17 : 18);
  items.forEach((item) => {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + 18, y);
    ctx.stroke();
    ctx.fillStyle = item.color;
    ctx.beginPath();
    ctx.arc(x + 9, y, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#34414d";
    ctx.fillText(item.label, x + 24, y);
    x += compact ? 64 : 146;
  });
  ctx.restore();
}

function drawConfidenceEmptyState(canvas, message = "暂无置信度计算 payload") {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  ctx.save();
  ctx.fillStyle = "#f7f9fb";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#34414d";
  ctx.font = "700 15px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(message, width / 2, height / 2);
  ctx.restore();
}

function drawConfidenceRawPeakMarks(ctx, appState, item, plot, compact) {
  const windowBounds = confidenceItemWavelengthWindow(item, appState.spectrum);
  const extraY = ((item.rawPeakMarks && item.rawPeakMarks.selectedExperimentalPeaks) || []).map((peak) => peak.intensity);
  const scale = spectrumScaleForPlot(appState.spectrum, plot, windowBounds, {
    includeZero: true,
    yPadding: 0.12,
    extraY,
  });
  drawSpectrumAxes(ctx, plot, scale, {
    compact,
    xLabel: "Wavelength (nm)",
    yLabel: "Intensity",
    targetXTicks: compact ? 3 : 6,
    targetYTicks: compact ? 3 : 4,
  });
  drawSpectrumLine(ctx, scale.rows, plot, scale, "#1f2933", compact ? 1.2 : 1.55);

  const theoryRows =
    item.rawPeakMarks && item.rawPeakMarks.theoreticalWavelengths.length
      ? item.rawPeakMarks.theoreticalWavelengths
      : item.allTheoreticalComb;
  ctx.save();
  ctx.beginPath();
  ctx.rect(plot.left, plot.top, plot.right - plot.left, plot.bottom - plot.top);
  ctx.clip();
  theoryRows.forEach((row) => {
    if (!Number.isFinite(row.wavelength) || row.wavelength < scale.minX || row.wavelength > scale.maxX) {
      return;
    }
    const x = plot.left + (row.wavelength - scale.minX) * scale.xScale;
    ctx.strokeStyle = CONFIDENCE_COMB_COLORS.allTheoretical;
    ctx.globalAlpha = row.matched ? 0.62 : 0.34;
    ctx.lineWidth = row.matched ? 1.4 : 1.0;
    ctx.beginPath();
    ctx.moveTo(x, plot.top + 4);
    ctx.lineTo(x, plot.bottom);
    ctx.stroke();
  });
  ((item.rawPeakMarks && item.rawPeakMarks.selectedExperimentalPeaks) || []).forEach((peak) => {
    if (!Number.isFinite(peak.wavelength) || peak.wavelength < scale.minX || peak.wavelength > scale.maxX) {
      return;
    }
    const pos = projectSpectrumValue(peak.wavelength, peak.intensity, scale, plot);
    ctx.globalAlpha = 0.95;
    ctx.fillStyle = CONFIDENCE_COMB_COLORS.matchedExperimental;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, compact ? 3.4 : 4.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "#27323e";
  ctx.font = compact ? "700 11px system-ui, sans-serif" : "700 12px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(`实验峰筛选解释图 · ${item.ion}`, plot.left, Math.max(4, plot.top - 34));
  ctx.restore();
}

function combScaleForPlot(item, plot) {
  const rows = [...item.allTheoreticalComb, ...item.matchedTheoreticalComb, ...item.matchedExperimentalComb].filter((row) => Number.isFinite(row.wavelength));
  const wavelengths = rows.map((row) => row.wavelength);
  const minWavelength = wavelengths.length ? Math.min(...wavelengths) : 0;
  const maxWavelength = wavelengths.length ? Math.max(...wavelengths) : 1;
  const span = Math.max(1, maxWavelength - minWavelength);
  const pad = Math.max(0.5, span * 0.12);
  const maxY = Math.max(1e-6, ...rows.map((row) => normalizeNumber(row.normalizedIntensity)));
  return {
    minX: minWavelength - pad,
    maxX: maxWavelength + pad,
    minY: 0,
    maxY: maxY * 1.12,
    xScale: (plot.right - plot.left) / (span + pad * 2 || 1),
    yScale: (plot.bottom - plot.top) / (maxY * 1.12 || 1),
  };
}

function drawCombSticks(ctx, rows, scale, plot, color, options = {}) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(plot.left, plot.top, plot.right - plot.left, plot.bottom - plot.top);
  ctx.clip();
  ctx.strokeStyle = color;
  ctx.lineWidth = options.lineWidth || 1.7;
  ctx.globalAlpha = options.alpha === undefined ? 0.9 : options.alpha;
  const pixelOffset = options.pixelOffset || 0;
  rows.forEach((row) => {
    if (!Number.isFinite(row.wavelength) || row.wavelength < scale.minX || row.wavelength > scale.maxX) {
      return;
    }
    const x = plot.left + (row.wavelength - scale.minX) * scale.xScale + pixelOffset;
    const y = plot.bottom - (normalizeNumber(row.normalizedIntensity) - scale.minY) * scale.yScale;
    ctx.beginPath();
    ctx.moveTo(x, plot.bottom);
    ctx.lineTo(x, Math.max(plot.top, y));
    ctx.stroke();
  });
  ctx.restore();
}

function drawMatchedStickSpectrum(ctx, item, plot, compact) {
  const scale = combScaleForPlot(item, plot);
  drawSpectrumAxes(ctx, plot, scale, {
    compact,
    xLabel: "Wavelength (nm)",
    yLabel: "Normalized Intensity",
    targetXTicks: compact ? 3 : 6,
    targetYTicks: compact ? 3 : 4,
  });
  drawConfidenceLegend(ctx, plot, compact);
  drawCombSticks(ctx, item.allTheoreticalComb, scale, plot, CONFIDENCE_COMB_COLORS.allTheoretical, {
    alpha: 0.46,
    lineWidth: compact ? 1.2 : 1.45,
  });
  drawCombSticks(ctx, item.matchedTheoreticalComb, scale, plot, CONFIDENCE_COMB_COLORS.matchedTheoretical, {
    alpha: 0.9,
    lineWidth: compact ? 1.8 : 2.1,
    pixelOffset: compact ? -1.5 : -2.2,
  });
  drawCombSticks(ctx, item.matchedExperimentalComb, scale, plot, CONFIDENCE_COMB_COLORS.matchedExperimental, {
    alpha: 0.9,
    lineWidth: compact ? 1.8 : 2.1,
    pixelOffset: compact ? 1.5 : 2.2,
  });

  ctx.save();
  ctx.fillStyle = "#27323e";
  ctx.font = compact ? "700 11px system-ui, sans-serif" : "700 12px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText("Matched Stick Spectrum", plot.left, Math.max(4, plot.top - 38));
  ctx.restore();
}

function drawConfidenceCalculation(canvas, appState) {
  const item = selectedConfidenceItem(appState.confidenceCalculation);
  if (!item) {
    drawConfidenceEmptyState(canvas);
    return;
  }
  const summary = confidenceTrustSummary(item, appState.confidenceCalculation);
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  const compact = width < 620;
  const pad = {
    left: compact ? 52 : 62,
    right: compact ? 18 : 28,
    top: compact ? 116 : 110,
    bottom: compact ? 42 : 48,
  };
  const gap = compact ? 42 : 58;
  const availableHeight = height - pad.top - pad.bottom - gap;
  const rawHeight = Math.max(compact ? 104 : 150, availableHeight * 0.48);
  const rawPlot = {
    left: pad.left,
    top: pad.top,
    right: width - pad.right,
    bottom: Math.min(height - pad.bottom - gap - 96, pad.top + rawHeight),
  };
  rawPlot.bottom = Math.max(rawPlot.top + (compact ? 96 : 108), rawPlot.bottom);
  const stickPlot = {
    left: pad.left,
    top: rawPlot.bottom + gap,
    right: width - pad.right,
    bottom: height - pad.bottom,
  };
  if (stickPlot.bottom - stickPlot.top < 100) {
    stickPlot.top = Math.max(rawPlot.bottom + 38, stickPlot.bottom - 118);
  }

  ctx.save();
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#27323e";
  ctx.font = compact ? "700 12px system-ui, sans-serif" : "700 14px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(`${summary.ion} / ${summary.element} · 原始置信度 ${summary.confidenceText} · ${summary.band}`, pad.left, 8);
  ctx.fillStyle = "#5f6a75";
  ctx.font = compact ? "10px system-ui, sans-serif" : "11px system-ui, sans-serif";
  ctx.fillText(
    truncateCanvasText(ctx, `复核点: ${summary.reviewText}`, width - pad.left - pad.right),
    pad.left,
    compact ? 26 : 29,
  );
  ctx.fillText(
    truncateCanvasText(ctx, `distance ${summary.distanceText} · ${summary.gateText} · T ${summary.temperatureText} · R2 ${summary.r2Text} · matched/all ${summary.matchedAllText}`, width - pad.left - pad.right),
    pad.left,
    compact ? 43 : 49,
  );
  ctx.restore();

  drawConfidenceRawPeakMarks(ctx, appState, item, rawPlot, compact);
  drawMatchedStickSpectrum(ctx, item, stickPlot, compact);
}

function temperaturePointScore(row) {
  return normalizeNumber(row.score, normalizeNumber(row.confidence) - 0.35 * Math.abs(normalizeNumber(row.r2) - 1));
}

function scoreColor(score, minScore, maxScore) {
  const ratio = Math.max(0, Math.min(1, (score - minScore) / (maxScore - minScore || 1)));
  const r = Math.round(45 + ratio * 173);
  const g = Math.round(103 + ratio * 82);
  const b = Math.round(142 - ratio * 82);
  return `rgb(${r}, ${g}, ${b})`;
}

function startCurveColor(index) {
  return TEMPERATURE_CURVE_COLORS[Math.abs(Number(index) || 0) % TEMPERATURE_CURVE_COLORS.length];
}

function hexColorText(hexValue) {
  return `#${Number(hexValue).toString(16).padStart(6, "0")}`;
}

function interpolateRgb(left, right, ratio) {
  return left.map((value, index) => Math.round(value + (right[index] - value) * ratio));
}

function temperatureColor(temperature, minTemperature, maxTemperature) {
  const ratio = Math.max(0, Math.min(1, (normalizeNumber(temperature) - minTemperature) / (maxTemperature - minTemperature || 1)));
  let left = TEMPERATURE_COLOR_STOPS[0];
  let right = TEMPERATURE_COLOR_STOPS.at(-1);
  for (let index = 0; index < TEMPERATURE_COLOR_STOPS.length - 1; index += 1) {
    const current = TEMPERATURE_COLOR_STOPS[index];
    const next = TEMPERATURE_COLOR_STOPS[index + 1];
    if (ratio >= current.at && ratio <= next.at) {
      left = current;
      right = next;
      break;
    }
  }
  const localRatio = (ratio - left.at) / (right.at - left.at || 1);
  const [r, g, b] = interpolateRgb(left.rgb, right.rgb, localRatio);
  return `rgb(${r}, ${g}, ${b})`;
}

function temperatureStartAxisLabel(start) {
  return `T0=${Math.round(normalizeNumber(start && start.initialTemperature))}K`;
}

function temperatureStartTickLabel(start) {
  return `${Math.round(normalizeNumber(start && start.initialTemperature))}`;
}

function temperatureIterationTicks(maxIteration) {
  const maxValue = Math.max(1, Math.round(normalizeNumber(maxIteration, 1)));
  const step = Math.max(1, Math.ceil(maxValue / 5));
  const ticks = [];
  for (let value = 0; value < maxValue; value += step) {
    ticks.push(value);
  }
  if (!ticks.includes(maxValue)) {
    ticks.push(maxValue);
  }
  return ticks;
}

function temperatureScoreTicks(minScore, maxScore) {
  const minValue = normalizeNumber(minScore);
  const maxValue = normalizeNumber(maxScore, 1);
  if (maxValue <= minValue) {
    return [minValue];
  }
  return [minValue, (minValue + maxValue) / 2, maxValue].map((value) => Number(value.toFixed(2)));
}

function shouldShowTemperatureStartLabel(startPosition, startCount, selected = false, compact = false) {
  return true;
}

function temperatureStartLabelPosition(xSpan, zSpan, startPosition, startCount, compact = false) {
  const count = Math.max(1, Math.round(normalizeNumber(startCount, 1)));
  const index = Math.max(0, Math.round(normalizeNumber(startPosition)));
  const z = (index / Math.max(1, count - 1) - 0.5) * zSpan;
  return {
    x: compact ? -xSpan / 2 + 1.08 : -xSpan / 2 - 0.84,
    y: compact ? -0.12 : -0.18,
    z,
  };
}

function temperatureStartAxisTitlePosition(xSpan, zSpan, compact = false) {
  return {
    x: -xSpan / 2 + (compact ? 1.68 : 0.95),
    y: compact ? -0.58 : -0.68,
    z: zSpan / 2 + (compact ? 0.46 : 0.62),
  };
}

function temperatureFrontIterationZ(zSpan) {
  return Math.max(0.1, Math.abs(normalizeNumber(zSpan, 1)) / 2);
}

let threeJsLoadPromise = null;

function loadThreeJsScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.dataset.threeSource = url;
    script.onload = () => (window.THREE ? resolve(window.THREE) : reject(new Error("Three.js did not expose window.THREE")));
    script.onerror = () => {
      script.remove();
      reject(new Error(`Three.js failed to load from ${url}`));
    };
    document.head.appendChild(script);
  });
}

function ensureThreeJs() {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Three.js is only loaded in the browser"));
  }
  if (window.THREE) {
    return Promise.resolve(window.THREE);
  }
  if (threeJsLoadPromise) {
    return threeJsLoadPromise;
  }
  threeJsLoadPromise = (async () => {
    const errors = [];
    for (const url of THREE_JS_URLS) {
      try {
        return await loadThreeJsScript(url);
      } catch (error) {
        errors.push(error.message);
      }
    }
    throw new Error(errors.join("; ") || "Three.js failed to load");
  })();
  threeJsLoadPromise.catch(() => {
    threeJsLoadPromise = null;
  });
  return threeJsLoadPromise;
}

function scheduleTemperatureRendererPreload() {
  if (typeof window === "undefined") {
    return;
  }
  const preload = () => {
    ensureThreeJs().catch(() => {});
  };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(preload, { timeout: 1500 });
    return;
  }
  window.setTimeout(preload, 600);
}

function drawTemperatureFallback(canvas, appState) {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  const starts = appState.temperatureStarts && appState.temperatureStarts.length
    ? appState.temperatureStarts
    : [
        {
          startIndex: 0,
          initialTemperature: appState.temperatureIterations[0] ? appState.temperatureIterations[0].temperature : appState.targetTemperature,
          finalTemperature: appState.targetTemperature,
          bestScore: appState.temperatureBestScore || 0,
          selected: true,
          trace: appState.temperatureIterations,
        },
      ];
  const traces = starts.map((start) => (start.trace && start.trace.length ? start.trace : [
    {
      iteration: 0,
      temperature: start.finalTemperature,
      candidate: start.bestCandidate || "无",
      confidence: start.bestConfidence || 0,
      r2: start.bestR2 || 0,
      score: start.bestScore || 0,
      delta: 0,
    },
  ]));
  const allPoints = traces.flatMap((trace, startIndex) => trace.map((point) => ({ ...point, startIndex, score: temperaturePointScore(point) })));
  const minScore = Math.min(0, ...allPoints.map((point) => point.score));
  const maxScore = Math.max(0.01, ...allPoints.map((point) => point.score));
  const maxIteration = Math.max(1, ...allPoints.map((point) => normalizeNumber(point.iteration)));
  const pad = {
    left: width < 620 ? 46 : 62,
    right: width < 620 ? 30 : 56,
    top: width < 620 ? 32 : 36,
    bottom: width < 620 ? 46 : 54,
  };
  const depthX = width < 620 ? 10 : 18;
  const depthY = width < 620 ? 8 : 12;
  const plotWidth = Math.max(90, width - pad.left - pad.right - depthX * Math.max(0, starts.length - 1));
  const plotHeight = Math.max(80, height - pad.top - pad.bottom - depthY * Math.max(0, starts.length - 1));
  const baseY = height - pad.bottom;
  const bestStart = starts.find((start) => start.selected) || starts[0];
  const bestStartIndex = starts.indexOf(bestStart);

  function project(point, startIndex) {
    const iteration = normalizeNumber(point.iteration);
    const score = temperaturePointScore(point);
    const scoreRatio = (score - minScore) / (maxScore - minScore || 1);
    return {
      x: pad.left + (iteration / maxIteration) * plotWidth + startIndex * depthX,
      y: baseY - startIndex * depthY - scoreRatio * plotHeight,
      baseY: baseY - startIndex * depthY,
      score,
    };
  }

  ctx.strokeStyle = "#ccd2d8";
  ctx.lineWidth = 1;
  starts.forEach((start, startIndex) => {
    const y = baseY - startIndex * depthY;
    const x0 = pad.left + startIndex * depthX;
    ctx.globalAlpha = start.selected ? 0.75 : 0.42;
    ctx.beginPath();
    ctx.moveTo(x0, y);
    ctx.lineTo(x0 + plotWidth, y);
    ctx.stroke();
    if (width >= 540 || start.selected || startIndex === 0 || startIndex === starts.length - 1) {
      ctx.fillStyle = start.selected ? "#27323e" : "#6b747d";
      ctx.font = width < 620 ? "10px system-ui, sans-serif" : "11px system-ui, sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(`S${start.startIndex + 1}`, x0 - 6, y + 4);
    }
  });
  ctx.globalAlpha = 1;

  ctx.strokeStyle = "#aeb7c0";
  ctx.beginPath();
  ctx.moveTo(pad.left, baseY);
  ctx.lineTo(pad.left + plotWidth, baseY);
  ctx.moveTo(pad.left, baseY);
  ctx.lineTo(pad.left + depthX * Math.max(1, starts.length - 1), baseY - depthY * Math.max(1, starts.length - 1));
  ctx.moveTo(pad.left, baseY);
  ctx.lineTo(pad.left, pad.top);
  ctx.stroke();

  ctx.fillStyle = "#5f6a75";
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("综合评分", 12, 18);
  ctx.fillText("迭代轮次", Math.max(pad.left, width - pad.right - 78), height - 14);
  if (width >= 520) {
    ctx.fillText("起始温度 T0/K", pad.left + depthX * starts.length + 8, baseY - depthY * starts.length - 4);
  } else {
    ctx.fillText("起点 T0", pad.left + depthX * starts.length + 4, baseY - depthY * starts.length - 4);
  }

  let bestPoint = null;
  traces.forEach((trace, startIndex) => {
    const coords = trace.map((point) => ({ point, ...project(point, startIndex) }));
    const selected = starts[startIndex] && starts[startIndex].selected;
    ctx.strokeStyle = selected ? "#c47a22" : "#005f8e";
    ctx.lineWidth = selected ? 2.4 : 1.4;
    ctx.globalAlpha = selected ? 1 : 0.52;
    ctx.beginPath();
    coords.forEach((coord, index) => {
      if (index === 0) {
        ctx.moveTo(coord.x, coord.y);
      } else {
        ctx.lineTo(coord.x, coord.y);
      }
    });
    ctx.stroke();

    coords.forEach((coord) => {
      if (!bestPoint || coord.score > bestPoint.score || (selected && coord.score === bestPoint.score)) {
        bestPoint = { ...coord, selected, startIndex };
      }
      ctx.strokeStyle = selected ? "#9a5d16" : "#244d66";
      ctx.fillStyle = scoreColor(coord.score, minScore, maxScore);
      ctx.lineWidth = selected ? 1.5 : 1;
      ctx.beginPath();
      ctx.ellipse(coord.x, coord.y, selected ? 5.2 : 4.2, selected ? 4.0 : 3.2, -0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
  });
  ctx.globalAlpha = 1;

  if (bestPoint) {
    ctx.strokeStyle = "#d17a00";
    ctx.fillStyle = "rgba(209, 122, 0, 0.12)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(bestPoint.x, bestPoint.y, 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (width >= 520) {
      ctx.fillStyle = "#27323e";
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(
        `最优 ${temperatureStartAxisLabel(starts[bestStartIndex])}: ${appState.targetTemperature.toFixed(0)} K / 评分 ${normalizeNumber(appState.temperatureBestScore, bestPoint.score).toFixed(3)}`,
        pad.left,
        pad.top - 8,
      );
    }
  }

  const legendY = height - 18;
  const legendX = pad.left;
  const gradientWidth = width < 620 ? 82 : 118;
  const gradient = ctx.createLinearGradient(legendX, legendY, legendX + gradientWidth, legendY);
  gradient.addColorStop(0, scoreColor(minScore, minScore, maxScore));
  gradient.addColorStop(1, scoreColor(maxScore, minScore, maxScore));
  ctx.fillStyle = gradient;
  ctx.fillRect(legendX, legendY - 7, gradientWidth, 8);
  ctx.strokeStyle = "#c2c8cf";
  ctx.strokeRect(legendX, legendY - 7, gradientWidth, 8);
  ctx.fillStyle = "#5f6a75";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(minScore.toFixed(2), legendX + gradientWidth + 8, legendY);
  ctx.fillText(maxScore.toFixed(2), legendX + gradientWidth + 50, legendY);
  ctx.textAlign = "left";
}

function drawTemperatureLoading(canvas) {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  ctx.fillStyle = "#27323e";
  ctx.font = "13px system-ui, sans-serif";
  ctx.fillText("Loading Three.js temperature scene...", 24, 34);
}

function prepareTemperatureThreeCanvas(mainCanvas) {
  const host = mainCanvas.parentElement;
  const rect = mainCanvas.getBoundingClientRect();
  const width = Math.max(320, rect.width || mainCanvas.clientWidth || 640);
  const height = Math.max(260, rect.height || mainCanvas.clientHeight || 320);
  disposeTemperatureThreeCanvas(mainCanvas);

  const threeCanvas = document.createElement("canvas");
  threeCanvas.className = TEMPERATURE_THREE_CANVAS_CLASS;
  threeCanvas.setAttribute("aria-label", "温度迭代 Three.js 3D 图谱");
  threeCanvas.style.gridRow = "2";
  threeCanvas.style.gridColumn = "1";
  threeCanvas.style.width = "100%";
  threeCanvas.style.height = "100%";
  threeCanvas.style.minHeight = "260px";
  threeCanvas.style.display = "block";
  threeCanvas.style.background = "#ffffff";
  threeCanvas.style.touchAction = "none";
  host.appendChild(threeCanvas);
  mainCanvas.style.display = "none";
  mainCanvas.dataset.chartMode = "temperature3d";
  return { threeCanvas, width, height };
}

function temperature3DData(appState) {
  const starts = appState.temperatureStarts && appState.temperatureStarts.length
    ? appState.temperatureStarts
    : [
        {
          startIndex: 0,
          initialTemperature: appState.temperatureIterations[0] ? appState.temperatureIterations[0].temperature : appState.targetTemperature,
          finalTemperature: appState.targetTemperature,
          bestScore: appState.temperatureBestScore || 0,
          selected: true,
          trace: appState.temperatureIterations,
        },
      ];
  const traces = starts.map((start) => (start.trace && start.trace.length ? start.trace : [
    {
      iteration: 0,
      temperature: start.finalTemperature,
      candidate: start.bestCandidate || "无",
      confidence: start.bestConfidence || 0,
      r2: start.bestR2 || 0,
      score: start.bestScore || 0,
      delta: 0,
    },
  ]));
  const points = traces.flatMap((trace, startPosition) =>
    trace.map((point) => ({
      ...point,
      startPosition,
      startLabel: starts[startPosition].startIndex + 1,
      selected: Boolean(starts[startPosition].selected),
      score: temperaturePointScore(point),
    })),
  );
  return {
    starts,
    traces,
    points,
    minScore: Math.min(0, ...points.map((point) => point.score)),
    maxScore: Math.max(0.01, ...points.map((point) => point.score)),
    minTemperature: Math.min(...points.map((point) => normalizeNumber(point.temperature))),
    maxTemperature: Math.max(...points.map((point) => normalizeNumber(point.temperature))),
    maxIteration: Math.max(1, ...points.map((point) => normalizeNumber(point.iteration))),
  };
}

function createTextSprite(THREE, text, color = "#27323e", fontSize = 38) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  ctx.font = `${fontSize}px system-ui, sans-serif`;
  const textWidth = Math.ceil(ctx.measureText(text).width);
  canvas.width = Math.max(64, textWidth + 24);
  canvas.height = fontSize + 22;
  ctx.font = `${fontSize}px system-ui, sans-serif`;
  ctx.fillStyle = color;
  ctx.textBaseline = "middle";
  ctx.fillText(text, 12, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  const scale = 0.012;
  sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
  return sprite;
}

function createTemperatureLegendSprite(THREE, minTemperature, maxTemperature, compact = false) {
  const canvas = document.createElement("canvas");
  canvas.width = compact ? 160 : 210;
  canvas.height = compact ? 300 : 360;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#8b97a3";
  ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);

  const gradientX = compact ? 28 : 34;
  const gradientY = compact ? 70 : 84;
  const gradientW = compact ? 34 : 42;
  const gradientH = compact ? 190 : 230;
  const gradient = ctx.createLinearGradient(gradientX, gradientY + gradientH, gradientX, gradientY);
  TEMPERATURE_COLOR_STOPS.forEach((stop) => {
    gradient.addColorStop(stop.at, `rgb(${stop.rgb.join(", ")})`);
  });
  ctx.fillStyle = gradient;
  ctx.fillRect(gradientX, gradientY, gradientW, gradientH);
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#404a55";
  ctx.strokeRect(gradientX, gradientY, gradientW, gradientH);

  ctx.fillStyle = "#111827";
  ctx.font = `700 ${compact ? 24 : 30}px system-ui, sans-serif`;
  ctx.fillText("温度/K", gradientX, compact ? 44 : 52);
  ctx.font = `700 ${compact ? 18 : 22}px system-ui, sans-serif`;
  ctx.fillText(`${Math.round(maxTemperature)}K`, gradientX + gradientW + 12, gradientY + 8);
  ctx.fillText(`${Math.round(minTemperature)}K`, gradientX + gradientW + 12, gradientY + gradientH);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  const scale = compact ? 0.013 : 0.012;
  sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
  return sprite;
}

function temperatureLegendHudLayout(width, height, compact = false) {
  const legendWidth = compact ? 90 : 132;
  const legendHeight = compact ? 168 : 226;
  const right = compact ? 8 : 18;
  const top = compact ? Math.max(42, height * 0.16) : Math.max(70, height * 0.16);
  return {
    width: legendWidth,
    height: legendHeight,
    x: Math.max(legendWidth / 2 + 8, width - right - legendWidth / 2),
    y: Math.min(height - legendHeight / 2 - 10, top + legendHeight / 2),
  };
}

function addLine(THREE, parent, points, color, opacity = 1, width = 1) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity, linewidth: width });
  const line = new THREE.Line(geometry, material);
  parent.add(line);
  return line;
}

function renderTemperatureThreeScene(mainCanvas, appState, THREE) {
  const { threeCanvas, width, height } = prepareTemperatureThreeCanvas(mainCanvas);
  const data = temperature3DData(appState);
  const compact = width < 620;
  const labelFontSize = compact ? 28 : 34;
  const xSpan = 10;
  const ySpan = 4.8;
  const zSpan = Math.max(3.8, data.starts.length * 0.75);
  const selectedStart = data.starts.find((start) => start.selected) || data.starts[0];
  const selectedStartPosition = data.starts.indexOf(selectedStart);

  function positionFor(point, startPosition) {
    const x = (normalizeNumber(point.iteration) / data.maxIteration - 0.5) * xSpan;
    const y = ((temperaturePointScore(point) - data.minScore) / (data.maxScore - data.minScore || 1)) * ySpan;
    const z = (startPosition / Math.max(1, data.starts.length - 1) - 0.5) * zSpan;
    return new THREE.Vector3(x, y, z);
  }

  const renderer = new THREE.WebGLRenderer({ canvas: threeCanvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  renderer.setClearColor(0xffffff, 1);
  renderer.autoClear = false;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000);
  camera.position.set(0, 5.6, 12.5);
  camera.lookAt(0, 1.8, 0);
  scene.add(new THREE.AmbientLight(0xffffff, 0.82));
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.65);
  keyLight.position.set(4, 8, 5);
  scene.add(keyLight);
  const hudScene = new THREE.Scene();
  const hudCamera = new THREE.OrthographicCamera(0, width, height, 0, 0, 10);
  hudCamera.position.z = 10;
  const cameraTarget = new THREE.Vector3(0, 1.8, 0);
  let cameraDistance = 12.5;

  const root = new THREE.Group();
  root.rotation.y = TEMPERATURE_INITIAL_YAW;
  root.rotation.x = TEMPERATURE_INITIAL_PITCH;
  scene.add(root);

  const base = new THREE.Group();
  root.add(base);
  const axisMaterial = 0x9da9b4;
  const frontIterationZ = temperatureFrontIterationZ(zSpan);
  addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, 0, frontIterationZ), new THREE.Vector3(xSpan / 2, 0, frontIterationZ)], axisMaterial, 0.95);
  addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, 0, -zSpan / 2), new THREE.Vector3(-xSpan / 2, 0, zSpan / 2)], axisMaterial, 0.9);
  addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, 0, -zSpan / 2), new THREE.Vector3(-xSpan / 2, ySpan, -zSpan / 2)], axisMaterial, 0.9);

  const iterationTicks = temperatureIterationTicks(data.maxIteration);
  for (let i = 0; i <= data.maxIteration; i += 1) {
    const x = (i / data.maxIteration - 0.5) * xSpan;
    addLine(THREE, base, [new THREE.Vector3(x, 0, -zSpan / 2), new THREE.Vector3(x, 0, zSpan / 2)], 0xd9dee3, 0.45);
  }
  iterationTicks.forEach((tick) => {
    const x = (tick / data.maxIteration - 0.5) * xSpan;
    addLine(THREE, base, [new THREE.Vector3(x, 0, frontIterationZ), new THREE.Vector3(x, -0.14, frontIterationZ)], axisMaterial, 0.82);
    const label = createTextSprite(THREE, String(tick), "#5f6a75", compact ? 24 : 28);
    label.position.set(x, -0.38, frontIterationZ + 0.24);
    base.add(label);
  });

  temperatureScoreTicks(data.minScore, data.maxScore).forEach((tick) => {
    const y = ((tick - data.minScore) / (data.maxScore - data.minScore || 1)) * ySpan;
    addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, y, -zSpan / 2), new THREE.Vector3(-xSpan / 2 - 0.18, y, -zSpan / 2)], axisMaterial, 0.72);
    addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, y, -zSpan / 2), new THREE.Vector3(xSpan / 2, y, -zSpan / 2)], 0xd9dee3, 0.22);
    const label = createTextSprite(THREE, tick.toFixed(2), "#5f6a75", compact ? 24 : 28);
    label.position.set(-xSpan / 2 - 0.58, y, -zSpan / 2 - 0.12);
    base.add(label);
  });

  data.starts.forEach((start, startPosition) => {
    const z = (startPosition / Math.max(1, data.starts.length - 1) - 0.5) * zSpan;
    const curveColor = startCurveColor(startPosition);
    addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, 0, z), new THREE.Vector3(xSpan / 2, 0, z)], curveColor, start.selected ? 0.78 : 0.34);
    addLine(THREE, base, [new THREE.Vector3(-xSpan / 2, 0, z), new THREE.Vector3(-xSpan / 2 - (compact ? 0.08 : 0.14), 0, z)], axisMaterial, 0.74);
    const shouldShowStartLabel = shouldShowTemperatureStartLabel(startPosition, data.starts.length, start.selected, compact);
    if (shouldShowStartLabel) {
      const label = createTextSprite(THREE, temperatureStartTickLabel(start), "#5f6a75", compact ? 13 : 17);
      const labelPosition = temperatureStartLabelPosition(xSpan, zSpan, startPosition, data.starts.length, compact);
      label.position.set(labelPosition.x, labelPosition.y, labelPosition.z);
      base.add(label);
    }
  });

  const xLabel = createTextSprite(THREE, compact ? "轮次" : "迭代轮次", "#4f5b67", labelFontSize);
  xLabel.position.set(xSpan / 2 - (compact ? 1.55 : 1.35), 0.18, frontIterationZ + 0.34);
  base.add(xLabel);
  const yLabel = createTextSprite(THREE, "综合评分", "#4f5b67", labelFontSize);
  yLabel.position.set(-xSpan / 2 - 0.75, ySpan + 0.28, -zSpan / 2);
  base.add(yLabel);
  const zLabel = createTextSprite(THREE, compact ? "起点温度" : "起点温度/K", "#4f5b67", compact ? 22 : 24);
  const zLabelPosition = temperatureStartAxisTitlePosition(xSpan, zSpan, compact);
  zLabel.position.set(zLabelPosition.x, zLabelPosition.y, zLabelPosition.z);
  base.add(zLabel);
  const colorLegend = createTemperatureLegendSprite(THREE, data.minTemperature, data.maxTemperature, compact);
  const legendLayout = temperatureLegendHudLayout(width, height, compact);
  colorLegend.scale.set(legendLayout.width, legendLayout.height, 1);
  colorLegend.position.set(legendLayout.x, height - legendLayout.y, 0);
  colorLegend.material.transparent = false;
  colorLegend.material.depthTest = false;
  colorLegend.material.depthWrite = false;
  hudScene.add(colorLegend);

  let best = null;
  data.traces.forEach((trace, startPosition) => {
    const start = data.starts[startPosition];
    const selected = Boolean(start && start.selected);
    const curveColor = startCurveColor(startPosition);
    const vectors = trace.map((point) => positionFor(point, startPosition));
    addLine(THREE, root, vectors, curveColor, selected ? 1 : 0.72, selected ? 2.4 : 1.4);
    trace.forEach((point) => {
      const vector = positionFor(point, startPosition);
      const score = temperaturePointScore(point);
      if (!best || score > best.score || (selected && score === best.score)) {
        best = { vector, point, score, start };
      }
      addLine(THREE, root, [new THREE.Vector3(vector.x, 0, vector.z), vector], curveColor, selected ? 0.28 : 0.16);
      const geometry = new THREE.SphereGeometry(selected ? 0.105 : 0.075, 20, 14);
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(temperatureColor(point.temperature, data.minTemperature, data.maxTemperature)),
        emissive: selected ? new THREE.Color(hexColorText(curveColor)).multiplyScalar(0.08) : 0x000000,
        roughness: 0.42,
        metalness: 0.05,
      });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.copy(vector);
      root.add(sphere);
    });
  });

  if (best) {
    const highlight = new THREE.Mesh(
      new THREE.SphereGeometry(0.18, 28, 18),
      new THREE.MeshStandardMaterial({ color: 0xd17a00, emissive: 0x4a2200, roughness: 0.35 }),
    );
    highlight.position.copy(best.vector);
    root.add(highlight);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.28, 0.018, 8, 40),
      new THREE.MeshBasicMaterial({ color: 0xd17a00 }),
    );
    ring.position.copy(best.vector);
    ring.rotation.x = Math.PI / 2.4;
    root.add(ring);
    const label = createTextSprite(
      THREE,
      compact
        ? `最优 ${temperatureStartAxisLabel(selectedStart)}`
        : `最优 ${temperatureStartAxisLabel(selectedStart)}: ${appState.targetTemperature.toFixed(0)} K / 评分 ${normalizeNumber(appState.temperatureBestScore, best.score).toFixed(3)}`,
      "#27323e",
      labelFontSize,
    );
    label.position.copy(best.vector.clone().add(new THREE.Vector3(1.25, 0.36, 0)));
    root.add(label);
  }

  let yaw = TEMPERATURE_INITIAL_YAW;
  let pitch = TEMPERATURE_INITIAL_PITCH;
  let dragging = false;
  let previousX = 0;
  let previousY = 0;

  function updateCamera() {
    camera.position.set(0, 5.6, cameraDistance);
    camera.lookAt(cameraTarget);
  }

  function renderScene() {
    root.rotation.y = yaw;
    root.rotation.x = pitch;
    updateCamera();
    renderer.clear();
    renderer.render(scene, camera);
    renderer.clearDepth();
    renderer.render(hudScene, hudCamera);
  }

  function handlePointerDown(event) {
    dragging = true;
    previousX = event.clientX;
    previousY = event.clientY;
    threeCanvas.setPointerCapture(event.pointerId);
  }
  function handlePointerMove(event) {
    if (!dragging) {
      return;
    }
    const dx = event.clientX - previousX;
    const dy = event.clientY - previousY;
    previousX = event.clientX;
    previousY = event.clientY;
    yaw += dx * 0.006;
    pitch = Math.max(-0.72, Math.min(0.35, pitch + dy * 0.006));
    renderScene();
  }
  function handlePointerUp(event) {
    dragging = false;
    if (threeCanvas.hasPointerCapture(event.pointerId)) {
      threeCanvas.releasePointerCapture(event.pointerId);
    }
  }
  function handleWheel(event) {
    event.preventDefault();
    const scale = event.deltaY > 0 ? 1.08 : 0.92;
    cameraDistance = Math.max(6.2, Math.min(22, cameraDistance * scale));
    renderScene();
  }

  threeCanvas.addEventListener("pointerdown", handlePointerDown);
  threeCanvas.addEventListener("pointermove", handlePointerMove);
  threeCanvas.addEventListener("pointerup", handlePointerUp);
  threeCanvas.addEventListener("pointercancel", handlePointerUp);
  threeCanvas.addEventListener("wheel", handleWheel, { passive: false });

  renderScene();

  threeCanvas.dataset.renderer = "threejs";
  threeCanvas.__disposeTemperatureScene = () => {
    threeCanvas.removeEventListener("pointerdown", handlePointerDown);
    threeCanvas.removeEventListener("pointermove", handlePointerMove);
    threeCanvas.removeEventListener("pointerup", handlePointerUp);
    threeCanvas.removeEventListener("pointercancel", handlePointerUp);
    threeCanvas.removeEventListener("wheel", handleWheel);
    [scene, hudScene].forEach((graph) => {
      graph.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        const materials = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
        materials.forEach((material) => {
          if (material.map) {
            material.map.dispose();
          }
          material.dispose();
        });
      });
    });
    renderer.dispose();
  };
}

function drawTemperature(canvas, appState) {
  drawTemperatureLoading(canvas);
  const renderToken = `${Date.now()}-${Math.random()}`;
  canvas.dataset.chartMode = "temperature3d";
  canvas.dataset.temperatureRenderToken = renderToken;
  ensureThreeJs()
    .then((THREE) => {
      if (canvas.dataset.temperatureRenderToken !== renderToken || canvas.dataset.chartMode !== "temperature3d") {
        return;
      }
      renderTemperatureThreeScene(canvas, appState, THREE);
    })
    .catch(() => {
      if (canvas.dataset.temperatureRenderToken === renderToken) {
        drawTemperatureFallback(canvas, appState);
      }
    });
}

function drawFit(canvas, appState) {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  const xMin = appState.fitWindow.left;
  const xMax = appState.fitWindow.right;
  const hasBackendFit = appState.fitRawPoints.length >= 2 && appState.fitSumFitPoints.length >= 2;
  const legendItems = [
    { label: "原始光谱", color: "#1f6fb2" },
    { label: "分峰曲线", color: "#2f9e44" },
    { label: "总拟合", color: "#d97706", dashed: true },
    { label: "拟合峰位", color: "#2f9e44", marker: true },
    { label: "局部极值", color: "#c92a2a", marker: true },
  ];
  const useSideLegend = hasBackendFit && width >= 720;
  const pad = drawAxes(ctx, width, height, "强度", {
    top: hasBackendFit ? (width < 620 ? 58 : 42) : 22,
    right: useSideLegend ? 190 : 18,
    bottom: hasBackendFit ? 52 : 34,
  });

  if (hasBackendFit) {
    const componentPoints = appState.fitComponentCurves.flatMap((component) => component.points || []);
    const markerPoints = [
      ...appState.fitFittedPeaks.map((peak) => ({ x: peak.wavelength, y: peak.intensity })),
      ...appState.fitLocalExtrema.map((point) => ({ x: point.wavelength, y: point.intensity })),
    ];
    const allPoints = [
      ...appState.fitRawPoints,
      ...appState.fitSumFitPoints,
      ...componentPoints,
      ...markerPoints,
    ].filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
    let minX = Math.min(...allPoints.map((point) => point.x));
    let maxX = Math.max(...allPoints.map((point) => point.x));
    let minY = Math.min(...allPoints.map((point) => point.y));
    let maxY = Math.max(...allPoints.map((point) => point.y));
    if (!Number.isFinite(minX) || !Number.isFinite(maxX) || minX === maxX) {
      minX = xMin;
      maxX = xMax;
    }
    const dataBounds = { minX, maxX, minY, maxY };
    const yRange = dataBounds.maxY - dataBounds.minY || 1;
    minY = dataBounds.minY - yRange * 0.08;
    maxY = dataBounds.maxY + yRange * 0.12;
    const xScale = (width - pad.left - pad.right) / (maxX - minX || 1);
    const yScale = (height - pad.top - pad.bottom) / (maxY - minY || 1);
    function project(point) {
      return {
        x: pad.left + (point.x - minX) * xScale,
        y: height - pad.bottom - (point.y - minY) * yScale,
      };
    }

    drawFitAxisTicks(ctx, pad, width, height, dataBounds, project);

    function drawScaledLine(data, color, lineWidth = 2, dash = []) {
      if (!data || data.length < 2) {
        return;
      }
      ctx.save();
      ctx.beginPath();
      ctx.rect(pad.left, pad.top, width - pad.left - pad.right, height - pad.top - pad.bottom);
      ctx.clip();
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.setLineDash(dash);
      ctx.beginPath();
      data.forEach((point, index) => {
        const pos = project(point);
        if (index === 0) {
          ctx.moveTo(pos.x, pos.y);
        } else {
          ctx.lineTo(pos.x, pos.y);
        }
      });
      ctx.stroke();
      ctx.restore();
    }

    drawScaledLine(appState.fitRawPoints, "#1f6fb2", 2.0);
    appState.fitComponentCurves.forEach((component) => {
      drawScaledLine(component.points, component.color || "#2f9e44", 1.5);
    });
    drawScaledLine(appState.fitSumFitPoints, "#d97706", 2.0, [6, 4]);

    appState.fitLocalExtrema.forEach((point) => {
      const pos = project({ x: point.wavelength, y: point.intensity });
      ctx.fillStyle = "#c92a2a";
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
    appState.fitFittedPeaks.forEach((peak) => {
      const pos = project({ x: peak.wavelength, y: peak.intensity });
      ctx.fillStyle = "#2f9e44";
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    const baselineText = appState.fitBaseline === null ? "基线 n/a" : `基线 ${appState.fitBaseline.toFixed(4)}`;
    const metricsText = [
      `窗口 ${xMin.toFixed(2)}-${xMax.toFixed(2)} nm`,
      `RMS ${appState.fitWindow.rms.toFixed(3)}`,
      baselineText,
    ].join(" · ");
    ctx.fillStyle = "#27323e";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(
      truncateCanvasText(ctx, metricsText, width - pad.left - pad.right - 12),
      pad.left + 4,
      Math.max(20, pad.top - 16),
    );
    ctx.fillStyle = "#5f6a75";
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(minX.toFixed(3), pad.left, height - pad.bottom + 30);
    ctx.textAlign = "right";
    ctx.fillText(Math.max(...allPoints.map((point) => point.y)).toFixed(3), pad.left - 8, pad.top + 4);
    ctx.textAlign = "left";

    drawFitLegend(ctx, fitLegendLayout(ctx, width, height, pad, legendItems), legendItems);
    return;
  }

  const points = [];
  for (let i = 0; i < 150; i += 1) {
    const x = xMin + ((xMax - xMin) * i) / 149;
    const y = appState.fitComponents.reduce((sum, peak) => {
      const d = (x - peak.center) / peak.width;
      return sum + peak.height * Math.exp(-0.5 * d * d);
    }, 0.04);
    points.push({ x, y });
  }
  const scale = plotLine(ctx, points, pad, width, height, "#253241", 2.0);
  appState.fitComponents.forEach((component) => {
    const data = points.map((point) => {
      const d = (point.x - component.center) / component.width;
      return { x: point.x, y: component.height * Math.exp(-0.5 * d * d) + 0.04 };
    });
    plotLine(ctx, data, pad, width, height, component.color, 1.5);
  });
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = "#88414b";
  appState.fitMarkers.forEach((marker) => {
    const x = pad.left + (marker - scale.minX) * scale.xScale;
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, height - pad.bottom);
    ctx.stroke();
  });
  ctx.setLineDash([]);
  ctx.fillStyle = "#27323e";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(`窗口 ${xMin}-${xMax} nm  RMS ${appState.fitWindow.rms.toFixed(3)}`, pad.left + 4, pad.top + 14);
  appState.fitComponents.forEach((component, index) => {
    ctx.fillStyle = component.color;
    ctx.fillRect(width - pad.right - 130, pad.top + index * 18, 10, 10);
    ctx.fillStyle = "#34414d";
    ctx.fillText(`${component.label} ${component.center.toFixed(2)} nm`, width - pad.right - 114, pad.top + 9 + index * 18);
  });
}

const CONFIDENCE_REVIEW_LIMITS = {
  strong: 0.7,
  review: 0.3,
  distance: 0.3,
  r2: 0.8,
  matchedLines: 2,
  matchedRatio: 0.5,
};

function reviewBandForConfidence(confidence) {
  const value = normalizeNumber(confidence);
  if (value >= CONFIDENCE_REVIEW_LIMITS.strong) {
    return "证据较强";
  }
  if (value >= CONFIDENCE_REVIEW_LIMITS.review) {
    return "待复核";
  }
  return "证据不足";
}

function confidenceTemperatureGate(confidenceCalculation) {
  const gate = (confidenceCalculation && confidenceCalculation.temperatureGate) || {};
  const min = finiteNumberOrNull(gate.min_k ?? gate.minK);
  const max = finiteNumberOrNull(gate.max_k ?? gate.maxK);
  const hasBounds = min !== null && max !== null && max >= min;
  return {
    hasBounds,
    min,
    max,
    label: hasBounds ? `T gate ${min.toFixed(0)}-${max.toFixed(0)} K` : "T gate 未提供明确上下界",
  };
}

function confidenceTrustSummary(confidenceItem, confidenceCalculation) {
  const calculation = confidenceCalculation || { items: [] };
  const gate = confidenceTemperatureGate(calculation);
  if (!confidenceItem) {
    return {
      ion: "无",
      element: "未知",
      confidence: null,
      confidenceText: "无",
      band: "证据不足",
      distance: null,
      distanceText: "无",
      temperature: null,
      temperatureText: "无",
      r2: null,
      r2Text: "无",
      lineCount: 0,
      lineCountText: "0",
      matchedCount: 0,
      allCount: 0,
      matchedAllText: "0/0",
      matchedRatio: 0,
      representativeLabel: "无代表粒子",
      representativeSelected: false,
      gateText: gate.label,
      gateStatus: "T gate 未判断",
      reviewReasons: ["无 confidence_calculation.items"],
      reviewText: "无 confidence_calculation.items",
    };
  }

  const confidence = normalizeNumber(confidenceItem.confidence);
  const distance = normalizeNumber(confidenceItem.distance);
  const temperature = normalizeNumber(confidenceItem.temperature);
  const r2 = normalizeNumber(confidenceItem.r2);
  const lineCount = normalizeNumber(confidenceItem.lineCount);
  const allCount = confidenceItem.allTheoreticalComb.length;
  const matchedCount = confidenceItem.matchedTheoreticalComb.length;
  const matchedRatio = allCount > 0 ? matchedCount / allCount : 0;
  const representativeSelected = Boolean(confidenceItem.representativeSelection && confidenceItem.representativeSelection.selected);
  const representativeLabel =
    (confidenceItem.representativeSelection && confidenceItem.representativeSelection.label) || "未参与代表粒子选择";
  const gateStatus =
    gate.hasBounds && Number.isFinite(temperature)
      ? temperature >= gate.min && temperature <= gate.max
        ? "T gate 内"
        : "T gate 外"
      : "T gate 未判断";
  const reviewReasons = [];

  if (confidence < CONFIDENCE_REVIEW_LIMITS.strong) {
    reviewReasons.push(confidence < CONFIDENCE_REVIEW_LIMITS.review ? "置信度低" : "置信度待复核");
  }
  if (distance >= CONFIDENCE_REVIEW_LIMITS.distance) {
    reviewReasons.push("distance 偏大");
  }
  if (r2 > 0 && r2 < CONFIDENCE_REVIEW_LIMITS.r2) {
    reviewReasons.push("R2 偏低");
  }
  if (gateStatus === "T gate 外") {
    reviewReasons.push("温度不在 gate 内");
  }
  if (matchedCount < CONFIDENCE_REVIEW_LIMITS.matchedLines) {
    reviewReasons.push("匹配谱线不足");
  }
  if (allCount > 0 && matchedRatio < CONFIDENCE_REVIEW_LIMITS.matchedRatio) {
    reviewReasons.push("matched/all 比例偏低");
  }
  if (!representativeSelected) {
    reviewReasons.push("非代表粒子");
  }

  const uniqueReasons = Array.from(new Set(reviewReasons));
  return {
    ion: confidenceItem.ion,
    element: confidenceItem.element || "未知",
    confidence,
    confidenceText: confidence.toFixed(4),
    band: reviewBandForConfidence(confidence),
    distance,
    distanceText: distance.toFixed(4),
    temperature,
    temperatureText: `${temperature.toFixed(2)} K`,
    r2,
    r2Text: r2.toFixed(4),
    lineCount,
    lineCountText: String(lineCount),
    matchedCount,
    allCount,
    matchedAllText: `${matchedCount}/${allCount}`,
    matchedRatio,
    representativeLabel,
    representativeSelected,
    gateText: gate.label,
    gateStatus,
    reviewReasons: uniqueReasons,
    reviewText: uniqueReasons.length ? uniqueReasons.join("；") : "未见重点复核项",
  };
}

function sortedRareEarthResults(appState) {
  return (Array.isArray(appState.rareEarthResults) ? appState.rareEarthResults : [])
    .slice()
    .sort((left, right) => normalizeNumber(right.confidence) - normalizeNumber(left.confidence));
}

function detectedRareEarthResults(appState) {
  return sortedRareEarthResults(appState).filter((row) => row.detected);
}

function resultDecisionSummary(appState) {
  const allResults = sortedRareEarthResults(appState);
  const detected = detectedRareEarthResults(appState);
  const primary = detected[0] || allResults[0] || null;
  const primaryConfidence = primary ? normalizeNumber(primary.confidence) : 0;
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const blockedCount = appState.spectralMatches.filter((line) => line.status === "blocked").length;
  const reviewLineCount = appState.spectralMatches.filter((line) => line.status === "review").length;
  const matchedLineCount = primary ? normalizeNumber(primary.matched) : confidenceItem ? confidenceItem.matchedTheoreticalComb.length : 0;
  const reasons = [];

  if (!detected.length) {
    reasons.push("未检出候选元素");
  }
  if (primary && primaryConfidence < 0.7) {
    reasons.push(primaryConfidence < 0.3 ? "低置信" : "置信度待复核");
  }
  if (blockedCount > 0) {
    reasons.push(`基体重叠 ${blockedCount} 条`);
  }
  if (reviewLineCount > 0) {
    reasons.push(`低置信谱线 ${reviewLineCount} 条`);
  }
  if (primary && matchedLineCount > 0 && matchedLineCount < 2) {
    reasons.push("匹配谱线不足");
  }
  if (!confidenceItem) {
    reasons.push("无置信度 payload");
  }
  if (appState.fitConfidenceRescue && appState.fitConfidenceRescue.applied !== false) {
    reasons.push("多峰拟合补救");
  }
  if (appState.fitFallbackReason) {
    reasons.push("拟合后备路径");
  }

  const uniqueReasons = Array.from(new Set(reasons));
  const conclusion = detected.length
    ? detected.map((row) => `${row.name}(${normalizeNumber(row.confidence).toFixed(4)})`).join(", ")
    : "未检出候选元素";
  const primaryConfidenceText = primary
    ? `${primary.name} ${primaryConfidence.toFixed(4)}`
    : "无结果置信度";

  return {
    conclusion,
    band: reviewBandForConfidence(primaryConfidence),
    primaryConfidence,
    primaryConfidenceText,
    reviewNeeded: uniqueReasons.length > 0 || primaryConfidence < 0.7,
    reviewText: uniqueReasons.length ? uniqueReasons.join("；") : "未见重点复核项",
    exportConfirmation: "复核来源、参数和异常证据后导出",
    detected,
    primary,
    blockedCount,
    reviewLineCount,
    matchedLineCount,
  };
}

function stageExplanationRows(stageId, appState) {
  const peakCount = appState.peaks.length;
  const enabledCount = appState.spectralMatches.filter((line) => line.status === "enabled").length;
  const blockedCount = appState.spectralMatches.filter((line) => line.status === "blocked").length;
  const reviewCount = appState.spectralMatches.filter((line) => line.status === "review").length;
  const matrixText = (appState.matrixElements && appState.matrixElements.length ? appState.matrixElements : appState.baseCandidates.map((row) => row.element)).join(", ") || "无";
  const selectedStart = appState.temperatureStarts.find((start) => start.selected) || appState.temperatureStarts[0] || null;
  const selectedStartText = selectedStart
    ? `起点 #${selectedStart.startIndex + 1}，${selectedStart.initialTemperature.toFixed(0)} -> ${selectedStart.finalTemperature.toFixed(0)} K`
    : "无温度起点";
  const fitComponentCount = appState.fitComponentCurves.length || appState.fitComponents.length;
  const fitPeakCount = appState.fitFittedPeaks.length || fitComponentCount;
  const fitFallbackText = appState.fitFallbackReason ? `后备路径: ${appState.fitFallbackReason}` : "未见拟合后备路径";
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const confidenceSummary = confidenceTrustSummary(confidenceItem, appState.confidenceCalculation);
  const resultDecision = resultDecisionSummary(appState);
  const detectedNames = resultDecision.detected.length ? resultDecision.detected.map((row) => row.name).join(", ") : "无";
  const pointCount = appState.pointCount || appState.spectrum.length;
  const sourceText = appState.importedName || "未选择来源";
  const rawRangeText = "200-900 nm";
  const fitTarget = appState.fitCandidates && appState.fitCandidates[0]
    ? `${appState.fitCandidates[0].label} ${appState.fitCandidates[0].center.toFixed(4)} nm`
    : appState.fitWindow && Number.isFinite(appState.fitWindow.target)
      ? `${appState.fitWindow.target.toFixed(4)} nm`
      : "自动";

  return {
    raw: [
      ["输入", sourceText, "操作者选择的光谱文件、示例样本或实时采集光谱"],
      ["系统处理", "解析波长-强度列", "生成预览光谱和采样点统计"],
      ["输出证据", `${pointCount} 点 / ${appState.fileStatus}`, `工作范围 ${rawRangeText}`],
      ["复核风险", "文件格式 / 波长范围 / 空数据", "非光谱文本或超出工作范围需复核"],
    ],
    peak: [
      ["输入", `原始光谱 ${pointCount} 点`, sourceText],
      ["系统处理", appState.peakMethod, "生成候选峰位和强度"],
      ["输出证据", `${peakCount} 个候选峰`, peakCount ? `首峰 ${appState.peaks[0].x.toFixed(2)} nm` : "无候选峰"],
      ["复核风险", "噪声 / 基线 / 弱峰 / 峰位偏移", "弱峰漏检或伪峰需人工复核"],
    ],
    match: [
      ["输入", `${peakCount} 个候选峰 / 稀土理论线 / 基体 ${matrixText}`, `容差 ${appState.matchTolerance.toFixed(2)} nm`],
      ["系统处理", "理论线匹配实验峰", "标记 enabled / blocked / review"],
      ["输出证据", `稀土匹配 ${enabledCount} / 基体重叠 ${blockedCount} / 低置信 ${reviewCount}`, `基体候选 ${matrixText}`],
      ["复核风险", "基体重叠 / delta 偏大 / 低置信谱线", "误匹配和重叠证据需复核"],
    ],
    temperature: [
      ["输入", `匹配谱线 ${enabledCount} 条 / 起点 ${appState.temperatureStarts.length} 个`, `候选基体 ${matrixText}`],
      ["系统处理", "多起点温度迭代", "选择 best start 和 best score"],
      ["输出证据", `${appState.targetTemperature.toFixed(0)} K / 评分 ${normalizeNumber(appState.temperatureBestScore).toFixed(3)}`, selectedStartText],
      ["复核风险", "局部最优 / 温度 gate / 起点敏感 / R2 偏低", "收敛质量和候选粒子需复核"],
    ],
    fit: [
      ["输入", `拟合目标 ${fitTarget}`, `窗口 ${appState.fitWindow.left}-${appState.fitWindow.right} nm`],
      ["系统处理", "Gaussian 多峰分解", "分解稀土线与基体线重叠"],
      ["输出证据", `分量 ${fitComponentCount} / 拟合峰 ${fitPeakCount} / RMS ${appState.fitWindow.rms.toFixed(3)}`, `局部极值 ${appState.fitLocalExtrema.length}`],
      ["复核风险", `重叠峰 / 目标选择 / ${fitFallbackText}`, appState.fitConfidenceRescue ? "存在后端置信度补救证据" : "未见后端补救证据"],
    ],
    confidence: [
      ["输入", `${appState.confidenceCalculation.items.length}/${appState.confidenceCalculation.totalCount} 个 confidence items`, `${confidenceSummary.ion} / matched ${confidenceSummary.matchedAllText}`],
      ["系统处理", "distance / T gate / R2 / matched-all", "生成前端 review band"],
      ["输出证据", `${confidenceSummary.confidenceText} / ${confidenceSummary.band}`, `复核原因 ${confidenceSummary.reviewText}`],
      ["复核风险", confidenceSummary.reviewText, "低置信、distance、R2、matched/all 和代表粒子需复核"],
    ],
    result: [
      ["输入", "前序阶段证据 / 稀土结果 / 阈值", `阈值 ${appState.detectionThreshold.toFixed(2)}`],
      ["系统处理", "汇总候选结论和复核点", "不替代操作者确认"],
      ["输出证据", resultDecision.conclusion, `证据强弱 ${resultDecision.band}`],
      ["复核风险", resultDecision.reviewText, resultDecision.exportConfirmation],
    ],
  }[stageId] || [
    ["输入", "无", "未知阶段"],
    ["系统处理", "无", "未知阶段"],
    ["输出证据", "无", "未知阶段"],
    ["复核风险", "无", "未知阶段"],
  ];
}

function drawResult(canvas, appState) {
  const { ctx, width, height } = getCanvasMetrics(canvas);
  clearCanvas(ctx, width, height);
  const summary = resultDecisionSummary(appState);
  const compact = width < 620;
  const pad = { left: compact ? 34 : 48, right: 24, top: compact ? 24 : 28, bottom: 34 };
  const rows = appState.rareEarthResults;
  const cardX = pad.left;
  const cardY = pad.top;
  const cardWidth = width - pad.left - pad.right;
  const cardHeight = compact ? 124 : 116;

  ctx.fillStyle = "#f7f9fb";
  ctx.strokeStyle = "#cbd3dc";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.rect(cardX, cardY, cardWidth, cardHeight);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#66717d";
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillText("候选结论", cardX + 12, cardY + 22);
  ctx.fillStyle = "#17212b";
  ctx.font = compact ? "18px system-ui, sans-serif" : "22px system-ui, sans-serif";
  ctx.fillText(truncateCanvasText(ctx, summary.conclusion, cardWidth - 24), cardX + 12, cardY + (compact ? 48 : 52));

  const bandColor = summary.band === "证据较强" ? "#246b57" : summary.band === "待复核" ? "#875f25" : "#88414b";
  const bandX = cardX + 12;
  const bandY = cardY + (compact ? 66 : 72);
  ctx.fillStyle = bandColor;
  ctx.font = "13px system-ui, sans-serif";
  ctx.fillText(`证据强弱: ${summary.band}`, bandX, bandY);
  ctx.fillStyle = "#4d5965";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(`主置信度 ${summary.primaryConfidenceText}`, bandX, bandY + 22);
  ctx.fillText(
    truncateCanvasText(ctx, `复核点: ${summary.reviewText}`, cardWidth - 24),
    bandX,
    bandY + 42,
  );

  const plotTop = Math.min(height - 86, cardY + cardHeight + 34);
  const plotBottom = height - pad.bottom;
  const plotHeight = Math.max(54, plotBottom - plotTop);
  ctx.fillStyle = "#27323e";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText("稀土结果明细", pad.left, plotTop - 12);
  ctx.strokeStyle = "#c2c8cf";
  ctx.beginPath();
  ctx.moveTo(pad.left, plotTop);
  ctx.lineTo(pad.left, plotBottom);
  ctx.lineTo(width - pad.right, plotBottom);
  ctx.stroke();

  const availableWidth = width - pad.left - pad.right;
  const gap = rows.length > 10 ? Math.max(4, Math.min(10, availableWidth * 0.018)) : 14;
  const barWidth = Math.max(6, (availableWidth - gap * (rows.length - 1)) / Math.max(1, rows.length));
  const labelFont = barWidth < 14 ? "9px system-ui, sans-serif" : "12px system-ui, sans-serif";
  rows.forEach((row, index) => {
    const barHeight = normalizeNumber(row.confidence) * Math.max(1, plotHeight - 10);
    const x = pad.left + index * (barWidth + gap);
    const y = plotBottom - barHeight;
    ctx.fillStyle = row.detected ? "#005f8e" : "#c1c8d0";
    ctx.fillRect(x, y, barWidth, barHeight);
    ctx.fillStyle = row.detected ? "#00496d" : "#66717d";
    ctx.font = labelFont;
    ctx.textAlign = "center";
    ctx.fillText(row.name, x + barWidth / 2, height - 12);
    if (barWidth >= 10 || row.detected) {
      ctx.fillText(normalizeNumber(row.confidence).toFixed(2), x + barWidth / 2, Math.max(plotTop + 12, y - 6));
    }
  });
  ctx.textAlign = "left";
  ctx.fillStyle = "#27323e";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(`检测阈值 ${appState.detectionThreshold.toFixed(2)} · 导出前确认`, pad.left + 4, plotTop + 14);
}

const chartRenderers = {
  raw: drawRaw,
  peak: drawPeaks,
  match: drawSpectralMatch,
  temperature: drawTemperature,
  fit: drawFit,
  confidence: drawConfidenceCalculation,
  result: drawResult,
};

function stageRows(stageId, appState) {
  const peakRows = appState.peaks.slice(0, 6).map((peak, index) => [
    `候选峰 ${index + 1}`,
    `${peak.x.toFixed(2)} nm`,
    `算法标记强度 ${peak.y.toFixed(3)}`,
  ]);
  const matchRows = appState.spectralMatches.map((line) => [
    `${line.element} ${line.wl.toFixed(2)} nm`,
    spectralLineStyle(line).label,
    `${line.reason}${line.deltaNm ? ` / Δ ${line.deltaNm.toFixed(4)} nm` : ""} / ${line.status === "enabled" ? "系统证据" : "待复核"}`,
  ]);
  const temperatureRows = appState.temperatureStarts.map((start) => [
    `${start.selected ? "最优 " : ""}起点 ${start.startIndex + 1}`,
    `${start.initialTemperature.toFixed(0)} -> ${start.finalTemperature.toFixed(0)} K`,
    `${start.bestCandidate || "无"} / 评分 ${start.bestScore.toFixed(3)} / R² ${start.bestR2.toFixed(2)}`,
  ]);
  const fittedPeakRows = appState.fitFittedPeaks.map((peak, index) => [
    `拟合峰位 ${index + 1}`,
    `${peak.wavelength.toFixed(4)} nm`,
    `${peak.label}, 强度 ${peak.intensity.toFixed(4)}, sigma ${peak.sigma.toFixed(4)}`,
  ]);
  const fitCandidateRows = (appState.fitCandidates || []).map((candidate, index) => [
    `拟合候选 ${index + 1}`,
    `${candidate.center.toFixed(4)} nm`,
    `${candidate.label}${candidate.element ? ` / ${candidate.element}` : ""}, ${candidate.source}, 强度 ${candidate.lineIntensity.toFixed(4)}, ${candidate.lineType || "line"}`,
  ]);
  const extremaRows = appState.fitLocalExtrema.slice(0, 6).map((point, index) => [
    `局部极值 ${index + 1}`,
    `${point.wavelength.toFixed(4)} nm`,
    `强度 ${point.intensity.toFixed(4)}`,
  ]);
  const componentRows = appState.fitComponents.map((component, index) => [
    `拟合分量 ${index + 1}`,
    `${component.center.toFixed(2)} nm`,
    `${component.label}, sigma ${component.width.toFixed(2)}`,
  ]);
  const fitRows = fitCandidateRows.length ? [...fitCandidateRows, ...fittedPeakRows, ...extremaRows] : fittedPeakRows.length ? [...fittedPeakRows, ...extremaRows] : componentRows;
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const confidenceSummary = confidenceTrustSummary(confidenceItem, appState.confidenceCalculation);
  const confidenceRows = [
    ["粒子 / 元素", `${confidenceSummary.ion} / ${confidenceSummary.element}`, confidenceSummary.representativeSelected ? "代表粒子" : "备选或空态"],
    ["原始置信度", confidenceSummary.confidenceText, "保持后端 confidence 数值"],
    ["证据强弱", confidenceSummary.band, "前端 review band，不写回 payload"],
    ["复核原因", confidenceSummary.reviewText, "前端复核提示"],
    [
      "距离 / R2 / 温度",
      `distance ${confidenceSummary.distanceText} / R2 ${confidenceSummary.r2Text} / T ${confidenceSummary.temperatureText}`,
      `${confidenceSummary.gateText} / ${confidenceSummary.gateStatus}`,
    ],
    ["匹配谱线", confidenceSummary.matchedAllText, `lineCount ${confidenceSummary.lineCountText}`],
    ["代表选择", confidenceSummary.representativeLabel, confidenceSummary.representativeSelected ? "已选为代表" : "不是代表粒子"],
    ["公式", "exp(-4.5 * distance / R2)", "系统计算置信度"],
  ];
  if (confidenceItem) {
    confidenceRows.push(
      ["强度梳", `all ${confidenceSummary.allCount} / matched ${confidenceSummary.matchedCount}`, "理论梳、匹配理论梳、实验梳对比"],
      ["实验峰", `${confidenceItem.rawPeakMarks.selectedExperimentalPeaks.length}`, "红点筛选峰"],
    );
  }
  const resultRows = appState.rareEarthResults.map((row) => [
    `稀土明细 ${row.name}`,
    row.confidence.toFixed(4),
    row.detected ? `检出 / ${row.matched || 0} 线` : "未检出",
  ]);
  const resultDecision = resultDecisionSummary(appState);

  const detailRows = {
    raw: [
      ["采样点", String(appState.pointCount || appState.spectrum.length), "系统解析前两列数值"],
      ["解析状态", appState.fileStatus, appState.importedName],
      ["工作范围", "200-900 nm", "当前显示范围"],
    ],
    peak: peakRows,
    match: matchRows,
    temperature: temperatureRows,
    fit: fitRows,
    confidence: confidenceRows,
    result: [
      ["候选结论", resultDecision.conclusion, "系统证据生成的候选结果"],
      ["证据强弱", resultDecision.band, `主置信度 ${resultDecision.primaryConfidenceText}`],
      ["复核点", resultDecision.reviewText, resultDecision.reviewNeeded ? "导出前请确认" : "常规复核"],
      ["导出确认", resultDecision.exportConfirmation, "CSV/JSON/摘要/HTML 报告"],
      ...resultRows,
    ],
  }[stageId] || [];

  return [...stageExplanationRows(stageId, appState), ...detailRows];
}

function parameterRows(stage, appState) {
  const highBase = (appState.matrixElements && appState.matrixElements.length ? appState.matrixElements : appState.baseCandidates.map((row) => row.element)).join(", ");
  const blockedCount = appState.spectralMatches.filter((line) => line.status === "blocked").length;
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const gate = appState.confidenceCalculation.temperatureGate || {};
  return {
    raw: [
      ["工作范围", "200-900 nm"],
      ["输入格式", "CSV/TXT/TSV"],
      ["操作者来源", appState.importedName],
    ],
    peak: [
      ["算法方法", appState.peakMethod],
      ["尺度", appState.peakMethod.includes("CWT") ? "1-10" : "后备参数"],
      ["候选峰", String(appState.peaks.length)],
    ],
    match: [
      ["匹配容差", `${appState.matchTolerance.toFixed(2)} nm`],
      ["候选基体", highBase || "无"],
      ["基体重叠线", String(blockedCount)],
    ],
    temperature: [
      ["温度区间", `${normalizeNumber(appState.temperatureParameters.t_min, 5000).toFixed(0)}-${normalizeNumber(appState.temperatureParameters.t_max, 20000).toFixed(0)} K`],
      ["起点数", String(appState.temperatureStarts.length || normalizeNumber(appState.temperatureParameters.multistart_count, 1))],
      ["迭代上限", `${normalizeNumber(appState.temperatureParameters.iterations, 12)} 轮`],
      ["收敛阈值", String(appState.temperatureParameters.tolerance || "1e-5")],
      ["Top-K / 阻尼", `${normalizeNumber(appState.temperatureParameters.top_k, 3)} / ${normalizeNumber(appState.temperatureParameters.alpha, 0.35).toFixed(2)}`],
    ],
    fit: [
      ["模型", appState.fitModel],
      ["分量数", String(appState.fitComponentCurves.length || appState.fitComponents.length)],
      ["候选数", String((appState.fitCandidates || []).length)],
      ["拟合目标", appState.fitCandidates && appState.fitCandidates[0] ? appState.fitCandidates[0].source : "自动"],
      ["目标窗口", `${appState.fitWindow.left}-${appState.fitWindow.right} nm`],
    ],
    confidence: [
      ["Ion", confidenceItem ? confidenceItem.ion : "无"],
      ["公式", "exp(-4.5 * distance / R2)"],
      ["T gate", `${normalizeNumber(gate.min_k, 5000).toFixed(0)}-${normalizeNumber(gate.max_k, 20000).toFixed(0)} K`],
      ["Scope", `${appState.confidenceCalculation.scopeNm.toFixed(2)} nm`],
      ["Items", `${appState.confidenceCalculation.items.length}/${appState.confidenceCalculation.totalCount}`],
    ],
    result: [
      ["固定顺序", "15 REE"],
      ["系统输出", "confidence CSV"],
      ["阈值", appState.detectionThreshold.toFixed(2)],
    ],
  }[stage.id];
}

function resultRows(stage, appState) {
  const highBase = (appState.matrixElements && appState.matrixElements.length ? appState.matrixElements : appState.baseCandidates.map((row) => row.element)).join(", ");
  const enabledCount = appState.spectralMatches.filter((line) => line.status === "enabled").length;
  const blockedCount = appState.spectralMatches.filter((line) => line.status === "blocked").length;
  const selectedStart = appState.temperatureStarts.find((start) => start.selected) || appState.temperatureStarts[0] || { startIndex: 0, initialTemperature: 0, bestScore: 0 };
  const confidenceItem = selectedConfidenceItem(appState.confidenceCalculation);
  const confidenceSummary = confidenceTrustSummary(confidenceItem, appState.confidenceCalculation);
  return {
    raw: [["来源状态", appState.fileStatus]],
    peak: [["系统候选峰", String(appState.peaks.length)]],
    match: [
      ["高置信基体", highBase || "无"],
      ["匹配/重叠", `${enabledCount}/${blockedCount}`],
      ["复核点", blockedCount ? "存在基体重叠证据" : "未见基体重叠证据"],
    ],
    temperature: [
      ["最优起点", `#${selectedStart.startIndex + 1} / ${selectedStart.initialTemperature.toFixed(0)} K`],
      ["收敛温度", `${appState.targetTemperature.toFixed(0)} K`],
      ["最佳评分", normalizeNumber(appState.temperatureBestScore, selectedStart.bestScore).toFixed(3)],
    ],
    fit: [
      ["拟合 RMS", appState.fitWindow.rms.toFixed(3)],
      ["补救置信度", `${appState.fitBeforeConfidence.toFixed(2)} -> ${appState.fitAfterConfidence.toFixed(2)}`],
      ["基线/极值", `${appState.fitBaseline === null ? "n/a" : appState.fitBaseline.toFixed(4)} / ${appState.fitLocalExtrema.length}`],
      ["复核点", "重叠峰与低置信证据"],
    ],
    confidence: [
      ["证据强弱", confidenceSummary.band],
      ["复核原因", confidenceSummary.reviewText],
      ["原始置信度", confidenceSummary.confidenceText],
      ["支撑数值", `distance ${confidenceSummary.distanceText} · ${confidenceSummary.gateText} · T ${confidenceSummary.temperatureText} · R2 ${confidenceSummary.r2Text}`],
      ["匹配谱线", confidenceSummary.matchedAllText],
      ["代表选择", confidenceSummary.representativeLabel],
    ],
    result: (() => {
      const decision = resultDecisionSummary(appState);
      return [
        ["候选结论", decision.conclusion],
        ["证据强弱", decision.band],
        ["复核点", decision.reviewText],
        ["导出确认", decision.exportConfirmation],
        ["主置信度", decision.primaryConfidenceText],
        ["匹配/重叠", `${enabledCount}/${blockedCount}`],
      ];
    })(),
  }[stage.id];
}

function logTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function stageTitleFromId(stageId) {
  const stage = PROCESS_STAGES.find((item) => item.id === stageId);
  return stage ? stage.title : "";
}

function normalizeEvidenceLogEntry(entry, fallbackTime = "--:--:--") {
  if (typeof entry === "string") {
    return {
      time: fallbackTime,
      actor: "工作站",
      stageId: "",
      stageTitle: "日志",
      action: "记录",
      evidence: entry,
      review: "",
      text: entry,
    };
  }

  const source = entry && typeof entry === "object" ? entry : {};
  const stageId = source.stageId || "";
  const stageTitle = source.stageTitle || stageTitleFromId(stageId) || "日志";
  const text = source.text || "";
  return {
    time: source.time || fallbackTime,
    actor: source.actor || "工作站",
    stageId,
    stageTitle,
    action: source.action || "记录",
    evidence: source.evidence || text || "无",
    review: source.review || "",
    text,
  };
}

function evidenceLogText(entry) {
  const normalized = normalizeEvidenceLogEntry(entry, entry && entry.time ? entry.time : "--:--:--");
  const scope = normalized.stageTitle || normalized.stageId || "日志";
  const action = `${normalized.actor || ""}${normalized.action || ""}` || normalized.text || "记录";
  const parts = [`[${scope}] ${action}`];
  if (normalized.evidence) {
    parts.push(`证据: ${normalized.evidence}`);
  }
  if (normalized.review) {
    parts.push(`复核: ${normalized.review}`);
  }
  return parts.join("；");
}

function stageExplanationField(stageId, appState, label) {
  const row = stageExplanationRows(stageId, appState).find((item) => item[0] === label);
  if (!row) {
    return "";
  }
  return [row[1], row[2]].filter((value) => String(value || "").trim()).join(" / ");
}

function stageEvidenceLogEntry(stage, appState, action = "完成阶段", fallbackTime = logTime()) {
  const stageId = typeof stage === "string" ? stage : stage && stage.id;
  const stageTitle = (stage && stage.title) || stageTitleFromId(stageId) || "阶段";
  const isStart = String(action).includes("开始");
  return normalizeEvidenceLogEntry(
    {
      time: fallbackTime,
      actor: "系统",
      stageId,
      stageTitle,
      action,
      evidence: stageExplanationField(stageId, appState, isStart ? "输入" : "输出证据") || stageSummary(stageId, appState),
      review: stageExplanationField(stageId, appState, "复核风险") || "常规复核",
    },
    fallbackTime,
  );
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeFileStem(name) {
  return String(name || "libs-rre-result")
    .replace(/\.[^.]+$/, "")
    .replace(/[^a-zA-Z0-9_\-\u4e00-\u9fa5]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80) || "libs-rre-result";
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function reportNumber(value, digits = 4, fallback = "无") {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : fallback;
}

function reportInteger(value, fallback = "无") {
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.round(number)) : fallback;
}

function reportDateTime(value) {
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString("zh-CN", { hour12: false });
  }
  return value || "无";
}

function reportWavelengthRange(range) {
  const min = range && Number(range.minX);
  const max = range && Number(range.maxX);
  if (Number.isFinite(min) && Number.isFinite(max)) {
    return `${min.toFixed(2)} - ${max.toFixed(2)} nm`;
  }
  return "无";
}

function reportFormulaText(formula) {
  if (!formula) {
    return "无";
  }
  if (typeof formula === "string") {
    return formula;
  }
  return formula.confidence || formula.mapping || formula.distance || JSON.stringify(formula);
}

function reportStatusLabel(status) {
  return {
    enabled: "稀土匹配",
    blocked: "基体重叠",
    review: "低置信",
  }[status] || status || "未知";
}

function reportTable(headers, rows, emptyText = "无数据") {
  const headerHtml = headers.map((header) => `<th scope="col">${escapeHtml(header)}</th>`).join("");
  const bodyHtml = rows.length
    ? rows
        .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
        .join("")
    : `<tr><td colspan="${headers.length}">${escapeHtml(emptyText)}</td></tr>`;
  return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`;
}

function reportKeyValueGrid(rows) {
  return `<dl class="kv-grid">${rows
    .map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("")}</dl>`;
}

function reportDetectedRows(payload) {
  return (Array.isArray(payload.rareEarthResults) ? payload.rareEarthResults : [])
    .map((row) => ({
      element: row.element || row.name || "未知",
      detected: Boolean(row.detected),
      confidence: normalizeNumber(row.confidence),
      matched: normalizeNumber(row.matched),
      temperature: finiteNumberOrNull(row.temperature),
      r2: finiteNumberOrNull(row.r2),
    }))
    .sort((left, right) => Number(right.detected) - Number(left.detected) || right.confidence - left.confidence || left.element.localeCompare(right.element));
}

function reportConclusion(payload) {
  const detected = reportDetectedRows(payload).filter((row) => row.detected);
  if (detected.length === 0) {
    return "未检出稀土元素";
  }
  return detected.map((row) => `${row.element} (${reportNumber(row.confidence, 4)})`).join("、");
}

function reportSelectedConfidenceItem(calculation) {
  if (!calculation || !Array.isArray(calculation.items)) {
    return null;
  }
  return calculation.selectedItem || selectedConfidenceItem(calculation);
}

function reportTemperatureStartRows(payload) {
  const starts = Array.isArray(payload.temperatureStarts) ? payload.temperatureStarts : [];
  return starts.map((start) => [
    start.selected ? `#${normalizeNumber(start.startIndex) + 1} / 最优` : `#${normalizeNumber(start.startIndex) + 1}`,
    reportNumber(start.initialTemperature, 0),
    reportNumber(start.finalTemperature, 0),
    start.bestCandidate || "无",
    reportNumber(start.bestScore, 4),
    reportNumber(start.bestR2, 4),
  ]);
}

function reportFitWindow(windowValue) {
  if (!windowValue) {
    return "无";
  }
  if (Array.isArray(windowValue) && windowValue.length >= 2) {
    return `${reportNumber(windowValue[0], 4)} - ${reportNumber(windowValue[1], 4)} nm`;
  }
  return `${reportNumber(windowValue.left, 4)} - ${reportNumber(windowValue.right, 4)} nm`;
}

function reportFitRescueStatus(rescue) {
  if (!rescue) {
    return "后端未返回 confidence_rescue";
  }
  const targetElement = rescue.targetElement || rescue.target_element || "无";
  const recomputed = rescue.recomputedConfidence ?? rescue.recomputed_confidence;
  return `${rescue.applied ? "已应用" : "未应用"} / ${rescue.reason || "无原因"} / target ${targetElement} / recomputed ${reportNumber(recomputed, 4)}`;
}

function reportFitCandidateRows(fit) {
  const candidates = Array.isArray(fit && fit.candidates) ? fit.candidates : [];
  return candidates.slice(0, 12).map((candidate, index) => [
    String(index + 1),
    candidate.label || "未知",
    candidate.element || "无",
    candidate.source || "无",
    reportNumber(candidate.center, 4),
    reportNumber(candidate.lineIntensity, 4),
    candidate.lineType || "无",
  ]);
}

function reportFitComponentRows(fit) {
  const components = Array.isArray(fit && fit.components) ? fit.components : [];
  return components.slice(0, 12).map((component, index) => [
    String(index + 1),
    component.label || "未知",
    reportNumber(component.center, 4),
    reportNumber(component.height ?? component.amplitude, 4),
    reportNumber(component.width ?? component.sigma, 4),
  ]);
}

function reportSpectralEvidence(payload) {
  const matches = Array.isArray(payload.spectralMatches) ? payload.spectralMatches : [];
  const counts = matches.reduce(
    (accumulator, line) => {
      const status = line.status || "review";
      accumulator[status] = (accumulator[status] || 0) + 1;
      return accumulator;
    },
    { enabled: 0, blocked: 0, review: 0 },
  );
  const priority = { enabled: 0, blocked: 1, review: 2 };
  const rows = matches
    .slice()
    .sort(
      (left, right) =>
        (priority[left.status || "review"] ?? 3) - (priority[right.status || "review"] ?? 3) ||
        normalizeNumber(right.confidence) - normalizeNumber(left.confidence) ||
        normalizeNumber(right.expInt) - normalizeNumber(left.expInt),
    )
    .slice(0, 12)
    .map((line) => [
      line.element || "未知",
      line.baseElement || "无",
      reportStatusLabel(line.status),
      reportNumber(line.wl, 4),
      reportNumber(line.expWl, 4),
      reportNumber(line.deltaNm, 4),
      reportNumber(line.confidence, 4),
      line.reason || "无",
    ]);
  return {
    counts,
    rows,
  };
}

function reportRareEarthResultRows(payload) {
  return reportDetectedRows(payload).map((row) => [
    row.element,
    row.detected ? "检出" : "未检出",
    reportNumber(row.confidence, 4),
    reportInteger(row.matched),
    row.temperature === null ? "无" : reportNumber(row.temperature, 2),
    row.r2 === null ? "无" : reportNumber(row.r2, 4),
  ]);
}

function reportStageRows(payload) {
  const summaries = payload.stageSummaries || {};
  return PROCESS_STAGES.map((stage) => [stage.id, stage.title, summaries[stage.id] || "无"]);
}

function reportOptionalImage(chartImageDataUrl) {
  const safeImage =
    typeof chartImageDataUrl === "string" && /^data:image\/png;base64,[a-zA-Z0-9+/=]+$/.test(chartImageDataUrl)
      ? chartImageDataUrl
      : "";
  if (!safeImage) {
    return "";
  }
  return `<section class="report-section"><h2>当前视图附图</h2><figure><img src="${escapeHtml(safeImage)}" alt="导出时主画布截图"><figcaption>导出时当前主画布的可选截图。</figcaption></figure></section>`;
}

function buildHtmlReport(payload, options = {}) {
  const calculation = payload.confidenceCalculation || {};
  const confidenceItem = reportSelectedConfidenceItem(calculation);
  const fit = payload.fit || {};
  const rescue = fit.confidenceRescue || null;
  const evidence = reportSpectralEvidence(payload);
  const jsonBlock = escapeHtml(JSON.stringify(payload, null, 2));
  const reportCss = `
    :root { color-scheme: light; --ink: #17212b; --muted: #5f6b76; --line: #c7ced6; --soft: #f4f6f8; --accent: #005f8e; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #ffffff; color: var(--ink); font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.55; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 28px 44px; }
    header.report-header { border-bottom: 3px solid var(--accent); padding-bottom: 18px; margin-bottom: 22px; }
    h1 { margin: 0 0 8px; font-size: 28px; line-height: 1.18; }
    h2 { margin: 0 0 12px; font-size: 18px; color: #203040; }
    h3 { margin: 18px 0 8px; font-size: 15px; color: #203040; }
    .subtitle { margin: 0; color: var(--muted); font-weight: 700; }
    .conclusion { margin: 18px 0 0; padding: 12px 14px; border-left: 5px solid var(--accent); background: var(--soft); font-size: 18px; font-weight: 800; }
    .report-section { margin: 22px 0; break-inside: avoid; }
    .kv-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
    .kv-grid div { border: 1px solid var(--line); background: var(--soft); padding: 9px 10px; min-width: 0; }
    dt { margin: 0 0 3px; color: var(--muted); font-size: 12px; font-weight: 800; }
    dd { margin: 0; overflow-wrap: anywhere; font-weight: 750; }
    table { width: 100%; border-collapse: collapse; margin: 8px 0 0; font-size: 13px; }
    th, td { border: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
    th { background: #e9eef3; color: #203040; font-weight: 800; }
    tbody tr:nth-child(even) td { background: #fafbfc; }
    .evidence-summary { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 10px; }
    .evidence-summary span { border: 1px solid var(--line); background: var(--soft); padding: 5px 8px; font-weight: 800; }
    details { border: 1px solid var(--line); background: #fbfcfd; padding: 10px 12px; }
    summary { cursor: pointer; font-weight: 850; }
    pre { max-height: 520px; overflow: auto; margin: 12px 0 0; padding: 12px; background: #111827; color: #e5e7eb; font-size: 12px; line-height: 1.45; white-space: pre-wrap; }
    figure { margin: 0; }
    img { max-width: 100%; border: 1px solid var(--line); background: #ffffff; }
    figcaption { margin-top: 6px; color: var(--muted); font-size: 12px; }
    @media (max-width: 720px) {
      main { padding: 22px 14px 32px; }
      .kv-grid { grid-template-columns: 1fr; }
      table { font-size: 12px; }
      th, td { padding: 6px; }
    }
    @media print {
      body { background: #ffffff; }
      main { max-width: none; padding: 0; }
      .report-section { page-break-inside: avoid; }
      details { border: 0; padding: 0; }
      pre { max-height: none; color: #111827; background: #ffffff; border: 1px solid #c7ced6; }
    }
  `;

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LIBS 稀土元素检测报告 - ${escapeHtml(payload.filename || "未命名样本")}</title>
  <style>${reportCss}</style>
</head>
<body>
  <main>
    <header class="report-header">
      <h1>LIBS 稀土元素检测报告</h1>
      <p class="subtitle">单文件离线报告，可直接双击打开并通过浏览器打印为 PDF。</p>
      <p class="conclusion">最终检测结论：${escapeHtml(reportConclusion(payload))}</p>
    </header>

    <section class="report-section">
      <h2>样本与任务</h2>
      ${reportKeyValueGrid([
        ["样本名", payload.filename || "无"],
        ["导出时间", reportDateTime(payload.exportedAt)],
        ["Job ID", payload.jobId || "无"],
        ["数据来源/文件状态", payload.fileStatus || "无"],
        ["点数", reportInteger(payload.pointCount)],
        ["波长范围", reportWavelengthRange(payload.wavelengthRange)],
        ["寻峰方法", payload.peakMethod || "无"],
        ["候选峰", reportInteger(payload.peakCount)],
        ["基体元素", Array.isArray(payload.matrixElements) && payload.matrixElements.length ? payload.matrixElements.join(", ") : "无"],
      ])}
    </section>

    <section class="report-section">
      <h2>稀土结果表</h2>
      ${reportTable(["element", "detected", "confidence", "matched", "temperature", "r2"], reportRareEarthResultRows(payload))}
    </section>

    <section class="report-section">
      <h2>七阶段摘要</h2>
      ${reportTable(["stage", "title", "summary"], reportStageRows(payload))}
    </section>

    <section class="report-section">
      <h2>温度迭代摘要</h2>
      ${reportKeyValueGrid([
        ["最终温度", `${reportNumber(payload.targetTemperature, 2)} K`],
        ["最佳起点", `#${normalizeNumber(payload.bestTemperatureStartIndex) + 1}`],
        ["score", reportNumber(payload.temperatureBestScore, 4)],
      ])}
      ${reportTable(["start", "initial T(K)", "final T(K)", "best candidate", "score", "R2"], reportTemperatureStartRows(payload))}
    </section>

    <section class="report-section">
      <h2>多峰拟合摘要</h2>
      ${reportKeyValueGrid([
        ["窗口", reportFitWindow(fit.window)],
        ["RMS", reportNumber(fit.window && fit.window.rms, 6)],
        ["components/candidates", `${Array.isArray(fit.components) ? fit.components.length : 0}/${Array.isArray(fit.candidates) ? fit.candidates.length : 0}`],
        ["fallback", fit.fallbackReason || "无"],
        ["rescue", reportFitRescueStatus(rescue)],
      ])}
      <h3>candidates</h3>
      ${reportTable(["#", "label", "element", "source", "center", "line intensity", "line type"], reportFitCandidateRows(fit))}
      <h3>components</h3>
      ${reportTable(["#", "label", "center", "height/amplitude", "width/sigma"], reportFitComponentRows(fit))}
    </section>

    <section class="report-section">
      <h2>置信度计算摘要</h2>
      ${reportKeyValueGrid([
        ["代表 ion", confidenceItem ? `${confidenceItem.ion} / ${confidenceItem.element || "未知"}` : "无"],
        ["confidence", confidenceItem ? reportNumber(confidenceItem.confidence, 4) : "无"],
        ["distance", confidenceItem ? reportNumber(confidenceItem.distance, 4) : "无"],
        ["T", confidenceItem ? `${reportNumber(confidenceItem.temperature, 2)} K` : "无"],
        ["R2", confidenceItem ? reportNumber(confidenceItem.r2, 4) : "无"],
        ["matched/all", confidenceItem ? `${confidenceItem.matchedTheoreticalComb.length}/${confidenceItem.allTheoreticalComb.length}` : "无"],
        ["formula", reportFormulaText(calculation.formula)],
      ])}
    </section>

    <section class="report-section">
      <h2>谱线匹配证据摘要</h2>
      <p class="evidence-summary">
        <span>稀土匹配 ${escapeHtml(evidence.counts.enabled || 0)}</span>
        <span>基体重叠 ${escapeHtml(evidence.counts.blocked || 0)}</span>
        <span>低置信 ${escapeHtml(evidence.counts.review || 0)}</span>
      </p>
      ${reportTable(["ion", "element", "status", "theory nm", "experiment nm", "delta nm", "confidence", "reason"], evidence.rows)}
    </section>

    ${reportOptionalImage(options.chartImageDataUrl)}

    <section class="report-section">
      <h2>附录</h2>
      <details>
        <summary>完整 JSON payload</summary>
        <pre>${jsonBlock}</pre>
      </details>
    </section>
  </main>
</body>
</html>`;
}

const COMMAND_HANDLERS = {
  importFile(context) {
    context.fileInput.click();
  },
  importFolder(context) {
    if (context.folderInput) {
      context.folderInput.click();
    }
  },
  loadSampleLibrary(context) {
    context.loadSampleLibrary();
  },
  startRun(context) {
    context.startPipeline();
  },
  rerun(context) {
    context.startPipeline();
  },
  resetPipeline(context) {
    context.resetPipeline();
  },
  exportCsv(context) {
    context.exportCsv();
  },
  exportJson(context) {
    context.exportJson();
  },
  exportSummary(context) {
    context.exportSummary();
  },
  exportHtmlReport(context) {
    context.exportHtmlReport();
  },
  showStageRaw(context) {
    context.selectStage(0);
  },
  showStagePeak(context) {
    context.selectStage(1);
  },
  showStageMatch(context) {
    context.selectStage(2);
  },
  showStageTemperature(context) {
    context.selectStage(3);
  },
  showStageFit(context) {
    context.selectStage(4);
  },
  showStageConfidence(context) {
    context.selectStage(5);
  },
  showStageResult(context) {
    context.selectStage(6);
  },
  toggleInspector(context) {
    context.shell.classList.toggle("hide-inspector");
    context.pushLog(context.shell.classList.contains("hide-inspector") ? "检查器已隐藏。" : "检查器已显示。");
    context.render();
  },
  toggleLog(context) {
    context.shell.classList.toggle("hide-log");
    context.pushLog(context.shell.classList.contains("hide-log") ? "事件日志已隐藏。" : "事件日志已显示。");
    context.render();
  },
  resetView(context) {
    context.shell.classList.remove("hide-inspector", "hide-log");
    context.pushLog("视图布局已恢复。");
    context.render();
  },
};

function initApp() {
  const model = createPipelineModel();
  const appState = buildDemoState();
  Object.assign(appState, {
    importedName: "未导入文件",
    fileStatus: "请先打开光谱或文件夹",
    pointCount: 0,
    resultCsv: "",
    jobId: null,
  });
  let timer = null;
  let frame = null;
  let isRunning = false;
  let selectedFile = null;
  let importedFiles = [];
  let selectedImportedKey = "";
  let sampleLibrary = [];
  let sampleLibraryLoaded = false;
  let sampleLibraryLoading = false;
  let selectedSampleLibraryPath = "";
  let selectedFitTargetValue = "";
  let selectFitStageAfterRun = false;
  let activeSourceMode = "offline";
  let realtimeSerialState = "serial_permission_needed";
  let realtimeParameterSummary = "";
  let realtimePorts = [];
  let realtimePortsLoading = false;
  let realtimePortsMessage = "未检测到采集板端口";
  let realtimePortsError = "";
  let selectedRealtimePort = "";
  let runToken = 0;
  const logs = [
    normalizeEvidenceLogEntry(
      {
        time: "--:--:--",
        actor: "工作站",
        stageTitle: "来源",
        action: "就绪",
        evidence: "等待操作者确认来源与参数",
        review: "来源与参数",
      },
      "--:--:--",
    ),
  ];

  const shell = document.querySelector(".workstation-shell");
  const mainView = document.querySelector(".main-view");
  const sourceModeButtons = Array.from(document.querySelectorAll("[data-source-mode]"));
  const sourcePanels = Array.from(document.querySelectorAll("[data-source-panel]"));
  const sourceModeHint = document.querySelector("#source-mode-hint");
  const serialStateBadge = document.querySelector("#serial-state-badge");
  const serialStateMessage = document.querySelector("#serial-state-message");
  const serialStateOptions = Array.from(document.querySelectorAll("[data-serial-state-option]"));
  const realtimeConfirmButton = document.querySelector("[data-action='confirm-realtime-params']");
  const serialPortSelect = document.querySelector("#serial-port-select");
  const spectrometerIpInput = document.querySelector("#spectrometer-ip-input");
  const spectrometerPortInput = document.querySelector("#spectrometer-port-input");
  const realtimeConfigStatus = document.querySelector("#realtime-config-status");
  const stageItems = Array.from(document.querySelectorAll(".stage-item"));
  const stepCells = Array.from(document.querySelectorAll(".step-cell"));
  const startButton = document.querySelector("[data-action='start']");
  const resetButton = document.querySelector("[data-action='reset']");
  const importButton = document.querySelector("[data-action='import']");
  const importFolderButton = document.querySelector("[data-action='import-folder']");
  const loadSamplesButton = document.querySelector("[data-action='load-samples']");
  const exportMenu = document.querySelector("[data-export-menu]");
  const exportMenuToggle = document.querySelector("[data-action='export-menu-toggle']");
  const exportMenuList = document.querySelector(".export-menu-list");
  const outputButton = document.querySelector("[data-action='output']");
  const jsonExportButton = document.querySelector("[data-action='export-json']");
  const summaryExportButton = document.querySelector("[data-action='export-summary']");
  const reportButton = document.querySelector("[data-action='export-report']");
  const exportActionButtons = [outputButton, jsonExportButton, summaryExportButton, reportButton].filter(Boolean);
  const fileInput = document.querySelector("#spectrum-file");
  const folderInput = document.querySelector("#spectrum-folder");
  const sampleSelect = document.querySelector("#sample-select");
  const sampleLibraryRow = document.querySelector("#sample-library-row");
  const sampleLibrarySelect = document.querySelector("#sample-library-select");
  const fitTargetSelect = document.querySelector("#fit-target-select");
  const sampleName = document.querySelector("#sample-name");
  const fileStatus = document.querySelector("#file-status");
  const toolbarState = document.querySelector(".toolbar-state");
  const runState = document.querySelector("#run-state");
  const progressBar = document.querySelector("#global-progress");
  const activeStageTitle = document.querySelector("#active-stage-title");
  const stageCounter = document.querySelector("#stage-counter");
  const plotTitle = document.querySelector("#plot-title");
  const plotStatus = document.querySelector("#plot-status");
  const chartToolsDrawer = document.querySelector("#chart-tools-drawer");
  const chartZoomToolbar = document.querySelector("#chart-zoom-toolbar");
  const chartZoomControls = document.querySelector("#chart-zoom-controls");
  const chartZoomOut = document.querySelector("[data-chart-zoom-out]");
  const chartZoomIn = document.querySelector("[data-chart-zoom-in]");
  const chartZoomReset = document.querySelector("[data-chart-zoom-reset]");
  const chartZoomWidth = document.querySelector("#chart-zoom-width");
  const chartZoomWidthValue = document.querySelector("#chart-zoom-width-value");
  const chartCoordinateReadout = document.querySelector("#chart-coordinate-readout");
  const matchEvidenceKey = document.querySelector(".match-evidence-key");
  const matchEvidenceItems = Array.from(document.querySelectorAll("[data-match-evidence-status]"));
  const confidenceIonControls = document.querySelector("#confidence-ion-controls");
  const confidenceIonSelect = document.querySelector("#confidence-ion-select");
  const confidenceIonCount = document.querySelector("#confidence-ion-count");
  const mainCanvas = document.querySelector("#main-canvas");
  const tableCaption = document.querySelector("#table-caption");
  const stageDataBody = document.querySelector("#stage-data-body");
  const inspectorStage = document.querySelector("#inspector-stage");
  const inspectorState = document.querySelector("#inspector-state");
  const inspectorProgress = document.querySelector("#inspector-progress");
  const parameterList = document.querySelector("#parameter-list");
  const resultList = document.querySelector("#result-list");
  const eventLogList = document.querySelector("#event-log-list");
  let isChartPointerActive = false;

  function pushLog(entry) {
    logs.unshift(normalizeEvidenceLogEntry(entry, logTime()));
    logs.splice(8);
  }

  function replaceLogs(entryOrEntries) {
    const entries = Array.isArray(entryOrEntries) ? entryOrEntries : [entryOrEntries];
    logs.splice(0, logs.length, ...entries.map((entry) => normalizeEvidenceLogEntry(entry, logTime())));
    logs.splice(8);
  }

  function renderDefinitionList(target, rows) {
    target.innerHTML = rows
      .map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value || "无")}</dd></div>`)
      .join("");
  }

  function renderTableRows(rows) {
    stageDataBody.innerHTML = rows
      .map(([name, value, note]) => `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(value)}</td><td>${escapeHtml(note)}</td></tr>`)
      .join("");
  }

  function renderLogs() {
    eventLogList.innerHTML = logs
      .map((entry) => `<li><time>${escapeHtml(entry.time)}</time><span>${escapeHtml(evidenceLogText(entry))}</span></li>`)
      .join("");
  }

  function renderSampleSelect() {
    const rows = importedSelectRows(importedFiles);
    const renderKey = `${selectedImportedKey}|${rows.map((row) => `${row.value}:${row.label}`).join("|")}`;
    if (sampleSelect.dataset.renderKey !== renderKey) {
      sampleSelect.innerHTML = rows
        .map((row) => `<option value="${escapeHtml(row.value)}"${row.disabled ? " disabled" : ""}>${escapeHtml(row.label)}</option>`)
        .join("");
      sampleSelect.dataset.renderKey = renderKey;
    }
    sampleSelect.value = findImportedFileByKey(importedFiles, selectedImportedKey) ? selectedImportedKey : "";
    sampleSelect.disabled = isRunning || importedFiles.length === 0;
    sampleSelect.title = importedFiles.length > 0 ? "操作者已导入文件" : "请先打开光谱或文件夹";
  }

  function renderSampleLibrary() {
    if (loadSamplesButton) {
      loadSamplesButton.disabled = isRunning || sampleLibraryLoading;
      loadSamplesButton.textContent = sampleLibraryLoading ? "加载中..." : sampleLibraryLoaded ? "重新加载示例样本库" : "加载示例样本库";
    }
    if (!sampleLibraryRow || !sampleLibrarySelect) {
      return;
    }
    sampleLibraryRow.hidden = !sampleLibraryLoaded;
    if (!sampleLibraryLoaded) {
      return;
    }
    const rows = sampleLibrarySelectRows(sampleLibrary);
    const renderKey = `${selectedSampleLibraryPath}|${rows.map((row) => `${row.value}:${row.label}`).join("|")}`;
    if (sampleLibrarySelect.dataset.renderKey !== renderKey) {
      sampleLibrarySelect.innerHTML = rows
        .map((row) => `<option value="${escapeHtml(row.value)}"${row.disabled ? " disabled" : ""}>${escapeHtml(row.label)}</option>`)
        .join("");
      sampleLibrarySelect.dataset.renderKey = renderKey;
    }
    sampleLibrarySelect.value = sampleLibrary.some((sample) => sample.path === selectedSampleLibraryPath) ? selectedSampleLibraryPath : "";
    sampleLibrarySelect.disabled = isRunning || sampleLibraryLoading || sampleLibrary.length === 0;
    sampleLibrarySelect.title = "显式加载的示例样本库，不会加入已导入文件列表";
  }

  function renderRealtimePortSelect() {
    if (!serialPortSelect) {
      return;
    }

    const rows = realtimePortSelectRows({ ports: realtimePorts, loading: realtimePortsLoading, error: realtimePortsError });
    const firstEnabled = rows.find((row) => !row.disabled);
    const hasSelected = rows.some((row) => !row.disabled && row.value === selectedRealtimePort);
    selectedRealtimePort = hasSelected ? selectedRealtimePort : firstEnabled ? firstEnabled.value : "";

    const renderKey = `${selectedRealtimePort}|${isRunning}|${rows.map((row) => `${row.value}:${row.label}:${row.disabled ? "1" : "0"}`).join("|")}`;
    if (serialPortSelect.dataset.renderKey !== renderKey) {
      serialPortSelect.innerHTML = rows
        .map((row) => `<option value="${escapeHtml(row.value)}"${row.disabled ? " disabled" : ""}>${escapeHtml(row.label)}</option>`)
        .join("");
      serialPortSelect.dataset.renderKey = renderKey;
    }

    serialPortSelect.value = selectedRealtimePort;
    serialPortSelect.disabled = isRunning || !firstEnabled;
    serialPortSelect.title = realtimePortsLoading ? "正在从本地后端识别采集板端口" : realtimePortsError || realtimePortsMessage;
  }

  function hasOfflineSource() {
    if (selectedSampleLibraryPath) {
      return true;
    }
    const selectedImport = findImportedFileByKey(importedFiles, selectedImportedKey);
    return Boolean(selectedFile && !importedFileRunDisabledReason(selectedImport));
  }

  function currentRealtimeParameterInput() {
    return {
      serialPort: serialPortSelect ? serialPortSelect.value : "",
      spectrometerIp: spectrometerIpInput ? spectrometerIpInput.value : "",
      spectrometerPort: spectrometerPortInput ? spectrometerPortInput.value : "",
    };
  }

  function markRealtimeParametersDirty() {
    if (realtimeSerialState === "serial_port_detected") {
      realtimeSerialState = "serial_permission_needed";
      realtimeParameterSummary = "";
      render();
    }
  }

  function confirmRealtimeParameters() {
    const normalized = normalizeRealtimeParameters(currentRealtimeParameterInput());
    if (!normalized.ok) {
      realtimeSerialState = "serial_unavailable";
      realtimeParameterSummary = normalized.error;
      pushLog(`实时采集参数确认失败: ${normalized.error}。`);
      render();
      return;
    }

    realtimeSerialState = "serial_port_detected";
    realtimeParameterSummary = `串口 ${normalized.serialPort || "待接入"}，光谱仪 ${normalized.spectrometerIp}:${normalized.spectrometerPort}`;
    pushLog(`操作者已确认实时采集参数: ${realtimeParameterSummary}。等待采集板 bridge 或串口协议接入。`);
    render();
  }

  async function refreshRealtimePorts() {
    if (!serialPortSelect || realtimePortsLoading) {
      return;
    }

    realtimePortsLoading = true;
    realtimePortsError = "";
    realtimePortsMessage = "正在识别采集板端口...";
    render();

    try {
      const response = await fetch(resolveApiUrl("/api/realtime/ports"));
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const normalized = normalizeRealtimePorts(await response.json());
      realtimePorts = normalized.ports;
      realtimePortsMessage = normalized.message;
      if (!realtimePorts.some((port) => port.path === selectedRealtimePort)) {
        selectedRealtimePort = "";
      }
      pushLog(normalized.message);
    } catch (error) {
      realtimePorts = [];
      selectedRealtimePort = "";
      realtimePortsError = `端口识别失败: ${error.message}`;
      realtimePortsMessage = "端口识别失败";
      pushLog(realtimePortsError);
    } finally {
      realtimePortsLoading = false;
      render();
    }
  }

  function renderSourceMode() {
    sourceModeButtons.forEach((button) => {
      const mode = button.dataset.sourceMode || "offline";
      const isActive = mode === activeSourceMode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
      button.disabled = isRunning;
    });

    sourcePanels.forEach((panel) => {
      panel.hidden = panel.dataset.sourcePanel !== activeSourceMode;
    });

    if (sourceModeHint) {
      sourceModeHint.textContent = SOURCE_MODE_HINTS[activeSourceMode] || "";
    }
    if (shell) {
      shell.dataset.sourceMode = activeSourceMode;
    }

    const serialState = SERIAL_UI_STATES[realtimeSerialState] || SERIAL_UI_STATES.not_wired;
    if (serialStateBadge) {
      serialStateBadge.dataset.serialState = realtimeSerialState;
      serialStateBadge.textContent = serialState.label;
    }
    if (serialStateMessage) {
      serialStateMessage.textContent = serialState.message;
    }
    if (realtimeConfigStatus) {
      realtimeConfigStatus.dataset.serialState = realtimeSerialState;
      realtimeConfigStatus.textContent = realtimeParameterSummary || serialState.message;
    }
    if (realtimeConfirmButton) {
      realtimeConfirmButton.textContent = realtimeSerialState === "serial_port_detected" ? "已确认" : "确认";
    }
    serialStateOptions.forEach((item) => {
      item.classList.toggle("is-current", item.dataset.serialStateOption === realtimeSerialState);
    });
  }

  function renderFitTargetSelect() {
    if (!fitTargetSelect) {
      return;
    }
    const options = buildFitTargetOptions(appState, selectedFitTargetValue);
    const renderKey = `${selectedFitTargetValue}|${options.map((option) => option.value).join("|")}`;
    if (fitTargetSelect.dataset.renderKey !== renderKey) {
      fitTargetSelect.innerHTML = options
        .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
        .join("");
      fitTargetSelect.dataset.renderKey = renderKey;
    }
    fitTargetSelect.value = options.some((option) => option.value === selectedFitTargetValue) ? selectedFitTargetValue : "";
    fitTargetSelect.disabled = isRunning;
    fitTargetSelect.title = options.length > 1 ? "操作者选择拟合目标后仅重跑多峰拟合" : "运行一次后可从匹配谱线中选择拟合目标";
  }

  function setExportMenuOpen(open) {
    if (!exportMenuToggle || !exportMenuList) {
      return;
    }
    const canOpen = open && !exportMenuToggle.disabled;
    exportMenuList.hidden = !canOpen;
    exportMenuToggle.setAttribute("aria-expanded", String(canOpen));
  }

  function renderConfidenceIonControls(stageId) {
    if (!confidenceIonControls || !confidenceIonSelect) {
      return;
    }
    const isConfidenceStage = stageId === "confidence";
    confidenceIonControls.hidden = !isConfidenceStage;
    if (!isConfidenceStage) {
      return;
    }
    const calculation = appState.confidenceCalculation || { items: [] };
    const selectedItem = syncSelectedConfidenceIon(calculation, calculation.selectedIon);
    const renderKey = `${calculation.selectedIon}|${calculation.items.map((item) => `${item.ion}:${item.confidence}:${item.matchedTheoreticalComb.length}`).join("|")}`;
    if (confidenceIonSelect.dataset.renderKey !== renderKey) {
      confidenceIonSelect.innerHTML = calculation.items.length
        ? calculation.items
            .map((item) => `<option value="${escapeHtml(item.ion)}">${escapeHtml(confidenceIonOptionLabel(item))}</option>`)
            .join("")
        : '<option value="">无 confidence_calculation.items</option>';
      confidenceIonSelect.dataset.renderKey = renderKey;
    }
    confidenceIonSelect.value = selectedItem ? selectedItem.ion : "";
    confidenceIonSelect.disabled = isRunning || calculation.items.length === 0;
    if (confidenceIonCount) {
      const matchedCount = selectedItem ? selectedItem.matchedTheoreticalComb.length : 0;
      const allCount = selectedItem ? selectedItem.allTheoreticalComb.length : 0;
      confidenceIonCount.textContent = `${calculation.items.length}/${calculation.totalCount || calculation.items.length} 项 · ${matchedCount}/${allCount}`;
    }
  }

  function selectedSpectrumStageId() {
    const selectedStage = model.stages[model.selectedIndex];
    return selectedStage && isSpectrumZoomStage(selectedStage.id) ? selectedStage.id : null;
  }

  function ensureChartZoom(stageId = selectedSpectrumStageId()) {
    if (!stageId) {
      return null;
    }
    const currentZoom = appState.chartZoom && appState.chartZoom.stageId === stageId ? appState.chartZoom : createDefaultChartZoom(stageId);
    const currentWindow = resolveSpectrumChartWindow(stageId, appState, currentZoom);
    const bounds = currentWindow.bounds;
    const fullSpan = bounds.maxX - bounds.minX || 1;
    const minWidth = Math.max(1, Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan));
    const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
    const widthNm = clampNumber(normalizeNumber(currentZoom.widthNm, defaultChartZoomWidth(stageId, fullSpan)), minWidth, maxWidth);
    const centerNm =
      finiteNumberOrNull(currentZoom.centerNm) === null
        ? (currentWindow.minX + currentWindow.maxX) / 2
        : finiteNumberOrNull(currentZoom.centerNm);
    appState.chartZoom = {
      ...createDefaultChartZoom(stageId),
      ...currentZoom,
      enabled: true,
      stageId,
      centerNm,
      widthNm,
      lens: {
        ...createDefaultChartZoom(stageId).lens,
        ...(currentZoom.lens || {}),
        enabled: true,
      },
    };
    if (stageId === "match") {
      appState.matchZoom = {
        ...createDefaultMatchZoom(),
        ...appState.chartZoom,
        mode: "manual",
      };
    }
    return appState.chartZoom;
  }

  function renderChartZoomToolbar(stageId) {
    if (!chartZoomToolbar) {
      return;
    }
    const isSpectrumStage = isSpectrumZoomStage(stageId);
    const isConfidenceStage = stageId === "confidence";
    const hasChartTools = isSpectrumStage || isConfidenceStage;
    if (chartToolsDrawer) {
      chartToolsDrawer.hidden = !hasChartTools;
      if (hasChartTools) {
        chartToolsDrawer.open = window.innerWidth >= 760;
      }
    }
    chartZoomToolbar.hidden = !hasChartTools;
    if (chartZoomControls) {
      chartZoomControls.hidden = !isSpectrumStage;
    }
    if (chartCoordinateReadout) {
      chartCoordinateReadout.hidden = !isSpectrumStage;
    }
    if (matchEvidenceKey) {
      matchEvidenceKey.hidden = stageId !== "match";
    }
    renderConfidenceIonControls(stageId);
    if (!isSpectrumStage) {
      return;
    }

    const zoom = ensureChartZoom(stageId);
    const bounds = spectrumBounds(appState.spectrum);
    const fullSpan = bounds.maxX - bounds.minX || 1;
    const minWidth = Math.max(1, Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan));
    const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
    const widthValue = clampNumber(normalizeNumber(zoom.widthNm, defaultChartZoomWidth(stageId, fullSpan)), minWidth, maxWidth);
    appState.chartZoom = { ...zoom, enabled: true, widthNm: widthValue };
    if (stageId === "match") {
      appState.matchZoom = { ...createDefaultMatchZoom(), ...appState.chartZoom, mode: "manual" };
    }
    if (chartZoomWidth) {
      chartZoomWidth.min = String(Math.round(minWidth));
      chartZoomWidth.max = String(Math.round(maxWidth));
      chartZoomWidth.value = String(Math.round(widthValue));
    }
    if (chartZoomWidthValue) {
      chartZoomWidthValue.textContent = `${widthValue.toFixed(widthValue < 10 ? 1 : 0)} nm`;
    }
    if (chartCoordinateReadout) {
      const cursor =
        appState.chartCursor && appState.chartCursor.stageId === stageId
          ? appState.chartCursor
          : { wavelength: normalizeNumber(appState.chartZoom.centerNm, bounds.minX + fullSpan / 2), active: false };
      chartCoordinateReadout.textContent = `${cursor.active ? "坐标" : "中心"} ${spectrumCoordinateText(stageId, appState, cursor.wavelength)}`;
    }

    const compactEvidenceLabels = window.innerWidth < 620;
    const labels = {
      enabled: "稀土匹配",
      blocked: "基体重叠",
      review: "低置信",
    };
    const counts = appState.spectralMatches.reduce(
      (accumulator, line) => {
        const status = line.status || "review";
        accumulator[status] = (accumulator[status] || 0) + 1;
        return accumulator;
      },
      { enabled: 0, blocked: 0, review: 0 },
    );
    matchEvidenceItems.forEach((item) => {
      const status = item.dataset.matchEvidenceStatus;
      const labelTarget = item.querySelector("[data-match-evidence-label]");
      if (!labelTarget || !labels[status]) {
        return;
      }
      labelTarget.textContent = `${labels[status]} ${counts[status] || 0}${compactEvidenceLabels ? "" : "条"}`;
    });
  }

  function eventToSpectrumCoordinate(event, stageId = selectedSpectrumStageId()) {
    const rect = mainCanvas.getBoundingClientRect();
    const bounds = spectrumBounds(appState.spectrum);
    const compact = rect.width < 620;
    const leftPad = compact ? 54 : 64;
    const rightPad = compact ? 24 : 28;
    const ratio = clampNumber((event.clientX - rect.left - leftPad) / Math.max(1, rect.width - leftPad - rightPad), 0, 1);
    const wavelength = bounds.minX + (bounds.maxX - bounds.minX) * ratio;
    const point = nearestSpectrumPoint(appState.spectrum, wavelength);
    return {
      stageId,
      wavelength,
      intensity: point ? normalizeNumber(point.y) : 0,
      active: true,
    };
  }

  function updateChartZoomCenter(event) {
    const stageId = selectedSpectrumStageId();
    if (!stageId) {
      return false;
    }
    ensureChartZoom(stageId);
    const coordinate = eventToSpectrumCoordinate(event, stageId);
    appState.chartCursor = coordinate;
    appState.chartZoom.centerNm = coordinate.wavelength;
    if (stageId === "match") {
      appState.matchZoom = { ...createDefaultMatchZoom(), ...appState.chartZoom, mode: "manual" };
    }
    return true;
  }

  function scaleChartZoomWidth(multiplier, event = null) {
    const stageId = selectedSpectrumStageId();
    if (!stageId) {
      return false;
    }
    ensureChartZoom(stageId);
    if (event) {
      const coordinate = eventToSpectrumCoordinate(event, stageId);
      appState.chartCursor = coordinate;
      appState.chartZoom.centerNm = coordinate.wavelength;
    }
    const bounds = spectrumBounds(appState.spectrum);
    const fullSpan = bounds.maxX - bounds.minX || 1;
    const minWidth = Math.max(1, Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan));
    const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
    appState.chartZoom.widthNm = clampNumber(appState.chartZoom.widthNm * multiplier, minWidth, maxWidth);
    if (stageId === "match") {
      appState.matchZoom = { ...createDefaultMatchZoom(), ...appState.chartZoom, mode: "manual" };
    }
    return true;
  }

  function buildExportPayload() {
    return {
      exportedAt: new Date().toISOString(),
      jobId: appState.jobId,
      filename: appState.importedName,
      fileStatus: appState.fileStatus,
      pointCount: appState.pointCount,
      peakCount: appState.peaks.length,
      wavelengthRange: spectrumBounds(appState.spectrum),
      peakMethod: appState.peakMethod,
      matrixElements: appState.matrixElements,
      targetTemperature: appState.targetTemperature,
      temperatureBestScore: appState.temperatureBestScore,
      bestTemperatureStartIndex: appState.bestTemperatureStartIndex,
      matchParameters: appState.matchParameters,
      realMultipeakFit: appState.realMultipeakFit,
      detectionThreshold: appState.detectionThreshold,
      stageSummaries: appState.stageSummaries,
      baseCandidates: appState.baseCandidates,
      spectralMatches: appState.spectralMatches,
      confidenceCalculation: appState.confidenceCalculation,
      temperatureStarts: appState.temperatureStarts,
      temperatureIterations: appState.temperatureIterations,
      fit: {
        window: appState.fitWindow,
        beforeConfidence: appState.fitBeforeConfidence,
        afterConfidence: appState.fitAfterConfidence,
        candidates: appState.fitCandidates,
        components: appState.fitComponents,
        rawPoints: appState.fitRawPoints,
        componentCurves: appState.fitComponentCurves,
        sumFitPoints: appState.fitSumFitPoints,
        fittedPeaks: appState.fitFittedPeaks,
        localExtrema: appState.fitLocalExtrema,
        residualPoints: appState.fitResidualPoints,
        baseline: appState.fitBaseline,
        fallbackReason: appState.fitFallbackReason,
        confidenceRescue: appState.fitConfidenceRescue,
      },
      rareEarthResults: appState.rareEarthResults,
    };
  }

  function exportCsv() {
    if (!model.isComplete || isRunning) {
      return;
    }
    const csvText =
      appState.resultCsv ||
      ["element,detected,confidence", ...appState.rareEarthResults.map((row) => `${row.name},${row.detected ? 1 : 0},${row.confidence.toFixed(4)}`)].join("\n");
    downloadText("rareearth_detection_result.csv", csvText, "text/csv;charset=utf-8");
    pushLog({
      actor: "操作者",
      stageTitle: "导出",
      action: "导出 CSV",
      evidence: "rareearth_detection_result.csv",
      review: "导出前确认候选结论与复核点",
    });
    render();
  }

  function exportJson() {
    if (!model.isComplete || isRunning) {
      return;
    }
    const filename = `${safeFileStem(appState.importedName)}_pipeline_result.json`;
    downloadText(filename, `${JSON.stringify(buildExportPayload(), null, 2)}\n`, "application/json;charset=utf-8");
    pushLog({
      actor: "操作者",
      stageTitle: "导出",
      action: "导出 JSON",
      evidence: filename,
      review: "JSON 保留完整前端 payload",
    });
    render();
  }

  function exportSummary() {
    if (!model.isComplete || isRunning) {
      return;
    }
    const detected = appState.rareEarthResults.filter((row) => row.detected);
    const lines = [
      `样本: ${appState.importedName}`,
      `Job ID: ${appState.jobId || "无"}`,
      `收敛温度: ${appState.targetTemperature.toFixed(2)} K`,
      `温度最优起点: #${normalizeNumber(appState.bestTemperatureStartIndex, 0) + 1}`,
      `温度最佳评分: ${normalizeNumber(appState.temperatureBestScore).toFixed(4)}`,
      `寻峰方法: ${appState.peakMethod}`,
      `候选峰: ${appState.peaks.length}`,
      `基体元素: ${(appState.matrixElements || []).join(", ") || "无"}`,
      `检出元素: ${detected.map((row) => `${row.name}(${row.confidence.toFixed(4)})`).join(", ") || "无"}`,
      "",
      "阶段摘要:",
      ...PROCESS_STAGES.map((stage) => `- ${stage.title}: ${stageSummary(stage.id, appState)}`),
    ];
    downloadText(`${safeFileStem(appState.importedName)}_summary.txt`, `${lines.join("\n")}\n`, "text/plain;charset=utf-8");
    pushLog({
      actor: "操作者",
      stageTitle: "导出",
      action: "导出阶段摘要",
      evidence: `${safeFileStem(appState.importedName)}_summary.txt`,
      review: "摘要用于复核阶段证据",
    });
    render();
  }

  function exportHtmlReport() {
    if (!model.isComplete || isRunning) {
      pushLog({
        actor: "工作站",
        stageTitle: "导出",
        action: "阻止 HTML 报告导出",
        evidence: "检测未完成",
        review: "等待流程完成后再导出",
      });
      render();
      return;
    }
    let chartImageDataUrl = "";
    try {
      if (mainCanvas && typeof mainCanvas.toDataURL === "function") {
        chartImageDataUrl = mainCanvas.toDataURL("image/png");
      }
    } catch (error) {
      chartImageDataUrl = "";
    }
    const filename = `${safeFileStem(appState.importedName)}_detection_report.html`;
    downloadText(filename, buildHtmlReport(buildExportPayload(), { chartImageDataUrl }), "text/html;charset=utf-8");
    pushLog({
      actor: "操作者",
      stageTitle: "导出",
      action: "导出 HTML 报告",
      evidence: filename,
      review: "来源、参数和待复核证据",
    });
    render();
  }

  function commandContext() {
    return {
      shell,
      fileInput,
      folderInput,
      model,
      appState,
      render,
      pushLog,
      startPipeline,
      resetPipeline,
      loadSampleLibrary,
      exportCsv,
      exportJson,
      exportSummary,
      exportHtmlReport,
      selectStage(index) {
        model.selectStage(index);
        render();
      },
    };
  }

  function isCommandDisabled(action) {
    if (action === "importFile" || action === "importFolder" || action === "loadSampleLibrary") {
      return isRunning || activeSourceMode !== "offline";
    }
    if (action === "startRun" || action === "rerun") {
      return Boolean(sourceModeRunDisabledReason({ sourceMode: activeSourceMode, hasOfflineSource: hasOfflineSource(), isRunning }));
    }
    if (action === "exportCsv" || action === "exportJson" || action === "exportSummary" || action === "exportHtmlReport") {
      return !model.isComplete || isRunning;
    }
    return false;
  }

  function setupKeyboardShortcuts() {
    document.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        if (!isCommandDisabled("importFile")) {
          COMMAND_HANDLERS.importFile(commandContext());
        }
      }
      if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        if (!isCommandDisabled("startRun")) {
          COMMAND_HANDLERS.startRun(commandContext());
        }
      }
    });
  }

  function render() {
    const selectedStage = model.stages[model.selectedIndex];
    const activeStage = model.stages[Math.min(model.activeIndex, model.stages.length - 1)];
    const selectedIndex = model.selectedIndex;

    stageItems.forEach((item, index) => {
      const stage = model.stages[index];
      item.dataset.state = stage.state;
      item.querySelector(".stage-mark").textContent =
        stage.state === "done" ? "完成" : stage.state === "active" ? (isRunning ? "运行" : "就绪") : "等待";
      item.classList.toggle("is-selected", index === selectedIndex);
      if (index === selectedIndex) {
        item.setAttribute("aria-current", "step");
      } else {
        item.removeAttribute("aria-current");
      }
    });

    stepCells.forEach((cell, index) => {
      cell.dataset.state = model.stages[index].state;
      cell.textContent = model.stages[index].shortLabel;
      cell.classList.toggle("is-selected", index === selectedIndex);
      if (index === selectedIndex) {
        cell.setAttribute("aria-current", "step");
      } else {
        cell.removeAttribute("aria-current");
      }
    });

    activeStageTitle.textContent = selectedStage.title;
    stageCounter.textContent = `${selectedIndex + 1} / ${model.stages.length}`;
    plotTitle.textContent = selectedStage.detail;
    plotStatus.textContent = selectedStage.summary;
    renderChartZoomToolbar(selectedStage.id);
    if (mainView) {
      mainView.classList.toggle("is-confidence-view", selectedStage.id === "confidence");
    }
    mainCanvas.classList.toggle("is-chart-zooming", isSpectrumZoomStage(selectedStage.id));
    mainCanvas.classList.toggle("is-match-zooming", selectedStage.id === "match");
    mainCanvas.classList.toggle("is-confidence-chart", selectedStage.id === "confidence");
    tableCaption.textContent = selectedStage.tableCaption;
    renderTableRows(stageRows(selectedStage.id, appState));
    chartRenderers[selectedStage.id](mainCanvas, appState);

    inspectorStage.textContent = selectedStage.title;
    inspectorState.textContent =
      selectedStage.state === "done" ? "完成" : selectedStage.state === "active" ? (isRunning ? "运行中" : "就绪") : "等待";
    inspectorProgress.textContent = `${Math.round(selectedStage.progress)}%`;
    renderDefinitionList(parameterList, parameterRows(selectedStage, appState));
    renderDefinitionList(resultList, resultRows(selectedStage, appState));
    renderLogs();

    const completed = model.stages.filter((stage) => stage.state === "done").length;
    progressBar.style.width = `${(completed / model.stages.length) * 100}%`;
    sampleName.textContent = appState.importedName;
    fileStatus.textContent = appState.fileStatus || "未选择";
    renderSourceMode();
    renderRealtimePortSelect();
    renderSampleSelect();
    renderSampleLibrary();
    renderFitTargetSelect();
    runState.textContent = model.isComplete ? "待复核" : isRunning ? activeStage.title : "就绪";
    toolbarState.dataset.state = model.isComplete ? "complete" : isRunning ? "running" : "ready";
    const startDisabledReason = sourceModeRunDisabledReason({ sourceMode: activeSourceMode, hasOfflineSource: hasOfflineSource(), isRunning });
    startButton.disabled = Boolean(startDisabledReason);
    startButton.title = startDisabledReason || `开始${SOURCE_MODE_LABELS[activeSourceMode] || "分析"}`;
    importButton.disabled = isRunning || activeSourceMode !== "offline";
    if (importFolderButton) {
      importFolderButton.disabled = isRunning || activeSourceMode !== "offline";
    }
    if (loadSamplesButton) {
      loadSamplesButton.disabled = isRunning || sampleLibraryLoading || activeSourceMode !== "offline";
    }
    const exportDisabled = !model.isComplete || isRunning;
    if (exportMenuToggle) {
      exportMenuToggle.disabled = exportDisabled;
      exportMenuToggle.title = exportDisabled ? "检测完成并复核后可导出结果" : "选择导出格式";
    }
    exportActionButtons.forEach((button) => {
      button.disabled = exportDisabled;
    });
    if (reportButton) {
      reportButton.title = reportButton.disabled ? "检测完成并复核后可导出离线 HTML 报告" : "复核后导出离线 HTML 检测报告";
    }
    if (exportDisabled) {
      setExportMenuOpen(false);
    }
  }

  async function requestBackendRun() {
    if (selectedFile) {
      const selectedImport = findImportedFileByKey(importedFiles, selectedImportedKey);
      const runDisabledReason = importedFileRunDisabledReason(selectedImport);
      if (runDisabledReason) {
        throw new Error(runDisabledReason);
      }
      const body = buildUploadedFileRequestBody(selectedImport || selectedFile, selectedFitTargetValue);
      if (!body) {
        throw new Error(runDisabledReason || "请先打开光谱或文件夹");
      }
      const response = await fetch(resolveApiUrl("/api/pipeline/run"), { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `后端返回 ${response.status}`);
      }
      return payload;
    }

    const samplePayload = buildSampleLibraryRequestPayload(selectedSampleLibraryPath, selectedFitTargetValue);
    if (!samplePayload) {
      throw new Error("请先打开光谱或文件夹");
    }
    const response = await fetch(resolveApiUrl("/api/pipeline/run"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(samplePayload),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || `后端返回 ${response.status}`);
    }
    return payload;
  }

  async function requestBackendFitRun() {
    if (!appState.jobId) {
      const error = new Error("缺少可复用的后端 job_id");
      error.status = 404;
      throw error;
    }
    const fitTarget = parseFitTargetValue(selectedFitTargetValue);
    const response = await fetch(resolveApiUrl(`/api/pipeline/${encodeURIComponent(appState.jobId)}/fit`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fitTarget ? { fit_target: fitTarget } : {}),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error || `后端返回 ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function markFitOnlyRunPending() {
    model.stages.forEach((stage, index) => {
      if (index < 4) {
        stage.state = "done";
        stage.progress = 100;
      } else if (index === 4) {
        stage.state = "active";
        stage.progress = 20;
        stage.summary = "重新拟合中";
      } else {
        stage.state = "waiting";
        stage.progress = 0;
      }
    });
    model.activeIndex = 4;
    model.selectedIndex = 4;
    model.isComplete = false;
  }

  function markFitOnlyRunComplete() {
    model.stages.forEach((stage) => {
      stage.state = "done";
      stage.progress = 100;
      stage.summary = stageSummary(stage.id, appState);
    });
    model.activeIndex = model.stages.length - 1;
    model.selectedIndex = 4;
    model.isComplete = true;
  }

  function restoreCompletedModelToFitStage() {
    model.stages.forEach((stage) => {
      stage.state = "done";
      stage.progress = 100;
      stage.summary = (appState.stageSummaries && appState.stageSummaries[stage.id]) || stage.summary || "处理完成";
    });
    model.activeIndex = model.stages.length - 1;
    model.selectedIndex = 4;
    model.isComplete = true;
  }

  function startFitOnlyPipeline() {
    if (!shouldUseFitOnlyRun({ jobId: appState.jobId, isRunning, selectedValue: selectedFitTargetValue })) {
      restoreCompletedModelToFitStage();
      appState.fileStatus = "拟合失败";
      pushLog({
        actor: "工作站",
        stageId: "fit",
        action: "阻止拟合重跑",
        evidence: "缺少可复用的后端 job_id",
        review: "请先完整运行一次样本",
      });
      render();
      return;
    }

    const token = runToken + 1;
    runToken = token;
    stopRun();
    markFitOnlyRunPending();
    replaceLogs({
      actor: "操作者",
      stageId: "fit",
      action: "调整拟合目标",
      evidence: fitTargetLabel(parseFitTargetValue(selectedFitTargetValue)),
      review: "仅重跑多峰拟合，复核目标选择",
    });
    isRunning = true;
    render();

    requestBackendFitRun()
      .then((result) => {
        if (token !== runToken) {
          return;
        }
        applyPipelineResult(appState, result);
        markFitOnlyRunComplete();
        isRunning = false;
        replaceLogs({
          ...stageEvidenceLogEntry(PROCESS_STAGES[4], appState, "更新多峰拟合证据"),
          evidence: `${fitTargetLabel(parseFitTargetValue(selectedFitTargetValue))} / ${stageExplanationField("fit", appState, "输出证据")}`,
        });
        render();
      })
      .catch((error) => {
        if (token !== runToken) {
          return;
        }
        isRunning = false;
        restoreCompletedModelToFitStage();
        appState.fileStatus = "拟合失败";
        pushLog({
          actor: "系统",
          stageId: "fit",
          action: "拟合重跑失败",
          evidence: error.message,
          review: "复核拟合目标或重新运行完整流程",
        });
        render();
      });
  }

  function startPipeline() {
    const disabledReason = sourceModeRunDisabledReason({ sourceMode: activeSourceMode, hasOfflineSource: hasOfflineSource(), isRunning });
    if (disabledReason) {
      appState.fileStatus = activeSourceMode === "realtime" ? "实时采集待接入" : "请先打开光谱或文件夹";
      pushLog({
        actor: "工作站",
        stageTitle: activeSourceMode === "realtime" ? "实时采集" : "来源",
        action: "阻止提交检测任务",
        evidence: disabledReason,
        review: activeSourceMode === "realtime" ? "采集板参数确认和光谱采集" : "打开光谱或文件夹",
      });
      render();
      return;
    }
    const token = runToken + 1;
    const shouldSelectFitStage = selectFitStageAfterRun;
    selectFitStageAfterRun = false;
    runToken = token;
    stopRun();
    model.reset();
    const selectedImport = findImportedFileByKey(importedFiles, selectedImportedKey);
    const selectedSample = findSampleByPath(sampleLibrary, selectedSampleLibraryPath);
    const runLabel = selectedImport ? selectedImport.label : selectedSample ? `示例 / ${selectedSample.label}` : selectedFile.name;
    replaceLogs({
      actor: "操作者",
      stageTitle: "来源",
      action: "提交检测任务",
      evidence: `${runLabel}${selectedFitTargetValue ? ` / 拟合目标 ${fitTargetLabel(parseFitTargetValue(selectedFitTargetValue))}` : ""}`,
      review: "来源与参数",
    });
    isRunning = true;
    render();
    requestBackendRun()
      .then((result) => {
        if (token !== runToken) {
          return;
        }
        applyPipelineResult(appState, result);
        model.reset();
        if (shouldSelectFitStage) {
          model.selectStage(4);
        }
        replaceLogs({
          actor: "系统",
          stageId: "result",
          action: "返回候选结论与证据链",
          evidence: stageSummary("result", appState),
          review: resultDecisionSummary(appState).reviewText,
        });
        render();
        runCurrentStage();
      })
      .catch((error) => {
        if (token !== runToken) {
          return;
        }
        isRunning = false;
        appState.fileStatus = "后端失败";
        pushLog({
          actor: "系统",
          stageTitle: "来源",
          action: "检测失败",
          evidence: error.message,
          review: "来源和参数",
        });
        render();
      });
  }

  function resetPipeline() {
    runToken += 1;
    stopRun();
    isRunning = false;
    model.reset();
    pushLog("检测流程已停止并复位，等待操作者重新确认。");
    render();
  }

  function stopRun() {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    if (frame) {
      window.cancelAnimationFrame(frame);
      frame = null;
    }
  }

  function runCurrentStage() {
    if (model.isComplete) {
      stopRun();
      isRunning = false;
      const decision = resultDecisionSummary(appState);
      pushLog({
        actor: "系统",
        stageId: "result",
        action: "完成流程",
        evidence: decision.conclusion,
        review: decision.reviewText,
      });
      render();
      return;
    }

    const stage = model.stages[model.activeIndex];
    model.selectStage(model.activeIndex);
    pushLog(stageEvidenceLogEntry(stage, appState, "开始处理"));
    const startedAt = performance.now();

    function tick(now) {
      const progress = Math.min(100, ((now - startedAt) / stage.duration) * 100);
      model.setActiveProgress(progress);
      render();
      if (progress < 100) {
        frame = window.requestAnimationFrame(tick);
        return;
      }
      timer = window.setTimeout(() => {
        const summary = stageSummary(stage.id, appState);
        model.completeCurrentStage(summary);
        pushLog({
          ...stageEvidenceLogEntry(stage, appState, "完成阶段"),
          evidence: `${summary} / ${stageExplanationField(stage.id, appState, "输出证据")}`,
        });
        if (model.isComplete) {
          isRunning = false;
        }
        render();
        runCurrentStage();
      }, 160);
    }

    frame = window.requestAnimationFrame(tick);
  }

  async function previewImportedFile(importedFile, logPrefix) {
    Object.assign(appState, buildDemoState());
    appState.importedName = importedFile.label;
    appState.fileStatus = "待后端解析";
    appState.pointCount = 0;
    importedFile.previewStatus = "pending";
    importedFile.previewError = "";

    try {
      const text = await importedFile.file.text();
      const parsed = parseCsvSpectrum(text);
      if (parsed) {
        importedFile.previewStatus = "valid";
        importedFile.previewError = "";
        appState.spectrum = parsed.slice(0, 1200);
        appState.peaks = findDemoPeaks(appState.spectrum);
        appState.fileStatus = "已本地预览";
        appState.pointCount = parsed.length;
        pushLog(`${logPrefix}: ${importedFile.label}，开始后由系统提交后端解析。`);
      } else {
        importedFile.previewStatus = "invalid_spectrum";
        importedFile.previewError = "未找到至少 8 行波长-强度数据";
        appState.spectrum = [];
        appState.peaks = [];
        appState.fileStatus = "不是光谱数据";
        pushLog(`${logPrefix}: ${importedFile.label} 未识别为原始光谱，请选择至少 8 行波长-强度数据。`);
      }
    } catch (error) {
      importedFile.previewStatus = "read_error";
      importedFile.previewError = error && error.message ? error.message : "读取失败";
      appState.fileStatus = "本地读取失败";
      pushLog(`${logPrefix}: ${importedFile.label} 本地读取失败，未提交后端。请复核文件来源。`);
    }
  }

  async function selectImportedFile(key, logPrefix = "已选择导入文件") {
    const importedFile = findImportedFileByKey(importedFiles, key);
    if (!importedFile) {
      selectedImportedKey = "";
      selectedFile = null;
      selectedSampleLibraryPath = "";
      appState.importedName = "未导入文件";
      appState.fileStatus = "请先打开光谱或文件夹";
      render();
      return;
    }

    selectedImportedKey = importedFile.key;
    selectedFile = importedFile.file;
    selectedSampleLibraryPath = "";
    selectedFitTargetValue = "";
    isRunning = false;
    model.reset();
    await previewImportedFile(importedFile, logPrefix);
    render();
  }

  async function importFiles(fileList, sourceLabel, sourceType = "file") {
    const incoming = normalizeImportedFiles(fileList);
    if (incoming.length === 0) {
      pushLog(`未发现可用光谱文件，请选择 .asc/.csv/.txt/.tsv。`);
      render();
      return;
    }

    const existingKeys = new Set(importedFiles.map((file) => file.key));
    importedFiles = nextImportedFilesForSource(fileList, importedFiles, sourceType);
    const firstNew = importedFiles.find((file) => !existingKeys.has(file.key));
    const firstIncoming = findImportedFileByKey(importedFiles, incoming[0].key);
    const selectedImport = sourceType === "folder" ? firstIncoming || importedFiles[0] : firstNew || firstIncoming || importedFiles[0];
    await selectImportedFile(selectedImport.key, `${sourceLabel}已导入`);
  }

  function selectSampleLibraryPath(path, logPrefix = "已选择示例样本") {
    const sample = findSampleByPath(sampleLibrary, path);
    if (!sample) {
      selectedSampleLibraryPath = "";
      render();
      return;
    }

    selectedSampleLibraryPath = sample.path;
    selectedImportedKey = "";
    selectedFile = null;
    selectedFitTargetValue = "";
    isRunning = false;
    model.reset();
    Object.assign(appState, buildDemoState());
    appState.importedName = `示例 / ${sample.label}`;
    appState.fileStatus = "示例样本库";
    appState.pointCount = 0;
    appState.resultCsv = "";
    appState.jobId = null;
    pushLog(`${logPrefix}: ${sample.label}，开始后将从后端样本库运行并生成系统证据。`);
    render();
  }

  async function loadSampleLibrary() {
    if (sampleLibraryLoading) {
      return;
    }
    sampleLibraryLoading = true;
    render();
    try {
      const response = await fetch(resolveApiUrl("/api/samples"));
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || `后端返回 ${response.status}`);
      }
      sampleLibrary = normalizeSampleList(payload);
      sampleLibraryLoaded = true;
      if (sampleLibrary[0]) {
        selectSampleLibraryPath(sampleLibrary[0].path, "示例样本库已加载");
      } else {
        selectedSampleLibraryPath = "";
        pushLog("示例样本库已加载，但没有可用光谱文件。");
      }
    } catch (error) {
      sampleLibraryLoaded = true;
      sampleLibrary = [];
      selectedSampleLibraryPath = "";
      pushLog(`示例样本库加载失败: ${error.message}`);
    } finally {
      sampleLibraryLoading = false;
      render();
    }
  }

  sourceModeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextMode = button.dataset.sourceMode === "realtime" ? "realtime" : "offline";
      if (nextMode === activeSourceMode || isRunning) {
        return;
      }
      activeSourceMode = nextMode;
      pushLog(
        nextMode === "realtime"
          ? "切换到实时采集；操作者确认采集板和光谱仪参数，获得光谱数据后再分析。"
          : "切换到离线分析；操作者可导入光谱文件、文件夹或加载示例样本库。",
      );
      render();
      if (nextMode === "realtime") {
        refreshRealtimePorts();
      }
    });
  });

  stageItems.forEach((item, index) => {
    item.addEventListener("click", () => {
      model.selectStage(index);
      render();
    });
  });

  stepCells.forEach((cell, index) => {
    cell.addEventListener("click", () => {
      model.selectStage(index);
      pushLog(`查看系统证据阶段: ${model.stages[index].title}。`);
      render();
    });
  });

  if (chartZoomReset) {
    chartZoomReset.addEventListener("click", () => {
      const stageId = selectedSpectrumStageId() || "raw";
      appState.chartZoom = createDefaultChartZoom(stageId);
      if (stageId === "match") {
        appState.matchZoom = createDefaultMatchZoom();
      }
      appState.chartCursor = null;
      pushLog(`${model.stages[model.selectedIndex].title}证据视图已复位。`);
      render();
    });
  }

  if (chartZoomIn) {
    chartZoomIn.addEventListener("click", () => {
      if (!scaleChartZoomWidth(0.82)) {
        return;
      }
      render();
    });
  }

  if (chartZoomOut) {
    chartZoomOut.addEventListener("click", () => {
      if (!scaleChartZoomWidth(1.18)) {
        return;
      }
      render();
    });
  }

  if (chartZoomWidth) {
    chartZoomWidth.addEventListener("input", (event) => {
      const stageId = selectedSpectrumStageId();
      if (!stageId) {
        return;
      }
      ensureChartZoom(stageId);
      const bounds = spectrumBounds(appState.spectrum);
      const fullSpan = bounds.maxX - bounds.minX || 1;
      const minWidth = Math.max(1, Math.min(CHART_ZOOM_MIN_WIDTH_NM, fullSpan));
      const maxWidth = Math.max(minWidth, Math.min(CHART_ZOOM_MAX_WIDTH_NM, fullSpan));
      appState.chartZoom.widthNm = clampNumber(normalizeNumber(event.target.value, appState.chartZoom.widthNm), minWidth, maxWidth);
      if (stageId === "match") {
        appState.matchZoom = { ...createDefaultMatchZoom(), ...appState.chartZoom, mode: "manual" };
      }
      render();
    });
  }

  mainCanvas.addEventListener("pointerdown", (event) => {
    if (!updateChartZoomCenter(event)) {
      return;
    }
    isChartPointerActive = true;
    mainCanvas.setPointerCapture(event.pointerId);
    event.preventDefault();
    render();
  });

  mainCanvas.addEventListener("pointermove", (event) => {
    const stageId = selectedSpectrumStageId();
    if (!stageId) {
      return;
    }
    const coordinate = eventToSpectrumCoordinate(event, stageId);
    appState.chartCursor = coordinate;
    if (isChartPointerActive) {
      if (!updateChartZoomCenter(event)) {
        return;
      }
      event.preventDefault();
    }
    render();
  });

  function stopChartPointer(event) {
    if (!isChartPointerActive) {
      return;
    }
    isChartPointerActive = false;
    if (mainCanvas.hasPointerCapture(event.pointerId)) {
      mainCanvas.releasePointerCapture(event.pointerId);
    }
  }

  mainCanvas.addEventListener("pointerup", stopChartPointer);
  mainCanvas.addEventListener("pointercancel", stopChartPointer);
  mainCanvas.addEventListener(
    "wheel",
    (event) => {
      if (!scaleChartZoomWidth(event.deltaY > 0 ? 1.12 : 0.88, event)) {
        return;
      }
      event.preventDefault();
      render();
    },
    { passive: false },
  );

  startButton.addEventListener("click", startPipeline);

  resetButton.addEventListener("click", resetPipeline);

  sampleSelect.addEventListener("change", async (event) => {
    const key = event.target.value || "";
    if (!key) {
      return;
    }
    await selectImportedFile(key);
  });

  if (fitTargetSelect) {
    fitTargetSelect.addEventListener("change", (event) => {
      selectedFitTargetValue = event.target.value || "";
      const target = parseFitTargetValue(selectedFitTargetValue);
      pushLog(target ? `操作者已选择拟合目标: ${fitTargetLabel(target)}。` : "拟合目标已切回自动。");
      const options = buildFitTargetOptions(appState, selectedFitTargetValue);
      if (shouldAutoRunAfterFitTargetChange({ isRunning, hasFitOptions: options.length > 1, selectedValue: selectedFitTargetValue })) {
        startFitOnlyPipeline();
        return;
      }
      render();
    });
  }

  if (confidenceIonSelect) {
    confidenceIonSelect.addEventListener("change", (event) => {
      const selectedItem = syncSelectedConfidenceIon(appState.confidenceCalculation, event.target.value || "");
      pushLog(selectedItem ? `已切换置信度证据粒子: ${selectedItem.ion} / ${selectedItem.element || "未知"}。` : "置信度计算暂无可选粒子。");
      render();
    });
  }

  if (realtimeConfirmButton) {
    realtimeConfirmButton.addEventListener("click", confirmRealtimeParameters);
  }
  if (serialPortSelect) {
    serialPortSelect.addEventListener("change", () => {
      selectedRealtimePort = serialPortSelect.value;
      markRealtimeParametersDirty();
    });
  }
  [spectrometerIpInput, spectrometerPortInput].filter(Boolean).forEach((input) => {
    input.addEventListener("input", markRealtimeParametersDirty);
    input.addEventListener("change", markRealtimeParametersDirty);
  });

  if (exportMenuToggle) {
    exportMenuToggle.addEventListener("click", () => {
      setExportMenuOpen(exportMenuList ? exportMenuList.hidden : false);
    });
  }

  importButton.addEventListener("click", () => fileInput.click());
  if (importFolderButton && folderInput) {
    importFolderButton.addEventListener("click", () => folderInput.click());
  }
  if (loadSamplesButton) {
    loadSamplesButton.addEventListener("click", loadSampleLibrary);
  }
  if (sampleLibrarySelect) {
    sampleLibrarySelect.addEventListener("change", (event) => {
      selectSampleLibraryPath(event.target.value || "");
    });
  }
  fileInput.addEventListener("change", async (event) => {
    await importFiles(event.target.files, "光谱文件", "file");
    event.target.value = "";
  });
  if (folderInput) {
    folderInput.addEventListener("change", async (event) => {
      await importFiles(event.target.files, "文件夹", "folder");
      event.target.value = "";
    });
  }

  outputButton.addEventListener("click", () => {
    setExportMenuOpen(false);
    exportCsv();
  });
  if (jsonExportButton) {
    jsonExportButton.addEventListener("click", () => {
      setExportMenuOpen(false);
      exportJson();
    });
  }
  if (summaryExportButton) {
    summaryExportButton.addEventListener("click", () => {
      setExportMenuOpen(false);
      exportSummary();
    });
  }
  if (reportButton) {
    reportButton.addEventListener("click", () => {
      setExportMenuOpen(false);
      exportHtmlReport();
    });
  }

  document.addEventListener("pointerdown", (event) => {
    if (exportMenu && !exportMenu.contains(event.target)) {
      setExportMenuOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setExportMenuOpen(false);
    }
  });

  window.addEventListener("resize", render);
  setupKeyboardShortcuts();
  render();
  scheduleTemperatureRendererPreload();
}

function runSelfTests() {
  const assert = (condition, message) => {
    if (!condition) {
      throw new Error(message);
    }
  };

  assert(Array.isArray(PROCESS_STAGES), "PROCESS_STAGES should exist");
  assert(PROCESS_STAGES.length === 7, "pipeline should contain exactly seven stages");
  assert(
    PROCESS_STAGES.map((stage) => stage.id).join("|") === "raw|peak|match|temperature|fit|confidence|result",
    "pipeline stage ids should remain stable",
  );
  assert(
    PROCESS_STAGES.map((stage) => stage.title).join("|") === "原始光谱|寻峰结果|谱线匹配|温度迭代|多峰拟合|置信度计算|检测结果",
    "pipeline should place confidence calculation between fit and result",
  );
  assert(PROCESS_STAGES[5].id === "confidence" && PROCESS_STAGES[6].id === "result", "confidence stage should sit immediately before result");
  assert(
    PROCESS_STAGES.every((stage) => typeof chartRenderers[stage.id] === "function"),
    "every workflow stage should have a chart renderer",
  );
  const appState = buildDemoState();
  PROCESS_STAGES.forEach((stage) => {
    assert(Array.isArray(stageRows(stage.id, appState)), `${stage.id} should expose table rows`);
    assert(Array.isArray(parameterRows(stage, appState)), `${stage.id} should expose parameter rows`);
    assert(Array.isArray(resultRows(stage, appState)), `${stage.id} should expose result rows`);
  });
  const explanationLabels = "输入|系统处理|输出证据|复核风险";
  PROCESS_STAGES.forEach((stage) => {
    const rows = stageRows(stage.id, appState);
    assert(
      rows.slice(0, 4).map((row) => row[0]).join("|") === explanationLabels,
      `${stage.id} stage table should lead with input/process/output/risk explanation rows`,
    );
    assert(
      rows.slice(0, 4).every((row) => row.length === 3 && row.every((cell) => String(cell).trim())),
      `${stage.id} stage explanation rows should keep the three-column table populated`,
    );
  });
  const detailRowsAfterExplanation = (stageId) => stageRows(stageId, appState).slice(4);
  assert(detailRowsAfterExplanation("raw").some((row) => row[0] === "采样点"), "raw detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("peak").some((row) => String(row[0]).startsWith("候选峰")), "peak detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("match").some((row) => row[1] === "稀土匹配"), "match detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("temperature").some((row) => String(row[0]).includes("起点")), "temperature detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("fit").some((row) => String(row[0]).startsWith("拟合分量")), "fit detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("confidence").some((row) => row[0] === "原始置信度"), "confidence detail rows should remain after explanation rows");
  assert(detailRowsAfterExplanation("result").some((row) => row[0] === "候选结论"), "result detail rows should remain after explanation rows");
  assert(typeof normalizeEvidenceLogEntry === "function", "evidence logs should expose a normalizer");
  assert(typeof evidenceLogText === "function", "evidence logs should expose a readable text formatter");
  assert(typeof stageEvidenceLogEntry === "function", "stage evidence logs should reuse stage explanation rows");
  const legacyEvidenceLog = normalizeEvidenceLogEntry("普通文本日志", "10:00:00");
  assert(legacyEvidenceLog.time === "10:00:00" && legacyEvidenceLog.text.includes("普通文本日志"), "string logs should remain compatible");
  const structuredEvidenceLog = normalizeEvidenceLogEntry({
    time: "10:00:01",
    actor: "系统",
    stageId: "match",
    action: "完成阶段",
    evidence: "稀土匹配 3",
    review: "基体重叠",
  });
  assert(
    ["time", "actor", "stageId", "stageTitle", "action", "evidence", "review"].every((key) => Object.prototype.hasOwnProperty.call(structuredEvidenceLog, key)),
    "structured evidence logs should keep traceable fields",
  );
  const stageLog = stageEvidenceLogEntry(PROCESS_STAGES[2], appState, "完成阶段", "10:00:02");
  const matchExplanationRows = stageExplanationRows("match", appState);
  assert(stageLog.evidence.includes(matchExplanationRows.find((row) => row[0] === "输出证据")[1]), "stage completion logs should reuse output evidence from stage explanations");
  assert(stageLog.review.includes(matchExplanationRows.find((row) => row[0] === "复核风险")[1]), "stage completion logs should reuse review risk from stage explanations");
  const stageLogText = evidenceLogText(stageLog);
  assert(
    stageLogText.includes("谱线匹配") && stageLogText.includes("完成阶段") && stageLogText.includes("证据") && stageLogText.includes("复核"),
    "rendered evidence log text should include stage, action, evidence, and review",
  );
  assert(appState.spectralMatches.some((line) => line.status === "blocked"), "matching stage should expose filtered conflict lines");
  assert(spectralLineStyle({ status: "enabled" }).label === "稀土匹配", "enabled spectral lines should be shown as rare-earth matches");
  assert(spectralLineStyle({ status: "blocked" }).label === "基体重叠", "blocked spectral lines should be shown as matrix overlaps");
  assert(spectralLineStyle({ status: "review" }).label === "低置信", "review spectral lines should be shown as low-confidence evidence");
  assert(spectralLineStyle({ status: "enabled" }).color === "#006bb6", "rare-earth match color should be a distinct blue");
  assert(spectralLineStyle({ status: "blocked" }).color === "#d43d51", "matrix overlap color should be a distinct red");
  assert(spectralLineStyle({ status: "review" }).color === "#d99000", "low-confidence color should be a distinct amber");
  assert(typeof drawSpectralLegend === "function", "spectral match chart should keep a compact evidence legend helper available");
  assert(typeof compressSpectralIntensity === "function", "spectral match overview should compress intensity display to reduce empty space");
  assert(typeof createSpectralOverviewTransform === "function", "spectral match overview should adapt intensity contrast to the current spectrum");
  assert(typeof selectHighlightedSpectralMatches === "function", "spectral match chart should limit full-height emphasis to key lines");
  assert(typeof drawSpectralEvidenceTicks === "function", "spectral match chart should render dense evidence as compact ticks");
  assert(typeof normalizeConfidenceCalculation === "function", "confidence calculation payload should have a normalizer");
  assert(typeof drawConfidenceRawPeakMarks === "function", "confidence view should render raw peak mark chart");
  assert(typeof drawMatchedStickSpectrum === "function", "confidence view should render matched stick chart");
  assert(CONFIDENCE_COMB_COLORS.allTheoretical === "#8fd3f4", "all theoretical comb sticks should use light blue");
  assert(CONFIDENCE_COMB_COLORS.matchedTheoretical === "#006bb6", "matched theoretical comb sticks should use blue");
  assert(CONFIDENCE_COMB_COLORS.matchedExperimental === "#d43d51", "matched experimental comb sticks should use red");
  assert(stageRows("match", appState).some((row) => row[1] === "稀土匹配"), "match table should use the rare-earth match label");
  assert(stageRows("match", appState).some((row) => row[1] === "基体重叠"), "match table should use the matrix overlap label");
  assert(parameterRows(PROCESS_STAGES[2], appState).some((row) => row[0] === "基体重叠线"), "match parameters should name matrix overlap lines clearly");
  assert(resultRows(PROCESS_STAGES[2], appState).some((row) => row[0] === "匹配/重叠"), "match result summary should use clear match/overlap wording");
  assert(appState.temperatureIterations.length >= 3, "temperature stage should expose an iteration trace");
  assert(appState.temperatureStarts.length >= 3, "temperature stage should expose multiple starting points");
  assert(appState.temperatureStarts.some((start) => start.selected), "temperature stage should mark the globally selected start");
  assert(typeof renderTemperatureThreeScene === "function", "temperature chart should use a real Three.js scene renderer");
  assert(typeof ensureThreeJs === "function", "temperature chart should load Three.js for the 3D scene");
  assert(typeof scheduleTemperatureRendererPreload === "function", "temperature chart should preload Three.js after app initialization");
  const preloadSource = scheduleTemperatureRendererPreload.toString();
  assert(preloadSource.includes("requestIdleCallback") && preloadSource.includes("ensureThreeJs"), "temperature preload should use idle time and the normal local-first loader");
  assert(Array.isArray(TEMPERATURE_CURVE_COLORS) && TEMPERATURE_CURVE_COLORS.length >= 7, "temperature 3D chart should provide distinct curve colors");
  assert(startCurveColor(0) !== startCurveColor(1), "temperature 3D chart should color different starts differently");
  assert(temperatureColor(5000, 5000, 20000) !== temperatureColor(20000, 5000, 20000), "temperature 3D chart should color low and high temperatures differently");
  assert(temperatureStartAxisLabel({ initialTemperature: 5000 }) === "T0=5000K", "temperature start axis should show initial temperature labels");
  assert(temperatureStartTickLabel({ initialTemperature: 5000 }) === "5000", "temperature start ticks should use compact numeric labels");
  assert(temperatureIterationTicks(10).includes(0) && temperatureIterationTicks(10).includes(10), "temperature 3D chart should expose iteration ticks");
  assert(temperatureScoreTicks(0, 1).includes(0) && temperatureScoreTicks(0, 1).includes(1), "temperature 3D chart should expose score ticks");
  const denseStartVisibility = Array.from({ length: 10 }, (_, index) => shouldShowTemperatureStartLabel(index, 10, index === 2, false));
  assert(denseStartVisibility.filter(Boolean).length === 10, "start-temperature axis should show every starting-temperature tick");
  const denseStartLabelRows = new Set(
    [0, 2, 9].map((index) => temperatureStartLabelPosition(10, 5.25, index, 10, false).y.toFixed(2)),
  );
  assert(denseStartLabelRows.size === 1, "start-temperature value labels should stay on one baseline instead of using score-axis height");
  const temperatureSceneSource = renderTemperatureThreeScene.toString();
  assert(!temperatureSceneSource.includes("visibleStartLabelRank"), "temperature value labels should not be converted into a separate readout rail");
  assert(!temperatureSceneSource.includes("labelPosition.x +"), "temperature value labels should not add connector guide lines");
  assert(!temperatureSceneSource.includes("zLabel.position.set(-xSpan / 2 + (compact ? 0.9 : 1.9), -0.38"), "start-temperature axis title should be moved away from the bottom tick labels");
  const startAxisTitlePosition = temperatureStartAxisTitlePosition(10, 5.25, false);
  assert(startAxisTitlePosition.y < 0, "start-temperature axis title should sit outside the plot floor instead of floating in the middle");
  assert(startAxisTitlePosition.x < -3.5, "start-temperature axis title should stay near the start-temperature axis edge");
  assert(startAxisTitlePosition.z > 5.25 / 2, "start-temperature axis title should stay on the start-temperature side of the 3D box");
  const compactStartAxisTitlePosition = temperatureStartAxisTitlePosition(10, 5.25, true);
  assert(compactStartAxisTitlePosition.y < 0, "compact start-temperature axis title should also stay outside the plot floor");
  assert(compactStartAxisTitlePosition.x > -4, "compact start-temperature axis title should avoid clipping on the left edge");
  assert(temperatureStartLabelPosition(10, 5.25, 9, 10, true).x > -4.5, "compact start-temperature value labels should avoid clipping on the left edge");
  assert(temperatureSceneSource.includes("迭代轮次"), "temperature chart should use a Chinese iteration axis label");
  assert(temperatureSceneSource.includes("综合评分"), "temperature chart should use a Chinese score axis label");
  assert(temperatureSceneSource.includes("起点温度"), "temperature chart should use a Chinese start-temperature axis label");
  assert(temperatureFrontIterationZ(4) > 0, "temperature iteration axis should be placed on the front side of the 3D box");
  assert(temperatureSceneSource.includes("addEventListener(\"wheel\""), "temperature 3D chart should support mouse-wheel zoom");
  assert(temperatureSceneSource.includes("event.preventDefault()"), "temperature wheel zoom should prevent page scrolling while zooming");
  assert(!temperatureSceneSource.includes("Multiple Start"), "temperature chart should avoid the unclear English start axis label");
  assert(TEMPERATURE_AUTO_ROTATE === false, "temperature 3D chart should not move after calculation unless the user drags it");
  assert(Math.abs(TEMPERATURE_INITIAL_YAW) <= 0.2, "temperature 3D chart should open in a mostly front-facing view");
  assert(Math.abs(TEMPERATURE_INITIAL_PITCH) <= 0.08, "temperature 3D chart should avoid an oblique initial tilt");
  const temperatureLegendSource = createTemperatureLegendSprite.toString();
  assert(!temperatureLegendSource.includes(["dot", "=", "T"].join(" ")), "temperature legend should avoid unclear dot shorthand");
  assert(!temperatureLegendSource.includes(["curve", "=", "start"].join(" ")), "temperature legend should avoid unclear curve shorthand");
  assert(!temperatureLegendSource.includes(["start", "curves"].join(" ")), "temperature legend should not show redundant start color chips");
  const desktopLegendLayout = temperatureLegendHudLayout(800, 400, false);
  assert(desktopLegendLayout.x > 650, "temperature legend HUD should stay on the right side of the chart");
  assert(desktopLegendLayout.width >= 120 && desktopLegendLayout.height >= 220, "temperature legend should be large enough to read");
  assert(temperatureLegendSource.includes("#111827") && temperatureLegendSource.includes("700 "), "temperature legend should use bold dark labels");
  assert(temperatureSceneSource.includes("hudScene.add(colorLegend)"), "temperature legend should render in a fixed HUD layer");
  assert(temperatureSceneSource.includes("renderer.clearDepth()"), "temperature renderer should overlay the fixed HUD after the 3D scene");
  assert(!temperatureSceneSource.includes("base.add(colorLegend)"), "temperature legend should not rotate with the 3D base group");
  assert(THREE_JS_URLS[0] === "./vendor/three.min.js", "Three.js should load from the local vendor file first");
  assert(require("fs").existsSync("web_app/vendor/three.min.js"), "local Three.js vendor file should exist for offline 3D");
  assert(require("fs").statSync("web_app/vendor/three.min.js").size > 100000, "local Three.js vendor file should contain the full library");
  assert(typeof COMMAND_HANDLERS.importFile === "function", "keyboard shortcut should keep the file import command available");
  assert(typeof COMMAND_HANDLERS.startRun === "function", "keyboard shortcut should keep the run command available");
  assert(typeof normalizeSampleList === "function", "sample selector should normalize /api/samples payloads");
  const normalizedSamples = normalizeSampleList({
    samples: [
      { path: "GBW/GBW07106.csv", name: "GBW07106.csv", size: 2048 },
      { path: "RREs/070101_95.csv", name: "070101_95.csv", size: 1024 },
      { path: "RREs/070101_95.csv", name: "duplicate.csv", size: 1024 },
      { path: "", name: "bad.csv", size: 0 },
    ],
  });
  assert(normalizedSamples.length === 2, "sample selector should ignore duplicates and invalid paths");
  assert(normalizedSamples[0].label === "GBW / GBW07106.csv", "sample selector should label samples by source folder and file name");
  assert(chooseSamplePath(normalizedSamples) === DEFAULT_SAMPLE_PATH, "sample selector should prefer the known RRE default when available");
  assert(chooseSamplePath([normalizedSamples[0]], "missing.csv") === "GBW/GBW07106.csv", "sample selector should fall back to the first API sample");
  assert(typeof normalizeImportedFiles === "function", "imported file selector should expose a local file normalizer");
  assert(typeof importedSelectRows === "function", "imported file selector should render from imported files only");
  assert(typeof buildUploadedFileRequestBody === "function", "pipeline requests should build FormData from imported files");
  assert(typeof importedFileRunDisabledReason === "function", "imported text files that are not spectra should block backend submission");
  const whitespaceSpectrumText = Array.from({ length: 8 }, (_value, index) => `${200 + index} ${10 + index}`).join("\n");
  assert(parseCsvSpectrum(whitespaceSpectrumText).length === 8, "local preview parser should accept whitespace-delimited ASC/TXT spectra");
  const exportedSummaryText = [
    "样本: 03124_95_random.csv",
    "Job ID: job-test",
    "收敛温度: 11084.12 K",
    "候选峰: 80",
    "阶段摘要:",
    "- 原始光谱: 24237 个有效采样点",
  ].join("\n");
  assert(parseCsvSpectrum(exportedSummaryText) === null, "exported summary text should not be parsed as a spectrum");
  const fakeFile = (name, size = 100, relativePath = "", lastModified = 1) => ({
    name,
    size,
    webkitRelativePath: relativePath,
    lastModified,
  });
  const emptyImportedRows = importedSelectRows([]);
  assert(emptyImportedRows.length === 1, "empty imported selector should show one placeholder row");
  assert(emptyImportedRows[0].label === "未导入文件", "empty imported selector should say no files have been imported");
  assert(
    emptyImportedRows.every((row) => !String(row.label).includes("GBW") && !String(row.label).includes("RREs")),
    "initial imported selector should not contain auto-scanned sample libraries",
  );
  const normalizedImported = normalizeImportedFiles([
    fakeFile("sample-a.asc", 120, "", 10),
    fakeFile("notes.md", 12, "", 11),
    fakeFile("sample-a.asc", 120, "", 10),
    fakeFile("sample-b.csv", 140, "", 12),
    fakeFile("sample-c.tsv", 160, "folder/sample-c.tsv", 13),
    fakeFile("sample-d.txt", 180, "folder/nested/sample-d.txt", 14),
  ]);
  assert(normalizedImported.length === 4, "imported file normalizer should filter non-spectra and remove duplicates");
  assert(normalizedImported.map((file) => file.name).join("|") === "sample-a.asc|sample-b.csv|sample-c.tsv|sample-d.txt", "imported files should preserve input order");
  assert(normalizedImported[2].label === "folder/sample-c.tsv", "folder imports should use webkitRelativePath as the UI label");
  const importedRows = importedSelectRows(normalizedImported);
  assert(importedRows.length === 4, "selector rows should come only from imported files");
  assert(importedRows.every((row) => row.key && row.file), "selector rows should preserve the imported File object");
  assert(!importedRows.some((row) => row.value === DEFAULT_SAMPLE_PATH), "imported selector should not add the default sample path");
  assert(typeof nextImportedFilesForSource === "function", "import source helper should decide whether imports append or replace");
  const existingImported = normalizeImportedFiles([fakeFile("old.asc", 100, "", 20)]);
  const folderReplacement = nextImportedFilesForSource([fakeFile("folder-a.asc", 120, "batch/folder-a.asc", 21)], existingImported, "folder");
  assert(folderReplacement.length === 1 && folderReplacement[0].label === "batch/folder-a.asc", "folder imports should replace the visible imported-file list");
  const fileAppend = nextImportedFilesForSource([fakeFile("new.csv", 130, "", 22)], existingImported, "file");
  assert(fileAppend.length === 2 && fileAppend[0].name === "old.asc" && fileAppend[1].name === "new.csv", "file imports should keep existing imported files and append new ones");
  assert(typeof sampleLibrarySelectRows === "function", "sample library rows should be separate from imported-file rows");
  const sampleLibraryRows = sampleLibrarySelectRows(normalizedSamples);
  assert(sampleLibraryRows.length === normalizedSamples.length + 1, "sample library selector should include one placeholder plus explicit /api/samples payloads");
  assert(sampleLibraryRows[0].label === "选择示例样本", "sample library selector should make the sample-source choice explicit");
  assert(importedSelectRows(normalizedImported).every((row) => !sampleLibraryRows.some((sample) => sample.value === row.value)), "sample library rows must not be mixed into the imported-file selector");
  const sampleLibraryPayload = buildSampleLibraryRequestPayload("RREs/070101_95.csv", "");
  assert(sampleLibraryPayload.sample_path === "RREs/070101_95.csv", "selected sample-library rows should run through the explicit sample_path request payload");
  class FakeFormData {
    constructor() {
      this.entries = [];
    }
    append(key, value) {
      this.entries.push([key, value]);
    }
    get(key) {
      const found = this.entries.find((entry) => entry[0] === key);
      return found ? found[1] : null;
    }
    has(key) {
      return this.entries.some((entry) => entry[0] === key);
    }
  }
  const requestBody = buildUploadedFileRequestBody(normalizedImported[0].file, "", FakeFormData);
  assert(requestBody.get("file") === normalizedImported[0].file, "imported file requests should upload the selected File object");
  assert(!requestBody.has("sample_path"), "imported file requests should not fall back to sample_path");
  const invalidImportedRow = { ...normalizedImported[3], previewStatus: "invalid_spectrum" };
  assert(importedFileRunDisabledReason(invalidImportedRow) === "请选择原始光谱文件", "invalid imported text should not be submitted to the backend");
  assert(buildUploadedFileRequestBody(invalidImportedRow, "", FakeFormData) === null, "invalid imported rows should not build a backend FormData request");
  assert(
    PROCESS_STAGES.every((stage) => stage.shortLabel && stage.shortLabel !== stage.id),
    "stage strip should expose concrete stage labels instead of numeric placeholders",
  );
  assert(
    resolveApiUrl("/api/pipeline/run", { protocol: "file:", hostname: "", port: "" }) === "http://127.0.0.1:5000/api/pipeline/run",
    "file pages should call the local Flask backend explicitly",
  );
  assert(
    resolveApiUrl("/api/pipeline/run", { protocol: "http:", hostname: "127.0.0.1", port: "5000" }) === "/api/pipeline/run",
    "Flask-served pages should keep same-origin API calls",
  );
  assert(
    resolveApiUrl("/api/pipeline/run", { protocol: "http:", hostname: "8.134.144.84", port: "" }) === "/api/pipeline/run",
    "deployed HTTP pages should call the same-origin Nginx proxy",
  );
  assert(
    resolveApiUrl("/api/pipeline/run", { protocol: "https:", hostname: "example.com", port: "" }) === "/api/pipeline/run",
    "deployed HTTPS pages should call the same-origin proxy",
  );

  const model = createPipelineModel();
  assert(model.stages[0].state === "active", "first stage should start active");
  assert(model.stages.slice(1).every((stage) => stage.state === "waiting"), "remaining stages should wait");
  assert(model.selectedIndex === 0, "selected stage should start at first stage");

  model.completeCurrentStage();
  assert(model.stages[0].state === "done", "completed stage should be marked done");
  assert(model.stages[1].state === "active", "next stage should become active");
  assert(model.selectedIndex === 1, "selected stage should follow active stage after completion");

  model.selectStage(0);
  assert(model.selectedIndex === 0, "operator can review a completed/earlier stage");

  model.completeCurrentStage();
  assert(model.stages[2].state === "active", "pipeline should advance one stage at a time");

  const backendResult = {
    job_id: "job-test",
    filename: "070101_95.csv",
    result_csv: "element,detected,confidence\nYb,1,0.2703\n",
    stages: [
      {
        id: "raw",
        summary: "3 个有效采样点",
        data: {
          filename: "070101_95.csv",
          point_count: 3,
          x_min: 270,
          x_max: 276,
          preview: [
            { x: 270, y: 0.1 },
            { x: 273, y: 0.4 },
            { x: 276, y: 0.2 },
          ],
        },
      },
      {
        id: "peak",
        summary: "检测到 1 个候选峰",
        data: { peak_count: 1, peaks: [{ wavelength: 274.895, intensity: 0.82 }] },
        parameters: { method: "CWT ridge peak detection" },
      },
      {
        id: "match",
        summary: "1 条稀土谱线匹配",
        data: {
          base_candidates: [{ element: "Mn", confidence: 0.42, matched: 3, temperature: 9600, r2: 0.91 }],
          matrix_elements: ["Mn"],
          confidence_calculation: {
            formula: {
              confidence: "exp(-4.5 * distance / max(R2, 1e-9))",
            },
            temperature_gate: { min_k: 5000, max_k: 20000 },
            scope_nm: 0.2,
            total_count: 1,
            omitted_count: 0,
            items: [
              {
                element: "Yb",
                ion: "YbII",
                confidence: 0.0779,
                distance: 0.4341,
                temperature: 15427.11,
                r2: 0.7655,
                line_count: 5,
                all_theoretical_comb: [
                  { wavelength: 265.375, intensity: 0.0589, normalized_intensity: 0.0589, A: 3.9, E: 7.326, g: 8, status: "review" },
                  { wavelength: 275.0477, intensity: 0.07, normalized_intensity: 0.07, A: 1.2, E: 7.1, g: 6, status: "enabled" },
                ],
                matched_theoretical_comb: [
                  { wavelength: 275.0477, intensity: 0.07, normalized_intensity: 1, matched_idx: 1 },
                ],
                matched_experimental_comb: [
                  { wavelength: 274.895, intensity: 0.0329, normalized_intensity: 1, delta_nm: 0.1527, theoretical_wavelength: 275.0477 },
                ],
                raw_peak_marks: {
                  theoretical_wavelengths: [
                    { wavelength: 265.375, normalized_intensity: 0.0589, status: "review", matched: false },
                    { wavelength: 275.0477, normalized_intensity: 0.07, status: "enabled", matched: true },
                  ],
                  selected_experimental_peaks: [
                    { wavelength: 274.895, intensity: 0.0329, theoretical_wavelength: 275.0477, delta_nm: 0.1527 },
                  ],
                },
                normalization: {
                  all_theoretical: { sum: 1 },
                  matched_theoretical: { sum: 0.07 },
                  matched_experimental: { sum: 0.0329 },
                },
                representative_selection: {
                  selected: true,
                  valid_temperature: true,
                  best_r2: true,
                  reason: "valid_temperature_best_r2",
                },
              },
            ],
          },
          spectral_matches: [
            {
              element: "Yb",
              ion: "YbII",
              wavelength: 274.895,
              status: "enabled",
              delta_nm: 0,
              matched_peak: { wavelength: 274.895, intensity: 0.82 },
              reason: "Rareearth_pt3 谱线库 + 匈牙利匹配",
            },
          ],
        },
        parameters: { match_tolerance_nm: 0.2 },
      },
      {
        id: "temperature",
        summary: "10390 K / 评分 0.389",
        data: {
          temperature: 10390.37,
          best_start_index: 1,
          best_score: 0.3885,
          trace: [{ iteration: 0, temperature: 10390.37, target_temperature: 11115.37, candidate: "Mn", confidence: 0.42, r2: 0.91, score: 0.3885, delta: 390.37 }],
          starts: [
            {
              start_index: 0,
              initial_temperature: 5000,
              final_temperature: 8870.22,
              best_score: 0.255,
              best_candidate: "Fe",
              best_confidence: 0.31,
              best_r2: 0.84,
              selected: false,
              trace: [{ iteration: 0, temperature: 8870.22, target_temperature: 16058.11, candidate: "Fe", confidence: 0.31, r2: 0.84, score: 0.254, delta: 3870.22 }],
            },
            {
              start_index: 1,
              initial_temperature: 10000,
              final_temperature: 10390.37,
              best_score: 0.3885,
              best_candidate: "Mn",
              best_confidence: 0.42,
              best_r2: 0.91,
              selected: true,
              trace: [{ iteration: 0, temperature: 10390.37, target_temperature: 11115.37, candidate: "Mn", confidence: 0.42, r2: 0.91, score: 0.3885, delta: 390.37 }],
            },
          ],
        },
        parameters: { t_min: 5000, t_max: 20000, multistart_count: 2, iterations: 10, top_k: 3, alpha: 0.35 },
      },
      {
        id: "fit",
        summary: "已执行局部 Gaussian 多峰拟合",
        data: {
          target: "YbII",
          target_element: "Yb",
          window_nm: [273.995, 275.795],
          fit_candidates: [
            {
              source: "normalized_pure_element",
              element: "Yb",
              label: "YbII",
              center: 274.895,
              line_intensity: 0.069972,
              line_type: "Rareearth_pt3 relative intensity",
              rank: 0,
            },
            {
              source: "matrix",
              element: "Mn",
              label: "MnII",
              center: 275.0125,
              line_intensity: 608.3,
              line_type: "Mn II (8.9e-1)",
              rank: 1,
            },
            {
              source: "matrix",
              element: "Mn",
              label: "MnII",
              center: 274.8702,
              line_intensity: 135.1,
              line_type: "Mn II (8.9e-1)",
              rank: 2,
            },
          ],
          components: [
            { source: "normalized_pure_element", element: "Yb", label: "YbII", center: 274.895, amplitude: 0.0182, sigma: 0.1425, rank: 0 },
            { source: "matrix", element: "Mn", label: "MnII", center: 275.0125, amplitude: 0.0113, sigma: 0.08, rank: 1 },
            { source: "matrix", element: "Mn", label: "MnII", center: 274.8702, amplitude: 0.0097, sigma: 0.08, rank: 2 },
          ],
          raw_points: [{ x: 273.995, y: 0.015 }, { x: 274.895, y: 0.034 }, { x: 275.795, y: 0.014 }],
          component_curves: [
            {
              label: "YbII",
              center: 274.895,
              amplitude: 0.0182,
              sigma: 0.1425,
              points: [{ x: 273.995, y: 0.0001 }, { x: 274.895, y: 0.0182 }, { x: 275.795, y: 0.0001 }],
            },
            {
              label: "MnII",
              center: 275.0125,
              amplitude: 0.0113,
              sigma: 0.08,
              points: [{ x: 273.995, y: 0.0001 }, { x: 274.895, y: 0.0065 }, { x: 275.795, y: 0.0001 }],
            },
            {
              label: "MnII",
              center: 274.8702,
              amplitude: 0.0097,
              sigma: 0.08,
              points: [{ x: 273.995, y: 0.0002 }, { x: 274.895, y: 0.0092 }, { x: 275.795, y: 0.0001 }],
            },
          ],
          sum_fit_points: [{ x: 273.995, y: 0.0158 }, { x: 274.895, y: 0.0339 }, { x: 275.795, y: 0.0158 }],
          fitted_peaks: [
            { label: "YbII", wavelength: 274.895, intensity: 0.0339, amplitude: 0.0182, sigma: 0.1425 },
            { label: "MnII", wavelength: 275.0125, intensity: 0.027, amplitude: 0.0113, sigma: 0.08 },
            { label: "MnII", wavelength: 274.8702, intensity: 0.0254, amplitude: 0.0097, sigma: 0.08 },
          ],
          local_extrema: [{ wavelength: 274.895, intensity: 0.034 }],
          residual_points: [{ x: 273.995, y: -0.0008 }, { x: 274.895, y: 0.0001 }, { x: 275.795, y: -0.0018 }],
          baseline: 0.0157,
          component_count: 3,
          fallback_reason: null,
          rms: 0.00434,
          before_confidence: 0.0772,
          after_confidence: 0.2703,
          real_multipeak_fit: true,
          confidence_rescue: {
            applied: true,
            reason: "fitted_peak_append_recompute",
            target_element: "Yb",
            base_confidence: 0.0772,
            recomputed_confidence: 0.2703,
            appended_peak_count: 1,
            appended_peaks: [{ label: "YbII", wavelength: 274.895, intensity: 0.0339, amplitude: 0.0182, sigma: 0.1425 }],
          },
        },
      },
      {
        id: "result",
        summary: "Yb",
        data: { detection_threshold: 0.05, rare_earth_results: [{ element: "Yb", detected: true, confidence: 0.2703, matched: 1 }] },
      },
    ],
  };
  const normalized = normalizeBackendResult(backendResult);
  assert(normalized.jobId === "job-test", "backend result should preserve job id");
  assert(normalized.resultCsv.includes("Yb,1,0.2703"), "backend result should preserve csv");
  assert(normalized.spectrum.length === 3, "backend preview should become drawable spectrum data");
  assert(normalized.peaks[0].x === 274.895, "backend peak wavelength should map to x");
  assert(normalized.spectralMatches[0].element === "YbII", "backend ion should drive match label");
  assert(normalized.confidenceCalculation.items.length === 1, "backend confidence calculation items should be normalized");
  assert(normalized.confidenceCalculation.selectedItem.ion === "YbII", "confidence view should default to the highest matched item");
  assert(normalized.confidenceCalculation.selectedItem.matchedTheoreticalComb.length === normalized.confidenceCalculation.selectedItem.matchedExperimentalComb.length, "matched comb arrays should stay paired");
  assert(stageRows("confidence", normalized).some((row) => row[0] === "原始置信度"), "confidence stage table should expose confidence calculation breakdown");
  const confidenceStageRows = stageRows("confidence", normalized);
  assert(
    confidenceStageRows.slice(0, 4).map((row) => row[0]).join("|") === explanationLabels,
    "confidence stage should include input/process/output/risk before trust evidence details",
  );
  const confidenceDetailRows = confidenceStageRows.slice(4);
  const confidenceStageLabels = confidenceDetailRows.slice(0, 7).map((row) => row[0]).join("|");
  assert(
    confidenceStageLabels === "粒子 / 元素|原始置信度|证据强弱|复核原因|距离 / R2 / 温度|匹配谱线|代表选择",
    "confidence stage table should lead with trust evidence fields in review order",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[1]).includes("0.0779")),
    "confidence stage table should preserve the raw confidence value",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[0]).includes("证据强弱") && String(row[1]).includes("证据不足")),
    "confidence stage table should expose the frontend review band",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[0]).includes("复核原因") && String(row[1]).includes("置信度低")),
    "confidence stage table should expose review reasons from existing confidence evidence",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[0]).includes("距离") && String(row[1]).includes("0.4341") && String(row[1]).includes("0.7655") && String(row[1]).includes("15427.11")),
    "confidence stage table should expose distance, R2, and temperature support values",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[0]).includes("匹配谱线") && String(row[1]).includes("1/2")),
    "confidence stage table should expose matched/all line counts",
  );
  assert(
    confidenceDetailRows.some((row) => String(row[0]).includes("代表选择") && String(row[1]).includes("T 门内")),
    "confidence stage table should expose representative selection reason",
  );
  const confidenceInspectorRows = resultRows(PROCESS_STAGES[5], normalized);
  assert(
    confidenceInspectorRows.slice(0, 4).map((row) => row[0]).join("|") === "证据强弱|复核原因|原始置信度|支撑数值",
    "confidence inspector should lead with review band, review reasons, raw confidence, and supporting values",
  );
  assert(
    confidenceInspectorRows.some((row) => String(row[0]).includes("支撑数值") && String(row[1]).includes("distance") && String(row[1]).includes("T gate") && String(row[1]).includes("R2")),
    "confidence inspector should keep distance, T gate, and R2 visible",
  );
  assert(!stageRows("match", normalized).some((row) => row[0] === "置信度"), "match stage should keep confidence rows in the dedicated stage");
  const emptyConfidenceNormalized = normalizeBackendResult({ stages: [], result_csv: "" });
  assert(emptyConfidenceNormalized.confidenceCalculation.items.length === 0, "empty confidence payload should normalize to an empty item list");
  assert(normalized.temperatureStarts.length === 2, "backend multistart temperature data should be preserved");
  assert(normalized.bestTemperatureStartIndex === 1, "backend selected temperature start should be preserved");
  assert(normalized.temperatureBestScore === 0.3885, "backend best temperature score should be preserved");
  assert(normalized.temperatureIterations[0].score === 0.3885, "selected start trace should drive temperature iterations");
  assert(normalized.fitRawPoints.length === 3, "backend raw fit points should be preserved");
  assert(normalized.fitCandidates.length === 3, "backend fit candidates should be preserved");
  assert(normalized.fitCandidates[0].source === "normalized_pure_element", "target candidate should preserve normalized_pure_element source");
  assert(normalized.fitCandidates.slice(1).every((row) => row.source === "matrix"), "matrix fit candidates should preserve matrix source");
  assert(normalized.fitComponentCurves.length === 3, "backend component curves should preserve all candidate-aligned curves");
  assert(normalized.fitSumFitPoints.length === 3, "backend sum fit points should be preserved");
  assert(normalized.fitFittedPeaks[0].wavelength === 274.895, "backend fitted peak marker should be preserved");
  assert(normalized.fitLocalExtrema.length === 1, "backend local extrema should be preserved");
  assert(normalized.fitBaseline === 0.0157, "backend fit baseline should be preserved");
  assert(normalized.fitConfidenceRescue && normalized.fitConfidenceRescue.reason === "fitted_peak_append_recompute", "fit confidence rescue should come from backend payload");
  assert(normalized.fitConfidenceRescue.recomputedConfidence === 0.2703, "fit confidence rescue should preserve backend recomputed confidence");
  assert(normalized.rareEarthResults[0].name === "Yb", "backend result element should map to display name");
  const rareEarthFixtureNames = ["La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Y"];
  const decisionResultState = {
    ...normalized,
    rareEarthResults: rareEarthFixtureNames.map((name) => ({
      name,
      detected: name === "Yb",
      confidence: name === "Yb" ? 0.2703 : 0.01,
      matched: name === "Yb" ? 1 : 0,
    })),
  };
  const decisionStageRows = stageRows("result", decisionResultState);
  assert(
    decisionStageRows.slice(0, 4).map((row) => row[0]).join("|") === explanationLabels,
    "result stage table should lead with input/process/output/risk explanation rows",
  );
  const decisionDetailRows = decisionStageRows.slice(4);
  assert(
    decisionDetailRows.slice(0, 4).map((row) => row[0]).join("|") === "候选结论|证据强弱|复核点|导出确认",
    "result stage table should keep decision summary rows after the explanation rows",
  );
  assert(
    decisionDetailRows.filter((row) => String(row[0]).startsWith("稀土明细 ")).length === 15,
    "result stage table should keep all 15 rare-earth detail rows after the summary",
  );
  assert(
    decisionDetailRows.find((row) => row[0] === "稀土明细 Yb") && decisionDetailRows.find((row) => row[0] === "稀土明细 Yb")[1].includes("0.2703"),
    "result stage detail rows should preserve original confidence values",
  );
  const decisionInspectorRows = resultRows(PROCESS_STAGES[6], decisionResultState);
  assert(
    decisionInspectorRows.slice(0, 4).map((row) => row[0]).join("|") === "候选结论|证据强弱|复核点|导出确认",
    "result inspector should lead with decision summary fields",
  );
  assert(decisionInspectorRows.find((row) => row[0] === "复核点")[1].includes("多峰拟合补救"), "result review reasons should surface backend-provided fit rescue");
  const noRescueDecisionRows = resultRows(PROCESS_STAGES[6], { ...decisionResultState, fitConfidenceRescue: null });
  assert(!noRescueDecisionRows.find((row) => row[0] === "复核点")[1].includes("多峰拟合补救"), "fit rescue review reason should not be inferred from before/after confidence");
  assert(resultRows(PROCESS_STAGES[6], { ...decisionResultState, rareEarthResults: [{ name: "Yb", detected: true, confidence: 0.7, matched: 3 }] })[1][1] === "证据较强", "review band should mark confidence >= 0.70 as strong evidence");
  assert(resultRows(PROCESS_STAGES[6], { ...decisionResultState, rareEarthResults: [{ name: "Yb", detected: true, confidence: 0.3, matched: 2 }] })[1][1] === "待复核", "review band should mark confidence >= 0.30 as review");
  assert(resultRows(PROCESS_STAGES[6], { ...decisionResultState, rareEarthResults: [{ name: "Yb", detected: true, confidence: 0.299, matched: 1 }] })[1][1] === "证据不足", "review band should mark confidence < 0.30 as weak evidence");
  const fitTargetOptions = buildFitTargetOptions(normalized, "");
  assert(fitTargetOptions[0].value === "", "fit target selector should offer automatic mode first");
  assert(fitTargetOptions.some((option) => option.target && option.target.ion === "YbII" && option.target.wavelength === 274.895), "fit target selector should expose matched rare-earth lines");
  const ybTargetOption = fitTargetOptions.find((option) => option.target && option.target.ion === "YbII" && option.target.wavelength === 274.895);
  const runPayload = buildPipelineRunPayload("RREs/070101_95.csv", ybTargetOption.value);
  assert(runPayload.fit_target.element === "Yb", "pipeline request payload should include selected target element");
  assert(runPayload.fit_target.ion === "YbII", "pipeline request payload should include selected target ion");
  assert(runPayload.fit_target.wavelength === 274.895, "pipeline request payload should include selected target wavelength");
  assert(runPayload.fit_target.source === "coarse_matched", "explicit UI target selection should request coarse_matched source mode");
  assert(
    shouldAutoRunAfterFitTargetChange({ isRunning: false, hasFitOptions: fitTargetOptions.length > 1, selectedValue: ybTargetOption.value }),
    "selecting a concrete fit target should auto-run when idle",
  );
  assert(
    !shouldAutoRunAfterFitTargetChange({ isRunning: true, hasFitOptions: fitTargetOptions.length > 1, selectedValue: ybTargetOption.value }),
    "fit target selector should not auto-run while a pipeline run is active",
  );
  assert(
    !shouldAutoRunAfterFitTargetChange({ isRunning: false, hasFitOptions: fitTargetOptions.length > 1, selectedValue: "" }),
    "switching fit target back to automatic should not auto-run without a concrete target",
  );
  assert(
    shouldUseFitOnlyRun({ jobId: normalized.jobId, isRunning: false, selectedValue: ybTargetOption.value }),
    "selecting a concrete fit target after a completed backend run should use fit-only rerun",
  );
  assert(
    !shouldUseFitOnlyRun({ jobId: null, isRunning: false, selectedValue: ybTargetOption.value }),
    "fit-only rerun should require an existing backend job id and must not fall back to a full run",
  );
  const fitCanvasTexts = [];
  const fitCanvas = {
    width: 960,
    height: 520,
    style: {},
    dataset: {},
    parentElement: null,
    getBoundingClientRect: () => ({ width: 960, height: 520 }),
    getContext: () => ({
      setTransform() {},
      clearRect() {},
      fillRect() {},
      strokeRect() {},
      beginPath() {},
      moveTo() {},
      lineTo() {},
      stroke() {},
      fill() {},
      arc() {},
      rect() {},
      clip() {},
      save() {},
      restore() {},
      setLineDash() {},
      measureText: (text) => ({ width: String(text).length * 7 }),
      fillText: (text) => fitCanvasTexts.push(String(text)),
    }),
  };
  const previousWindow = globalThis.window;
  globalThis.window = { devicePixelRatio: 1 };
  drawFit(fitCanvas, normalized);
  if (previousWindow === undefined) {
    delete globalThis.window;
  } else {
    globalThis.window = previousWindow;
  }
  assert(fitCanvasTexts.includes("原始光谱"), "fit legend should use Chinese raw spectrum label");
  assert(fitCanvasTexts.includes("分峰曲线"), "fit legend should use Chinese component curve label");
  assert(fitCanvasTexts.includes("总拟合"), "fit legend should use Chinese sum fit label");
  assert(fitCanvasTexts.includes("拟合峰位"), "fit legend should use Chinese fitted peak label");
  assert(fitCanvasTexts.includes("局部极值"), "fit legend should use Chinese local extrema label");
  assert(fitCanvasTexts.every((text) => text !== "Gaussian Components"), "fit legend should not expose English component label");
  assert(fitCanvasTexts.some((text) => text === "273.995"), "fit chart should draw numeric x-axis tick labels");
  assert(fitCanvasTexts.some((text) => text === "0.034" || text === "0.0340"), "fit chart should draw numeric y-axis tick labels");
  const fitTableRows = stageRows("fit", normalized).slice(4);
  assert(fitTableRows[0][0].startsWith("拟合候选"), "fit table should keep selected fit candidates after explanation rows");
  assert(fitTableRows[1][2].includes("matrix"), "fit table should show candidate source for matrix lines");
  assert(fitTableRows.some((row) => row[0].startsWith("局部极值")), "fit table should still include local extrema rows");

  const denseMatches = Array.from({ length: 24 }, (_, index) => ({
    element: `L${index}`,
    wl: 430 + index * 2.6,
    expWl: 430 + index * 2.6,
    expInt: 0.35 + index * 0.01,
    status: index % 5 === 0 ? "blocked" : "enabled",
    deltaNm: index * 0.002,
  }));
  const matchWindow = selectSpectralMatchWindow(generateSpectrum(), denseMatches);
  assert(matchWindow.maxX - matchWindow.minX < 260, "spectral match chart should zoom into dense matched lines");
  assert(typeof createDefaultChartZoom === "function", "spectrum stages should expose a shared chart zoom state factory");
  assert(typeof resolveSpectrumChartWindow === "function", "spectrum stages should resolve zoom windows through a shared helper");
  assert(typeof drawSpectrumChart === "function", "raw, peak, and match stages should use one shared spectrum chart renderer");
  assert(typeof drawSpectrumAxes === "function", "spectrum chart should draw grid, ticks, and complete axis labels");
  assert(typeof spectrumInsetLayout === "function", "spectrum chart should place inset lenses with obstacle avoidance");
  assert(typeof spectrumZoomEmphasis === "function", "spectrum chart zoom should enlarge lines, markers, and labels");
  const defaultRawZoom = createDefaultChartZoom("raw");
  assert(defaultRawZoom.stageId === "raw" && defaultRawZoom.lens.enabled === true, "raw spectrum should get an enabled lens zoom state");
  const defaultPeakZoom = createDefaultChartZoom("peak");
  assert(defaultPeakZoom.stageId === "peak" && defaultPeakZoom.widthNm > 0, "peak spectrum should get a controllable wavelength window");
  const rawWindow = resolveSpectrumChartWindow("raw", appState, { ...defaultRawZoom, centerNm: 516, widthNm: 20 });
  assert(Math.abs(rawWindow.maxX - rawWindow.minX - 20) < 0.001, "raw spectrum zoom should control the x window width");
  const peakWindow = resolveSpectrumChartWindow("peak", appState, { ...defaultPeakZoom, centerNm: appState.peaks[0].x, widthNm: 18 });
  assert(Math.abs(peakWindow.maxX - peakWindow.minX - 18) < 0.001, "peak spectrum zoom should control the x window width");
  const blockedInset = spectrumInsetLayout(900, 420, { left: 58, right: 24, top: 32, bottom: 56 }, [
    { x: 520, y: 38, width: 330, height: 210, weight: 12 },
  ]);
  assert(blockedInset.x < 450 || blockedInset.y > 190, "spectrum inset should avoid high-priority occupied regions");
  const looseEmphasis = spectrumZoomEmphasis(spectrumBounds(generateSpectrum()), { minX: 420, maxX: 520 });
  const closeEmphasis = spectrumZoomEmphasis(spectrumBounds(generateSpectrum()), { minX: 450, maxX: 470 });
  assert(closeEmphasis.labelFontSize > looseEmphasis.labelFontSize, "tighter spectrum zoom should enlarge important labels");
  assert(typeof createDefaultMatchZoom === "function", "spectral match chart should expose explicit zoom state");
  assert(typeof resolveSpectralMatchWindow === "function", "spectral match chart should resolve manual zoom windows");
  assert(typeof spectralZoomEmphasis === "function", "spectral match zoom should enlarge lines and markers");
  assert(typeof spectralInsetLayout === "function", "spectral match chart should draw a bounded inset lens");
  assert(typeof drawSpectralXAxis === "function", "spectral match chart should draw wavelength ticks on the x axis");
  const defaultMatchZoom = createDefaultMatchZoom();
  assert(defaultMatchZoom.mode === "manual" && defaultMatchZoom.enabled === true, "spectral match zoom should default to direct manual navigation");
  const manualMatchWindow = resolveSpectralMatchWindow(generateSpectrum(), denseMatches, {
    ...defaultMatchZoom,
    enabled: true,
    mode: "manual",
    centerNm: 460,
    widthNm: 20,
  });
  assert(Math.abs(manualMatchWindow.maxX - manualMatchWindow.minX - 20) < 0.001, "manual spectral match zoom should control the x window width");
  const defaultManualWindow = resolveSpectralMatchWindow(generateSpectrum(), denseMatches, createDefaultMatchZoom());
  assert(
    denseMatches.some((line) => line.wl >= defaultManualWindow.minX && line.wl <= defaultManualWindow.maxX),
    "default manual zoom should focus on a real highlighted match line",
  );
  const wideEmphasis = spectralZoomEmphasis(spectrumBounds(generateSpectrum()), { minX: 420, maxX: 520 });
  const tightEmphasis = spectralZoomEmphasis(spectrumBounds(generateSpectrum()), { minX: 450, maxX: 470 });
  assert(tightEmphasis.lineWidthMultiplier > wideEmphasis.lineWidthMultiplier, "tighter spectral zoom should use thicker lines");
  assert(tightEmphasis.pointRadiusMultiplier > wideEmphasis.pointRadiusMultiplier, "tighter spectral zoom should use larger peak markers");
  const mobileInset = spectralInsetLayout(390, 320, { left: 48, right: 24, top: 38, bottom: 42 });
  assert(mobileInset.x >= 48 && mobileInset.x + mobileInset.width <= 390 - 24 + 0.001, "spectral match inset should stay inside the mobile canvas");
  assert(mobileInset.width >= 210 && mobileInset.height >= 145, "spectral match inset should be large enough for readable detail");
  const desktopInset = spectralInsetLayout(1280, 560, { left: 48, right: 24, top: 26, bottom: 64 });
  assert(desktopInset.width >= 650 && desktopInset.height >= 270, "spectral match inset should use available desktop whitespace");
  assert(compressSpectralIntensity(0.25) > 0.25 && compressSpectralIntensity(1) === 1, "intensity compression should lift small peaks without changing the maximum");
  const adaptiveTransform = createSpectralOverviewTransform([{ y: 0.01 }, { y: 0.08 }, { y: 0.1 }, { y: 1 }]);
  assert(adaptiveTransform(0.08) > compressSpectralIntensity(0.08), "adaptive spectral overview should keep non-dominant peaks visible");
  const unclearAxisLabel = ["Intensity", "/", "sticks"].join(" ");
  assert(!drawSpectralMatch.toString().includes(unclearAxisLabel), "spectral match chart should omit the unclear y-axis label");
  const indexHtml = require("fs").readFileSync("web_app/index.html", "utf8");
  const stylesCss = require("fs").readFileSync("web_app/styles.css", "utf8");
  const appJs = require("fs").readFileSync("web_app/app.js", "utf8");
  assert(typeof buildHtmlReport === "function", "HTML report export should provide a static report builder");
  assert(indexHtml.includes('data-action="export-report"'), "toolbar should expose a dedicated HTML report export action");
  assert(indexHtml.includes('data-action="export-json"'), "toolbar should keep JSON export available");
  assert(indexHtml.includes('data-action="export-summary"'), "toolbar should keep text summary export available");
  assert(indexHtml.includes('class="export-menu"'), "toolbar should merge export formats into one export menu");
  assert(indexHtml.includes('data-action="export-menu-toggle"'), "merged export menu should expose one toolbar export trigger");
  assert(indexHtml.includes('class="export-menu-list"'), "merged export menu should contain the export format list");
  assert(!indexHtml.includes('class="tool-button" type="button" data-action="output"'), "CSV should not remain as a standalone toolbar button");
  assert(!indexHtml.includes('class="tool-button" type="button" data-action="export-json"'), "JSON should not remain as a standalone toolbar button");
  assert(!indexHtml.includes('class="tool-button" type="button" data-action="export-summary"'), "summary should not remain as a standalone toolbar button");
  assert(!indexHtml.includes('class="tool-button report" type="button" data-action="export-report"'), "HTML report should not remain as a standalone toolbar button");
  assert(stylesCss.includes(".export-menu"), "CSS should style the merged export menu");
  const reportFixture = {
    exportedAt: "2026-06-05T12:00:00.000Z",
    jobId: "job-report-fixture",
    filename: "fixture-Yb<sample>.csv",
    fileStatus: "后端结果",
    pointCount: 2048,
    peakCount: 32,
    wavelengthRange: { minX: 270.125, maxX: 890.75 },
    peakMethod: "CWT ridge peak detection",
    matrixElements: ["Mn", "Fe"],
    targetTemperature: 15427.11,
    temperatureBestScore: 0.7655,
    bestTemperatureStartIndex: 1,
    stageSummaries: Object.fromEntries(PROCESS_STAGES.map((stage) => [stage.id, `${stage.id} summary`])),
    spectralMatches: [
      { element: "YbII", baseElement: "Yb", wl: 274.895, expWl: 274.895, expInt: 0.82, deltaNm: 0, confidence: 0.0779, status: "enabled", reason: "fixture match" },
      { element: "MnII", baseElement: "Mn", wl: 275.0125, expWl: 275.01, expInt: 0.51, deltaNm: 0.0025, confidence: 0.0, status: "blocked", reason: "fixture overlap" },
      { element: "EuII", baseElement: "Eu", wl: 420.12, expWl: 420.2, expInt: 0.1, deltaNm: 0.08, confidence: 0.0, status: "review", reason: "fixture low confidence" },
    ],
    confidenceCalculation: normalizeConfidenceCalculation({
      formula: { confidence: "exp(-4.5 * distance / max(R2, 1e-9))" },
      total_count: 1,
      items: [
        {
          element: "Yb",
          ion: "YbII",
          confidence: 0.0779,
          distance: 0.4341,
          temperature: 15427.11,
          r2: 0.7655,
          line_count: 5,
          all_theoretical_comb: [{ wavelength: 275.0477 }, { wavelength: 328.937 }],
          matched_theoretical_comb: [{ wavelength: 275.0477 }],
          matched_experimental_comb: [{ wavelength: 274.895 }],
          representative_selection: { selected: true, reason: "valid_temperature_best_r2" },
        },
      ],
    }),
    temperatureStarts: [
      { startIndex: 0, initialTemperature: 5000, finalTemperature: 12000, bestCandidate: "Fe", bestScore: 0.32, bestR2: 0.7, selected: false },
      { startIndex: 1, initialTemperature: 10000, finalTemperature: 15427.11, bestCandidate: "Yb", bestScore: 0.7655, bestR2: 0.7655, selected: true },
    ],
    fit: {
      window: { left: 273.995, right: 275.795, rms: 0.00434 },
      candidates: [{ source: "normalized_pure_element", element: "Yb", label: "YbII", center: 274.895, lineIntensity: 0.0699, lineType: "Rareearth_pt3 relative intensity" }],
      components: [{ label: "YbII", center: 274.895, height: 0.0182, width: 0.1425 }],
      fallbackReason: null,
      confidenceRescue: {
        applied: true,
        reason: "fitted_peak_append_recompute",
        targetElement: "Yb",
        baseConfidence: 0.0772,
        recomputedConfidence: 0.2703,
        appendedPeakCount: 1,
      },
    },
    rareEarthResults: [
      { name: "Yb", detected: true, confidence: 0.2703, matched: 1, temperature: 15427.11, r2: 0.7655 },
      { name: "Eu", detected: false, confidence: 0.0, matched: 0, temperature: 0, r2: 0 },
    ],
  };
  const reportHtml = buildHtmlReport(reportFixture, { chartImageDataUrl: "data:image/png;base64,AA==" });
  assert(reportHtml.includes("LIBS 稀土元素检测报告"), "HTML report should include the required title");
  assert(reportHtml.includes("Yb"), "HTML report should include detected elements from the payload fixture");
  assert(PROCESS_STAGES.every((stage) => reportHtml.includes(`>${stage.id}<`) && reportHtml.includes(`${stage.id} summary`)), "HTML report should include all seven stage summaries");
  assert(reportHtml.includes("置信度计算摘要"), "HTML report should include the confidence calculation summary");
  assert(reportHtml.includes("稀土结果表"), "HTML report should include the rare-earth result table");
  assert(reportHtml.includes("完整 JSON payload"), "HTML report should include the full JSON appendix");
  assert(reportHtml.includes("&quot;filename&quot;"), "HTML report JSON appendix should be escaped");
  assert(reportHtml.includes("fixture-Yb&lt;sample&gt;.csv"), "HTML report should escape dynamic sample names");
  assert(!reportHtml.includes("fixture-Yb<sample>.csv"), "HTML report should not contain unescaped dynamic sample names");
  assert(reportHtml.includes("@media print"), "HTML report should include print CSS");
  assert(reportHtml.includes("data:image/png;base64,AA=="), "HTML report should include a valid optional canvas image when provided");
  assert(!reportHtml.includes("<script"), "HTML report should be static and not depend on runtime JavaScript");
  assert(indexHtml.includes('data-source-mode="offline"'), "UI should expose an offline analysis source mode");
  assert(indexHtml.includes('data-source-mode="realtime"'), "UI should expose a real-time acquisition source mode");
  assert(indexHtml.includes("操作者确认"), "HCI copy should explicitly mark operator confirmation areas");
  assert(indexHtml.includes("系统证据"), "HCI copy should label generated evidence without overstating automation");
  assert(indexHtml.includes("待复核"), "HCI copy should mark review points before report export");
  assert(PROCESS_STAGES.some((stage) => stage.detail.includes("算法")), "stage subtitles should describe algorithm work while keeping stable stage names");
  const aiTerm = ["A", "I"].join("");
  const genericIntelligenceTerm = ["人工", "智能"].join("");
  assert(!(indexHtml + appJs).includes(aiTerm) && !(indexHtml + appJs).includes(genericIntelligenceTerm), "HCI copy should not present the current LIBS workstation as a generic intelligent system");
  assert(indexHtml.includes('data-source-panel="realtime"'), "UI should expose a dedicated real-time acquisition panel");
  assert(indexHtml.includes("采集板串口"), "real-time acquisition panel should focus on acquisition-board serial selection");
  assert((indexHtml.match(/class="realtime-block"/g) || []).length === 1, "real-time acquisition panel should stay compact and use a single block");
  assert(!indexHtml.includes("光谱仪 IP 绑定"), "compact real-time panel should not show the future spectrometer binding block yet");
  assert(!indexHtml.includes("采集控制"), "compact real-time panel should not show future acquisition controls yet");
  assert(!indexHtml.includes("光谱预览"), "compact real-time panel should not show future preview metadata yet");
  assert(!indexHtml.includes('class="serial-state-list"'), "compact real-time parameter panel should not render a long serial-state explanation list");
  assert(!stylesCss.includes('.workstation-shell[data-source-mode="realtime"] .workflow-tree'), "real-time mode should not reorder mobile panels above the chart");
  assert(typeof normalizeRealtimeParameters === "function", "real-time parameter confirmation should have a pure validator");
  assert(normalizeRealtimeParameters({ serialPort: "", spectrometerIp: "192.168.0.10", spectrometerPort: "5000" }).ok, "default real-time IP/port parameters should be confirmable");
  assert(!normalizeRealtimeParameters({ serialPort: "", spectrometerIp: "192.168.0.999", spectrometerPort: "5000" }).ok, "real-time parameter confirmation should reject invalid IPv4 addresses");
  assert(!normalizeRealtimeParameters({ serialPort: "", spectrometerIp: "192.168.0.10", spectrometerPort: "99999" }).ok, "real-time parameter confirmation should reject invalid ports");
  const misleadingShellLabel = ["UI", "shell"].join(" ");
  assert(!indexHtml.includes(misleadingShellLabel), "real-time acquisition UI should not expose the misleading shell label");
  assert(!appJs.includes(misleadingShellLabel), "runtime copy should not tell operators the feature is only a shell");
  const waitingSerialLabel = ["等待授权", "串口"].join("");
  assert(!indexHtml.includes(waitingSerialLabel), "real-time serial header should use a confirmation action instead of a waiting-authorization status");
  const unauthorizedPortLabel = ["未授权", "端口"].join("");
  assert(!indexHtml.includes(unauthorizedPortLabel), "real-time serial port selector should not imply browser-side authorization");
  const serialPlaceholderLabel = ["串口", "占位"].join("");
  assert(!appJs.includes(serialPlaceholderLabel), "real-time status copy should describe backend-detected acquisition-board ports");
  assert(indexHtml.includes("未检测到采集板端口"), "real-time serial port selector should default to a backend-detected empty state");
  assert(appJs.includes("/api/realtime/ports"), "real-time acquisition should request backend USB/serial candidates");
  assert(typeof normalizeRealtimePorts === "function", "real-time acquisition should normalize backend USB/serial candidates");
  const normalizedPorts = normalizeRealtimePorts({
    ports: [
      { path: " /dev/ttyUSB0 ", label: "采集板 USB0", source: "ttyUSB", target: "/dev/ttyUSB0" },
      { path: "/dev/ttyUSB0", label: "重复端口" },
      { path: "", label: "空端口" },
    ],
  });
  assert(normalizedPorts.ports.length === 1, "real-time port normalization should deduplicate non-empty paths");
  assert(normalizedPorts.ports[0].path === "/dev/ttyUSB0", "real-time port normalization should trim serial paths");
  assert(realtimePortSelectRows({ loading: true })[0].label === "正在识别采集板端口...", "real-time port selector should expose a loading row");
  assert(realtimePortSelectRows({ ports: [] })[0].label === "未检测到采集板端口", "real-time port selector should expose an empty row");
  assert(indexHtml.includes('data-action="confirm-realtime-params"'), "real-time acquisition panel should expose a parameter confirmation button");
  assert(indexHtml.includes('id="realtime-config-status"'), "real-time acquisition panel should show confirmed parameter status");
  assert(!indexHtml.includes('data-realtime-action="authorize-serial"'), "compact real-time parameter panel should not show a serial authorization button");
  assert(!indexHtml.includes('data-realtime-action="refresh-serial"'), "compact real-time parameter panel should not show a serial refresh button");
  assert(!indexHtml.includes("待接入；不会打开端口或发送命令"), "compact real-time parameter panel should remove the long not-wired serial sentence");
  assert(indexHtml.includes('id="serial-port-select"'), "real-time parameter panel should expose a COM/port selector placeholder");
  assert(indexHtml.includes('id="spectrometer-ip-input"'), "real-time parameter panel should expose a spectrometer IP setting");
  assert(indexHtml.includes('id="spectrometer-port-input"'), "real-time parameter panel should expose a spectrometer port setting");
  assert(typeof sourceModeRunDisabledReason === "function", "source mode helper should explain why run is disabled");
  assert(
    sourceModeRunDisabledReason({ sourceMode: "realtime", hasOfflineSource: true, isRunning: false }) === "实时采集尚未产生光谱数据",
    "real-time source mode should not run the backend pipeline from an offline source",
  );
  assert(sourceModeRunDisabledReason({ sourceMode: "offline", hasOfflineSource: false, isRunning: false }) === "请先打开光谱或文件夹", "offline mode should still require an imported or sample-library source");
  assert(sourceModeRunDisabledReason({ sourceMode: "offline", hasOfflineSource: true, isRunning: false }) === "", "offline mode should allow an available offline source");
  const serialApiProperty = ["navigator", "serial"].join(".");
  const serialRequestMethod = ["request", "Port"].join("");
  const serialListMethod = ["get", "Ports"].join("");
  const serialOpenCall = ["port", "open"].join(".");
  const serialWriteCall = ["writer", "write"].join(".");
  assert(!indexHtml.includes(serialApiProperty), "HTML should not reference Web Serial APIs");
  assert(!indexHtml.includes(serialRequestMethod), "HTML should not request serial ports");
  assert(!indexHtml.includes(serialListMethod), "HTML should not enumerate serial ports");
  assert(!indexHtml.includes(serialOpenCall), "HTML should not open serial ports");
  assert(!indexHtml.includes(serialWriteCall), "HTML should not send serial commands");
  assert(!stylesCss.includes(".serial-source") && !stylesCss.includes(".rj45-source"), "CSS should not split serial and RJ45 into parallel real-time sources");
  assert(indexHtml.includes('id="spectrum-folder"'), "UI should expose a hidden folder import input");
  assert(indexHtml.includes("webkitdirectory directory mozdirectory multiple"), "folder input should expose browser directory-selection attributes");
  assert(!indexHtml.includes('<option value="RREs/070101_95.csv"'), "initial selector should not embed the default scanned RRE sample");
  assert(indexHtml.includes('data-action="load-samples"'), "sample library should be loaded only by an explicit button");
  assert(indexHtml.includes('id="sample-library-select"'), "sample library should use a separate selector from imported files");
  assert(indexHtml.includes('class="stage-toolbar"'), "stage title and step navigation should be merged into a compact toolbar");
  assert(!indexHtml.includes('data-menu-root'), "top menu root should be removed because toolbar actions already cover the commands");
  assert(!stylesCss.includes(".toolbar-menu"), "top menu styles should not remain after removing the duplicate command menu");
  assert(!indexHtml.includes('id="stage-select"'), "stage selector dropdown should be removed because the step strip already handles stage navigation");
  assert(indexHtml.includes('class="chart-tools-drawer"'), "chart controls should live in a collapsible drawer");
  assert(stylesCss.includes(".stage-toolbar"), "CSS should style the compact stage toolbar");
  assert(!stylesCss.includes(".stage-selector"), "CSS should not keep stale stage-selector layout after removing the dropdown");
  assert(stylesCss.includes(".chart-tools-drawer"), "CSS should style the chart tools drawer");
  assert(stylesCss.includes(".chart-zoom-controls[hidden]"), "CSS must not let chart zoom controls override the hidden attribute");
  assert(stylesCss.includes(".match-evidence-key[hidden]"), "CSS must not let match evidence legend override the hidden attribute");
  assert(stylesCss.includes("height: 100vh;"), "desktop workstation shell should lock to the viewport height");
  assert(stylesCss.includes("body {\n  margin: 0;\n  height: 100%;"), "body should use fixed viewport height instead of growing the full page");
  assert(stylesCss.includes("overflow: hidden;"), "desktop layout should avoid whole-page scrolling");
  assert(stylesCss.includes("grid-template-columns: minmax(120px, 1fr) auto auto;"), "desktop plot header should keep title, tools, and status in one compact row");
  assert(!stylesCss.includes("grid-template-rows: auto auto minmax(260px, 1fr) 180px;"), "main view should not keep separate view-header and step-strip rows above the plot");
  assert(indexHtml.includes("match-evidence-key"), "spectral match evidence legend should live in the title toolbar");
  assert(!drawSpectralMatch.toString().includes("drawSpectralLegend"), "spectral match canvas should not spend plot area on a bottom legend");
  assert(!indexHtml.includes(["data", "match", "zoom", "mode"].join("-")), "spectral match controls should not expose redundant zoom modes");
  assert(!indexHtml.includes(["match", "zoom", "width"].join("-")), "spectral match controls should not expose a redundant window slider");
  const visibleLabels = chooseVisibleSpectralLabels(denseMatches, 900);
  assert(visibleLabels.length <= 12, "spectral match chart should cap label count for readability");
  const highlightedDenseMatches = selectHighlightedSpectralMatches(denseMatches, 900);
  assert(highlightedDenseMatches.length <= 4, "dense spectral matches should only promote a few lines to full-height highlights");
  assert(
    drawSpectrumOverviewFeatures.toString().includes("drawSpectralEvidenceTicks") && drawSpectrumInset.toString().includes("drawSpectralEvidenceTicks"),
    "dense spectral matches should use compact tick evidence instead of full-height clutter",
  );
  const labelLayout = layoutSpectralLabels(visibleLabels, { minX: matchWindow.minX, xScale: 5 }, { left: 48, top: 32 }, 900);
  const hasCollision = labelLayout.some((label, index) =>
    labelLayout.slice(index + 1).some((other) => label.row === other.row && Math.abs(label.labelX - other.labelX) < 54),
  );
  assert(!hasCollision, "spectral match labels should avoid horizontal collisions");
}

if (typeof window === "undefined") {
  runSelfTests();
} else {
  window.addEventListener("DOMContentLoaded", initApp);
}

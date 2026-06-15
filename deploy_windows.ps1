param(
    [int]$Port = 5000,
    [switch]$SkipInstall,
    [switch]$NoBrowser,
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-Python {
    $candidates = @(
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() },
        @{ Command = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        try {
            & $candidate.Command @($candidate.Args) --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
            continue
        }
    }

    throw "未找到 Python。请先安装 Python 3.10+，并勾选 Add python.exe to PATH。"
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)] [hashtable]$PythonCommand,
        [string[]]$Arguments = @()
    )
    & $PythonCommand.Command @($PythonCommand.Args) @Arguments
}

function Invoke-VenvPython {
    param([string[]]$Arguments = @())
    & $script:VenvPython @Arguments
}

function Wait-ForHealth {
    param([string]$Url)

    $deadline = (Get-Date).AddSeconds(45)
    $lastError = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 5
            if ($response.status -eq "ok") {
                return $response
            }
        } catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Seconds 1
        }
    }

    throw "服务未在 45 秒内就绪: $lastError"
}

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$requiredPaths = @(
    "backend\app.py",
    "backend\pipeline.py",
    "backend\samples.py",
    "web_app\index.html",
    "web_app\app.js",
    "RandomSpectrum_av2\Pt2"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        throw "缺少必要文件或目录: $path。请在完整项目根目录运行本脚本。"
    }
}

$sampleCount = @(Get-ChildItem -Path "RandomSpectrum_av2\Pt2" -Filter "*.csv" -File).Count
if ($sampleCount -lt 1) {
    throw "RandomSpectrum_av2\Pt2 中没有 CSV 示例光谱，示例样本库无法运行。"
}

Write-Step "准备 Python 虚拟环境"
$python = Resolve-Python
$VenvDir = Join-Path $ProjectRoot ".venv"
$script:VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $script:VenvPython)) {
    Invoke-Python -PythonCommand $python -Arguments @("-m", "venv", $VenvDir)
}

if (-not (Test-Path $script:VenvPython)) {
    throw "虚拟环境创建失败: $VenvDir"
}

if (-not $SkipInstall) {
    Write-Step "安装 Web 运行依赖"
    Invoke-VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-VenvPython -Arguments @("-m", "pip", "install", "flask", "numpy", "scipy", "PyWavelets")
}

Write-Step "运行本地预检"
Invoke-VenvPython -Arguments @("-m", "compileall", "-q", "backend")

$sampleCheck = @"
from backend.samples import list_sample_files
samples = list_sample_files()
assert samples, "示例样本库为空"
assert all(row["path"].startswith("RandomSpectrum_av2/Pt2/") for row in samples), samples[:3]
print(f"samples={len(samples)}")
"@
Invoke-VenvPython -Arguments @("-c", $sampleCheck)

if ($SmokeOnly) {
    Write-Step "预检完成"
    Write-Host "未启动服务，因为指定了 -SmokeOnly。"
    exit 0
}

Write-Step "启动本地 Web 服务"
$BaseUrl = "http://127.0.0.1:$Port"
$LogDir = Join-Path $env:TEMP "rre-libs-web"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$StdoutLogFile = Join-Path $LogDir "flask-$Port.out.log"
$StderrLogFile = Join-Path $LogDir "flask-$Port.err.log"

$serverCode = @"
from backend.app import app
app.run(host="127.0.0.1", port=$Port, debug=False, use_reloader=False)
"@

$server = Start-Process `
    -FilePath $script:VenvPython `
    -ArgumentList @("-c", $serverCode) `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $StdoutLogFile `
    -RedirectStandardError $StderrLogFile `
    -PassThru `
    -WindowStyle Hidden

try {
    Wait-ForHealth "$BaseUrl/api/health" | Out-Null
    if ($server.HasExited) {
        throw "服务进程已退出，请查看日志: $StderrLogFile"
    }

    Write-Step "运行接口烟测"
    $samplesResponse = Invoke-RestMethod -Uri "$BaseUrl/api/samples" -TimeoutSec 15
    $samples = @($samplesResponse.samples)
    if ($samples.Count -lt 1) {
        throw "/api/samples 返回空列表"
    }
    $badSamples = @($samples | Where-Object { $_.path -notlike "RandomSpectrum_av2/Pt2/*" })
    if ($badSamples.Count -ne 0) {
        throw "/api/samples 返回了非 RandomSpectrum_av2/Pt2 的路径"
    }

    $firstSample = $samples[0].path
    $body = @{ sample_path = $firstSample } | ConvertTo-Json -Compress
    $pipelineResponse = Invoke-RestMethod `
        -Uri "$BaseUrl/api/pipeline/run" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 120

    if (@($pipelineResponse.stages).Count -ne 6) {
        throw "/api/pipeline/run 未返回 6 个阶段"
    }

    Write-Host ""
    Write-Host "本地部署已启动: $BaseUrl" -ForegroundColor Green
    Write-Host "示例样本数: $($samples.Count)"
    Write-Host "烟测样本: $firstSample"
    Write-Host "烟测结果: $($pipelineResponse.stages[-1].summary)"
    Write-Host "服务进程 PID: $($server.Id)"
    Write-Host "服务标准输出日志: $StdoutLogFile"
    Write-Host "服务错误日志: $StderrLogFile"
    Write-Host ""
    Write-Host "关闭服务时可运行:"
    Write-Host "Stop-Process -Id $($server.Id)"

    if (-not $NoBrowser) {
        Start-Process $BaseUrl
    }
} catch {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    throw
}

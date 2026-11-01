# 本机一键起官方 DeepSeek Harness Web UI。
# 从用户主目录启动，避免 DSH 把本仓库当成 workspace。
# DSH 是旁路运行时，不进 src/core，也不在这里接 QQ。

$ErrorActionPreference = "Stop"

$DshListenHost = "127.0.0.1"
$DshListenPort = 3080
$DshWebRoot = "http://${DshListenHost}:${DshListenPort}"
$MinNodeMajor = 24
$MinNodeMinor = 9

function Write-Info([string]$Message) {
    Write-Host $Message
}

function Write-Fail([string]$Message) {
    Write-Host $Message -ForegroundColor Red
}

function Add-ToolPath([string]$Directory) {
    if (-not $Directory) {
        return
    }
    if (-not (Test-Path -LiteralPath $Directory)) {
        return
    }
    $parts = $env:Path -split ";"
    if ($parts -contains $Directory) {
        return
    }
    $env:Path = "$Directory;$env:Path"
}

function Initialize-LaunchPath {
    Add-ToolPath (Join-Path $env:APPDATA "npm")
    Add-ToolPath "${env:ProgramFiles}\nodejs"
    Add-ToolPath "${env:ProgramFiles(x86)}\nodejs"
}

function Get-CommandPath([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Get-NodeVersionParts {
    $raw = (& node -v).Trim()
    if ($raw -notmatch "^v(?<major>\d+)\.(?<minor>\d+)\.") {
        throw "无法解析 node 版本：$raw"
    }
    return [pscustomobject]@{
        Raw   = $raw
        Major = [int]$Matches.major
        Minor = [int]$Matches.minor
    }
}

function Test-PortListening([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$connections
}

function Open-DshHome {
    $work_dir = $env:USERPROFILE
    if (-not $work_dir) {
        throw "找不到 USERPROFILE，无法选择 DSH 工作目录。"
    }
    Set-Location -LiteralPath $work_dir
    Write-Info "工作目录：$work_dir"
}

Initialize-LaunchPath

$node_path = Get-CommandPath "node"
if (-not $node_path) {
    Write-Fail "没找到 node。DSH 需要 Node.js ${MinNodeMajor}.${MinNodeMinor}+。"
    exit 1
}

try {
    $node_version = Get-NodeVersionParts
}
catch {
    Write-Fail $_.Exception.Message
    exit 1
}

$node_too_old = (
    $node_version.Major -lt $MinNodeMajor -or
    ($node_version.Major -eq $MinNodeMajor -and $node_version.Minor -lt $MinNodeMinor)
)
if ($node_too_old) {
    Write-Fail "当前 node 是 $($node_version.Raw)，DSH 需要 ${MinNodeMajor}.${MinNodeMinor}+。"
    exit 1
}

$dsh_path = Get-CommandPath "dsh"
if (-not $dsh_path) {
    Write-Fail "没找到 dsh。先装：npm install -g @deepseek-ai/dsh"
    exit 1
}

Write-Info "node $($node_version.Raw)"
Write-Info "dsh  $dsh_path"

if (Test-PortListening $DshListenPort) {
    Write-Info "DSH 已经在听 $DshWebRoot"
    Write-Info "若页面要 token，去看当初启动的那个窗口。"
    Start-Process $DshWebRoot
    exit 0
}

Open-DshHome
Write-Info "启动 dsh web（默认打开浏览器）..."
& dsh web
exit $LASTEXITCODE

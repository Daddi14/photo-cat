# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
param(
    [string]$ModeArg = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectDir
$VersionFile = Join-Path $ProjectDir "VERSION"
$ProgramVersion = "unknown"
if (Test-Path $VersionFile) {
    $versionText = (Get-Content -Path $VersionFile -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not [string]::IsNullOrWhiteSpace($versionText)) {
        $ProgramVersion = $versionText.Trim()
    }
}
$env:PHOTO_CAT_PROJECT_DIR = $ProjectDir
$env:PHOTO_CAT_CONFIG = Join-Path $ProjectDir "config.yaml"
$env:PHOTO_CAT_VERSION = $ProgramVersion
$env:PYTHONPATH = Join-Path $ProjectDir "src"

$TitleLine = ("=" * 72)
$SoftLine = ("-" * 72)

$LogDir = Join-Path $ProjectDir "logs"
$SetupLog = Join-Path $LogDir "setup_windows.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$RuntimeDir = Join-Path $ProjectDir ".runtime"
$RuntimeToolsDir = Join-Path $RuntimeDir "tools"
$RuntimePythonDir = Join-Path $RuntimeDir "python"
$RuntimeDownloadsDir = Join-Path $RuntimeDir "downloads"
$RuntimeUvDir = Join-Path $RuntimeToolsDir "uv"
$PreferredRuntimePython = "3.12"

$Mode = "ALL"
if ($ModeArg -ieq "--install-only") {
    $Mode = "INSTALL"
}
elseif ($ModeArg -ieq "--configure-only") {
    $Mode = "CONFIGURE"
}
elseif ($ModeArg -ieq "--run-only") {
    $Mode = "RUN"
}

function Write-InfoLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    Write-Host (("  {0,-16}: {1}" -f $Label, $Value))
}

function Write-Note {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Write-Host ("  " + $Text) -ForegroundColor Gray
}

function Write-Header {
    Write-Host $TitleLine -ForegroundColor Cyan
    Write-Host "PHOTO-CAT - Setup" -ForegroundColor Cyan
    Write-Host $TitleLine -ForegroundColor Cyan
    Write-Host ""
    Write-InfoLine -Label "Version" -Value $ProgramVersion
    Write-InfoLine -Label "Project folder" -Value $ProjectDir
    Write-InfoLine -Label "Setup log" -Value $SetupLog
    Write-Host ""
}

function Write-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan
    Write-Host $SoftLine -ForegroundColor DarkGray
}


function Write-ProgressBar {
    param(
        [int]$Percent = 0,
        [string]$Detail = "",
        [switch]$Complete
    )

    if ($Percent -lt 0) { $Percent = 0 }
    if ($Percent -gt 100) { $Percent = 100 }

    $hostWidth = 88
    try {
        $hostWidth = [Console]::WindowWidth - 1
    }
    catch {
        $hostWidth = 88
    }
    if ($hostWidth -lt 42) { $hostWidth = 42 }
    if ($hostWidth -gt 96) { $hostWidth = 96 }

    $prefix = "    "
    $percentText = ("{0,3}%" -f $Percent)
    $detailText = $Detail

    $minBarWidth = 10
    $maxBarWidth = 34
    $reserved = $prefix.Length + $percentText.Length + 4
    $maxDetailLength = $hostWidth - $reserved - $minBarWidth - 2
    if ($maxDetailLength -lt 0) { $maxDetailLength = 0 }

    if ($detailText.Length -gt $maxDetailLength) {
        if ($maxDetailLength -gt 1) {
            $detailText = $detailText.Substring(0, $maxDetailLength - 1) + "."
        }
        else {
            $detailText = ""
        }
    }

    $barWidth = $hostWidth - $reserved - $detailText.Length
    if ($detailText.Length -gt 0) { $barWidth -= 2 }
    if ($barWidth -lt $minBarWidth) { $barWidth = $minBarWidth }
    if ($barWidth -gt $maxBarWidth) { $barWidth = $maxBarWidth }

    $filled = [int][Math]::Round($barWidth * ($Percent / 100.0))
    $empty = $barWidth - $filled
    $filledPart = "=" * $filled
    $emptyPart = "-" * $empty

    $esc = [char]27
    Write-Host "`r$esc[2K$prefix" -NoNewline
    if ($filled -gt 0) {
        Write-Host $filledPart -NoNewline -ForegroundColor Magenta
    }
    if ($empty -gt 0) {
        Write-Host $emptyPart -NoNewline -ForegroundColor DarkGray
    }
    Write-Host "  " -NoNewline
    Write-Host $percentText -NoNewline -ForegroundColor Green
    if ($detailText.Length -gt 0) {
        Write-Host "  $detailText" -NoNewline -ForegroundColor Gray
    }

    if ($Complete) {
        Write-Host ""
    }
}

function Write-Ok {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Write-Host "[ OK ] $Text" -ForegroundColor Green
}

function Write-WarnLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Write-Host "[WARN] $Text" -ForegroundColor Yellow
}

function Write-Fail {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

function Add-SetupLog {
    param(
        [AllowEmptyString()]
        [AllowNull()]
        [string]$Text = ""
    )

    if ($null -eq $Text) {
        $Text = ""
    }

    Add-Content -Path $SetupLog -Value $Text -Encoding UTF8
}

function Initialize-SetupLog {
    Set-Content -Path $SetupLog -Value "PHOTO-CAT Windows setup log" -Encoding UTF8
    Add-SetupLog "Started: $(Get-Date -Format s)"
    Add-SetupLog "Version: $ProgramVersion"
    Add-SetupLog "Project folder: $ProjectDir"
    Add-SetupLog ""
}

function Get-PythonDisplay {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$PrefixArgs = @()
    )

    $parts = @($Command) + @($PrefixArgs)
    return (($parts | Where-Object { $_ -ne $null -and $_ -ne "" }) -join " ").Trim()
}

function Test-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$PrefixArgs = @()
    )

    try {
        $healthCheck = @"
import sys
if not ((3, 10) <= sys.version_info[:2] <= (3, 13)):
    raise SystemExit(1)
import venv
import ensurepip
import tkinter
raise SystemExit(0)
"@
        & $Command @PrefixArgs -c $healthCheck *> $null

        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Command = $Command
                PrefixArgs = @($PrefixArgs)
                Display = Get-PythonDisplay -Command $Command -PrefixArgs $PrefixArgs
            }
        }
    }
    catch {
        return $null
    }

    return $null
}

function Find-Python {
    $launcherVersions = @("3.13", "3.12", "3.11", "3.10")
    foreach ($version in $launcherVersions) {
        $candidate = Test-PythonCommand -Command "py" -PrefixArgs @("-$version")
        if ($null -ne $candidate) {
            return $candidate
        }
    }

    $directCommands = @("python3.13", "python3.12", "python3.11", "python3.10", "python", "python3")
    foreach ($command in $directCommands) {
        $candidate = Test-PythonCommand -Command $command -PrefixArgs @()
        if ($null -ne $candidate) {
            return $candidate
        }
    }

    return $null
}

function Refresh-PythonPath {
    $candidateFolders = @()

    if ($env:LocalAppData) {
        $candidateFolders += Get-ChildItem -Path (Join-Path $env:LocalAppData "Programs\Python") -Directory -ErrorAction SilentlyContinue
    }

    if ($env:ProgramFiles) {
        $candidateFolders += Get-ChildItem -Path $env:ProgramFiles -Directory -Filter "Python3*" -ErrorAction SilentlyContinue
    }

    foreach ($folder in $candidateFolders) {
        $pythonExe = Join-Path $folder.FullName "python.exe"

        if (Test-Path $pythonExe) {
            $scriptsDir = Join-Path $folder.FullName "Scripts"
            $env:Path = "$($folder.FullName);$scriptsDir;$env:Path"
        }
    }
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    Add-SetupLog "================================================================"
    Add-SetupLog $Description
    Add-SetupLog ("> " + $Command + " " + (($Arguments | Where-Object { $_ -ne $null -and $_ -ne "" }) -join " "))
    Add-SetupLog "================================================================"

    & $Command @Arguments *>> $SetupLog
    $exitCode = $LASTEXITCODE

    Add-SetupLog ""
    Add-SetupLog "Exit code: $exitCode"
    Add-SetupLog ""

    return ($exitCode -eq 0)
}

function Get-UvDownloadUrl {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()

    if ($arch -eq "arm64") {
        return "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-pc-windows-msvc.zip"
    }

    return "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
}

function Get-LocalUv {
    $uvExe = Join-Path $RuntimeUvDir "uv.exe"
    if (Test-Path $uvExe) {
        return $uvExe
    }

    Write-Step "Step 1 of 3 - Prepare local runtime manager"
    Write-Note "Downloading a private runtime helper into the project folder."
    Write-Note "This does not modify your system Python or your PATH."

    New-Item -ItemType Directory -Force -Path $RuntimeDownloadsDir | Out-Null
    New-Item -ItemType Directory -Force -Path $RuntimeUvDir | Out-Null

    $downloadUrl = Get-UvDownloadUrl
    $archivePath = Join-Path $RuntimeDownloadsDir "uv.zip"
    $extractPath = Join-Path $RuntimeDownloadsDir "uv-extract"

    if (Test-Path $extractPath) {
        Remove-Item -Recurse -Force $extractPath
    }

    Add-SetupLog "Downloading local uv runtime helper: $downloadUrl"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath

    Expand-Archive -Path $archivePath -DestinationPath $extractPath -Force

    $found = Get-ChildItem -Path $extractPath -Recurse -Filter "uv.exe" -File | Select-Object -First 1
    if ($null -eq $found) {
        throw "Could not find uv.exe after extracting the local runtime helper."
    }

    Copy-Item -Force $found.FullName $uvExe
    Write-Ok "Local runtime helper is ready."
    return $uvExe
}

function Find-LocalRuntimePython {
    if (-not (Test-Path $RuntimePythonDir)) {
        return $null
    }

    $candidate = Get-ChildItem -Path $RuntimePythonDir -Recurse -Filter "python.exe" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\Scripts\\python\.exe$" } |
        Sort-Object FullName |
        Select-Object -First 1

    if ($null -eq $candidate) {
        return $null
    }

    return Test-PythonCommand -Command $candidate.FullName -PrefixArgs @()
}

function Install-LocalPythonRuntime {
    Write-WarnLine "No supported Python 3.10-3.13 with Tkinter was found."
    Write-Note "PHOTO-CAT will download a private Python runtime into .runtime."
    Write-Note "Your installed Python versions will not be modified."
    Write-Host ""

    $existing = Find-LocalRuntimePython
    if ($null -ne $existing) {
        Write-Ok "Local Python runtime found: $($existing.Display)"
        return $existing
    }

    $uvExe = Get-LocalUv

    Write-Step "Step 1 of 3 - Prepare local Python runtime"
    Write-Note "Installing private Python $PreferredRuntimePython into the project folder."

    New-Item -ItemType Directory -Force -Path $RuntimePythonDir | Out-Null

    Add-SetupLog "Installing local Python runtime with uv."
    Add-SetupLog "> $uvExe python install $PreferredRuntimePython --install-dir $RuntimePythonDir"

    & $uvExe python install $PreferredRuntimePython --install-dir $RuntimePythonDir *>> $SetupLog
    $exitCode = $LASTEXITCODE
    Add-SetupLog "uv exit code: $exitCode"

    if ($exitCode -ne 0) {
        throw "Could not install the private PHOTO-CAT Python runtime. See the setup log for details."
    }

    $runtimePython = Find-LocalRuntimePython
    if ($null -eq $runtimePython) {
        throw "The private Python runtime was installed, but PHOTO-CAT could not find a usable python.exe inside .runtime."
    }

    Write-Ok "Local Python runtime is ready: $($runtimePython.Display)"
    return $runtimePython
}

function Ensure-Python {
    Write-Step "Step 1 of 3 - Verify Python"
    Write-ProgressBar -Percent 0 -Detail "[Checking Python]"

    $python = Find-Python
    if ($null -ne $python) {
        Write-ProgressBar -Percent 100 -Detail "[Python ready]" -Complete
        Write-Ok "Python found: $($python.Display)"
        return $python
    }

    Write-ProgressBar -Percent 100 -Detail "[local runtime needed]" -Complete
    return Install-LocalPythonRuntime
}

function Invoke-DetectedPython {
    param(
        [Parameter(Mandatory = $true)]
        $Python,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Python.Command @($Python.PrefixArgs + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Ensure-Libraries {
    param(
        [Parameter(Mandatory = $true)]
        $Python
    )

    Write-Step "Step 2 of 3 - Prepare PHOTO-CAT dependencies"
    Invoke-DetectedPython -Python $Python -Arguments @("-m", "photo_cat.install")
}

function Invoke-VenvPythonModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModuleName
    )

    $venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment Python was not found: $venvPython"
    }

    & $venvPython -m $ModuleName
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE."
    }
}

function Configure-Tool {
    Write-Step "Step 3 of 3 - Open graphical configurator"
    Write-Note "Opening the graphical configurator..."
    Invoke-VenvPythonModule -ModuleName "photo_cat.configure_gui"
}

function Run-Tool {
    Write-Step "Step 3 of 3 - Run PHOTO-CAT pipeline"
    Write-Note "Running the PHOTO-CAT pipeline..."
    Invoke-VenvPythonModule -ModuleName "photo_cat.config_and_run"
}

function Finish-Install {
    Write-Host ""
    Write-Host $TitleLine -ForegroundColor Green
    Write-Host "PHOTO-CAT setup is complete." -ForegroundColor Green
    Write-Host "Run START_WINDOWS.bat again to configure and run." -ForegroundColor Green
    Write-Host $TitleLine -ForegroundColor Green
}

function Finish-Run {
    Write-Host ""
    Write-Host $TitleLine -ForegroundColor Green
    Write-Host "PHOTO-CAT finished successfully." -ForegroundColor Green
    Write-Host "Check the configured output folder for results." -ForegroundColor Green
    Write-Host $TitleLine -ForegroundColor Green
}

try {
    Initialize-SetupLog
    Write-Header

    $Python = Ensure-Python
    Ensure-Libraries -Python $Python

    if ($Mode -eq "INSTALL") {
        Finish-Install
        exit 0
    }

    if ($Mode -eq "RUN") {
        Run-Tool
        Finish-Run
        exit 0
    }

    Configure-Tool

    # The GUI handles Save + run by opening the pipeline in its own console.
    # When the GUI is closed, this launcher closes too instead of asking another question.
    exit 0
}
catch {
    Write-Host ""
    Write-Host $TitleLine -ForegroundColor Red
    Write-Fail "Something failed."
    $message = $_.Exception.Message
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = $_.ToString()
    }
    Write-Host $message
    Write-Host ""
    Write-InfoLine -Label "Detailed setup log" -Value $SetupLog
    Write-Host $TitleLine -ForegroundColor Red
    exit 1
}

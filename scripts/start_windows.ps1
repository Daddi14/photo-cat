param(
    [string]$ModeArg = ""
)

$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectDir

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

function Write-Title {
    Write-Host "============================================================"
    Write-Host "PHOTO-CAT - Windows easy start"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host "This launcher will:"
    Write-Host "  1. Check/install Python if needed."
    Write-Host "  2. Create the local .venv folder."
    Write-Host "  3. Install the required libraries."
    Write-Host "  4. Open the graphical configurator."
    Write-Host "  5. Optionally run the pipeline."
    Write-Host ""
}

function Test-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$PrefixArgs = @()
    )

    try {
        $versionCheck = "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
        & $Command @PrefixArgs -c $versionCheck *> $null

        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Command = $Command
                PrefixArgs = $PrefixArgs
                Display = (($Command, $PrefixArgs) -join " ").Trim()
            }
        }
    }
    catch {
        return $null
    }

    return $null
}

function Find-Python {
    $candidate = Test-PythonCommand -Command "py" -PrefixArgs @("-3")
    if ($null -ne $candidate) {
        return $candidate
    }

    $candidate = Test-PythonCommand -Command "python" -PrefixArgs @()
    if ($null -ne $candidate) {
        return $candidate
    }

    $candidate = Test-PythonCommand -Command "python3" -PrefixArgs @()
    if ($null -ne $candidate) {
        return $candidate
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

function Install-PythonWithWinget {
    if ($null -eq (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget was not found. Trying the official Python installer instead."
        return $false
    }

    Write-Host "Installing Python with winget..."
    Write-Host "This can take a few minutes."
    Write-Host ""

    & winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    return ($LASTEXITCODE -eq 0)
}

function Install-PythonWithOfficialInstaller {
    $pythonVersion = "3.12.10"
    $installerPath = Join-Path $env:TEMP "python-$pythonVersion-amd64.exe"
    $pythonUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"

    Write-Host ""
    Write-Host "Downloading Python from python.org..."
    Write-Host $pythonUrl
    Write-Host ""

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath

    Write-Host ""
    Write-Host "Installing Python for the current user..."
    Write-Host ""

    $args = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_launcher=1",
        "InstallLauncherAllUsers=0",
        "Include_pip=1",
        "Include_test=0"
    )

    $process = Start-Process -FilePath $installerPath -ArgumentList $args -Wait -PassThru
    return ($process.ExitCode -eq 0)
}

function Ensure-Python {
    $python = Find-Python
    if ($null -ne $python) {
        Write-Host "Python found: $($python.Display)"
        return $python
    }

    Write-Host "Python was not found."
    Write-Host "I will try to install Python automatically."
    Write-Host ""

    [void](Install-PythonWithWinget)
    Refresh-PythonPath

    $python = Find-Python
    if ($null -ne $python) {
        Write-Host ""
        Write-Host "Python installed successfully."
        Write-Host "Python found: $($python.Display)"
        return $python
    }

    [void](Install-PythonWithOfficialInstaller)
    Refresh-PythonPath

    $python = Find-Python
    if ($null -ne $python) {
        Write-Host ""
        Write-Host "Python installed successfully."
        Write-Host "Python found: $($python.Display)"
        return $python
    }

    throw @"
Python could not be installed automatically.

Manual fix:
1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. During installation, tick "Add python.exe to PATH".
3. Close this window.
4. Double-click START_WINDOWS.bat again.
"@
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

    Write-Host ""
    Write-Host "Checking/installing the local virtual environment and libraries..."
    Write-Host ""

    Invoke-DetectedPython -Python $Python -Arguments @("src\install.py")
}

function Invoke-VenvPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath
    )

    $venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment Python was not found: $venvPython"
    }

    & $venvPython $ScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE."
    }
}

function Configure-Tool {
    Write-Host ""
    Write-Host "Opening the graphical configurator..."
    Write-Host ""

    Invoke-VenvPython -ScriptPath "src\configure_gui.py"
}

function Run-Tool {
    Write-Host ""
    Write-Host "Running the pipeline with the local virtual environment..."
    Write-Host ""

    Invoke-VenvPython -ScriptPath "src\config_and_run.py"
}

Write-Title
$Python = Ensure-Python
Ensure-Libraries -Python $Python

if ($Mode -eq "INSTALL") {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Installation completed successfully."
    Write-Host "You can now run START_WINDOWS.bat again to configure and run."
    Write-Host "============================================================"
    exit 0
}

if ($Mode -eq "RUN") {
    Run-Tool
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Finished successfully."
    Write-Host "Check the output folder for results."
    Write-Host "============================================================"
    exit 0
}

Configure-Tool

# The GUI handles Save + run by opening the pipeline in its own console.
# When the GUI is closed, this launcher closes too instead of asking another question.
exit 0

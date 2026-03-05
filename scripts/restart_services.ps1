param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Stop-MatchingProcesses {
    param(
        [string[]]$Patterns
    )

    try {
        $procs = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            foreach ($p in $Patterns) {
                if ($cmd -like "*$p*") { return $true }
            }
            return $false
        }
    } catch {
        # Some environments deny CIM process queries; continue restart without pre-kill.
        return
    }

    foreach ($proc in $procs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        } catch {
            # Ignore races where process already exited.
        }
    }
}

Set-Location $ProjectRoot

function Start-PythonModule {
    param(
        [string[]]$Args,
        [string]$StdOutPath,
        [string]$StdErrPath
    )

    try {
        Start-Process -FilePath "python" -ArgumentList $Args -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdOutPath -RedirectStandardError $StdErrPath -ErrorAction Stop | Out-Null
        return
    } catch {
        $pyArgs = @("-3") + $Args
        Start-Process -FilePath "py" -ArgumentList $pyArgs -WorkingDirectory $ProjectRoot -RedirectStandardOutput $StdOutPath -RedirectStandardError $StdErrPath -ErrorAction Stop | Out-Null
    }
}

# Give the current UI request a moment to return before terminating services.
Start-Sleep -Seconds 2

Stop-MatchingProcesses -Patterns @(
    "uvicorn app.backend.main:app",
    "streamlit run app/frontend/main.py",
    "streamlit run app.py"
)

Start-PythonModule -Args @(
    "-m", "uvicorn", "app.backend.main:app", "--host", "127.0.0.1", "--port", "8000"
) -StdOutPath (Join-Path $ProjectRoot "restart_backend_out.log") -StdErrPath (Join-Path $ProjectRoot "restart_backend_err.log")
Start-Sleep -Seconds 4
Start-PythonModule -Args @(
    "-m", "streamlit", "run", "app/frontend/main.py",
    "--server.port", "8501",
    "--server.fileWatcherType", "none",
    "--server.runOnSave", "false"
) -StdOutPath (Join-Path $ProjectRoot "restart_frontend_out.log") -StdErrPath (Join-Path $ProjectRoot "restart_frontend_err.log")

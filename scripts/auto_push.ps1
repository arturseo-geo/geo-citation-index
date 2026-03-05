[CmdletBinding()]
param(
    [ValidateRange(1, 1440)]
    [int]$IntervalMinutes = 5,

    [switch]$RunTests,

    [string]$Branch = "main",

    [string]$MessagePrefix = "auto-sync",

    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-GitExecutable {
    $candidates = @(
        "git",
        "C:\Program Files\Git\cmd\git.exe",
        "C:\Program Files\Git\bin\git.exe"
    )

    foreach ($candidate in $candidates) {
        try {
            if ($candidate -eq "git") {
                $cmd = Get-Command git -ErrorAction Stop
                return $cmd.Source
            }

            if (Test-Path $candidate) {
                return $candidate
            }
        } catch {
            continue
        }
    }

    throw "Git executable not found. Install Git or add it to PATH."
}

function Invoke-Git {
    param(
        [string[]]$GitArgs,
        [switch]$AllowFailure
    )

    & $script:GitExe -C $script:RepoPath @GitArgs
    $exit = $LASTEXITCODE

    if (-not $AllowFailure -and $exit -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $exit"
    }

    return $exit
}

function Run-ValidationTests {
    Write-Host "Running test gate..." -ForegroundColor Cyan
    $testArgs = @(
        "-m", "unittest", "-v",
        "test_competitor_benchmarking.py",
        "test_schema_completeness.py",
        "test_pdf_filename.py"
    )

    & python @testArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Tests failed. Skipping commit/push for this cycle."
        return $false
    }

    Write-Host "Test gate passed." -ForegroundColor Green
    return $true
}

function Invoke-AutoPushCycle {
    Write-Host ""
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Checking for changes..." -ForegroundColor Yellow

    $currentBranch = (& $script:GitExe -C $script:RepoPath rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to detect current git branch."
    }

    if ($currentBranch -ne $Branch) {
        Write-Warning "Current branch is '$currentBranch' but target branch is '$Branch'. Skipping this cycle."
        return
    }

    $status = (& $script:GitExe -C $script:RepoPath status --porcelain).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read git status."
    }

    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Host "No changes detected." -ForegroundColor DarkGray
        return
    }

    if ($RunTests) {
        $ok = Run-ValidationTests
        if (-not $ok) {
            return
        }
    }

    Invoke-Git -GitArgs @("add", "-A")

    # Skip commit if staging produced no changes (e.g., only ignored files changed).
    $stagedExit = Invoke-Git -GitArgs @("diff", "--cached", "--quiet") -AllowFailure
    if ($stagedExit -eq 0) {
        Write-Host "No staged changes after git add (likely ignored-only changes)." -ForegroundColor DarkGray
        return
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $message = "$MessagePrefix $timestamp"

    Invoke-Git -GitArgs @("commit", "-m", $message)
    Invoke-Git -GitArgs @("push", "origin", $Branch)

    Write-Host "Pushed commit to origin/$Branch with message: $message" -ForegroundColor Green
}

try {
    $script:GitExe = Get-GitExecutable
    Write-Host "Using git: $GitExe" -ForegroundColor DarkGray
    Write-Host "Repo path: $RepoPath" -ForegroundColor DarkGray
    Write-Host "Interval: $IntervalMinutes minute(s) | Branch: $Branch | RunTests: $RunTests" -ForegroundColor DarkGray

    do {
        Invoke-AutoPushCycle

        if ($Once) {
            break
        }

        Start-Sleep -Seconds ($IntervalMinutes * 60)
    } while ($true)
}
catch {
    Write-Error $_
    exit 1
}

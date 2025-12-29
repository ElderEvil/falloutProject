# Quick start script for running Locust performance tests (PowerShell)
# Usage: .\backend\locust\run_tests.ps1 [mode]

param(
    [Parameter(Position=0)]
    [ValidateSet('web', 'headless', 'baseline', 'stress', 'quick')]
    [string]$Mode = 'web',

    [string]$HostUrl = $env:LOCUST_HOST ?? "http://localhost:8000",
    [int]$Users = [int]($env:LOCUST_USERS ?? 10),
    [int]$SpawnRate = [int]($env:LOCUST_SPAWN_RATE ?? 2),
    [string]$RunTime = $env:LOCUST_RUN_TIME ?? "5m"
)

Write-Host "======================================"
Write-Host "Fallout Shelter Performance Tests"
Write-Host "======================================"
Write-Host "Host: $HostUrl"
Write-Host "Users: $Users"
Write-Host "Spawn Rate: $SpawnRate/s"
Write-Host "Run Time: $RunTime"
Write-Host "======================================"
Write-Host ""

# Load environment variables from .env.locust if it exists
$EnvFile = "backend\locust\.env.locust"
if (Test-Path $EnvFile) {
    Write-Host "Loading configuration from .env.locust"
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^([^#].+?)=(.+)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Item -Path "env:$name" -Value $value
        }
    }
    Write-Host ""
}

# Generate timestamp for report filenames
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

switch ($Mode) {
    'web' {
        Write-Host "Starting Locust Web UI..."
        Write-Host "Open http://localhost:8089 in your browser"
        Write-Host ""
        locust -f backend\locust\locustfile.py --host $HostUrl
    }

    'headless' {
        Write-Host "Running headless performance test..."
        locust -f backend\locust\locustfile.py `
            --host $HostUrl `
            --users $Users `
            --spawn-rate $SpawnRate `
            --run-time $RunTime `
            --headless `
            --html "locust_report_$Timestamp.html"
    }

    'baseline' {
        Write-Host "Running baseline test (10 users, 10 minutes)..."
        locust -f backend\locust\locustfile.py `
            --host $HostUrl `
            --users 10 `
            --spawn-rate 2 `
            --run-time 10m `
            --headless `
            --html "baseline_report_$Timestamp.html" `
            --csv "baseline_data_$Timestamp"
    }

    'stress' {
        Write-Host "Running stress test (100 users, 15 minutes)..."
        locust -f backend\locust\locustfile.py `
            --host $HostUrl `
            --users 100 `
            --spawn-rate 10 `
            --run-time 15m `
            --headless `
            --html "stress_report_$Timestamp.html" `
            --csv "stress_data_$Timestamp"
    }

    'quick' {
        Write-Host "Running quick test (5 users, 2 minutes)..."
        locust -f backend\locust\locustfile.py `
            --host $HostUrl `
            --users 5 `
            --spawn-rate 1 `
            --run-time 2m `
            --headless `
            --only-summary
    }

    default {
        Write-Host "Usage: .\run_tests.ps1 [mode]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Modes:"
        Write-Host "  web      - Start with web UI (default)"
        Write-Host "  headless - Run without UI"
        Write-Host "  baseline - Run baseline performance test"
        Write-Host "  stress   - Run stress test with high load"
        Write-Host "  quick    - Quick smoke test"
        Write-Host ""
        Write-Host "Environment variables:"
        Write-Host "  LOCUST_HOST        - API host URL"
        Write-Host "  LOCUST_USERS       - Number of simulated users"
        Write-Host "  LOCUST_SPAWN_RATE  - Users spawned per second"
        Write-Host "  LOCUST_RUN_TIME    - Test duration (e.g., 5m, 1h)"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\run_tests.ps1 web"
        Write-Host "  .\run_tests.ps1 quick"
        Write-Host "  .\run_tests.ps1 baseline -HostUrl http://localhost:8000"
        Write-Host '  $env:LOCUST_USERS=50; .\run_tests.ps1 headless'
        exit 1
    }
}

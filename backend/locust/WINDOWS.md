# Locust on Windows - Quick Guide

This guide is specifically for Windows developers using PowerShell.

## 🪟 Quick Start for Windows

### Step 1: Install Locust

```powershell
cd backend
uv sync --group perf
# or
pip install locust
```

### Step 2: Setup Test Data

```powershell
# Make sure your API and database are running first!
python -m locust.setup_test_data
```

### Step 3: Run Tests

```powershell
# Start Web UI (recommended for first time)
.\backend\locust\run_tests.ps1 web

# Then open http://localhost:8089 in your browser
```

## 🎯 Available Commands

```powershell
# Interactive web interface
.\backend\locust\run_tests.ps1 web

# Quick 2-minute smoke test
.\backend\locust\run_tests.ps1 quick

# 10-minute baseline test
.\backend\locust\run_tests.ps1 baseline

# 15-minute stress test (100 users)
.\backend\locust\run_tests.ps1 stress

# Custom headless test
.\backend\locust\run_tests.ps1 headless -Users 20 -RunTime "5m"
```

## 🔧 Configuration

### Environment Variables

Set environment variables in PowerShell:

```powershell
$env:LOCUST_HOST = "http://localhost:8000"
$env:LOCUST_TEST_USER_EMAIL = "test@test.com"
$env:LOCUST_TEST_USER_PASSWORD = "testpassword"
```

Or create a `.env.locust` file:

```powershell
Copy-Item .env.example .env.locust
notepad .env.locust  # Edit with your settings
```

### Custom Parameters

```powershell
# Set custom parameters
.\backend\locust\run_tests.ps1 headless -HostUrl "http://localhost:8000" -Users 50 -RunTime "10m"

# Using environment variables
$env:LOCUST_USERS = 50
$env:LOCUST_RUN_TIME = "10m"
.\backend\locust\run_tests.ps1 headless
```

## 📊 Direct Locust Commands

You can also use locust directly:

```powershell
# Web UI
locust -f backend\locust\locustfile.py --host http://localhost:8000

# Headless test
locust -f backend\locust\locustfile.py `
    --host http://localhost:8000 `
    --users 10 `
    --spawn-rate 2 `
    --run-time 5m `
    --headless `
    --html report.html
```

**Note:** Use backtick `` ` `` for line continuation in PowerShell (not backslash `\`).

## 🎨 PowerShell Script Features

The `run_tests.ps1` script provides:

- ✅ Parameter validation
- ✅ Automatic timestamp for reports
- ✅ Environment variable support
- ✅ Color-coded output
- ✅ Help message with examples

### Script Parameters

```powershell
# View all parameters
Get-Help .\backend\locust\run_tests.ps1 -Detailed

# Use named parameters
.\backend\locust\run_tests.ps1 -Mode baseline -HostUrl "http://localhost:8000"
```

## 🐛 Windows-Specific Troubleshooting

### Execution Policy

If you get an execution policy error:

```powershell
# Check current policy
Get-ExecutionPolicy

# Allow local scripts (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or run with bypass (one-time)
powershell -ExecutionPolicy Bypass -File .\backend\locust\run_tests.ps1 web
```

### Path Issues

Use backslashes or quotes for paths:

```powershell
# These work on Windows
locust -f backend\locust\locustfile.py
locust -f "backend/locust/locustfile.py"
```

### Line Continuation

PowerShell uses backtick (`` ` ``) for line continuation:

```powershell
# Correct (backtick)
locust -f backend\locust\locustfile.py `
    --users 10 `
    --spawn-rate 2

# Wrong (backslash - this is for bash/Linux)
locust -f backend\locust\locustfile.py
--users 10 \
--spawn-rate 2
```

### Port Already in Use

If port 8089 is already in use:

```powershell
# Find process using port 8089
netstat -ano | findstr :8089

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use a different port
locust -f backend\locust\locustfile.py --host http://localhost:8000 --web-port 8090
```

## 💡 Tips for Windows Users

1. **Use Windows Terminal** - Better experience than Command Prompt
2. **PowerShell 7+** - More features than Windows PowerShell 5.1
   ```powershell
   winget install Microsoft.PowerShell
   ```
3. **VS Code Terminal** - Integrated terminal in your editor
4. **Path Autocomplete** - Use Tab key to autocomplete paths
5. **History** - Use arrow keys or `Get-History` to see previous commands

## 🚀 Example Workflow

```powershell
# 1. Start your API (in one terminal)
cd backend
uvicorn main:app --reload

# 2. In another terminal, setup test data (first time only)
python -m locust.setup_test_data

# 3. Run quick test to verify everything works
.\backend\locust\run_tests.ps1 quick

# 4. Run baseline test
.\backend\locust\run_tests.ps1 baseline

# 5. Check the generated HTML report
Invoke-Item baseline_report_*.html  # Opens in default browser
```

## 📈 Viewing Results

```powershell
# Open HTML report in browser
Invoke-Item locust_report_*.html

# Open latest report
$latest = Get-ChildItem -Filter "*report*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Invoke-Item $latest.FullName

# View CSV data
Import-Csv baseline_data_*_stats.csv | Format-Table
```

## 🔗 Resources

- Main README: [README.md](README.md)
- Setup Guide: [SETUP.md](SETUP.md)
- Quick Reference: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- Locust Docs: https://docs.locust.io/

## ❓ Need Help?

Common issues are documented in the main [README.md](README.md) under the Troubleshooting section.

For Windows-specific PowerShell questions, check out:

- PowerShell documentation: https://learn.microsoft.com/powershell/
- Windows Terminal: https://github.com/microsoft/terminal

---

**Happy testing on Windows!** 🪟🚀

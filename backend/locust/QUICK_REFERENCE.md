# Locust Quick Reference

## One-Line Commands

### Linux/Mac
```bash
# Setup test data (first time only)
python -m locust.setup_test_data

# Start web UI
./backend/locust/run_tests.sh web

# Quick 2-minute test
./backend/locust/run_tests.sh quick

# 10-minute baseline
./backend/locust/run_tests.sh baseline

# Stress test (100 users)
./backend/locust/run_tests.sh stress

# Custom headless test
locust -f backend/locust/locustfile.py --host http://localhost:8000 \
    --users 20 --spawn-rate 5 --run-time 5m --headless
```

### Windows (PowerShell)
```powershell
# Setup test data (first time only)
python -m locust.setup_test_data

# Start web UI
.\backend\locust\run_tests.ps1 web

# Quick 2-minute test
.\backend\locust\run_tests.ps1 quick

# 10-minute baseline
.\backend\locust\run_tests.ps1 baseline

# Stress test (100 users)
.\backend\locust\run_tests.ps1 stress

# Custom headless test
locust -f backend\locust\locustfile.py --host http://localhost:8000 `
    --users 20 --spawn-rate 5 --run-time 5m --headless
```

## Common Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--users` | Number of concurrent users | `--users 50` |
| `--spawn-rate` | Users spawned/sec | `--spawn-rate 10` |
| `--run-time` | Test duration | `--run-time 10m` |
| `--headless` | Run without UI | `--headless` |
| `--html` | Generate report | `--html report.html` |
| `--csv` | Export CSV data | `--csv results` |
| `--host` | API URL | `--host http://localhost:8000` |

## User Types

| Type | Weight | Behavior |
|------|--------|----------|
| CasualPlayer | 70% | Read-heavy, occasional writes |
| ActivePlayer | 20% | Balanced reads/writes |
| PowerUser | 10% | Heavy writes, fast actions |
| GamePlayer | - | Game mechanics focused |
| ReadOnlyPlayer | - | Pure reads, no mutations |

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| P95 (reads) | < 1000ms | < 2000ms |
| P95 (writes) | < 2000ms | < 3000ms |
| Success rate | > 99% | > 90% |
| Game tick | < 5000ms | < 10000ms |

## File Structure

```
locust/
├── locustfile.py       # Main scenarios
├── config.py           # Configuration
├── utils.py            # Helpers
├── tasks/              # Task definitions
│   ├── auth_tasks.py
│   ├── vault_tasks.py
│   ├── game_tasks.py
│   └── dweller_tasks.py
├── run_tests.sh        # Quick launcher (Linux/Mac)
└── run_tests.ps1       # Quick launcher (Windows)
```

## Environment Variables

**Linux/Mac:**
```bash
export LOCUST_HOST=http://localhost:8000
export LOCUST_TEST_USER_EMAIL=test@test.com
export LOCUST_TEST_USER_PASSWORD=testpassword
export LOCUST_USERS=10
export LOCUST_SPAWN_RATE=2
export LOCUST_RUN_TIME=5m
```

**Windows (PowerShell):**
```powershell
$env:LOCUST_HOST="http://localhost:8000"
$env:LOCUST_TEST_USER_EMAIL="test@test.com"
$env:LOCUST_TEST_USER_PASSWORD="testpassword"
$env:LOCUST_USERS=10
$env:LOCUST_SPAWN_RATE=2
$env:LOCUST_RUN_TIME="5m"
```

## Web UI

1. Start: `./backend/locust/run_tests.sh web` (or `.\backend\locust\run_tests.ps1 web` on Windows)
2. Open: http://localhost:8089
3. Configure: Users, spawn rate, host
4. Monitor: Charts, Statistics, Failures tabs

## Distributed Testing

```bash
# Master
locust -f locustfile.py --master --host http://api.com

# Workers (run on other machines)
locust -f locustfile.py --worker --master-host=<master-ip>
```

## Report Generation

```bash
# HTML report
locust ... --html report.html

# CSV data
locust ... --csv results
# Creates: results_stats.csv, results_failures.csv, results_exceptions.csv
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 401 errors | Run `setup_test_data.py` |
| Connection refused | Start API: `uvicorn main:app` |
| High failures | Reduce `--users` count |
| Slow tests | Check DB performance |

## Key Metrics

- **RPS**: Requests per second
- **P50**: Median response time
- **P95**: 95th percentile (target: < 1s)
- **P99**: 99th percentile (< 2s)
- **Max**: Maximum response time
- **Failures**: Error rate

## Best Practices

1. ✅ Start with small user count (5-10)
2. ✅ Use staging, not production
3. ✅ Monitor system resources
4. ✅ Run baseline before optimizations
5. ✅ Automate in CI/CD
6. ❌ Don't test without test user setup
7. ❌ Don't run on production database
8. ❌ Don't ignore warning signs

## Quick Wins

1. Add database indexes
2. Enable Redis caching
3. Optimize N+1 queries
4. Add connection pooling
5. Implement pagination
6. Add rate limiting
7. Use background tasks
8. Enable compression

---

**Need help?** See `README.md` for full documentation.

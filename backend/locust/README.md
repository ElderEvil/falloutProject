# Fallout Shelter API - Performance Testing with Locust

This directory contains performance and load testing scenarios for the Fallout Shelter API using [Locust](https://locust.io/).

## 📋 Prerequisites

1. **Install Locust**:
   ```bash
   # From the backend directory
   cd backend
   uv sync --group perf
   # or
   pip install locust
   ```

2. **Test Environment**:
   - Running instance of the Fallout Shelter API
   - Test database with at least one test user account
   - Recommended: Use a dedicated test/staging environment, NOT production

3. **Test User Setup**:
   Create test users in your database:
   ```bash
   # Example using initial_data.py or admin interface
   python initial_data.py  # Adjust as needed
   ```

## 🚀 Quick Start

### 1. Configure Environment

Copy the example environment file and configure it:

**Linux/Mac:**
```bash
cp .env.example .env.locust
# Edit .env.locust with your test credentials
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env.locust
# Edit .env.locust with your test credentials
```

### 2. Start Your API

Make sure your API is running:

**Linux/Mac:**
```bash
cd backend
uvicorn main:app --reload
```

**Windows (PowerShell):**
```powershell
cd backend
uvicorn main:app --reload
```

### 3. Run Locust Web UI

Basic test with web interface:

**Linux/Mac:**
```bash
./backend/locust/run_tests.sh web
# or
locust -f backend/locust/locustfile.py --host http://localhost:8000
```

**Windows (PowerShell):**
```powershell
.\backend\locust\run_tests.ps1 web
# or
locust -f backend\locust\locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 in your browser and configure:
- **Number of users**: Start with 10
- **Spawn rate**: 2 users/second
- **Host**: http://localhost:8000

### 4. Run Headless Mode

For automated testing without UI:

**Linux/Mac:**
```bash
./backend/locust/run_tests.sh headless
# or
locust -f backend/locust/locustfile.py \
    --host http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 5m \
    --headless \
    --html report.html
```

**Windows (PowerShell):**
```powershell
.\backend\locust\run_tests.ps1 headless
# or
locust -f backend\locust\locustfile.py `
    --host http://localhost:8000 `
    --users 10 `
    --spawn-rate 2 `
    --run-time 5m `
    --headless `
    --html report.html
```

## 👥 User Scenarios

The test suite includes different user behaviors:

### CasualPlayer (70% of traffic)
- Mostly reads data (vaults, dwellers, game state)
- Occasional game actions
- Rarely creates new content
- Wait time: 1-3 seconds between actions

### ActivePlayer (20% of traffic)
- Balanced mix of reads and writes
- Frequently creates vaults and dwellers
- Regular game tick triggers
- Wait time: 1-3 seconds between actions

### PowerUser (10% of traffic)
- Heavy operations
- Creates lots of content
- Stress tests the system
- Wait time: 0.5-1.5 seconds (faster)

### GamePlayer
- Focuses on game mechanics
- Triggers ticks, checks incidents
- Less CRUD operations
- Wait time: 1-3 seconds between actions

### ReadOnlyPlayer
- Only views data, no mutations
- Useful for caching tests
- Pure read load

## 📊 Test Scenarios

### Baseline Test
Establish performance baseline:

**Linux/Mac:**
```bash
./backend/locust/run_tests.sh baseline
```

**Windows:**
```powershell
.\backend\locust\run_tests.ps1 baseline
```

### Stress Test
Find breaking point:

**Linux/Mac:**
```bash
./backend/locust/run_tests.sh stress
```

**Windows:**
```powershell
.\backend\locust\run_tests.ps1 stress
```

### Spike Test
Test sudden traffic bursts:

**Linux/Mac:**
```bash
# Start with few users, then manually increase in UI
./backend/locust/run_tests.sh web
```

**Windows:**
```powershell
# Start with few users, then manually increase in UI
.\backend\locust\run_tests.ps1 web
```

### Endurance Test
Test sustained load:

**Linux/Mac:**
```bash
locust -f backend/locust/locustfile.py \
    --host http://localhost:8000 \
    --users 20 \
    --spawn-rate 2 \
    --run-time 60m \
    --headless
```

**Windows:**
```powershell
locust -f backend\locust\locustfile.py `
    --host http://localhost:8000 `
    --users 20 `
    --spawn-rate 2 `
    --run-time 60m `
    --headless
```

### Specific User Type
Test a specific user behavior:

**Linux/Mac:**
```bash
locust -f backend/locust/locustfile.py \
    --host http://localhost:8000 \
    CasualPlayer \
    --users 20 \
    --spawn-rate 5
```

**Windows:**
```powershell
locust -f backend\locust\locustfile.py `
    --host http://localhost:8000 `
    CasualPlayer `
    --users 20 `
    --spawn-rate 5
```

## 📈 Performance Metrics

### Key Metrics to Monitor

1. **Response Times**:
   - Median (50th percentile)
   - 95th percentile (P95)
   - 99th percentile (P99)
   - Maximum

2. **Throughput**:
   - Requests per second (RPS)
   - Failures per second

3. **Success Rate**:
   - Should be > 99% under normal load
   - Check error rates and types

### Recommended Thresholds

- **P95 Response Time**: < 1000ms for reads, < 2000ms for writes
- **P99 Response Time**: < 2000ms for reads, < 3000ms for writes
- **Success Rate**: > 99%
- **Game Tick Processing**: < 5 seconds per vault

## 🔍 Analyzing Results

### During Test (Web UI)

1. Open http://localhost:8089
2. Monitor:
   - Charts tab: Real-time graphs
   - Statistics tab: Per-endpoint metrics
   - Failures tab: Error details

### After Test (Reports)

Generate HTML report:
```bash
locust -f backend/locust/locustfile.py \
    --host http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 10m \
    --headless \
    --html performance_report.html \
    --csv performance_data
```

This generates:
- `performance_report.html` - Visual report
- `performance_data_stats.csv` - Statistics
- `performance_data_failures.csv` - Failure details
- `performance_data_exceptions.csv` - Exception details

## 🛠️ Advanced Usage

### Custom Task Weights

Edit task weights in `locustfile.py` to adjust behavior:

```python
tasks = {
    VaultTaskSet: 5,    # 50% vault operations
    DwellerTaskSet: 3,  # 30% dweller operations
    GameTaskSet: 2,     # 20% game operations
}
```

### Distributed Load Testing

Run Locust across multiple machines:

**Master:**
```bash
locust -f backend/locust/locustfile.py \
    --master \
    --host http://your-api-host.com
```

**Workers:**
```bash
locust -f backend/locust/locustfile.py \
    --worker \
    --master-host=<master-ip>
```

### Custom Environment Variables

Override config in runtime:
```bash
LOCUST_TEST_USER_EMAIL=custom@user.com \
LOCUST_HOST=https://staging.example.com \
locust -f backend/locust/locustfile.py
```

## 🎯 Optimization Tips

Based on test results, consider:

1. **Database**:
   - Add indexes on frequently queried fields
   - Optimize connection pooling
   - Consider read replicas

2. **Caching**:
   - Add Redis caching for read-heavy endpoints
   - Cache game state calculations
   - Implement HTTP caching headers

3. **API**:
   - Add rate limiting
   - Implement pagination for list endpoints
   - Optimize N+1 queries

4. **Game Loop**:
   - Batch vault processing
   - Use background tasks (Celery)
   - Implement queue for tick processing

## 📝 Task Sets

### AuthTaskSet
- Login operations
- Token validation

### VaultTaskSet
- List vaults (high weight)
- Get vault details
- Create vaults
- Get rooms/dwellers for vault

### GameTaskSet
- Get game state
- Manual tick trigger
- Pause/resume vault
- Get incidents, quests, objectives

### DwellerTaskSet
- List dwellers
- Get dweller details
- Create dwellers
- Update dwellers

## 🐛 Troubleshooting

### Common Issues

**401 Unauthorized errors:**
- Check test user credentials in .env.locust
- Verify user exists in test database
- Check token expiration settings

**Connection errors:**
- Verify API is running
- Check host URL
- Verify firewall/network settings

**High failure rate:**
- Reduce number of users
- Increase wait time
- Check API logs for errors

**Slow response times:**
- Check database performance
- Monitor CPU/memory usage
- Review slow query logs

## 📚 Resources

- [Locust Documentation](https://docs.locust.io/)
- [Writing a Locustfile](https://docs.locust.io/en/stable/writing-a-locustfile.html)
- [Distributed Load Testing](https://docs.locust.io/en/stable/running-distributed.html)

## 🔄 CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Performance Tests

on:
  pull_request:
    branches: [main]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install locust
      - run: docker-compose up -d  # Start services
      - run: |
          locust -f backend/locust/locustfile.py \
            --host http://localhost:8000 \
            --users 10 \
            --spawn-rate 2 \
            --run-time 5m \
            --headless \
            --only-summary
```

## 📊 Example Results

After running tests, you should see output like:

```
Type     Name                                    # reqs      # fails  |    Avg     Min     Max  Median  |   req/s failures/s
--------|----------------------------------------|-------|-----------|-------|-------|-------|-------|--------|-----------
GET      /api/v1/vaults/                          1234         0     |     45      12     234      41  |   12.3        0.00
POST     /api/v1/game/vaults/{id}/tick             234         2     |    156      45     892     134  |    2.3        0.02
...
```

Look for:
- ✅ Low failure rate (< 1%)
- ✅ Consistent response times
- ✅ Stable throughput
- ⚠️ High P99 times (investigate)
- ❌ Increasing failures (capacity issue)

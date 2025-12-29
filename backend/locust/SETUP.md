# Locust Performance Testing Setup

## ✅ Installation Complete

The Locust performance testing suite has been successfully set up for your Fallout Shelter API!

## 📁 Structure

```
backend/locust/
├── __init__.py                 # Package marker
├── locustfile.py              # Main test scenarios (5 user types)
├── config.py                  # Configuration management
├── utils.py                   # Helper functions and mixins
├── setup_test_data.py         # Test data creation script
├── run_tests.sh               # Quick start script (Linux/Mac)
├── run_tests.ps1              # Quick start script (Windows)
├── .env.example               # Environment template
├── .gitignore                 # Ignore test reports
├── README.md                  # Comprehensive documentation
├── SETUP.md                   # This file
└── tasks/
    ├── __init__.py
    ├── auth_tasks.py          # Authentication tests
    ├── vault_tasks.py         # Vault CRUD operations
    ├── game_tasks.py          # Game loop mechanics
    └── dweller_tasks.py       # Dweller management
```

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

**Linux/Mac:**
```bash
cd backend
uv sync --group perf
# or
pip install locust
```

**Windows:**
```powershell
cd backend
uv sync --group perf
# or
pip install locust
```

### Step 2: Setup Test Data

**All platforms:**
```bash
# Make sure your API and database are running
python -m locust.setup_test_data
```

This creates:
- Test user account (test@test.com / testpassword)
- 5 initial vaults with rooms and resources

### Step 3: Run Tests

**Option A: Web UI (Recommended for first time)**

Linux/Mac:
```bash
./backend/locust/run_tests.sh web
```

Windows:
```powershell
.\backend\locust\run_tests.ps1 web
```

Then open http://localhost:8089 in your browser.

**Option B: Quick Headless Test**

Linux/Mac:
```bash
./backend/locust/run_tests.sh quick
```

Windows:
```powershell
.\backend\locust\run_tests.ps1 quick
```

## 📊 Available Test Scenarios

### User Types (automatically distributed)

1. **CasualPlayer** (70% of users)
   - Browsing and viewing data
   - Occasional actions
   - Simulates typical player behavior

2. **ActivePlayer** (20% of users)
   - Creating vaults and dwellers
   - Regular game interactions
   - Balanced read/write operations

3. **PowerUser** (10% of users)
   - Heavy content creation
   - Rapid actions (0.5-1.5s wait time)
   - Stress tests the system

4. **GamePlayer**
   - Focuses on game mechanics
   - Triggers ticks and events
   - Quest/incident management

5. **ReadOnlyPlayer**
   - Pure read operations
   - Tests caching effectiveness
   - No mutations

### Test Modes

**Linux/Mac:**
```bash
./backend/locust/run_tests.sh web       # Web UI (interactive)
./backend/locust/run_tests.sh headless  # Headless (automated)
./backend/locust/run_tests.sh baseline  # Baseline (10 users, 10 min)
./backend/locust/run_tests.sh stress    # Stress test (100 users, 15 min)
./backend/locust/run_tests.sh quick     # Quick smoke test (5 users, 2 min)
```

**Windows:**
```powershell
.\backend\locust\run_tests.ps1 web       # Web UI (interactive)
.\backend\locust\run_tests.ps1 headless  # Headless (automated)
.\backend\locust\run_tests.ps1 baseline  # Baseline (10 users, 10 min)
.\backend\locust\run_tests.ps1 stress    # Stress test (100 users, 15 min)
.\backend\locust\run_tests.ps1 quick     # Quick smoke test (5 users, 2 min)
```

## 🎯 What Gets Tested

### API Endpoints (88 total)

- ✅ **Authentication**: Login, token validation
- ✅ **Vaults**: List, create, details, rooms, dwellers
- ✅ **Game Loop**: Game state, manual ticks, pause/resume
- ✅ **Dwellers**: CRUD operations, assignments
- ✅ **Game Mechanics**: Incidents, quests, objectives
- ✅ **Resources**: Production/consumption simulation

### Performance Metrics

- **Response Times**: P50, P95, P99, Max
- **Throughput**: Requests per second
- **Success Rate**: Error percentage
- **Concurrent Users**: Scalability testing

## 📈 Expected Results

### Baseline Performance (10 users)

| Endpoint Type | Target P95 | Target Success Rate |
|--------------|-----------|---------------------|
| Read (GET) | < 1000ms | > 99% |
| Write (POST/PUT) | < 2000ms | > 99% |
| Game Tick | < 5000ms | > 95% |

### Stress Test (100 users)

Monitor for:
- Response time degradation
- Error rate increases
- Database connection pool exhaustion
- Memory leaks

## 🔧 Configuration

### Environment Variables

Create `backend/locust/.env.locust`:

```env
LOCUST_HOST=http://localhost:8000
LOCUST_TEST_USER_EMAIL=test@test.com
LOCUST_TEST_USER_PASSWORD=testpassword
```

### Custom Test Parameters

```bash
# Custom user count and duration
LOCUST_USERS=50 LOCUST_RUN_TIME=10m ./backend/locust/run_tests.sh headless

# Different API host
LOCUST_HOST=https://staging.api.com ./backend/locust/run_tests.sh web
```

## 📊 Interpreting Results

### Good Signs ✅
- P95 response time < 1 second for reads
- P95 response time < 2 seconds for writes
- Success rate > 99%
- Stable performance over time
- Linear scaling with user count

### Warning Signs ⚠️
- P95 > 2 seconds
- P99 > 5 seconds
- Success rate < 95%
- Increasing response times over time
- High database connection wait times

### Critical Issues ❌
- Success rate < 90%
- Response times > 10 seconds
- Crashes or OOM errors
- Database connection failures
- Exponential degradation

## 🛠️ Optimization Recommendations

Based on typical results:

1. **Add Database Indexes**
   - vault_id, user_id on dwellers
   - vault_id on rooms, game_state
   - created_at for time-based queries

2. **Implement Caching**
   - Redis cache for vault lists
   - Cache game state calculations
   - HTTP caching headers

3. **Optimize Queries**
   - Use select_related/join loading
   - Paginate large result sets
   - Add database connection pooling

4. **Background Processing**
   - Move game ticks to Celery
   - Queue heavy operations
   - Batch vault processing

5. **API Improvements**
   - Add rate limiting
   - Implement request throttling
   - Add response compression

## 📚 Next Steps

1. **Run Baseline Test**
   ```bash
   ./backend/locust/run_tests.sh baseline
   ```

2. **Review Results**
   - Check generated HTML report
   - Identify slow endpoints
   - Note error patterns

3. **Optimize**
   - Fix identified bottlenecks
   - Add indexes/caching
   - Rerun tests to verify improvements

4. **Establish Benchmarks**
   - Document baseline metrics
   - Set performance SLOs
   - Add to CI/CD pipeline

5. **Continuous Testing**
   - Run quick tests on PRs
   - Full tests on staging
   - Monitor production metrics

## 🐛 Troubleshooting

### "401 Unauthorized" errors
- Run `setup_test_data.py` to create test user
- Check credentials in .env.locust
- Verify API is running

### "Connection refused"
- Start your API: `uvicorn main:app --reload`
- Check LOCUST_HOST matches API address
- Verify port is correct (default: 8000)

### High failure rate
- Reduce user count
- Check API logs for errors
- Verify database is running
- Check connection pool settings

### Slow performance
- Monitor database query times
- Check for N+1 queries
- Review CPU/memory usage
- Consider scaling resources

## 📖 Documentation

- Full docs: `backend/locust/README.md`
- Locust docs: https://docs.locust.io/
- Task customization: Edit files in `tasks/` directory
- Configuration: Modify `config.py`

## 💡 Tips

1. **Start Small**: Begin with 5-10 users, then scale up
2. **Use Staging**: Don't load test production!
3. **Monitor System**: Watch CPU, memory, DB during tests
4. **Iterate**: Test → Optimize → Retest
5. **Automate**: Add to CI/CD for regression detection

---

**Ready to test?** Run: `./backend/locust/run_tests.sh web`

Questions? Check `README.md` or Locust documentation.

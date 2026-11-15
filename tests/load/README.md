# Load Testing Suite (Locust)

This test suite validates platform limits, concurrency bounds, and graceful 429 shedding under peak traffic as defined in [ADR 0001](../../docs/adr/0001-service-and-data-decisions.md) and the [Capacity Plan](../../docs/architecture/capacity-and-scaling-plan.md).

## 1. Installation
Install optional dev dependencies including Locust:
```bash
pip install -e .[dev]
```

## 2. Running Load Tests Against Local Server

1. Start your local API:
```bash
uvicorn obliq_api.main:app --host 0.0.0.0 --port 8000
```

2. Run a 30-second headless load test with 5 concurrent users:
```bash
locust -f tests/load/locustfile.py --headless -u 5 -r 1 --run-time 30s --host http://localhost:8000
```

## 3. Running Against Staging
```bash
LOAD_TEST_API_KEY="obliq_internal_staging_key" locust -f tests/load/locustfile.py \
    --headless \
    -u 10 \
    -r 2 \
    --run-time 1m \
    --host https://<org>-obliq-api-staging.hf.space
```

## 4. Key Metrics to Observe
- **Failures %:** Under normal load, 0%. Under burst load, 429s are counted as expected rate limits.
- **P95 Latency:** Ensure 95th percentile response time remains within the < 4.0s SLA.
- **Memory Consumption:** Monitor container memory to verify it never crosses 80%.

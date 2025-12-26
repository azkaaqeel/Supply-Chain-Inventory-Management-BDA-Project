# Supply Chain & Inventory Optimization - Real-Time BDA Pipeline

## 📚 Documentation Index

- **[QUICK_START.md](QUICK_START.md)** - Step-by-step setup guide (start here!)
- **[PHASE1_SUMMARY.md](PHASE1_SUMMARY.md)** - Complete Phase 1 implementation details
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture & design decisions
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing procedures
- **[project_context.md](../project_context.md)** - Assignment requirements & constraints

---

## Phase 1: Foundation (MongoDB + Generator + Airflow)

### Current Status
✅ Phase 1: Streaming data generation + Orchestration (COMPLETE)
⏳ Phase 2: Spark analytics + HDFS archiving (coming next)
⏳ Phase 3: Dashboard + Complete integration

### Quick Start

```bash
# Enable Rosetta 2 emulation in Docker Desktop (for HDFS later)
# Settings → Features in development → "Use Rosetta for x86/amd64 emulation"

# Start Phase 1 services
docker compose up -d

# Initialize Airflow database
docker compose run --rm airflow airflow db init

# Create Airflow admin user
docker compose run --rm airflow airflow users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin

# Start Airflow webserver
docker exec -it airflow airflow webserver &

# Start Airflow scheduler
docker exec -it airflow airflow scheduler
```

### Access Points
- **Airflow UI**: http://localhost:8080 (admin/admin)
- **MongoDB**: localhost:27017 (admin/admin123)

### Verify Data Generation

```bash
# Connect to MongoDB
docker exec -it mongo mongosh -u admin -p admin123

# Switch to database and check collections
use supply_chain
show collections
db.orders_fact.countDocuments()
db.inventory_fact.countDocuments()

# Watch real-time inserts
db.orders_fact.find().sort({order_ts: -1}).limit(5)
```

### Directory Structure

```
supply-chain-bda/
├── docker-compose.yml          # Phase 1: MongoDB, Generator, Airflow
├── .env                        # Environment variables
├── generator/                  # Statistical data generator
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── generator.py           # Main streaming logic
│   ├── config.py              # Domain data (SKUs, DCs, etc.)
│   └── models.py              # Statistical models
├── airflow/                    # Orchestration
│   ├── Dockerfile
│   ├── dags/
│   │   └── monitor_data.py   # Phase 1 monitoring DAG
│   ├── logs/                  # Auto-generated
│   └── plugins/               # Custom operators (future)
└── README.md
```

### Resource Usage (Phase 1)
- MongoDB: ~500MB RAM
- Generator: ~100MB RAM
- Airflow: ~800MB RAM
- **Total: ~1.4GB** (safe for 8GB M1)

### Next Steps (Phase 2)
- Add Spark (master + worker)
- Add HDFS (namenode + datanode with Rosetta)
- Add Redis cache
- Implement archiving logic (when MongoDB > 300MB)


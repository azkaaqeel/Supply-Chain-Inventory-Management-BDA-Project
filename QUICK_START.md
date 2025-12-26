# 🚀 Phase 1 Quick Start Guide

## Prerequisites

✅ Docker Desktop installed (with Rosetta 2 enabled for M1)  
✅ At least 4GB RAM allocated to Docker  
✅ Terminal access

---

## Step 1: Navigate to Project Directory

```bash
cd "/Users/aqeel/Desktop/BDA Project/supply-chain-bda"
```

---

## Step 2: Build and Start Services

```bash
# Build all images and start services
docker compose up -d --build

# Watch logs (optional)
docker compose logs -f
```

**Expected containers:**
- `mongo` - MongoDB database
- `generator` - Data generator
- `airflow` - Airflow scheduler + webserver

---

## Step 3: Wait for Services to Start

```bash
# Check service health
docker compose ps

# You should see all services "Up" and healthy
```

Wait about 30-60 seconds for Airflow to fully initialize.

---

## Step 4: Access Airflow UI

Open your browser and go to:

```
http://localhost:8080
```

**Login credentials:**
- Username: `admin`
- Password: `admin`

---

## Step 5: Verify Data Generation

### Option A: Check MongoDB Directly

```bash
# Connect to MongoDB shell
docker exec -it mongo mongosh -u admin -p admin123

# Inside mongosh:
use supply_chain
show collections
db.orders_fact.countDocuments()
db.shipments_fact.countDocuments()

# See latest orders
db.orders_fact.find().sort({order_ts: -1}).limit(3).pretty()

# Exit
exit
```

### Option B: Check Airflow DAG Logs

1. Go to Airflow UI → DAGs
2. Find `monitor_data_pipeline_phase1`
3. Click on the DAG → Graph view
4. Click on a task → Logs
5. You'll see data volume reports

---

## Step 6: Monitor Real-Time Progress

### Watch Generator Logs
```bash
docker logs -f generator
```

You should see output like:
```
[14:23:15] Iteration 0001 | Orders: 234 | Shipments: 45 | Inventory: 40 | DB Size: 2.3 MB | Duration: 0.45s
[14:24:15] Iteration 0002 | Orders: 245 | Shipments: 52 | Inventory: 40 | DB Size: 4.8 MB | Duration: 0.48s
...
```

### Watch Database Growth
```bash
# Run this periodically to check size
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  db.stats().dataSize / 1024 / 1024;
" --quiet
```

---

## Expected Behavior

After **5-10 minutes**, you should have:
- ✅ ~10-20 MB of data in MongoDB
- ✅ Thousands of orders, shipments, and inventory records
- ✅ Airflow DAG running every 5 minutes
- ✅ Real-time data streaming visible in logs

---

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs <container_name>

# Restart specific service
docker compose restart <service_name>
```

### MongoDB Connection Refused
```bash
# Wait 30 seconds for MongoDB to initialize
# Then restart generator
docker compose restart generator
```

### Airflow UI Not Loading
```bash
# Check Airflow is running
docker exec -it airflow ps aux | grep airflow

# If not running, exec into container and start manually
docker exec -it airflow bash
airflow webserver &
airflow scheduler &
```

### Out of Memory
```bash
# Check Docker stats
docker stats

# If containers are using >90% memory, reduce limits in docker-compose.yml
# Or increase Docker Desktop memory allocation (Settings → Resources)
```

---

## Stopping Services

```bash
# Stop all services (keep data)
docker compose down

# Stop and remove all data
docker compose down -v
```

---

## Next Steps (Phase 2)

Once Phase 1 is stable and you've accumulated ~50-100 MB of data:

1. Add Spark (master + worker)
2. Add HDFS (namenode + datanode)
3. Add Redis cache
4. Implement archiving logic (MongoDB → HDFS when > 300 MB)
5. Create Spark analytics jobs (KPI computation)

---

## Verification Checklist

- [ ] Docker containers all running (`docker compose ps`)
- [ ] MongoDB accessible and contains data
- [ ] Generator logs show continuous data creation
- [ ] Airflow UI loads at localhost:8080
- [ ] Airflow DAG `monitor_data_pipeline_phase1` is active
- [ ] Database size growing over time

---

## Success Criteria for Phase 1

✅ All services start without errors  
✅ Data is continuously generated every 60 seconds  
✅ MongoDB size grows steadily (aim for 50-100 MB before Phase 2)  
✅ Airflow monitoring DAG runs successfully  
✅ No memory/CPU alerts  

**If all criteria met → Ready for Phase 2!** 🎉


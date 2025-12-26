# 🚀 Quick Reference - Phase 2

## 🎬 Demo Mode (Most Important!)

### **Current Status**
```bash
# Check current mode
docker exec airflow bash -c 'echo "Mode: $DEMO_MODE"; echo "Threshold: $ARCHIVE_THRESHOLD_MB MB"'
```

### **Switch to Demo Mode** (for presentations)
```bash
# Option 1: Use script (recommended)
./switch_demo_mode.sh demo

# Option 2: Manual
# Edit docker-compose.yml: DEMO_MODE=false → DEMO_MODE=true
docker compose restart airflow
```

### **Switch to Production Mode** (for compliance)
```bash
./switch_demo_mode.sh production
```

**Why Demo Mode?**
- Production: 300 MB threshold → ~7 hours to trigger archival
- Demo: 30 MB threshold → ~1 hour to trigger archival
- Same code, just different parameter ✅

---

## 📊 Check System Status

### **All Services**
```bash
docker compose ps
```

### **MongoDB Size** (watch for archival trigger)
```bash
docker exec mongo mongosh "mongodb://admin:admin123@localhost:27017/supply_chain?authSource=admin" --quiet --eval "
print('Size: ' + (db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB');
print('Orders: ' + db.orders_fact.countDocuments());
print('Threshold: ' + (process.env.DEMO_MODE === 'true' ? '30 MB (demo)' : '300 MB (prod)'));
"
```

### **Redis KPIs** (should always have data)
```bash
# List all KPI keys
docker exec redis redis-cli KEYS "kpi:*"

# Check last update
docker exec redis redis-cli GET kpi:last_update

# View supplier performance (prettified)
docker exec redis redis-cli GET kpi:supplier_performance | jq .
```

### **HDFS Archive** (after first archival triggers)
```bash
docker exec namenode hdfs dfs -ls -R /supply_chain_archive
```

---

## 🧪 Manual Testing

### **Run KPI Computation Manually**
```bash
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0 \
  --driver-memory 512m \
  --executor-memory 512m \
  /opt/spark/jobs/compute_minute_kpis.py
```

### **Run Archival Manually** (even if < threshold)
```bash
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0,org.apache.hadoop:hadoop-client:3.3.4 \
  --driver-memory 512m \
  --executor-memory 768m \
  /opt/spark/jobs/archive_mongo_to_hdfs.py
```

---

## 🔍 Troubleshooting

### **Airflow DAG Not Running**
```bash
# Check DAG status
docker exec airflow airflow dags list

# View logs
docker exec airflow airflow tasks logs compute_kpis_phase2 spark_compute_kpis --latest
docker exec airflow airflow tasks logs archive_to_hdfs_phase2 check_database_size --latest

# Restart Airflow
docker compose restart airflow
```

### **Redis Empty**
```bash
# Check if KPI job is running
docker logs airflow 2>&1 | grep "compute_kpis"

# Manually trigger KPI computation (see above)
```

### **Spark Job Failing**
```bash
# Check Spark logs
docker logs spark-master
docker logs spark-worker

# Check if worker is connected
docker logs spark-worker 2>&1 | grep "registered with master"
```

### **HDFS Not Accessible**
```bash
# Check NameNode status
docker exec namenode hdfs dfsadmin -report

# View NameNode UI
open http://localhost:9870
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `PHASE2_COMPLETE.md` | Full Phase 2 documentation |
| `DEMO_MODE.md` | Detailed demo mode guide |
| `switch_demo_mode.sh` | Script to switch modes |
| `env.example` | Environment configuration template |
| `spark/jobs/compute_minute_kpis.py` | 5 KPIs implementation |
| `spark/jobs/archive_mongo_to_hdfs.py` | Archival logic |
| `airflow/dags/compute_kpis_phase2.py` | KPI orchestration |
| `airflow/dags/archive_to_hdfs_phase2.py` | Archive orchestration |

---

## 🌐 Web UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8080 | admin / admin |
| Spark Master | http://localhost:8081 | None |
| HDFS NameNode | http://localhost:9870 | None |

---

## 🎥 Recording a Demo

1. **Start Fresh** (optional)
   ```bash
   docker compose down -v
   DEMO_MODE=true docker compose up -d
   ```

2. **Show System Running** (~5 min)
   - Airflow UI: DAGs running
   - Redis: KPIs updating
   - MongoDB: Size growing

3. **Fast-Forward** (time-lapse or speed up video)
   - Wait for DB to hit 30 MB (~1 hour)
   - Or manually edit `DEMO_THRESHOLD_MB=5` for faster demo

4. **Show Archival** (~5 min)
   - Airflow: `trigger_archival` task succeeds
   - HDFS: New Parquet files
   - MongoDB: Size drops

5. **Explain Compliance**
   - Show docker-compose.yml: default is 300MB
   - Mention demo mode is just parameter change

---

## 💾 Backup & Cleanup

### **Stop All Services**
```bash
docker compose down
```

### **Stop & Remove All Data** (fresh start)
```bash
docker compose down -v
```

### **Restart Services**
```bash
docker compose up -d
```

### **View Logs**
```bash
docker compose logs -f [service_name]
# e.g., docker compose logs -f airflow
```

---

## 📊 Expected Performance (8GB M1 Mac)

| Metric | Value |
|--------|-------|
| Total RAM Usage | ~4.9 GB |
| Data Generation Rate | ~29 MB/hour |
| KPI Computation Time | ~10-15 seconds |
| Time to 300MB | ~10 hours (production) |
| Time to 30MB | ~1 hour (demo) |

---

## ✅ Pre-Demo Checklist

- [ ] All 8 containers running (`docker compose ps`)
- [ ] Redis has 9 KPI keys (`docker exec redis redis-cli KEYS "kpi:*"`)
- [ ] MongoDB size visible (`docker exec mongo mongosh...`)
- [ ] Airflow UI accessible (http://localhost:8080)
- [ ] Demo mode enabled if needed (`./switch_demo_mode.sh demo`)
- [ ] KPIs updating every minute (check `kpi:last_update`)
- [ ] Archival DAG visible in Airflow

---

## 🆘 Emergency Commands

### **Restart Everything**
```bash
docker compose restart
```

### **Check What's Using RAM**
```bash
docker stats --no-stream
```

### **Force Kill & Restart**
```bash
docker compose down
docker system prune -f
docker compose up -d
```

### **View Real-Time Logs**
```bash
docker compose logs -f --tail=50
```

---

## 📚 Full Documentation

For complete details, see:
- `PHASE2_COMPLETE.md` - Full implementation report
- `DEMO_MODE.md` - Demo mode usage guide
- `PHASE1_SUMMARY.md` - Phase 1 details
- `QUICK_START.md` - Initial setup guide
- `PROJECT_CONTEXT.md` - Requirements & constraints


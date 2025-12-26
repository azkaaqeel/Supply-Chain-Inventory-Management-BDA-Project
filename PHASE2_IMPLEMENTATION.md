# Phase 2 Implementation Guide

## 🎯 **What Was Added**

Phase 2 extends Phase 1 with distributed analytics, archival, and caching capabilities.

### **New Infrastructure (5 Services)**

| Service | Container | Purpose | Memory |
|---------|-----------|---------|--------|
| **Redis** | redis:7-alpine | KPI cache | 128MB |
| **Spark Master** | apache/spark:3.5.1 | Job coordination | 512MB |
| **Spark Worker** | apache/spark:3.5.1 | Processing node | 1280MB |
| **HDFS NameNode** | hadoop:3.2.1 (x86 emulated) | Metadata + UI | 512MB |
| **HDFS DataNode** | hadoop:3.2.1 (x86 emulated) | Block storage | 512MB |

**Total Phase 2 Memory:** ~3GB  
**Combined (Phase 1 + 2):** ~5GB total

---

## 📊 **Spark Jobs Implemented**

### **Job 1: `compute_minute_kpis.py`**

**Purpose:** Compute 5 supply chain KPIs and cache in Redis

**Trigger:** Every 1 minute via Airflow DAG

**What It Does:**
1. Reads last 15 minutes of data from MongoDB
2. Performs multi-table joins (facts × dimensions)
3. Uses Spark SQL with WHERE, GROUP BY, HAVING
4. Computes KPIs:
   - **KPI 1:** Total Inventory Level (by SKU & DC)
   - **KPI 2:** Stockout Risk (days until stockout)
   - **KPI 3:** Supplier Lead Time Performance
   - **KPI 4:** DC Utilization Rate
   - **KPI 5:** Regional Order Fulfillment & Revenue
5. Caches results in Redis as JSON
6. Sets 120-second TTL on cached data

**Example Query (KPI 2 - Stockout Risk):**
```sql
SELECT 
    i.sku_id,
    s.product_name,
    d.dc_name,
    AVG(i.on_hand_qty) AS current_stock,
    SUM(o.quantity) / 15.0 * 1440 AS units_per_day,
    CASE 
        WHEN units_per_day > 0 
        THEN current_stock / units_per_day
        ELSE 9999
    END AS days_to_stockout
FROM inventory_fact i
LEFT JOIN orders_fact o 
    ON i.sku_id = o.sku_id AND i.dc_id = o.dc_id
JOIN skus_dim s ON i.sku_id = s.sku_id
JOIN dcs_dim d ON i.dc_id = d.dc_id
WHERE i.inventory_ts >= NOW() - INTERVAL 15 MINUTES
  AND o.order_ts >= NOW() - INTERVAL 15 MINUTES
GROUP BY i.sku_id, i.dc_id
HAVING days_to_stockout < 7
ORDER BY days_to_stockout
```

---

### **Job 2: `archive_mongo_to_hdfs.py`**

**Purpose:** Archive old MongoDB data to HDFS when size > 300MB

**Trigger:** Every 5 minutes via Airflow DAG (conditional)

**What It Does:**
1. Checks MongoDB dataSize
2. If < 300MB: skips archival
3. If ≥ 300MB:
   - Archives data older than 2 hours
   - Writes to HDFS in Parquet format
   - Partitions by `event_date` and `event_hour`
   - Generates metadata JSON
   - Deletes archived data from MongoDB

**HDFS Directory Structure:**
```
hdfs://namenode:8020/supply_chain_archive/
├── orders_fact/
│   ├── event_date=2025-12-25/
│   │   ├── event_hour=10/
│   │   │   └── part-00000.parquet
│   │   └── event_hour=11/
│   │       └── part-00000.parquet
│   └── event_date=2025-12-26/
│       └── event_hour=12/
│           └── part-00000.parquet
├── shipments_fact/
│   └── event_date=2025-12-25/
│       └── event_hour=10/
│           └── part-00000.parquet
├── inventory_fact/
│   └── event_date=2025-12-25/
│       └── event_hour=10/
│           └── part-00000.parquet
└── metadata/
    ├── archive_<uuid-1>.json
    └── archive_<uuid-2>.json
```

**Metadata JSON Example:**
```json
{
  "archive_id": "a3f8b2c1-4d5e-6789-abcd-ef1234567890",
  "created_at": "2025-12-25T14:30:00Z",
  "archived_collections": [
    {
      "collection": "orders_fact",
      "record_count": 145230,
      "size_mb": 68.5,
      "date_range": {
        "min": "2025-12-25T10:00:00Z",
        "max": "2025-12-25T12:00:00Z"
      }
    },
    {
      "collection": "shipments_fact",
      "record_count": 58120,
      "size_mb": 27.3,
      "date_range": {
        "min": "2025-12-25T10:00:00Z",
        "max": "2025-12-25T12:00:00Z"
      }
    }
  ],
  "total_records": 203350,
  "total_size_mb": 95.8,
  "hdfs_base_path": "hdfs://namenode:8020/supply_chain_archive",
  "archive_policy": {
    "older_than_minutes": 120,
    "format": "parquet",
    "compression": "snappy",
    "partitioned_by": ["event_date", "event_hour"]
  }
}
```

---

## 🔄 **Airflow DAGs (Phase 2)**

### **DAG 1: `compute_kpis_phase2`**

- **Schedule:** Every 1 minute (`* * * * *`)
- **Tasks:** 1 task (spark_compute_kpis)
- **Purpose:** Continuous KPI refresh
- **Execution Time:** ~30-60 seconds

**Task Flow:**
```
spark_compute_kpis
   ↓
   Reads MongoDB → Joins → Computes KPIs → Writes to Redis
```

---

### **DAG 2: `archive_to_hdfs_phase2`**

- **Schedule:** Every 5 minutes (`*/5 * * * *`)
- **Tasks:** 4 tasks (branching logic)
- **Purpose:** Conditional archival based on size
- **Execution Time:** 
  - Skip path: ~5 seconds
  - Archive path: ~2-5 minutes

**Task Flow:**
```
check_database_size
   ├─ (if size > 300MB) → trigger_archival → log_archival_complete
   └─ (if size ≤ 300MB) → skip_archival    → log_archival_complete
```

---

## 🚀 **Startup Instructions**

### **Step 1: Stop Phase 1 Services**

```bash
cd "/Users/aqeel/Desktop/BDA Project/supply-chain-bda"
docker compose down
```

### **Step 2: Rebuild with Phase 2 Services**

```bash
docker compose up -d --build
```

This will start:
- ✅ All Phase 1 services (mongo, generator, airflow)
- ✅ New Phase 2 services (redis, spark-master, spark-worker, namenode, datanode)

**Expected containers:** 9 total

### **Step 3: Wait for Initialization**

```bash
# Wait 60 seconds for all services to start
sleep 60

# Check all services are running
docker compose ps
```

Expected output:
```
NAME           STATUS
mongo          Up (healthy)
generator      Up
airflow        Up
redis          Up
spark-master   Up
spark-worker   Up
namenode       Up
datanode       Up
```

### **Step 4: Initialize HDFS Directories**

```bash
docker exec -it namenode bash -c "
  hdfs dfs -mkdir -p /supply_chain_archive/metadata &&
  hdfs dfs -mkdir -p /supply_chain_archive/orders_fact &&
  hdfs dfs -mkdir -p /supply_chain_archive/shipments_fact &&
  hdfs dfs -mkdir -p /supply_chain_archive/inventory_fact &&
  hdfs dfs -chmod -R 777 /supply_chain_archive
"
```

### **Step 5: Verify HDFS**

```bash
# Check HDFS directories
docker exec -it namenode hdfs dfs -ls /supply_chain_archive

# Access HDFS UI (optional)
open http://localhost:9870
```

### **Step 6: Enable Phase 2 DAGs in Airflow**

1. Open Airflow UI: http://localhost:8080 (admin/admin)
2. Find DAGs:
   - `compute_kpis_phase2`
   - `archive_to_hdfs_phase2`
3. Toggle **ON** for both DAGs
4. Manually trigger `compute_kpis_phase2` to test

---

## 📊 **Verification & Testing**

### **Test 1: Verify Spark Master**

```bash
# Check Spark UI
open http://localhost:8081

# Should show:
# - Spark Master status
# - 1 worker registered
```

### **Test 2: Verify Redis Cache**

```bash
# Check Redis keys
docker exec -it redis redis-cli KEYS 'kpi:*'

# Expected output (after first KPI run):
# kpi:last_update
# kpi:inventory_level
# kpi:stockout_alerts
# kpi:supplier_performance
# kpi:dc_utilization
# kpi:regional_performance
```

### **Test 3: Manually Trigger KPI Computation**

```bash
# From Airflow UI:
# 1. Go to compute_kpis_phase2 DAG
# 2. Click "Trigger DAG" button
# 3. Wait ~60 seconds
# 4. Check task logs

# Verify Redis was populated:
docker exec -it redis redis-cli GET kpi:last_update
# Should show recent timestamp
```

### **Test 4: Check KPI Data**

```bash
# View stockout alerts (pretty printed)
docker exec -it redis redis-cli GET kpi:stockout_alerts | python3 -m json.tool
```

### **Test 5: Verify HDFS Archival (When DB > 300MB)**

```bash
# Check current MongoDB size
docker exec mongo mongosh "mongodb://admin:admin123@localhost:27017/supply_chain?authSource=admin" --quiet --eval "
print('DB Size: ' + (db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB');
"

# If < 300MB, wait for more data generation
# If ≥ 300MB, the archive_to_hdfs_phase2 DAG will trigger automatically

# Check HDFS after archival:
docker exec -it namenode hdfs dfs -ls -R /supply_chain_archive
```

---

## 🔍 **Monitoring Commands**

### **Check All Containers**
```bash
docker compose ps
docker stats --no-stream
```

### **View Logs**

```bash
# Spark Master
docker logs spark-master --tail 50

# Spark Worker
docker logs spark-worker --tail 50

# Airflow (for DAG execution)
docker logs airflow --tail 100

# Redis (connection logs)
docker logs redis --tail 20
```

### **Monitor KPI Updates**

```bash
# Watch KPI refresh in real-time
watch -n 5 'docker exec redis redis-cli GET kpi:last_update'
```

### **Check HDFS Health**

```bash
# HDFS report
docker exec -it namenode hdfs dfsadmin -report

# DataNode status
docker exec -it datanode jps
```

---

## ⚠️ **Troubleshooting**

### **Issue: Spark Jobs Fail with "Connection Refused"**

**Cause:** Spark worker not connected to master

**Fix:**
```bash
docker compose restart spark-worker
docker logs spark-worker | grep "Successfully registered"
```

---

### **Issue: HDFS NameNode Not Accessible**

**Cause:** NameNode initialization incomplete (x86 emulation slow on M1)

**Fix:**
```bash
# Wait longer (2-3 minutes)
sleep 120

# Check logs
docker logs namenode | grep "Web-server up"

# Restart if needed
docker compose restart namenode datanode
```

---

### **Issue: Redis Empty (No KPI Keys)**

**Cause:** KPI DAG hasn't run yet or failed

**Fix:**
```bash
# Check DAG status in Airflow UI
# Manually trigger compute_kpis_phase2

# Check Spark logs for errors
docker logs spark-worker | grep ERROR
```

---

### **Issue: MongoDB Not Archiving**

**Cause:** Database size < 300MB

**Solution:**
- This is expected! Archival only triggers when size > 300MB
- Let Phase 1 generator run for 5-10 hours to accumulate data
- Or manually lower threshold in `archive_to_hdfs_phase2.py` (change line 19)

---

### **Issue: Out of Memory**

**Symptom:**
```bash
docker stats
# Shows containers using > 90% memory
```

**Fix:**
```bash
# Option 1: Increase Docker Desktop memory to 6-7GB
# Settings → Resources → Memory

# Option 2: Reduce Spark worker memory
# Edit docker-compose.yml:
#   SPARK_WORKER_MEMORY=768M  # down from 1G
```

---

## 📈 **Expected Performance**

### **KPI Computation**
- **Frequency:** Every 1 minute
- **Execution Time:** 30-60 seconds
- **Data Processed:** Last 15 minutes (~2000-3000 records)
- **Output:** 5 KPIs cached in Redis

### **Archival**
- **Frequency:** Every 5 minutes (conditional)
- **Trigger:** When MongoDB > 300MB
- **Execution Time:** 2-5 minutes
- **Data Moved:** ~150MB per archival run
- **Space Freed:** ~50% of MongoDB size

### **Resource Usage**
| Component | CPU | Memory |
|-----------|-----|--------|
| Phase 1 (Mongo + Gen + Airflow) | 10-20% | 1.5GB |
| Spark Master | 5% | 400MB |
| Spark Worker (idle) | 5% | 600MB |
| Spark Worker (running) | 50-80% | 1GB |
| Redis | 1% | 50MB |
| HDFS (NameNode + DataNode) | 10% | 800MB |
| **Total** | **30-50%** | **~5GB** |

---

## ✅ **Success Criteria**

Phase 2 is fully operational when:

- ✅ All 9 containers running
- ✅ Spark UI accessible (http://localhost:8081)
- ✅ HDFS UI accessible (http://localhost:9870)
- ✅ Redis contains KPI keys
- ✅ `compute_kpis_phase2` DAG runs every minute without errors
- ✅ `archive_to_hdfs_phase2` DAG checks size every 5 minutes
- ✅ KPIs update in Redis (check `kpi:last_update` timestamp)
- ✅ No OOM errors after 1 hour of runtime

---

## 🎯 **What's Next: Phase 3**

After Phase 2 is stable (running for 2+ hours):

1. **Build Streamlit Dashboard**
   - Read KPIs from Redis
   - Display real-time charts and alerts
   - Auto-refresh every 60 seconds

2. **Add Dashboard Container**
   - Lightweight Python 3.11 image
   - Connects to Redis only (no MongoDB queries)
   - Accessible at http://localhost:8501

3. **Final Integration Testing**
   - End-to-end data flow validation
   - Performance tuning
   - Documentation finalization

---

## 📝 **Summary**

**Phase 2 Adds:**
- ✅ Spark distributed processing (2 containers)
- ✅ HDFS cold storage (2 containers)
- ✅ Redis KPI cache (1 container)
- ✅ 2 Spark jobs (KPI + Archival)
- ✅ 2 new Airflow DAGs
- ✅ Multi-table OLAP queries
- ✅ Automated archival when > 300MB
- ✅ Sub-second KPI access via cache

**Total Implementation:**
- 9 Docker containers
- ~5GB memory footprint
- 5 KPIs computed every minute
- Automatic archival to HDFS
- Ready for Phase 3 dashboard

---

**Phase 2 implementation complete! 🚀**

Test thoroughly before proceeding to Phase 3.


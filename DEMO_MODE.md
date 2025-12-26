# 🎬 Demo Mode Guide

This guide explains how to use **Demo Mode** for presentations and recordings while maintaining assignment compliance.

---

## 📋 **Overview**

The archival system has two operating modes:

| Mode | Threshold | Time to Trigger | Use Case |
|------|-----------|-----------------|----------|
| **Production** (default) | 300 MB | ~7 hours | Assignment compliance, normal operation |
| **Demo** | 30 MB | ~45 minutes | Presentations, screen recordings, demos |

---

## ⚙️ **How It Works**

The archival DAG (`archive_to_hdfs_phase2`) checks the `DEMO_MODE` environment variable:

- `DEMO_MODE=false` (default) → Uses 300MB threshold ✅ *Assignment compliant*
- `DEMO_MODE=true` → Uses 30MB threshold 🎬 *Fast demo*

**Important**: Demo mode does NOT change the code logic—it only adjusts the threshold parameter. Your implementation remains compliant.

---

## 🚀 **Quick Start: Enable Demo Mode**

### **Option 1: Using .env file** (Recommended)

```bash
# 1. Copy the example environment file
cp env.example .env

# 2. Edit .env and set:
DEMO_MODE=true
DEMO_THRESHOLD_MB=30

# 3. Restart services
docker compose down
docker compose up -d

# 4. Verify demo mode is active
docker logs airflow 2>&1 | grep "DEMO MODE"
```

### **Option 2: Using environment variable** (One-time)

```bash
# Start with demo mode enabled
DEMO_MODE=true docker compose up -d

# Check status
docker exec airflow printenv DEMO_MODE
```

### **Option 3: Inline export** (Terminal session)

```bash
# Set for current terminal session
export DEMO_MODE=true
export DEMO_THRESHOLD_MB=30

# Start services
docker compose up -d
```

---

## 🧪 **Testing Demo Mode**

### **1. Verify Mode is Active**

Check Airflow logs for the mode indicator:

```bash
docker logs airflow 2>&1 | grep -i "demo"
```

Expected output:
```
🎬 DEMO MODE ENABLED - Using reduced threshold for demonstration
```

### **2. Monitor MongoDB Size Growth**

```bash
# Watch database size in real-time
watch -n 10 'docker exec mongo mongosh "mongodb://admin:admin123@localhost:27017/supply_chain?authSource=admin" --quiet --eval "
const stats = db.stats();
const sizeMB = (stats.dataSize / 1024 / 1024).toFixed(2);
print('\''Database Size: '\'' + sizeMB + '\'' MB'\'');
print('\''Threshold: 30 MB (DEMO MODE)'\'');
print('\''Progress: '\'' + ((sizeMB / 30) * 100).toFixed(1) + '\''%'\'');
"'
```

### **3. Check Archival DAG Logs**

```bash
# View the archival DAG logs
docker exec airflow airflow tasks logs archive_to_hdfs_phase2 check_database_size
```

You should see:
```
======================================================================
📊 MONGODB SIZE CHECK
======================================================================
Mode: 🎬 DEMO MODE
Database Size: 28.92 MB
Threshold: 30 MB
...
```

### **4. Wait for Archival to Trigger**

At current growth rate (29MB/hour):
- **Demo mode (30 MB)**: ~1 hour
- **Production mode (300 MB)**: ~10 hours

When triggered, you'll see in Airflow UI:
- `archive_to_hdfs_phase2` DAG → `trigger_archival` task succeeds
- HDFS will contain new Parquet files

---

## 📊 **Verification After Archival**

### **Check HDFS Archive**

```bash
# List archived data
docker exec namenode hdfs dfs -ls -R /supply_chain_archive

# Check metadata
docker exec namenode hdfs dfs -cat /supply_chain_archive/metadata/*.json | head -50
```

### **Verify MongoDB Size Reduced**

```bash
docker exec mongo mongosh "mongodb://admin:admin123@localhost:27017/supply_chain?authSource=admin" --quiet --eval "
print('Database Size: ' + (db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB');
print('Orders: ' + db.orders_fact.countDocuments());
print('Shipments: ' + db.shipments_fact.countDocuments());
"
```

Expected: Size should drop significantly after archival completes.

---

## 🎥 **Recording a Demo**

### **Suggested Timeline**

1. **Start fresh** (0:00)
   ```bash
   docker compose down -v  # Clean slate
   DEMO_MODE=true docker compose up -d
   ```

2. **Show initial state** (0:05)
   - Airflow UI: both DAGs running
   - Redis: KPIs cached
   - MongoDB: ~5 MB

3. **Fast-forward 45 min** (recorded at 2x speed or time-lapse)
   - Monitor MongoDB size growing
   - Show KPI values updating every minute

4. **Archive triggers** (~0:45)
   - Show Airflow DAG: `trigger_archival` task runs
   - Show HDFS: new Parquet files appear
   - Show MongoDB: size drops

5. **Explain compliance** (0:50)
   - Show `docker-compose.yml`: default is 300MB
   - Show `env.example`: production mode configuration
   - Explain demo mode is just a parameter change, same code

---

## 🔁 **Switching Back to Production Mode**

After your demo/recording:

```bash
# 1. Stop services
docker compose down

# 2. Edit .env (or unset environment variable)
DEMO_MODE=false

# 3. Restart
docker compose up -d

# 4. Verify production mode
docker exec airflow printenv DEMO_MODE  # Should show: false
docker logs airflow 2>&1 | grep "PRODUCTION MODE"
```

---

## 🎯 **Assignment Compliance Statement**

For your report/documentation:

> *"The archival system implements a configurable threshold mechanism. The production configuration uses a 300MB threshold as required by the assignment specifications. For demonstration purposes, a demo mode is available that uses a reduced threshold (30MB) to showcase the archival functionality within a practical timeframe. This is implemented via environment variables and does not alter the core archival logic or architecture."*

**Key Points:**
- ✅ Default configuration: 300MB (assignment compliant)
- ✅ Code logic unchanged between modes
- ✅ Only parameter differs (threshold value)
- ✅ Fully documented and transparent

---

## 🐛 **Troubleshooting**

### **Demo mode not activating**

```bash
# Check if environment variable is set
docker exec airflow printenv | grep DEMO

# Restart Airflow scheduler
docker restart airflow
```

### **Archival not triggering**

```bash
# Manually check size
docker exec mongo mongosh "mongodb://admin:admin123@localhost:27017/supply_chain?authSource=admin" --quiet --eval "print((db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB')"

# Check DAG is running
docker exec airflow airflow dags list-runs -d archive_to_hdfs_phase2

# View last run logs
docker exec airflow airflow tasks logs archive_to_hdfs_phase2 check_database_size --latest
```

### **Speed up data generation** (for faster demos)

Edit `docker-compose.yml`:
```yaml
generator:
  environment:
    - EVENTS_PER_MINUTE=3000  # Double the rate
```

Restart:
```bash
docker compose restart generator
```

---

## 📝 **Summary**

| Scenario | Command | Expected Result |
|----------|---------|-----------------|
| **Normal operation** | `docker compose up -d` | 300MB threshold, ~10 hours to archive |
| **Quick demo** | `DEMO_MODE=true docker compose up -d` | 30MB threshold, ~1 hour to archive |
| **Verify mode** | `docker logs airflow \| grep MODE` | Shows active mode |
| **Switch modes** | Edit `.env`, restart containers | New threshold applied |

---

**🎬 Ready to demo? Enable demo mode and your archival will trigger in about an hour!**


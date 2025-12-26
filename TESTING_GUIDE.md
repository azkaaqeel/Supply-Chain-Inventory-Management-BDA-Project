# Phase 1 Testing Guide

## Pre-Flight Checklist

Before starting, ensure:
- [ ] Docker Desktop is installed and running
- [ ] At least 4GB RAM allocated to Docker (Settings → Resources)
- [ ] Rosetta 2 enabled (Settings → Features → "Use Rosetta for x86/amd64 emulation")
- [ ] No services running on ports: 8080, 27017

---

## Test 1: Container Startup ✅

### Goal
Verify all containers start successfully

### Steps
```bash
cd "/Users/aqeel/Desktop/BDA Project/supply-chain-bda"

# Build and start
docker compose up -d --build

# Wait 30 seconds for initialization

# Check status
docker compose ps
```

### Expected Output
```
NAME        IMAGE                         STATUS
airflow     supply-chain-bda-airflow      Up
generator   supply-chain-bda-generator    Up
mongo       mongo:6.0                     Up (healthy)
```

### Pass Criteria
- All containers show "Up" status
- MongoDB shows "healthy"
- No errors in `docker compose ps`

---

## Test 2: MongoDB Connectivity ✅

### Goal
Verify MongoDB is accessible and seeded with dimensions

### Steps
```bash
docker exec -it mongo mongosh -u admin -p admin123
```

Inside mongosh:
```javascript
// Switch to database
use supply_chain

// Check collections exist
show collections
// Expected: regions_dim, dcs_dim, skus_dim, suppliers_dim, 
//           orders_fact, shipments_fact, inventory_fact, inventory_state

// Count dimension records
db.regions_dim.countDocuments()      // Expected: 4
db.dcs_dim.countDocuments()          // Expected: 5
db.skus_dim.countDocuments()         // Expected: 8
db.suppliers_dim.countDocuments()    // Expected: 4

// Check inventory state initialized
db.inventory_state.countDocuments()  // Expected: 40 (8 SKUs × 5 DCs)

// Exit
exit
```

### Pass Criteria
- All dimension tables have correct counts
- inventory_state has 40 records

---

## Test 3: Data Generation (Real-Time) ✅

### Goal
Verify generator is producing data continuously

### Steps
```bash
# Watch generator logs
docker logs -f generator
```

### Expected Output
```
✅ Connected to MongoDB: mongo:27017/supply_chain
📇 Creating indexes...
✅ Indexes created
✅ Seeded 4 regions, 5 DCs, 8 SKUs, 4 suppliers
✅ Initialized inventory for 40 SKU-DC combinations

📊 Generation Parameters:
   - Events per minute: 1500
   - Generation interval: 60s
   - SKUs: 8
   - Distribution Centers: 5
   - Suppliers: 4

🔄 Starting continuous data generation...

[14:23:15] Iteration 0001 | Orders: 234 | Shipments: 45 | Inventory: 40 | DB Size: 2.3 MB | Duration: 0.45s
[14:24:15] Iteration 0002 | Orders: 245 | Shipments: 52 | Inventory: 40 | DB Size: 4.8 MB | Duration: 0.48s
[14:25:15] Iteration 0003 | Orders: 251 | Shipments: 48 | Inventory: 40 | DB Size: 7.2 MB | Duration: 0.42s
```

### Pass Criteria
- New iterations appear every 60 seconds
- Orders count ~200-300 per iteration
- Shipments count ~40-60 per iteration
- DB size increases steadily
- Duration < 1 second

### Common Issues

**"MongoDB connection failed"**
- Wait 30 seconds for MongoDB to initialize
- Check MongoDB container is running: `docker ps`
- Restart generator: `docker compose restart generator`

**"Orders: 0"**
- Check MongoDB has dimensions: See Test 2
- Check generator logs for Python errors

---

## Test 4: Data Persistence ✅

### Goal
Verify data is being written to MongoDB and accumulating

### Steps (Run in terminal)
```bash
# Count documents at start
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  print('Orders: ' + db.orders_fact.countDocuments());
" --quiet

# Wait 2 minutes

# Count again
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  print('Orders: ' + db.orders_fact.countDocuments());
" --quiet
```

### Expected Result
- Second count should be ~500-600 higher than first
- If counts are equal, data generation is stalled (check generator logs)

### Pass Criteria
- Document count increases after 2 minutes
- Growth rate ~250 orders/minute

---

## Test 5: Data Quality (Statistical Realism) ✅

### Goal
Verify data uses statistical models (not random)

### Steps
```bash
docker exec -it mongo mongosh -u admin -p admin123
```

Inside mongosh:
```javascript
use supply_chain

// Check order value distribution (should be right-skewed)
db.orders_fact.aggregate([
  { $group: {
      _id: null,
      avg_value: { $avg: "$order_value" },
      min_value: { $min: "$order_value" },
      max_value: { $max: "$order_value" }
  }}
])
// Expected: avg ~500-800, min ~50, max ~3000+

// Check priority distribution (should follow weighted probabilities)
db.orders_fact.aggregate([
  { $group: { _id: "$priority_level", count: { $sum: 1 } } }
])
// Expected: NORMAL ~70%, HIGH ~15%, LOW ~15%

// Check high-value orders are more often HIGH priority (correlation)
db.orders_fact.aggregate([
  { $match: { order_value: { $gt: 2000 } } },
  { $group: { _id: "$priority_level", count: { $sum: 1 } } }
])
// Expected: HIGH should dominate for expensive orders

// Check inventory depletion (stateful behavior)
db.inventory_state.find().sort({ on_hand_qty: 1 }).limit(5).pretty()
// Expected: Some SKUs should have depleted inventory (< 50% of base_stock)

exit
```

### Pass Criteria
- Order values follow log-normal pattern (not uniform)
- Priority levels follow weighted distribution
- High-value orders have higher HIGH priority ratio
- Some inventory has depleted significantly

---

## Test 6: Airflow UI Access ✅

### Goal
Verify Airflow webserver is accessible

### Steps
1. Open browser: http://localhost:8080
2. Login with:
   - Username: `admin`
   - Password: `admin`

### Expected Result
- Login page loads successfully
- After login, Airflow dashboard appears
- No error messages

### Common Issues

**"Connection refused"**
- Wait 60 seconds for Airflow to initialize
- Check Airflow container logs: `docker logs airflow`
- Manually restart webserver: `docker exec -it airflow airflow webserver`

**"Airflow not initialized"**
- The docker-compose.yml auto-initializes
- If fails, run manually:
  ```bash
  docker compose run --rm airflow airflow db init
  docker compose restart airflow
  ```

---

## Test 7: Airflow DAG Execution ✅

### Goal
Verify monitoring DAG runs successfully

### Steps
1. In Airflow UI, go to **DAGs** page
2. Find DAG: `monitor_data_pipeline_phase1`
3. Check DAG is **enabled** (toggle switch should be blue)
4. Click on DAG name → **Graph** view
5. Wait for DAG to run (scheduled every 5 minutes)
   - Or manually trigger: Click **Play** button → "Trigger DAG"

### Expected Result
- DAG runs successfully (all tasks green)
- Task execution order:
  1. `check_mongo_connection` (green)
  2. `monitor_data_volume` (green)
  3. `check_data_freshness` (green)
  4. `log_system_status` (green)

### View Task Logs
1. Click on task box (e.g., `monitor_data_volume`)
2. Click **Log** button
3. Should see data volume report:
   ```
   ======================================================================
   📊 DATA VOLUME REPORT
   ======================================================================
   Database Size: 12.45 MB
   Target Threshold: 300 MB (for archiving in Phase 2)
   Progress: 4.2%
   
   Collection Document Counts:
     - orders_fact         : 3,245
     - shipments_fact      : 1,302
     - inventory_fact      : 120
   ```

### Pass Criteria
- All 4 tasks complete successfully (green)
- Logs show database statistics
- No Python exceptions or errors

---

## Test 8: Data Freshness ✅

### Goal
Verify data is recent (< 2 minutes old)

### Steps
```bash
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  var latest = db.orders_fact.find().sort({order_ts: -1}).limit(1).toArray()[0];
  if (latest) {
    var ageSeconds = (new Date() - latest.order_ts) / 1000;
    print('Latest order: ' + ageSeconds.toFixed(0) + ' seconds ago');
    if (ageSeconds > 120) {
      print('⚠️  WARNING: Data is stale!');
    } else {
      print('✅ Data is fresh');
    }
  }
" --quiet
```

### Expected Output
```
Latest order: 45 seconds ago
✅ Data is fresh
```

### Pass Criteria
- Age < 120 seconds
- If age > 120s, generator may have crashed (check logs)

---

## Test 9: Database Growth Rate ✅

### Goal
Verify database grows at expected rate (~1 MB/min)

### Steps
```bash
# Record size at T0
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  var sizeMB = db.stats().dataSize / 1024 / 1024;
  print('Size: ' + sizeMB.toFixed(2) + ' MB');
" --quiet

# Wait 5 minutes

# Record size at T5
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  var sizeMB = db.stats().dataSize / 1024 / 1024;
  print('Size: ' + sizeMB.toFixed(2) + ' MB');
" --quiet
```

### Expected Result
- Growth: 4-6 MB in 5 minutes (~1 MB/min)
- Extrapolate: ~60 MB/hour, ~300 MB in 5 hours

### Pass Criteria
- Database size increases
- Growth rate ~0.8-1.2 MB/min

---

## Test 10: Resource Usage ✅

### Goal
Verify system stays within 8GB RAM constraint

### Steps
```bash
# Monitor real-time resource usage
docker stats

# Let it run for 30 seconds, then press Ctrl+C
```

### Expected Output
```
CONTAINER   CPU %   MEM USAGE / LIMIT   MEM %   NET I/O
mongo       5%      450MB / 1GB         45%     1MB / 500kB
generator   2%      120MB / 256MB       47%     200kB / 1MB
airflow     8%      650MB / 1GB         65%     500kB / 300kB
```

### Pass Criteria
- **Total memory usage < 2.5 GB**
- No containers hitting their memory limits
- CPU usage reasonable (< 50% per container)

### Warning Signs
- ⚠️ Memory > 90% of limit → Container may OOM-kill
- ⚠️ CPU constantly 100% → Performance issue
- ⚠️ Total memory > 5GB → Reduce EVENTS_PER_MINUTE

---

## Test 11: Graceful Shutdown ✅

### Goal
Verify services stop cleanly without data corruption

### Steps
```bash
# Stop all services
docker compose down

# Check no containers running
docker ps -a

# Restart
docker compose up -d

# Wait 30 seconds

# Verify data persisted
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  print('Orders: ' + db.orders_fact.countDocuments());
" --quiet
```

### Pass Criteria
- All containers stop without errors
- After restart, order count unchanged (data persisted)
- Generator resumes from where it left off

---

## Test 12: Long-Running Stability (Optional) ✅

### Goal
Verify system runs stably for extended period

### Steps
```bash
# Start services
docker compose up -d

# Let run overnight (6-8 hours)

# Next day, check status
docker compose ps
docker stats --no-stream

# Check database size
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  var sizeMB = db.stats().dataSize / 1024 / 1024;
  print('Size: ' + sizeMB.toFixed(2) + ' MB');
  print('Orders: ' + db.orders_fact.countDocuments());
" --quiet
```

### Expected After 8 Hours
- Database size: ~400-500 MB
- Order count: ~240,000
- All containers still running
- No OOM kills or crashes

### Pass Criteria
- All services still up after 8+ hours
- No memory leaks (check `docker stats`)
- Database size continues growing linearly

---

## Troubleshooting

### Generator Keeps Restarting
```bash
# Check logs
docker logs generator

# Common causes:
# 1. MongoDB not ready → Wait 60s, restart generator
# 2. Connection string wrong → Check MONGO_URI in docker-compose.yml
# 3. Python error → Check logs for traceback
```

### Airflow DAG Not Running
```bash
# Check scheduler is running
docker exec -it airflow ps aux | grep scheduler

# If not running, start it
docker exec -it airflow airflow scheduler &

# Check DAG is enabled in UI (toggle switch)
```

### MongoDB Out of Space
```bash
# Check Docker disk usage
docker system df

# Clean up if needed
docker system prune -a --volumes

# Warning: This deletes ALL Docker data
```

### Containers Using Too Much Memory
```bash
# Reduce event rate in docker-compose.yml
# Change: EVENTS_PER_MINUTE=1500
# To:     EVENTS_PER_MINUTE=800

# Restart
docker compose down
docker compose up -d
```

---

## Success Metrics

### Phase 1 Complete When:
✅ All 12 tests pass  
✅ Database accumulates 50-100 MB (5-10 hours runtime)  
✅ No stability issues after 8+ hours  
✅ Airflow DAG executes reliably every 5 minutes  
✅ Memory usage stable (no leaks)

### Ready for Phase 2 When:
✅ All Phase 1 tests pass  
✅ Database size approaching 100-150 MB  
✅ Data generation characteristics confirmed (statistical, not random)  
✅ Comfortable with Airflow UI and logs

---

## Next Steps After Testing

1. **If All Tests Pass:**
   - Let system accumulate 100+ MB of data
   - Document any observations
   - Prepare for Phase 2 (Spark + HDFS)

2. **If Tests Fail:**
   - Review logs: `docker logs <container_name>`
   - Check resource usage: `docker stats`
   - Verify Docker Desktop settings (memory allocation)
   - Consult troubleshooting section

3. **Optional Enhancements:**
   - Add more SKUs/DCs in `config.py` (increase data volume)
   - Adjust event rate (`EVENTS_PER_MINUTE`)
   - Experiment with statistical parameters in `models.py`

---

## Final Verification Command

Run this comprehensive check:

```bash
#!/bin/bash
echo "========================================="
echo "PHASE 1 HEALTH CHECK"
echo "========================================="

echo "1. Container Status:"
docker compose ps

echo -e "\n2. MongoDB Size:"
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  print('Size: ' + (db.stats().dataSize / 1024 / 1024).toFixed(2) + ' MB');
" --quiet

echo -e "\n3. Document Counts:"
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  print('Orders: ' + db.orders_fact.countDocuments());
  print('Shipments: ' + db.shipments_fact.countDocuments());
  print('Inventory: ' + db.inventory_fact.countDocuments());
" --quiet

echo -e "\n4. Data Freshness:"
docker exec -it mongo mongosh -u admin -p admin123 --eval "
  use supply_chain;
  var latest = db.orders_fact.find().sort({order_ts: -1}).limit(1).toArray()[0];
  if (latest) {
    var ageSeconds = (new Date() - latest.order_ts) / 1000;
    print('Latest order: ' + ageSeconds.toFixed(0) + ' seconds ago');
  }
" --quiet

echo -e "\n5. Resource Usage:"
docker stats --no-stream

echo -e "\n========================================="
echo "✅ Phase 1 Health Check Complete"
echo "========================================="
```

Save as `health_check.sh`, make executable (`chmod +x health_check.sh`), and run.

---

**Phase 1 testing complete! Ready for Phase 2? 🚀**


# Supply Chain BDA Pipeline - Architecture

## Phase 1 Architecture (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│                      PHASE 1: FOUNDATION                        │
│                  (MongoDB + Generator + Airflow)                │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  CONTAINER: generator                                            │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Statistical Data Generator (Python)                   │     │
│  │  - Poisson order arrivals (context-aware λ)           │     │
│  │  - Normal lead time distribution                       │     │
│  │  - Log-normal pricing                                  │     │
│  │  - Exponential delays                                  │     │
│  │  - Correlated attributes                               │     │
│  │                                                         │     │
│  │  Rate: ~1500 events/min (60s intervals)               │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                      │
│                   writes to MongoDB                              │
└──────────────────────────────────────────────────────────────────┘

                            ↓

┌──────────────────────────────────────────────────────────────────┐
│  CONTAINER: mongo (mongo:6.0)                                    │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Hot Data Storage (Fresh Streaming Data)              │     │
│  │                                                         │     │
│  │  Fact Tables (Time-Series Events):                    │     │
│  │    • orders_fact       (~1000/min)                    │     │
│  │    • shipments_fact    (~400/min)                     │     │
│  │    • inventory_fact    (~40/min)                      │     │
│  │                                                         │     │
│  │  Dimension Tables (Reference):                         │     │
│  │    • regions_dim       (4 records)                    │     │
│  │    • dcs_dim           (5 records)                    │     │
│  │    • skus_dim          (8 records)                    │     │
│  │    • suppliers_dim     (4 records)                    │     │
│  │                                                         │     │
│  │  State Collection:                                     │     │
│  │    • inventory_state   (40 records, updated)          │     │
│  │                                                         │     │
│  │  Current Size: Growing at ~1 MB/min                   │     │
│  │  Target: 300 MB (triggers archival in Phase 2)        │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘

                            ↓

┌──────────────────────────────────────────────────────────────────┐
│  CONTAINER: airflow (apache/airflow:2.10.2)                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Orchestration & Monitoring                            │     │
│  │                                                         │     │
│  │  DAG: monitor_data_pipeline_phase1                     │     │
│  │  Schedule: */5 * * * * (every 5 minutes)              │     │
│  │                                                         │     │
│  │  Tasks:                                                 │     │
│  │    1. check_mongo_connection                           │     │
│  │    2. monitor_data_volume                              │     │
│  │    3. check_data_freshness                             │     │
│  │    4. log_system_status                                │     │
│  │                                                         │     │
│  │  UI: http://localhost:8080                             │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase 2 Architecture (Planned - Next Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 2: ANALYTICS + ARCHIVING                     │
│         (+ Spark + HDFS + Redis + Archival Logic)              │
└─────────────────────────────────────────────────────────────────┘

                    [Generator] (existing)
                         ↓
                    [MongoDB] (existing)
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                  ↓
   [Airflow DAG 1]                   [Airflow DAG 2]
   archive_to_hdfs                   compute_kpis
   (when size > 300MB)               (every 1-2 min)
        ↓                                  ↓
        ↓                            [Spark Master]
        ↓                                  ↓
        ↓                            [Spark Worker]
        ↓                                  ↓
        ↓                            Read MongoDB
        ↓                            Join fact × dims
        ↓                            Compute KPIs
        ↓                                  ↓
   [HDFS NameNode]                      [Redis]
        ↓                            (cache KPIs)
   [HDFS DataNode]                        ↓
   (Parquet files)                  [Dashboard]
   Partitioned:                     (Phase 3)
   /archive/
     event_date=2025-12-25/
       hour=14/
         part-00000.parquet

   + Metadata (JSON):
   {
     "archive_id": "...",
     "date_range": [...],
     "record_count": 150000,
     "size_mb": 320
   }
```

---

## Detailed Layer Breakdown

### Layer 1: Data Ingestion ✅ (Phase 1)
**Component:** `generator` container  
**Technology:** Python 3.11 + NumPy  
**Function:** Generate streaming supply chain events using statistical models  
**Output:** MongoDB writes (1500 events/min)

### Layer 2: Fresh Data Storage ✅ (Phase 1)
**Component:** `mongo` container  
**Technology:** MongoDB 6.0 (ARM64 native)  
**Function:** Hot data store for recent events (< 300 MB)  
**Schema:** Star schema (3 fact tables, 4 dimension tables)

### Layer 3: Metadata Storage ⏳ (Phase 2)
**Component:** HDFS `/archive/metadata/`  
**Technology:** JSON manifests in HDFS  
**Function:** Track archival batches (date ranges, counts, sizes)

### Layer 4: Archive Storage ⏳ (Phase 2)
**Component:** HDFS NameNode + DataNode  
**Technology:** Hadoop 3.2.1 (Rosetta emulation on M1)  
**Function:** Cold storage for data > 300 MB  
**Format:** Parquet (columnar, compressed)

### Layer 5: Staging & Transformation ⏳ (Phase 2)
**Component:** Spark jobs  
**Function:** Clean, validate, enrich data before analytics  
**Operations:** Null handling, schema validation, derived columns

### Layer 6: Analytics (Spark SQL / OLAP) ⏳ (Phase 2)
**Component:** Spark Master + Worker  
**Function:** Compute KPIs via multi-table joins  
**Queries:**
- WHERE (time-windowed)
- GROUP BY (sku, dc, region)
- HAVING (threshold filters)
- Joins (fact × dimensions)

### Layer 7: Cache ⏳ (Phase 2)
**Component:** Redis 7  
**Function:** Store pre-aggregated KPIs (sub-second reads)  
**TTL:** 60 seconds (refreshed by Spark)

### Layer 8: BI Dashboard ⏳ (Phase 3)
**Component:** Streamlit  
**Function:** Live visualizations (updates every 60s)  
**Data Source:** Reads from Redis only (no MongoDB queries)

---

## Orchestration Flow

### Phase 1 (Current)
```
[Airflow Scheduler]
    ↓
    ├─> Every 5 min: monitor_data_pipeline_phase1
    │       ├─> Check MongoDB health
    │       ├─> Monitor data volume
    │       ├─> Check data freshness
    │       └─> Log system status
    └─> (Generator runs independently, not DAG-managed)
```

### Phase 2 (Planned)
```
[Airflow Scheduler]
    ↓
    ├─> Every 5 min: check_mongodb_size
    │       └─> If size > 300 MB:
    │           └─> Trigger: archive_to_hdfs
    │               ├─> spark-submit archive_mongo_to_hdfs.py
    │               ├─> Move old data to HDFS (Parquet)
    │               ├─> Write metadata JSON
    │               └─> Delete archived data from MongoDB
    │
    └─> Every 1 min: compute_kpis
            └─> spark-submit compute_minute_kpis.py
                ├─> Read MongoDB (last 15 min)
                ├─> Join orders × inventory × skus × dcs × regions
                ├─> Compute 5 KPIs
                └─> Write to Redis cache
```

---

## Data Flow Diagram

```
REAL-TIME PATH (Hot Data):
┌─────────┐     ┌─────────┐     ┌───────┐     ┌──────────┐
│Generator│ --> │ MongoDB │ --> │ Spark │ --> │  Redis   │
│(Python) │     │ (Hot)   │     │(OLAP) │     │ (Cache)  │
└─────────┘     └─────────┘     └───────┘     └──────────┘
                                                     ↓
                                              ┌──────────┐
                                              │Dashboard │
                                              │(Streamlit│
                                              └──────────┘

ARCHIVAL PATH (Cold Data):
┌─────────┐     ┌─────────┐     ┌──────────────────┐
│ Airflow │ --> │  Spark  │ --> │ HDFS (Parquet)   │
│(Trigger)│     │(Archive)│     │ + Metadata (JSON)│
└─────────┘     └─────────┘     └──────────────────┘
                      ↑
                ┌─────────┐
                │ MongoDB │
                │ (Prune) │
                └─────────┘
```

---

## KPI Computation (Phase 2 Design)

### KPI 1: Total Inventory Level
```sql
SELECT sku_id, dc_id, SUM(on_hand_qty) AS total_inventory
FROM inventory_fact
WHERE inventory_ts >= NOW() - INTERVAL 15 MINUTES
GROUP BY sku_id, dc_id
```

### KPI 2: Stockout Risk (Days Until Stockout)
```sql
SELECT 
    i.sku_id, 
    i.dc_id,
    AVG(i.on_hand_qty) AS avg_stock,
    SUM(o.quantity) / 15.0 AS units_per_min,
    (avg_stock / NULLIF(units_per_min, 0)) / 1440 AS days_to_stockout
FROM inventory_fact i
LEFT JOIN orders_fact o 
    ON i.sku_id = o.sku_id 
    AND i.dc_id = o.dc_id
WHERE i.inventory_ts >= NOW() - INTERVAL 15 MINUTES
  AND o.order_ts >= NOW() - INTERVAL 15 MINUTES
GROUP BY i.sku_id, i.dc_id
HAVING days_to_stockout < 7
```

### KPI 3: Supplier Lead Time Performance
```sql
SELECT 
    s.supplier_id,
    AVG(sf.lead_time_days) AS avg_lead_time,
    STDDEV(sf.lead_time_days) AS lead_time_variance
FROM shipments_fact sf
JOIN suppliers_dim s ON sf.supplier_id = s.supplier_id
WHERE sf.shipment_ts >= NOW() - INTERVAL 30 MINUTES
GROUP BY s.supplier_id
```

### KPI 4: DC Utilization Rate
```sql
SELECT 
    d.dc_id,
    SUM(i.on_hand_qty * sk.storage_m3) AS current_volume_m3,
    d.capacity_m3,
    (current_volume_m3 / d.capacity_m3) AS utilization_rate
FROM inventory_fact i
JOIN dcs_dim d ON i.dc_id = d.dc_id
JOIN skus_dim sk ON i.sku_id = sk.sku_id
WHERE i.inventory_ts >= NOW() - INTERVAL 15 MINUTES
GROUP BY d.dc_id
HAVING utilization_rate > 0.85
```

### KPI 5: Order Fulfillment Rate
```sql
SELECT 
    r.region_id,
    COUNT(*) AS total_orders,
    SUM(o.order_value) AS total_revenue
FROM orders_fact o
JOIN dcs_dim d ON o.dc_id = d.dc_id
JOIN regions_dim r ON d.region_id = r.region_id
WHERE o.order_ts >= NOW() - INTERVAL 15 MINUTES
GROUP BY r.region_id
```

---

## Resource Allocation Summary

| Phase | Services | Total Memory | Docker Limit Needed |
|-------|----------|--------------|---------------------|
| **Phase 1** | 3 (Mongo, Generator, Airflow) | ~2.3 GB | 4 GB |
| **Phase 2** | 8 (+ Spark, HDFS, Redis) | ~5.0 GB | 6 GB |
| **Phase 3** | 9 (+ Dashboard) | ~5.3 GB | 6 GB |

**macOS M1 8GB:** Safe (leaves 2-3 GB for OS)

---

## Technology Justification

### Why MongoDB?
- ✅ Fast writes (high insert throughput)
- ✅ Flexible schema (easy to iterate)
- ✅ Native time-series support
- ✅ ARM64 compatible

### Why Spark?
- ✅ Distributed processing (scales horizontally)
- ✅ SQL-like syntax (meets OLAP requirement)
- ✅ Native Parquet support
- ✅ MongoDB connector available

### Why HDFS?
- ✅ Assignment requirement (mandatory)
- ✅ Industry standard for big data archival
- ✅ Fault-tolerant (replication)
- ⚠️ Requires Rosetta on M1 (acceptable trade-off)

### Why Redis?
- ✅ Sub-millisecond reads (dashboard performance)
- ✅ Decouples visualization from compute
- ✅ TTL support (auto-expire stale data)

### Why Airflow?
- ✅ Assignment requirement (mandatory)
- ✅ Visual DAG editor (easy debugging)
- ✅ Cron-like scheduling
- ✅ Retry logic & monitoring

### Why Streamlit?
- ✅ Python-native (easy integration)
- ✅ Auto-refresh support
- ✅ Interactive filters
- ✅ Fast development

---

## Security Considerations

### Current (Phase 1)
- MongoDB: Username/password authentication
- Airflow: Admin user with strong password
- Docker network: Default bridge (isolated from host)

### Future Enhancements (Production)
- TLS/SSL for MongoDB connections
- Airflow RBAC (role-based access control)
- Secrets management (Docker secrets or Vault)
- HDFS Kerberos authentication

---

## Performance Optimization Strategies

### Already Implemented (Phase 1)
✅ MongoDB indexes on timestamps  
✅ Bulk inserts (ordered=False for parallelism)  
✅ Conservative memory limits  
✅ WiredTiger cache limit (512MB)

### Planned (Phase 2)
- Spark broadcast joins (for small dimensions)
- Parquet columnar storage (efficient compression)
- Partition pruning (date/hour partitions)
- Redis pipeline batching
- Early aggregation before joins

---

## Monitoring & Observability

### Phase 1 (Current)
- Airflow DAG logs
- Docker logs (`docker logs <container>`)
- MongoDB shell queries

### Phase 2 (Planned)
- Spark UI (port 8081)
- HDFS NameNode UI (port 9870)
- Airflow task logs with XCom
- Custom metrics in Redis

### Phase 3 (Future)
- Prometheus + Grafana (optional)
- Custom alerting (email/Slack on failures)

---

## Testing Strategy

### Unit Tests
- Statistical model functions (models.py)
- Data validation logic

### Integration Tests
- End-to-end data flow (generator → MongoDB → Spark → Redis)
- Archival process (MongoDB → HDFS)

### Performance Tests
- Sustained load (24-hour continuous generation)
- Memory leak detection (`docker stats`)

### Manual Tests
- Dashboard visual inspection
- Airflow DAG execution
- MongoDB query performance

---

## Next Steps Checklist

### Before Phase 2
- [ ] Let Phase 1 run for 2-5 hours
- [ ] Verify database reaches 50-100 MB
- [ ] Confirm no memory/CPU issues
- [ ] Review Airflow logs for any warnings

### Phase 2 Implementation
- [ ] Add Spark services to docker-compose.yml
- [ ] Add HDFS services (with Rosetta enabled)
- [ ] Add Redis service
- [ ] Implement archive_mongo_to_hdfs.py (Spark job)
- [ ] Implement compute_minute_kpis.py (Spark job)
- [ ] Create new Airflow DAGs for archiving + analytics
- [ ] Test archival process manually
- [ ] Verify KPIs appear in Redis

---

## Questions & Answers

**Q: Why not use Kafka for streaming?**  
A: Controlled generation (not event-driven) simplifies testing and meets requirements without added complexity.

**Q: Why SQLite for Airflow (not PostgreSQL)?**  
A: SequentialExecutor is sufficient for single-node. SQLite reduces overhead.

**Q: Can I run this on x86 Linux?**  
A: Yes! Remove Rosetta requirement, use native Hadoop images.

**Q: What if I exceed 8GB RAM?**  
A: Reduce EVENTS_PER_MINUTE in generator, lower Spark worker memory, or pause services selectively.

**Q: How to reset and start fresh?**  
A: `docker compose down -v` (deletes all data volumes)

---

## Conclusion

Phase 1 establishes a **production-grade foundation** for real-time Big Data Analytics:

✅ Statistically realistic data generation  
✅ Proper schema design (star schema)  
✅ Orchestration & monitoring  
✅ Resource-efficient (2.3 GB)  
✅ ARM64 native (no emulation)  
✅ Ready for Phase 2 expansion

**The hard part is done. Phases 2-3 build on this solid base!** 🚀


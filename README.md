# Supply Chain Analytics - Big Data Pipeline

A real-time Big Data Analytics pipeline for supply chain and inventory optimization. The system processes streaming supply chain events, computes key performance indicators (KPIs) using distributed analytics, and provides real-time visibility through an interactive dashboard.

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture Overview](#architecture-overview)
- [End-to-End Execution Flow](#end-to-end-execution-flow)
- [Data Processing Model](#data-processing-model)
- [Analytics Dashboard](#analytics-dashboard)
- [Reliability and Observability](#reliability-and-observability)
- [How to Run the System](#how-to-run-the-system)
- [Validation and Verification](#validation-and-verification)
- [Repository Structure](#repository-structure)

## Project Overview

This system addresses supply chain optimization challenges for retail operations, specifically designed for grocery and FMCG supply chains. It provides real-time monitoring of inventory levels, stockout risks, supplier performance, distribution center utilization, and regional revenue metrics.

The pipeline ingests high-volume streaming data, performs OLAP-style analytics with multi-table joins, and maintains both hot (MongoDB) and cold (HDFS) data tiers for comprehensive historical analysis.

## Architecture Overview

The system is containerized using Docker Compose and consists of the following components:

**Airflow** orchestrates the entire pipeline. It schedules Spark jobs for KPI computation every minute and conditional archival jobs every five minutes. Airflow uses SequentialExecutor with SQLite metadata storage.

**Spark** performs distributed analytics in a standalone cluster configuration (master and worker nodes). Spark jobs read from MongoDB, perform multi-table joins with dimension tables, compute KPIs using Spark SQL, and write results to Redis. The system implements a unified OLAP pattern that logically combines hot data from MongoDB with cold archived data from HDFS.

**MongoDB** serves as the hot data store, receiving streaming events from the data generator. It maintains fact tables (orders, shipments, inventory snapshots) and dimension tables (SKUs, distribution centers, regions, suppliers) in a star schema design.

**Redis** caches pre-computed KPI results as JSON with a 60-second TTL. The dashboard reads exclusively from Redis, ensuring sub-second response times without querying MongoDB or triggering Spark jobs.

**HDFS** provides cold storage for historical data. When MongoDB exceeds a configurable threshold (300MB by default, 30MB in demo mode), older data is archived to HDFS in Parquet format, partitioned by date and hour, with metadata JSON files tracking archive batches.

**Analytics Dashboard** is a Streamlit application that visualizes KPIs in real-time. It reads pre-computed metrics from Redis, applies client-side filters, and auto-refreshes every 60 seconds.

## End-to-End Execution Flow

Starting the system with `docker compose up -d` initializes all services. The data generator begins producing supply chain events every 60 seconds, writing to MongoDB collections. Events include customer orders, supplier shipments, and inventory state snapshots.

Airflow scheduler monitors DAG schedules and triggers tasks accordingly. The `compute_kpis_phase2` DAG runs every minute, executing a BashOperator that submits a Spark job via `spark-submit`. The Spark job connects to the Spark master, which assigns executors from the worker pool.

The Spark job reads recent data from MongoDB (last 15 minutes by default), optionally reads historical data from HDFS archives, and performs a logical union of hot and cold data. It joins fact tables with dimension tables, applies aggregations and window functions, and computes five KPIs: total inventory level by SKU and distribution center, stockout risk (days until stockout), supplier lead time performance, distribution center utilization rate, and regional revenue and order fulfillment metrics.

Computed KPIs are serialized to JSON and written to Redis with appropriate keys. The dashboard continuously polls Redis, deserializes the data, applies user-selected filters, and renders visualizations.

The `archive_to_hdfs_phase2` DAG runs every five minutes. It first checks MongoDB database size. If the size exceeds the configured threshold, it triggers a Spark archival job that reads data older than a cutoff time, writes it to HDFS in Parquet format with date/hour partitioning, generates metadata JSON, and deletes the archived data from MongoDB.

## Data Processing Model

The system uses a micro-batch processing model. Data generation occurs continuously at 60-second intervals, producing approximately 1,500 events per minute. Spark jobs process these events in one-minute batches, computing KPIs over a rolling 15-minute window.

KPI computation involves multi-table joins between fact and dimension tables. For example, inventory level computation joins inventory snapshots with SKU and distribution center dimensions, then aggregates by SKU-DC combination. Stockout risk calculation joins inventory with order history to compute demand velocity and project days until stockout.

The system implements a unified OLAP pattern where Spark logically unions recent MongoDB data with historical HDFS archives at query time. This provides comprehensive analytics without physically merging data or copying archives back to MongoDB.

Data refresh occurs at two levels: Spark recomputes KPIs every minute and writes to Redis, while the dashboard reads from Redis every 60 seconds. This design ensures the dashboard always displays metrics computed within the last minute, with Redis serving as a low-latency cache layer.

## Analytics Dashboard

The dashboard displays five executive KPIs: total inventory units across all SKU-DC combinations, count of active stockout alerts (items with less than 7 days supply), average supplier lead time in days, average distribution center utilization percentage, and total revenue from fulfilled orders in the last 15 minutes.

Interactive visualizations include inventory distribution by distribution center (stacked bar charts), revenue by region (donut charts), distribution center utilization versus capacity (horizontal bar charts with threshold indicators), and supplier performance analysis (scatter plots showing reliability versus lead time).

The dashboard consumes precomputed KPIs from Redis. It does not query MongoDB directly or trigger Spark jobs. All filtering (by distribution center, SKU, or category) occurs client-side on data already loaded from Redis.

The dashboard auto-refreshes every 60 seconds using Streamlit's rerun mechanism. Each refresh fetches the latest KPI data from Redis, ensuring users see metrics updated within the last minute. The dashboard displays a "Last Updated" timestamp sourced from Redis to indicate data freshness.

## Reliability and Observability

Failure handling is managed through Airflow's retry mechanisms. DAG tasks are configured with one retry and a 30-second delay. Task failures are visible in the Airflow UI, with detailed logs available for each task instance.

Spark job failures surface in multiple ways: Airflow task logs show the `spark-submit` command output, the Spark Master UI displays application status and execution details, and executor logs are accessible through the Spark UI. Failed Spark jobs are marked as failed in Airflow, triggering retry logic.

System observability is provided through several interfaces. The Airflow UI (port 8080) shows DAG execution history, task status, and logs. The Spark Master UI (port 8081) displays running and completed applications, executor status, and resource utilization. The HDFS NameNode UI (port 9870) shows file system structure and archive contents.

Container logs are accessible via `docker logs` for each service. Airflow task logs are stored in `airflow/logs/` and are also viewable through the Airflow UI. Spark application logs are available through the Spark UI and container logs.

## How to Run the System

### Prerequisites

- Docker Desktop installed and running
- At least 6GB RAM allocated to Docker
- Docker Compose v2.0 or later
- For macOS M1/M2: Rosetta 2 emulation enabled for x86_64 containers (HDFS uses x86 images)

### Starting the System

```bash
cd supply-chain-bda
docker compose up -d
```

This command builds custom images (generator, airflow, spark, dashboard) and starts all services. Initial startup takes approximately 60-90 seconds for all containers to become healthy.

### Service URLs

- **Airflow UI**: http://localhost:8080
  - Username: `admin`
  - Password: `admin`

- **Spark Master UI**: http://localhost:8081

- **HDFS NameNode UI**: http://localhost:9870

- **Analytics Dashboard**: http://localhost:8501

- **MongoDB**: localhost:27017
  - Username: `admin`
  - Password: `admin123`
  - Database: `supply_chain`

- **Redis**: localhost:6379

### Stopping the System

```bash
docker compose down
```

To remove all data volumes:

```bash
docker compose down -v
```

## Validation and Verification

### Verify All Services Are Running

```bash
docker compose ps
```

All containers should show "Up" status. MongoDB and HDFS NameNode should show "healthy".

### Trigger KPI Computation Manually

```bash
docker exec airflow airflow dags trigger compute_kpis_phase2
```

Wait 30-60 seconds, then verify in Airflow UI that the task completed successfully. Check Redis for KPI keys:

```bash
docker exec redis redis-cli KEYS "kpi:*"
```

Expected keys: `kpi:inventory_level`, `kpi:stockout_alerts`, `kpi:supplier_performance`, `kpi:dc_utilization`, `kpi:regional_performance`, `kpi:last_update`.

### Verify Data Flow End-to-End

Check MongoDB is receiving data:

```bash
docker exec mongo mongosh --quiet -u admin -p admin123 --authenticationDatabase admin supply_chain --eval "print(db.orders_fact.countDocuments())"
```

The count should increase over time. Check Redis has recent KPI data:

```bash
docker exec redis redis-cli GET kpi:last_update
```

The timestamp should be within the last 2 minutes. Verify Spark jobs are executing:

Open http://localhost:8081 and check "Completed Applications" section. You should see applications named "supply-chain-kpi-computation" with status "FINISHED".

### Verify HDFS Archival

Check if archival has occurred (requires MongoDB size > threshold):

```bash
docker exec namenode hdfs dfs -ls -R /supply_chain_archive
```

If archival has run, you should see Parquet files in partitioned directories under `orders_fact/`, `shipments_fact/`, and `inventory_fact/`, plus metadata JSON files in `metadata/`.

### Check Dashboard Data

Open http://localhost:8501. The dashboard should display KPI cards with non-zero values and interactive charts. If KPIs show zero or "No data available", verify that:
1. Spark jobs are running successfully (check Airflow UI)
2. Redis contains KPI keys (use command above)
3. At least 2-3 minutes have passed since system startup

## Repository Structure

```
supply-chain-bda/
├── docker-compose.yml          # Service orchestration and configuration
├── generator/                  # Statistical data generation
│   ├── generator.py           # Main streaming logic with inventory balance equations
│   ├── config.py               # Domain configuration (SKUs, DCs, suppliers, regions)
│   ├── models.py               # Statistical models (Poisson, Normal, Log-Normal)
│   └── Dockerfile
├── airflow/                    # Orchestration layer
│   ├── dags/                   # Airflow DAG definitions
│   │   ├── compute_kpis_phase2.py      # KPI computation DAG (every 1 minute)
│   │   ├── archive_to_hdfs_phase2.py   # Archival DAG (every 5 minutes, conditional)
│   │   └── monitor_data_pipeline.py    # Health monitoring DAG
│   ├── logs/                   # Airflow task execution logs
│   └── Dockerfile
├── spark/                      # Distributed analytics
│   ├── jobs/                   # Spark job definitions
│   │   ├── compute_minute_kpis.py      # KPI computation with OLAP unification
│   │   └── archive_mongo_to_hdfs.py    # MongoDB to HDFS archival logic
│   └── Dockerfile
└── dashboard/                  # Real-time analytics dashboard
    ├── app.py                  # Streamlit application
    └── Dockerfile
```

The `generator/` directory contains the data generation logic that produces realistic supply chain events using statistical distributions. The `airflow/dags/` directory defines workflow orchestration. The `spark/jobs/` directory contains analytics logic that reads from MongoDB and HDFS, performs joins and aggregations, and writes results to Redis. The `dashboard/` directory contains the Streamlit application that visualizes pre-computed KPIs.

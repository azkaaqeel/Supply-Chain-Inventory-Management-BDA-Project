#!/bin/bash

# Phase 2 Startup Script
# Starts all Phase 1 + Phase 2 services and initializes HDFS

echo "========================================================================"
echo "🚀 PHASE 2 STARTUP SCRIPT"
echo "========================================================================"

# Navigate to project directory
cd "$(dirname "$0")"

echo ""
echo "📋 Step 1: Stopping existing containers..."
docker compose down

echo ""
echo "🔨 Step 2: Building and starting all services..."
docker compose up -d --build

echo ""
echo "⏳ Step 3: Waiting for services to initialize (60 seconds)..."
sleep 60

echo ""
echo "📊 Step 4: Checking container status..."
docker compose ps

echo ""
echo "🗂️  Step 5: Initializing HDFS directories..."
docker exec -it namenode bash -c "
  echo '  Creating HDFS archive directories...'
  hdfs dfs -mkdir -p /supply_chain_archive/metadata
  hdfs dfs -mkdir -p /supply_chain_archive/orders_fact
  hdfs dfs -mkdir -p /supply_chain_archive/shipments_fact
  hdfs dfs -mkdir -p /supply_chain_archive/inventory_fact
  hdfs dfs -chmod -R 777 /supply_chain_archive
  echo '  ✅ HDFS directories created'
"

echo ""
echo "✅ Step 6: Verifying HDFS structure..."
docker exec -it namenode hdfs dfs -ls /supply_chain_archive

echo ""
echo "========================================================================"
echo "✅ PHASE 2 STARTUP COMPLETE"
echo "========================================================================"
echo ""
echo "📍 Access Points:"
echo "   - Airflow UI:    http://localhost:8080  (admin/admin)"
echo "   - Spark UI:      http://localhost:8081"
echo "   - HDFS UI:       http://localhost:9870"
echo ""
echo "📝 Next Steps:"
echo "   1. Open Airflow UI"
echo "   2. Enable DAGs: compute_kpis_phase2, archive_to_hdfs_phase2"
echo "   3. Trigger compute_kpis_phase2 manually to test"
echo "   4. Check Redis for KPI data:"
echo "      docker exec -it redis redis-cli KEYS 'kpi:*'"
echo ""
echo "📖 Full documentation: PHASE2_IMPLEMENTATION.md"
echo "========================================================================"


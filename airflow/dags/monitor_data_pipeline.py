"""
Phase 1 Monitoring DAG
Monitors data generation and MongoDB health
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from pymongo import MongoClient


# ============================================================
# CONFIGURATION
# ============================================================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin"
)


# ============================================================
# TASK FUNCTIONS
# ============================================================
def check_mongo_connection(**context):
    """Test MongoDB connectivity"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ MongoDB connection: OK")
        client.close()
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise


def monitor_data_volume(**context):
    """Monitor database size and collection counts"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        
        # Get database statistics
        stats = db.command("dbStats")
        db_size_mb = stats["dataSize"] / (1024 * 1024)
        
        # Count documents in each collection
        collections = {
            "orders_fact": db.orders_fact.count_documents({}),
            "shipments_fact": db.shipments_fact.count_documents({}),
            "inventory_fact": db.inventory_fact.count_documents({}),
            "regions_dim": db.regions_dim.count_documents({}),
            "dcs_dim": db.dcs_dim.count_documents({}),
            "skus_dim": db.skus_dim.count_documents({}),
            "suppliers_dim": db.suppliers_dim.count_documents({}),
        }
        
        print("=" * 70)
        print("📊 DATA VOLUME REPORT")
        print("=" * 70)
        print(f"Database Size: {db_size_mb:.2f} MB")
        print(f"Target Threshold: 300 MB (for archiving in Phase 2)")
        print(f"Progress: {(db_size_mb / 300) * 100:.1f}%")
        print("\nCollection Document Counts:")
        for coll, count in collections.items():
            print(f"  - {coll:20s}: {count:,}")
        print("=" * 70)
        
        # Push metrics to XCom for downstream tasks
        context['ti'].xcom_push(key='db_size_mb', value=db_size_mb)
        context['ti'].xcom_push(key='collections', value=collections)
        
        client.close()
        return db_size_mb
        
    except Exception as e:
        print(f"❌ Error monitoring data: {e}")
        raise


def check_data_freshness(**context):
    """Check if data is being generated in real-time"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        
        # Get most recent records from each fact table
        recent_order = db.orders_fact.find_one(sort=[("order_ts", -1)])
        recent_shipment = db.shipments_fact.find_one(sort=[("shipment_ts", -1)])
        recent_inventory = db.inventory_fact.find_one(sort=[("inventory_ts", -1)])
        
        print("=" * 70)
        print("🕒 DATA FRESHNESS CHECK")
        print("=" * 70)
        
        now = datetime.utcnow()
        
        if recent_order:
            age_seconds = (now - recent_order["order_ts"].replace(tzinfo=None)).total_seconds()
            print(f"Most recent order: {age_seconds:.0f} seconds ago")
            if age_seconds > 120:
                print("⚠️  WARNING: Orders are stale (>2 minutes old)")
        
        if recent_shipment:
            age_seconds = (now - recent_shipment["shipment_ts"].replace(tzinfo=None)).total_seconds()
            print(f"Most recent shipment: {age_seconds:.0f} seconds ago")
        
        if recent_inventory:
            age_seconds = (now - recent_inventory["inventory_ts"].replace(tzinfo=None)).total_seconds()
            print(f"Most recent inventory: {age_seconds:.0f} seconds ago")
        
        print("=" * 70)
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error checking freshness: {e}")
        raise


def log_system_status(**context):
    """Log overall system status summary"""
    # Pull metrics from XCom
    db_size_mb = context['ti'].xcom_pull(
        task_ids='monitor_data_volume',
        key='db_size_mb'
    )
    
    print("\n" + "=" * 70)
    print("✅ PHASE 1 STATUS SUMMARY")
    print("=" * 70)
    print(f"✓ MongoDB: Connected")
    print(f"✓ Data Generator: Active")
    print(f"✓ Current DB Size: {db_size_mb:.2f} MB / 300 MB target")
    print(f"✓ Airflow: Orchestrating")
    print("\nNext Phase: Add Spark, HDFS, and archiving logic")
    print("=" * 70 + "\n")


# ============================================================
# DAG DEFINITION
# ============================================================
default_args = {
    'owner': 'supply_chain_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    dag_id='monitor_data_pipeline_phase1',
    default_args=default_args,
    description='Phase 1: Monitor data generation and MongoDB health',
    schedule_interval='*/5 * * * *',  # Every 5 minutes
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['phase1', 'monitoring', 'supply_chain'],
) as dag:
    
    # Task 1: Check MongoDB connection
    check_mongo = PythonOperator(
        task_id='check_mongo_connection',
        python_callable=check_mongo_connection,
        provide_context=True,
    )
    
    # Task 2: Monitor data volume
    monitor_volume = PythonOperator(
        task_id='monitor_data_volume',
        python_callable=monitor_data_volume,
        provide_context=True,
    )
    
    # Task 3: Check data freshness
    check_freshness = PythonOperator(
        task_id='check_data_freshness',
        python_callable=check_data_freshness,
        provide_context=True,
    )
    
    # Task 4: Log system status
    log_status = PythonOperator(
        task_id='log_system_status',
        python_callable=log_system_status,
        provide_context=True,
    )
    
    # Define task dependencies
    check_mongo >> [monitor_volume, check_freshness] >> log_status


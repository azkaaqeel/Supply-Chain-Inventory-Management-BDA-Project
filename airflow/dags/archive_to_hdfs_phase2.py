"""
Phase 2 DAG: Archive to HDFS (Conditional)
Checks MongoDB size and archives to HDFS when > 300MB threshold
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from pymongo import MongoClient

# ============================================================
# CONFIGURATION
# ============================================================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin"
)

# Demo mode: Enables faster archival trigger for demonstrations
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# Archival trigger threshold
if DEMO_MODE:
    ARCHIVE_THRESHOLD_MB = int(os.environ.get("DEMO_THRESHOLD_MB", "30"))  # Demo: 30MB (triggers in ~45 min)
    print("🎬 DEMO MODE ENABLED - Using reduced threshold for demonstration")
else:
    ARCHIVE_THRESHOLD_MB = int(os.environ.get("ARCHIVE_THRESHOLD_MB", "300"))  # Production: 300MB (compliance)

ARCHIVE_THRESHOLD_BYTES = ARCHIVE_THRESHOLD_MB * 1024 * 1024


# ============================================================
# TASK FUNCTIONS
# ============================================================
def check_mongodb_size(**context):
    """
    Check MongoDB database size and decide if archival is needed
    
    Returns:
        str: Task ID to branch to ('trigger_archival' or 'skip_archival')
    """
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        
        # Get database statistics
        stats = db.command("dbStats")
        db_size_bytes = stats["dataSize"]
        db_size_mb = db_size_bytes / (1024 * 1024)
        
        # Get collection counts for logging
        orders_count = db.orders_fact.count_documents({})
        shipments_count = db.shipments_fact.count_documents({})
        inventory_count = db.inventory_fact.count_documents({})
        
        print("=" * 70)
        print("📊 MONGODB SIZE CHECK")
        print("=" * 70)
        mode_indicator = "🎬 DEMO MODE" if DEMO_MODE else "🏢 PRODUCTION MODE"
        print(f"Mode: {mode_indicator}")
        print(f"Database Size: {db_size_mb:.2f} MB")
        print(f"Threshold: {ARCHIVE_THRESHOLD_MB} MB")
        print(f"\nCollection Counts:")
        print(f"  - orders_fact: {orders_count:,}")
        print(f"  - shipments_fact: {shipments_count:,}")
        print(f"  - inventory_fact: {inventory_count:,}")
        print("=" * 70)
        
        # Push metrics to XCom for downstream tasks
        context['ti'].xcom_push(key='db_size_mb', value=db_size_mb)
        context['ti'].xcom_push(key='orders_count', value=orders_count)
        context['ti'].xcom_push(key='shipments_count', value=shipments_count)
        
        client.close()
        
        # Decide whether to trigger archival
        if db_size_bytes > ARCHIVE_THRESHOLD_BYTES:
            print(f"\n⚠️  Database exceeds threshold ({db_size_mb:.2f} MB > {ARCHIVE_THRESHOLD_MB} MB)")
            print("✅ Triggering archival process...")
            return 'trigger_archival'
        else:
            progress_pct = (db_size_mb / ARCHIVE_THRESHOLD_MB) * 100
            print(f"\n✅ Database within threshold ({progress_pct:.1f}% of limit)")
            print("ℹ️  Skipping archival")
            return 'skip_archival'
        
    except Exception as e:
        print(f"❌ Error checking MongoDB size: {e}")
        raise


def log_archival_skipped(**context):
    """Log that archival was skipped"""
    db_size_mb = context['ti'].xcom_pull(task_ids='check_database_size', key='db_size_mb')
    print(f"\nℹ️  Archival skipped - Database size: {db_size_mb:.2f} MB (< {ARCHIVE_THRESHOLD_MB} MB)")


def log_archival_complete(**context):
    """Log archival completion statistics"""
    db_size_before = context['ti'].xcom_pull(task_ids='check_database_size', key='db_size_mb')
    
    # Re-check size after archival
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        stats = db.command("dbStats")
        db_size_after = stats["dataSize"] / (1024 * 1024)
        
        space_freed = db_size_before - db_size_after
        
        print("=" * 70)
        print("✅ ARCHIVAL COMPLETE")
        print("=" * 70)
        print(f"Database Size Before: {db_size_before:.2f} MB")
        print(f"Database Size After:  {db_size_after:.2f} MB")
        print(f"Space Freed: {space_freed:.2f} MB ({(space_freed/db_size_before)*100:.1f}%)")
        print("=" * 70)
        
        client.close()
        
    except Exception as e:
        print(f"⚠️  Could not verify archival results: {e}")


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
    dag_id='archive_to_hdfs_phase2',
    default_args=default_args,
    description='Phase 2: Conditionally archive MongoDB to HDFS when size > 300MB',
    schedule_interval='*/5 * * * *',  # Every 5 minutes
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['phase2', 'archival', 'hdfs', 'spark'],
) as dag:
    
    # ========================================
    # TASK 1: CHECK MONGODB SIZE
    # ========================================
    check_size = BranchPythonOperator(
        task_id='check_database_size',
        python_callable=check_mongodb_size,
        provide_context=True,
    )
    
    # ========================================
    # TASK 2A: TRIGGER ARCHIVAL (if needed)
    # ========================================
    run_archival = BashOperator(
        task_id='trigger_archival',
        bash_command="""
        export PYSPARK_PYTHON=/usr/bin/python3
        export PYSPARK_DRIVER_PYTHON=/usr/bin/python3
        /opt/spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            --conf spark.pyspark.python=/usr/bin/python3 \
            --conf spark.pyspark.driver.python=/usr/bin/python3 \
            --conf spark.mongodb.read.connection.uri=mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin \
            --conf spark.mongodb.write.connection.uri=mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin \
            --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0,org.apache.hadoop:hadoop-client:3.3.4 \
            --driver-memory 512m \
            --executor-memory 768m \
            /opt/spark/jobs/archive_mongo_to_hdfs.py
        """,
        execution_timeout=timedelta(minutes=10),
        env={
            'PYSPARK_PYTHON': '/usr/bin/python3',
            'PYSPARK_DRIVER_PYTHON': '/usr/bin/python3'
        },
    )
    
    # ========================================
    # TASK 2B: SKIP ARCHIVAL (if not needed)
    # ========================================
    skip_archival = PythonOperator(
        task_id='skip_archival',
        python_callable=log_archival_skipped,
        provide_context=True,
    )
    
    # ========================================
    # TASK 3: LOG COMPLETION
    # ========================================
    log_complete = PythonOperator(
        task_id='log_archival_complete',
        python_callable=log_archival_complete,
        provide_context=True,
        trigger_rule='none_failed_min_one_success',  # Run if either branch succeeds
    )
    
    # ========================================
    # DAG FLOW
    # ========================================
    check_size >> [run_archival, skip_archival] >> log_complete


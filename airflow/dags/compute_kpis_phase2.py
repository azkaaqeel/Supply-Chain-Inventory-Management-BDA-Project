"""
Phase 2 DAG: Compute KPIs Every Minute
Triggers Spark job to compute supply chain KPIs and cache in Redis
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# ============================================================
# DAG CONFIGURATION
# ============================================================
default_args = {
    'owner': 'supply_chain_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=30),
}

with DAG(
    dag_id='compute_kpis_phase2',
    default_args=default_args,
    description='Phase 2: Compute real-time KPIs using Spark and cache in Redis',
    schedule_interval='* * * * *',  # Every 1 minute
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['phase2', 'kpi', 'spark', 'redis'],
) as dag:
    
    # ========================================
    # TASK: SPARK KPI COMPUTATION (DISTRIBUTED MODE)
    # ========================================
    # Running in distributed mode with Spark master + workers cluster
    # Python versions now aligned (Airflow 3.8 matches Spark 3.8)
    compute_kpis = BashOperator(
        task_id='spark_compute_kpis',
        bash_command="""
        /opt/spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            --conf spark.mongodb.read.connection.uri=mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin \
            --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0 \
            --driver-memory 512m \
            --executor-memory 512m \
            /opt/spark/jobs/compute_minute_kpis.py
        """,
        execution_timeout=timedelta(minutes=3),
    )
    
    # Single task in this DAG
    compute_kpis


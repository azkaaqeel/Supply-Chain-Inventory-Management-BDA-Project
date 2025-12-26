"""
Phase 2: MongoDB to HDFS Archival
Archives old data when MongoDB exceeds 300MB threshold
Stores data in partitioned Parquet format with metadata
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, year, month, dayofmonth, hour as Fhour

# ============================================================
# CONFIGURATION
# ============================================================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin"
)

HDFS_BASE_PATH = "hdfs://namenode:8020/supply_chain_archive"
ARCHIVE_OLDER_THAN_MINUTES = int(os.environ.get("ARCHIVE_OLDER_THAN_MINUTES", "120"))  # Archive data > 2 hours old


# ============================================================
# MONGODB READER
# ============================================================
def read_mongo(spark, collection_name):
    """Read from MongoDB collection"""
    return (
        spark.read
        .format("mongodb")
        .option("connection.uri", MONGO_URI)
        .option("database", "supply_chain")
        .option("collection", collection_name)
        .load()
    )


# ============================================================
# ARCHIVE FUNCTION
# ============================================================
def archive_collection(spark, collection_name, timestamp_column):
    """
    Archive old data from a MongoDB collection to HDFS
    
    Args:
        spark: SparkSession
        collection_name: MongoDB collection to archive
        timestamp_column: Column name containing timestamp
    
    Returns:
        dict: Archive statistics
    """
    print(f"\n📦 Archiving {collection_name}...")
    
    # Calculate cutoff time
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ARCHIVE_OLDER_THAN_MINUTES)
    print(f"   Cutoff: {cutoff.isoformat()}")
    
    # Read old data from MongoDB
    df = read_mongo(spark, collection_name).where(
        col(timestamp_column) < lit(cutoff)
    )
    
    record_count = df.count()
    
    if record_count == 0:
        print(f"   ℹ️  No records to archive")
        return None
    
    print(f"   📊 Found {record_count:,} records to archive")
    
    # Add partitioning columns
    df_partitioned = (
        df
        .withColumn("event_date", col(timestamp_column).cast("date"))
        .withColumn("event_year", year(col(timestamp_column)))
        .withColumn("event_month", month(col(timestamp_column)))
        .withColumn("event_day", dayofmonth(col(timestamp_column)))
        .withColumn("event_hour", Fhour(col(timestamp_column)))
    )
    
    # Calculate date range
    from pyspark.sql.functions import min as Fmin, max as Fmax
    
    date_stats_row = df.agg(
        Fmin(timestamp_column).alias("min_date"),
        Fmax(timestamp_column).alias("max_date")
    ).collect()[0]
    
    min_date = date_stats_row["min_date"]
    max_date = date_stats_row["max_date"]
    
    # Write to HDFS in Parquet format (partitioned by date and hour)
    output_path = f"{HDFS_BASE_PATH}/{collection_name}"
    
    print(f"   💾 Writing to HDFS: {output_path}")
    
    df_partitioned.write \
        .mode("append") \
        .partitionBy("event_date", "event_hour") \
        .parquet(output_path)
    
    print(f"   ✅ Archived {record_count:,} records to HDFS")
    
    # Calculate approximate size (in MB)
    # Rough estimate: each record ~500 bytes
    size_mb = (record_count * 500) / (1024 * 1024)
    
    return {
        "collection": collection_name,
        "record_count": record_count,
        "size_mb": round(size_mb, 2),
        "date_range": {
            "min": min_date.isoformat() if min_date else None,
            "max": max_date.isoformat() if max_date else None
        }
    }


# ============================================================
# METADATA GENERATION
# ============================================================
def write_metadata(spark, archive_stats_list):
    """
    Write archive metadata to HDFS as JSON
    
    Args:
        spark: SparkSession
        archive_stats_list: List of archive statistics
    """
    print("\n📝 Writing metadata...")
    
    archive_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    metadata = {
        "archive_id": archive_id,
        "created_at": timestamp,
        "archived_collections": archive_stats_list,
        "total_records": sum(s["record_count"] for s in archive_stats_list if s),
        "total_size_mb": sum(s["size_mb"] for s in archive_stats_list if s),
        "hdfs_base_path": HDFS_BASE_PATH,
        "archive_policy": {
            "older_than_minutes": ARCHIVE_OLDER_THAN_MINUTES,
            "format": "parquet",
            "compression": "snappy",
            "partitioned_by": ["event_date", "event_hour"]
        }
    }
    
    # Convert to JSON
    metadata_json = json.dumps(metadata, indent=2)
    
    # Write to HDFS
    metadata_path = f"{HDFS_BASE_PATH}/metadata/archive_{archive_id}.json"
    
    # Create DataFrame with single row containing JSON
    metadata_df = spark.createDataFrame([(metadata_json,)], ["metadata"])
    
    metadata_df.write \
        .mode("overwrite") \
        .text(metadata_path)
    
    print(f"   ✅ Metadata written: {metadata_path}")
    print(f"   📊 Total archived: {metadata['total_records']:,} records ({metadata['total_size_mb']:.2f} MB)")
    
    return metadata


# ============================================================
# DELETE ARCHIVED DATA FROM MONGODB
# ============================================================
def cleanup_mongodb(collection_name, timestamp_column):
    """
    Delete archived data from MongoDB to free space
    
    Args:
        collection_name: MongoDB collection
        timestamp_column: Timestamp column for filtering
    """
    print(f"\n🗑️  Cleaning up {collection_name} in MongoDB...")
    
    from pymongo import MongoClient
    
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()
    collection = db[collection_name]
    
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ARCHIVE_OLDER_THAN_MINUTES)
    
    result = collection.delete_many({timestamp_column: {"$lt": cutoff}})
    
    print(f"   ✅ Deleted {result.deleted_count:,} old records from MongoDB")
    
    client.close()


# ============================================================
# MAIN ARCHIVAL PROCESS
# ============================================================
def main():
    print("=" * 70)
    print("📦 PHASE 2: MONGODB TO HDFS ARCHIVAL")
    print("=" * 70)
    
    # Initialize Spark
    spark = (
        SparkSession.builder
        .appName("supply-chain-archival")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.mongodb.read.connection.uri", MONGO_URI)
        .config("spark.mongodb.write.connection.uri", MONGO_URI)
        .getOrCreate()
    )
    
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"\n📅 Archive Policy: Data older than {ARCHIVE_OLDER_THAN_MINUTES} minutes")
    print(f"📂 HDFS Destination: {HDFS_BASE_PATH}")
    
    # Collections to archive (with their timestamp columns)
    collections_to_archive = [
        ("orders_fact", "order_ts"),
        ("shipments_fact", "shipment_ts"),
        ("inventory_fact", "inventory_ts")
    ]
    
    archive_stats_list = []
    
    # Archive each collection
    for collection_name, timestamp_column in collections_to_archive:
        try:
            stats = archive_collection(spark, collection_name, timestamp_column)
            if stats:
                archive_stats_list.append(stats)
        except Exception as e:
            print(f"   ❌ Error archiving {collection_name}: {e}")
            continue
    
    # If nothing was archived, exit
    if not archive_stats_list:
        print("\n✅ No data to archive at this time")
        spark.stop()
        return
    
    # Write metadata
    metadata = write_metadata(spark, archive_stats_list)
    
    # Cleanup MongoDB (delete archived data)
    print("\n🧹 Cleaning up archived data from MongoDB...")
    for collection_name, timestamp_column in collections_to_archive:
        if any(s["collection"] == collection_name for s in archive_stats_list):
            try:
                cleanup_mongodb(collection_name, timestamp_column)
            except Exception as e:
                print(f"   ⚠️  Warning: Could not clean up {collection_name}: {e}")
    
    print("\n" + "=" * 70)
    print("✅ ARCHIVAL COMPLETE")
    print("=" * 70)
    print(f"Archive ID: {metadata['archive_id']}")
    print(f"Records Archived: {metadata['total_records']:,}")
    print(f"Space Saved: ~{metadata['total_size_mb']:.2f} MB")
    print("=" * 70)
    
    spark.stop()


if __name__ == "__main__":
    main()


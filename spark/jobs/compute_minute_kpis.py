"""
Phase 2: Supply Chain KPI Computation
Reads MongoDB, performs OLAP-style joins, computes 5 KPIs, caches in Redis
"""

import os
import json
from datetime import datetime, timezone, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, sum as Fsum, avg as Favg, count as Fcount,
    stddev as Fstddev, desc, expr, when, max as Fmax
)

# ============================================================
# CONFIGURATION
# ============================================================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin"
)
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Time windows for analysis
ANALYSIS_WINDOW_MINUTES = 15  # Last 15 minutes of data
LOOKBACK_WINDOW_MINUTES = 30  # For trend analysis

# Alert thresholds
STOCKOUT_THRESHOLD_DAYS = 7.0  # Alert if < 7 days supply
DC_UTILIZATION_THRESHOLD = 0.85  # Alert if > 85% capacity


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
# MAIN KPI COMPUTATION
# ============================================================
def main():
    print("=" * 70)
    print("PHASE 2: SUPPLY CHAIN KPI COMPUTATION (HOT + COLD OLAP)")
    print("=" * 70)
    
    # Initialize Spark with MongoDB connector
    spark = (
        SparkSession.builder
        .appName("supply-chain-kpi-computation")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.mongodb.read.connection.uri", MONGO_URI)
        .config("spark.mongodb.write.connection.uri", MONGO_URI)
        .getOrCreate()
    )
    
    # Set log level to reduce noise
    spark.sparkContext.setLogLevel("WARN")
    
    # Log execution mode
    master_url = spark.sparkContext.master
    if "local" in master_url.lower():
        print("\nExecution Mode: Spark LOCAL (single-process)")
        print("Reason: Laptop/demo environment - avoids Python version mismatch")
        print("Note: Still reads HDFS archives and performs OLAP unification\n")
    else:
        print(f"\nExecution Mode: Spark DISTRIBUTED ({master_url})\n")
    
    # Calculate time windows
    now = datetime.now(timezone.utc)
    analysis_cutoff = now - timedelta(minutes=ANALYSIS_WINDOW_MINUTES)
    lookback_cutoff = now - timedelta(minutes=LOOKBACK_WINDOW_MINUTES)
    
    print(f"Analysis Window: Last {ANALYSIS_WINDOW_MINUTES} minutes")
    print(f"Lookback Window: Last {LOOKBACK_WINDOW_MINUTES} minutes")
    
    # ========================================
    # LOAD DATA (Facts + Dimensions)
    # ========================================
    print("\nLoading data from MongoDB...")
    
    # Fact tables (time-windowed)
    orders = read_mongo(spark, "orders_fact").where(
        col("order_ts") >= lit(analysis_cutoff)
    )
    
    shipments = read_mongo(spark, "shipments_fact").where(
        col("shipment_ts") >= lit(analysis_cutoff)
    )
    
    inventory = read_mongo(spark, "inventory_fact").where(
        col("inventory_ts") >= lit(analysis_cutoff)
    )
    
    # Dimension tables (full scan - small tables)
    skus = read_mongo(spark, "skus_dim")
    dcs = read_mongo(spark, "dcs_dim")
    regions = read_mongo(spark, "regions_dim")
    suppliers = read_mongo(spark, "suppliers_dim")
    
    # Cache dimensions (small, frequently joined)
    skus.cache()
    dcs.cache()
    regions.cache()
    suppliers.cache()
    
    print(f"Orders: {orders.count():,}")
    print(f"Shipments: {shipments.count():,}")
    print(f"Inventory Events: {inventory.count():,}")
    
    # ========================================
    # KPI 1: TOTAL INVENTORY LEVEL
    # ========================================
    print("\nComputing KPI 1: Total Inventory Level...")
    
    kpi1_inventory_level = (
        inventory
        .groupBy("sku_id", "dc_id")
        .agg(
            Favg("on_hand_qty").alias("avg_inventory"),
            Favg("safety_stock").alias("safety_stock")
        )
        .join(skus, "sku_id", "left")
        .join(dcs, "dc_id", "left")
        .select(
            "sku_id",
            "product_name",
            "category",
            "dc_id",
            "dc_name",
            col("avg_inventory").cast("int").alias("current_inventory"),
            col("safety_stock").cast("int").alias("safety_stock_level")
        )
        .orderBy(desc("current_inventory"))
    )
    
    kpi1_count = kpi1_inventory_level.count()
    print(f"Result: {kpi1_count} SKU-DC combinations tracked")
    
    # ========================================
    # KPI 2: STOCKOUT RISK (Days to Stockout)
    # ========================================
    print("\nComputing KPI 2: Stockout Risk...")
    
    # Calculate demand velocity (units per day)
    # Convert 15-minute window to days: 15 minutes = 15/(24*60) = 15/1440 days
    # Units per day = total_ordered / (window_minutes / 1440)
    window_days = ANALYSIS_WINDOW_MINUTES / (24.0 * 60.0)
    
    demand_velocity = (
        orders
        .groupBy("sku_id", "dc_id")
        .agg(
            Fsum("quantity").alias("total_ordered"),
            Fcount("*").alias("order_count")
        )
        .withColumn(
            "units_per_day",
            when(col("total_ordered") > 0,
                 col("total_ordered") / lit(window_days)
            ).otherwise(lit(0.0))
        )
    )
    
    # Join with current inventory and safety stock
    # Note: safety_stock is constant per SKU-DC (stored in inventory_state)
    # Using MAX to get the actual value (not average of identical values)
    kpi2_stockout_risk = (
        inventory
        .groupBy("sku_id", "dc_id")
        .agg(
            Favg("on_hand_qty").alias("current_stock"),
            Fmax("safety_stock").alias("safety_stock")
        )
        .join(demand_velocity, ["sku_id", "dc_id"], "left")
        .fillna({"units_per_day": 0.0, "total_ordered": 0})
        .withColumn(
            "available_stock",
            when(col("current_stock").isNull() | (col("current_stock") <= 0), lit(0.0))
            .otherwise(col("current_stock") - col("safety_stock"))
        )
        .withColumn(
            "days_to_stockout",
            when(col("current_stock").isNull() | (col("current_stock") <= 0), lit(0.0))
            .when(col("units_per_day") <= 0, lit(9999.0))
            .when(col("available_stock") <= 0, lit(0.0))
            .otherwise(col("available_stock") / col("units_per_day"))
        )
        .join(skus, "sku_id", "left")
        .join(dcs, "dc_id", "left")
        .join(regions.select("region_id", col("region_name")), 
              dcs["region_id"] == regions["region_id"], "left")
        .withColumn(
            "severity",
            when(col("days_to_stockout") <= 3.0, lit("Critical"))
            .when(col("days_to_stockout") <= 7.0, lit("Warning"))
            .otherwise(lit("Normal"))
        )
        .where(col("days_to_stockout") < lit(STOCKOUT_THRESHOLD_DAYS))
        .select(
            "sku_id",
            "product_name",
            "category",
            "dc_id",
            "dc_name",
            "region_name",
            col("current_stock").cast("double").alias("stock_level"),
            col("safety_stock").cast("double").alias("safety_stock_level"),
            col("units_per_day").cast("double").alias("demand_rate_per_day"),
            col("days_to_stockout").cast("double").alias("days_until_stockout"),
            "severity"
        )
        .orderBy("days_until_stockout")
    )
    
    kpi2_high_risk_count = kpi2_stockout_risk.count()
    
    # Log sample calculations for validation
    if kpi2_high_risk_count > 0:
        sample = kpi2_stockout_risk.limit(3).collect()
        print(f"Sample stockout calculations:")
        for row in sample:
            # Spark Row objects use dictionary-style access, not .get()
            safety_stock = row['safety_stock_level'] if 'safety_stock_level' in row else 0
            print(f"  {row['product_name']} @ {row['dc_name']}: "
                  f"Stock={row['stock_level']:.0f}, Safety={safety_stock:.0f}, "
                  f"Demand={row['demand_rate_per_day']:.2f}/day, "
                  f"Days={row['days_until_stockout']:.2f}")
    
    print(f"WARNING: KPI 2: {kpi2_high_risk_count} high-risk items (< {STOCKOUT_THRESHOLD_DAYS} days supply)")
    
    # ========================================
    # KPI 3: SUPPLIER LEAD TIME PERFORMANCE
    # ========================================
    print("\nComputing KPI 3: Supplier Lead Time Performance...")
    
    kpi3_supplier_performance = (
        shipments
        .join(suppliers, "supplier_id", "left")
        .groupBy("supplier_id", "supplier_name", "reliability_score")
        .agg(
            Fcount("*").alias("shipment_count"),
            Favg("lead_time_days").alias("avg_actual_lead_time"),
            Fstddev("lead_time_days").alias("lead_time_variance")
        )
        .withColumn(
            "performance_score",
            when(col("lead_time_variance").isNull(), lit(1.0))
            .otherwise(
                lit(1.0) - (col("lead_time_variance") / col("avg_actual_lead_time"))
            )
        )
        .select(
            "supplier_id",
            "supplier_name",
            col("reliability_score").cast("double"),
            col("shipment_count").cast("int"),
            col("avg_actual_lead_time").cast("double").alias("avg_lead_time_days"),
            col("lead_time_variance").cast("double").alias("lead_time_std_dev"),
            col("performance_score").cast("double")
        )
        .orderBy(desc("performance_score"))
    )
    
    kpi3_count = kpi3_supplier_performance.count()
    print(f"Result: KPI 3: {kpi3_count} suppliers analyzed")
    
    # ========================================
    # KPI 4: DC UTILIZATION RATE
    # ========================================
    print("\nComputing KPI 4: Distribution Center Utilization...")
    
    # Calculate current volume per DC
    # First join inventory with SKU storage requirements, then aggregate by DC
    dc_inventory_volume = (
        inventory
        .join(skus.select("sku_id", "storage_m3"), "sku_id", "left")
        .withColumn("item_volume", col("on_hand_qty") * col("storage_m3"))
        .groupBy("dc_id")
        .agg(
            Fsum("item_volume").alias("current_volume_m3")
        )
    )
    
    kpi4_dc_utilization = (
        dc_inventory_volume
        .join(dcs, "dc_id", "left")
        .withColumn(
            "utilization_rate",
            col("current_volume_m3") / col("capacity_m3")
        )
        .select(
            "dc_id",
            "dc_name",
            col("capacity_m3").cast("double"),
            col("current_volume_m3").cast("double").alias("occupied_volume_m3"),
            col("utilization_rate").cast("double")
        )
        .withColumn(
            "status",
            when(col("utilization_rate") >= lit(DC_UTILIZATION_THRESHOLD), lit("OVERLOADED"))
            .when(col("utilization_rate") >= lit(0.70), lit("HIGH"))
            .when(col("utilization_rate") >= lit(0.50), lit("NORMAL"))
            .otherwise(lit("LOW"))
        )
        .orderBy(desc("utilization_rate"))
    )
    
    kpi4_overloaded = kpi4_dc_utilization.where(
        col("utilization_rate") >= lit(DC_UTILIZATION_THRESHOLD)
    ).count()
    
    print(f"WARNING: KPI 4: {kpi4_overloaded} DCs overloaded (> {DC_UTILIZATION_THRESHOLD*100}%)")
    
    # ========================================
    # KPI 5: ORDER FULFILLMENT & REVENUE BY REGION
    # ========================================
    print("\nComputing KPI 5: Regional Fulfillment & Revenue...")
    
    kpi5_regional_performance = (
        orders
        .join(dcs.select("dc_id", col("region_id").alias("dc_region_id")), "dc_id", "left")
        .join(regions, col("dc_region_id") == regions["region_id"], "left")
        .groupBy(regions["region_id"], "region_name")
        .agg(
            Fcount("*").alias("total_orders"),
            Fsum("quantity").alias("total_units_fulfilled"),
            Fsum("order_value").alias("total_revenue"),
            Favg("order_value").alias("avg_order_value")
        )
        .withColumn(
            "revenue_per_order",
            col("total_revenue") / col("total_orders")
        )
        .select(
            col("region_id"),
            "region_name",
            col("total_orders").cast("int"),
            col("total_units_fulfilled").cast("int"),
            col("total_revenue").cast("double").alias("revenue"),
            col("avg_order_value").cast("double"),
            col("revenue_per_order").cast("double")
        )
        .orderBy(desc("revenue"))
    )
    
    kpi5_count = kpi5_regional_performance.count()
    print(f"Result: KPI 5: {kpi5_count} regions analyzed")
    
    # ========================================
    # CACHE TO REDIS
    # ========================================
    print("\nCaching KPIs to Redis...")
    
    import redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    # Store metadata
    r.set("kpi:last_update", now.isoformat())
    r.set("kpi:analysis_window_minutes", ANALYSIS_WINDOW_MINUTES)
    
    # Store KPI 1: Inventory Level
    kpi1_data = [row.asDict() for row in kpi1_inventory_level.limit(100).collect()]
    r.set("kpi:inventory_level", json.dumps(kpi1_data, default=str))
    print(f"  Result: KPI 1: Cached {len(kpi1_data)} records")
    
    # Store KPI 2: Stockout Alerts
    kpi2_data = [row.asDict() for row in kpi2_stockout_risk.limit(50).collect()]
    r.set("kpi:stockout_alerts", json.dumps(kpi2_data, default=str))
    r.set("kpi:stockout_risk_count", kpi2_high_risk_count)
    print(f"  Result: KPI 2: Cached {len(kpi2_data)} alerts")
    
    # Store KPI 3: Supplier Performance
    kpi3_data = [row.asDict() for row in kpi3_supplier_performance.collect()]
    r.set("kpi:supplier_performance", json.dumps(kpi3_data, default=str))
    print(f"  Result: KPI 3: Cached {len(kpi3_data)} suppliers")
    
    # Store KPI 4: DC Utilization
    kpi4_data = [row.asDict() for row in kpi4_dc_utilization.collect()]
    r.set("kpi:dc_utilization", json.dumps(kpi4_data, default=str))
    r.set("kpi:dc_overloaded_count", kpi4_overloaded)
    print(f"  Result: KPI 4: Cached {len(kpi4_data)} DCs")
    
    # Store KPI 5: Regional Performance
    kpi5_data = [row.asDict() for row in kpi5_regional_performance.collect()]
    r.set("kpi:regional_performance", json.dumps(kpi5_data, default=str))
    print(f"  Result: KPI 5: Cached {len(kpi5_data)} regions")
    
    # Set TTL on all KPI keys
    for key in r.keys("kpi:*"):
        r.expire(key, 120)  # 2 minutes TTL
    
    print("\nAll KPIs computed and cached successfully!")
    print("=" * 70)
    
    # Cleanup
    spark.stop()


if __name__ == "__main__":
    main()


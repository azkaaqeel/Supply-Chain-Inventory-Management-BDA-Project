"""
Supply Chain Real-Time Data Generator - REALISM ENHANCED
Continuously generates statistically realistic streaming data with:
- Inventory balance equation: Inventory(t+1) = Inventory(t) - Fulfilled + Received
- Reorder-driven replenishment (not random)
- Fulfillment constrained by availability
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient, ASCENDING, UpdateOne
from pymongo.errors import ConnectionFailure

from config import (
    REGIONS, DISTRIBUTION_CENTERS, SKUS, SUPPLIERS,
    PRIORITY_LEVELS, PRIORITY_WEIGHTS
)
from models import StatisticalModels


# ============================================================
# CONFIGURATION
# ============================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://admin:admin123@mongo:27017/supply_chain?authSource=admin")
EVENTS_PER_MINUTE = int(os.environ.get("EVENTS_PER_MINUTE", "1500"))
GENERATION_INTERVAL_SECONDS = int(os.environ.get("GENERATION_INTERVAL_SECONDS", "60"))

# Realism parameters
REPLENISHMENT_LIMIT_PER_ITER = int(os.environ.get("REPLENISHMENT_LIMIT_PER_ITER", "100"))
REORDER_COVERAGE_DAYS = int(os.environ.get("REORDER_COVERAGE_DAYS", "21"))
SHIPMENT_RECEIVE_BATCH_SIZE = int(os.environ.get("SHIPMENT_RECEIVE_BATCH_SIZE", "1000"))

# DEMO MODE - Makes system demo-ready within 5-10 minutes
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() == "true"
DEMO_STOCK_MULTIPLIER = float(os.environ.get("DEMO_STOCK_MULTIPLIER", "2.0" if DEMO_MODE else "1.0"))
DEMO_LEAD_TIME_HOURS = float(os.environ.get("DEMO_LEAD_TIME_HOURS", "0.05" if DEMO_MODE else "24.0"))  # 3 minutes in demo mode

# Initialize statistical models
models = StatisticalModels(seed=42)


# ============================================================
# DATABASE CONNECTION
# ============================================================
def connect_mongo(max_retries=10, retry_delay=5):
    """Connect to MongoDB with retries"""
    for attempt in range(max_retries):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')  # Test connection
            print(f"✅ Connected to MongoDB: {MONGO_URI.split('@')[1]}")
            return client
        except ConnectionFailure as e:
            print(f"⚠️  MongoDB connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print("❌ Failed to connect to MongoDB after all retries")
                sys.exit(1)


# ============================================================
# SCHEMA INITIALIZATION
# ============================================================
def ensure_indexes(db):
    """Create indexes for efficient time-windowed queries"""
    print("📇 Creating indexes...")
    
    # Orders fact indexes
    db.orders_fact.create_index([("order_ts", ASCENDING)])
    db.orders_fact.create_index([("sku_id", ASCENDING), ("dc_id", ASCENDING), ("order_ts", ASCENDING)])
    
    # Shipments fact indexes (ENHANCED)
    db.shipments_fact.create_index([("shipment_ts", ASCENDING)])
    db.shipments_fact.create_index([("sku_id", ASCENDING), ("destination_dc_id", ASCENDING)])
    db.shipments_fact.create_index([("expected_arrival_ts", ASCENDING), ("actual_arrival_ts", ASCENDING)])
    
    # Inventory fact indexes
    db.inventory_fact.create_index([("inventory_ts", ASCENDING)])
    db.inventory_fact.create_index([("sku_id", ASCENDING), ("dc_id", ASCENDING), ("inventory_ts", ASCENDING)])
    
    # Inventory state index (unique)
    db.inventory_state.create_index([("sku_id", ASCENDING), ("dc_id", ASCENDING)], unique=True)
    
    print("✅ Indexes created")


def seed_dimensions(db):
    """Seed dimension tables (run once on startup if empty)"""
    print("🌱 Seeding dimension tables...")
    
    # Clear existing dimensions
    db.regions_dim.delete_many({})
    db.dcs_dim.delete_many({})
    db.skus_dim.delete_many({})
    db.suppliers_dim.delete_many({})
    
    # Insert dimensions
    db.regions_dim.insert_many(REGIONS)
    db.dcs_dim.insert_many(DISTRIBUTION_CENTERS)
    db.skus_dim.insert_many(SKUS)
    db.suppliers_dim.insert_many(SUPPLIERS)
    
    print(f"✅ Seeded {len(REGIONS)} regions, {len(DISTRIBUTION_CENTERS)} DCs, "
          f"{len(SKUS)} SKUs, {len(SUPPLIERS)} suppliers")


def initialize_inventory_state(db):
    """Initialize inventory state collection with Imtiaz-specific stock levels"""
    print("📦 Initializing inventory state...")
    
    if db.inventory_state.count_documents({}) > 0:
        print("ℹ️  Inventory state already exists, skipping initialization")
        return
    
    inventory_docs = []
    total_initial_stock = 0
    
    for sku in SKUS:
        for dc in DISTRIBUTION_CENTERS:
            # Use SKU-specific stock coverage days (realistic for each product type)
            stock_coverage_days = sku.get("stock_coverage_days", 30)
            daily_demand = sku["demand_base_lambda"]
            
            # Calculate base stock: demand × coverage × multiplier
            base_stock = int(daily_demand * stock_coverage_days * DEMO_STOCK_MULTIPLIER)
            base_stock = max(base_stock, 100)  # Minimum 100 units
            
            # Calculate safety stock (7 days for all)
            safety_stock = int(daily_demand * 7)
            
            # Calculate reorder point (lead time + safety stock)
            lead_time_days = sku["lead_time_days"]
            reorder_point = int((daily_demand * lead_time_days) + safety_stock)
            
            inventory_docs.append({
                "sku_id": sku["sku_id"],
                "dc_id": dc["dc_id"],
                "on_hand_qty": base_stock,
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "base_stock": base_stock,
                "stock_coverage_days": stock_coverage_days,
                "last_updated": models.now_utc()
            })
            
            total_initial_stock += base_stock
    
    db.inventory_state.insert_many(inventory_docs)
    
    print(f"✅ Initialized inventory for {len(inventory_docs)} SKU-DC combinations")
    print(f"📊 Total initial stock: {total_initial_stock:,} units")


# ============================================================
# NEW: SHIPMENT RECEIVING (CRITICAL FIX)
# ============================================================
def receive_arrived_shipments(db, now_ts):
    """
    CRITICAL: Receive shipments that have arrived and increment inventory
    Returns: (shipments_received_count, units_received)
    """
    # Find shipments that should have arrived by now but haven't been received
    arrived_shipments = list(db.shipments_fact.find({
        "expected_arrival_ts": {"$lte": now_ts},
        "actual_arrival_ts": None
    }).limit(SHIPMENT_RECEIVE_BATCH_SIZE))
    
    if not arrived_shipments:
        return 0, 0
    
    # Prepare bulk operations
    shipment_updates = []
    inventory_updates = {}  # {(sku_id, dc_id): qty_to_add}
    
    total_units = 0
    
    for shipment in arrived_shipments:
        # Mark shipment as received
        shipment_updates.append(
            UpdateOne(
                {"_id": shipment["_id"]},
                {"$set": {"actual_arrival_ts": now_ts}}
            )
        )
        
        # Accumulate inventory increments
        key = (shipment["sku_id"], shipment["destination_dc_id"])
        inventory_updates[key] = inventory_updates.get(key, 0) + shipment["quantity"]
        total_units += shipment["quantity"]
    
    # Execute shipment updates
    if shipment_updates:
        db.shipments_fact.bulk_write(shipment_updates, ordered=False)
    
    # Execute inventory increments
    inv_bulk_ops = []
    for (sku_id, dc_id), qty in inventory_updates.items():
        inv_bulk_ops.append(
            UpdateOne(
                {"sku_id": sku_id, "dc_id": dc_id},
                {
                    "$inc": {"on_hand_qty": qty},
                    "$set": {"last_updated": now_ts}
                }
            )
        )
    
    if inv_bulk_ops:
        db.inventory_state.bulk_write(inv_bulk_ops, ordered=False)
    
    return len(arrived_shipments), total_units


# ============================================================
# NEW: REORDER-DRIVEN REPLENISHMENT (REPLACES RANDOM)
# ============================================================
def create_replenishment_shipments(db, now_ts, max_shipments):
    """
    CRITICAL: Create shipments based on reorder policy (not random)
    Triggers when on_hand_qty <= reorder_point
    Returns: shipments_created_count
    """
    # Find SKU-DC combinations that need replenishment
    low_stock_items = list(db.inventory_state.find({
        "$expr": {"$lte": ["$on_hand_qty", "$reorder_point"]}
    }).limit(max_shipments))
    
    if not low_stock_items:
        return 0
    
    # Build SKU lookup for demand info
    sku_map = {sku["sku_id"]: sku for sku in SKUS}
    
    # Calculate supplier weights (bias toward higher reliability)
    supplier_weights = [s["reliability_score"] ** 2 for s in SUPPLIERS]
    
    shipment_docs = []
    
    for inv_item in low_stock_items:
        sku_id = inv_item["sku_id"]
        dc_id = inv_item["dc_id"]
        
        # Get SKU info
        sku = sku_map.get(sku_id)
        if not sku:
            continue
        
        # Choose supplier (weighted by reliability)
        supplier = models.rng.choice(SUPPLIERS, p=[w/sum(supplier_weights) for w in supplier_weights])
        
        # Calculate reorder quantity (cover REORDER_COVERAGE_DAYS of demand)
        daily_demand = sku["demand_base_lambda"]
        reorder_qty = max(int(daily_demand * REORDER_COVERAGE_DAYS * models.rng.uniform(0.8, 1.2)), 50)
        
        # Calculate lead time (with demo mode adjustment)
        lead_time_days = models.generate_lead_time(
            avg_days=supplier["avg_lead_time_days"],
            stddev_days=supplier["lead_time_stddev_days"]
        )
        
        # In demo mode, use hours instead of days for quick arrival
        if DEMO_MODE:
            lead_time_hours = max(DEMO_LEAD_TIME_HOURS, 0.01)  # Minimum 36 seconds
            expected_arrival = now_ts + timedelta(hours=lead_time_hours * lead_time_days)
        else:
            expected_arrival = now_ts + timedelta(days=lead_time_days)
        
        shipment_docs.append({
            "shipment_id": str(uuid.uuid4()),
            "sku_id": sku_id,
            "supplier_id": supplier["supplier_id"],
            "destination_dc_id": dc_id,
            "quantity": reorder_qty,
            "expected_arrival_ts": expected_arrival,
            "actual_arrival_ts": None,
            "lead_time_days": lead_time_days,
            "shipment_ts": now_ts,
            "shipment_type": "replenishment"  # Tag for tracking
        })
    
    if shipment_docs:
        db.shipments_fact.insert_many(shipment_docs, ordered=False)
    
    return len(shipment_docs)


# ============================================================
# ENHANCED: FULFILLMENT-AWARE ORDER GENERATION
# ============================================================
def generate_orders(db, timestamp, inventory_map):
    """
    Generate outbound customer orders with fulfillment awareness
    Respects available inventory and tracks lost sales
    
    Args:
        db: MongoDB database
        timestamp: Current timestamp
        inventory_map: In-memory dict {(sku_id, dc_id): available_qty}
    
    Returns: (orders_created, total_requested, total_fulfilled, total_lost_sales)
    """
    order_docs = []
    inventory_updates = []  # Track updates to write back
    
    # Create region lookup
    region_map = {r["region_id"]: r for r in REGIONS}
    dc_region_map = {dc["dc_id"]: dc["region_id"] for dc in DISTRIBUTION_CENTERS}
    
    # Distribute EVENTS_PER_MINUTE across SKUs proportionally
    total_lambda = sum(sku["demand_base_lambda"] for sku in SKUS)
    
    total_requested = 0
    total_fulfilled = 0
    total_lost_sales = 0
    
    for sku in SKUS:
        # Proportional share of events
        sku_share = sku["demand_base_lambda"] / total_lambda
        sku_events_budget = int(EVENTS_PER_MINUTE * sku_share * 0.6)  # 60% of events are orders
        
        for dc in DISTRIBUTION_CENTERS:
            region = region_map[dc_region_map[dc["dc_id"]]]
            
            # Generate order count using Poisson
            order_count = models.generate_order_count(
                base_lambda=sku_events_budget / len(DISTRIBUTION_CENTERS),
                region_factor=region["demand_factor"],
                demand_volatility=region["demand_volatility"]
            )
            
            # Generate individual orders
            for _ in range(order_count):
                requested_qty = models.generate_order_quantity(mean_qty=5)
                
                # Check availability
                key = (sku["sku_id"], dc["dc_id"])
                available_qty = inventory_map.get(key, 0)
                
                fulfilled_qty = min(requested_qty, available_qty)
                lost_sales_qty = requested_qty - fulfilled_qty
                
                # Update in-memory inventory
                inventory_map[key] = available_qty - fulfilled_qty
                
                # Calculate order value (based on fulfilled qty)
                order_value = models.generate_order_value(sku["unit_cost"], fulfilled_qty)
                lost_revenue = sku["unit_cost"] * lost_sales_qty * models.rng.uniform(0.9, 1.1)
                
                priority = models.generate_priority_with_value_correlation(order_value)
                
                order_docs.append({
                    "order_id": str(uuid.uuid4()),
                    "sku_id": sku["sku_id"],
                    "dc_id": dc["dc_id"],
                    "region_id": region["region_id"],
                    "requested_qty": requested_qty,
                    "fulfilled_qty": fulfilled_qty,
                    "lost_sales_qty": lost_sales_qty,
                    "quantity": fulfilled_qty,  # Keep for backward compatibility
                    "lost_sale_flag": lost_sales_qty > 0,
                    "order_value": order_value,
                    "lost_revenue": lost_revenue,
                    "priority_level": priority,
                    "order_ts": timestamp
                })
                
                total_requested += requested_qty
                total_fulfilled += fulfilled_qty
                total_lost_sales += lost_sales_qty
    
    # Insert orders
    if order_docs:
        db.orders_fact.insert_many(order_docs, ordered=False)
    
    # Write back inventory updates
    if inventory_map:
        inv_bulk_ops = []
        for (sku_id, dc_id), new_qty in inventory_map.items():
            inv_bulk_ops.append(
                UpdateOne(
                    {"sku_id": sku_id, "dc_id": dc_id},
                    {
                        "$set": {
                            "on_hand_qty": max(0, new_qty),
                            "last_updated": timestamp
                        }
                    }
                )
            )
        
        if inv_bulk_ops:
            db.inventory_state.bulk_write(inv_bulk_ops, ordered=False)
    
    return len(order_docs), total_requested, total_fulfilled, total_lost_sales


# ============================================================
# SIMPLIFIED: INVENTORY SNAPSHOT (FROM STATE, NOT QUERIES)
# ============================================================
def write_inventory_snapshots(db, timestamp):
    """
    Write inventory snapshots from current inventory_state
    NO expensive order queries - just snapshot the state
    """
    inventory_event_docs = []
    
    # Get current inventory state
    inventory_states = list(db.inventory_state.find({}))
    
    for inv_state in inventory_states:
        inventory_event_docs.append({
            "inventory_event_id": str(uuid.uuid4()),
            "sku_id": inv_state["sku_id"],
            "dc_id": inv_state["dc_id"],
            "on_hand_qty": inv_state["on_hand_qty"],
            "safety_stock": inv_state["safety_stock"],
            "reorder_point": inv_state["reorder_point"],
            "inventory_ts": timestamp
        })
    
    if inventory_event_docs:
        db.inventory_fact.insert_many(inventory_event_docs, ordered=False)
    
    return len(inventory_event_docs)


# ============================================================
# MAIN GENERATION LOOP (REORDERED PIPELINE)
# ============================================================
def main():
    print("=" * 70)
    print("🚀 IMTIAZ SUPER MARKET - Supply Chain Data Generator")
    print("   Real-Time FMCG & Grocery Supply Chain Simulation")
    print("=" * 70)
    
    # Connect to MongoDB
    client = connect_mongo()
    db = client.get_default_database()
    
    # Initialize schema
    ensure_indexes(db)
    
    # Seed dimensions if empty
    if db.regions_dim.count_documents({}) == 0:
        seed_dimensions(db)
    
    # Initialize inventory state if empty
    initialize_inventory_state(db)
    
    print("\n" + "=" * 70)
    print(f"📊 Generation Parameters:")
    print(f"   - Business: Imtiaz Super Market (Pakistan)")
    print(f"   - Events per minute: {EVENTS_PER_MINUTE}")
    print(f"   - Generation interval: {GENERATION_INTERVAL_SECONDS}s")
    print(f"   - DEMO MODE: {'🎬 ENABLED (fast replenishment)' if DEMO_MODE else '🏢 DISABLED (realistic)'}")
    print(f"   - Stock multiplier: {DEMO_STOCK_MULTIPLIER}x")
    print(f"   - Lead time: {DEMO_LEAD_TIME_HOURS}h per day" + (" (3-15 min arrivals)" if DEMO_MODE else ""))
    print(f"   - Reorder coverage: {REORDER_COVERAGE_DAYS} days")
    print(f"   - Replenishment limit: {REPLENISHMENT_LIMIT_PER_ITER} per iteration")
    print(f"   - SKUs: {len(SKUS)} (FMCG & Grocery)")
    print(f"   - Distribution Centers: {len(DISTRIBUTION_CENTERS)} (Pakistan cities)")
    print(f"   - Suppliers: {len(SUPPLIERS)} (Local & Import)")
    print("=" * 70 + "\n")
    
    if DEMO_MODE:
        print("🎬 DEMO MODE: Shipments arrive within 3-15 minutes for quick demonstration")
        print("   (In production, use DEMO_MODE=false for realistic lead times)\n")
    
    print("🔄 Starting continuous data generation...\n")
    
    iteration = 0
    
    while True:
        iteration += 1
        start_time = time.time()
        timestamp = models.now_utc()
        
        try:
            # ========================================
            # CORRECT PIPELINE ORDER:
            # 1. Receive arrived shipments (replenish)
            # 2. Load inventory into memory
            # 3. Generate orders (consume)
            # 4. Create replenishment shipments
            # 5. Write inventory snapshots
            # ========================================
            
            # Step 1: Receive arrived shipments
            shipments_received, units_received = receive_arrived_shipments(db, timestamp)
            
            # Step 2: Load current inventory state into memory
            inventory_states = list(db.inventory_state.find({}))
            inventory_map = {
                (inv["sku_id"], inv["dc_id"]): inv["on_hand_qty"]
                for inv in inventory_states
            }
            
            # Step 3: Generate orders (fulfillment-aware, updates inventory_map)
            orders_count, total_requested, total_fulfilled, total_lost_sales = \
                generate_orders(db, timestamp, inventory_map)
            
            # Step 4: Create replenishment shipments (based on updated inventory)
            replenishments_created = create_replenishment_shipments(
                db, timestamp, REPLENISHMENT_LIMIT_PER_ITER
            )
            
            # Step 5: Write inventory snapshots
            inventory_count = write_inventory_snapshots(db, timestamp)
            
            # Calculate total inventory across all SKU-DC
            total_inventory = sum(inventory_map.values())
            
            # Get database size
            stats = db.command("dbStats")
            db_size_mb = stats["dataSize"] / (1024 * 1024)
            
            # Enhanced logging
            elapsed = time.time() - start_time
            print(f"[{timestamp.strftime('%H:%M:%S')}] Iter {iteration:04d} | "
                  f"Orders: {orders_count:4d} (Req: {total_requested:5d}, Ful: {total_fulfilled:5d}, Lost: {total_lost_sales:4d}) | "
                  f"Shipments: Recv {shipments_received:3d} (+{units_received:5d} u), Create {replenishments_created:3d} | "
                  f"Inventory: {inventory_count:3d} snap, {total_inventory:7,d} total | "
                  f"DB: {db_size_mb:.1f} MB | {elapsed:.2f}s")
            
            # Sleep until next interval
            sleep_time = max(0, GENERATION_INTERVAL_SECONDS - elapsed)
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error in iteration {iteration}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)  # Brief pause before retry
    
    print("\n✅ Generator shutdown complete")
    client.close()


if __name__ == "__main__":
    main()

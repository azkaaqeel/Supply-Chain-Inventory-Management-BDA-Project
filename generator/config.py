"""
Supply Chain Domain Configuration - IMTIAZ SUPER MARKET (Pakistan)
Defines: SKUs, Distribution Centers, Suppliers, Regions
Business Context: Grocery & FMCG supply chain across major Pakistani cities
"""

# ============================================================
# REGIONS (Pakistan Geography)
# ============================================================
REGIONS = [
    {
        "region_id": "PK-SINDH",
        "region_name": "Sindh Province",
        "demand_factor": 2.0,  # Karachi - highest demand
        "demand_volatility": 0.35  # High variance (megacity dynamics)
    },
    {
        "region_id": "PK-PUNJAB-NORTH",
        "region_name": "Punjab North",
        "demand_factor": 1.6,  # Lahore, Faisalabad
        "demand_volatility": 0.28
    },
    {
        "region_id": "PK-PUNJAB-SOUTH",
        "region_name": "Punjab South",
        "demand_factor": 1.2,  # Multan region
        "demand_volatility": 0.25
    },
    {
        "region_id": "PK-CAPITAL",
        "region_name": "Capital Region",
        "demand_factor": 1.4,  # Islamabad/Rawalpindi
        "demand_volatility": 0.22  # More stable (government sector)
    },
]

# ============================================================
# DISTRIBUTION CENTERS (Imtiaz Warehouses)
# ============================================================
DISTRIBUTION_CENTERS = [
    {
        "dc_id": "DC-KHI",
        "dc_name": "Karachi Central Warehouse",
        "region_id": "PK-SINDH",
        "capacity_m3": 75000,  # Largest - serves megacity
        "throughput_per_day": 25000,  # Units per day
        "operating_cost_per_day": 12000
    },
    {
        "dc_id": "DC-LHE",
        "dc_name": "Lahore Distribution Hub",
        "region_id": "PK-PUNJAB-NORTH",
        "capacity_m3": 60000,
        "throughput_per_day": 20000,
        "operating_cost_per_day": 10000
    },
    {
        "dc_id": "DC-ISB",
        "dc_name": "Islamabad Regional Center",
        "region_id": "PK-CAPITAL",
        "capacity_m3": 45000,
        "throughput_per_day": 15000,
        "operating_cost_per_day": 8500
    },
    {
        "dc_id": "DC-FSD",
        "dc_name": "Faisalabad Warehouse",
        "region_id": "PK-PUNJAB-NORTH",
        "capacity_m3": 40000,
        "throughput_per_day": 12000,
        "operating_cost_per_day": 7000
    },
    {
        "dc_id": "DC-MUL",
        "dc_name": "Multan Distribution Point",
        "region_id": "PK-PUNJAB-SOUTH",
        "capacity_m3": 35000,
        "throughput_per_day": 10000,
        "operating_cost_per_day": 6000
    },
]

# ============================================================
# SKUs / PRODUCTS (Imtiaz FMCG & Grocery)
# ============================================================
SKUS = [
    # STAPLES (High demand, long shelf life, large storage)
    {
        "sku_id": "SKU-STAPLE-001",
        "product_name": "Atta (Wheat Flour) - 10kg",
        "category": "Staples",
        "unit_cost": 850.00,  # PKR
        "storage_m3": 0.015,  # Bulky
        "demand_base_lambda": 80,  # Very high demand
        "lead_time_days": 3,  # Local mills - short lead time
        "stock_coverage_days": 45  # Keep 45 days stock (staple)
    },
    {
        "sku_id": "SKU-STAPLE-002",
        "product_name": "Basmati Rice - 5kg",
        "category": "Staples",
        "unit_cost": 950.00,
        "storage_m3": 0.010,
        "demand_base_lambda": 70,
        "lead_time_days": 4,
        "stock_coverage_days": 40
    },
    {
        "sku_id": "SKU-STAPLE-003",
        "product_name": "Cooking Oil - 5L",
        "category": "Staples",
        "unit_cost": 1450.00,
        "storage_m3": 0.008,
        "demand_base_lambda": 65,
        "lead_time_days": 5,  # Import/refining process
        "stock_coverage_days": 35
    },
    {
        "sku_id": "SKU-STAPLE-004",
        "product_name": "Sugar - 5kg",
        "category": "Staples",
        "unit_cost": 550.00,
        "storage_m3": 0.012,
        "demand_base_lambda": 60,
        "lead_time_days": 3,
        "stock_coverage_days": 40
    },
    
    # DAIRY (High turnover, short shelf life, cold chain)
    {
        "sku_id": "SKU-DAIRY-001",
        "product_name": "Fresh Milk - 1L",
        "category": "Dairy",
        "unit_cost": 220.00,
        "storage_m3": 0.002,  # Small footprint
        "demand_base_lambda": 120,  # Highest demand
        "lead_time_days": 1,  # Local dairies - daily delivery
        "stock_coverage_days": 3  # Perishable - keep minimal
    },
    {
        "sku_id": "SKU-DAIRY-002",
        "product_name": "Yogurt - 400g",
        "category": "Dairy",
        "unit_cost": 150.00,
        "storage_m3": 0.001,
        "demand_base_lambda": 90,
        "lead_time_days": 1,
        "stock_coverage_days": 4
    },
    
    # SNACKS & BEVERAGES (Medium demand, moderate shelf life)
    {
        "sku_id": "SKU-SNACK-001",
        "product_name": "Chips Family Pack",
        "category": "Snacks",
        "unit_cost": 180.00,
        "storage_m3": 0.004,
        "demand_base_lambda": 50,
        "lead_time_days": 3,  # Local FMCG suppliers
        "stock_coverage_days": 20
    },
    {
        "sku_id": "SKU-BEV-001",
        "product_name": "Soft Drink - 1.5L",
        "category": "Beverages",
        "unit_cost": 150.00,
        "storage_m3": 0.003,
        "demand_base_lambda": 75,
        "lead_time_days": 2,  # Local bottlers
        "stock_coverage_days": 15
    },
    
    # CLEANING (Lower demand, long shelf life)
    {
        "sku_id": "SKU-CLEAN-001",
        "product_name": "Detergent - 3kg",
        "category": "Cleaning",
        "unit_cost": 650.00,
        "storage_m3": 0.006,
        "demand_base_lambda": 35,
        "lead_time_days": 5,
        "stock_coverage_days": 30
    },
    {
        "sku_id": "SKU-CLEAN-002",
        "product_name": "Dishwashing Liquid - 1L",
        "category": "Cleaning",
        "unit_cost": 280.00,
        "storage_m3": 0.002,
        "demand_base_lambda": 40,
        "lead_time_days": 4,
        "stock_coverage_days": 25
    },
]

# ============================================================
# SUPPLIERS (Pakistan Local & Import)
# ============================================================
SUPPLIERS = [
    # LOCAL FMCG - Short lead time, high reliability
    {
        "supplier_id": "SUP-LOCAL-001",
        "supplier_name": "National Foods (Pvt) Ltd",
        "reliability_score": 0.96,  # Very reliable
        "avg_lead_time_days": 2,  # Local - fast
        "lead_time_stddev_days": 0.5,  # Low variance
        "supplier_type": "local_fmcg"
    },
    {
        "supplier_id": "SUP-LOCAL-002",
        "supplier_name": "Nestle Pakistan",
        "reliability_score": 0.94,
        "avg_lead_time_days": 2,
        "lead_time_stddev_days": 0.6,
        "supplier_type": "local_fmcg"
    },
    
    # REGIONAL SUPPLIERS - Medium lead time
    {
        "supplier_id": "SUP-REGIONAL-001",
        "supplier_name": "Punjab Oil Mills",
        "reliability_score": 0.88,
        "avg_lead_time_days": 4,
        "lead_time_stddev_days": 1.2,
        "supplier_type": "regional"
    },
    
    # IMPORT-BASED - Longer lead time, higher variance
    {
        "supplier_id": "SUP-IMPORT-001",
        "supplier_name": "Global Trading Corp",
        "reliability_score": 0.82,  # Less predictable
        "avg_lead_time_days": 7,  # Import delays
        "lead_time_stddev_days": 2.5,  # High variance
        "supplier_type": "import"
    },
]

# ============================================================
# PRIORITY LEVELS (Order priority based on customer type)
# ============================================================
PRIORITY_LEVELS = ["HIGH", "NORMAL", "LOW"]
PRIORITY_WEIGHTS = [0.12, 0.76, 0.12]  # 12% high (bulk orders), 76% normal, 12% low

# ============================================================
# BUSINESS RULES (Imtiaz-specific)
# ============================================================
BUSINESS_RULES = {
    "ramadan_demand_spike": 1.8,  # 80% increase during Ramadan
    "weekend_demand_spike": 1.3,  # 30% increase Fri-Sat
    "stockout_tolerance_days": 2,  # Alert if < 2 days supply
    "overstock_threshold": 90,  # Alert if > 90 days supply
    "dc_utilization_target": 0.75,  # Target 75% capacity
    "dc_utilization_critical": 0.90,  # Alert if > 90%
}

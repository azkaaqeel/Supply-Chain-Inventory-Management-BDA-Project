# Analytics Dashboard - KPI Documentation

## Dashboard Purpose

The Supply Chain Analytics Dashboard provides real-time visibility into inventory operations, supplier performance, and distribution center efficiency for retail supply chain management. The dashboard addresses critical business problems:

**Inventory Optimization**: Prevents stockouts and overstock situations by monitoring inventory levels and demand velocity across all SKU-DC combinations. Managers can identify items at risk of running out and prioritize replenishment orders.

**Operational Efficiency**: Tracks distribution center utilization to prevent capacity bottlenecks and optimize warehouse space allocation. High utilization alerts indicate when a DC is approaching capacity limits.

**Supplier Performance Management**: Monitors supplier reliability and lead time consistency to support procurement decisions. Managers can identify suppliers with poor performance and adjust ordering strategies accordingly.

**Revenue Monitoring**: Tracks order fulfillment and revenue by region to understand geographic performance patterns and identify high-performing or underperforming markets.

The dashboard operates on a near-real-time basis, with KPIs recomputed every minute and displayed metrics reflecting the last 15 minutes of operational data. This time horizon enables proactive decision-making rather than reactive problem-solving.

## Underlying Data Model

The dashboard is built on a star schema data model with fact tables capturing operational events and dimension tables providing descriptive attributes.

### Fact Tables

**Orders Fact** (`orders_fact`): Captures customer order events with the following key attributes:
- `order_ts`: Timestamp when the order was placed
- `sku_id`: Product identifier
- `dc_id`: Distribution center identifier
- `quantity`: Number of units ordered (requested quantity)
- `fulfilled_qty`: Number of units actually fulfilled from available inventory
- `lost_sales_qty`: Number of units that could not be fulfilled due to stockout
- `order_value`: Revenue from fulfilled units
- `lost_sale_flag`: Boolean indicating if any units were lost due to stockout

**Inventory Fact** (`inventory_fact`): Contains periodic snapshots of inventory state:
- `inventory_ts`: Timestamp of the snapshot
- `sku_id`: Product identifier
- `dc_id`: Distribution center identifier
- `on_hand_qty`: Current inventory level in units
- `safety_stock`: Minimum buffer stock level for this SKU-DC
- `reorder_point`: Inventory level that triggers replenishment orders

**Shipments Fact** (`shipments_fact`): Tracks supplier shipments and replenishment orders:
- `shipment_ts`: Timestamp when shipment was created
- `sku_id`: Product identifier
- `supplier_id`: Supplier identifier
- `destination_dc_id`: Target distribution center
- `quantity`: Number of units in shipment
- `expected_arrival_ts`: Projected arrival timestamp
- `actual_arrival_ts`: Actual arrival timestamp (null until shipment arrives)
- `lead_time_days`: Actual lead time from shipment creation to arrival

### Dimension Tables

**SKU Dimension** (`skus_dim`): Product master data including product name, category, unit cost, storage requirements (cubic meters per unit), and base demand characteristics.

**Distribution Center Dimension** (`dcs_dim`): Warehouse master data including DC name, region assignment, storage capacity in cubic meters, and throughput capacity.

**Region Dimension** (`regions_dim`): Geographic regions with demand factors and volatility characteristics.

**Supplier Dimension** (`suppliers_dim`): Supplier master data including supplier name, reliability score (0-1 scale), and typical lead time characteristics.

### Grain of Analysis

The primary grain of analysis is **SKU-DC-Time**: each KPI computation groups data by SKU and Distribution Center, with time windows applied to filter recent events. This granularity enables managers to identify specific product-location combinations that require attention.

## Data Freshness and Update Cycle

KPIs are recomputed every 60 seconds by Apache Spark jobs orchestrated by Airflow. The computation process:

1. Spark reads the last 15 minutes of data from MongoDB fact tables
2. Performs multi-table joins with dimension tables
3. Computes aggregations and derived metrics
4. Writes results to Redis cache with a 120-second TTL

The dashboard reads exclusively from Redis, ensuring sub-second response times. The dashboard auto-refreshes every 60 seconds to display the latest computed KPIs.

**What "Current" Means**: When the dashboard displays "current inventory" or "current stockout risk", it refers to the most recent snapshot within the last 15-minute analysis window. Inventory snapshots are taken every 60 seconds by the data generator, so "current" typically means data from the last 1-2 minutes.

**Time Window Rationale**: The 15-minute window balances recency with statistical significance. Too short a window (e.g., 1 minute) would have insufficient data for reliable demand velocity calculations. Too long a window (e.g., 1 hour) would delay detection of rapid inventory depletion.

## KPI Definitions and Calculations

### Total Inventory Level

**Business Meaning**: Total units of each product currently held at each distribution center, including both sellable stock and safety stock buffer.

**Calculation Logic**:
- Groups inventory snapshots by SKU and DC
- Computes average `on_hand_qty` across all snapshots in the 15-minute window
- Joins with SKU and DC dimensions to include product names and DC names
- Results are sorted by inventory level (highest first)

**Data Sources**: `inventory_fact` (last 15 minutes), `skus_dim`, `dcs_dim`

**Manager Action**: 
- High inventory levels may indicate overstocking or slow-moving items
- Low inventory levels combined with high demand velocity indicate replenishment urgency
- Compare inventory levels across DCs to identify rebalancing opportunities

### Stockout Risk / Days to Stockout

**Business Meaning**: Projected number of days until inventory depletion for each SKU-DC combination, accounting for current demand velocity and safety stock requirements.

**Calculation Logic**:
1. Compute demand velocity: Sum all order quantities for each SKU-DC in the 15-minute window, then divide by the window duration in days to get units per day
2. Get current stock: Average `on_hand_qty` for each SKU-DC from inventory snapshots
3. Get safety stock: Maximum `safety_stock` value for each SKU-DC (constant per SKU-DC)
4. Calculate available stock: `current_stock - safety_stock`
5. Calculate days to stockout: `available_stock / units_per_day` (if demand > 0 and available stock > 0)
6. Apply severity classification:
   - Critical: ≤ 3 days
   - Warning: ≤ 7 days
   - Normal: > 7 days

Only items with Critical or Warning severity are displayed in the stockout alerts table.

**Data Sources**: `orders_fact` (last 15 minutes), `inventory_fact` (last 15 minutes), `skus_dim`, `dcs_dim`, `regions_dim`

**Manager Action**:
- Critical items (≤ 3 days): Immediate replenishment required, expedite supplier orders if possible
- Warning items (≤ 7 days): Plan replenishment within 24-48 hours, verify supplier lead times
- Monitor demand rate trends: If demand is accelerating, adjust reorder points upward

### Distribution Center Utilization Rate

**Business Meaning**: Percentage of storage capacity currently occupied at each distribution center, calculated by summing the volume (cubic meters) of all inventory items.

**Calculation Logic**:
1. Join inventory snapshots with SKU dimension to get `storage_m3` per unit
2. Calculate item volume: `on_hand_qty × storage_m3` for each inventory record
3. Sum item volumes by DC to get total occupied volume
4. Divide occupied volume by DC capacity to get utilization rate
5. Classify status:
   - OVERLOADED: ≥ 85%
   - HIGH: ≥ 70%
   - NORMAL: ≥ 50%
   - LOW: < 50%

**Data Sources**: `inventory_fact` (last 15 minutes), `skus_dim`, `dcs_dim`

**Manager Action**:
- OVERLOADED DCs: Immediate action required - transfer inventory to other DCs, increase capacity, or slow inbound shipments
- HIGH utilization: Plan for capacity expansion or inventory rebalancing
- LOW utilization: Opportunity to consolidate operations or accept more inventory transfers

### Supplier Lead Time Performance

**Business Meaning**: Analysis of supplier reliability based on actual lead times versus expected lead times, measuring both average performance and consistency (variance).

**Calculation Logic**:
1. Join shipments with supplier dimension
2. For each supplier, compute:
   - `shipment_count`: Total number of shipments
   - `avg_actual_lead_time`: Average of `lead_time_days` across all shipments
   - `lead_time_variance`: Standard deviation of `lead_time_days`
3. Calculate performance score: `1.0 - (variance / average_lead_time)` to penalize high variance
4. Results include supplier reliability score from dimension table for comparison

**Data Sources**: `shipments_fact` (last 15 minutes), `suppliers_dim`

**Manager Action**:
- Low performance score or high variance: Consider diversifying suppliers, negotiating better terms, or increasing safety stock for items from unreliable suppliers
- High reliability score with low variance: Prefer these suppliers for critical items or time-sensitive replenishment
- Compare actual lead times to supplier promises to identify discrepancies

### Regional Revenue Distribution

**Business Meaning**: Total revenue, order count, and units fulfilled by geographic region over the last 15 minutes, enabling identification of high-performing and underperforming markets.

**Calculation Logic**:
1. Join orders with DC dimension to get region assignment
2. Join with region dimension
3. Group by region and compute:
   - `total_orders`: Count of order events
   - `total_units_fulfilled`: Sum of `fulfilled_qty`
   - `total_revenue`: Sum of `order_value`
   - `avg_order_value`: Average `order_value`
4. Results sorted by revenue (highest first)

**Data Sources**: `orders_fact` (last 15 minutes), `dcs_dim`, `regions_dim`

**Manager Action**:
- High revenue regions: Ensure adequate inventory allocation, consider expanding capacity
- Low revenue regions: Investigate demand patterns, marketing effectiveness, or competitive factors
- Monitor revenue trends over time to identify growth or decline patterns

### Revenue (Recent Window)

**Business Meaning**: Total revenue from fulfilled orders in the last 15 minutes, representing near-real-time sales performance.

**Calculation Logic**:
- Sum of `order_value` from all orders in the 15-minute window
- Only includes revenue from fulfilled units (lost sales are excluded)

**Data Sources**: `orders_fact` (last 15 minutes)

**Manager Action**:
- Compare to historical averages to identify sales spikes or drops
- Correlate with inventory levels: High revenue with low inventory may indicate stockout risk
- Use for short-term demand forecasting

### Top SKUs by Inventory

**Business Meaning**: Products with the highest inventory levels across all distribution centers, helping identify potential overstock situations.

**Calculation Logic**:
- Same as Total Inventory Level KPI, but sorted by inventory level descending
- Typically displays top 20-50 SKUs

**Data Sources**: `inventory_fact` (last 15 minutes), `skus_dim`, `dcs_dim`

**Manager Action**:
- High inventory SKUs: Review demand forecasts, consider promotional activities, or slow replenishment
- Identify slow-moving items that may require markdowns or discontinuation

## Stockout Risk Logic (Detailed)

The stockout risk calculation is the most complex KPI and requires detailed explanation of its components and rationale.

### Demand Rate Calculation

Demand rate (units per day) is computed from order history:

```
total_ordered = SUM(quantity) for all orders in 15-minute window, grouped by SKU-DC
window_days = 15 minutes / (24 hours × 60 minutes) = 0.0104 days
units_per_day = total_ordered / window_days
```

This calculation assumes demand is relatively constant over the analysis window. For SKU-DC combinations with no orders in the window, `units_per_day` is set to 0, resulting in "infinite" days to stockout (9999 days).

### Safety Stock Usage

Safety stock is a buffer maintained to handle demand variability and supply uncertainty. It is stored per SKU-DC combination in the `inventory_state` collection and is constant for each SKU-DC (typically calculated as 7 days of average demand).

In the stockout calculation, safety stock is excluded from available inventory because:
- Safety stock is not intended for normal demand fulfillment
- It serves as a buffer for unexpected demand spikes or supply delays
- Depleting safety stock indicates the system is operating in a risky state

### Available Stock Calculation

Available stock represents inventory that can be used to fulfill normal demand:

```
available_stock = current_stock - safety_stock
```

If `available_stock ≤ 0`, the item is effectively at or below the safety stock level, and days to stockout is set to 0 (immediate risk).

### Days to Stockout Formula

The complete formula with edge case handling:

```
IF current_stock ≤ 0:
    days_to_stockout = 0 (out of stock)
ELSE IF units_per_day ≤ 0:
    days_to_stockout = 9999 (no demand, effectively infinite)
ELSE IF available_stock ≤ 0:
    days_to_stockout = 0 (at or below safety stock)
ELSE:
    days_to_stockout = available_stock / units_per_day
```

### Severity Levels

Severity classification provides actionable thresholds:

- **Critical (≤ 3 days)**: Immediate action required. Inventory will deplete within 3 days at current demand rate. Expedite replenishment orders, consider emergency transfers from other DCs, or implement demand management (e.g., limit order quantities).

- **Warning (≤ 7 days)**: Replenishment planning required. Inventory will deplete within a week. Verify supplier lead times, confirm replenishment orders are in transit, and monitor demand trends closely.

- **Normal (> 7 days)**: No immediate action needed. Sufficient inventory buffer exists. Continue normal replenishment cycles.

The dashboard only displays Critical and Warning items in the stockout alerts table to focus manager attention on items requiring action.

## How Managers Should Use This Dashboard

### Daily Operational Monitoring

Managers should review the dashboard at the start of each shift and periodically throughout the day (every 2-4 hours). Focus areas:

1. **Stockout Alerts Table**: Review all Critical and Warning items. For Critical items, verify replenishment orders are placed and expedited if possible. For Warning items, confirm replenishment is scheduled within the next 24-48 hours.

2. **DC Utilization**: Check for OVERLOADED or HIGH utilization DCs. If any DC exceeds 85% capacity, immediately assess options: transfer inventory to other DCs, slow inbound shipments, or activate overflow storage.

3. **Total Inventory KPI Card**: Monitor the aggregate inventory level. Significant drops may indicate systemic issues (e.g., supplier delays, demand spikes). Compare to historical baselines.

### Identifying Replenishment Priorities

The stockout risk calculation provides a clear prioritization mechanism:

1. Sort stockout alerts by `days_until_stockout` (ascending)
2. Items with the lowest days-to-stockout should receive highest priority for replenishment
3. Cross-reference with supplier performance: For items with low days-to-stockout and unreliable suppliers, consider:
   - Placing larger order quantities to extend coverage
   - Diversifying to additional suppliers
   - Increasing safety stock levels for these items

### Detecting Supplier Issues

Monitor the Supplier Performance section:

1. Identify suppliers with high variance in lead times (high `lead_time_std_dev` relative to average)
2. Compare actual lead times to supplier promises or historical averages
3. For suppliers with declining performance scores:
   - Review recent shipment history for patterns
   - Contact suppliers to understand delays
   - Consider adjusting safety stock or reorder points for items sourced from these suppliers
   - Evaluate alternative suppliers

### Inventory Rebalancing Decisions

Use the dashboard to identify rebalancing opportunities:

1. **High Inventory + Low Demand**: If a SKU shows high inventory levels at one DC but low demand velocity, consider transferring to DCs with higher demand or lower inventory.

2. **DC Capacity Imbalance**: If one DC is OVERLOADED while others are LOW, identify SKUs that can be transferred. Prioritize transfers of high-volume items to maximize capacity relief.

3. **Regional Demand Patterns**: Use Regional Revenue to identify regions with high demand but low local inventory. Consider rebalancing inventory toward high-demand regions.

### Action Correspondences

**KPI Signal → Manager Action**:

- **Stockout Alert (Critical)**: Expedite replenishment, verify supplier commitments, consider emergency transfers, implement demand management
- **Stockout Alert (Warning)**: Confirm replenishment orders placed, verify supplier lead times, monitor demand trends
- **DC Utilization (OVERLOADED)**: Transfer inventory, slow inbound shipments, activate overflow storage, plan capacity expansion
- **DC Utilization (HIGH)**: Plan inventory rebalancing, schedule capacity review, optimize storage layout
- **Supplier Performance (Low Score)**: Review supplier relationship, diversify suppliers, increase safety stock, negotiate better terms
- **Regional Revenue (High)**: Ensure adequate inventory allocation, consider expanding DC capacity in region
- **Regional Revenue (Low)**: Investigate demand patterns, review marketing effectiveness, assess competitive factors

## What the Dashboard Is Optimized For

The dashboard is designed for **real-time operational monitoring** rather than ad-hoc analysis or historical reporting. This design choice has several implications:

**Precomputed KPIs**: All metrics are computed by Spark jobs every minute and cached in Redis. The dashboard reads precomputed results, ensuring sub-second response times. This architecture supports high-frequency monitoring without querying operational databases directly.

**Time-Bounded Analysis**: KPIs focus on the last 15 minutes of data, providing a near-real-time view of current operations. This window is optimal for detecting rapid changes (e.g., sudden inventory depletion, demand spikes) but is not suitable for long-term trend analysis or monthly reporting.

**Operational Focus**: The dashboard emphasizes actionable alerts (stockout risks, capacity issues) rather than comprehensive analytics. Managers use it to identify problems and take immediate action, not to perform deep-dive analysis.

**Expected Usage Pattern**: The intended workflow is **observe → identify → act**:
1. Manager opens dashboard
2. Reviews alerts and KPI cards (30-60 seconds)
3. Identifies items requiring attention
4. Takes action (places orders, transfers inventory, contacts suppliers)
5. Monitors impact in subsequent dashboard refreshes

For historical analysis, trend reporting, or complex ad-hoc queries, managers should use dedicated analytics tools that query the full historical dataset (including HDFS archives) rather than this real-time dashboard.


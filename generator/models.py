"""
Statistical Models for Supply Chain Data Generation
Uses: Poisson, Normal, Exponential, Log-Normal distributions
"""

import numpy as np
from datetime import datetime, timezone, timedelta


class StatisticalModels:
    """
    Encapsulates all statistical data generation logic
    """
    
    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)
    
    # ============================================================
    # ORDER GENERATION (Poisson-based arrival rates)
    # ============================================================
    
    def generate_order_count(self, base_lambda, region_factor, demand_volatility):
        """
        Generate number of orders per time window using Poisson distribution
        
        Args:
            base_lambda: Base arrival rate (from SKU config)
            region_factor: Regional demand multiplier
            demand_volatility: Adds random variation (0-1 scale)
        
        Returns:
            Integer count of orders
        """
        # Add time-of-day effect (simulate peak/off-peak hours)
        hour = datetime.now(timezone.utc).hour
        time_multiplier = self._get_time_multiplier(hour)
        
        # Context-aware lambda
        adjusted_lambda = base_lambda * region_factor * time_multiplier
        
        # Add volatility (stochastic variation)
        volatility_factor = 1.0 + self.rng.normal(0, demand_volatility)
        final_lambda = max(1.0, adjusted_lambda * volatility_factor)
        
        # Sample from Poisson
        return int(self.rng.poisson(final_lambda))
    
    def _get_time_multiplier(self, hour):
        """
        Simulate time-of-day demand patterns
        Peak: 9am-5pm (business hours)
        Off-peak: night hours
        """
        if 9 <= hour <= 17:
            return 1.5  # Peak hours
        elif 18 <= hour <= 22:
            return 1.2  # Evening
        else:
            return 0.7  # Night/early morning
    
    # ============================================================
    # QUANTITY GENERATION (Poisson for discrete counts)
    # ============================================================
    
    def generate_order_quantity(self, mean_qty=5):
        """
        Generate order quantity using Poisson distribution
        Most orders are small (1-5 units), some are bulk (10-20)
        """
        qty = int(self.rng.poisson(mean_qty))
        return max(1, qty)  # Ensure at least 1
    
    # ============================================================
    # PRICING (Log-Normal for right-skewed distributions)
    # ============================================================
    
    def generate_order_value(self, unit_cost, quantity, margin_pct=0.30):
        """
        Generate order value using log-normal distribution
        
        Args:
            unit_cost: Base cost per unit
            quantity: Number of units
            margin_pct: Profit margin (default 30%)
        
        Returns:
            Float: Total order value with realistic variance
        """
        # Expected value (cost + margin)
        expected_value = unit_cost * quantity * (1 + margin_pct)
        
        # Log-normal parameters
        mu = np.log(expected_value)
        sigma = 0.2  # ~20% coefficient of variation
        
        value = self.rng.lognormal(mu, sigma)
        return round(max(unit_cost * quantity, value), 2)  # Can't be below cost
    
    # ============================================================
    # LEAD TIME GENERATION (Normal distribution with floor)
    # ============================================================
    
    def generate_lead_time(self, avg_days, stddev_days):
        """
        Generate supplier lead time using Normal distribution
        
        Args:
            avg_days: Average lead time
            stddev_days: Standard deviation (reliability indicator)
        
        Returns:
            Float: Actual lead time in days
        """
        lead_time = self.rng.normal(avg_days, stddev_days)
        return round(max(1.0, lead_time), 2)  # At least 1 day
    
    # ============================================================
    # DELAY GENERATION (Exponential for random delays)
    # ============================================================
    
    def generate_fulfillment_delay(self, mean_hours=2.0):
        """
        Generate fulfillment processing delay using Exponential distribution
        (memoryless property = good for queue times)
        
        Args:
            mean_hours: Average processing time
        
        Returns:
            Float: Delay in hours
        """
        delay = self.rng.exponential(mean_hours)
        return round(max(0.5, delay), 2)
    
    # ============================================================
    # INVENTORY INITIALIZATION
    # ============================================================
    
    def generate_initial_inventory(self, min_stock=500, max_stock=5000):
        """
        Generate starting inventory level using Uniform distribution
        """
        return int(self.rng.integers(min_stock, max_stock + 1))
    
    def generate_safety_stock(self, base_stock, coverage_days=7):
        """
        Calculate safety stock (minimum buffer)
        Typically 10-20% of base stock, adjusted by desired coverage
        """
        safety_pct = self.rng.uniform(0.10, 0.20)
        return int(base_stock * safety_pct)
    
    def generate_reorder_point(self, daily_demand, lead_time_days, safety_stock):
        """
        Calculate reorder point (when to trigger replenishment)
        ROP = (avg daily demand × lead time) + safety stock
        """
        return int(daily_demand * lead_time_days + safety_stock)
    
    # ============================================================
    # CORRELATED ATTRIBUTES (Business logic-based relationships)
    # ============================================================
    
    def generate_priority_with_value_correlation(self, order_value):
        """
        High-value orders are more likely to be HIGH priority
        Uses conditional probability
        """
        if order_value > 5000:
            # High value: 60% HIGH, 35% NORMAL, 5% LOW
            return self.rng.choice(
                ["HIGH", "NORMAL", "LOW"],
                p=[0.60, 0.35, 0.05]
            )
        elif order_value > 1000:
            # Medium value: 20% HIGH, 70% NORMAL, 10% LOW
            return self.rng.choice(
                ["HIGH", "NORMAL", "LOW"],
                p=[0.20, 0.70, 0.10]
            )
        else:
            # Low value: 5% HIGH, 60% NORMAL, 35% LOW
            return self.rng.choice(
                ["HIGH", "NORMAL", "LOW"],
                p=[0.05, 0.60, 0.35]
            )
    
    # ============================================================
    # TIMESTAMP UTILITIES
    # ============================================================
    
    @staticmethod
    def now_utc():
        """Return current UTC timestamp"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def future_timestamp(days_ahead):
        """Generate future timestamp for expected arrivals"""
        return datetime.now(timezone.utc) + timedelta(days=days_ahead)


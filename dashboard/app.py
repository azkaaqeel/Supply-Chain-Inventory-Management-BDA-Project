"""
Supply Chain Analytics Dashboard - Production Grade
PowerBI-Style Real-Time Analytics Platform

Author: Supply Chain Analytics Team
Version: 3.0 (Redesigned)
"""

import streamlit as st
import redis
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Any, Union
import traceback

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Supply Chain Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# THEME & STYLING - POWERBI INSPIRED
# ============================================================
THEME = {
    'primary': '#00B4D8',      # Teal
    'secondary': '#0077B6',     # Deep blue
    'success': '#06D6A0',       # Green
    'warning': '#FFB703',       # Amber
    'danger': '#EF476F',        # Red
    'background': '#F8F9FA',    # Light gray
    'card': '#FFFFFF',          # White
    'text_primary': '#212529',  # Dark gray
    'text_secondary': '#6C757D', # Medium gray
    'border': '#DEE2E6'         # Light border
}

def inject_custom_css():
    """PowerBI-inspired professional styling"""
    st.markdown(f"""
    <style>
        /* Main container */
        .main {{
            background-color: {THEME['background']};
        }}
        
        /* Remove default padding */
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
        }}
        
        /* Header styling */
        .dashboard-header {{
            background: linear-gradient(135deg, {THEME['primary']} 0%, {THEME['secondary']} 100%);
            padding: 1.5rem 2rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            color: white;
        }}
        
        .dashboard-title {{
            font-size: 1.8rem;
            font-weight: 600;
            margin: 0;
            color: white;
        }}
        
        .dashboard-subtitle {{
            font-size: 0.95rem;
            opacity: 0.9;
            margin: 0.3rem 0 0 0;
        }}
        
        /* KPI Card styling - Clean PowerBI style */
        .kpi-card {{
            background: {THEME['card']};
            padding: 1.25rem;
            border-radius: 6px;
            border: 1px solid {THEME['border']};
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
            transition: all 0.2s;
            height: 100%;
        }}
        
        .kpi-card:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transform: translateY(-2px);
        }}
        
        .kpi-label {{
            font-size: 0.75rem;
            color: {THEME['text_secondary']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .kpi-value {{
            font-size: 2rem;
            font-weight: 700;
            color: {THEME['text_primary']};
            margin: 0.25rem 0;
        }}
        
        .kpi-change {{
            font-size: 0.85rem;
            font-weight: 500;
        }}
        
        .kpi-change.positive {{
            color: {THEME['success']};
        }}
        
        .kpi-change.negative {{
            color: {THEME['danger']};
        }}
        
        /* Status badges */
        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            display: inline-block;
        }}
        
        .status-success {{
            background: {THEME['success']}20;
            color: {THEME['success']};
        }}
        
        .status-warning {{
            background: {THEME['warning']}20;
            color: {THEME['warning']};
        }}
        
        .status-danger {{
            background: {THEME['danger']}20;
            color: {THEME['danger']};
        }}
        
        /* Section styling */
        .section-container {{
            background: {THEME['card']};
            padding: 1.5rem;
            border-radius: 6px;
            border: 1px solid {THEME['border']};
            margin-bottom: 1.5rem;
        }}
        
        .section-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: {THEME['text_primary']};
            margin: 0 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid {THEME['primary']};
        }}
        
        /* Filter bar */
        .filter-bar {{
            background: {THEME['card']};
            padding: 1rem;
            border-radius: 6px;
            border: 1px solid {THEME['border']};
            margin-bottom: 1.5rem;
        }}
        
        /* Data freshness indicator */
        .freshness-indicator {{
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.75rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .freshness-fresh {{
            background: {THEME['success']}20;
            color: {THEME['success']};
        }}
        
        .freshness-stale {{
            background: {THEME['warning']}20;
            color: {THEME['warning']};
        }}
        
        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {THEME['primary']} 0%, {THEME['secondary']} 100%);
        }}
        
        [data-testid="stSidebar"] * {{
            color: white !important;
        }}
        
        /* Error/warning styling */
        .stAlert {{
            border-radius: 6px;
        }}
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# REDIS CONNECTION
# ============================================================
@st.cache_resource
def get_redis_connection():
    """Initialize Redis connection with robust error handling"""
    try:
        r = redis.Redis(
            host='redis',
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True
        )
        r.ping()
        return r
    except Exception as e:
        st.error(f"Redis connection failed: {e}")
        return None

# ============================================================
# DATA NORMALIZATION LAYER
# ============================================================
def safe_read_json(redis_client, key: str) -> Optional[Union[dict, list, str]]:
    """Safely read and parse JSON from Redis (or return plain string)"""
    if not redis_client:
        return None
    try:
        data = redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                # Not JSON - return as plain string (e.g., last_update timestamp)
                return data
    except Exception as e:
        st.warning(f"Error reading {key}: {e}")
    return None

def normalize_inventory(data: Any) -> pd.DataFrame:
    """
    Normalize inventory data to standard schema.
    Handles various field name variations.
    
    Returns DataFrame with columns:
    - sku_id, dc_id, dc_name, product_name, category
    - current_inventory (numeric)
    - safety_stock_level (numeric)
    """
    if not data:
        return pd.DataFrame()
    
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
    
    # Normalize field names (handle variations)
    field_mappings = {
        'current_inventory': ['current_inventory', 'total_inventory', 'inventory', 
                             'on_hand_qty', 'avg_on_hand_qty', 'quantity'],
        'safety_stock_level': ['safety_stock_level', 'safety_stock', 'safety_stock_qty',
                               'min_stock', 'reorder_point']
    }
    
    for target_field, possible_names in field_mappings.items():
        if target_field not in df.columns:
            for name in possible_names:
                if name in df.columns:
                    df[target_field] = df[name]
                    break
    
    # Ensure numeric types
    for col in ['current_inventory', 'safety_stock_level']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Ensure required columns exist
    required = ['current_inventory', 'safety_stock_level']
    for col in required:
        if col not in df.columns:
            df[col] = 0
    
    return df

def normalize_stockout_alerts(data: Any) -> pd.DataFrame:
    """
    Normalize stockout alert data.
    
    Returns DataFrame with columns:
    - sku_id, dc_id, dc_name, product_name
    - days_to_stockout (numeric)
    - severity (string: critical/high/medium/low)
    - stock_level, demand_rate_per_day
    """
    if not data:
        return pd.DataFrame()
    
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
    
    # Normalize days_to_stockout field (multiple possible names)
    if 'days_to_stockout' not in df.columns:
        for col in ['days_until_stockout', 'stockout_days', 'tte', 'days_to_stock_out']:
            if col in df.columns:
                df['days_to_stockout'] = df[col]
                break
    
    if 'days_to_stockout' in df.columns:
        df['days_to_stockout'] = pd.to_numeric(df['days_to_stockout'], errors='coerce').fillna(999)
    else:
        df['days_to_stockout'] = 999
    
    # Handle null product/DC names - use IDs as fallback
    if 'product_name' in df.columns:
        df['product_name'] = df['product_name'].fillna(df['sku_id'])
    else:
        df['product_name'] = df['sku_id']
    
    if 'dc_name' in df.columns:
        df['dc_name'] = df['dc_name'].fillna(df['dc_id'])
    else:
        df['dc_name'] = df['dc_id']
    
    # Ensure numeric fields exist
    if 'stock_level' in df.columns:
        df['stock_level'] = pd.to_numeric(df['stock_level'], errors='coerce').fillna(0)
    
    if 'demand_rate_per_day' in df.columns:
        df['demand_rate_per_day'] = pd.to_numeric(df['demand_rate_per_day'], errors='coerce').fillna(0)
    
    # Add severity classification
    def classify_severity(days):
        if days < 1:
            return 'critical'
        elif days < 3:
            return 'high'
        elif days < 7:
            return 'medium'
        else:
            return 'low'
    
    df['severity'] = df['days_to_stockout'].apply(classify_severity)
    
    return df

def normalize_supplier_performance(data: Any) -> pd.DataFrame:
    """
    Normalize supplier performance data.
    
    Returns DataFrame with columns:
    - supplier_id, supplier_name
    - avg_lead_time_days (numeric)
    - reliability_score (0-1)
    - performance_score (0-1)
    - shipment_count (optional)
    """
    if not data:
        return pd.DataFrame()
    
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
    
    # Normalize field names
    if 'avg_lead_time_days' not in df.columns:
        for col in ['lead_time', 'avg_lead_time', 'lead_time_days']:
            if col in df.columns:
                df['avg_lead_time_days'] = df[col]
                break
    
    if 'reliability_score' not in df.columns:
        for col in ['reliability', 'reliability_pct', 'on_time_pct']:
            if col in df.columns:
                df['reliability_score'] = df[col]
                break
    
    # Ensure numeric types
    for col in ['avg_lead_time_days', 'reliability_score', 'performance_score']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Ensure required columns
    if 'reliability_score' not in df.columns:
        df['reliability_score'] = 0
    if 'performance_score' not in df.columns:
        df['performance_score'] = 0
    if 'avg_lead_time_days' not in df.columns:
        df['avg_lead_time_days'] = 0
    
    return df

def normalize_dc_utilization(data: Any) -> pd.DataFrame:
    """
    Normalize DC utilization data.
    
    Returns DataFrame with columns:
    - dc_id, dc_name
    - utilization_rate (0-1)
    - capacity (optional)
    """
    if not data:
        return pd.DataFrame()
    
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
    
    # Normalize utilization field
    if 'utilization_rate' not in df.columns:
        for col in ['utilization', 'dc_utilization', 'utilization_pct', 'util_rate']:
            if col in df.columns:
                df['utilization_rate'] = df[col]
                break
    
    if 'utilization_rate' in df.columns:
        df['utilization_rate'] = pd.to_numeric(df['utilization_rate'], errors='coerce').fillna(0)
        # If values are > 1, assume they're percentages and normalize to 0-1
        if df['utilization_rate'].max() > 1:
            df['utilization_rate'] = df['utilization_rate'] / 100
    else:
        df['utilization_rate'] = 0
    
    return df

def normalize_regional_revenue(data: Any) -> pd.DataFrame:
    """
    Normalize regional revenue/performance data.
    
    Returns DataFrame with columns:
    - region_id, region_name
    - total_revenue (numeric)
    - total_orders (optional)
    """
    if not data:
        return pd.DataFrame()
    
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
    
    # Normalize revenue field (check revenue first, then total_revenue)
    if 'total_revenue' not in df.columns:
        for col in ['revenue', 'total_sales', 'sales']:
            if col in df.columns:
                df['total_revenue'] = df[col]
                break
    
    # If still no total_revenue column, create it
    if 'total_revenue' in df.columns:
        df['total_revenue'] = pd.to_numeric(df['total_revenue'], errors='coerce').fillna(0)
    else:
        df['total_revenue'] = 0
    
    if 'total_orders' in df.columns:
        df['total_orders'] = pd.to_numeric(df['total_orders'], errors='coerce').fillna(0)
    
    return df

# ============================================================
# DATA LOADING WITH NORMALIZATION
# ============================================================
@st.cache_data(ttl=10)
def load_kpis(_redis_client) -> Dict[str, Any]:
    """Load and normalize all KPIs from Redis"""
    if not _redis_client:
        return {}
    
    kpis = {
        'inventory': normalize_inventory(safe_read_json(_redis_client, 'kpi:inventory_level')),
        'stockout_alerts': normalize_stockout_alerts(safe_read_json(_redis_client, 'kpi:stockout_alerts')),
        'supplier_performance': normalize_supplier_performance(safe_read_json(_redis_client, 'kpi:supplier_performance')),
        'dc_utilization': normalize_dc_utilization(safe_read_json(_redis_client, 'kpi:dc_utilization')),
        'regional_performance': normalize_regional_revenue(safe_read_json(_redis_client, 'kpi:regional_performance')),
        'last_update': safe_read_json(_redis_client, 'kpi:last_update'),
        'stockout_count': safe_read_json(_redis_client, 'kpi:stockout_risk_count') or 0,
        'dc_overload_count': safe_read_json(_redis_client, 'kpi:dc_overloaded_count') or 0,
        'analysis_window': safe_read_json(_redis_client, 'kpi:analysis_window_minutes') or 15
    }
    
    return kpis

# ============================================================
# DEBUG UTILITY
# ============================================================
def render_debug_panel(redis_client):
    """Debug panel to inspect Redis keys and data structure"""
    with st.expander("🔍 Debug: Redis Data Inspector", expanded=False):
        if not redis_client:
            st.error("Redis not connected")
            return
        
        try:
            # List all KPI keys
            keys = redis_client.keys("kpi:*")
            st.write(f"**Found {len(keys)} KPI keys**")
            
            for key in sorted(keys):
                st.markdown(f"---\n**Key:** `{key}`")
                
                try:
                    # Get data type
                    data_type = redis_client.type(key)
                    st.write(f"Type: `{data_type}`")
                    
                    # Get value
                    value = redis_client.get(key)
                    
                    if value:
                        # Show length
                        st.write(f"Length: {len(value)} chars")
                        
                        # Try to parse as JSON
                        try:
                            parsed = json.loads(value)
                            st.write("**Structure:**")
                            
                            if isinstance(parsed, list):
                                st.write(f"- List with {len(parsed)} items")
                                if len(parsed) > 0:
                                    st.write("- First item keys:", list(parsed[0].keys()) if isinstance(parsed[0], dict) else "N/A")
                            elif isinstance(parsed, dict):
                                st.write(f"- Dict with keys:", list(parsed.keys()))
                            else:
                                st.write(f"- Value: {parsed}")
                            
                            # Show preview (first 500 chars)
                            preview = str(parsed)[:500]
                            st.code(preview, language='json')
                            
                        except json.JSONDecodeError:
                            st.write("**Raw value (first 500 chars):**")
                            st.code(value[:500])
                    else:
                        st.write("(empty)")
                        
                except Exception as e:
                    st.error(f"Error inspecting {key}: {e}")
                    
        except Exception as e:
            st.error(f"Error listing keys: {e}")
            st.code(traceback.format_exc())

# ============================================================
# DASHBOARD COMPONENTS
# ============================================================
def render_header(last_update, data_freshness):
    """Render dashboard header"""
    st.markdown(f"""
    <div class="dashboard-header">
        <div class="dashboard-title">Supply Chain Analytics</div>
        <div class="dashboard-subtitle">Real-Time Inventory Optimization & Performance Intelligence</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Data freshness bar
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        if last_update and last_update != 'N/A':
            try:
                if isinstance(last_update, str):
                    dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_time = last_update
                st.markdown(f"**Last Updated:** {formatted_time}")
            except:
                st.markdown(f"**Last Updated:** {last_update}")
        else:
            st.markdown("**Last Updated:** Waiting for data...")
    
    with col2:
        freshness_class = 'freshness-fresh' if data_freshness == 'Fresh' else 'freshness-stale'
        st.markdown(f'<span class="freshness-indicator {freshness_class}">Data: {data_freshness}</span>', 
                   unsafe_allow_html=True)
    
    with col3:
        st.markdown("**Auto-Refresh:** 60s")
    
    with col4:
        st.markdown(f"**Time:** {datetime.now().strftime('%H:%M:%S')}")

def render_kpi_cards(kpis: Dict):
    """Render executive KPI cards - clean PowerBI style"""
    
    # Extract normalized data
    df_inv = kpis.get('inventory', pd.DataFrame())
    df_supplier = kpis.get('supplier_performance', pd.DataFrame())
    df_dc = kpis.get('dc_utilization', pd.DataFrame())
    df_regional = kpis.get('regional_performance', pd.DataFrame())
    stockout_count = kpis.get('stockout_count', 0)
    
    # Calculate metrics
    total_inventory = int(df_inv['current_inventory'].sum()) if not df_inv.empty else 0
    avg_lead_time = df_supplier['avg_lead_time_days'].mean() if not df_supplier.empty else 0
    avg_dc_util = (df_dc['utilization_rate'].mean() * 100) if not df_dc.empty else 0
    total_revenue = df_regional['total_revenue'].sum() if not df_regional.empty else 0
    
    # KPI Cards
    cols = st.columns(5)
    
    kpis_data = [
        {
            'label': 'Total Inventory',
            'value': f'{total_inventory:,}',
            'suffix': 'units',
            'color': THEME['primary']
        },
        {
            'label': 'Stockout Alerts',
            'value': f'{stockout_count}',
            'suffix': 'at risk',
            'color': THEME['danger'] if stockout_count > 20 else THEME['warning'] if stockout_count > 10 else THEME['success']
        },
        {
            'label': 'Avg Lead Time',
            'value': f'{avg_lead_time:.1f}',
            'suffix': 'days',
            'color': THEME['secondary']
        },
        {
            'label': 'DC Utilization',
            'value': f'{avg_dc_util:.1f}%',
            'suffix': 'capacity',
            'color': THEME['danger'] if avg_dc_util > 85 else THEME['warning'] if avg_dc_util > 75 else THEME['success']
        },
        {
            'label': 'Revenue (15 min)',
            'value': f'${total_revenue/1000:.1f}K' if total_revenue < 1000000 else f'${total_revenue/1000000:.2f}M',
            'suffix': 'orders',
            'color': THEME['success']
        }
    ]
    
    for col, kpi in zip(cols, kpis_data):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">{kpi['label']}</div>
                <div class="kpi-value" style="color: {kpi['color']};">{kpi['value']}</div>
                <div style="color: {THEME['text_secondary']}; font-size: 0.8rem;">{kpi['suffix']}</div>
            </div>
            """, unsafe_allow_html=True)

def render_overview_page(kpis: Dict, filters: Dict):
    """Render overview/home page with key charts"""
    st.markdown(f'<div class="section-title">Overview Dashboard</div>', unsafe_allow_html=True)
    
    df_inv = kpis.get('inventory', pd.DataFrame())
    df_regional = kpis.get('regional_performance', pd.DataFrame())
    df_dc = kpis.get('dc_utilization', pd.DataFrame())
    df_stockout = kpis.get('stockout_alerts', pd.DataFrame())
    
    # Apply filters
    if not df_inv.empty and filters.get('dc') and filters['dc'] != 'All':
        df_inv = df_inv[df_inv['dc_name'] == filters['dc']]
    
    # Row 1: Revenue by Region + DC Utilization
    col1, col2 = st.columns(2)
    
    with col1:
        if not df_regional.empty:
            fig = go.Figure(data=[go.Pie(
                labels=df_regional['region_name'],
                values=df_regional['total_revenue'],
                hole=0.5,
                marker=dict(colors=[THEME['primary'], THEME['secondary'], THEME['success'], 
                                   THEME['warning'], THEME['danger']]),
                textinfo='label+percent',
                hovertemplate='<b>%{label}</b><br>Revenue: $%{value:,.0f}<extra></extra>'
            )])
            fig.update_layout(
                title='Revenue Distribution by Region',
                height=350,
                template='plotly_white',
                margin=dict(t=40, b=20, l=20, r=20)
            )
            st.plotly_chart(fig, use_container_width=True, key='revenue_donut')
        else:
            st.info("No regional revenue data available yet")
    
    with col2:
        if not df_dc.empty:
            df_dc_sorted = df_dc.sort_values('utilization_rate', ascending=True)
            df_dc_sorted['utilization_pct'] = df_dc_sorted['utilization_rate'] * 100
            
            colors = [THEME['danger'] if x > 0.85 else THEME['warning'] if x > 0.75 else THEME['success'] 
                     for x in df_dc_sorted['utilization_rate']]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=df_dc_sorted['dc_name'],
                x=df_dc_sorted['utilization_pct'],
                orientation='h',
                marker=dict(color=colors),
                text=df_dc_sorted['utilization_pct'].round(1).astype(str) + '%',
                textposition='auto',
                hovertemplate='<b>%{y}</b><br>Utilization: %{x:.1f}%<extra></extra>'
            ))
            
            fig.add_vline(x=85, line_dash="dash", line_color=THEME['danger'], 
                         annotation_text="Threshold (85%)", annotation_position="top right")
            
            fig.update_layout(
                title='Distribution Center Utilization',
                xaxis_title='Utilization (%)',
                height=350,
                template='plotly_white',
                margin=dict(t=40, b=40, l=20, r=20),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True, key='dc_util_bar')
        else:
            st.info("No DC utilization data available yet")
    
    # Row 2: Inventory Heatmap
    if not df_inv.empty and 'dc_name' in df_inv.columns and 'product_name' in df_inv.columns:
        st.markdown("---")
        
        pivot = df_inv.pivot_table(
            values='current_inventory',
            index='product_name',
            columns='dc_name',
            aggfunc='sum',
            fill_value=0
        )
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[[0, '#f8f9fa'], [0.5, THEME['primary']], [1, THEME['secondary']]],
            hovertemplate='DC: %{x}<br>SKU: %{y}<br>Inventory: %{z:,.0f}<extra></extra>'
        ))
        fig.update_layout(
            title='Inventory Heatmap: SKU × Distribution Center',
            height=400,
            template='plotly_white',
            margin=dict(t=40, b=80, l=150, r=20)
        )
        st.plotly_chart(fig, use_container_width=True, key='inv_heatmap')

def render_inventory_page(kpis: Dict, filters: Dict):
    """Render detailed inventory analytics page"""
    st.markdown(f'<div class="section-title">Inventory Analytics</div>', unsafe_allow_html=True)
    
    df_inv = kpis.get('inventory', pd.DataFrame())
    
    if df_inv.empty:
        st.info("No inventory data available yet. Waiting for KPI computation...")
        return
    
    # Apply filters
    if filters.get('dc') and filters['dc'] != 'All':
        df_inv = df_inv[df_inv['dc_name'] == filters['dc']]
    if filters.get('sku') and filters['sku'] != 'All':
        df_inv = df_inv[df_inv['product_name'] == filters['sku']]
    
    if df_inv.empty:
        st.info("No data matching selected filters")
        return
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Inventory by DC (stacked by SKU)
        if 'dc_name' in df_inv.columns and 'product_name' in df_inv.columns:
            fig = px.bar(
                df_inv,
                x='dc_name',
                y='current_inventory',
                color='product_name',
                title='Inventory Distribution by Distribution Center',
                labels={'current_inventory': 'Units', 'dc_name': 'Distribution Center'},
                color_discrete_sequence=px.colors.qualitative.Set2,
                barmode='stack'
            )
            fig.update_layout(
                height=400,
                template='plotly_white',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True, key='inv_by_dc')
        else:
            st.info("Missing required columns for this chart")
    
    with col2:
        # Top SKUs by inventory
        if 'product_name' in df_inv.columns:
            top_skus = df_inv.groupby('product_name')['current_inventory'].sum().sort_values(ascending=False).head(10)
            
            fig = go.Figure(data=[go.Bar(
                x=top_skus.values,
                y=top_skus.index,
                orientation='h',
                marker=dict(
                    color=top_skus.values,
                    colorscale=[[0, THEME['primary']], [1, THEME['secondary']]],
                    showscale=False
                ),
                text=top_skus.values,
                textposition='auto'
            )])
            fig.update_layout(
                title='Top 10 SKUs by Inventory Volume',
                xaxis_title='Units',
                height=400,
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True, key='top_skus')
        else:
            st.info("Missing required columns for this chart")
    
    # Inventory table
    st.markdown("### Inventory Details")
    if not df_inv.empty:
        display_cols = ['sku_id', 'product_name', 'dc_name', 'current_inventory', 'safety_stock_level']
        available_cols = [col for col in display_cols if col in df_inv.columns]
        st.dataframe(df_inv[available_cols].sort_values('current_inventory', ascending=False), 
                    use_container_width=True, hide_index=True)

def render_supplier_page(kpis: Dict):
    """Render supplier performance page"""
    st.markdown(f'<div class="section-title">Supplier Performance</div>', unsafe_allow_html=True)
    
    df_supplier = kpis.get('supplier_performance', pd.DataFrame())
    
    if df_supplier.empty:
        st.info("No supplier performance data available yet")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Scatter plot: Lead Time vs Reliability
        df_supplier['reliability_pct'] = df_supplier['reliability_score'] * 100
        
        fig = px.scatter(
            df_supplier,
            x='avg_lead_time_days',
            y='reliability_pct',
            size='shipment_count' if 'shipment_count' in df_supplier.columns else None,
            color='performance_score',
            hover_name='supplier_name' if 'supplier_name' in df_supplier.columns else None,
            title='Supplier Performance Matrix',
            labels={
                'avg_lead_time_days': 'Average Lead Time (days)',
                'reliability_pct': 'Reliability (%)',
                'performance_score': 'Score'
            },
            color_continuous_scale=[[0, THEME['danger']], [0.5, THEME['warning']], [1, THEME['success']]]
        )
        
        # Add reference lines
        fig.add_hline(y=90, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=10, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            height=500,
            template='plotly_white'
        )
        st.plotly_chart(fig, use_container_width=True, key='supplier_scatter')
    
    with col2:
        st.markdown("### Supplier Scorecard")
        
        # Performance grades
        def get_grade(score):
            if score >= 0.9:
                return 'A'
            elif score >= 0.8:
                return 'B'
            elif score >= 0.7:
                return 'C'
            else:
                return 'D'
        
        df_supplier['grade'] = df_supplier['performance_score'].apply(get_grade)
        df_sorted = df_supplier.sort_values('performance_score', ascending=False)
        
        for _, row in df_sorted.iterrows():
            grade_class = 'status-success' if row['grade'] == 'A' else 'status-warning' if row['grade'] == 'B' else 'status-danger'
            supplier_name = row.get('supplier_name', row.get('supplier_id', 'Unknown'))
            
            st.markdown(f"""
            <div class="kpi-card" style="margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong>{supplier_name}</strong>
                    <span class="status-badge {grade_class}">Grade {row['grade']}</span>
                </div>
                <div style="margin-top: 0.5rem; font-size: 0.85rem; color: {THEME['text_secondary']};">
                    Lead Time: {row['avg_lead_time_days']:.1f} days<br>
                    Reliability: {row['reliability_pct']:.1f}%
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_location_page(kpis: Dict):
    """Render DC/location analytics page"""
    st.markdown(f'<div class="section-title">Distribution Center Analytics</div>', unsafe_allow_html=True)
    
    df_dc = kpis.get('dc_utilization', pd.DataFrame())
    df_regional = kpis.get('regional_performance', pd.DataFrame())
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Distribution Center Utilization")
        
        if not df_dc.empty:
            df_dc['utilization_pct'] = df_dc['utilization_rate'] * 100
            df_dc_sorted = df_dc.sort_values('utilization_pct', ascending=False)
            
            for _, row in df_dc_sorted.iterrows():
                util = row['utilization_pct']
                status_class = 'status-danger' if util > 85 else 'status-warning' if util > 75 else 'status-success'
                status_text = 'Critical' if util > 85 else 'High' if util > 75 else 'Normal'
                
                st.markdown(f"""
                <div class="kpi-card" style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>{row['dc_name']}</strong>
                        <span class="status-badge {status_class}">{status_text}</span>
                    </div>
                    <div style="margin-top: 0.75rem;">
                        <div style="font-size: 1.5rem; font-weight: 700; color: {THEME['primary']};">
                            {util:.1f}%
                        </div>
                        <div style="font-size: 0.8rem; color: {THEME['text_secondary']};">Utilization</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No DC utilization data available")
    
    with col2:
        st.markdown("### Regional Performance")
        
        if not df_regional.empty:
            for _, row in df_regional.iterrows():
                region_name = row.get('region_name', row.get('region_id', 'Unknown'))
                revenue = row['total_revenue']
                orders = row.get('total_orders', 0)
                
                st.markdown(f"""
                <div class="kpi-card" style="margin-bottom: 1rem;">
                    <strong>{region_name}</strong>
                    <div style="margin-top: 0.75rem;">
                        <div style="font-size: 1.3rem; font-weight: 700; color: {THEME['success']};">
                            ${revenue:,.0f}
                        </div>
                        <div style="font-size: 0.8rem; color: {THEME['text_secondary']};">
                            {orders:,} orders
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No regional performance data available")

def render_stockout_page(kpis: Dict, filters: Dict):
    """Render stockout risk page"""
    st.markdown(f'<div class="section-title">Stockout Risk Analysis</div>', unsafe_allow_html=True)
    
    df_stockout = kpis.get('stockout_alerts', pd.DataFrame())
    
    if df_stockout.empty:
        st.success("✓ No stockout risks detected. All inventory levels are healthy!")
        return
    
    # Apply filters
    if filters.get('dc') and filters['dc'] != 'All':
        df_stockout = df_stockout[df_stockout['dc_name'] == filters['dc']]
    
    if df_stockout.empty:
        st.info("No stockout risks for selected filters")
        return
    
    # Sort by severity
    df_stockout = df_stockout.sort_values('days_to_stockout')
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Horizontal bar chart
        colors = [THEME['danger'] if d < 3 else THEME['warning'] if d < 5 else THEME['success'] 
                 for d in df_stockout['days_to_stockout']]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_stockout['days_to_stockout'],
            y=df_stockout['product_name'] if 'product_name' in df_stockout.columns else df_stockout['sku_id'],
            orientation='h',
            marker=dict(color=colors),
            text=df_stockout['days_to_stockout'].round(1),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Days to stockout: %{x:.1f}<extra></extra>'
        ))
        
        fig.add_vline(x=7, line_dash="dash", line_color=THEME['warning'], 
                     annotation_text="Warning (7 days)")
        fig.add_vline(x=3, line_dash="dash", line_color=THEME['danger'],
                     annotation_text="Critical (3 days)")
        
        fig.update_layout(
            title='Days to Stockout (sorted by urgency)',
            xaxis_title='Days Until Stockout',
            height=max(400, len(df_stockout) * 25),
            template='plotly_white',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True, key='stockout_bar')
    
    with col2:
        st.markdown("### High-Risk Items")
        
        top_risks = df_stockout.head(15)
        
        for _, row in top_risks.iterrows():
            days = row['days_to_stockout']
            product = row.get('product_name', row.get('sku_id', 'Unknown'))
            dc = row.get('dc_name', row.get('dc_id', 'Unknown'))
            stock = row.get('stock_level', 0)
            demand = row.get('demand_rate_per_day', 0)
            
            if days < 1:
                status_class = 'status-danger'
                status_text = 'CRITICAL'
            elif days < 3:
                status_class = 'status-warning'
                status_text = 'HIGH'
            elif days < 7:
                status_class = 'status-warning'
                status_text = 'MEDIUM'
            else:
                status_class = 'status-success'
                status_text = 'LOW'
            
            # Format demand nicely
            if demand >= 1000:
                demand_str = f"{demand/1000:.1f}K"
            else:
                demand_str = f"{demand:.0f}"
            
            st.markdown(f"""
            <div class="kpi-card" style="margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong>{product}</strong>
                    <span class="status-badge {status_class}">{status_text}</span>
                </div>
                <div style="margin-top: 0.5rem; font-size: 0.85rem; color: {THEME['text_secondary']};">
                    DC: {dc}<br>
                    Stock: <strong>{stock:,.0f}</strong> units<br>
                    Demand: <strong>{demand_str}</strong> units/day<br>
                    <span style="color: {THEME['danger']}; font-weight: 600;">
                    {days:.2f} days until stockout
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Add summary metrics
        if not df_stockout.empty:
            st.markdown("---")
            st.markdown("### Summary")
            critical_count = len(df_stockout[df_stockout['severity'] == 'critical'])
            high_count = len(df_stockout[df_stockout['severity'] == 'high'])
            st.markdown(f"""
            <div style="font-size: 0.9rem;">
                🔴 Critical (< 1 day): <strong>{critical_count}</strong><br>
                🟠 High (1-3 days): <strong>{high_count}</strong><br>
                📊 Total at risk: <strong>{len(df_stockout)}</strong>
            </div>
            """, unsafe_allow_html=True)

# ============================================================
# SIDEBAR & FILTERS
# ============================================================
def render_sidebar(kpis: Dict, redis_client) -> Dict:
    """Render sidebar navigation and filters"""
    with st.sidebar:
        st.markdown("## Navigation")
        
        page = st.radio(
            "Select View",
            ["Overview", "Inventory", "Supplier", "Location / DC", "Stockout Risk"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("## Filters")
        
        # Extract filter options
        df_inv = kpis.get('inventory', pd.DataFrame())
        
        dcs = ['All']
        skus = ['All']
        categories = ['All']
        
        if not df_inv.empty:
            if 'dc_name' in df_inv.columns:
                dcs += sorted(df_inv['dc_name'].dropna().unique().tolist())
            if 'product_name' in df_inv.columns:
                skus += sorted(df_inv['product_name'].dropna().unique().tolist())
            if 'category' in df_inv.columns:
                categories += sorted(df_inv['category'].dropna().unique().tolist())
        
        filters = {
            'page': page,
            'dc': st.selectbox("Distribution Center", dcs, key='filter_dc'),
            'sku': st.selectbox("SKU / Product", skus, key='filter_sku'),
            'category': st.selectbox("Category", categories, key='filter_category')
        }
        
        st.markdown("---")
        
        # Debug panel toggle
        render_debug_panel(redis_client)
        
        st.markdown("---")
        st.markdown("## About")
        st.info("""
        **Supply Chain Analytics**
        
        Real-time monitoring powered by:
        - Apache Spark
        - Redis Cache
        - MongoDB
        
        Auto-refresh: 60s
        """)
    
    return filters

# ============================================================
# MAIN APPLICATION WITH ERROR HANDLING
# ============================================================
def main():
    """Main application with comprehensive error handling"""
    
    try:
        # Inject CSS
        inject_custom_css()
        
        # Initialize Redis
        redis_client = get_redis_connection()
        
        if not redis_client:
            st.error("❌ Cannot connect to Redis. Please ensure Redis container is running.")
            st.code("docker ps | grep redis", language='bash')
            st.stop()
        
        # Load KPIs with normalization
        kpis = load_kpis(redis_client)
        
        # Check data availability
        has_data = any([
            not kpis.get('inventory', pd.DataFrame()).empty,
            not kpis.get('supplier_performance', pd.DataFrame()).empty,
            not kpis.get('dc_utilization', pd.DataFrame()).empty
        ])
        
        if not has_data:
            st.warning("⚠️ No KPI data available. Waiting for Spark to compute KPIs...")
            st.info("💡 This usually takes 1-2 minutes after system startup. The page will auto-refresh.")
            
            with st.expander("Troubleshooting"):
                st.markdown("""
                **Check if services are running:**
                ```bash
                docker ps
                ```
                
                **Check Spark job logs:**
                ```bash
                docker logs airflow | grep "compute_kpis"
                ```
                
                **Check Redis keys:**
                ```bash
                docker exec redis redis-cli KEYS "kpi:*"
                ```
                """)
            
            # Still show sidebar debug panel
            with st.sidebar:
                render_debug_panel(redis_client)
            
            time.sleep(60)
            st.rerun()
            return
        
        # Calculate data freshness
        last_update = kpis.get('last_update')
        data_freshness = 'Unknown'
        
        if last_update:
            try:
                if isinstance(last_update, str):
                    dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    age_seconds = (datetime.now(dt.tzinfo) - dt).total_seconds()
                    data_freshness = 'Fresh' if age_seconds < 120 else 'Stale'
            except:
                pass
        
        # Render sidebar and get filters
        filters = render_sidebar(kpis, redis_client)
        
        # Render header
        render_header(last_update, data_freshness)
        
        # Render KPI cards
        render_kpi_cards(kpis)
        
        st.markdown("---")
        
        # Render selected page
        page = filters.get('page', 'Overview')
        
        if page == 'Overview':
            render_overview_page(kpis, filters)
        elif page == 'Inventory':
            render_inventory_page(kpis, filters)
        elif page == 'Supplier':
            render_supplier_page(kpis)
        elif page == 'Location / DC':
            render_location_page(kpis)
        elif page == 'Stockout Risk':
            render_stockout_page(kpis, filters)
        
    except Exception as e:
        st.error("❌ An unexpected error occurred")
        
        with st.expander("Show error details", expanded=False):
            st.code(traceback.format_exc())
            st.markdown("**Error:** " + str(e))
        
        st.info("The dashboard will auto-refresh in 60 seconds")

# ============================================================
# ENTRY POINT WITH AUTO-REFRESH
# ============================================================
if __name__ == "__main__":
    main()
    
    # Auto-refresh
    time.sleep(60)
    st.rerun()

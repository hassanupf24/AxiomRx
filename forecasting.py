import pandas as pd
import numpy as np
import xgboost as xgb
import logging
from datetime import timedelta, date
from database import get_db_connection

logger = logging.getLogger(__name__)

def fetch_sales_training_data() -> pd.DataFrame:
    """Extracts time-series sales data aggregating sold quantities per ProductID daily."""
    query = """
        SELECT 
            DATE(s.Timestamp) as sale_date,
            sd.ProductID,
            SUM(sd.Quantity) as total_qty
        FROM Sales s
        JOIN SalesDetails sd ON s.TransactionID = sd.TransactionID
        GROUP BY DATE(s.Timestamp), sd.ProductID
        ORDER BY sd.ProductID, sale_date ASC
    """
    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def fetch_current_inventory() -> pd.DataFrame:
    """Extracts core inventory layout."""
    query = "SELECT ID as ProductID, Name, StockQuantity, ReorderLevel FROM Products"
    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """Create local statistical and time-series features."""
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    df = df.sort_values(by=['ProductID', 'sale_date'])
    
    # Extract day of the week and month
    df['day_of_week'] = df['sale_date'].dt.dayofweek
    df['month'] = df['sale_date'].dt.month
    
    # Calculate a 7-day rolling sales average per product
    df['rolling_avg_7d'] = df.groupby('ProductID')['total_qty'].transform(
        lambda x: x.rolling(window=7, min_periods=1).mean()
    )
    
    return df

def train_and_localize_model(df: pd.DataFrame, forecast_days: int) -> pd.DataFrame:
    """Train a standalone XGBoost regression model and forecast demand."""
    if df.empty or len(df) < 3:
        # Insufficient data to train; skip modeling
        return pd.DataFrame()
        
    features = ['ProductID', 'day_of_week', 'month', 'rolling_avg_7d']
    target = 'total_qty'
    
    X_train = df[features]
    y_train = df[target]
    
    # Train lightweight localized model
    model = xgb.XGBRegressor(
        n_estimators=100, 
        max_depth=3, 
        objective='reg:squarederror', 
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Perform Inference for the future timeframe
    future_records = []
    last_known_dates = df.groupby('ProductID')['sale_date'].max()
    product_ids = df['ProductID'].unique()
    
    for pid in product_ids:
        # Get the most recent rolling average feature data
        recent_data = df[df['ProductID'] == pid]
        last_rolling = recent_data['rolling_avg_7d'].iloc[-1]
        
        last_date = last_known_dates.loc[pid]
        
        for day_offset in range(1, forecast_days + 1):
            target_date = last_date + pd.Timedelta(days=day_offset)
            future_records.append({
                'ProductID': pid,
                'target_date': target_date,
                'day_of_week': target_date.dayofweek,
                'month': target_date.month,
                'rolling_avg_7d': last_rolling # Assumption: rolling avg is steady state across local window
            })
            
    future_df = pd.DataFrame(future_records)
    X_pred = future_df[['ProductID', 'day_of_week', 'month', 'rolling_avg_7d']]
    
    # Run Inference
    predictions = model.predict(X_pred)
    future_df['predicted_qty'] = np.maximum(0, np.round(predictions)) # Cannot have negative demand
    
    return future_df

def generate_smart_restock_list(forecast_horizon_days=14) -> list[dict]:
    """Execute AI Forecasting pipeline and return items for the Smart Restock UI."""
    sales_df = fetch_sales_training_data()
    inventory_df = fetch_current_inventory()
    
    if sales_df.empty:
        return [] # No sales history exists to regress against
        
    engineered_df = feature_engineering(sales_df)
    predictions_df = train_and_localize_model(engineered_df, forecast_horizon_days)
    
    if predictions_df.empty:
        return []
        
    # Aggregate total predicted 14/30-day demand per Product
    agg_pred = predictions_df.groupby('ProductID')['predicted_qty'].sum().reset_index()
    
    # Merge with inventory database
    merged = pd.merge(inventory_df, agg_pred, on='ProductID', how='left')
    merged['predicted_qty'] = merged['predicted_qty'].fillna(0)
    
    restock_list = []
    for _, row in merged.iterrows():
        projected_stock = row['StockQuantity'] - row['predicted_qty']
        
        # Determine if predicted depletion trips our offline reorder threshold
        if projected_stock <= row['ReorderLevel']:
            restock_list.append({
                'ProductID': row['ProductID'],
                'Name': row['Name'],
                'CurrentStock': row['StockQuantity'],
                'ReorderLevel': row['ReorderLevel'],
                'PredictedDemand': int(row['predicted_qty']),
                'ProjectedStock': int(projected_stock)
            })
            
    # Sort strictly by priority (highest projected deficit negative values)
    restock_list = sorted(restock_list, key=lambda x: x['ProjectedStock'])
    return restock_list

"""
Machine Learning Engine for Requiva
Predictive analytics for lab order management
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')


def predict_reorder_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    Predict when items need to be reordered based on usage patterns.
    Uses time-series analysis of order frequency.
    """
    if df.empty or 'ITEM' not in df.columns:
        return pd.DataFrame()
    
    # Calculate order frequency for each item
    df['DATE_ORDERED_DT'] = pd.to_datetime(df['DATE ORDERED'], errors='coerce')
    df_sorted = df.sort_values('DATE_ORDERED_DT')
    
    reorder_predictions = []
    
    for item in df['ITEM'].unique():
        item_df = df_sorted[df_sorted['ITEM'] == item].copy()
        
        if len(item_df) < 2:
            continue
        
        # Calculate average days between orders
        item_df['days_diff'] = item_df['DATE_ORDERED_DT'].diff().dt.days
        avg_days = item_df['days_diff'].mean()
        
        if pd.isna(avg_days):
            continue
        
        # Get last order date
        last_order = item_df['DATE_ORDERED_DT'].max()
        
        # Predict next order date
        predicted_date = last_order + timedelta(days=avg_days)
        days_until = (predicted_date - datetime.now()).days
        
        # Get average quantity and vendor
        avg_qty = item_df['NUMBER OF ITEM'].mean()
        common_vendor = item_df['VENDOR'].mode()[0] if not item_df['VENDOR'].empty else "Unknown"
        
        reorder_predictions.append({
            'ITEM': item,
            'PREDICTED_REORDER_DATE': predicted_date.strftime('%Y-%m-%d'),
            'DAYS_UNTIL_REORDER': max(0, days_until),
            'AVG_QUANTITY': round(avg_qty, 1),
            'RECOMMENDED_VENDOR': common_vendor,
            'ORDER_FREQUENCY_DAYS': round(avg_days, 1)
        })
    
    result = pd.DataFrame(reorder_predictions)
    
    if not result.empty:
        result = result.sort_values('DAYS_UNTIL_REORDER')
        result['URGENCY'] = result['DAYS_UNTIL_REORDER'].apply(
            lambda x: '🔴 Urgent' if x <= 7 else ('🟡 Soon' if x <= 30 else '🟢 Normal')
        )
    
    return result


def forecast_spending(df: pd.DataFrame, months: int = 3) -> dict:
    """
    Forecast lab spending for the next N months using time series analysis.
    Includes grant-level breakdown.
    """
    if df.empty or 'TOTAL' not in df.columns:
        return {}
    
    df['DATE_ORDERED_DT'] = pd.to_datetime(df['DATE ORDERED'], errors='coerce')
    df = df.dropna(subset=['DATE_ORDERED_DT', 'TOTAL'])
    
    # Group by month
    df['YEAR_MONTH'] = df['DATE_ORDERED_DT'].dt.to_period('M')
    monthly_spending = df.groupby('YEAR_MONTH')['TOTAL'].sum()
    
    if len(monthly_spending) < 2:
        return {
            'total_forecast': df['TOTAL'].sum(),
            'monthly_avg': df['TOTAL'].mean(),
            'dates': [],
            'amounts': []
        }
    
    # Simple moving average for forecast
    window = min(3, len(monthly_spending))
    ma = monthly_spending.rolling(window=window).mean()
    avg_monthly = ma.iloc[-1] if not ma.empty else monthly_spending.mean()
    
    # Generate forecast dates
    last_date = monthly_spending.index[-1].to_timestamp()
    forecast_dates = [last_date + pd.DateOffset(months=i+1) for i in range(months)]
    forecast_amounts = [avg_monthly] * months
    
    # Calculate trend
    if len(monthly_spending) >= 3:
        recent_values = monthly_spending.tail(3).values
        trend = (recent_values[-1] - recent_values[0]) / 3
        forecast_amounts = [avg_monthly + (trend * i) for i in range(1, months+1)]
    
    # Grant-level breakdown
    grant_spending = {}
    if 'GRANT USED' in df.columns:
        grants = df[df['GRANT USED'].notna()].groupby('GRANT USED')['TOTAL'].sum()
        grant_spending = grants.to_dict()
    
    return {
        'total_forecast': sum(forecast_amounts),
        'monthly_avg': avg_monthly,
        'dates': [d.strftime('%Y-%m') for d in forecast_dates],
        'amounts': forecast_amounts,
        'by_grant': grant_spending
    }


def detect_anomalies(df: pd.DataFrame, new_order: dict = None) -> pd.DataFrame:
    """
    Detect anomalous orders using Isolation Forest.
    Flags unusual prices, quantities, or patterns.
    """
    if df.empty or 'TOTAL' not in df.columns:
        return pd.DataFrame()
    
    # Prepare features for anomaly detection
    df_clean = df.copy()
    df_clean = df_clean[df_clean['TOTAL'] > 0].copy()
    
    if len(df_clean) < 10:
        return pd.DataFrame()
    
    # Extract numeric features
    features = df_clean[['NUMBER OF ITEM', 'AMOUNT PER ITEM', 'TOTAL']].copy()
    features = features.replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(features) < 10:
        return pd.DataFrame()
    
    # Normalize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    # Train Isolation Forest
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    predictions = iso_forest.fit_predict(features_scaled)
    scores = iso_forest.score_samples(features_scaled)
    
    # Normalize scores to 0-1 (higher = more anomalous)
    scores_normalized = 1 - ((scores - scores.min()) / (scores.max() - scores.min()))
    
    # Flag anomalies
    df_clean['ANOMALY'] = predictions == -1
    df_clean['ANOMALY_SCORE'] = scores_normalized
    
    anomalies = df_clean[df_clean['ANOMALY']].copy()
    
    # If checking a new order
    if new_order and 'TOTAL' in new_order:
        new_features = np.array([[
            new_order.get('NUMBER OF ITEM', 0),
            new_order.get('AMOUNT PER ITEM', 0),
            new_order.get('TOTAL', 0)
        ]])
        new_features_scaled = scaler.transform(new_features)
        new_score = iso_forest.score_samples(new_features_scaled)[0]
        new_score_normalized = 1 - ((new_score - scores.min()) / (scores.max() - scores.min()))
        return new_score_normalized
    
    return anomalies[['REQ#', 'ITEM', 'VENDOR', 'TOTAL', 'ANOMALY_SCORE']].sort_values('ANOMALY_SCORE', ascending=False)


def recommend_vendors(df: pd.DataFrame) -> dict:
    """
    Recommend best vendors for each item based on:
    - Historical pricing
    - Order frequency
    - Reliability (successful deliveries)
    """
    if df.empty or 'VENDOR' not in df.columns:
        return {}
    
    recommendations = {}
    
    for item in df['ITEM'].unique():
        item_df = df[df['ITEM'] == item].copy()
        
        if len(item_df) < 2:
            continue
        
        # Calculate metrics per vendor
        vendor_stats = item_df.groupby('VENDOR').agg({
            'AMOUNT PER ITEM': 'mean',
            'REQ#': 'count',
            'DATE RECEIVED': lambda x: x.notna().sum()
        }).reset_index()
        
        vendor_stats.columns = ['VENDOR', 'AVG_PRICE', 'ORDER_COUNT', 'DELIVERED_COUNT']
        vendor_stats['RELIABILITY'] = vendor_stats['DELIVERED_COUNT'] / vendor_stats['ORDER_COUNT']
        
        # Score vendors (lower price + higher reliability = better)
        vendor_stats['SCORE'] = (
            (1 - (vendor_stats['AVG_PRICE'] - vendor_stats['AVG_PRICE'].min()) / 
             (vendor_stats['AVG_PRICE'].max() - vendor_stats['AVG_PRICE'].min() + 1)) * 0.6 +
            vendor_stats['RELIABILITY'] * 0.4
        )
        
        # Get top 3 vendors
        top_vendors = vendor_stats.nlargest(3, 'SCORE')['VENDOR'].tolist()
        recommendations[item] = top_vendors
    
    return recommendations


def forecast_demand(df: pd.DataFrame, item: str = None, days_ahead: int = 90) -> dict:
    """
    Forecast demand for specific items or overall lab consumption.
    Uses simple exponential smoothing.
    """
    if df.empty:
        return {}
    
    df['DATE_ORDERED_DT'] = pd.to_datetime(df['DATE ORDERED'], errors='coerce')
    df = df.dropna(subset=['DATE_ORDERED_DT'])
    
    if item:
        df = df[df['ITEM'] == item]
    
    # Group by week
    df['WEEK'] = df['DATE_ORDERED_DT'].dt.to_period('W')
    weekly_orders = df.groupby('WEEK').size()
    
    if len(weekly_orders) < 4:
        return {'message': 'Insufficient data for demand forecasting'}
    
    # Simple exponential smoothing
    alpha = 0.3
    forecast = [weekly_orders.iloc[0]]
    
    for i in range(1, len(weekly_orders)):
        forecast.append(alpha * weekly_orders.iloc[i] + (1 - alpha) * forecast[-1])
    
    # Predict future weeks
    weeks_ahead = days_ahead // 7
    future_forecast = [forecast[-1]] * weeks_ahead
    
    return {
        'current_weekly_avg': round(forecast[-1], 2),
        'predicted_total': round(sum(future_forecast), 0),
        'trend': 'increasing' if forecast[-1] > forecast[0] else 'decreasing'
    }


def get_bulk_opportunities(df: pd.DataFrame) -> dict:
    """
    Identify items that could benefit from bulk ordering.
    Based on order frequency and price per unit.
    """
    if df.empty or 'ITEM' not in df.columns:
        return {}
    
    opportunities = {}
    
    for item in df['ITEM'].unique():
        item_df = df[df['ITEM'] == item].copy()
        
        if len(item_df) < 3:
            continue
        
        # Calculate metrics
        total_qty = item_df['NUMBER OF ITEM'].sum()
        avg_order_qty = item_df['NUMBER OF ITEM'].mean()
        order_count = len(item_df)
        avg_price = item_df['AMOUNT PER ITEM'].mean()
        
        # Estimate bulk discount (assume 10% for orders 3x average)
        suggested_qty = avg_order_qty * 3
        potential_savings = suggested_qty * avg_price * 0.1
        
        # Only recommend if significant savings
        if potential_savings > 100 and order_count >= 3:
            opportunities[item] = {
                'current_avg_qty': round(avg_order_qty, 1),
                'suggested_qty': round(suggested_qty, 1),
                'order_frequency': order_count,
                'potential_savings': potential_savings,
                'estimated_discount': '10%'
            }
    
    return dict(sorted(opportunities.items(), key=lambda x: x[1]['potential_savings'], reverse=True))


def train_ml_models(df: pd.DataFrame):
    """
    Pre-train ML models when historical data is loaded.
    This improves prediction speed.
    """
    if df.empty or len(df) < 50:
        return None
    
    # Train anomaly detector
    features = df[['NUMBER OF ITEM', 'AMOUNT PER ITEM', 'TOTAL']].copy()
    features = features.replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(features) >= 50:
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(features_scaled)
        
        return {'scaler': scaler, 'model': model}
    
    return None

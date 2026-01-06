# Requiva ML Update - Deployment Instructions

## Changes Made

### Bug Fixes
1. Session state persistence - No logout after adding orders
2. Form handling - Prevents automatic page reloads
3. Error handling - Better Firebase connection management
4. Authentication - Maintained login state across operations

### Machine Learning Features
1. Predictive Reordering - Forecasts reorder dates based on usage patterns
2. Spending Forecast - 3-12 month spending predictions with grant breakdown
3. Anomaly Detection - Flags unusual orders automatically
4. Vendor Recommendations - Suggests best vendors based on historical data
5. Bulk Opportunities - Identifies cost-saving bulk order possibilities

## Files Modified

### Updated Files
- app.py - Integrated ML features and fixed session bugs
- utils.py - Fixed authentication issues
- requirements.txt - Added scikit-learn, numpy, scipy

### New Files
- ml_engine.py - All ML models and prediction logic

## Deployment to Render

### Step 1: Update Local Files

Replace these files in your Requiva project:
- app.py
- utils.py  
- requirements.txt

Add this new file:
- ml_engine.py

### Step 2: Test Locally (Optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Test checklist:
- Login functionality
- Add order without logout
- ML Insights tab appears
- Predictions display (need 10+ orders)

### Step 3: Deploy

```bash
git add .
git commit -m "Add ML features and fix session state bug"
git push origin main
```

Render will automatically redeploy in 2-3 minutes.

## Machine Learning Feature Details

### Predictive Reordering

Analyzes order frequency per item and predicts next reorder date.

Requirements: At least 2 orders per item

Output includes:
- Predicted reorder date
- Days until reorder needed
- Recommended quantity
- Suggested vendor
- Urgency classification

### Spending Forecast

Projects future spending based on historical trends.

Requirements: At least 10 orders across 2+ months

Output includes:
- Total predicted spending
- Monthly average
- Trend direction
- Grant-level breakdown

### Anomaly Detection

Uses Isolation Forest algorithm to identify unusual orders.

Requirements: 10 orders minimum, 50+ for best accuracy

Flags orders with:
- Unusual pricing (significantly higher/lower)
- Abnormal quantities
- Atypical patterns

### Vendor Recommendations

Scores vendors on price and reliability.

Requirements: At least 2 orders per item from different vendors

Scoring factors:
- Average price (60% weight)
- Delivery success rate (40% weight)

### Bulk Opportunities

Identifies items suitable for bulk ordering.

Requirements: At least 3 orders per item

Calculations:
- Suggests 3x average order quantity
- Assumes 10% bulk discount
- Shows potential savings

## Data Requirements

| Feature | Minimum Orders | Optimal Data |
|---------|---------------|--------------|
| Reorder Prediction | 10 total, 2 per item | 30+ per item |
| Spending Forecast | 10 total | 50+ across 3+ months |
| Anomaly Detection | 10 total | 50+ for accuracy |
| Vendor Recommendations | 10 total, 2 per item | 20+ per vendor |
| Bulk Opportunities | 10 total, 3 per item | 30+ per item |

With 3 years of historical data, all features will perform optimally.

## Loading Historical Data

### Option 1: CSV Upload
Format data with required columns and upload through app

### Option 2: Direct Firestore Upload
Use Firebase console or script to bulk upload historical orders

Required columns:
- REQ#
- ITEM
- NUMBER OF ITEM
- AMOUNT PER ITEM
- TOTAL
- VENDOR
- CAT #
- GRANT USED
- PO SOURCE
- PO #
- NOTES
- ORDERED BY
- DATE ORDERED
- DATE RECEIVED
- RECEIVED BY
- ITEM LOCATION
- LAB

## Troubleshooting

### Still Logging Out After Orders
- Clear browser cache
- Verify st.rerun() is used (not st.experimental_rerun())
- Check session state initialization

### ML Tab Shows "Need More Data"
- Requires at least 10 orders
- Load historical data
- Features activate automatically once threshold met

### Firebase Connection Error
- Verify secrets.toml has correct credentials
- Check Firestore database exists
- Confirm Render environment variables set

### Predictions Seem Inaccurate
- Requires sufficient historical data
- Check data quality (valid dates, prices)
- Accuracy improves over time with more data

## Testing Checklist

### Basic Functionality
- [ ] Login works
- [ ] Create account works
- [ ] Add order without logout
- [ ] View orders table
- [ ] Filter by vendor/grant
- [ ] Export to CSV/Excel

### ML Features (Need 10+ orders)
- [ ] Reorder predictions display
- [ ] Spending forecast shows
- [ ] Anomaly detection runs
- [ ] Vendor recommendations appear
- [ ] Bulk opportunities listed

## Contact

For issues or questions:
Email: ogunbowaleadeola@gmail.com

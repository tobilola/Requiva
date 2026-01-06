# Requiva - Lab Order Management System

Laboratory order tracking platform with machine learning predictions for research teams. Manages consumables, purchase orders, and generates audit-ready reports with secure authentication and real-time data synchronization.

## Features

### Core Functionality
- Secure authentication with account creation
- Multi-lab order tracking
- Grant and vendor filtering
- Receipt confirmation workflow
- CSV and Excel export
- Admin access controls

### Machine Learning Capabilities
- **Predictive Reordering** - Forecasts when items need reordering based on usage patterns
- **Spending Forecast** - Projects monthly and quarterly spending with grant-level breakdown
- **Anomaly Detection** - Identifies unusual orders (price spikes, quantity outliers)
- **Vendor Recommendations** - Suggests optimal vendors based on price and reliability
- **Bulk Opportunities** - Identifies items suitable for bulk ordering with cost savings

## Technology Stack

- **Frontend:** Streamlit
- **Backend:** Firebase Authentication, Firestore Database
- **Data Processing:** Pandas, NumPy
- **Machine Learning:** Scikit-learn (Isolation Forest, Random Forest)
- **Visualization:** Matplotlib
- **Export:** OpenPyXL, XlsxWriter

## Installation

Clone the repository:
```bash
git clone https://github.com/tobilola/requiva.git
cd requiva
pip install -r requirements.txt
```

Configure Firebase credentials in `.streamlit/secrets.toml`

Run the application:
```bash
streamlit run app.py
```

## Machine Learning Models

### Reorder Prediction
- Algorithm: Time-series analysis of order frequency
- Output: Predicted reorder date with urgency classification

### Spending Forecast
- Algorithm: Moving average with trend analysis
- Output: Multi-month spending projections with grant breakdown

### Anomaly Detection
- Algorithm: Isolation Forest
- Output: Anomaly scores for flagging unusual patterns

### Vendor Recommendations
- Algorithm: Multi-factor scoring (price, reliability)
- Output: Top 3 recommended vendors per item

### Bulk Opportunities
- Algorithm: Order frequency and volume analysis
- Output: Suggested bulk quantities with savings estimates

## Deployment

Configured for deployment on Render or Streamlit Cloud.

## Author

Tobilola Ogunbowale  
Email: ogunbowaleadeola@gmail.com  
GitHub: https://github.com/tobilola

"""Sales and Revenue Forecasting module for IntelliOps.

Use-case identifier: sales_revenue_forecasting
Endpoint: POST /api/v1/predict/sales_revenue_forecasting
"""

from modules.sales_revenue_forecasting.service import forecast_sales_revenue

__all__ = ["forecast_sales_revenue"]

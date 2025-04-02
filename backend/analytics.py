from fastapi import APIRouter, HTTPException
import pandas as pd
from datetime import datetime
import plotly.express as px
from fastapi.responses import JSONResponse
import logging
from data_gen import engine  # using shared engine from rag module

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/analytics")
async def generate_analytics():
    try:
        df = pd.read_sql("SELECT * FROM hotel_bookings", con=engine)
        if df.empty:
            return JSONResponse(content={"error": "No data found"}, status_code=404)
        
        # Revenue Trends Chart
        revenue_df = df.groupby(['arrival_date_year', 'arrival_date_month'])['revenue'] \
                      .sum().reset_index().rename(columns={'revenue': 'total_revenue'})
        revenue_df['date'] = revenue_df.apply(
            lambda x: datetime(x['arrival_date_year'],
                               datetime.strptime(x['arrival_date_month'], '%B').month,
                               1), axis=1)
        revenue_df = revenue_df.sort_values('date')
        fig1 = px.line(revenue_df, x='date', y='total_revenue', markers=True,
                       title="Revenue Trends Over Time", labels={"date": "Date", "total_revenue": "Total Revenue (€)"})
        
        # Cancellation Rate Chart
        cancel_df = df.groupby(['arrival_date_year', 'arrival_date_month']) \
                      .agg(total_bookings=('is_canceled', 'count'),
                           cancellations=('is_canceled', 'sum')).reset_index()
        cancel_df['cancellation_rate'] = (cancel_df['cancellations'] / cancel_df['total_bookings']) * 100
        cancel_df['date'] = cancel_df.apply(
            lambda x: datetime(x['arrival_date_year'],
                               datetime.strptime(x['arrival_date_month'], '%B').month,
                               1), axis=1)
        cancel_df = cancel_df.sort_values('date')
        fig2 = px.line(cancel_df, x='date', y='cancellation_rate', markers=True,
                       title="Cancellation Rate Over Time", labels={"date": "Date", "cancellation_rate": "Cancellation Rate (%)"})
        
        # Geographical Distribution Chart
        country_dist = df['country'].value_counts().nlargest(10)
        geo_df = pd.DataFrame({'country': country_dist.index, 'bookings': country_dist.values})
        fig3 = px.bar(geo_df, x='bookings', y='country', orientation='h',
                      title="Top 10 Countries by Booking Count", labels={'bookings': 'Number of Bookings', 'country': 'Country Code'})
        
        # Lead Time Chart
        lead_df = df.groupby(['arrival_date_year', 'arrival_date_month'])['lead_time'] \
                   .mean().reset_index().rename(columns={'lead_time': 'avg_lead_time'})
        lead_df['date'] = lead_df.apply(
            lambda x: datetime(x['arrival_date_year'],
                               datetime.strptime(x['arrival_date_month'], '%B').month,
                               1), axis=1)
        lead_df = lead_df.sort_values('date')
        fig4 = px.line(lead_df, x='date', y='avg_lead_time', markers=True,
                       title="Average Booking Lead Time Over Time", labels={'date': 'Date', 'avg_lead_time': 'Average Lead Time (Days)'})
        
        # ADR Distribution Chart
        fig5 = px.box(df, x='hotel', y='adr', title="ADR Distribution by Hotel Type",
                      labels={'hotel': 'Hotel Type', 'adr': 'Average Daily Rate (€)'}, color='hotel')
        
        # Stay Duration Chart
        df['total_stay'] = df['stays_in_week_nights'] + df['stays_in_weekend_nights']
        stay_df = df.groupby('hotel')[['stays_in_week_nights', 'stays_in_weekend_nights']].mean().reset_index()
        fig6 = px.bar(stay_df, x='hotel', y=['stays_in_week_nights', 'stays_in_weekend_nights'],
                      title="Average Stay Duration by Hotel Type",
                      labels={'value': 'Average Nights', 'hotel': 'Hotel Type'}, barmode='stack')
        
        # Monthly Booking Trends Chart
        month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        monthly_bookings = df.groupby('arrival_date_month').size().reindex(month_order, fill_value=0).reset_index()
        monthly_bookings.columns = ['month', 'bookings']
        fig7 = px.bar(monthly_bookings, x='month', y='bookings',
                      title="Monthly Booking Trends", labels={'month': 'Month', 'bookings': 'Number of Bookings'})
        
        return {
            "revenue_trend": fig1.to_json(),
            "cancellation_rate": fig2.to_json(),
            "geographical_dist": fig3.to_json(),
            "lead_time_dist": fig4.to_json(),
            "adr_distribution": fig5.to_json(),
            "stay_duration": fig6.to_json(),
            "monthly_trends": fig7.to_json()
        }
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

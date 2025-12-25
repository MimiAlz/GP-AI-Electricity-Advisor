import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Power Consumption Analytics Dashboard",
    layout="wide"
)

st.title("⚡ Power Consumption Analytics Dashboard")

# -----------------------------
# Mock Data Generators
# -----------------------------
def generate_time_series(start, end, freq="15min"):
    return pd.date_range(start=start, end=end, freq=freq)

def generate_house_data(house_id, start, end):
    time_index = generate_time_series(start, end)

    aggregate = np.random.uniform(0.5, 5.0, size=len(time_index))

    loads = {
        "HVAC": aggregate * np.random.uniform(0.3, 0.5),
        "Lighting": aggregate * np.random.uniform(0.1, 0.2),
        "Appliances": aggregate * np.random.uniform(0.2, 0.3),
        "Other": aggregate * np.random.uniform(0.05, 0.15),
    }

    df = pd.DataFrame({"timestamp": time_index, "aggregate": aggregate})
    for load, values in loads.items():
        df[load] = values

    return df

def generate_forecast(df, horizon_hours=24):
    last_time = df["timestamp"].iloc[-1]
    future_index = pd.date_range(
        start=last_time + timedelta(minutes=15),
        periods=horizon_hours * 4,
        freq="15min"
    )

    forecast_values = df["aggregate"].iloc[-1] + np.cumsum(
        np.random.normal(0, 0.05, size=len(future_index))
    )

    forecast_df = pd.DataFrame({
        "timestamp": future_index,
        "forecast": forecast_values
    })

    return forecast_df

def generate_area_data(area_id, start, end):
    time_index = generate_time_series(start, end)
    aggregate = np.random.uniform(50, 200, size=len(time_index))

    return pd.DataFrame({
        "timestamp": time_index,
        "aggregate": aggregate
    })

# -----------------------------
# Sidebar Controls
# -----------------------------
st.sidebar.header("🔧 Controls")

section = st.sidebar.radio(
    "Select Analysis Type",
    [
        "House Load Disaggregation",
        "House Consumption Forecast",
        "Area Consumption Forecast"
    ]
)

start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=7))
end_date = st.sidebar.date_input("End Date", datetime.now())

# -----------------------------
# Section 1: House-level Disaggregation
# -----------------------------
if section == "House Load Disaggregation":
    st.subheader("🏠 House-Level Load Disaggregation")

    house_id = st.sidebar.selectbox(
        "Select House/Customer ID",
        ["House_001", "House_002", "House_003"]
    )

    df = generate_house_data(house_id, start_date, end_date)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name="Aggregate",
        line=dict(width=3)
    ))

    for load in ["HVAC", "Lighting", "Appliances", "Other"]:
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df[load],
            name=load,
            stackgroup=None
        ))

    fig.update_layout(
        title=f"Aggregate vs Individual Loads – {house_id}",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Section 2: House-level Forecast
# -----------------------------
elif section == "House Consumption Forecast":
    st.subheader("📈 House-Level Consumption Forecast")

    house_id = st.sidebar.selectbox(
        "Select House/Customer ID",
        ["House_001", "House_002", "House_003"]
    )

    df = generate_house_data(house_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name="Historical Consumption"
    ))

    fig.add_trace(go.Scatter(
        x=forecast_df["timestamp"],
        y=forecast_df["forecast"],
        name="Forecast",
        line=dict(dash="dash")
    ))

    fig.update_layout(
        title=f"Historical and Forecasted Consumption – {house_id}",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Section 3: Area-level Forecast
# -----------------------------
elif section == "Area Consumption Forecast":
    st.subheader("🌍 Area-Level Consumption Forecast")

    area_id = st.sidebar.selectbox(
        "Select Area",
        ["Area_A", "Area_B", "Area_C"]
    )

    df = generate_area_data(area_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name="Historical Area Consumption"
    ))

    fig.add_trace(go.Scatter(
        x=forecast_df["timestamp"],
        y=forecast_df["forecast"],
        name="Forecast",
        line=dict(dash="dash")
    ))

    fig.update_layout(
        title=f"Historical and Forecasted Consumption – {area_id}",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

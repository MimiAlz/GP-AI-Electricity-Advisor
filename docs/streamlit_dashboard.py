import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import streamlit_authenticator as stauth

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Power Consumption Dashboard",
    layout="wide"
)

# -------------------------------------------------
# Authentication config (FIXED)
# -------------------------------------------------
hashed_passwords = stauth.Hasher().hash_passwords(
    ["admin123", "user123"]
)

credentials = {
    "usernames": {
        "admin": {
            "name": "Admin User",
            "password": hashed_passwords[0]
        },
        "user1": {
            "name": "House User",
            "password": hashed_passwords[1]
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="power_dashboard",
    key="auth",
    cookie_expiry_days=1
)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
name, authentication_status, username = authenticator.login(
    "Login",
    location="main"
)

if authentication_status:
    st.session_state.authenticated = True
    st.session_state.username = username
    st.session_state.name = name
    st.success(f"Welcome {name}")

elif authentication_status is False:
    st.error("Username/password is incorrect")
    st.stop()

elif authentication_status is None:
    st.info("Please enter your username and password")
    st.stop()

# -------------------------------------------------
# LOGOUT
# -------------------------------------------------
authenticator.logout("Logout", "sidebar")

# -------------------------------------------------
# Title
# -------------------------------------------------
st.title("⚡ Power Consumption Analytics Dashboard")

# -------------------------------------------------
# Mock Data Generators
# -------------------------------------------------
def generate_time_series(start, end, freq="15min"):
    return pd.date_range(start=start, end=end, freq=freq)

def generate_house_data(house_id, start, end):
    time_index = generate_time_series(start, end)
    aggregate = np.random.uniform(0.5, 5.0, len(time_index))

    df = pd.DataFrame({
        "timestamp": time_index,
        "aggregate": aggregate,
        "HVAC": aggregate * np.random.uniform(0.3, 0.5),
        "Lighting": aggregate * np.random.uniform(0.1, 0.2),
        "Appliances": aggregate * np.random.uniform(0.2, 0.3),
        "Other": aggregate * np.random.uniform(0.05, 0.15)
    })
    return df

def generate_area_data(area_id, start, end):
    time_index = generate_time_series(start, end)
    aggregate = np.random.uniform(50, 200, len(time_index))
    return pd.DataFrame({
        "timestamp": time_index,
        "aggregate": aggregate
    })

def generate_forecast(df, horizon_hours=24):
    last_time = df["timestamp"].iloc[-1]
    future_index = pd.date_range(
        start=last_time + timedelta(minutes=15),
        periods=horizon_hours * 4,
        freq="15min"
    )

    forecast = df["aggregate"].iloc[-1] + np.cumsum(
        np.random.normal(0, 0.05, len(future_index))
    )

    return pd.DataFrame({
        "timestamp": future_index,
        "forecast": forecast
    })

# -------------------------------------------------
# Sidebar controls
# -------------------------------------------------
st.sidebar.header("Controls")

section = st.sidebar.radio(
    "Select Analysis Type",
    [
        "House Load Disaggregation",
        "House Consumption Forecast",
        "Area Consumption Forecast"
    ]
)

start_date = st.sidebar.date_input(
    "Start Date",
    datetime.now() - timedelta(days=7)
)

end_date = st.sidebar.date_input(
    "End Date",
    datetime.now()
)

# -------------------------------------------------
# SECTION 1 – House Load Disaggregation
# -------------------------------------------------
if section == "House Load Disaggregation":
    st.subheader("🏠 Aggregate vs Individual Load Consumption")

    house_id = st.sidebar.selectbox(
        "House / Customer ID",
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
            name=load
        ))

    fig.update_layout(
        title=f"House {house_id} – Aggregate & Load Consumption",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 2 – House Forecast
# -------------------------------------------------
elif section == "House Consumption Forecast":
    st.subheader("📈 House-Level Forecast")

    house_id = st.sidebar.selectbox(
        "House / Customer ID",
        ["House_001", "House_002", "House_003"]
    )

    df = generate_house_data(house_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name="Historical"
    ))

    fig.add_trace(go.Scatter(
        x=forecast_df["timestamp"],
        y=forecast_df["forecast"],
        name="Forecast",
        line=dict(dash="dash")
    ))

    fig.update_layout(
        title=f"House {house_id} – Historical & Forecasted Consumption",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 3 – Area Forecast
# -------------------------------------------------
elif section == "Area Consumption Forecast":
    st.subheader("🌍 Area-Level Forecast")

    area_id = st.sidebar.selectbox(
        "Area ID",
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
        title=f"Area {area_id} – Historical & Forecasted Consumption",
        xaxis_title="Time",
        yaxis_title="Power (kW)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

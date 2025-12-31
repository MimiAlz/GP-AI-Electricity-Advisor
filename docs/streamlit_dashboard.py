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
# Authentication config
# -------------------------------------------------
credentials = {
    "usernames": {
        "admin": {
            "name": "Admin User",
            "password": "admin123"
        },
        "user1": {
            "name": "House User",
            "password": "user123"
        }
    }
}

credentials = stauth.Hasher().hash_passwords(credentials)

authenticator = stauth.Authenticate(
    credentials,
    cookie_name="power_dashboard",
    key="auth",
    cookie_expiry_days=1
)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
authenticator.login(location="main", key="Login")

# Now read from session_state
auth_status = st.session_state.get("authentication_status")
user_name = st.session_state.get("name")
user_username = st.session_state.get("username")

if auth_status:
    st.success(f"Welcome {user_name}")

elif auth_status is False:
    st.error("Username/password is incorrect")
    st.stop()

else:
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
# The rest of your sections…
# (same as before, omitted for brevity)

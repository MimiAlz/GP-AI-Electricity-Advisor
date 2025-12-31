import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os 

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Power Consumption Dashboard", layout="wide")

# -------------------------------------------------
# Load credentials from YAML
# -------------------------------------------------
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.yaml")

def load_credentials():
    with open(CREDENTIALS_FILE, "r") as file:
        return yaml.load(file, Loader=SafeLoader)

def save_credentials(credentials):
    with open(CREDENTIALS_FILE, "w") as file:
        yaml.dump(credentials, file)

credentials = load_credentials()

# -------------------------------------------------
# Signup form (sidebar)
# -------------------------------------------------
st.sidebar.header("User Access")

signup_clicked = st.sidebar.checkbox("Sign Up")
if signup_clicked:
    st.sidebar.subheader("Create a New Account")
    new_username = st.sidebar.text_input("Username")
    new_name = st.sidebar.text_input("Full Name")
    new_password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Register"):
        if new_username in credentials["usernames"]:
            st.sidebar.error("Username already exists!")
        elif not new_username or not new_password or not new_name:
            st.sidebar.error("All fields are required!")
        else:
            credentials["usernames"][new_username] = {
                "name": new_name,
                "password": new_password
            }
            # Hash all passwords and save
            credentials = stauth.Hasher().hash_passwords(credentials)
            save_credentials(credentials)
            st.sidebar.success(f"Account created for {new_name}. You can now log in.")

# -------------------------------------------------
# Authenticator instance
# -------------------------------------------------
authenticator = stauth.Authenticate(
    credentials,
    cookie_name="power_dashboard",
    key="auth",
    cookie_expiry_days=1
)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
authenticator.login(location="main", key="login_form")

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
    return pd.DataFrame({"timestamp": time_index, "aggregate": aggregate})

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
    return pd.DataFrame({"timestamp": future_index, "forecast": forecast})

# -------------------------------------------------
# Sidebar controls
# -------------------------------------------------
st.sidebar.header("Controls")
section = st.sidebar.radio(
    "Select Analysis Type",
    ["House Load Disaggregation", "House Consumption Forecast", "Area Consumption Forecast"]
)

start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=7))
end_date = st.sidebar.date_input("End Date", datetime.now())

# -------------------------------------------------
# SECTION 1 – House Load Disaggregation
# -------------------------------------------------
if section == "House Load Disaggregation":
    st.subheader("🏠 Aggregate vs Individual Load Consumption")
    house_id = st.sidebar.selectbox("House / Customer ID", ["House_001", "House_002", "House_003"])
    df = generate_house_data(house_id, start_date, end_date)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name="Aggregate", line=dict(width=3)))
    for load in ["HVAC", "Lighting", "Appliances", "Other"]:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df[load], name=load))

    fig.update_layout(
        title=f"House {house_id} – Aggregate & Load Consumption",
        xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 2 – House Forecast
# -------------------------------------------------
elif section == "House Consumption Forecast":
    st.subheader("📈 House-Level Forecast")
    house_id = st.sidebar.selectbox("House / Customer ID", ["House_001", "House_002", "House_003"])
    df = generate_house_data(house_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name="Historical"))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"], name="Forecast", line=dict(dash="dash")))

    fig.update_layout(
        title=f"House {house_id} – Historical & Forecasted Consumption",
        xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 3 – Area Forecast
# -------------------------------------------------
elif section == "Area Consumption Forecast":
    st.subheader("🌍 Area-Level Forecast")
    area_id = st.sidebar.selectbox("Area ID", ["Area_A", "Area_B", "Area_C"])
    df = generate_area_data(area_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name="Historical Area Consumption"))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"], name="Forecast", line=dict(dash="dash")))

    fig.update_layout(
        title=f"Area {area_id} – Historical & Forecasted Consumption",
        xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

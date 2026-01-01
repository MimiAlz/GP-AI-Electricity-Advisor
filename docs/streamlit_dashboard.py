import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import os

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Power Consumption Dashboard",
    layout="wide"
)

# -------------------------------------------------
# Credentials file
# -------------------------------------------------
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.yaml")

def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        # create default empty credentials if file doesn't exist
        with open(CREDENTIALS_FILE, "w") as f:
            yaml.dump({"credentials": {"usernames": {}}}, f)
    with open(CREDENTIALS_FILE, "r") as file:
        return yaml.load(file, Loader=SafeLoader)

def save_credentials(credentials):
    with open(CREDENTIALS_FILE, "w") as file:
        yaml.dump(credentials, file)

credentials = load_credentials()

# -------------------------------------------------
# Sidebar Signup form
# -------------------------------------------------
st.sidebar.header("Sign Up (New User)")
signup_name = st.sidebar.text_input("Full Name", key="signup_name")
signup_national_id = st.sidebar.text_input("National ID (numbers only)", key="signup_id")
signup_password = st.sidebar.text_input("Password", type="password", key="signup_password")
signup_button = st.sidebar.button("Sign Up", key="signup_button")

if signup_button:
    if not signup_national_id.isdigit():
        st.sidebar.error("National ID must contain only numbers!")
    elif signup_national_id in credentials["credentials"]["usernames"]:
        st.sidebar.error("User already exists!")
    else:
        hashed_password = stauth.Hasher([signup_password]).generate()[0]
        credentials["credentials"]["usernames"][signup_national_id] = {
            "name": signup_name,
            "password": hashed_password
        }
        save_credentials(credentials)
        st.sidebar.success(f"User {signup_name} created! You can now log in.")

# -------------------------------------------------
# Authenticator
# -------------------------------------------------
authenticator = stauth.Authenticate(
    credentials["credentials"],
    cookie_name="power_dashboard",
    key="auth",
    cookie_expiry_days=1
)

# -------------------------------------------------
# Sidebar Login
# -------------------------------------------------
st.sidebar.header("User Login")
username_input = st.sidebar.text_input("National ID", key="login_username")
password_input = st.sidebar.text_input("Password", type="password", key="login_password")
login_button = st.sidebar.button("Log In", key="login_button")

if login_button:
    if username_input in credentials["credentials"]["usernames"]:
        user = credentials["credentials"]["usernames"][username_input]
        if stauth.Hasher().check_password(password_input, user["password"]):
            st.session_state["authentication_status"] = True
            st.session_state["name"] = user["name"]
            st.session_state["username"] = username_input
            st.success(f"Welcome {user['name']}")
        else:
            st.session_state["authentication_status"] = False
            st.error("Incorrect password")
    else:
        st.session_state["authentication_status"] = False
        st.error("User not found")

# Stop execution if not authenticated
if not st.session_state.get("authentication_status"):
    st.stop()

# -------------------------------------------------
# Logout button
# -------------------------------------------------
authenticator.logout("Logout", "sidebar")

# -------------------------------------------------
# Title
# -------------------------------------------------
st.title("⚡ Power Consumption Analytics Dashboard")

# -------------------------------------------------
# Appliance categories
# -------------------------------------------------
LOAD_CATEGORIES = {
    "CDE": "Clothes Dryer",
    "CWE": "Clothes Washer",
    "DWE": "Dishwasher",
    "FRE": "HVAC / Furnace (AC & Heater)",
    "HPE": "Heat Pump",
    "FGE": "Kitchen Fridge",
    "HTE": "Instant Hot Water Unit",
    "TVE": "Entertainment (TV/PVR/AMP)",
    "Extra": "Additional / Miscellaneous",
    "EV": "Electrical Vehicles"
}

# -------------------------------------------------
# Mock Data Generators
# -------------------------------------------------
def generate_time_series(start, end, freq="15min"):
    return pd.date_range(start=start, end=end, freq=freq)

def generate_house_data(house_id, start, end):
    time_index = generate_time_series(start, end)
    aggregate = np.random.uniform(0.5, 5.0, len(time_index))
    data = {"timestamp": time_index, "aggregate": aggregate}
    for code in LOAD_CATEGORIES:
        data[code] = aggregate * np.random.uniform(0.05, 0.3, len(time_index))
    return pd.DataFrame(data)

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
    for code, label in LOAD_CATEGORIES.items():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df[code], name=label))
    fig.update_layout(title=f"House {house_id} – Aggregate & Load Consumption",
                      xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 2 – House Consumption Forecast
# -------------------------------------------------
elif section == "House Consumption Forecast":
    st.subheader("📈 House-Level Forecast")
    house_id = st.sidebar.selectbox("House / Customer ID", ["House_001", "House_002", "House_003"])
    df = generate_house_data(house_id, start_date, end_date)
    forecast_df = generate_forecast(df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name="Historical"))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"], name="Forecast", line=dict(dash="dash")))
    fig.update_layout(title=f"House {house_id} – Historical & Forecasted Consumption",
                      xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 3 – Area Consumption Forecast
# -------------------------------------------------
elif section == "Area Consumption Forecast":
    st.subheader("🌍 Area-Level Forecast")
    area_id = st.sidebar.selectbox("Area ID", ["Area_A", "Area_B", "Area_C"])
    df = generate_area_data(area_id, start_date, end_date)
    forecast_df = generate_forecast(df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name="Historical Area Consumption"))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"], name="Forecast", line=dict(dash="dash")))
    fig.update_layout(title=f"Area {area_id} – Historical & Forecasted Consumption",
                      xaxis_title="Time", yaxis_title="Power (kW)", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

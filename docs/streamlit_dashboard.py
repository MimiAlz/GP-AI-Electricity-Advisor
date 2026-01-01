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
# Signup form (sidebar) with persistent button
# -------------------------------------------------
# -------------------------------------------------
# Signup form (sidebar) – persistent
# -------------------------------------------------
st.sidebar.header("User Access")

# Initialize session state for signup form visibility
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False

# Toggle signup form visibility
if st.sidebar.button("Sign Up / Register"):
    st.session_state.show_signup = True

# Display signup form if toggle is True
if st.session_state.show_signup:
    st.sidebar.subheader("Create a New Account")

    new_username = st.sidebar.text_input("National ID (numbers only)", key="signup_id")
    new_name = st.sidebar.text_input("Full Name", key="signup_name")
    new_password = st.sidebar.text_input("Password", type="password", key="signup_pass")

    if st.sidebar.button("Register", key="register_btn"):
        # Validation
        if not new_username.isdigit():
            st.sidebar.error("Username must contain numbers only (national ID).")
        elif len(new_username) != 10:
            st.sidebar.error("National ID must be exactly 10 digits.")
        elif new_username in credentials["credentials"]["usernames"]:
            st.sidebar.error("This national ID is already registered!")
        elif not new_name or not new_password:
            st.sidebar.error("Full name and password are required!")
        else:
            # Add the user as plain text password
            credentials["credentials"]["usernames"][new_username] = {
                "name": new_name,
                "password": new_password
            }
            # Save credentials to YAML
            with open(CREDENTIALS_FILE, "w") as file:
                yaml.dump(credentials, file)
            st.sidebar.success(f"Account created for {new_name}. You can now log in.")
            # Hide signup form after registration
            st.session_state.show_signup = False



# -------------------------------------------------
# Authenticator instance
# -------------------------------------------------
authenticator = stauth.Authenticate(
    credentials=credentials["credentials"],  # <--- only pass the 'credentials' part
    cookie_name=credentials["cookie"]["name"],
    key=credentials["cookie"]["key"],
    cookie_expiry_days=credentials["cookie"]["expiry_days"]
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

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
# Language state
# -------------------------------------------------
if "lang" not in st.session_state:
    st.session_state.lang = "en"

def toggle_language():
    st.session_state.lang = "ar" if st.session_state.lang == "en" else "en"

LANG = st.session_state.lang

# -------------------------------------------------
# Translations
# -------------------------------------------------
TEXT = {
    "en": {
        "page_title": "Power Consumption Dashboard",
        "lang_btn": "العربية / English",
        "user_access": "User Access",
        "signup": "Sign Up / Register",
        "create_account": "Create a New Account",
        "national_id": "National ID (numbers only)",
        "full_name": "Full Name",
        "password": "Password",
        "register": "Register",
        "welcome": "Welcome",
        "login_error": "Username/password is incorrect",
        "login_prompt": "Please enter your username and password",
        "logout": "Logout",
        "dashboard_title": "⚡ Power Consumption Analytics Dashboard",
        "controls": "Controls",
        "analysis_type": "Select Analysis Type",
        "start_date": "Start Date",
        "end_date": "End Date",
        "house_disagg": "House Load Disaggregation",
        "house_forecast": "House Consumption Forecast",
        "area_forecast": "Area Consumption Forecast",
        "house_section": "🏠 Aggregate vs Individual Load Consumption",
        "house_forecast_title": "📈 House-Level Forecast",
        "area_forecast_title": "🌍 Area-Level Forecast",
        "house_id": "House / Customer ID",
        "area_id": "Area ID",
        "aggregate": "Aggregate",
        "historical": "Historical",
        "forecast": "Forecast",
        "time": "Time",
        "power": "Power (kW)"
    },
    "ar": {
        "page_title": "لوحة استهلاك الطاقة",
        "lang_btn": "العربية / English",
        "user_access": "دخول المستخدم",
        "signup": "تسجيل / إنشاء حساب",
        "create_account": "إنشاء حساب جديد",
        "national_id": "الرقم الوطني (أرقام فقط)",
        "full_name": "الاسم الكامل",
        "password": "كلمة المرور",
        "register": "تسجيل",
        "welcome": "مرحباً",
        "login_error": "اسم المستخدم أو كلمة المرور غير صحيحة",
        "login_prompt": "الرجاء إدخال اسم المستخدم وكلمة المرور",
        "logout": "تسجيل الخروج",
        "dashboard_title": "⚡ لوحة تحليل استهلاك الطاقة",
        "controls": "لوحة التحكم",
        "analysis_type": "اختر نوع التحليل",
        "start_date": "تاريخ البداية",
        "end_date": "تاريخ النهاية",
        "house_disagg": "تفكيك أحمال المنزل",
        "house_forecast": "توقع استهلاك المنزل",
        "area_forecast": "توقع استهلاك المنطقة",
        "house_section": "🏠 الاستهلاك الكلي مقابل الأحمال الفردية",
        "house_forecast_title": "📈 توقع استهلاك المنزل",
        "area_forecast_title": "🌍 توقع استهلاك المنطقة",
        "house_id": "معرف المنزل / المشترك",
        "area_id": "معرف المنطقة",
        "aggregate": "الإجمالي",
        "historical": "سجل الاستهلاك",
        "forecast": "التوقع",
        "time": "الوقت",
        "power": "القدرة (كيلوواط)"
    }
}

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title=TEXT[LANG]["page_title"], layout="wide")

# RTL support for Arabic
if LANG == "ar":
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            direction: rtl;
            text-align: right;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# Load credentials
# -------------------------------------------------
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.yaml")

def load_credentials():
    with open(CREDENTIALS_FILE, "r") as file:
        return yaml.load(file, Loader=SafeLoader)

credentials = load_credentials()

# -------------------------------------------------
# Sidebar: language toggle
# -------------------------------------------------
st.sidebar.button(TEXT[LANG]["lang_btn"], on_click=toggle_language)

# -------------------------------------------------
# Signup form
# -------------------------------------------------
st.sidebar.header(TEXT[LANG]["user_access"])

if "show_signup" not in st.session_state:
    st.session_state.show_signup = False

if st.sidebar.button(TEXT[LANG]["signup"]):
    st.session_state.show_signup = True

if st.session_state.show_signup:
    st.sidebar.subheader(TEXT[LANG]["create_account"])

    new_username = st.sidebar.text_input(TEXT[LANG]["national_id"])
    new_name = st.sidebar.text_input(TEXT[LANG]["full_name"])
    new_password = st.sidebar.text_input(TEXT[LANG]["password"], type="password")

    if st.sidebar.button(TEXT[LANG]["register"]):
        credentials["credentials"]["usernames"][new_username] = {
            "name": new_name,
            "password": new_password
        }
        with open(CREDENTIALS_FILE, "w") as file:
            yaml.dump(credentials, file)
        st.session_state.show_signup = False

# -------------------------------------------------
# Authenticator
# -------------------------------------------------
authenticator = stauth.Authenticate(
    credentials=credentials["credentials"],
    cookie_name=credentials["cookie"]["name"],
    key=credentials["cookie"]["key"],
    cookie_expiry_days=credentials["cookie"]["expiry_days"]
)

authenticator.login(location="main", key="login_form")

auth_status = st.session_state.get("authentication_status")
user_name = st.session_state.get("name")

if auth_status:
    st.success(f"{TEXT[LANG]['welcome']} {user_name}")
elif auth_status is False:
    st.error(TEXT[LANG]["login_error"])
    st.stop()
else:
    st.info(TEXT[LANG]["login_prompt"])
    st.stop()

authenticator.logout(TEXT[LANG]["logout"], "sidebar")

# -------------------------------------------------
# Title
# -------------------------------------------------
st.title(TEXT[LANG]["dashboard_title"])

# -------------------------------------------------
# Appliance categories
# -------------------------------------------------
LOAD_CATEGORIES = {
    "CDE": "Clothes Dryer",
    "CWE": "Clothes Washer",
    "DWE": "Dishwasher",
    "FRE": "HVAC / Furnace",
    "HPE": "Heat Pump",
    "FGE": "Kitchen Fridge",
    "HTE": "Instant Hot Water",
    "TVE": "Entertainment",
    "Extra": "Miscellaneous",
    "EV": "Electric Vehicle"
}

# -------------------------------------------------
# Mock data generators (UNCHANGED)
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
    future_index = pd.date_range(start=last_time + timedelta(minutes=15),
                                 periods=horizon_hours * 4, freq="15min")
    forecast = df["aggregate"].iloc[-1] + np.cumsum(np.random.normal(0, 0.05, len(future_index)))
    return pd.DataFrame({"timestamp": future_index, "forecast": forecast})

# -------------------------------------------------
# Sidebar controls
# -------------------------------------------------
st.sidebar.header(TEXT[LANG]["controls"])

section = st.sidebar.radio(
    TEXT[LANG]["analysis_type"],
    [
        TEXT[LANG]["house_disagg"],
        TEXT[LANG]["house_forecast"],
        TEXT[LANG]["area_forecast"]
    ]
)

start_date = st.sidebar.date_input(TEXT[LANG]["start_date"], datetime.now() - timedelta(days=7))
end_date = st.sidebar.date_input(TEXT[LANG]["end_date"], datetime.now())

# -------------------------------------------------
# SECTION 1 – House Load Disaggregation
# -------------------------------------------------
if section == TEXT[LANG]["house_disagg"]:
    st.subheader(TEXT[LANG]["house_section"])
    house_id = st.sidebar.selectbox(TEXT[LANG]["house_id"], ["House_001", "House_002", "House_003"])
    df = generate_house_data(house_id, start_date, end_date)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"],
                             name=TEXT[LANG]["aggregate"], line=dict(width=3)))

    for code, label in LOAD_CATEGORIES.items():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df[code], name=label))

    fig.update_layout(
        title=f"{house_id} – {TEXT[LANG]['house_section']}",
        xaxis_title=TEXT[LANG]["time"],
        yaxis_title=TEXT[LANG]["power"],
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 2 – House Forecast
# -------------------------------------------------
elif section == TEXT[LANG]["house_forecast"]:
    st.subheader(TEXT[LANG]["house_forecast_title"])
    house_id = st.sidebar.selectbox(TEXT[LANG]["house_id"], ["House_001", "House_002", "House_003"])
    df = generate_house_data(house_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"], name=TEXT[LANG]["historical"]))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"],
                             name=TEXT[LANG]["forecast"], line=dict(dash="dash")))

    fig.update_layout(
        title=f"{house_id} – {TEXT[LANG]['house_forecast_title']}",
        xaxis_title=TEXT[LANG]["time"],
        yaxis_title=TEXT[LANG]["power"],
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# SECTION 3 – Area Forecast
# -------------------------------------------------
elif section == TEXT[LANG]["area_forecast"]:
    st.subheader(TEXT[LANG]["area_forecast_title"])
    area_id = st.sidebar.selectbox(TEXT[LANG]["area_id"], ["Area_A", "Area_B", "Area_C"])
    df = generate_area_data(area_id, start_date, end_date)
    forecast_df = generate_forecast(df)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["aggregate"],
                             name=TEXT[LANG]["historical"]))
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"], y=forecast_df["forecast"],
                             name=TEXT[LANG]["forecast"], line=dict(dash="dash")))

    fig.update_layout(
        title=f"{area_id} – {TEXT[LANG]['area_forecast_title']}",
        xaxis_title=TEXT[LANG]["time"],
        yaxis_title=TEXT[LANG]["power"],
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

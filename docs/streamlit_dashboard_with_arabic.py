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
# Arabic numeral converter
# -------------------------------------------------
AR_NUMS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

def format_number(val):
    s = f"{val:.2f}"
    return s.translate(AR_NUMS) if LANG == "ar" else s

def format_time(ts):
    s = ts.strftime("%Y-%m-%d %H:%M")
    return s.translate(AR_NUMS) if LANG == "ar" else s

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
# Appliance categories (EN + AR)
# -------------------------------------------------
LOAD_CATEGORIES = {
    "CDE": {"en": "Clothes Dryer", "ar": "نشافة الملابس"},
    "CWE": {"en": "Clothes Washer", "ar": "غسالة الملابس"},
    "DWE": {"en": "Dishwasher", "ar": "غسالة الصحون"},
    "FRE": {"en": "HVAC / Furnace", "ar": "نظام التدفئة والتكييف"},
    "HPE": {"en": "Heat Pump", "ar": "مضخة حرارية"},
    "FGE": {"en": "Kitchen Fridge", "ar": "ثلاجة المطبخ"},
    "HTE": {"en": "Instant Hot Water", "ar": "سخان مياه فوري"},
    "TVE": {"en": "Entertainment", "ar": "أجهزة الترفيه"},
    "Extra": {"en": "Miscellaneous", "ar": "أحمال إضافية"},
    "EV": {"en": "Electric Vehicle", "ar": "مركبة كهربائية"}
}

# -------------------------------------------------
# Page config + RTL
# -------------------------------------------------
st.set_page_config(page_title=TEXT[LANG]["page_title"], layout="wide")

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
# Authenticator (UNCHANGED)
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
# Data generators (UNCHANGED)
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
    [TEXT[LANG]["house_disagg"], TEXT[LANG]["house_forecast"], TEXT[LANG]["area_forecast"]]
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
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name=TEXT[LANG]["aggregate"],
        hovertemplate=f"{TEXT[LANG]['time']}: %{{customdata[0]}}<br>{TEXT[LANG]['power']}: %{{customdata[1]}}<extra></extra>",
        customdata=np.stack([
            df["timestamp"].apply(format_time),
            df["aggregate"].apply(format_number)
        ], axis=-1),
        line=dict(width=3)
    ))

    for code, labels in LOAD_CATEGORIES.items():
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df[code],
            name=labels[LANG],
            hovertemplate=f"{labels[LANG]}<br>{TEXT[LANG]['power']}: %{{customdata}}<extra></extra>",
            customdata=df[code].apply(format_number)
        ))

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

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name=TEXT[LANG]["historical"],
        hovertemplate=f"{TEXT[LANG]['time']}: %{{customdata[0]}}<br>"
                      f"{TEXT[LANG]['power']}: %{{customdata[1]}}"
                      "<extra></extra>",
        customdata=np.stack([
            df["timestamp"].apply(format_time),
            df["aggregate"].apply(format_number)
        ], axis=-1)
    ))

    fig.add_trace(go.Scatter(
        x=forecast_df["timestamp"],
        y=forecast_df["forecast"],
        name=TEXT[LANG]["forecast"],
        line=dict(dash="dash"),
        hovertemplate=f"{TEXT[LANG]['time']}: %{{customdata[0]}}<br>"
                      f"{TEXT[LANG]['power']}: %{{customdata[1]}}"
                      "<extra></extra>",
        customdata=np.stack([
            forecast_df["timestamp"].apply(format_time),
            forecast_df["forecast"].apply(format_number)
        ], axis=-1)
    ))

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

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["aggregate"],
        name=TEXT[LANG]["historical"],
        hovertemplate=f"{TEXT[LANG]['time']}: %{{customdata[0]}}<br>"
                      f"{TEXT[LANG]['power']}: %{{customdata[1]}}"
                      "<extra></extra>",
        customdata=np.stack([
            df["timestamp"].apply(format_time),
            df["aggregate"].apply(format_number)
        ], axis=-1)
    ))

    fig.add_trace(go.Scatter(
        x=forecast_df["timestamp"],
        y=forecast_df["forecast"],
        name=TEXT[LANG]["forecast"],
        line=dict(dash="dash"),
        hovertemplate=f"{TEXT[LANG]['time']}: %{{customdata[0]}}<br>"
                      f"{TEXT[LANG]['power']}: %{{customdata[1]}}"
                      "<extra></extra>",
        customdata=np.stack([
            forecast_df["timestamp"].apply(format_time),
            forecast_df["forecast"].apply(format_number)
        ], axis=-1)
    ))

    fig.update_layout(
        title=f"{area_id} – {TEXT[LANG]['area_forecast_title']}",
        xaxis_title=TEXT[LANG]["time"],
        yaxis_title=TEXT[LANG]["power"],
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)  

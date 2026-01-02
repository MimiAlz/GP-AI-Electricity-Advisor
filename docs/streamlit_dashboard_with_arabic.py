import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

# -----------------------------
# Page config
# -----------------------------
if "lang" not in st.session_state:
    st.session_state.lang = "en"

st.set_page_config(
    page_title="Power Consumption Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# Language & RTL
# -----------------------------
def apply_language_css(lang):
    if lang == "ar":
        st.markdown("""
        <style>
        html, body, [class*="css"] { direction: rtl; text-align: right; font-family: Tahoma, Arial, sans-serif; }
        section[data-testid="stSidebar"] * { direction: rtl; text-align: right; }
        label, input, textarea, select { direction: rtl; text-align: right !important; }
        h1, h2, h3, h4, h5 { text-align: right; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        html, body, [class*="css"] { direction: ltr; text-align: left; }
        </style>
        """, unsafe_allow_html=True)

def to_arabic_digits(val):
    return str(val).translate(str.maketrans("0123456789","٠١٢٣٤٥٦٧٨٩"))

LANG = st.session_state.lang
apply_language_css(LANG)

# -----------------------------
# Translation dictionary
# -----------------------------
TEXT = {
    "en": {
        "page_title":"Power Consumption Dashboard",
        "lang_btn":"العربية / English",
        "user_access":"User Access",
        "signup":"Sign Up / Register",
        "create_account":"Create a New Account",
        "national_id":"National ID (numbers only)",
        "full_name":"Full Name",
        "password":"Password",
        "register":"Register",
        "welcome":"Welcome",
        "login_error":"Username/password is incorrect",
        "login_prompt":"Please enter your username and password",
        "logout":"Logout",
        "dashboard_title":"Power Consumption Analytics Dashboard",
        "controls":"Controls",
        "analysis_type":"Select Analysis Type",
        "start_date":"Start Date",
        "end_date":"End Date",
        "house_disagg":"House Load Disaggregation",
        "house_forecast":"House Consumption Forecast",
        "area_forecast":"Area Consumption Forecast",
        "house_section":"Aggregate vs Individual Load Consumption",
        "house_forecast_title":"House-Level Forecast",
        "area_forecast_title":"Area-Level Forecast",
        "house_id":"House / Customer ID",
        "area_id":"Area ID",
        "aggregate":"Aggregate",
        "historical":"Historical",
        "forecast":"Forecast",
        "time":"Time",
        "power":"Power (kW)"
    },
    "ar": {
        "page_title":"لوحة استهلاك الطاقة",
        "lang_btn":"العربية / English",
        "user_access":"دخول المستخدم",
        "signup":"تسجيل / إنشاء حساب",
        "create_account":"إنشاء حساب جديد",
        "national_id":"الرقم الوطني (أرقام فقط)",
        "full_name":"الاسم الكامل",
        "password":"كلمة المرور",
        "register":"تسجيل",
        "welcome":"مرحباً",
        "login_error":"اسم المستخدم أو كلمة المرور غير صحيحة",
        "login_prompt":"الرجاء إدخال اسم المستخدم وكلمة المرور",
        "logout":"تسجيل الخروج",
        "dashboard_title":"لوحة تحليل استهلاك الطاقة",
        "controls":"لوحة التحكم",
        "analysis_type":"اختر نوع التحليل",
        "start_date":"تاريخ البداية",
        "end_date":"تاريخ النهاية",
        "house_disagg":"تفكيك أحمال المنزل",
        "house_forecast":"توقع استهلاك المنزل",
        "area_forecast":"توقع استهلاك المنطقة",
        "house_section":"الاستهلاك الكلي مقابل الأحمال الفردية",
        "house_forecast_title":"توقع استهلاك المنزل",
        "area_forecast_title":"توقع استهلاك المنطقة",
        "house_id":"معرف المنزل / المشترك",
        "area_id":"معرف المنطقة",
        "aggregate":"الإجمالي",
        "historical":"سجل الاستهلاك",
        "forecast":"التوقع",
        "time":"الوقت",
        "power":"القدرة (كيلوواط)"
    }
}

# -----------------------------
# Language switch
# -----------------------------
st.sidebar.radio(
    "Language / اللغة",
    ["English","العربية"],
    index=0 if LANG=="en" else 1,
    on_change=lambda: st.session_state.update(
        {"lang":"ar" if st.session_state.get("lang")=="en" else "en"}
    )
)
LANG = st.session_state.lang
apply_language_css(LANG)


# -----------------------------
# YAML credentials
# -----------------------------
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.yaml")
def load_credentials():
    with open(CREDENTIALS_FILE,"r") as f: return yaml.load(f,Loader=SafeLoader)
credentials = load_credentials()

# -----------------------------
# Signup / register
# -----------------------------
st.sidebar.header(TEXT[LANG]["user_access"])
if "show_signup" not in st.session_state: st.session_state.show_signup=False
if st.sidebar.button(TEXT[LANG]["signup"]): st.session_state.show_signup=True

if st.session_state.show_signup:
    st.sidebar.subheader(TEXT[LANG]["create_account"])
    new_username = st.sidebar.text_input(TEXT[LANG]["national_id"])
    new_name = st.sidebar.text_input(TEXT[LANG]["full_name"])
    new_password = st.sidebar.text_input(TEXT[LANG]["password"],type="password")
    if st.sidebar.button(TEXT[LANG]["register"]):
        credentials["credentials"]["usernames"][new_username] = {
            "name": new_name,"password":new_password
        }
        with open(CREDENTIALS_FILE,"w") as f: yaml.dump(credentials,f)
        st.sidebar.success(f"{TEXT[LANG]['welcome']} {new_name}")
        st.session_state.show_signup=False

# -----------------------------
# Authenticator
# -----------------------------
authenticator = stauth.Authenticate(
    credentials=credentials["credentials"],
    cookie_name=credentials["cookie"]["name"],
    key=credentials["cookie"]["key"],
    cookie_expiry_days=credentials["cookie"]["expiry_days"]
)
authenticator.login(location="main",key="login_form")

if LANG == "ar":
    st.markdown("""
    <style>
    /* Hide label ONLY for username (text input) */
    div[data-testid="stTextInput"]:has(input[type="text"]) label {
        display: none;
    }

    /* Replace with Arabic National ID */
    div[data-testid="stTextInput"]:has(input[type="text"])::before {
        content: "الرقم الوطني";
        display: block;
        font-weight: 600;
        margin-bottom: 4px;
        text-align: right;
        direction: rtl;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    /* Hide label ONLY for username (text input) */
    div[data-testid="stTextInput"]:has(input[type="text"]) label {
        display: none;
    }

    /* Replace with English National ID */
    div[data-testid="stTextInput"]:has(input[type="text"])::before {
        content: "National ID";
        display: block;
        font-weight: 600;
        margin-bottom: 4px;
        text-align: left;
    }
    </style>
    """, unsafe_allow_html=True)



auth_status = st.session_state.get("authentication_status")
user_name = st.session_state.get("name")
if auth_status: st.success(f"{TEXT[LANG]['welcome']} {user_name}")
elif auth_status is False: st.error(TEXT[LANG]["login_error"]); st.stop()
else: st.info(TEXT[LANG]["login_prompt"]); st.stop()
authenticator.logout(TEXT[LANG]["logout"],"sidebar")

# -----------------------------
# Dashboard title
# -----------------------------
st.title(TEXT[LANG]["dashboard_title"])

# -----------------------------
# Appliance categories
# -----------------------------
LOAD_CATEGORIES = {
    "CDE":{"en":"Clothes Dryer","ar":"نشافة الملابس"},
    "CWE":{"en":"Clothes Washer","ar":"غسالة الملابس"},
    "DWE":{"en":"Dishwasher","ar":"غسالة الصحون"},
    "FRE":{"en":"HVAC / Furnace","ar":"نظام التدفئة والتكييف"},
    "HPE":{"en":"Heat Pump","ar":"مضخة حرارية"},
    "FGE":{"en":"Kitchen Fridge","ar":"ثلاجة المطبخ"},
    "HTE":{"en":"Instant Hot Water","ar":"سخان مياه فوري"},
    "TVE":{"en":"Entertainment","ar":"أجهزة الترفيه"},
    "Extra":{"en":"Miscellaneous","ar":"أحمال إضافية"},
    "EV":{"en":"Electric Vehicle","ar":"مركبة كهربائية"}
}

# -----------------------------
# Data generation functions
# -----------------------------
def generate_time_series(start,end,freq="15min"):
    return pd.date_range(start=start,end=end,freq=freq)

def generate_house_data(house_id,start,end):
    t=generate_time_series(start,end)
    agg=np.random.uniform(0.5,5.0,len(t))
    data={"timestamp":t,"aggregate":agg}
    for k in LOAD_CATEGORIES: data[k]=agg*np.random.uniform(0.05,0.3,len(t))
    return pd.DataFrame(data)

def generate_area_data(area_id,start,end):
    t=generate_time_series(start,end)
    agg=np.random.uniform(50,200,len(t))
    return pd.DataFrame({"timestamp":t,"aggregate":agg})

def generate_forecast(df,horizon_hours=24):
    last_time=df["timestamp"].iloc[-1]
    future_index=pd.date_range(start=last_time+timedelta(minutes=15),periods=horizon_hours*4,freq="15min")
    forecast=df["aggregate"].iloc[-1]+np.cumsum(np.random.normal(0,0.05,len(future_index)))
    return pd.DataFrame({"timestamp":future_index,"forecast":forecast})

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header(TEXT[LANG]["controls"])
start_val = datetime.now()-timedelta(days=7)
end_val = datetime.now()
start_date = st.sidebar.date_input(TEXT[LANG]["start_date"], start_val)
end_date = st.sidebar.date_input(TEXT[LANG]["end_date"], end_val)

section = st.sidebar.radio(
    TEXT[LANG]["analysis_type"],
    [TEXT[LANG]["house_disagg"], TEXT[LANG]["house_forecast"], TEXT[LANG]["area_forecast"]]
)

# -----------------------------
# Hover formatting
# -----------------------------
def format_hover_time(ts): return to_arabic_digits(ts.strftime("%Y-%m-%d %H:%M")) if LANG=="ar" else ts
def format_hover_value(val): return to_arabic_digits(round(val,2)) if LANG=="ar" else round(val,2)

# -----------------------------
# Section 1 – House Load Disaggregation
# -----------------------------
if section==TEXT[LANG]["house_disagg"]:
    st.subheader(TEXT[LANG]["house_section"])
    house_id=st.sidebar.selectbox(TEXT[LANG]["house_id"],["House_001","House_002","House_003"])
    df=generate_house_data(house_id,start_date,end_date)
    fig=go.Figure()
    hover_agg=df.apply(lambda row:f"{TEXT[LANG]['time']}: {format_hover_time(row['timestamp'])}<br>{TEXT[LANG]['power']}: {format_hover_value(row['aggregate'])}",axis=1)
    fig.add_trace(go.Scatter(x=df["timestamp"],y=df["aggregate"],name=TEXT[LANG]["aggregate"],hovertext=hover_agg,hoverinfo="text"))
    for code,labels in LOAD_CATEGORIES.items():
        hover_text=df.apply(lambda row:f"{labels[LANG]}<br>{TEXT[LANG]['power']}: {format_hover_value(row[code])}",axis=1)
        fig.add_trace(go.Scatter(x=df["timestamp"],y=df[code],name=labels[LANG],hovertext=hover_text,hoverinfo="text"))
    fig.update_layout(height=600,autosize=True,margin=dict(l=60,r=60,t=80,b=60),title=f"{house_id} – {TEXT[LANG]['house_section']}",xaxis_title=TEXT[LANG]["time"],yaxis_title=TEXT[LANG]["power"],hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)

# -----------------------------
# Section 2 – House Forecast
# -----------------------------
elif section==TEXT[LANG]["house_forecast"]:
    st.subheader(TEXT[LANG]["house_forecast_title"])
    house_id=st.sidebar.selectbox(TEXT[LANG]["house_id"],["House_001","House_002","House_003"])
    df=generate_house_data(house_id,start_date,end_date)
    forecast_df=generate_forecast(df)
    fig=go.Figure()
    hist_hover=df.apply(lambda row:f"{TEXT[LANG]['time']}: {format_hover_time(row['timestamp'])}<br>{TEXT[LANG]['power']}: {format_hover_value(row['aggregate'])}",axis=1)
    fig.add_trace(go.Scatter(x=df["timestamp"],y=df["aggregate"],name=TEXT[LANG]["historical"],hovertext=hist_hover,hoverinfo="text"))
    fc_hover=forecast_df.apply(lambda row:f"{TEXT[LANG]['time']}: {format_hover_time(row['timestamp'])}<br>{TEXT[LANG]['power']}: {format_hover_value(row['forecast'])}",axis=1)
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"],y=forecast_df["forecast"],name=TEXT[LANG]["forecast"],line=dict(dash="dash"),hovertext=fc_hover,hoverinfo="text"))
    fig.update_layout(height=600,autosize=True,margin=dict(l=60,r=60,t=80,b=60),title=f"{house_id} – {TEXT[LANG]['house_forecast_title']}",xaxis_title=TEXT[LANG]["time"],yaxis_title=TEXT[LANG]["power"],hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)

# -----------------------------
# Section 3 – Area Forecast
# -----------------------------
elif section==TEXT[LANG]["area_forecast"]:
    st.subheader(TEXT[LANG]["area_forecast_title"])
    area_id=st.sidebar.selectbox(TEXT[LANG]["area_id"],["Area_A","Area_B","Area_C"])
    df=generate_area_data(area_id,start_date,end_date)
    forecast_df=generate_forecast(df)
    fig=go.Figure()
    hist_hover=df.apply(lambda row:f"{TEXT[LANG]['time']}: {format_hover_time(row['timestamp'])}<br>{TEXT[LANG]['power']}: {format_hover_value(row['aggregate'])}",axis=1)
    fig.add_trace(go.Scatter(x=df["timestamp"],y=df["aggregate"],name=TEXT[LANG]["historical"],hovertext=hist_hover,hoverinfo="text"))
    fc_hover=forecast_df.apply(lambda row:f"{TEXT[LANG]['time']}: {format_hover_time(row['timestamp'])}<br>{TEXT[LANG]['power']}: {format_hover_value(row['forecast'])}",axis=1)
    fig.add_trace(go.Scatter(x=forecast_df["timestamp"],y=forecast_df["forecast"],name=TEXT[LANG]["forecast"],line=dict(dash="dash"),hovertext=fc_hover,hoverinfo="text"))
    fig.update_layout(height=600,autosize=True,margin=dict(l=60,r=60,t=80,b=60),title=f"{area_id} – {TEXT[LANG]['area_forecast_title']}",xaxis_title=TEXT[LANG]["time"],yaxis_title=TEXT[LANG]["power"],hovermode="x unified")
    st.plotly_chart(fig,use_container_width=True)

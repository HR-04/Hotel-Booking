import streamlit as st
import requests
import plotly.io as pio
from datetime import datetime

# Configure page
st.set_page_config(page_title="Hotel Booking Assistant", page_icon="🏨", layout="wide")

# Initialize session state variables if not already set
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "charts" not in st.session_state:
    st.session_state["charts"] = {}
if "selected_chart" not in st.session_state:
    st.session_state["selected_chart"] = "All Charts"

API_ENDPOINT = "http://localhost:8000/api"

# ---- HEADER ----
st.title("Hotel Booking Assistant 🏨")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ---- SIDEBAR CONTROLS ----
with st.sidebar:
    st.subheader("📊 Analytics Dashboard")
    st.session_state["selected_chart"] = st.selectbox(
        "Choose Your Chart",
        options=[
            "All Charts", "Revenue Trends", "Cancellation Rate",
            "Geographical Distribution", "Monthly Booking Trends",
            "Lead Time Trends", "ADR Distribution", "Stay Duration"
        ],
        key="chart_selector"
    )
    if st.button("✨ Generate Analytics Report"):
        with st.spinner("Generating analytics..."):
            try:
                response = requests.post(f"{API_ENDPOINT}/analytics")
                if response.status_code == 200:
                    data = response.json()
                    st.session_state["charts"] = {
                        "Revenue Trends": data["revenue_trend"],
                        "Cancellation Rate": data["cancellation_rate"],
                        "Geographical Distribution": data["geographical_dist"],
                        "Monthly Booking Trends": data["monthly_trends"],
                        "Lead Time Trends": data["lead_time_dist"],
                        "ADR Distribution": data["adr_distribution"],
                        "Stay Duration": data["stay_duration"]
                    }
                    st.success("Analytics generated successfully!")
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
            except requests.ConnectionError:
                st.error("Backend service unavailable. Please check server status.")
    
    st.subheader("🛠️ Data Generation")
    if st.button("🔥 Create New Booking Record"):
        with st.spinner("Generating new record..."):
            try:
                response = requests.post(f"{API_ENDPOINT}/generate-data")
                if response.status_code == 200:
                    st.success(response.json().get("message", "New data generated"))
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
            except requests.ConnectionError:
                st.error("Backend service unavailable. Please check server status.")

# ---- DASHBOARD SECTION ----
if st.session_state["charts"]:
    selected = st.session_state["selected_chart"]
    if selected == "All Charts":
        for chart_title, chart_json in st.session_state["charts"].items():
            with st.expander(chart_title, expanded=True):
                st.plotly_chart(pio.from_json(chart_json), use_container_width=True)
    else:
        chart_json = st.session_state["charts"].get(selected)
        if chart_json:
            st.plotly_chart(pio.from_json(chart_json), use_container_width=True)

# ---- CHAT SECTION ----
chat_container = st.container()
with chat_container:
    for msg in st.session_state["chat_history"]:
        st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("Ask about bookings...")
if user_input:
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    try:
        response = requests.post(f"{API_ENDPOINT}/ask", json={"question": user_input})
        if response.status_code == 200:
            answer = response.json().get("answer", "No answer received")
            st.session_state["chat_history"].append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)
        else:
            error_msg = f"API Error: {response.json().get('error', 'Unknown error')}"
            st.chat_message("assistant").write(error_msg)
    except requests.ConnectionError:
        st.chat_message("assistant").write("Backend service unavailable. Please check server status.")

import streamlit as st
import requests
import plotly.io as pio
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Hotel Booking Assistant",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
    <style>
    .stTextInput input {
        border-radius: 20px;
        padding: 12px;
    }
    .stChatMessage {
        border-radius: 15px;
        margin: 10px 0;
    }
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)

API_ENDPOINT = "http://localhost:8000"

# Session state initialization
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar navigation
with st.sidebar:
    st.title("🏨 Navigation")
    page = st.radio("Choose a page:", 
                   ["📊 Analytics Dashboard", "💬 Booking Assistant"],
                   label_visibility="collapsed")

    st.markdown("---")
    st.caption("Powered by Ollama & LangChain")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if page == "📊 Analytics Dashboard":
    st.title("Hotel Booking Analytics")
    st.write("Explore key metrics and trends from booking data")
    
    if st.button("Generate Full Report", key="report_btn"):
        with st.spinner("Crunching numbers..."):
            try:
                response = requests.post(f"{API_ENDPOINT}/analytics")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Top Row: Revenue + Cancellations
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        with st.expander("📈 Revenue Trends", expanded=True):
                            st.plotly_chart(pio.from_json(data['revenue_trend']), 
                                          use_container_width=True)
                    with col2:
                        with st.expander("❌✅ Cancellations"):
                            st.plotly_chart(pio.from_json(data['cancellation_rate']), 
                                          use_container_width=True)

                    # Second Row: Operational Metrics
                    col3, col4 = st.columns(2)
                    with col3:
                        with st.expander("🏨 ADR Distribution by Hotel Type"):
                            st.plotly_chart(pio.from_json(data['adr_distribution']), 
                                          use_container_width=True)
                    with col4:
                        with st.expander("🌙 Stay Duration Analysis"):
                            st.plotly_chart(pio.from_json(data['stay_duration']), 
                                          use_container_width=True)

                    # Third Row: Geographical & Temporal Trends
                    col5, col6 = st.columns(2)
                    with col5:
                        with st.expander("🌍 Geographical Distribution"):
                            st.plotly_chart(pio.from_json(data['geographical_dist']), 
                                          use_container_width=True)
                    with col6:
                        with st.expander("📅 Monthly Booking Trends"):
                            st.plotly_chart(pio.from_json(data['monthly_trends']), 
                                          use_container_width=True)

                    # Bottom Row: Lead Time Analysis
                    with st.expander("⏱️ Lead Time Distribution", expanded=True):
                        st.plotly_chart(pio.from_json(data['lead_time_dist']), 
                                      use_container_width=True)
                
                else:
                    st.error(f"Error: {response.json().get('error', 'Unknown error')}")
            
            except requests.ConnectionError:
                st.error("Backend service unavailable. Please check server status.")

# Chat Interface Page
elif page == "💬 Booking Assistant":
    st.title("Booking Data Assistant")
    st.caption("Ask natural language questions about hotel bookings")
    
    # Chat container
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Question input
    if prompt := st.chat_input("Ask about bookings..."):
        # Add user question to history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                try:
                    response = requests.post(
                        f"{API_ENDPOINT}/ask",
                        json={"question": prompt}
                    )
                    
                    if response.status_code == 200:
                        answer = response.json().get("answer", "No answer received")
                        st.markdown(answer)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": answer}
                        )
                    else:
                        error_msg = f"API Error: {response.json().get('error', 'Unknown error')}"
                        st.error(error_msg)
                
                except requests.ConnectionError:
                    st.error("Backend service unavailable. Please check server status.")

# Run instructions
if __name__ == "__main__":
    st.sidebar.markdown("---")
    st.sidebar.info(
        "**Run these commands in separate terminals:**\n\n"
        "1. `uvicorn analytics_api:app --reload`\n"
        "2. `streamlit run main.py`"
    )
    
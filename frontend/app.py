import streamlit as st
import requests

# --- NEW LOGIC: Backend URL Setup ---
try:
    # Fetch Render URL from Streamlit Secrets in cloud environment
    BACKEND_URL = st.secrets["API_URL"]
except:
    # Fallback to localhost for local development
    BACKEND_URL = "http://127.0.0.1:8000"
# -------------------------------------

password = st.text_input("Enter Password to access AutoDev AI", type="password")
if password != "dafinitiq2026":
    st.warning("Please enter the correct password.")
    st.stop()

# Configure the Streamlit page
st.set_page_config(page_title="AutoDev AI Pipeline", layout="centered")

st.title("AutoDev AI Code Generator")

# Initialize session state variables to persist data between button clicks
if "final_code" not in st.session_state:
    st.session_state.final_code = ""
if "router_decision" not in st.session_state:
    st.session_state.router_decision = ""
if "user_prompt" not in st.session_state:
    st.session_state.user_prompt = ""

# User Input Section
st.subheader("What do you want to build?")
prompt_input = st.text_area("Enter your Python requirement here:", height=150)

# Generate Button Action
if st.button("Generate Code", type="primary"):
    if not prompt_input.strip():
        st.warning("Please enter a prompt first.")
    else:
        st.session_state.user_prompt = prompt_input
        with st.spinner("Agents are working on your request. Please wait..."):
            try:
                # NEW CHANGE: Replaced hardcoded localhost with BACKEND_URL variable
                response = requests.post(
                    f"{BACKEND_URL}/api/generate-code", 
                    json={"requirement": prompt_input}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Guardrail rejection check
                    if data.get("status") == "rejected":
                        st.error(data.get("message"))
                    else:
                        # Store results in session state if valid
                        st.session_state.final_code = data.get("code", "")
                        st.session_state.router_decision = data.get("router_decision", "")
                else:
                    st.error(f"Agent Execution Error: {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to backend. Is the FastAPI server running?")

# Review and Approval Section (Only visible if code is generated)
if st.session_state.final_code:
    st.markdown("---")
    st.header("Review Code")
    
    # Display the engine that processed the request
    st.info(f"Processed by: **{st.session_state.router_decision} Engine**")
    
    # Display the final generated code
    st.code(st.session_state.final_code, language="python")
    
    # Layout for Approve and Reject buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("✅ Approve (Save to DB)"):
            # Prepare data payload for Supabase
            save_payload = {
                "user_prompt": st.session_state.user_prompt,
                "router_decision": st.session_state.router_decision,
                "final_code": st.session_state.final_code
            }
            
            with st.spinner("Saving to Supabase..."):
                try:
                    # NEW CHANGE: Replaced hardcoded localhost with BACKEND_URL variable
                    save_res = requests.post(f"{BACKEND_URL}/api/save-code", json=save_payload)
                    
                    if save_res.status_code == 200:
                        st.success("Approved! Ready for Supabase. Data successfully saved! 🎉")
                        # Clear session state after successful save
                        st.session_state.final_code = ""
                        st.session_state.router_decision = ""
                    else:
                        st.error(f"Failed to save to database: {save_res.text}")
                except Exception as e:
                    st.error(f"Backend connection error during save: {e}")
                    
    with col2:
        if st.button("❌ Reject"):
            st.warning("Code rejected. You can adjust your prompt and try again.")
            # Clear session state
            st.session_state.final_code = ""
            st.session_state.router_decision = ""
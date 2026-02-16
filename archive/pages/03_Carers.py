import streamlit as st


st.query_params["route"] = "/care-hub/login"
st.switch_page("app.py")

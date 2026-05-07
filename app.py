import streamlit as st

st.set_page_config(page_title="AI News Digest Agent", page_icon="📰", layout="centered")

st.title("AI News Digest Agent")
st.caption("Module 0 初始化页面")

topic = st.text_input("Topic", value="AI")

if st.button("Generate Digest Demo"):
    st.info(f"Demo only: Module 0 skeleton ready. Topic={topic}. Real pipeline is not implemented yet.")

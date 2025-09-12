import streamlit as st

from src.ui.app import main

st.set_page_config(page_title="JustPark", page_icon=":parking:", layout="wide")

if __name__ == "__main__":
    main()

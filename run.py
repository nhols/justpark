import streamlit as st

from src.app import main

st.set_page_config(page_title="JustPark", page_icon=":parking:")

if __name__ == "__main__":
    main()

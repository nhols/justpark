import polars as pl
import sqlparse
import streamlit as st

from src.bookings import Bookings


def df_sql_widget(data: Bookings) -> None:
    st.session_state.setdefault("query_history", [])
    query_history = st.session_state.query_history
    dfs = {"Bookings": data.bookings, "Drivers": data.drivers, "Vehicles": data.vehicles}
    for name, df in dfs.items():
        with st.expander(f"{name} Schema"):
            st.dataframe([{"name": k, "type": v} for k, v in df.schema.items()])

    drivers = data.drivers
    vehicles = data.vehicles
    bookings = data.bookings
    query = st.text_area(
        "SQL Query",
        height=200,
        value="""SELECT * FROM bookings b 
LEFT JOIN drivers d ON b.driver_id = d.id 
LEFT JOIN vehicles v ON b.vehicle_id = v.id
""",
    )
    if query:
        query = sqlparse.format(query, reindent=True, keyword_case="upper")
        if query != (query_history[-1] if query_history else None):
            query_history.append(query)
        st.dataframe(pl.sql(query).collect())

    with st.expander("Query history"):
        if not query_history:
            st.info("No queries executed yet")
        for prev_query in query_history[::-1]:
            st.code(prev_query, language="sql")

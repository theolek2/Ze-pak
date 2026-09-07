"""Podgląd bazy DuckDB (ENTSO-E). Uruchomienie: streamlit run app.py"""

import os

import duckdb
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "energy.duckdb")

st.set_page_config(page_title="ENTSO-E DuckDB", layout="wide")
st.title("ENTSO-E — podgląd bazy DuckDB")


@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)


try:
    conn = get_conn()
except Exception as e:
    st.error(f"Nie można otworzyć bazy (używana przez inny proces?): {e}")
    st.stop()

tab_tables, tab_chart = st.tabs(["Tabele", "Wykres cen energii"])

with tab_tables:
    st.subheader("Tabele w bazie")
    tables = conn.execute("show all tables").df()
    tables = tables[tables["schema"].isin(["raw", "analytics"])]
    tables = tables[~tables["name"].str.startswith("_dlt")]
    tables = tables.sort_values(["schema", "name"])
    tables["full"] = tables["schema"] + "." + tables["name"]
    options = tables["full"].tolist()

    if not options:
        st.warning("Brak tabel w schematach raw/analytics.")
    else:
        selected = st.selectbox("Wybierz tabelę", options)
        schema, name = selected.split(".", 1)
        qualified = f'"{schema}"."{name}"'

        count = conn.execute(f"select count(*) from {qualified}").fetchone()[0]
        st.metric("Liczba rekordów", f"{count:,}")

        cols = conn.execute(f"describe {qualified}").df()
        time_col = None
        if "datetime" in cols["column_name"].values:
            time_col = "datetime"
        else:
            for cname, ctype in zip(cols["column_name"], cols["column_type"]):
                if "TIMESTAMP" in str(ctype).upper():
                    time_col = cname
                    break

        if time_col:
            mn, mx = conn.execute(
                f'select min("{time_col}"), max("{time_col}") from {qualified}'
            ).fetchone()
            st.write(f"**Zakres czasu** ({time_col}): {mn} → {mx}")
        else:
            st.write("Brak kolumny czasu (TIMESTAMP).")

        st.write("**Podgląd (pierwsze 20 wierszy)**")
        st.dataframe(conn.execute(f"select * from {qualified} limit 20").df())

with tab_chart:
    st.subheader("Ceny energii (analytics.fct_energy_prices)")

    areas = [
        r[0]
        for r in conn.execute(
            "select distinct area_map_code from analytics.fct_energy_prices order by 1"
        ).fetchall()
    ]
    contracts = [
        r[0]
        for r in conn.execute(
            "select distinct contract_type from analytics.fct_energy_prices order by 1"
        ).fetchall()
    ]
    resolutions = [
        r[0]
        for r in conn.execute(
            "select distinct resolution_code from analytics.fct_energy_prices order by 1"
        ).fetchall()
    ]

    if not areas:
        st.warning("Brak danych w fct_energy_prices. Uruchom najpierw dlt i dbt.")
    else:
        c1, c2, c3 = st.columns(3)
        area = c1.selectbox("Obszar (area_map_code)", areas)
        contract = c2.selectbox("Contract type", contracts)
        resolution = c3.selectbox("Resolution", resolutions)

        df = conn.execute(
            """
            select datetime, price
            from analytics.fct_energy_prices
            where area_map_code = ? and contract_type = ? and resolution_code = ?
            order by datetime
            """,
            [area, contract, resolution],
        ).df()

        if df.empty:
            st.info("Brak wierszy dla wybranych filtrów.")
        else:
            st.line_chart(df, x="datetime", y="price")

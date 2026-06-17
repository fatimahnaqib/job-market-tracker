# Run with: streamlit run dashboard/app.py

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
st.set_page_config(
    page_title="Job Market Intelligence Tracker",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_engine():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not all([host, port, name, user, password]):
        st.error("Database credentials missing. Set DB_* variables in .env")
        st.stop()
    return create_engine(f"postgresql://{user}:{password}@{host}:{port}/{name}")


def run_query(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql))
        return pd.DataFrame(result.fetchall(), columns=result.keys())


@st.cache_data(ttl=300)
def fetch_total_jobs():
    return run_query("SELECT COUNT(*) AS total FROM jobs").iloc[0]["total"]


@st.cache_data(ttl=300)
def fetch_last_updated():
    return run_query("SELECT MAX(fetched_at) AS last_updated FROM jobs").iloc[0]["last_updated"]


@st.cache_data(ttl=300)
def fetch_metrics():
    return run_query("""
        SELECT
            COUNT(DISTINCT company) AS unique_companies,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_remote) / NULLIF(COUNT(*), 0), 1) AS remote_pct,
            AVG(salary_min) FILTER (WHERE salary_min IS NOT NULL) AS avg_salary
        FROM jobs
    """).iloc[0]


@st.cache_data(ttl=300)
def fetch_top_skills():
    return run_query("""
        SELECT skill, COUNT(*) AS count
        FROM jobs, unnest(skills) AS skill
        GROUP BY skill
        ORDER BY count DESC
        LIMIT 15
    """)


@st.cache_data(ttl=300)
def fetch_remote_split():
    return run_query("""
        SELECT is_remote, COUNT(*) AS count
        FROM jobs
        GROUP BY is_remote
    """)


@st.cache_data(ttl=300)
def fetch_top_companies():
    return run_query("""
        SELECT company, COUNT(*) AS count
        FROM jobs
        WHERE company IS NOT NULL
        GROUP BY company
        ORDER BY count DESC
        LIMIT 10
    """)


@st.cache_data(ttl=300)
def fetch_latest_jobs():
    return run_query("""
        SELECT title, company, location, is_remote, salary_min, date_posted
        FROM jobs
        ORDER BY fetched_at DESC
        LIMIT 100
    """)


def format_salary(value):
    if pd.isna(value):
        return "N/A"
    return f"${value:,.0f}"


# Sidebar
with st.sidebar:
    st.title("📊 Job Market Tracker")
    st.caption("Real-time job market analysis")
    total_jobs = fetch_total_jobs()
    last_updated = fetch_last_updated()
    st.metric("Total Jobs", f"{total_jobs:,}")
    st.metric("Last Updated", last_updated.strftime("%Y-%m-%d %H:%M") if pd.notna(last_updated) else "N/A")

st.title("Job Market Intelligence Tracker")
st.subheader("Insights from live job postings")

if total_jobs == 0:
    st.warning("No job data found. Run the ingestion pipeline first.")
    st.stop()

metrics = fetch_metrics()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs", f"{total_jobs:,}")
c2.metric("Unique Companies", f"{int(metrics['unique_companies']):,}")
c3.metric("Remote Jobs %", f"{metrics['remote_pct']}%")
c4.metric("Avg Salary", format_salary(metrics["avg_salary"]))

col1, col2 = st.columns(2)

skills_df = fetch_top_skills()
with col1:
    if skills_df.empty:
        st.warning("No skill data available.")
    else:
        fig = px.bar(
            skills_df.sort_values("count"),
            x="count", y="skill", orientation="h",
            title="Most In-Demand Skills",
            color_discrete_sequence=["#4C9BE8"],
        )
        fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="Postings")
        st.plotly_chart(fig, use_container_width=True)

remote_df = fetch_remote_split()
with col2:
    if remote_df.empty:
        st.warning("No remote/on-site data available.")
    else:
        remote_df["label"] = remote_df["is_remote"].map({True: "Remote", False: "On-site"})
        fig = px.pie(
            remote_df, names="label", values="count",
            title="Remote vs On-site", hole=0.4,
            color_discrete_sequence=["#4C9BE8", "#E8834C"],
        )
        st.plotly_chart(fig, use_container_width=True)

companies_df = fetch_top_companies()
if companies_df.empty:
    st.warning("No company data available.")
else:
    fig = px.bar(
        companies_df.sort_values("count"),
        x="count", y="company", orientation="h",
        title="Top Hiring Companies",
        color_discrete_sequence=["#4CAF82"],
    )
    fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="Postings")
    st.plotly_chart(fig, use_container_width=True)

st.header("Latest Job Postings")
search = st.text_input("Search by job title")
jobs_df = fetch_latest_jobs()
if jobs_df.empty:
    st.warning("No job postings to display.")
else:
    if search:
        jobs_df = jobs_df[jobs_df["title"].str.contains(search, case=False, na=False)]
    st.dataframe(jobs_df, use_container_width=True, hide_index=True)

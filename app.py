import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="FOH Cleaning Task Tracker", layout="wide")
st.title("FOH Cleaning Task Tracker")

DB_PATH = "cleaning_log.db"


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleaning_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            employee TEXT NOT NULL,
            date_cleaned TEXT NOT NULL,
            frequency_days INTEGER NOT NULL,
            next_due TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def calculate_status(date_cleaned, frequency):
    next_due = date_cleaned + timedelta(days=int(frequency))
    today = datetime.today().date()

    if next_due < today:
        status = "Overdue"
    elif (next_due - today).days <= 2:
        status = "Due Soon"
    else:
        status = "On Track"

    return next_due, status


def add_task(task, employee, frequency):
    date_cleaned = datetime.today().date()
    next_due, status = calculate_status(date_cleaned, frequency)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cleaning_tasks
        (task, employee, date_cleaned, frequency_days, next_due, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        task.strip(),
        employee.strip(),
        str(date_cleaned),
        int(frequency),
        str(next_due),
        status
    ))
    conn.commit()
    conn.close()


def load_tasks():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cleaning_tasks", conn)
    conn.close()

    if not df.empty:
        df["Date Cleaned"] = pd.to_datetime(df["date_cleaned"], errors="coerce")
        df["Next Due"] = pd.to_datetime(df["next_due"], errors="coerce")
        df["Frequency (days)"] = pd.to_numeric(df["frequency_days"], errors="coerce")
        df["Status"] = df["status"]

        df = df.rename(columns={
            "id": "ID",
            "task": "Task",
            "employee": "Employee"
        })

        df = df[[
            "ID", "Task", "Employee", "Date Cleaned",
            "Frequency (days)", "Next Due", "Status"
        ]].sort_values("Next Due")

    return df


def delete_task(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cleaning_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


# Initialize database
init_db()

# Load current data
df = load_tasks()

st.subheader("Add Task")

col1, col2, col3 = st.columns(3)

with col1:
    task = st.text_input("Task")

with col2:
    employee = st.text_input("Employee")

with col3:
    frequency = st.number_input("Frequency (days)", min_value=1, value=7, step=1)

if st.button("Add Task"):
    if task.strip() and employee.strip():
        add_task(task, employee, frequency)
        st.success("Task added.")
        st.rerun()
    else:
        st.warning("Please enter both a task and employee.")

st.subheader("Current Tasks")
if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.info("No tasks yet.")

st.subheader("Delete Task")

with st.expander("Open delete menu"):
    if not df.empty:
        delete_options = {
            f"{row['Task']} | {row['Employee']} | Due: {row['Next Due'].date() if pd.notnull(row['Next Due']) else 'N/A'}": row["ID"]
            for _, row in df.iterrows()
        }

        selected_label = st.selectbox("Select a task to delete", list(delete_options.keys()))

        if st.button("Delete Selected Task"):
            delete_task(delete_options[selected_label])
            st.success("Task deleted.")
            st.rerun()
    else:
        st.info("No tasks yet.")

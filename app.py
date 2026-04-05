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
def get_task_by_id(task_id):
    conn = get_connection()
    query = "SELECT * FROM cleaning_tasks WHERE id = ?"
    df_task = pd.read_sql_query(query, conn, params=(task_id,))
    conn.close()
    return df_task.iloc[0] if not df_task.empty else None


def update_task(task_id, task, employee, date_cleaned, frequency):
    next_due, status = calculate_status(date_cleaned, frequency)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cleaning_tasks
        SET task = ?, employee = ?, date_cleaned = ?, frequency_days = ?, next_due = ?, status = ?
        WHERE id = ?
    """, (
        task.strip(),
        employee.strip(),
        str(date_cleaned),
        int(frequency),
        str(next_due),
        status,
        task_id
    ))
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Load current data
df = load_tasks()
if "editing_task_id" not in st.session_state:
    st.session_state.editing_task_id = None

# Dashboard metrics
st.subheader("Dashboard")

if df.empty:
    total_tasks = 0
    overdue_tasks = 0
    due_soon_tasks = 0
    on_track_tasks = 0
else:
    total_tasks = len(df)
    overdue_tasks = (df["Status"] == "Overdue").sum()
    due_soon_tasks = (df["Status"] == "Due Soon").sum()
    on_track_tasks = (df["Status"] == "On Track").sum()

metric1, metric2, metric3, metric4 = st.columns(4)

with metric1:
    st.metric("Total Tasks", total_tasks)

with metric2:
    st.metric("Overdue", overdue_tasks)

with metric3:
    st.metric("Due Soon", due_soon_tasks)

with metric4:
    st.metric("On Track", on_track_tasks)
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

if df.empty:
    st.info("No tasks yet.")
else:
    for _, row in df.iterrows():
        if st.session_state.editing_task_id == row["ID"]:
            st.markdown(f"### Editing: {row['Task']}")

            existing_task = get_task_by_id(row["ID"])

            edit_col1, edit_col2, edit_col3 = st.columns(3)

            with edit_col1:
                edited_task = st.text_input(
                    "Task",
                    value=existing_task["task"],
                    key=f"edit_task_{row['ID']}"
                )

            with edit_col2:
                edited_employee = st.text_input(
                    "Employee",
                    value=existing_task["employee"],
                    key=f"edit_employee_{row['ID']}"
                )

            with edit_col3:
                existing_date = pd.to_datetime(existing_task["date_cleaned"]).date()
                edited_date = st.date_input(
                    "Date Cleaned",
                    value=existing_date,
                    key=f"edit_date_{row['ID']}"
                )

            edited_frequency = st.number_input(
                "Frequency (days)",
                min_value=1,
                value=int(existing_task["frequency_days"]),
                step=1,
                key=f"edit_frequency_{row['ID']}"
            )

            save_col, cancel_col = st.columns(2)

            with save_col:
                if st.button("Save", key=f"save_{row['ID']}"):
                    if edited_task.strip() and edited_employee.strip():
                        update_task(
                            row["ID"],
                            edited_task,
                            edited_employee,
                            edited_date,
                            edited_frequency
                        )
                        st.session_state.editing_task_id = None
                        st.success("Task updated.")
                        st.rerun()
                    else:
                        st.warning("Please enter both a task and employee.")

            with cancel_col:
                if st.button("Cancel", key=f"cancel_{row['ID']}"):
                    st.session_state.editing_task_id = None
                    st.rerun()

            st.divider()

        else:
            col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 1, 1])

            with col1:
                st.write(f"**{row['Task']}**")

            with col2:
                st.write(row["Employee"])

            with col3:
                st.write(f"Due: {row['Next Due'].date()}")

            with col4:
                st.write(row["Status"])

            with col5:
                if st.button("Edit", key=f"edit_{row['ID']}"):
                    st.session_state.editing_task_id = row["ID"]
                    st.rerun()

            with col6:
                if st.button("Delete", key=f"delete_{row['ID']}"):
                    delete_task(row["ID"])
                    st.rerun()

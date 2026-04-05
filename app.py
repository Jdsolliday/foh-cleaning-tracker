import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="FOH Cleaning Task Tracker", layout="wide")

DB_PATH = "cleaning_log.db"


# ── Database helpers ──────────────────────────────────────────────────────────

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS cleaning_tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task            TEXT    NOT NULL,
            employee        TEXT    NOT NULL,
            date_cleaned    TEXT    NOT NULL,
            frequency_days  INTEGER NOT NULL,
            next_due        TEXT    NOT NULL,
            status          TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def load_tasks() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cleaning_tasks", conn)
    conn.close()

    if df.empty:
        return df

    df["Date Cleaned"] = pd.to_datetime(df["date_cleaned"], errors="coerce")
    df["Next Due"] = pd.to_datetime(df["next_due"], errors="coerce")
    df["Frequency (days)"] = pd.to_numeric(df["frequency_days"], errors="coerce")

    df = df.rename(columns={"id": "ID", "task": "Task", "employee": "Employee", "status": "Status"})

    return df[["ID", "Task", "Employee", "Date Cleaned", "Frequency (days)", "Next Due", "Status"]].sort_values("Next Due")


def get_task_by_id(task_id: int):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cleaning_tasks WHERE id = ?", conn, params=(task_id,))
    conn.close()
    return df.iloc[0] if not df.empty else None


def add_task(task: str, employee: str, frequency: int):
    date_cleaned = datetime.today().date()
    next_due, status = _calculate_status(date_cleaned, frequency)

    conn = get_connection()
    conn.cursor().execute(
        "INSERT INTO cleaning_tasks (task, employee, date_cleaned, frequency_days, next_due, status) VALUES (?, ?, ?, ?, ?, ?)",
        (task.strip(), employee.strip(), str(date_cleaned), int(frequency), str(next_due), status),
    )
    conn.commit()
    conn.close()


def update_task(task_id: int, task: str, employee: str, date_cleaned, frequency: int):
    next_due, status = _calculate_status(date_cleaned, frequency)

    conn = get_connection()
    conn.cursor().execute(
        """UPDATE cleaning_tasks
           SET task = ?, employee = ?, date_cleaned = ?, frequency_days = ?, next_due = ?, status = ?
           WHERE id = ?""",
        (task.strip(), employee.strip(), str(date_cleaned), int(frequency), str(next_due), status, task_id),
    )
    conn.commit()
    conn.close()


def delete_task(task_id: int):
    conn = get_connection()
    conn.cursor().execute("DELETE FROM cleaning_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


# ── Business logic ────────────────────────────────────────────────────────────

def _calculate_status(date_cleaned, frequency: int) -> tuple:
    next_due = date_cleaned + timedelta(days=int(frequency))
    today = datetime.today().date()

    if next_due < today:
        status = "Overdue"
    elif (next_due - today).days <= 2:
        status = "Due Soon"
    else:
        status = "On Track"

    return next_due, status


# ── UI components ─────────────────────────────────────────────────────────────

def render_dashboard(df: pd.DataFrame):
    st.subheader("Dashboard")

    total = len(df)
    overdue   = (df["Status"] == "Overdue").sum()  if not df.empty else 0
    due_soon  = (df["Status"] == "Due Soon").sum() if not df.empty else 0
    on_track  = (df["Status"] == "On Track").sum() if not df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tasks", total)
    col2.metric("Overdue",     overdue)
    col3.metric("Due Soon",    due_soon)
    col4.metric("On Track",    on_track)


def render_add_task_form():
    col1, col2, col3 = st.columns(3)
    task      = col1.text_input("Task")
    employee  = col2.text_input("Employee")
    frequency = col3.number_input("Frequency (days)", min_value=1, value=7, step=1)

    if st.button("Add Task"):
        if task.strip() and employee.strip():
            add_task(task, employee, frequency)
            st.success("Task added.")
            st.rerun()
        else:
            st.warning("Please enter both a task and employee.")


def render_edit_form(row: pd.Series):
    st.markdown(f"### Editing: {row['Task']}")
    existing = get_task_by_id(row["ID"])

    col1, col2, col3 = st.columns(3)
    edited_task     = col1.text_input("Task",     value=existing["task"],     key=f"edit_task_{row['ID']}")
    edited_employee = col2.text_input("Employee", value=existing["employee"], key=f"edit_employee_{row['ID']}")
    edited_date     = col3.date_input("Date Cleaned", value=pd.to_datetime(existing["date_cleaned"]).date(), key=f"edit_date_{row['ID']}")

    edited_frequency = st.number_input(
        "Frequency (days)", min_value=1, value=int(existing["frequency_days"]), step=1, key=f"edit_frequency_{row['ID']}"
    )

    save_col, cancel_col = st.columns(2)

    with save_col:
        if st.button("Save", key=f"save_{row['ID']}"):
            if edited_task.strip() and edited_employee.strip():
                update_task(row["ID"], edited_task, edited_employee, edited_date, edited_frequency)
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


def render_task_row(row: pd.Series):
    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 1, 1])
    col1.write(f"**{row['Task']}**")
    col2.write(row["Employee"])
    col3.write(f"Due: {row['Next Due'].date()}")
    col4.write(row["Status"])

    with col5:
        if st.button("Edit", key=f"edit_{row['ID']}"):
            st.session_state.editing_task_id = row["ID"]
            st.rerun()

    with col6:
        if st.button("Delete", key=f"delete_{row['ID']}"):
            delete_task(row["ID"])
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.title("FOH Cleaning Task Tracker")

    init_db()

    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None

    df = load_tasks()

    render_dashboard(df)
    st.divider()

    st.subheader("Add Task")
    render_add_task_form()
    st.divider()

    st.subheader("Current Tasks")

    if df.empty:
        st.info("No tasks yet.")
    else:
        for _, row in df.iterrows():
            if st.session_state.editing_task_id == row["ID"]:
                render_edit_form(row)
            else:
                render_task_row(row)


if __name__ == "__main__":
    main()

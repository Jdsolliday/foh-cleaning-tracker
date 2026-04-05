import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Dry Storage Bakehouse FOH Task Tracker", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
TABLE = "cleaning_tasks"


# ── Auth ──────────────────────────────────────────────────────────────────────

def render_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.sidebar:
            st.subheader("Staff Login")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if password == STAFF_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
            st.caption("No password? You can still view the app as a guest.")


def is_staff() -> bool:
    return st.session_state.get("authenticated", False)




# ── Supabase client ───────────────────────────────────────────────────────────

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Database helpers ──────────────────────────────────────────────────────────

def load_tasks() -> pd.DataFrame:
    response = get_client().table(TABLE).select("*").execute()
    rows = response.data

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Date Cleaned"] = pd.to_datetime(df["date_cleaned"], errors="coerce")
    df["Next Due"] = pd.to_datetime(df["next_due"], errors="coerce")
    df["Frequency (days)"] = pd.to_numeric(df["frequency_days"], errors="coerce")
    df = df.rename(columns={"id": "ID", "task": "Task", "employee": "Employee", "status": "Status"})

    return df[["ID", "Task", "Employee", "Date Cleaned", "Frequency (days)", "Next Due", "Status", "completed"]].sort_values("Next Due")


def get_task_by_id(task_id: int):
    response = get_client().table(TABLE).select("*").eq("id", task_id).execute()
    return response.data[0] if response.data else None


def add_task(task: str, employee: str, frequency: int):
    date_cleaned = datetime.today().date()
    next_due, status = _calculate_status(date_cleaned, frequency)

    get_client().table(TABLE).insert({
        "task":           task.strip(),
        "employee":       employee.strip(),
        "date_cleaned":   str(date_cleaned),
        "frequency_days": int(frequency),
        "next_due":       str(next_due),
        "status":         status,
        "completed":      0,
    }).execute()


def update_task(task_id: int, task: str, employee: str, date_cleaned, frequency: int):
    next_due, status = _calculate_status(date_cleaned, frequency)

    get_client().table(TABLE).update({
        "task":           task.strip(),
        "employee":       employee.strip(),
        "date_cleaned":   str(date_cleaned),
        "frequency_days": int(frequency),
        "next_due":       str(next_due),
        "status":         status,
    }).eq("id", task_id).execute()


def mark_task_complete(task_id: int):
    get_client().table(TABLE).update({"completed": 1}).eq("id", task_id).execute()


def restore_task(task_id: int):
    get_client().table(TABLE).update({"completed": 0}).eq("id", task_id).execute()


def delete_task(task_id: int):
    get_client().table(TABLE).delete().eq("id", task_id).execute()


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

STATUS_COLORS = {
    "Overdue":  ("#ff4b4b", "white"),
    "Due Soon": ("#ffa500", "white"),
    "On Track": ("#21c354", "white"),
}

def render_status_badge(status: str):
    bg, fg = STATUS_COLORS.get(status, ("#cccccc", "black"))
    st.markdown(
        f'<span style="background-color:{bg};color:{fg};padding:2px 10px;border-radius:12px;font-size:0.85em;font-weight:600">{status}</span>',
        unsafe_allow_html=True,
    )


def render_dashboard(df: pd.DataFrame):
    st.subheader("Dashboard")

    active   = df[df["completed"] == 0] if not df.empty else df
    total    = len(active)
    overdue  = (active["Status"] == "Overdue").sum()  if not active.empty else 0
    due_soon = (active["Status"] == "Due Soon").sum() if not active.empty else 0
    on_track = (active["Status"] == "On Track").sum() if not active.empty else 0

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
    edited_task     = col1.text_input("Task",         value=existing["task"],     key=f"edit_task_{row['ID']}")
    edited_employee = col2.text_input("Employee",     value=existing["employee"], key=f"edit_employee_{row['ID']}")
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


def render_task_row(row: pd.Series, editable: bool = True):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 2, 2, 2, 1, 1, 1])
    col1.write(f"**{row['Task']}**")
    col2.write(row["Employee"])
    col3.write(f"Due: {row['Next Due'].date()}")
    with col4:
        render_status_badge(row["Status"])

    if editable:
        complete = col5.button("✅", key=f"complete_{row['ID']}", help="Mark Complete")
        edit     = col6.button("Edit",   key=f"edit_{row['ID']}")
        delete   = col7.button("Delete", key=f"delete_{row['ID']}")

        if complete:
            mark_task_complete(row["ID"])
            st.rerun()

        if edit:
            st.session_state.editing_task_id = row["ID"]
            st.rerun()

        if delete:
            delete_task(row["ID"])
            st.rerun()


def render_completed_row(row: pd.Series, editable: bool = True):
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
    col1.write(f"~~{row['Task']}~~")
    col2.write(row["Employee"])
    col3.write(f"Cleaned: {row['Date Cleaned'].date()}")
    col4.write("Completed")

    if editable:
        restore = col5.button("↩️ Restore", key=f"restore_{row['ID']}")
        if restore:
            restore_task(row["ID"])
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    st.title("Dry Storage Bakehouse FOH Task Tracker")

    render_auth()

    if "editing_task_id" not in st.session_state:
        st.session_state.editing_task_id = None

    df = load_tasks()
    active_df    = df[df["completed"] == 0] if not df.empty else df
    completed_df = df[df["completed"] == 1] if not df.empty else df

    render_dashboard(df)
    st.divider()

    if is_staff():
        st.subheader("Add Task")
        render_add_task_form()
        st.divider()
    else:
        st.sidebar.info("👀 Viewing as guest — login for full access.")

    st.subheader("Current Tasks")
    if active_df.empty:
        st.info("No active tasks.")
    else:
        for _, row in active_df.iterrows():
            if is_staff() and st.session_state.editing_task_id == row["ID"]:
                render_edit_form(row)
            else:
                render_task_row(row, editable=is_staff())

    st.divider()

    st.subheader("Completed")
    if completed_df.empty:
        st.info("No completed tasks yet.")
    else:
        for _, row in completed_df.iterrows():
            render_completed_row(row, editable=is_staff())


if __name__ == "__main__":
    main()

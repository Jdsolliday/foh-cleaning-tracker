import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="FOH Cleaning Task Tracker", layout="wide")
st.title("FOH Cleaning Task Tracker")

file_path = "cleaning_log.csv"

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

# Load data
if os.path.exists(file_path):
    df = pd.read_csv(file_path)
else:
    df = pd.DataFrame(columns=[
        "Task", "Employee", "Date Cleaned",
        "Frequency (days)", "Next Due", "Status"
    ])

st.subheader("Add Task")

col1, col2, col3 = st.columns(3)

with col1:
    task = st.text_input("Task")

with col2:
    employee = st.text_input("Employee")

with col3:
    frequency = st.number_input("Frequency (days)", min_value=1, value=7)

if st.button("Add Task"):
    if task.strip() and employee.strip():
        date_cleaned = datetime.today().date()
        next_due, status = calculate_status(date_cleaned, frequency)

        new_row = {
            "Task": task,
            "Employee": employee,
            "Date Cleaned": date_cleaned,
            "Frequency (days)": frequency,
            "Next Due": next_due,
            "Status": status
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(file_path, index=False)
        st.success("Task added.")
        st.rerun()
    else:
        st.warning("Please enter both a task and employee.")

if not df.empty:
    df["Date Cleaned"] = pd.to_datetime(df["Date Cleaned"], errors="coerce")
    df["Next Due"] = pd.to_datetime(df["Next Due"], errors="coerce")
    df = df.sort_values("Next Due")

st.subheader("Current Tasks")
st.dataframe(df, use_container_width=True)

st.subheader("Delete Task")

with st.expander("Open delete menu"):
    if not df.empty:
        delete_labels = [
            f"{i} | {row['Task']} | {row['Employee']} | Due: {row['Next Due'].date() if pd.notnull(row['Next Due']) else 'N/A'}"
            for i, row in df.iterrows()
        ]

        selected_delete = st.selectbox("Select a task to delete", delete_labels)

        if st.button("Delete Selected Task"):
            delete_index = int(selected_delete.split(" | ")[0])
            df = df.drop(delete_index).reset_index(drop=True)
            df.to_csv(file_path, index=False)
            st.success("Task deleted.")
            st.rerun()
    else:
        st.info("No tasks yet.")

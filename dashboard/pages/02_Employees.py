"""
Employee Management — View, Search, Add, and Delete Employees
===============================================================

Features:
    - Overview statistics
    - Search by name / ID / department
    - Employee table with key details
    - Add new employee (manual)
    - Delete employee with confirmation
    - View attendance history per employee
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd

from services.employee_service import EmployeeService
from database.database import get_session
from database.repository import AttendanceRepo

st.set_page_config(page_title="Employees", page_icon="👥", layout="wide")

# ── Initialize session state ────────────────────────────────
if "show_add_form" not in st.session_state:
    st.session_state["show_add_form"] = False

# ── Page Header ──────────────────────────────────────────────
st.title("👥 Employee Management")
st.markdown("Register, view, and manage employee records.")

# ── Statistics ───────────────────────────────────────────────
employees = EmployeeService.get_all()
total = len(employees)
departments = len(set(e.department for e in employees if e.department))
faiss_enrolled = sum(1 for e in employees if e.faiss_id is not None)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Employees", total)
with col2:
    st.metric("Departments", departments)
with col3:
    st.metric("FAISS Enrolled", faiss_enrolled)
with col4:
    st.metric("Active", total)

st.markdown("---")

# ── Search + Add Row ─────────────────────────────────────────
search_col, add_col = st.columns([3, 1])

with search_col:
    search_query = st.text_input("🔍 Search by name, ID, or department", placeholder="e.g. gokul, EMP003, Engineering")

with add_col:
    if st.button("➕ Add Employee", type="primary", use_container_width=True):
        st.session_state["show_add_form"] = True

# ── Filter employees based on search ─────────────────────────
if search_query:
    filtered = EmployeeService.search(search_query)
else:
    filtered = employees

# ── Employee Table ───────────────────────────────────────────
if filtered:
    # Batch-fetch today's attendance counts in a single session
    today_counts = {}
    with get_session() as s:
        for emp in filtered:
            today_counts[emp.id] = len(AttendanceRepo.get_by_employee(s, emp.id))

    table_data = []
    for emp in filtered:
        tc = today_counts.get(emp.id, 0)
        table_data.append({
            "ID": emp.employee_id,
            "Name": emp.name,
            "Department": emp.department or "—",
            "FAISS ID": emp.faiss_id if emp.faiss_id is not None else "—",
            "Today": f"{tc} ✅" if tc > 0 else "0",
            "Enrolled": emp.created_at.strftime("%d %b %Y") if emp.created_at else "—",
            "emp_obj": emp,  # hidden column for actions
        })

    df = pd.DataFrame(table_data)

    # Display without the hidden column
    display_cols = [c for c in df.columns if c != "emp_obj"]
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("Employee ID", width="small"),
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Department": st.column_config.TextColumn("Department", width="medium"),
            "FAISS ID": st.column_config.TextColumn("FAISS", width="small"),
            "Today": st.column_config.TextColumn("Today", width="small"),
            "Enrolled": st.column_config.TextColumn("Enrolled", width="small"),
        },
    )

    # ── Expandable delete rows ───────────────────────────────
    with st.expander("🗑️ Delete an Employee"):
        emp_to_delete = st.selectbox(
            "Select employee to delete",
            options=[(e.employee_id, e.name) for e in filtered],
            format_func=lambda x: f"{x[0]} — {x[1]}",
        )
        if emp_to_delete:
            st.warning(f"This will remove {emp_to_delete[1]} ({emp_to_delete[0]}) from the database. FAISS embedding will NOT be removed automatically.")
            confirm = st.text_input("Type the Employee ID to confirm:", placeholder=emp_to_delete[0])
            if confirm == emp_to_delete[0]:
                if st.button("🗑️ Delete Permanently", type="primary", use_container_width=True):
                    success = EmployeeService.delete(emp_to_delete[0], operator="dashboard")
                    if success:
                        st.success(f"Deleted {emp_to_delete[1]}")
                        st.rerun()
                    else:
                        st.error("Failed to delete employee.")
            elif confirm:
                st.error("ID does not match.")

else:
    st.info("No employees found. Add one using the button above.")

# ── Add Employee Form ────────────────────────────────────────
if st.session_state.get("show_add_form"):
    st.markdown("---")
    st.markdown("### 📝 Register New Employee")

    with st.form("add_employee_form"):
        emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP004",
                               help="Unique identifier for the employee")
        name = st.text_input("Full Name *", placeholder="e.g. John Doe")
        dept = st.text_input("Department", placeholder="e.g. Engineering")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            submitted = st.form_submit_button("✅ Register", type="primary", use_container_width=True)
        with col_s2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted:
            if not emp_id or not name:
                st.error("Employee ID and Name are required.")
            else:
                try:
                    emp = EmployeeService.create(
                        employee_id=emp_id.strip(),
                        name=name.strip(),
                        department=dept.strip() or None,
                        operator="dashboard",
                    )
                    st.success(f"✅ {emp.name} ({emp.employee_id}) registered successfully!")
                    st.session_state["show_add_form"] = False
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        if cancelled:
            st.session_state["show_add_form"] = False
            st.rerun()

# ── Attendance History (expandable per employee) ─────────────
st.markdown("---")
st.markdown("### 📋 Attendance History")

with get_session() as s:
    all_attendance = []
    for emp in filtered[:10]:  # limit to first 10 to avoid slow loads
        records = AttendanceRepo.get_by_employee(s, emp.id)
        for r in records:
            all_attendance.append({
                "Employee": emp.name,
                "ID": emp.employee_id,
                "Date": r.timestamp.strftime("%d %b %Y"),
                "Time": r.timestamp.strftime("%I:%M %p"),
                "Confidence": f"{r.confidence:.1%}",
            })

if all_attendance:
    df_att = pd.DataFrame(all_attendance)
    st.dataframe(df_att, use_container_width=True, hide_index=True)
else:
    st.caption("No attendance records yet.")

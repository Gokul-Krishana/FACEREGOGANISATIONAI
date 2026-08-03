"""
Analytics — Real Charts from SQLite Data
=========================================

Charts:
1. Daily Attendance (bar chart - last 30 days)
2. Hourly Attendance (bar chart - today or selected date)
3. Top Employees (horizontal bar chart)
4. Recognition Accuracy (pie chart - known vs unknown)
5. Department Distribution (pie chart)
6. Recognition Confidence Distribution (histogram)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from database.database import get_session
from database.repository import (
    AttendanceRepo, EmployeeRepo, RecognitionLogRepo, UnknownFaceRepo
)
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from database.models import Attendance, Employee, RecognitionLog, UnknownFace

logger = logging.getLogger(__name__)


st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")


# ── Helper Functions ────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_attendance_df(days: int = 30, limit: int = 5000) -> pd.DataFrame:
    """Load a bounded attendance slice as DataFrame."""
    try:
        with get_session() as session:
            cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
            records = (
                session.query(
                    Attendance.id,
                    Attendance.timestamp,
                    Attendance.employee_id,
                    Attendance.confidence,
                    Employee.name.label("employee_name"),
                    Employee.department.label("department"),
                )
                .join(Employee, Employee.id == Attendance.employee_id)
                .filter(Attendance.timestamp >= cutoff)
                .order_by(desc(Attendance.timestamp))
                .limit(limit)
                .all()
            )
            data = []
            for r in records:
                data.append({
                    "date": r.timestamp.date(),
                    "hour": r.timestamp.hour,
                    "timestamp": r.timestamp,
                    "employee_id": r.employee_id,
                    "employee_name": r.employee_name or "Unknown",
                    "department": r.department or "—",
                    "confidence": r.confidence,
                })
            # Always keep the schema columns — an empty result must still
            # be a valid, columned DataFrame so the page's column access
            # (e.g. attendance_df["confidence"]) never raises KeyError.
            return pd.DataFrame(data, columns=["date", "hour", "timestamp",
                                               "employee_id", "employee_name",
                                               "department", "confidence"])
    except Exception as _exc:
        logger.warning("Could not load attendance analytics: %s", _exc)
        return pd.DataFrame(columns=["date", "hour", "timestamp", "employee_id",
                                     "employee_name", "department", "confidence"])


@st.cache_data(ttl=30)
def load_recognition_df(days: int = 30, limit: int = 5000) -> pd.DataFrame:
    """Load a bounded recognition slice as DataFrame."""
    try:
        with get_session() as session:
            cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
            records = (
                session.query(
                    RecognitionLog.timestamp,
                    RecognitionLog.is_known,
                    RecognitionLog.confidence,
                    Employee.name.label("employee_name"),
                )
                .outerjoin(Employee, Employee.id == RecognitionLog.employee_id)
                .filter(RecognitionLog.timestamp >= cutoff)
                .order_by(desc(RecognitionLog.timestamp))
                .limit(limit)
                .all()
            )
            data = []
            for r in records:
                data.append({
                    "timestamp": r.timestamp,
                    "is_known": r.is_known,
                    "confidence": r.confidence,
                    "employee_name": r.employee_name,
                })
            return pd.DataFrame(data, columns=["timestamp", "is_known",
                                               "confidence", "employee_name"])
    except Exception as _exc:
        logger.warning("Could not load recognition analytics: %s", _exc)
        return pd.DataFrame(columns=["timestamp", "is_known", "confidence", "employee_name"])


@st.cache_data(ttl=30)
def load_employee_stats() -> pd.DataFrame:
    """Load employee attendance statistics."""
    try:
        with get_session() as session:
            records = (
                session.query(
                    Employee.id,
                    Employee.employee_id,
                    Employee.name,
                    Employee.department,
                    func.count(Attendance.id).label("total_attendance"),
                    func.max(Attendance.timestamp).label("last_seen"),
                )
                .outerjoin(Attendance, Employee.id == Attendance.employee_id)
                .group_by(Employee.id)
                .all()
            )
            data = []
            for r in records:
                data.append({
                    "id": r.id,
                    "employee_id": r.employee_id,
                    "name": r.name,
                    "department": r.department or "—",
                    "total_attendance": r.total_attendance or 0,
                    "last_seen": r.last_seen,
                })
            return pd.DataFrame(data, columns=["id", "employee_id", "name",
                                               "department", "total_attendance",
                                               "last_seen"])
    except Exception as _exc:
        logger.warning("Could not load attendance-by-employee analytics: %s", _exc)
        return pd.DataFrame(columns=["id", "employee_id", "name", "department",
                                     "total_attendance", "last_seen"])


@st.cache_data(ttl=30)
def load_unknown_face_stats(days: int = 30) -> dict:
    """Load unknown face statistics."""
    try:
        with get_session() as session:
            cutoff = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
            total = session.query(UnknownFace).count()
            today = session.query(UnknownFace).filter(
                UnknownFace.timestamp >= datetime.combine(date.today(), datetime.min.time())
            ).count()
            this_week = session.query(UnknownFace).filter(
                UnknownFace.timestamp >= cutoff
            ).count()
            pending = session.query(UnknownFace).filter(
                UnknownFace.reviewed == False
            ).count()
            converted = session.query(UnknownFace).filter(
                UnknownFace.converted_to_employee == True
            ).count()
            return {
                "total": total,
                "today": today,
                "this_week": this_week,
                "pending": pending,
                "converted": converted,
            }
    except Exception as _exc:
        logger.warning("Could not load unknown-face analytics: %s", _exc)
        return {"total": 0, "today": 0, "this_week": 0, "pending": 0, "converted": 0}


# ── Page Header ────────────────────────────────────────────────
st.title("📈 Analytics")
st.markdown("Real-time analytics from your attendance and recognition database")

# ── Date Range Selector ────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📅 Date Range")
    days_back = st.selectbox(
        "Analysis Period",
        options=[7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"Last {x} days" if x > 0 else "All Time"
    )
    st.divider()
    st.markdown("### 🎯 Quick Filters")
    show_only_known = st.checkbox("Known faces only", value=False)
    min_confidence = st.slider("Min Confidence", 0.0, 1.0, 0.0, 0.05)

# ── Load Data ──────────────────────────────────────────────────
attendance_df = load_attendance_df(days_back)
recognition_df = load_recognition_df(days_back)
employee_stats = load_employee_stats()
unknown_stats = load_unknown_face_stats(days_back)

if min_confidence > 0:
    attendance_df = attendance_df[attendance_df["confidence"] >= min_confidence]
    recognition_df = recognition_df[recognition_df["confidence"].fillna(0) >= min_confidence]

# ── Summary Cards ──────────────────────────────────────────────
st.markdown("### 📊 Summary")

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Total Employees", len(employee_stats))
with col2:
    st.metric("Total Attendance", len(attendance_df))
with col3:
    st.metric("Unique Present", attendance_df["employee_id"].nunique() if not attendance_df.empty else 0)
with col4:
    known_count = len(recognition_df[recognition_df["is_known"] == True]) if not recognition_df.empty else 0
    unknown_count = len(recognition_df[recognition_df["is_known"] == False]) if not recognition_df.empty else 0
    total_rec = known_count + unknown_count
    accuracy = (known_count / total_rec * 100) if total_rec > 0 else 0
    st.metric("Recognition Accuracy", f"{accuracy:.1f}%")
with col5:
    st.metric("Unknown Faces (Week)", unknown_stats["this_week"])
with col6:
    avg_conf = attendance_df["confidence"].mean() if not attendance_df.empty else 0
    st.metric("Avg Confidence", f"{avg_conf:.1%}")

st.divider()

# ── Charts Row 1: Daily Attendance & Hourly Distribution ───────
st.markdown("### 📅 Attendance Trends")

chart_col1, chart_col2 = st.columns(2)

# 1. Daily Attendance Bar Chart
with chart_col1:
    st.markdown("#### Daily Attendance (Last 30 Days)")
    
    if not attendance_df.empty:
        daily_counts = attendance_df.groupby("date").size().reset_index(name="count")
        daily_counts["date"] = pd.to_datetime(daily_counts["date"])
        daily_counts = daily_counts.sort_values("date")
        
        # Fill missing dates with 0
        date_range = pd.date_range(
            start=daily_counts["date"].min(),
            end=daily_counts["date"].max(),
            freq="D"
        )
        daily_counts = daily_counts.set_index("date").reindex(date_range, fill_value=0).reset_index()
        daily_counts.columns = ["date", "count"]
        
        fig_daily = px.bar(
            daily_counts,
            x="date",
            y="count",
            title="",
            labels={"date": "Date", "count": "Attendance Marks"},
            color_discrete_sequence=["#00cc88"],
        )
        fig_daily.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Date",
            yaxis_title="Marks",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_daily.update_traces(hovertemplate="%{x|%d %b %Y}<br>%{y} marks<extra></extra>")
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.info("No attendance data in selected period")

# 2. Hourly Attendance Distribution
with chart_col2:
    st.markdown("#### Hourly Distribution (Selected Period)")
    
    if not attendance_df.empty:
        hourly_counts = attendance_df.groupby("hour").size().reset_index(name="count")
        hourly_counts = hourly_counts.sort_values("hour")
        
        fig_hourly = px.bar(
            hourly_counts,
            x="hour",
            y="count",
            title="",
            labels={"hour": "Hour of Day", "count": "Attendance Marks"},
            color_discrete_sequence=["#0088ff"],
        )
        fig_hourly.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis=dict(tickmode="linear", tick0=0, dtick=1),
            xaxis_title="Hour (24h)",
            yaxis_title="Marks",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_hourly.update_traces(hovertemplate="%{x}:00<br>%{y} marks<extra></extra>")
        st.plotly_chart(fig_hourly, use_container_width=True)
    else:
        st.info("No attendance data in selected period")

# ── Charts Row 2: Top Employees & Recognition Accuracy ─────────
st.markdown("### 👥 Employee Performance & Recognition")

chart_col3, chart_col4 = st.columns(2)

# 3. Top Employees by Attendance
with chart_col3:
    st.markdown("#### Top Employees (Total Attendance)")
    
    if not employee_stats.empty:
        top_emps = employee_stats.nlargest(10, "total_attendance")
        
        fig_top = px.bar(
            top_emps,
            x="total_attendance",
            y="name",
            orientation="h",
            title="",
            labels={"total_attendance": "Total Attendance Marks", "name": "Employee"},
            color="department",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_top.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=40),
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_top.update_traces(hovertemplate="%{y}<br>%{x} marks<br>Dept: %{customdata[0]}<extra></extra>",
                              customdata=top_emps[["department"]].values)
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No employee data available")

# 4. Recognition Accuracy Pie Chart
with chart_col4:
    st.markdown("#### Recognition Accuracy")
    
    if not recognition_df.empty:
        known = len(recognition_df[recognition_df["is_known"] == True])
        unknown = len(recognition_df[recognition_df["is_known"] == False])
        
        fig_pie = px.pie(
            values=[known, unknown],
            names=["Known Faces", "Unknown Faces"],
            title="",
            color_discrete_sequence=["#00cc88", "#ff4444"],
            hole=0.5,
        )
        fig_pie.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_pie.update_traces(
            textinfo="percent+label",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No recognition data in selected period")

# ── Charts Row 3: Department Distribution & Confidence Histogram ──
st.markdown("### 🏢 Department & Confidence Analysis")

chart_col5, chart_col6 = st.columns(2)

# 5. Department Distribution
with chart_col5:
    st.markdown("#### Attendance by Department")
    
    if not attendance_df.empty:
        dept_counts = attendance_df.groupby("department").size().reset_index(name="count")
        dept_counts = dept_counts.sort_values("count", ascending=False)
        
        fig_dept = px.pie(
            dept_counts,
            values="count",
            names="department",
            title="",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=0.4,
        )
        fig_dept.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_dept.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
        st.plotly_chart(fig_dept, use_container_width=True)
    else:
        st.info("No attendance data for department analysis")

# 6. Confidence Distribution Histogram
with chart_col6:
    st.markdown("#### Recognition Confidence Distribution")
    
    if not attendance_df.empty:
        fig_hist = px.histogram(
            attendance_df,
            x="confidence",
            nbins=20,
            title="",
            labels={"confidence": "Confidence Score", "count": "Frequency"},
            color_discrete_sequence=["#ffaa00"],
        )
        fig_hist.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Confidence",
            yaxis_title="Count",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_hist.update_traces(hovertemplate="Confidence: %{x:.2f}<br>Count: %{y}<extra></extra>")
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No confidence data available")

# ── Charts Row 4: Weekly Heatmap & Monthly Trend ───────────────
st.markdown("### 🔥 Advanced Visualizations")

adv_col1, adv_col2 = st.columns(2)

# 7. Weekly Heatmap (Day of Week vs Hour)
with adv_col1:
    st.markdown("#### Weekly Attendance Heatmap")
    
    if not attendance_df.empty:
        attendance_df["day_of_week"] = attendance_df["timestamp"].dt.dayofweek
        attendance_df["day_name"] = attendance_df["timestamp"].dt.day_name()
        
        heatmap_data = attendance_df.groupby(["day_name", "hour"]).size().reset_index(name="count")
        
        # Order days properly
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heatmap_data["day_name"] = pd.Categorical(heatmap_data["day_name"], categories=day_order, ordered=True)
        heatmap_data = heatmap_data.sort_values("day_name")
        
        # Create pivot table
        pivot = heatmap_data.pivot(index="day_name", columns="hour", values="count").fillna(0)
        # Reindex to ensure all days are present in order
        pivot = pivot.reindex(day_order).fillna(0)
        
        fig_heat = px.imshow(
            pivot.values,
            x=[str(h) for h in pivot.columns],
            y=pivot.index.tolist(),
            color_continuous_scale="Viridis",
            labels=dict(x="Hour", y="Day", color="Count"),
            aspect="auto",
        )
        fig_heat.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Not enough data for heatmap")

# 8. Monthly Trend Line
with adv_col2:
    st.markdown("#### Monthly Attendance Trend")
    
    if not attendance_df.empty:
        attendance_df["month"] = attendance_df["timestamp"].dt.to_period("M")
        monthly = attendance_df.groupby("month").size().reset_index(name="count")
        monthly["month_str"] = monthly["month"].astype(str)
        
        fig_month = px.line(
            monthly,
            x="month_str",
            y="count",
            markers=True,
            title="",
            labels={"month_str": "Month", "count": "Total Marks"},
            color_discrete_sequence=["#0088ff"],
        )
        fig_month.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Month",
            yaxis_title="Attendance Marks",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_month.update_traces(hovertemplate="%{x}<br>%{y} marks<extra></extra>")
        st.plotly_chart(fig_month, use_container_width=True)
    else:
        st.info("Not enough data for monthly trend")

# ── Raw Data Tables ────────────────────────────────────────────
with st.expander("📋 View Raw Data Tables"):
    tab1, tab2, tab3 = st.tabs(["Attendance Records", "Employee Stats", "Recognition Logs"])
    
    with tab1:
        if not attendance_df.empty:
            display_df = attendance_df.copy()
            display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No attendance records")
    
    with tab2:
        if not employee_stats.empty:
            display_emp = employee_stats.copy()
            display_emp["last_seen"] = display_emp["last_seen"].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "Never"
            )
            st.dataframe(display_emp, use_container_width=True, hide_index=True)
        else:
            st.info("No employee data")
    
    with tab3:
        if not recognition_df.empty:
            display_rec = recognition_df.copy()
            display_rec["timestamp"] = display_rec["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            display_rec["type"] = display_rec["is_known"].map({True: "Known", "False": "Unknown"})
            st.dataframe(display_rec[["timestamp", "type", "confidence", "employee_name"]], 
                        use_container_width=True, hide_index=True)
        else:
            st.info("No recognition logs")

# ── Export Section ─────────────────────────────────────────────
st.divider()
st.markdown("### 📤 Export Data")

exp_col1, exp_col2, exp_col3 = st.columns(3)

with exp_col1:
    if st.button("📥 Export Attendance (CSV)", use_container_width=True):
        if not attendance_df.empty:
            csv = attendance_df.to_csv(index=False)
            st.download_button(
                "Download Attendance CSV",
                csv,
                file_name=f"attendance_export_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

with exp_col2:
    if st.button("📥 Export Employees (CSV)", use_container_width=True):
        if not employee_stats.empty:
            csv = employee_stats.to_csv(index=False)
            st.download_button(
                "Download Employees",
                csv,
                file_name=f"employees_export_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

with exp_col3:
    if st.button("📥 Export Recognition Logs (CSV)", use_container_width=True):
        if not recognition_df.empty:
            csv = recognition_df.to_csv(index=False)
            st.download_button(
                "Download Recognition Logs",
                csv,
                file_name=f"recognition_logs_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ── Professional formats: PDF / Excel ─────────────────────────
exp_col4, exp_col5, exp_col6 = st.columns(3)

with exp_col4:
    if st.button("📕 Export Attendance (PDF)", use_container_width=True):
        if not attendance_df.empty:
            try:
                from services.report_service import ReportService, ReportUnavailableError
                rows = [
                    {
                        "Date": r["date"].strftime("%Y-%m-%d") if r.get("date") is not None else "",
                        "Time": r["timestamp"].strftime("%H:%M:%S") if r.get("timestamp") is not None else "",
                        "ID": r.get("employee_id", ""),
                        "Name": r.get("employee_name", ""),
                        "Department": r.get("department", ""),
                        "Confidence": f"{r.get('confidence', 0):.1%}" if r.get("confidence") is not None else "",
                    }
                    for r in attendance_df.to_dict("records")
                ]
                pdf = ReportService._pdf_table(
                    f"Attendance Report — Last {days_back} days",
                    ["Date", "Time", "ID", "Name", "Department", "Confidence"],
                    rows,
                    subtitle=f"{len(rows)} record(s) · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                )
                st.download_button(
                    "Download Attendance PDF",
                    pdf,
                    file_name=f"attendance_report_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except ReportUnavailableError as _exc:
                st.error(f"⚠️ {_exc}")

with exp_col5:
    if st.button("📗 Export Attendance (Excel)", use_container_width=True):
        if not attendance_df.empty:
            try:
                from services.report_service import ReportService, ReportUnavailableError
                rows = [
                    {
                        "Date": r["date"].strftime("%Y-%m-%d") if r.get("date") is not None else "",
                        "Time": r["timestamp"].strftime("%H:%M:%S") if r.get("timestamp") is not None else "",
                        "ID": r.get("employee_id", ""),
                        "Name": r.get("employee_name", ""),
                        "Department": r.get("department", ""),
                        "Confidence": f"{r.get('confidence', 0):.1%}" if r.get("confidence") is not None else "",
                    }
                    for r in attendance_df.to_dict("records")
                ]
                xlsx = ReportService._excel_table(
                    f"Attendance Report — Last {days_back} days",
                    ["Date", "Time", "ID", "Name", "Department", "Confidence"],
                    rows,
                    sheet_name="Attendance",
                )
                st.download_button(
                    "Download Attendance Excel",
                    xlsx,
                    file_name=f"attendance_report_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except ReportUnavailableError as _exc:
                st.error(f"⚠️ {_exc}")

with exp_col6:
    if st.button("📘 Export Employees (Excel)", use_container_width=True):
        if not employee_stats.empty:
            try:
                from services.report_service import ReportService, ReportUnavailableError
                rows = [
                    {
                        "ID": r.get("employee_id", ""),
                        "Name": r.get("name", ""),
                        "Department": r.get("department", ""),
                        "Total Marks": r.get("total_attendance", 0),
                    }
                    for r in employee_stats.to_dict("records")
                ]
                xlsx = ReportService._excel_table(
                    "Employee Directory",
                    ["ID", "Name", "Department", "Total Marks"],
                    rows,
                    sheet_name="Employees",
                )
                st.download_button(
                    "Download Employees Excel",
                    xlsx,
                    file_name=f"employees_report_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except ReportUnavailableError as _exc:
                st.error(f"⚠️ {_exc}")

# ── Technical Details ──────────────────────────────────────────
with st.expander("ℹ️ Data Sources & Technical Details"):
    st.markdown("""
    **Data Sources:**
    - **Attendance**: SQLite `attendance` table (via `AttendanceRepo`)
    - **Employees**: SQLite `employees` table (via `EmployeeRepo`)
    - **Recognition Logs**: SQLite `recognition_log` table (via `RecognitionLogRepo`)
    - **Unknown Faces**: SQLite `unknown_faces` table (via `UnknownFaceRepo`)
    
    **Pipeline Metrics:**
    - YOLO11 person detection → RetinaFace face detection → ArcFace embeddings → FAISS search
    - Recognition threshold: `cfg.RECOGNITION_THRESHOLD` (L2 distance)
    - YOLO confidence: `cfg.YOLO_CONFIDENCE`
    - Frame skip: `cfg.FRAME_SKIP` (process every Nth frame)
    
    **Chart Library:** Plotly (interactive, zoomable, hoverable)
    **Cache TTL:** 30 seconds for all data queries
    """)

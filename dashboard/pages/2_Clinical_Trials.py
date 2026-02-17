import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Indication, ClinicalTrial
from dashboard.components.charts import create_trial_timeline, create_phase_distribution

st.set_page_config(page_title="Clinical Trials - CI Tool", layout="wide")
st.title("Clinical Trials")

try:
    with get_session() as session:
        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            assets = session.query(Asset).all()
            asset_options = ["All Assets"] + [a.name for a in assets]
            selected_asset = st.selectbox("Asset", asset_options)

        with col2:
            indications = session.query(Indication).all()
            indication_options = ["All Indications"] + [i.name for i in indications]
            selected_indication = st.selectbox("Indication", indication_options)

        with col3:
            status_options = [
                "All Statuses",
                "NOT_YET_RECRUITING",
                "RECRUITING",
                "ENROLLING_BY_INVITATION",
                "ACTIVE_NOT_RECRUITING",
            ]
            selected_status = st.selectbox("Status", status_options)

        # Build query
        query = session.query(ClinicalTrial)

        if selected_asset != "All Assets":
            asset = session.query(Asset).filter_by(name=selected_asset).first()
            if asset:
                query = query.filter(ClinicalTrial.asset_id == asset.id)

        if selected_indication != "All Indications":
            indication = session.query(Indication).filter_by(name=selected_indication).first()
            if indication:
                query = query.filter(ClinicalTrial.indication_id == indication.id)

        if selected_status != "All Statuses":
            query = query.filter(ClinicalTrial.status == selected_status)

        trials = query.order_by(ClinicalTrial.start_date.desc()).all()

        st.divider()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Trials", len(trials))
        with col2:
            recruiting = len([t for t in trials if t.status == "RECRUITING"])
            st.metric("Recruiting", recruiting)
        with col3:
            completed = len([t for t in trials if t.status == "COMPLETED"])
            st.metric("Completed", completed)
        with col4:
            total_enrollment = sum(t.enrollment or 0 for t in trials)
            st.metric("Total Enrollment", f"{total_enrollment:,}")

        # Charts
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Phase Distribution")
            if trials:
                fig = create_phase_distribution(trials)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Trial Timeline")
            if trials:
                fig = create_trial_timeline(trials)
                st.plotly_chart(fig, use_container_width=True)

        # Trial table
        st.divider()
        st.subheader("Trial Details")

        if trials:
            df = pd.DataFrame([
                {
                    "NCT ID": t.nct_id,
                    "Title": t.title[:80] + "..." if len(t.title or "") > 80 else t.title,
                    "Phase": t.phase,
                    "Status": t.status,
                    "Sponsor": t.sponsor,
                    "Enrollment": t.enrollment,
                    "Start Date": t.start_date.strftime("%Y-%m-%d") if t.start_date else "N/A",
                }
                for t in trials
            ])

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "NCT ID": st.column_config.LinkColumn(
                        "NCT ID",
                        help="Click to view on ClinicalTrials.gov",
                        display_text=None,
                    ),
                },
            )

            # Detailed view
            st.divider()
            st.subheader("Trial Details")
            selected_nct = st.selectbox("Select trial for details", [t.nct_id for t in trials])

            trial = next((t for t in trials if t.nct_id == selected_nct), None)
            if trial:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Title:** {trial.title}")
                    st.markdown(f"**NCT ID:** [{trial.nct_id}]({trial.source_url})")
                    st.markdown(f"**Phase:** {trial.phase or 'N/A'}")
                    st.markdown(f"**Status:** {trial.status or 'N/A'}")
                with col2:
                    st.markdown(f"**Sponsor:** {trial.sponsor or 'N/A'}")
                    st.markdown(f"**Enrollment:** {trial.enrollment or 'N/A'}")
                    st.markdown(f"**Start:** {trial.start_date or 'N/A'}")
                    st.markdown(f"**Completion:** {trial.completion_date or 'N/A'}")

                if trial.primary_endpoint:
                    st.markdown("**Primary Endpoint:**")
                    st.info(trial.primary_endpoint)
        else:
            st.info("No trials found matching the filters.")

except Exception as e:
    st.error(f"Error: {e}")

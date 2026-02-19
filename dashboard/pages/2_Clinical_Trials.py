import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Indication, ClinicalTrial, ClinicalTrialChange
from dashboard.components.charts import create_phase_distribution, create_trial_starts_by_year

st.set_page_config(page_title="Clinical Trials - CI Tool", layout="wide")
st.title("Clinical Trials")


def _get_interventions(trial):
    """Extract intervention names from trial raw_data."""
    if not trial.raw_data:
        return ""
    arms = trial.raw_data.get("protocolSection", {}).get("armsInterventionsModule", {})
    names = [i.get("name", "") for i in arms.get("interventions", [])]
    return ", ".join(names[:3])


try:
    with get_session() as session:
        assets = session.query(Asset).all()

        if not assets:
            st.info("No assets configured. Add assets to the database to see trial data.")
            st.stop()

        # Build indication lookup once
        all_indications = {i.id: i for i in session.query(Indication).all()}

        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # ── Per-asset sections ──────────────────────────────────────
        for asset in assets:
            st.header(asset.name)

            # ── Filters ─────────────────────────────────────────────
            fcol1, fcol2, fcol3 = st.columns(3)

            with fcol1:
                view_mode = st.selectbox(
                    "View Mode",
                    ["All", "Target / Biomarker", "Indication"],
                    key=f"view_mode_{asset.id}",
                )

            with fcol2:
                # Get indications linked to this asset's trials
                asset_indication_ids = (
                    session.query(ClinicalTrial.indication_id)
                    .filter(
                        ClinicalTrial.asset_id == asset.id,
                        ClinicalTrial.indication_id.isnot(None),
                    )
                    .distinct()
                    .all()
                )
                asset_indications = [
                    all_indications[iid[0]]
                    for iid in asset_indication_ids
                    if iid[0] in all_indications
                ]

                if view_mode == "Target / Biomarker":
                    st.selectbox(
                        "Indication",
                        ["All Indications"],
                        disabled=True,
                        key=f"indication_disabled_{asset.id}",
                    )
                    selected_indication = "All Indications"
                else:
                    indication_options = ["All Indications"] + [
                        i.name for i in asset_indications
                    ]
                    selected_indication = st.selectbox(
                        "Indication",
                        indication_options,
                        key=f"indication_{asset.id}",
                    )

            with fcol3:
                status_options = [
                    "All Statuses",
                    "NOT_YET_RECRUITING",
                    "RECRUITING",
                    "ENROLLING_BY_INVITATION",
                    "ACTIVE_NOT_RECRUITING",
                ]
                selected_status = st.selectbox(
                    "Status",
                    status_options,
                    key=f"status_{asset.id}",
                )

            # ── Query ───────────────────────────────────────────────
            query = session.query(ClinicalTrial).filter(
                ClinicalTrial.asset_id == asset.id
            )

            if view_mode == "Target / Biomarker":
                query = query.filter(ClinicalTrial.search_type == "target")
            elif view_mode == "Indication":
                query = query.filter(ClinicalTrial.search_type == "indication")

            if selected_indication != "All Indications":
                ind = next(
                    (i for i in asset_indications if i.name == selected_indication),
                    None,
                )
                if ind:
                    query = query.filter(ClinicalTrial.indication_id == ind.id)

            if selected_status != "All Statuses":
                query = query.filter(ClinicalTrial.status == selected_status)

            trials = query.order_by(ClinicalTrial.start_date.desc()).all()

            # Deduplicate for "All" mode
            if view_mode == "All":
                seen = {}
                for t in trials:
                    if t.nct_id not in seen:
                        seen[t.nct_id] = t
                trials = list(seen.values())

            # ── KPIs ────────────────────────────────────────────────
            st.divider()
            kcol1, kcol2, kcol3 = st.columns(3)
            with kcol1:
                st.metric("Total Active Trials", len(trials))
            with kcol2:
                recruiting = len([t for t in trials if t.status == "RECRUITING"])
                st.metric("Recruiting", recruiting)
            with kcol3:
                total_enrollment = sum(t.enrollment or 0 for t in trials)
                st.metric("Total Enrollment", f"{total_enrollment:,}")

            # ── Charts ──────────────────────────────────────────────
            st.divider()
            ccol1, ccol2 = st.columns(2)

            with ccol1:
                st.subheader("Phase Distribution")
                if trials:
                    fig = create_phase_distribution(trials)
                    st.plotly_chart(fig, use_container_width=True, key=f"phase_{asset.id}")
                else:
                    st.info("No trials to display.")

            with ccol2:
                st.subheader("Trial Starts by Year")
                if trials:
                    fig = create_trial_starts_by_year(trials)
                    st.plotly_chart(fig, use_container_width=True, key=f"starts_{asset.id}")
                else:
                    st.info("No trials to display.")

            # ── New & Changed Trials (Last 7 Days) ──────────────────
            st.divider()
            st.subheader("New & Changed Trials (Last 7 Days)")

            # New trials
            new_trials = [t for t in trials if t.fetched_at >= seven_days_ago]

            if new_trials:
                st.markdown(f"**New Trials** ({len(new_trials)})")
                new_df = pd.DataFrame([
                    {
                        "NCT ID": t.source_url,
                        "Title": (t.title[:70] + "...") if len(t.title or "") > 70 else t.title,
                        "Phase": t.phase or "—",
                        "Status": t.status or "—",
                        "Sponsor": t.sponsor or "—",
                        "Intervention": _get_interventions(t),
                        "Start Date": t.start_date.strftime("%Y-%m-%d") if t.start_date else "—",
                    }
                    for t in new_trials
                ])
                st.dataframe(
                    new_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "NCT ID": st.column_config.LinkColumn("NCT ID"),
                    },
                    key=f"new_trials_{asset.id}",
                )
            else:
                st.info("No new trials in the last 7 days.")

            # Changed trials
            trial_nct_ids = [t.nct_id for t in trials]
            trial_lookup = {t.nct_id: t for t in trials}

            changes = []
            if trial_nct_ids:
                changes = (
                    session.query(ClinicalTrialChange)
                    .filter(
                        ClinicalTrialChange.nct_id.in_(trial_nct_ids),
                        ClinicalTrialChange.detected_at >= seven_days_ago,
                    )
                    .order_by(ClinicalTrialChange.detected_at.desc())
                    .all()
                )

            if changes:
                st.markdown(f"**Changed Trials** ({len(changes)})")
                change_rows = []
                for c in changes:
                    t = trial_lookup.get(c.nct_id)
                    change_rows.append({
                        "NCT ID": t.source_url if t else c.nct_id,
                        "Title": ((t.title[:70] + "...") if len(t.title or "") > 70 else t.title) if t else "—",
                        "Change Type": c.field_name,
                        "Old → New": f"{c.old_value or '—'} → {c.new_value or '—'}",
                        "Change Date": c.detected_at.strftime("%Y-%m-%d %H:%M") if c.detected_at else "—",
                        "Sponsor": (t.sponsor or "—") if t else "—",
                        "Intervention": _get_interventions(t) if t else "—",
                    })
                change_df = pd.DataFrame(change_rows)
                st.dataframe(
                    change_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "NCT ID": st.column_config.LinkColumn("NCT ID"),
                    },
                    key=f"changed_trials_{asset.id}",
                )
            else:
                st.info("No trial changes detected in the last 7 days.")

            st.divider()

except Exception as e:
    st.error(f"Error: {e}")

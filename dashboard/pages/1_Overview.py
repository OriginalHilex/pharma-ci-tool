import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Company, Indication, AssetIndication
from dashboard.components.charts import create_pipeline_chart

st.set_page_config(page_title="Overview - CI Tool", layout="wide")
st.title("Asset Overview")

try:
    with get_session() as session:
        # Asset selector
        assets = session.query(Asset).all()
        asset_names = [a.name for a in assets]

        if not asset_names:
            st.warning("No assets in database. Run seed_data.py first.")
            st.stop()

        selected_asset = st.selectbox("Select Asset", asset_names)

        asset = session.query(Asset).filter_by(name=selected_asset).first()
        if not asset:
            st.error("Asset not found")
            st.stop()

        # Asset details
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"{asset.name}")
            st.markdown(f"**Company:** {asset.company.name if asset.company else 'N/A'}")
            st.markdown(f"**Generic Name:** {asset.generic_name or 'N/A'}")
            st.markdown(f"**Stage:** {asset.stage or 'N/A'}")

            if asset.mechanism_of_action:
                st.markdown("**Mechanism of Action:**")
                st.info(asset.mechanism_of_action)

        with col2:
            st.subheader("Indications")
            for ai in asset.indications:
                status_color = "🟢" if ai.status == "Approved" else "🟡" if "Phase" in (ai.status or "") else "⚪"
                st.markdown(f"{status_color} **{ai.indication.name}**")
                if ai.status:
                    st.caption(f"Status: {ai.status}")

        st.divider()

        # Quick stats
        st.subheader("Activity Summary")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            trial_count = len(asset.clinical_trials)
            st.metric("Clinical Trials", trial_count)

        with col2:
            pub_count = len(asset.publications)
            st.metric("Publications", pub_count)

        with col3:
            news_count = len(asset.news_articles)
            st.metric("News Articles", news_count)

        with col4:
            patent_count = len(asset.patents)
            st.metric("Patents", patent_count)

        # Pipeline visualization
        st.divider()
        st.subheader("Trial Pipeline")

        if asset.clinical_trials:
            fig = create_pipeline_chart(asset.clinical_trials)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No clinical trials data available yet.")

except Exception as e:
    st.error(f"Error: {e}")

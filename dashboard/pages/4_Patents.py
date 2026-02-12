import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Patent
from dashboard.components.charts import create_patent_timeline

st.set_page_config(page_title="Patents - CI Tool", layout="wide")
st.title("Patent Monitoring")

try:
    with get_session() as session:
        # Filters
        col1, col2 = st.columns(2)

        with col1:
            assets = session.query(Asset).all()
            asset_options = ["All Assets"] + [a.name for a in assets]
            selected_asset = st.selectbox("Asset", asset_options)

        with col2:
            sort_options = ["Filing Date (Newest)", "Filing Date (Oldest)", "Grant Date"]
            selected_sort = st.selectbox("Sort By", sort_options)

        # Build query
        query = session.query(Patent)

        if selected_asset != "All Assets":
            asset = session.query(Asset).filter_by(name=selected_asset).first()
            if asset:
                query = query.filter(Patent.asset_id == asset.id)

        if selected_sort == "Filing Date (Newest)":
            query = query.order_by(Patent.filing_date.desc())
        elif selected_sort == "Filing Date (Oldest)":
            query = query.order_by(Patent.filing_date.asc())
        else:
            query = query.order_by(Patent.grant_date.desc())

        patents = query.all()

        st.divider()

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Patents", len(patents))
        with col2:
            granted = len([p for p in patents if p.grant_date])
            st.metric("Granted", granted)
        with col3:
            assignees = set(p.assignee for p in patents if p.assignee)
            st.metric("Unique Assignees", len(assignees))

        # Timeline chart
        st.divider()
        st.subheader("Patent Filing Timeline")

        if patents:
            fig = create_patent_timeline(patents)
            st.plotly_chart(fig, use_container_width=True)

        # Patent table
        st.divider()
        st.subheader("Patent Details")

        if patents:
            df = pd.DataFrame([
                {
                    "Patent #": p.patent_number,
                    "Title": p.title[:60] + "..." if len(p.title or "") > 60 else p.title,
                    "Assignee": p.assignee or "N/A",
                    "Filing Date": p.filing_date.strftime("%Y-%m-%d") if p.filing_date else "N/A",
                    "Grant Date": p.grant_date.strftime("%Y-%m-%d") if p.grant_date else "Pending",
                    "Claims": p.claims_count or "N/A",
                }
                for p in patents
            ])

            st.dataframe(df, use_container_width=True, hide_index=True)

            # Detailed view
            st.divider()
            selected_patent = st.selectbox(
                "Select patent for details",
                [p.patent_number for p in patents]
            )

            patent = next((p for p in patents if p.patent_number == selected_patent), None)
            if patent:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Title:** {patent.title}")
                    st.markdown(f"**Patent #:** [{patent.patent_number}]({patent.source_url})")
                    st.markdown(f"**Assignee:** {patent.assignee or 'N/A'}")
                with col2:
                    st.markdown(f"**Filing Date:** {patent.filing_date or 'N/A'}")
                    st.markdown(f"**Grant Date:** {patent.grant_date or 'Pending'}")
                    st.markdown(f"**Claims:** {patent.claims_count or 'N/A'}")

                if patent.abstract:
                    st.markdown("**Abstract:**")
                    st.info(patent.abstract)
        else:
            st.info("No patents found. Run the collectors to fetch patent data.")

        # Assignee breakdown
        st.divider()
        st.subheader("Patents by Assignee")

        if patents:
            assignee_counts = {}
            for p in patents:
                assignee = p.assignee or "Unknown"
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

            df = pd.DataFrame([
                {"Assignee": k, "Patents": v}
                for k, v in sorted(assignee_counts.items(), key=lambda x: -x[1])
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")

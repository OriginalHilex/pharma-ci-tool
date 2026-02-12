import streamlit as st
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_session
from database.models import Company, Asset, Indication, ClinicalTrial, NewsArticle

st.set_page_config(
    page_title="Pharma CI Tool",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Competitive Intelligence Dashboard")
st.markdown("Track competitor drugs, clinical trials, news, and patents in biotech/pharma.")

# Sidebar navigation info
st.sidebar.title("Navigation")
st.sidebar.info(
    """
    Use the pages in the sidebar to navigate:
    - **Overview**: Asset summary and key metrics
    - **Clinical Trials**: Trial comparisons and status
    - **News**: Latest news articles
    - **Patents**: Patent filings and grants
    """
)

# Main page content - Summary metrics
st.header("Summary")

try:
    with get_session() as session:
        # Count metrics
        company_count = session.query(Company).count()
        asset_count = session.query(Asset).count()
        indication_count = session.query(Indication).count()
        trial_count = session.query(ClinicalTrial).count()
        news_count = session.query(NewsArticle).count()

        # Display metrics in columns
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Companies", company_count)
        with col2:
            st.metric("Assets", asset_count)
        with col3:
            st.metric("Indications", indication_count)
        with col4:
            st.metric("Clinical Trials", trial_count)
        with col5:
            st.metric("News Articles", news_count)

        st.divider()

        # Tracked Assets
        st.subheader("Tracked Assets")

        assets = session.query(Asset).all()
        if assets:
            for asset in assets:
                with st.expander(f"**{asset.name}** ({asset.company.name if asset.company else 'Unknown'})"):
                    st.markdown(f"**Generic Name:** {asset.generic_name or 'N/A'}")
                    st.markdown(f"**Mechanism:** {asset.mechanism_of_action or 'N/A'}")
                    st.markdown(f"**Stage:** {asset.stage or 'N/A'}")

                    # Show associated indications
                    indications = [ai.indication.name for ai in asset.indications]
                    if indications:
                        st.markdown(f"**Indications:** {', '.join(indications)}")

                    # Quick stats for this asset
                    trial_ct = session.query(ClinicalTrial).filter_by(asset_id=asset.id).count()
                    news_ct = session.query(NewsArticle).filter_by(asset_id=asset.id).count()
                    st.markdown(f"📋 {trial_ct} trials | 📰 {news_ct} news articles")
        else:
            st.info("No assets tracked yet. Run the seed script to add initial data.")

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure to configure DATABASE_URL in .env and run init_db.py")

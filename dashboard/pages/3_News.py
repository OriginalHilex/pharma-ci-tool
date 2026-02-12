import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, NewsArticle

st.set_page_config(page_title="News - CI Tool", layout="wide")
st.title("News Feed")

try:
    with get_session() as session:
        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            assets = session.query(Asset).all()
            asset_options = ["All Assets"] + [a.name for a in assets]
            selected_asset = st.selectbox("Asset", asset_options)

        with col2:
            date_options = {
                "Last 7 days": 7,
                "Last 30 days": 30,
                "Last 90 days": 90,
                "All time": None,
            }
            selected_date = st.selectbox("Time Period", list(date_options.keys()))

        with col3:
            sort_options = ["Newest First", "Oldest First"]
            selected_sort = st.selectbox("Sort", sort_options)

        # Build query
        query = session.query(NewsArticle)

        if selected_asset != "All Assets":
            asset = session.query(Asset).filter_by(name=selected_asset).first()
            if asset:
                query = query.filter(NewsArticle.asset_id == asset.id)

        days = date_options[selected_date]
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(NewsArticle.published_at >= cutoff)

        if selected_sort == "Newest First":
            query = query.order_by(NewsArticle.published_at.desc())
        else:
            query = query.order_by(NewsArticle.published_at.asc())

        articles = query.limit(100).all()

        st.divider()

        # Metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Articles Found", len(articles))
        with col2:
            sources = set(a.source for a in articles if a.source)
            st.metric("Unique Sources", len(sources))

        st.divider()

        # News cards
        if articles:
            for article in articles:
                with st.container():
                    col1, col2 = st.columns([4, 1])

                    with col1:
                        st.markdown(f"### [{article.title}]({article.url})")
                        if article.summary:
                            st.markdown(article.summary[:300] + "..." if len(article.summary) > 300 else article.summary)

                    with col2:
                        if article.source:
                            st.caption(f"📰 {article.source}")
                        if article.published_at:
                            st.caption(f"📅 {article.published_at.strftime('%Y-%m-%d')}")

                        # Find associated asset
                        if article.asset:
                            st.caption(f"💊 {article.asset.name}")

                    st.divider()
        else:
            st.info("No news articles found. Run the collectors to fetch news.")

        # Source breakdown
        st.subheader("Sources")
        if articles:
            source_counts = {}
            for a in articles:
                source = a.source or "Unknown"
                source_counts[source] = source_counts.get(source, 0) + 1

            df = pd.DataFrame([
                {"Source": k, "Articles": v}
                for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")

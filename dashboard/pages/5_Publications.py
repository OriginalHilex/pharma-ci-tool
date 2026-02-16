import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Publication

st.set_page_config(page_title="Publications - CI Tool", layout="wide")
st.title("PubMed Publications")

try:
    with get_session() as session:
        # Filters
        col1, col2 = st.columns(2)

        with col1:
            assets = session.query(Asset).all()
            asset_options = ["All Assets"] + [a.name for a in assets]
            selected_asset = st.selectbox("Asset", asset_options)

        with col2:
            sort_options = [
                "Publication Date (Newest)",
                "Publication Date (Oldest)",
                "Journal",
            ]
            selected_sort = st.selectbox("Sort By", sort_options)

        # Build query
        query = session.query(Publication)

        if selected_asset != "All Assets":
            asset = session.query(Asset).filter_by(name=selected_asset).first()
            if asset:
                query = query.filter(Publication.asset_id == asset.id)

        if selected_sort == "Publication Date (Newest)":
            query = query.order_by(Publication.publication_date.desc())
        elif selected_sort == "Publication Date (Oldest)":
            query = query.order_by(Publication.publication_date.asc())
        else:
            query = query.order_by(Publication.journal.asc())

        publications = query.all()

        st.divider()

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Publications", len(publications))
        with col2:
            journals = set(p.journal for p in publications if p.journal)
            st.metric("Unique Journals", len(journals))
        with col3:
            authors_set = set()
            for p in publications:
                if p.authors:
                    for author in p.authors.split(", "):
                        authors_set.add(author.strip())
            st.metric("Unique Authors", len(authors_set))

        # Publications table
        st.divider()
        st.subheader("Publications")

        if publications:
            df = pd.DataFrame([
                {
                    "PMID": p.pmid,
                    "Title": p.title[:80] + "..." if len(p.title or "") > 80 else p.title,
                    "Authors": (p.authors[:50] + "...") if p.authors and len(p.authors) > 50 else (p.authors or "N/A"),
                    "Journal": p.journal or "N/A",
                    "Date": p.publication_date.strftime("%Y-%m-%d") if p.publication_date else "N/A",
                    "DOI": p.doi or "N/A",
                }
                for p in publications
            ])

            st.dataframe(df, use_container_width=True, hide_index=True)

            # Detail view
            st.divider()
            selected_pub = st.selectbox(
                "Select publication for details",
                [p.pmid for p in publications],
                format_func=lambda pmid: next(
                    (f"{pmid} — {p.title[:60]}" for p in publications if p.pmid == pmid),
                    pmid,
                ),
            )

            pub = next((p for p in publications if p.pmid == selected_pub), None)
            if pub:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Title:** {pub.title}")
                    st.markdown(f"**PMID:** [{pub.pmid}]({pub.source_url})")
                    st.markdown(f"**Authors:** {pub.authors or 'N/A'}")
                with col2:
                    st.markdown(f"**Journal:** {pub.journal or 'N/A'}")
                    st.markdown(f"**Date:** {pub.publication_date or 'N/A'}")
                    if pub.doi:
                        st.markdown(f"**DOI:** [{pub.doi}](https://doi.org/{pub.doi})")
                    else:
                        st.markdown("**DOI:** N/A")

                if pub.abstract:
                    st.markdown("**Abstract:**")
                    st.info(pub.abstract)
        else:
            st.info("No publications found. Run the collectors to fetch PubMed data.")

        # Journal breakdown
        st.divider()
        st.subheader("Publications by Journal")

        if publications:
            journal_counts = {}
            for p in publications:
                journal = p.journal or "Unknown"
                journal_counts[journal] = journal_counts.get(journal, 0) + 1

            df = pd.DataFrame([
                {"Journal": k, "Publications": v}
                for k, v in sorted(journal_counts.items(), key=lambda x: -x[1])
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")

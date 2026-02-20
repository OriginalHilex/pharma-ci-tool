import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.connection import get_session
from database.models import Asset, Indication, Publication
from dashboard.components.charts import create_publications_by_year

st.set_page_config(page_title="Publications - CI Tool", layout="wide")
st.title("PubMed Publications")


try:
    with get_session() as session:
        assets = session.query(Asset).all()

        if not assets:
            st.info("No assets configured. Add assets to the database to see publication data.")
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
                    key=f"pub_view_mode_{asset.id}",
                )

            with fcol2:
                # Get indications linked to this asset's publications
                asset_indication_ids = (
                    session.query(Publication.indication_id)
                    .filter(
                        Publication.asset_id == asset.id,
                        Publication.indication_id.isnot(None),
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
                        key=f"pub_indication_disabled_{asset.id}",
                    )
                    selected_indication = "All Indications"
                else:
                    indication_options = ["All Indications"] + [
                        i.name for i in asset_indications
                    ]
                    selected_indication = st.selectbox(
                        "Indication",
                        indication_options,
                        key=f"pub_indication_{asset.id}",
                    )

            with fcol3:
                time_options = {
                    "Last 7 days": 7,
                    "Last 30 days": 30,
                    "Last 90 days": 90,
                    "All time": None,
                }
                selected_time = st.selectbox(
                    "Time Period",
                    list(time_options.keys()),
                    index=3,
                    key=f"pub_time_{asset.id}",
                )

            # ── Query ───────────────────────────────────────────────
            query = session.query(Publication).filter(
                Publication.asset_id == asset.id
            )

            if view_mode == "Target / Biomarker":
                query = query.filter(Publication.search_type == "target")
            elif view_mode == "Indication":
                query = query.filter(Publication.search_type == "indication")

            if selected_indication != "All Indications":
                ind = next(
                    (i for i in asset_indications if i.name == selected_indication),
                    None,
                )
                if ind:
                    query = query.filter(Publication.indication_id == ind.id)

            all_pubs = query.order_by(Publication.publication_date.desc()).all()

            # Deduplicate for "All" mode
            if view_mode == "All":
                seen = {}
                for p in all_pubs:
                    if p.pmid not in seen:
                        seen[p.pmid] = p
                all_pubs = list(seen.values())

            # Apply timeframe filter (chart always uses all_pubs for full 10-year view)
            time_days = time_options[selected_time]
            if time_days:
                cutoff = datetime.utcnow() - timedelta(days=time_days)
                publications = [
                    p for p in all_pubs
                    if p.publication_date and p.publication_date >= cutoff.date()
                ]
            else:
                publications = all_pubs

            # ── KPIs ────────────────────────────────────────────────
            st.divider()
            kcol1, kcol2, kcol3 = st.columns(3)
            with kcol1:
                st.metric("Total Publications", len(publications))
            with kcol2:
                journals = set(p.journal for p in publications if p.journal)
                st.metric("Unique Journals", len(journals))
            with kcol3:
                new_pubs = len([p for p in publications if p.fetched_at >= seven_days_ago])
                st.metric("New (Last 7 Days)", new_pubs)

            # ── Charts ──────────────────────────────────────────────
            st.divider()
            st.subheader("Publications by Year")
            if all_pubs:
                fig = create_publications_by_year(all_pubs)
                st.plotly_chart(fig, use_container_width=True, key=f"pub_year_{asset.id}")
            else:
                st.info("No publications to display.")

            # ── Publications Table ──────────────────────────────────
            st.divider()
            st.subheader("Publications")

            if publications:
                df = pd.DataFrame([
                    {
                        "PMID": p.source_url,
                        "Title": (p.title[:80] + "...") if len(p.title or "") > 80 else p.title,
                        "Authors": (p.authors[:50] + "...") if p.authors and len(p.authors) > 50 else (p.authors or "—"),
                        "Journal": p.journal or "—",
                        "Date": p.publication_date.strftime("%Y-%m-%d") if p.publication_date else "—",
                        "DOI": f"https://doi.org/{p.doi}" if p.doi else "—",
                    }
                    for p in publications
                ])
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "PMID": st.column_config.LinkColumn("PMID"),
                        "DOI": st.column_config.LinkColumn("DOI"),
                    },
                    key=f"pub_table_{asset.id}",
                )
            else:
                st.info("No publications found. Run the collectors to fetch PubMed data.")

            st.divider()

except Exception as e:
    st.error(f"Error: {e}")

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from collections import Counter


def create_pipeline_chart(trials):
    """Create a pipeline visualization showing trials by phase and status."""
    phase_order = ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"]

    data = []
    for trial in trials:
        phase = trial.phase or "NA"
        # Normalize phase names
        phase = phase.upper().replace(" ", "").replace("PHASE", "PHASE")
        if phase not in phase_order:
            phase = "NA"

        data.append({
            "Phase": phase,
            "Status": trial.status or "Unknown",
            "Trial": trial.nct_id,
        })

    if not data:
        return go.Figure()

    df = pd.DataFrame(data)
    counts = df.groupby(["Phase", "Status"]).size().reset_index(name="Count")

    fig = px.bar(
        counts,
        x="Phase",
        y="Count",
        color="Status",
        title="Trial Pipeline by Phase",
        category_orders={"Phase": phase_order},
        color_discrete_map={
            "RECRUITING": "#2ecc71",
            "ACTIVE_NOT_RECRUITING": "#f1c40f",
            "COMPLETED": "#3498db",
            "TERMINATED": "#e74c3c",
            "WITHDRAWN": "#95a5a6",
        },
    )

    fig.update_layout(
        xaxis_title="Phase",
        yaxis_title="Number of Trials",
        legend_title="Status",
        bargap=0.2,
    )

    return fig


def create_trial_timeline(trials):
    """Create a timeline visualization of trials."""
    data = []
    for trial in trials:
        if trial.start_date:
            data.append({
                "Trial": trial.nct_id[:20],
                "Start": trial.start_date,
                "End": trial.completion_date or pd.Timestamp.now(),
                "Phase": trial.phase or "Unknown",
                "Status": trial.status or "Unknown",
            })

    if not data:
        return go.Figure()

    df = pd.DataFrame(data)
    df = df.sort_values("Start")

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="End",
        y="Trial",
        color="Phase",
        title="Trial Timeline",
        hover_data=["Status"],
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="",
        showlegend=True,
    )

    return fig


def create_phase_distribution(trials):
    """Create a pie chart of trial phase distribution."""
    phases = [t.phase or "Unknown" for t in trials]
    phase_counts = Counter(phases)

    fig = px.pie(
        values=list(phase_counts.values()),
        names=list(phase_counts.keys()),
        title="Trials by Phase",
        hole=0.4,
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")

    return fig


def create_patent_timeline(patents):
    """Create a timeline of patent filings."""
    data = []
    for patent in patents:
        if patent.filing_date:
            data.append({
                "Patent": patent.patent_number,
                "Date": patent.filing_date,
                "Type": "Filed",
                "Assignee": patent.assignee or "Unknown",
            })
        if patent.grant_date:
            data.append({
                "Patent": patent.patent_number,
                "Date": patent.grant_date,
                "Type": "Granted",
                "Assignee": patent.assignee or "Unknown",
            })

    if not data:
        return go.Figure()

    df = pd.DataFrame(data)
    df = df.sort_values("Date")

    fig = px.scatter(
        df,
        x="Date",
        y="Assignee",
        color="Type",
        symbol="Type",
        title="Patent Timeline",
        hover_data=["Patent"],
        color_discrete_map={"Filed": "#3498db", "Granted": "#2ecc71"},
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Assignee",
        showlegend=True,
    )

    return fig

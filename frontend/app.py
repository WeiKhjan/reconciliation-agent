"""
Reconciliation Agent - Streamlit Frontend
"""
import streamlit as st
import pandas as pd
import time
import json
from utils.api_client import api_client

# Page configuration
st.set_page_config(
    page_title="Reconciliation Agent",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stProgress .st-bo {
        background-color: #00cc66;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "step" not in st.session_state:
    st.session_state.step = 1
if "upload_complete" not in st.session_state:
    st.session_state.upload_complete = False
if "reconciliation_complete" not in st.session_state:
    st.session_state.reconciliation_complete = False
if "results" not in st.session_state:
    st.session_state.results = None
if "accepted" not in st.session_state:
    st.session_state.accepted = False


def reset_session():
    """Reset the session state."""
    st.session_state.session_id = None
    st.session_state.step = 1
    st.session_state.upload_complete = False
    st.session_state.reconciliation_complete = False
    st.session_state.results = None
    st.session_state.accepted = False


# Sidebar
with st.sidebar:
    st.title("Reconciliation Agent")
    st.markdown("---")

    # Check backend health
    health = api_client.health_check()
    if health.get("status") == "healthy":
        st.success("Backend: Connected")
        st.caption(f"Model: {health.get('model', 'N/A')}")
    else:
        st.error("Backend: Disconnected")
        st.caption(health.get("error", ""))

    st.markdown("---")

    # Progress tracker
    st.subheader("Progress")
    steps = ["Upload Data", "Reconcile", "Review", "Export"]
    for i, step_name in enumerate(steps, 1):
        if i < st.session_state.step:
            st.markdown(f" {step_name}")
        elif i == st.session_state.step:
            st.markdown(f" **{step_name}**")
        else:
            st.markdown(f" {step_name}")

    st.markdown("---")

    if st.button("Start New Session", use_container_width=True):
        reset_session()
        st.rerun()


# Main content
st.title("AI-Powered Reconciliation Agent")

# Step 1: Upload Data
if st.session_state.step == 1:
    st.header("Step 1: Upload Datasets")
    st.markdown("""
    Upload two datasets to reconcile:
    - **Dataset A**: Source dataset (e.g., Statement of Account)
    - **Dataset B**: Target dataset (e.g., Line by Line transactions)

    Supported formats: CSV, Excel (.xlsx, .xls), PDF
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dataset A (Source)")
        file_a = st.file_uploader(
            "Upload SOA or Bank Statement",
            type=["csv", "xlsx", "xls", "pdf"],
            key="file_a"
        )
        if file_a:
            st.success(f"Uploaded: {file_a.name}")

    with col2:
        st.subheader("Dataset B (Target)")
        file_b = st.file_uploader(
            "Upload LBL or Transaction Records",
            type=["csv", "xlsx", "xls", "pdf"],
            key="file_b"
        )
        if file_b:
            st.success(f"Uploaded: {file_b.name}")

    st.markdown("---")

    # Optional hint
    st.subheader("Optional: Provide a Hint")
    hint = st.text_area(
        "Describe how these datasets should be reconciled (optional)",
        placeholder="e.g., Match by RFX or MY reference numbers. Dataset A has references embedded in the Narration field.",
        key="hint"
    )

    # Upload button
    if st.button("Upload and Continue", disabled=not (file_a and file_b), use_container_width=True, type="primary"):
        with st.spinner("Creating session and uploading files..."):
            try:
                # Create session
                session_response = api_client.create_session()
                st.session_state.session_id = session_response["session_id"]

                # Upload files
                upload_response = api_client.upload_files(
                    st.session_state.session_id,
                    (file_a.name, file_a.getvalue(), file_a.type or "application/octet-stream"),
                    (file_b.name, file_b.getvalue(), file_b.type or "application/octet-stream")
                )

                st.session_state.upload_response = upload_response
                st.session_state.hint = hint
                st.session_state.upload_complete = True
                st.session_state.step = 2
                st.success("Files uploaded successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Upload failed: {e}")

# Step 2: Reconcile
elif st.session_state.step == 2:
    st.header("Step 2: Run Reconciliation")

    # Show data previews
    if hasattr(st.session_state, 'upload_response'):
        upload = st.session_state.upload_response

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"Dataset A: {upload['dataset_a']['filename']}")
            st.caption(f"{upload['preview_a']['total_rows']} rows, {len(upload['preview_a']['columns'])} columns")
            preview_df_a = pd.DataFrame(upload['preview_a']['sample_rows'])
            st.dataframe(preview_df_a, use_container_width=True, height=300)

        with col2:
            st.subheader(f"Dataset B: {upload['dataset_b']['filename']}")
            st.caption(f"{upload['preview_b']['total_rows']} rows, {len(upload['preview_b']['columns'])} columns")
            preview_df_b = pd.DataFrame(upload['preview_b']['sample_rows'])
            st.dataframe(preview_df_b, use_container_width=True, height=300)

    st.markdown("---")

    # Start reconciliation button
    if st.button("Start Reconciliation", use_container_width=True, type="primary"):
        with st.spinner("Starting reconciliation..."):
            try:
                api_client.start_reconciliation(
                    st.session_state.session_id,
                    st.session_state.get("hint")
                )

                # Poll for status
                progress_bar = st.progress(0)
                status_text = st.empty()
                reasoning_container = st.container()

                max_polls = 180  # 3 minutes max
                poll_count = 0

                while poll_count < max_polls:
                    status = api_client.get_status(st.session_state.session_id)

                    current_status = status.get("status", "unknown")
                    iteration = status.get("iteration", 0)
                    max_iter = status.get("max_iterations", 5)
                    match_rate = status.get("match_rate", 0)

                    # Update progress
                    progress = min((iteration / max_iter) * 100, 100)
                    progress_bar.progress(int(progress))

                    status_text.markdown(f"""
                    **Status**: {current_status.replace('_', ' ').title()}
                    | **Iteration**: {iteration}/{max_iter}
                    | **Match Rate**: {match_rate:.1%}
                    """)

                    if current_status in ["complete", "awaiting_feedback", "error"]:
                        break

                    time.sleep(2)
                    poll_count += 1

                # Get results
                results = api_client.get_results(st.session_state.session_id)
                st.session_state.results = results
                st.session_state.reconciliation_complete = True
                st.session_state.step = 3
                st.rerun()

            except Exception as e:
                st.error(f"Reconciliation failed: {e}")

# Step 3: Review
elif st.session_state.step == 3:
    st.header("Step 3: Review Results")

    results = st.session_state.results

    if results:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Match Rate", f"{results['match_rate']:.1%}")
        with col2:
            st.metric("Matched", results['matched_count'])
        with col3:
            st.metric("Unmatched (A)", results['unmatched_a_count'])
        with col4:
            st.metric("Unmatched (B)", results['unmatched_b_count'])

        st.markdown("---")

        # Results tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Matched Records",
            "Unmatched (A)",
            "Unmatched (B)",
            "Generated Code",
            "Reasoning"
        ])

        with tab1:
            if results['matched_records']:
                st.dataframe(
                    pd.DataFrame(results['matched_records']),
                    use_container_width=True,
                    height=400
                )
            else:
                st.info("No matched records")

        with tab2:
            if results['unmatched_a']:
                st.dataframe(
                    pd.DataFrame(results['unmatched_a']),
                    use_container_width=True,
                    height=400
                )
            else:
                st.success("All records from Dataset A were matched!")

        with tab3:
            if results['unmatched_b']:
                st.dataframe(
                    pd.DataFrame(results['unmatched_b']),
                    use_container_width=True,
                    height=400
                )
            else:
                st.success("All records from Dataset B were matched!")

        with tab4:
            st.code(results['generated_code'], language="python")

        with tab5:
            for i, step in enumerate(results.get('reasoning_trace', []), 1):
                with st.expander(f"Step {i}"):
                    st.markdown(step)

        st.markdown("---")

        # Action buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Accept Results", use_container_width=True, type="primary"):
                st.session_state.accepted = True
                st.session_state.step = 4
                st.rerun()

        with col2:
            if st.button("Provide Feedback", use_container_width=True):
                st.session_state.show_feedback = True

        with col3:
            if st.button("Start Over", use_container_width=True):
                reset_session()
                st.rerun()

        # Feedback form
        if st.session_state.get("show_feedback", False):
            st.markdown("---")
            st.subheader("Provide Feedback")

            feedback = st.text_area(
                "Describe what needs to be improved",
                placeholder="e.g., The date matching is wrong. Some reference numbers have different formats.",
                height=150
            )

            if st.button("Submit Feedback & Refine", disabled=not feedback):
                with st.spinner("Processing feedback and refining..."):
                    try:
                        api_client.submit_feedback(st.session_state.session_id, feedback)

                        # Poll for new results
                        time.sleep(3)
                        max_polls = 60

                        for _ in range(max_polls):
                            status = api_client.get_status(st.session_state.session_id)
                            if status.get("status") in ["complete", "awaiting_feedback", "error"]:
                                break
                            time.sleep(2)

                        # Get new results
                        results = api_client.get_results(st.session_state.session_id)
                        st.session_state.results = results
                        st.session_state.show_feedback = False
                        st.rerun()

                    except Exception as e:
                        st.error(f"Feedback processing failed: {e}")

# Step 4: Export
elif st.session_state.step == 4:
    st.header("Step 4: Export Results")

    results = st.session_state.results

    st.success("Results accepted! Choose your export options below.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Reconciled Data")
        format_option = st.selectbox("Format", ["CSV", "Excel"])

        if st.button("Download Data", use_container_width=True):
            try:
                data = api_client.export_data(
                    st.session_state.session_id,
                    format_option.lower()
                )
                ext = "csv" if format_option == "CSV" else "xlsx"
                st.download_button(
                    "Click to Download",
                    data,
                    file_name=f"reconciled_data.{ext}",
                    mime="text/csv" if ext == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Export failed: {e}")

    with col2:
        st.subheader("Python Code")
        if st.button("Download Code", use_container_width=True):
            try:
                code = api_client.export_code(st.session_state.session_id)
                st.download_button(
                    "Click to Download",
                    code,
                    file_name="reconciliation_code.py",
                    mime="text/x-python",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Export failed: {e}")

    with col3:
        st.subheader("n8n Workflow")
        st.caption("JavaScript Code nodes for native n8n execution")

        if st.button("Download n8n Workflow", use_container_width=True):
            try:
                data = api_client.download_n8n(st.session_state.session_id)
                st.download_button(
                    "Click to Download JSON",
                    data,
                    file_name="reconciliation_workflow.json",
                    mime="application/json",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Export failed: {e}")

    st.markdown("---")

    # Preview n8n workflow
    st.subheader("n8n Workflow Preview")
    try:
        n8n_data = api_client.export_n8n(st.session_state.session_id)
        st.json(n8n_data["workflow"])
    except Exception as e:
        st.error(f"Could not load preview: {e}")

    st.markdown("---")

    if st.button("Start New Reconciliation", use_container_width=True, type="primary"):
        reset_session()
        st.rerun()

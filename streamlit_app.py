import streamlit as st
from trial_matching_agent import WorkflowOrchestrator, TrialDatabase

st.set_page_config(page_title="Sanofi Agentic Screener", layout="wide")

# Initialize System
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = WorkflowOrchestrator()
    st.session_state.db = TrialDatabase()

st.title("🧬 Agentic Clinical Trial Screener (Powered by Gemini)")
st.markdown("**Zero-Based Process Automation** for Pharma Pipelines")

# Sidebar
with st.sidebar:
    st.header("Input Data")
    input_method = st.radio("Choose Input:", ["Simulated Text", "Manual Entry"])
    
    default_text = """
    Patient ID: P-99
    Age: 52
    Diagnosis: Type 2 Diabetes
    Biomarkers: HbA1c: 8.2
    Medications: Metformin
    Location: Toronto
    """
    
    if input_method == "Simulated Text":
        text_input = st.text_area("Medical Record", value=default_text, height=200)
    else:
        text_input = st.text_area("Paste Medical Record Here...", height=200)

    process_btn = st.button("🚀 Run AI Workflow")

# Main Area
if process_btn:
    with st.spinner("🤖 AI Agent is analyzing record..."):
        # 1. Fetch Trials
        trials = st.session_state.db.get_trials()
        
        # 2. Run Workflow
        results = st.session_state.orchestrator.run_workflow(text_input, trials)
        
        # 3. Display Results
        st.success("Analysis Complete")
        
        col1, col2 = st.columns(2)
        col1.metric("Trials Checked", len(trials))
        col2.metric("Eligible Matches", sum(1 for r in results if r.match_decision))
        
        st.markdown("---")
        for res in results:
            with st.expander(f"{'✅' if res.match_decision else '❌'} Trial: {res.trial_id} ({res.confidence_score:.0%})"):
                st.write(f"**Decision:** {'Eligible' if res.match_decision else 'Ineligible'}")
                st.write("**Reasoning:**")
                for r in res.reasoning:
                    st.markdown(f"- {r}")
                if res.missing_criteria:
                    st.write("**Missing Criteria:**")
                    for m in res.missing_criteria:
                        st.markdown(f"- {m}")
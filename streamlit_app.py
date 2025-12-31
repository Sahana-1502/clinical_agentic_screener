import streamlit as st
from pypdf import PdfReader
from trial_matching_agent import WorkflowOrchestrator, TrialDatabase

st.set_page_config(page_title="Sanofi Agentic Screener", layout="wide")

# Initialize System in Session State (Memory)
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = WorkflowOrchestrator()
    st.session_state.db = TrialDatabase()

st.title("🧬 Agentic Clinical Trial Screener (Powered by Gemini)")
st.markdown("**Zero-Based Process Automation** for Pharma Pipelines")

# ===== SIDEBAR (INPUTS) =====
with st.sidebar:
    st.header("Input Data")
    
    # User chooses how to input data
    input_method = st.radio(
        "Choose Input Method:", 
        ["Upload PDF", "Simulated Text", "Manual Entry"]
    )
    
    text_input = "" # This variable will hold the final text sent to AI

    # OPTION 1: PDF Upload (The Consumer-Grade Feature)
    if input_method == "Upload PDF":
        uploaded_file = st.file_uploader("Upload Medical Record (PDF)", type="pdf")
        
        if uploaded_file:
            try:
                # Read the PDF file
                pdf = PdfReader(uploaded_file)
                text_input = ""
                for page in pdf.pages:
                    text_input += page.extract_text()
                
                st.success("✅ PDF Processed Successfully")
                # Optional: Preview the extracted text
                with st.expander("View Extracted Text"):
                    st.text(text_input[:500] + "...") 
            except Exception as e:
                st.error(f"Error reading PDF: {e}")

    # OPTION 2: Simulated Text (Fastest for Demos)
    elif input_method == "Simulated Text":
        default_text = """
        Patient ID: P-99
        Age: 52
        Diagnosis: Type 2 Diabetes
        Biomarkers: HbA1c: 8.2
        Medications: Metformin
        Location: Toronto
        """
        text_input = st.text_area("Medical Record", value=default_text, height=200)

    # OPTION 3: Manual Entry (Fallback)
    else:
        text_input = st.text_area("Paste Medical Record Here...", height=200)

    # The Trigger Button
    process_btn = st.button("🚀 Run AI Workflow")


# ===== MAIN AREA (OUTPUTS) =====
if process_btn:
    if not text_input:
        st.warning("⚠️ Please provide patient data first.")
    else:
        with st.spinner("🤖 AI Agent is analyzing record..."):
            # 1. Fetch Trials from "Database"
            trials = st.session_state.db.get_trials()
            
            # 2. Run the Workflow (The Agent thinks here)
            results = st.session_state.orchestrator.run_workflow(text_input, trials)
            
            # 3. Dashboard Metrics
            st.success("Analysis Complete")
            
            col1, col2 = st.columns(2)
            col1.metric("Trials Checked", len(trials))
            col2.metric("Eligible Matches", sum(1 for r in results if r.match_decision))
            
            st.markdown("---")
            
            # 4. Detailed Results Cards
            for res in results:
                icon = "✅" if res.match_decision else "❌"
                status_color = ":green" if res.match_decision else ":red"
                
                with st.expander(f"{icon} Trial: {res.trial_id} ({res.confidence_score:.0%})"):
                    st.write(f"**Decision:** {res.match_decision}")
                    
                    st.write("**Reasoning:**")
                    for r in res.reasoning:
                        st.markdown(f"- {r}")
                    
                    if res.missing_criteria:
                        st.write("**Missing Criteria:**")
                        for m in res.missing_criteria:
                            st.markdown(f"- {m}")
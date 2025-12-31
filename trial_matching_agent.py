import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# --- GOOGLE GEMINI IMPORTS ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Load environment variables (API Key)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== DATA MODELS =====

class PatientData(BaseModel):
    patient_id: str
    age: int
    diagnosis: str
    # Biomarkers must be floats. The prompt ensures "160/95" becomes separate fields.
    biomarkers: Dict[str, float] = Field(default_factory=dict)
    medications: List[str] = Field(default_factory=list)
    location: str

    @validator('age')
    def validate_age(cls, v):
        if v < 0 or v > 120: raise ValueError(f"Invalid age: {v}")
        return v

class ClinicalTrial(BaseModel):
    trial_id: str
    title: str
    condition: str
    phase: str
    age_min: int
    age_max: int
    required_biomarkers: Dict[str, tuple] = Field(default_factory=dict)
    excluded_medications: List[str] = Field(default_factory=list)
    locations: List[str]

class MatchResult(BaseModel):
    patient_id: str
    trial_id: str
    match_decision: bool
    confidence_score: float
    reasoning: List[str]
    missing_criteria: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

# ===== AGENTS =====

class PatientExtractionAgent:
    def __init__(self):
        # Using the specific 2.5 Flash model available in your list
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    def extract_from_text(self, medical_text: str) -> PatientData:
        prompt_text = """
        You are a medical data extractor. Extract patient data from the text below.
        Return ONLY raw JSON. Do not use Markdown formatting (no ```json).
        
        CRITICAL RULES FOR BIOMARKERS:
        - Values must be NUMBERS (floats) only.
        - DO NOT include fractions or strings like "120/80".
        - If you see Blood Pressure (e.g. "160/95"), split it into two fields: "SystolicBP" (160) and "DiastolicBP" (95).
        
        Fields required:
        - patient_id (string)
        - age (integer)
        - diagnosis (string)
        - biomarkers (dictionary of floats)
        - medications (list of strings)
        - location (string)

        Medical Record:
        {text}
        """
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.llm
        
        try:
            # 1. Get raw string response
            response = chain.invoke({"text": medical_text})
            raw_content = response.content
            
            # 2. Clean the cleanup (Remove markdown if Gemini adds it)
            clean_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            # 3. Parse JSON manually
            result = json.loads(clean_content)
            
            # 4. Add defaults if missing
            if "biomarkers" not in result: result["biomarkers"] = {}
            if "medications" not in result: result["medications"] = []
            
            return PatientData(**result)
            
        except Exception as e:
            # Print error to terminal for debugging
            print(f"\n❌ FULL ERROR: {e}")
            print(f"❌ RAW AI OUTPUT: {raw_content if 'raw_content' in locals() else 'No output'}\n")
            
            # Return error data so UI doesn't crash completely
            return PatientData(
                patient_id="ERR", age=0, diagnosis=f"Failed: {str(e)[:50]}", location="Unknown"
            )

class TrialMatchingAgent:
    def evaluate_match(self, patient: PatientData, trial: ClinicalTrial) -> MatchResult:
        reasoning = []
        missing = []
        checks = 0
        passed = 0

        # Logic 1: Diagnosis (Flexible string match)
        checks += 1
        if trial.condition.lower() in patient.diagnosis.lower():
            reasoning.append(f"✓ Diagnosis match: {patient.diagnosis}")
            passed += 1
        else:
            missing.append(f"Diagnosis mismatch: {patient.diagnosis} != {trial.condition}")

        # Logic 2: Age
        checks += 1
        if trial.age_min <= patient.age <= trial.age_max:
            reasoning.append(f"✓ Age {patient.age} within range")
            passed += 1
        else:
            missing.append(f"Age {patient.age} outside {trial.age_min}-{trial.age_max}")

        # Logic 3: Location (Smart substring match)
        checks += 1
        # Checks if "Toronto" is inside "Toronto, ON"
        location_match = any(site.lower() in patient.location.lower() for site in trial.locations)
        
        if location_match:
            reasoning.append(f"✓ Location match: {patient.location}")
            passed += 1
        else:
            missing.append(f"Location {patient.location} not in trial sites {trial.locations}")

        # Calculate Score
        confidence = passed / checks if checks > 0 else 0
        
        # STRICT MODE: Patient must match ALL criteria (100%) to be eligible
        decision = (confidence == 1.0)

        return MatchResult(
            patient_id=patient.patient_id,
            trial_id=trial.trial_id,
            match_decision=decision,
            confidence_score=confidence,
            reasoning=reasoning,
            missing_criteria=missing
        )

# ===== ORCHESTRATOR & DATABASE =====

class WorkflowOrchestrator:
    def __init__(self):
        self.extractor = PatientExtractionAgent()
        self.matcher = TrialMatchingAgent()
        self.history = []

    def run_workflow(self, text: str, trials: List[ClinicalTrial]):
        patient = self.extractor.extract_from_text(text)
        results = []
        for trial in trials:
            res = self.matcher.evaluate_match(patient, trial)
            results.append(res)
        
        self.history.append({"time": datetime.now(), "matches": len(results)})
        return results

class TrialDatabase:
    def get_trials(self):
        # Dummy data simulating SQL DB
        return [
            ClinicalTrial(
                trial_id="NCT001", title="Diabetes Phase 3", condition="Diabetes",
                phase="Phase 3", age_min=18, age_max=75,
                locations=["Toronto", "Montreal"], excluded_medications=["Insulin"]
            ),
             ClinicalTrial(
                trial_id="NCT002", title="Hypertension Study", condition="Hypertension",
                phase="Phase 2", age_min=40, age_max=80,
                locations=["Vancouver"], excluded_medications=[]
            )
        ]
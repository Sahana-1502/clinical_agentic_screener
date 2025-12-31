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
        # Initialize Google Gemini Pro
        # The older, most compatible model version
        self.llm = ChatGoogleGenerativeAI(model="gemini-1.0-pro", temperature=0)

    def extract_from_text(self, medical_text: str) -> PatientData:
        # NOTICE: We use {{ }} for the JSON example to tell LangChain "this is text, not a variable"
        prompt_text = """
        Extract the following patient data from the text below into JSON format:
        - patient_id (string)
        - age (integer)
        - diagnosis (string)
        - biomarkers (dictionary of floats, e.g. {{"HbA1c": 8.2}})
        - medications (list of strings)
        - location (string)

        Medical Record:
        {text}
        """
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | self.llm | JsonOutputParser()
        
        try:
            result = chain.invoke({"text": medical_text})
            # Add defaults if missing to pass validation
            if "biomarkers" not in result: result["biomarkers"] = {}
            if "medications" not in result: result["medications"] = []
            return PatientData(**result)
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # Fallback for demo if LLM fails
            return PatientData(
                patient_id="ERR001", age=0, diagnosis="Error", location="Unknown"
            )

class TrialMatchingAgent:
    def evaluate_match(self, patient: PatientData, trial: ClinicalTrial) -> MatchResult:
        reasoning = []
        missing = []
        checks = 0
        passed = 0

        # Logic 1: Diagnosis
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

        # Logic 3: Location
        checks += 1
        if patient.location in trial.locations:
            reasoning.append(f"✓ Location match: {patient.location}")
            passed += 1
        else:
            missing.append(f"Location {patient.location} not in trial sites")

        confidence = passed / checks if checks > 0 else 0
        decision = confidence >= 0.66 # Simple threshold

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
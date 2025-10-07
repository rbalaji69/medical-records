import os
import json
import sys
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from agentic_doc.parse import parse
from fhir.resources.bundle import Bundle
from fhir.resources.patient import Patient
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.observation import Observation

class MedicalDocumentFields(BaseModel):
    patient_name: str = Field(description="Patient name")
    gender: str = Field(description="Patient gender (M/F)")
    age: int = Field(description="Patient age")
    lab_name: str = Field(description="Laboratory name")
    report_date: str = Field(description="Report date")
    cholesterol: float = Field(description="Total cholesterol value", default=None)
    triglycerides: float = Field(description="Triglycerides value", default=None)
    hdl: float = Field(description="HDL cholesterol value", default=None)
    ldl: float = Field(description="LDL cholesterol value", default=None)
    vldl: float = Field(description="VLDL cholesterol value", default=None)
    cholesterol_hdl_ratio: float = Field(description="Cholesterol/HDL ratio", default=None)
    ldl_hdl_ratio: float = Field(description="LDL/HDL ratio", default=None)
    hemoglobin: float = Field(description="Hemoglobin value", default=None)
    blood_sugar: float = Field(description="Blood sugar/glucose value", default=None)
    microalbuminuria: float = Field(description="Urine microalbuminuria value", default=None)
    tsh: float = Field(description="TSH value", default=None)
    creatinine: float = Field(description="Creatinine value", default=None)
    egfr: float = Field(description="eGFR value", default=None)

class AgenticDocumentExtractor:
    def __init__(self):
        self.patient_id = "patient-001"
        self.obs_counter = 1
    
    def extract_structured_data(self, file_path: str) -> Dict[str, Any]:
        """Extract structured data from document using Agentic"""
        try:
            results = parse(file_path, extraction_model=MedicalDocumentFields)
            if results and len(results) > 0:
                fields = results[0].extraction
                # Convert Pydantic model to dictionary
                return fields.dict()
            return None
        except Exception as e:
            print(f"Error processing document: {e}")
            return None
    
    def extract_patient_info(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract patient information from structured data"""
        patient = {
            "resourceType": "Patient",
            "id": self.patient_id,
            "name": [{"text": "Unknown"}],
            "gender": "unknown"
        }
        
        # Extract patient name from structured data
        if structured_data.get('patient_name'):
            patient["name"] = [{"text": str(structured_data['patient_name'])}]
        
        # Extract gender
        if structured_data.get('gender'):
            gender = str(structured_data['gender']).upper()
            if gender in ['M', 'MALE']:
                patient["gender"] = "male"
            elif gender in ['F', 'FEMALE']:
                patient["gender"] = "female"
        
        return patient
    
    def extract_diagnostic_report(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract diagnostic report information"""
        lab_name = "Clinical Laboratory"
        if structured_data.get('lab_name'):
            lab_name = str(structured_data['lab_name'])
        
        report_date = None
        if structured_data.get('report_date'):
            report_date = str(structured_data['report_date'])
            # Convert date format if needed
            if "/" in report_date:
                try:
                    day, month, year = report_date.split("/")
                    report_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    pass
        
        diagnostic_report = {
            "resourceType": "DiagnosticReport",
            "id": "dr-001",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "LAB",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "57698-3",
                        "display": "Lipid panel with direct LDL - Serum or Plasma"
                    }
                ],
                "text": "Laboratory Report"
            },
            "subject": {"reference": f"Patient/{self.patient_id}"},
            "performer": [
                {
                    "display": lab_name
                }
            ]
        }
        
        if report_date:
            diagnostic_report["effectiveDateTime"] = report_date
        
        return diagnostic_report
    
    def extract_observations(self, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract laboratory observations from structured data"""
        observations = []
        
        # Define mapping for lab tests with their LOINC codes
        lab_mappings = {
            'cholesterol': ('33747-0', 'Cholesterol [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'triglycerides': ('2571-8', 'Triglyceride [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'hdl': ('2085-9', 'Cholesterol in HDL [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'ldl': ('18262-6', 'Cholesterol in LDL [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'vldl': ('13458-5', 'Cholesterol in VLDL [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'cholesterol_hdl_ratio': ('9830-1', 'Cholesterol.total/Cholesterol in HDL [Mass Ratio] in Serum or Plasma', 'ratio'),
            'ldl_hdl_ratio': ('11054-4', 'Cholesterol in LDL/Cholesterol in HDL [Mass Ratio] in Serum or Plasma', 'ratio'),
            'hemoglobin': ('718-7', 'Hemoglobin [Mass/volume] in Blood', 'g/dL'),
            'blood_sugar': ('33747-0', 'Glucose [Mass/volume] in Blood', 'mg/dL'),
            'microalbuminuria': ('14959-1', 'Albumin [Mass/volume] in Urine', 'mg/L'),
            'tsh': ('3016-3', 'Thyrotropin [Units/volume] in Serum or Plasma', 'mlU/mL'),
            'creatinine': ('2160-0', 'Creatinine [Mass/volume] in Serum or Plasma', 'mg/dL'),
            'egfr': ('33914-3', 'Glomerular filtration rate/1.73 square meters [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (MDRD)', 'mL/min/1.73 m²')
        }
        
        # Extract observations from structured data
        for key, value in structured_data.items():
            if value is not None and key in lab_mappings:
                try:
                    loinc_code, display_name, default_unit = lab_mappings[key]
                    num_value = float(value)
                    
                    obs = {
                        "resourceType": "Observation",
                        "id": f"obs-{self.obs_counter:03d}",
                        "status": "final",
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                        "code": "laboratory",
                                        "display": "Laboratory"
                                    }
                                ]
                            }
                        ],
                        "code": {
                            "coding": [
                                {
                                    "system": "http://loinc.org",
                                    "code": loinc_code,
                                    "display": display_name
                                }
                            ]
                        },
                        "subject": {"reference": f"Patient/{self.patient_id}"}
                    }
                    
                    # Add value quantity
                    if "ratio" in display_name.lower():
                        obs["valueQuantity"] = {
                            "value": num_value
                        }
                    else:
                        obs["valueQuantity"] = {
                            "value": num_value,
                            "unit": default_unit,
                            "system": "http://unitsofmeasure.org",
                            "code": default_unit
                        }
                    
                    observations.append(obs)
                    self.obs_counter += 1
                    
                except (ValueError, TypeError):
                    continue
        
        return observations
    
    def create_fhir_bundle(self, file_path: str) -> Dict[str, Any]:
        """Main method to extract data and create FHIR bundle"""
        # Extract structured data from document
        structured_data = self.extract_structured_data(file_path)
        
        if not structured_data:
            return {"error": "No structured data extracted from document"}
        
        # Extract components
        patient = self.extract_patient_info(structured_data)
        diagnostic_report = self.extract_diagnostic_report(structured_data)
        observations = self.extract_observations(structured_data)
        
        # Create bundle
        bundle = {
            "resourceType": "Bundle",
            "id": "bundle-001",
            "type": "collection",
            "entry": [{"resource": patient}, {"resource": diagnostic_report}] + [{"resource": obs} for obs in observations]
        }
        
        # Validate bundle
        try:
            Bundle(**bundle)
        except Exception as e:
            print(f"WARNING: FHIR validation warning: {e}")
        
        return bundle

def main():
    if len(sys.argv) != 2:
        print("Usage: python agentic_document_extractor.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found")
        sys.exit(1)
    
    # Check file extension
    file_ext = Path(input_file).suffix.lower()
    if file_ext not in ['.jpg', '.jpeg', '.pdf']:
        print(f"Error: Unsupported file format: {file_ext}")
        print("Supported formats: .jpg, .jpeg, .pdf")
        sys.exit(1)
    
    try:
        # Create extractor and process document
        extractor = AgenticDocumentExtractor()
        fhir_json = extractor.create_fhir_bundle(input_file)
        
        # Generate output filename
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}-agentic.json"
        
        # Write output
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(fhir_json, f, indent=2)
        
        print(f"SUCCESS: FHIR Bundle JSON written to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

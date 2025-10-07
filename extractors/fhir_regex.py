import re
import json
import sys
import os
from datetime import datetime
from fhir.resources.bundle import Bundle
from fhir.resources.patient import Patient
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.observation import Observation

def extract_fhir_bundle_regex(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # --- Patient ---
    # Extract patient name more precisely
    patient_name_match = re.search(r"Patient Name[:\s]+([A-Za-z\s\.]+?)(?:\s+Age|$)", raw_text)
    patient_name = patient_name_match.group(1).strip() if patient_name_match else "Unknown"
    
    # Extract age and gender
    age_sex_match = re.search(r"Age\s*/\s*Sex[:\s]+(\d+)([MF])", raw_text)
    age = age_sex_match.group(1) if age_sex_match else None
    gender = "male" if age_sex_match and age_sex_match.group(2) == "M" else "female" if age_sex_match else "unknown"

    patient = {
        "resourceType": "Patient",
        "id": "patient-001",
        "name": [{"text": patient_name}],
        "gender": gender
    }
    
    if age:
        birth_year = datetime.now().year - int(age)
        patient["birthDate"] = f"{birth_year}-01-01"

    # --- Diagnostic Report ---
    # Extract lab name more precisely
    lab_match = re.search(r"(VIGNASH[^0-9]*LABORATORY[^0-9]*)", raw_text)
    lab_name = lab_match.group(1).strip() if lab_match else "Clinical Laboratory"
    
    # Extract report date
    report_date_match = re.search(r"Reported Date[:\s]+(\d{2}/\d{2}/\d{4})", raw_text)
    report_date = report_date_match.group(1) if report_date_match else str(datetime.now().date())
    
    # Convert date format from DD/MM/YYYY to YYYY-MM-DD
    if "/" in report_date:
        try:
            day, month, year = report_date.split("/")
            report_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except:
            report_date = str(datetime.now().date())

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
            "text": "Lipid Profile"
        },
        "subject": {"reference": "Patient/patient-001"},
        "effectiveDateTime": report_date,
        "performer": [
            {
                "display": lab_name
            }
        ]
    }

    # --- Observations ---
    # More precise patterns for lab values
    lab_patterns = [
        (r"Serum Total Cholesterol[:\s]+([\d.]+)\s*(mgs?/dl)", "33747-0", "Cholesterol [Mass/volume] in Serum or Plasma"),
        (r"Serum Triglycerides[:\s]+([\d.]+)\s*(mgs?/dl)", "2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
        (r"HDL Cholesterol[:\s]+([\d.]+)\s*(mgs?/dl)", "2085-9", "Cholesterol in HDL [Mass/volume] in Serum or Plasma"),
        (r"LDL Cholesterol[:\s]+([\d.]+)\s*(mgs?/dl)", "18262-6", "Cholesterol in LDL [Mass/volume] in Serum or Plasma"),
        (r"VLDL Cholesterol[:\s]+([\d.]+)\s*(mgs?/dl)", "13458-5", "Cholesterol in VLDL [Mass/volume] in Serum or Plasma"),
        (r"Cholesterol/HDL Ratio[:\s]+([\d.]+)", "9830-1", "Cholesterol.total/Cholesterol in HDL [Mass Ratio] in Serum or Plasma"),
        (r"LDL/HDL Ratio[:\s]+([\d.]+)", "11054-4", "Cholesterol in LDL/Cholesterol in HDL [Mass Ratio] in Serum or Plasma")
    ]
    
    observations = []
    obs_count = 1

    for pattern, loinc_code, display_name in lab_patterns:
        match = re.search(pattern, raw_text)
        if match:
            value = float(match.group(1))
            unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""
            
            obs = {
                "resourceType": "Observation",
                "id": f"obs-{obs_count:03d}",
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
                "subject": {"reference": "Patient/patient-001"},
                "effectiveDateTime": report_date
            }
            
            if unit and "ratio" not in display_name.lower():
                obs["valueQuantity"] = {
                    "value": value,
                    "unit": unit,
                    "system": "http://unitsofmeasure.org",
                    "code": "mg/dL" if "mg" in unit else unit
                }
            else:
                obs["valueQuantity"] = {
                    "value": value
                }
            
            observations.append(obs)
            obs_count += 1

    # --- Bundle ---
    bundle = {
        "resourceType": "Bundle",
        "id": "bundle-001",
        "type": "collection",
        "entry": [{"resource": patient}, {"resource": diagnostic_report}]
                + [{"resource": obs} for obs in observations]
    }

    # --- Validate Bundle ---
    try:
        Bundle(**bundle)  # raises if invalid
    except Exception as e:
        print("WARNING: Validation warning:", str(e))

    return bundle


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fhir_regex.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    base, ext = os.path.splitext(input_file)
    program_stem = os.path.splitext(os.path.basename(__file__))[0]  # Get program stem (e.g., 'fhir_regex')
    output_file = f"{base}-{program_stem}.json"

    fhir_json = extract_fhir_bundle_regex(input_file)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fhir_json, f, indent=2)

    print(f"SUCCESS: FHIR Bundle JSON written to {output_file}")

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
    patient_name = re.search(r"Patient Name[:\s]+(.+)", raw_text)
    patient_name = patient_name.group(1).strip() if patient_name else "Unknown"

    patient = {
        "resourceType": "Patient",
        "id": "patient-001",
        "name": [{"text": patient_name}]
    }

    # --- Diagnostic Report ---
    lab = re.search(r"Lab[:\s]+(.+)", raw_text)
    lab = lab.group(1).strip() if lab else "Unknown Lab"

    diagnostic_report = {
        "resourceType": "DiagnosticReport",
        "id": "dr-001",
        "status": "unknown",
        "code": {"text": "Lab Report"},
        "subject": {"reference": "Patient/patient-001"},
        "note": [{"text": lab}],
        "effectiveDateTime": str(datetime.now().date())
    }

    # --- Observations ---
    metric_pattern = re.compile(r"([\w\s/]+)[:\s]+([\d.]+)\s*([A-Za-z/%]*)\s*(?:\(Ref\s*([^\)]+)\))?")
    observations = []
    obs_count = 1

    for match in metric_pattern.finditer(raw_text):
        metric_name, value, unit, ref = match.groups()
        obs = {
            "resourceType": "Observation",
            "id": f"obs-{obs_count:03d}",
            "status": "unknown",
            "code": {"text": metric_name.strip()},
            "subject": {"reference": "Patient/patient-001"},
            "valueQuantity": {"value": float(value), "unit": unit.strip()},
        }
        if ref:
            obs["referenceRange"] = [{"text": ref}]
        observations.append(obs)
        obs_count += 1

    # --- Bundle ---
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": patient}, {"resource": diagnostic_report}]
                + [{"resource": obs} for obs in observations]
    }

    # --- Validate Bundle ---
    try:
        Bundle(**bundle)  # raises if invalid
    except Exception as e:
        print("⚠️ Validation warning:", str(e))

    return bundle


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fhir_regex_bundle.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}-regex-output.json"

    fhir_json = extract_fhir_bundle_regex(input_file)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fhir_json, f, indent=2)

    print(f"✅ Regex-based FHIR Bundle JSON written to {output_file}")

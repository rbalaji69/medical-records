import sys
import os
import json
from dotenv import load_dotenv
import openai
from fhir.resources.bundle import Bundle

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI with explicit API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("ERROR: OPENAI_API_KEY not found in environment variables.")
    print("Please make sure you have a .env file with: OPENAI_API_KEY=your-api-key")
    sys.exit(1)

openai.api_key = api_key

def extract_fhir_bundle_llm(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    prompt = f"""
Convert the following OCR medical report into valid FHIR R4 JSON.
The output must be a Bundle resource with:
- "resourceType": "Bundle"
- "type": "collection"
- "entry": an array containing Patient, DiagnosticReport, and Observation resources.

CRITICAL FHIR R4 Requirements:
1. DiagnosticReport MUST have a "code" field with coding system (use LOINC when possible)
2. All datetime fields with time components MUST include timezone (use "Z" for UTC if unknown)
3. Patient resources should have proper name structure
4. All resources must have valid IDs (alphanumeric, no special characters like commas)
5. Use proper LOINC codes for laboratory observations when possible
6. CRITICAL: Observation "category" field MUST be an array [{{}}], not a single object {{}}
7. CRITICAL: DiagnosticReport "category" field MUST be an array [{{}}], not a single object {{}}

IMPORTANT DATA EXTRACTION RULES:
1. Extract ALL laboratory values and ratios mentioned in the text - be thorough and systematic. Always include valueQuantity field for observations. Include units for valueQuantity whenever possible.
2. Pay special attention to ratio measurements like "LDL/HDL Ratio", "Cholesterol/HDL Ratio", etc.
3. ABSOLUTELY FORBIDDEN: Do not compute, calculate, derive, or infer birthDate, birthTime, or any birth-related fields from age and dates
4. If only age is mentioned (like "Age 71F"), do NOT include any birth-related fields (birthDate, birthTime, extensions) in the Patient resource
5. Patient resource should only contain: name, gender, and explicitly stated information - NO calculated fields
6. Extract patient demographics (name, gender) only from what is explicitly stated - do not infer or calculate
7. Create separate Observation resources for each distinct laboratory measurement. For observations that are ratios, use the "ratio" unit. Whenever possible, include the code and category fields for observations.
8. Be systematic: scan the entire text for all numerical values with units or ratios

Be consistent and thorough in extracting all measurements. Ensure the JSON is strictly FHIR R4 compliant and validates without errors.

CORRECT FHIR Structure Examples:
- Observation category: "category": [{{"coding": [{{"system": "...", "code": "laboratory"}}]}}]
- DiagnosticReport category: "category": [{{"coding": [{{"system": "...", "code": "LAB"}}]}}]

OCR Text:
---
{raw_text}
---
"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Using gpt-3.5-turbo as it's compatible with older API
        messages=[
            {"role": "system", "content": "You are an expert in HL7 FHIR healthcare data modeling. You extract only the data that is explicitly present in medical documents. You NEVER calculate, compute, or derive dates, ages, or other values. You only extract what is directly stated."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    json_str = response.choices[0].message.content.strip()
    
    # Remove markdown code blocks if present
    if json_str.startswith("```json"):
        json_str = json_str[7:]  # Remove ```json
    if json_str.startswith("```"):
        json_str = json_str[3:]   # Remove ```
    if json_str.endswith("```"):
        json_str = json_str[:-3]  # Remove trailing ```
    json_str = json_str.strip()

    try:
        fhir_json = json.loads(json_str)
    except json.JSONDecodeError:
        fhir_json = {"error": "Invalid JSON from LLM", "raw_output": json_str}
        return fhir_json

    # --- Validate Bundle ---
    try:
        Bundle(**fhir_json)
    except Exception as e:
        print("WARNING: Validation warning:", str(e))

    return fhir_json


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python fhir_llm.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    base, ext = os.path.splitext(input_file)
    program_stem = os.path.splitext(os.path.basename(__file__))[0]  # Get program stem (e.g., 'fhir_llm')
    output_file = f"{base}-{program_stem}.json"

    fhir_json = extract_fhir_bundle_llm(input_file)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fhir_json, f, indent=2)

    print(f"SUCCESS: FHIR Bundle JSON written to {output_file}")

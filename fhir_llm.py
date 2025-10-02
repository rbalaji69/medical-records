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
    print("❌ Error: OPENAI_API_KEY not found in environment variables.")
    print("Please make sure you have a .env file with: OPENAI_API_KEY=your-api-key")
    sys.exit(1)

openai.api_key = api_key

def extract_fhir_bundle_llm(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    prompt = f"""
Convert the following OCR medical report into valid FHIR JSON.
The output must be a Bundle resource with:
- "resourceType": "Bundle"
- "type": "collection"
- "entry": an array containing Patient, DiagnosticReport, and Observation resources.
Ensure the JSON is strictly FHIR compliant.

OCR Text:
---
{raw_text}
---
"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Using gpt-3.5-turbo as it's compatible with older API
        messages=[
            {"role": "system", "content": "You are an expert in HL7 FHIR healthcare data modeling."},
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
        print("⚠️ Validation warning:", str(e))

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

    print(f"✅ FHIR Bundle JSON written to {output_file}")

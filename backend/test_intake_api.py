"""Test script for the handoff intake endpoint."""

import json
import requests

# Sample patient handoff transcript
SAMPLE_TRANSCRIPT = """
Patient John Doe in room 302, 68 years old. Chief complaint is chest pain.
He's on aspirin 81mg daily, metoprolol 50mg twice daily, and atorvastatin 40mg at bedtime.
Pending tasks include cardiac enzyme labs at 6 AM and cardiology consult.
Latest vitals: blood pressure 145 over 92, heart rate 88, temperature 98.6, oxygen saturation 96 percent.
Safety alert: fall risk due to dizziness.
"""

def test_handoff_endpoint():
    """Test the /handoff/intake endpoint with a sample transcript."""
    url = "http://localhost:8000/handoff/intake"
    
    payload = {
        "transcript": SAMPLE_TRANSCRIPT
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        print("✓ Request successful!")
        print("\nExtracted Data:")
        data = response.json()
        print(f"  Confidence: {data.get('confidence', 0):.2f}")
        print(f"  Reasoning: {data.get('reasoning', 'N/A')}")
        print(f"\n{json.dumps(data, indent=2)}")
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server. Make sure it's running on http://localhost:8000")
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {e}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("Testing Patient Handoff Intake API")
    print("=" * 50)
    test_handoff_endpoint()

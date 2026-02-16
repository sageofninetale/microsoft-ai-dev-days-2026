"""Generate 100 realistic synthetic patients for testing."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # Load .env file

import json
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from faker import Faker
from supabase import create_client


# Initialize Faker
fake = Faker()


def get_supabase_client():
    """Create and return Supabase client."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
    
    return create_client(supabase_url, supabase_key)


def generate_age_weighted() -> int:
    """Generate age with realistic distribution."""
    rand = random.random()
    if rand < 0.30:  # 30% elderly (65+)
        return random.randint(65, 95)
    elif rand < 0.80:  # 50% middle-age (40-64)
        return random.randint(40, 64)
    else:  # 20% young (18-39)
        return random.randint(18, 39)


def generate_diagnosis() -> str:
    """Generate primary diagnosis with weighted distribution."""
    diagnoses = [
        ("Acute Coronary Syndrome (ACS)", 0.10),
        ("Congestive Heart Failure (CHF)", 0.15),
        ("Pneumonia", 0.12),
        ("COPD Exacerbation", 0.10),
        ("Type 2 Diabetes with complications", 0.15),
        ("Sepsis", 0.08),
        ("Hip Fracture Post-Op", 0.10),
        ("Ischemic Stroke", 0.08),
        ("Diabetic Ketoacidosis (DKA)", 0.06),
        ("GI Bleed", 0.06),
    ]
    
    return random.choices(
        [d[0] for d in diagnoses],
        weights=[d[1] for d in diagnoses]
    )[0]


def generate_medications(count: int = None) -> List[Dict[str, str]]:
    """Generate realistic medication list."""
    if count is None:
        count = random.randint(3, 8)
    
    medication_options = [
        {"name": "Aspirin", "dose": random.choice(["81mg", "325mg"]), "frequency": "daily", "route": "oral"},
        {"name": "Metformin", "dose": random.choice(["500mg", "1000mg"]), "frequency": "twice daily", "route": "oral"},
        {"name": "Lisinopril", "dose": random.choice(["10mg", "20mg"]), "frequency": "daily", "route": "oral"},
        {"name": "Atorvastatin", "dose": random.choice(["40mg", "80mg"]), "frequency": "at bedtime", "route": "oral"},
        {"name": "Metoprolol", "dose": random.choice(["25mg", "50mg", "100mg"]), "frequency": "twice daily", "route": "oral"},
        {"name": "Furosemide", "dose": random.choice(["20mg", "40mg"]), "frequency": random.choice(["daily", "twice daily"]), "route": "oral"},
        {"name": "Warfarin", "dose": "5mg", "frequency": "daily", "route": "oral"},
        {"name": "Levothyroxine", "dose": random.choice(["50mcg", "100mcg"]), "frequency": "daily", "route": "oral"},
        {"name": "Lantus", "dose": "20 units", "frequency": "at bedtime", "route": "subcutaneous"},
        {"name": "Humalog", "dose": "sliding scale", "frequency": "with meals", "route": "subcutaneous"},
        {"name": "Albuterol", "dose": "2 puffs", "frequency": "every 4 hours as needed", "route": "inhaled"},
        {"name": "Amlodipine", "dose": random.choice(["5mg", "10mg"]), "frequency": "daily", "route": "oral"},
        {"name": "Omeprazole", "dose": "20mg", "frequency": "daily", "route": "oral"},
        {"name": "Gabapentin", "dose": random.choice(["300mg", "600mg"]), "frequency": "three times daily", "route": "oral"},
    ]
    
    # Randomly select medications without duplicates
    selected_meds = random.sample(medication_options, min(count, len(medication_options)))
    return selected_meds


def generate_allergies() -> List[str]:
    """Generate patient allergies with realistic distribution."""
    rand = random.random()
    
    if rand < 0.40:  # 40% no allergies
        return []
    
    possible_allergies = []
    
    if random.random() < 0.30:  # 30% chance of Penicillin
        possible_allergies.append("Penicillin")
    if random.random() < 0.15:  # 15% chance of Sulfa
        possible_allergies.append("Sulfa drugs")
    if random.random() < 0.10:  # 10% chance of Latex
        possible_allergies.append("Latex")
    if random.random() < 0.08:  # 8% chance of NSAIDs
        possible_allergies.append("NSAIDs")
    
    return possible_allergies[:3]  # Max 3 allergies


def generate_vitals_history() -> List[Dict[str, Any]]:
    """Generate 3 vital sign readings over last 24 hours."""
    vitals_list = []
    now = datetime.now()
    
    for i in range(3):
        # Readings 8 hours apart (most recent first)
        timestamp = now - timedelta(hours=i * 8)
        
        systolic = random.randint(100, 180)
        diastolic = random.randint(60, 110)
        
        vitals = {
            "blood_pressure": f"{systolic}/{diastolic}",
            "heart_rate": random.randint(55, 120),
            "temperature": round(random.uniform(97.0, 102.5), 1),
            "spo2": random.randint(88, 100),
            "respiratory_rate": random.randint(12, 28),
            "timestamp": timestamp.isoformat() + "Z"
        }
        vitals_list.append(vitals)
    
    return vitals_list


def generate_past_medical_history() -> List[str]:
    """Generate past medical history with 2-5 conditions."""
    conditions = [
        "Hypertension", "Type 2 Diabetes", "Hyperlipidemia",
        "COPD", "Chronic Kidney Disease", "Coronary Artery Disease",
        "Atrial Fibrillation", "Osteoarthritis", "Depression", "Hypothyroidism"
    ]
    
    count = random.randint(2, 5)
    return random.sample(conditions, count)


def generate_fall_risk_score(age: int) -> int:
    """Generate fall risk score based on age."""
    if age >= 65:
        return random.randint(5, 9)
    elif age >= 40:
        return random.randint(2, 6)
    else:
        return random.randint(0, 3)


def generate_code_status() -> str:
    """Generate code status with realistic distribution."""
    rand = random.random()
    if rand < 0.85:
        return "Full Code"
    elif rand < 0.95:
        return "DNR"
    else:
        return "DNI"


def generate_patient(patient_id: str) -> Dict[str, Any]:
    """Generate a single realistic patient record."""
    age = generate_age_weighted()
    date_of_birth = datetime.now() - timedelta(days=age * 365.25)
    admission_date = datetime.now() - timedelta(days=random.randint(1, 30))
    
    patient = {
        "patient_id": patient_id,
        "name": fake.name(),
        "age": age,
        "date_of_birth": date_of_birth.date().isoformat(),
        "gender": random.choice(["Male", "Female"]),
        "room_number": str(random.randint(100, 999)),
        "admission_date": admission_date.isoformat() + "Z",
        "primary_diagnosis": generate_diagnosis(),
        "medications": generate_medications(),
        "allergies": generate_allergies(),
        "vitals_history": generate_vitals_history(),
        "past_medical_history": generate_past_medical_history(),
        "fall_risk_score": generate_fall_risk_score(age),
        "code_status": generate_code_status(),
        "created_at": datetime.now().isoformat() + "Z",
    }
    
    return patient


def insert_patients_batch(supabase, patients: List[Dict[str, Any]], start_idx: int) -> None:
    """Insert a batch of patients into Supabase."""
    try:
        response = supabase.table("patients").insert(patients).execute()
        print(f"✅ Successfully inserted patients {start_idx}-{start_idx + len(patients) - 1}")
    except Exception as e:
        print(f"❌ Error inserting patients {start_idx}-{start_idx + len(patients) - 1}: {str(e)}")
        raise


def main():
    """Generate and insert 100 synthetic patients."""
    print("\n" + "=" * 80)
    print("  SYNTHETIC PATIENT DATA GENERATOR")
    print("=" * 80 + "\n")
    
    print("🔧 Initializing Supabase client...")
    try:
        supabase = get_supabase_client()
        print("✅ Supabase client initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase: {e}")
        return
    
    # Check existing patient count
    try:
        response = supabase.table("patients").select("patient_id", count="exact").execute()
        existing_count = response.count if hasattr(response, 'count') else len(response.data)
        print(f"📊 Current patients in database: {existing_count}\n")
    except Exception as e:
        print(f"⚠️  Could not count existing patients: {e}\n")
        existing_count = 0
    
    # Check if P006-P105 already exist
    try:
        response = supabase.table("patients").select("patient_id").gte("patient_id", "P006").lte("patient_id", "P105").execute()
        existing_patient_ids = {p['patient_id'] for p in response.data}
        
        if existing_patient_ids:
            print(f"⚠️  Found {len(existing_patient_ids)} existing patients in P006-P105 range")
            print("🗑️  Deleting existing patients P006-P105 to avoid duplicates...\n")
            
            # Delete in batches to avoid timeout
            for patient_id in existing_patient_ids:
                try:
                    supabase.table("patients").delete().eq("patient_id", patient_id).execute()
                except Exception as e:
                    print(f"⚠️  Could not delete {patient_id}: {e}")
            
            print(f"✅ Cleared {len(existing_patient_ids)} existing patients\n")
    except Exception as e:
        print(f"⚠️  Could not check for existing patients: {e}\n")
    
    print("🧬 Generating 100 synthetic patients (P006-P105)...\n")
    
    # Generate 100 patients
    all_patients = []
    for i in range(6, 106):  # P006 to P105
        patient_id = f"P{i:03d}"
        patient = generate_patient(patient_id)
        all_patients.append(patient)
    
    print(f"✅ Generated {len(all_patients)} patients\n")
    print("📤 Inserting patients into Supabase in batches of 10...\n")
    
    # Insert in batches of 10
    batch_size = 10
    successful_inserts = 0
    
    for i in range(0, len(all_patients), batch_size):
        batch = all_patients[i:i + batch_size]
        start_idx = i + 6  # Start from P006
        
        try:
            insert_patients_batch(supabase, batch, start_idx)
            successful_inserts += len(batch)
        except Exception as e:
            print(f"⚠️  Continuing with next batch...\n")
            continue
    
    # Final count
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80 + "\n")
    
    try:
        response = supabase.table("patients").select("patient_id", count="exact").execute()
        final_count = response.count if hasattr(response, 'count') else len(response.data)
        print(f"✅ Successfully inserted {successful_inserts} new patients")
        print(f"📊 Total patients in database: {final_count}")
        print(f"📈 Database grew from {existing_count} to {final_count} patients\n")
    except Exception as e:
        print(f"✅ Successfully inserted {successful_inserts} new patients")
        print(f"⚠️  Could not verify final count: {e}\n")
    
    # Show sample patients
    print("📋 Sample of generated patients:")
    print("-" * 80)
    for patient in all_patients[:3]:
        print(f"\n{patient['patient_id']}: {patient['name']}, Age {patient['age']} ({patient['gender']})")
        print(f"  Room: {patient['room_number']}")
        print(f"  Diagnosis: {patient['primary_diagnosis']}")
        print(f"  Medications: {len(patient['medications'])} meds")
        print(f"  Allergies: {', '.join(patient['allergies']) if patient['allergies'] else 'None'}")
        print(f"  Fall Risk Score: {patient['fall_risk_score']}/10")
        print(f"  Code Status: {patient['code_status']}")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()

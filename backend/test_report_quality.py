"""
CascadeAI Report Quality Test Suite
=====================================
Runs the full draft generator against the canonical P087 Brian Harris scenario
and scores the output across 30 clinical quality checks.

Usage:
    python test_report_quality.py              # full run + score
    python test_report_quality.py --verbose    # full run + print raw JSON
    python test_report_quality.py --save       # saves last result to quality_last_run.json

The test bypasses Supabase entirely — uses fixed golden patient data so results
are reproducible and independent of what is in the database.
"""

from __future__ import annotations
import asyncio
import json
import sys
import uuid
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple

# ── golden test data ──────────────────────────────────────────────────────────

PATIENT_DATA = {
    "patient_id": "P087",
    "name": "Brian Harris",
    "age": 24,
    "room_number": "355",
    "allergies": [],
    "medications": [
        "Warfarin 5mg oral daily",
        "Omeprazole 20mg oral daily",
        "Amlodipine 10mg oral daily",
        "Lisinopril 10mg oral daily",
    ],
}

# Five updates matching the real P087 nurse dictation scenario
RAW_UPDATES = [
    {
        "time": "07:30",
        "type": "procedure",
        "text": (
            "Sputum culture collected and sent to lab at 7:30. Results pending."
        ),
    },
    {
        "time": "08:00",
        "type": "medication",
        "text": (
            "Warfarin 5mg given orally as scheduled at 8am. Omeprazole 20mg given "
            "with breakfast. Amlodipine 10mg was held this morning due to low blood "
            "pressure and hypotensive concerns. INR drawn earlier this morning, "
            "result pending."
        ),
    },
    {
        "time": "09:00",
        "type": "vital_signs",
        "text": (
            "Vitals at 9am: blood pressure 98 over 62, heart rate 112, respiratory "
            "rate 26, temperature 100.4 Fahrenheit, SpO2 91 percent on 4 litres "
            "nasal cannula. Patient is short of breath at rest and using accessory "
            "muscles."
        ),
    },
    {
        "time": "10:30",
        "type": "procedure",
        "text": (
            "Chest X-ray completed at 10:30. Results showing worsening bilateral "
            "infiltrates consistent with pneumonia. Radiology report is pending "
            "attending physician review."
        ),
    },
    {
        "time": "11:00",
        "type": "general",
        "text": (
            "Family updated at 11am. Daughter informed of patient's worsening "
            "condition. Family agreed to full code status. Patient is anxious about "
            "breathing and asking about going home. Patient ambulated to bathroom "
            "with assistance."
        ),
    },
]

# ── NEWS2 vital thresholds ─────────────────────────────────────────────────────
# SINGLE SOURCE OF TRUTH (trust stack Phase 2c): the threshold table lives in
# backend/clinical_rules.py and is shared by the runtime risk pipeline, this
# test suite, and the eval-pack graders. The local lambda copy that used to
# sit here (and was never actually invoked — expected severities were
# hardcoded) is gone; expected severities are now DERIVED from the rule table,
# so a table change cannot silently diverge from what this suite asserts.

from clinical_rules import NEWS2_THRESHOLDS, classify_vital  # noqa: F401 (table re-exported for graders)

EXPECTED_VITALS = {
    "hr":    {"value": 112,   "expected_severity": classify_vital("hr", 112)},
    "bp":    {"value": 98,    "expected_severity": classify_vital("bp_sys", 98)},  # systolic
    "temp":  {"value": 100.4, "expected_severity": classify_vital("temp_f", 100.4)},
    "spo2":  {"value": 91,    "expected_severity": classify_vital("spo2", 91)},
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_updates():
    """Build PatientUpdate objects from raw golden data."""
    from models import PatientUpdate
    updates = []
    base = datetime(2026, 4, 26)
    for raw in RAW_UPDATES:
        h, m = map(int, raw["time"].split(":"))
        ts = base.replace(hour=h, minute=m)
        updates.append(
            PatientUpdate(
                id=str(uuid.uuid4()),
                shift_id="TEST-SHIFT-P087",
                patient_id="P087",
                nurse_id="TEST-NURSE",
                timestamp=ts,
                update_type=raw["type"],
                transcription=raw["text"],
            )
        )
    return updates


def _parse_vital_value(value_str: str) -> float:
    """Extract numeric part from a vital value string like '112 bpm'."""
    import re
    nums = re.findall(r"[\d.]+", str(value_str))
    return float(nums[0]) if nums else 0.0


def _timeline_is_sorted(timeline: List[Dict]) -> bool:
    """Return True if timeline events are in strict chronological order."""
    from datetime import datetime as dt

    def to_minutes(t: str) -> int:
        for fmt in ("%I:%M %p", "%H:%M", "%I:%M%p"):
            try:
                parsed = dt.strptime(t.strip(), fmt)
                return parsed.hour * 60 + parsed.minute
            except ValueError:
                continue
        return -1

    times = [to_minutes(e.get("time", "")) for e in timeline]
    valid = [t for t in times if t >= 0]
    return valid == sorted(valid)


# ── individual checks ─────────────────────────────────────────────────────────

CheckResult = Tuple[bool, str]  # (passed, detail)


def check_all_sections_present(report: Dict) -> CheckResult:
    required = ["timeline", "current_status", "safety_alerts",
                "key_changes", "pending_actions", "narrative_summary"]
    missing = [k for k in required if k not in report]
    if missing:
        return False, f"Missing sections: {missing}"
    return True, "All 6 sections present"


# TIMELINE CHECKS ──────────────────────────────────────────────────────────────

def check_timeline_chronological(report: Dict) -> CheckResult:
    tl = report.get("timeline", [])
    if not tl:
        return False, "Timeline is empty"
    if _timeline_is_sorted(tl):
        return True, f"Timeline sorted correctly ({len(tl)} events)"
    times = [e.get("time", "?") for e in tl]
    return False, f"Timeline out of order: {times}"


def check_timeline_no_gray_clinical(report: Dict) -> CheckResult:
    tl = report.get("timeline", [])
    gray_clinical = [
        e for e in tl
        if isinstance(e, dict)
        and e.get("severity", "").upper() == "GRAY"
        and any(kw in e.get("event", "").lower()
                for kw in ["mg", "bp", "hr", "spo2", "rr", "temp",
                            "warfarin", "omeprazole", "amlodipine",
                            "x-ray", "culture", "family", "oxygen"])
    ]
    if gray_clinical:
        return False, f"{len(gray_clinical)} clinical event(s) wrongly marked GRAY"
    return True, "No clinical events marked GRAY"


def check_timeline_has_exact_values(report: Dict) -> CheckResult:
    tl = report.get("timeline", [])
    combined = " ".join(e.get("event", "") for e in tl if isinstance(e, dict))
    checks = {
        "BP 98/62 or 98 over 62": any(v in combined for v in ["98/62", "98 over 62", "98/6"]),
        "HR 112": "112" in combined,
        "SpO2 91%": "91" in combined,
        "RR 26": "26" in combined,
        "Temp 100.4": "100.4" in combined,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        return False, f"Missing exact values in timeline: {failed}"
    return True, "All exact vital values present in timeline"


def check_timeline_medication_names(report: Dict) -> CheckResult:
    tl = report.get("timeline", [])
    combined = " ".join(e.get("event", "") for e in tl if isinstance(e, dict)).lower()
    meds = ["warfarin", "omeprazole", "amlodipine"]
    missing = [m for m in meds if m not in combined]
    if missing:
        return False, f"Missing medication names in timeline: {missing}"
    return True, "All key medication names present in timeline"


def check_timeline_amlodipine_held(report: Dict) -> CheckResult:
    tl = report.get("timeline", [])
    combined = " ".join(e.get("event", "") for e in tl if isinstance(e, dict)).lower()
    if "amlodipine" in combined and ("held" in combined or "withheld" in combined):
        return True, "Amlodipine held event present in timeline"
    return False, "Timeline missing: Amlodipine held due to hypotension"


# VITAL SIGN CHECKS ────────────────────────────────────────────────────────────

def check_vital_hr_severity(report: Dict) -> CheckResult:
    vitals = report.get("current_status", {}).get("latest_vitals", {})
    hr = vitals.get("hr", {})
    if not isinstance(hr, dict):
        return False, f"HR vital not structured object: {hr}"
    sev = hr.get("severity", "").upper()
    expected = EXPECTED_VITALS["hr"]["expected_severity"]
    if sev == expected:
        return True, f"HR 112 bpm → {sev} (correct per NEWS2)"
    return False, f"HR 112 bpm → {sev} (expected {expected} per NEWS2)"


def check_vital_bp_severity(report: Dict) -> CheckResult:
    vitals = report.get("current_status", {}).get("latest_vitals", {})
    bp = vitals.get("bp", {})
    if not isinstance(bp, dict):
        return False, f"BP vital not structured object: {bp}"
    sev = bp.get("severity", "").upper()
    expected = EXPECTED_VITALS["bp"]["expected_severity"]
    if sev == expected:
        return True, f"BP 98/62 mmHg → {sev} (correct per NEWS2)"
    return False, f"BP 98/62 mmHg → {sev} (expected {expected} per NEWS2)"


def check_vital_temp_severity(report: Dict) -> CheckResult:
    vitals = report.get("current_status", {}).get("latest_vitals", {})
    temp = vitals.get("temp", {})
    if not isinstance(temp, dict):
        return False, f"Temp vital not structured object: {temp}"
    sev = temp.get("severity", "").upper()
    expected = EXPECTED_VITALS["temp"]["expected_severity"]
    if sev == expected:
        return True, f"Temp 100.4°F → {sev} (correct per NEWS2)"
    return False, f"Temp 100.4°F → {sev} (expected {expected} per NEWS2)"


def check_vital_spo2_severity(report: Dict) -> CheckResult:
    vitals = report.get("current_status", {}).get("latest_vitals", {})
    spo2 = vitals.get("spo2", {})
    if not isinstance(spo2, dict):
        return False, f"SpO2 vital not structured object: {spo2}"
    sev = spo2.get("severity", "").upper()
    expected = EXPECTED_VITALS["spo2"]["expected_severity"]
    if sev == expected:
        return True, f"SpO2 91% → {sev} (correct per NEWS2)"
    return False, f"SpO2 91% → {sev} (expected {expected} per NEWS2)"


def check_vital_spo2_notes_oxygen(report: Dict) -> CheckResult:
    vitals = report.get("current_status", {}).get("latest_vitals", {})
    spo2 = vitals.get("spo2", {})
    value = str(spo2.get("value", "") if isinstance(spo2, dict) else spo2).lower()
    if any(kw in value for kw in ["nc", "nasal", "l/min", "4l", "4 l", "oxygen", "o2"]):
        return True, f"SpO2 value notes supplemental oxygen: '{value}'"
    return False, f"SpO2 value should note '4L NC' — got: '{value}'"


# MEDICATION CHECKS ────────────────────────────────────────────────────────────

def check_amlodipine_conflicting(report: Dict) -> CheckResult:
    meds = report.get("current_status", {}).get("medications", [])
    for med in meds:
        if isinstance(med, dict):
            name = med.get("name", "").lower() + med.get("display", "").lower()
            if "amlodipine" in name:
                status = med.get("status", "").upper()
                if status == "CONFLICTING":
                    display = med.get("display", "")
                    if "held" in display.lower() or "held" in med.get("name", "").lower():
                        return True, f"Amlodipine → CONFLICTING with held note"
                    return False, f"Amlodipine → CONFLICTING but missing '— Held' note in display"
                return False, f"Amlodipine → {status} (expected CONFLICTING — it was held)"
    return False, "Amlodipine not found in medications list"


def check_warfarin_verified(report: Dict) -> CheckResult:
    meds = report.get("current_status", {}).get("medications", [])
    for med in meds:
        if isinstance(med, dict) and "warfarin" in med.get("name", "").lower():
            status = med.get("status", "").upper()
            if status == "VERIFIED":
                return True, "Warfarin → VERIFIED (in EMR, administered as scheduled)"
            return False, f"Warfarin → {status} (expected VERIFIED)"
    return False, "Warfarin not found in medications list"


# SAFETY ALERT CHECKS ──────────────────────────────────────────────────────────

def check_safety_alert_warfarin_omeprazole(report: Dict) -> CheckResult:
    alerts = report.get("safety_alerts", [])
    combined = " ".join(
        a.get("message", "") if isinstance(a, dict) else str(a)
        for a in alerts
    ).lower()
    if "warfarin" in combined and "omeprazole" in combined:
        if any(kw in combined for kw in ["cyp2c19", "inr", "interaction", "ppi", "metabolism"]):
            return True, "Warfarin+Omeprazole interaction alert present with mechanism"
        return False, "Warfarin+Omeprazole alert present but missing mechanism (CYP2C19/INR)"
    return False, "Missing: Warfarin+Omeprazole drug interaction safety alert"


def check_safety_alert_respiratory(report: Dict) -> CheckResult:
    alerts = report.get("safety_alerts", [])
    combined = " ".join(
        a.get("message", "") if isinstance(a, dict) else str(a)
        for a in alerts
    ).lower()
    keywords = ["respiratory", "rr 26", "spo2 91", "accessory", "breathin", "distress"]
    matched = [kw for kw in keywords if kw in combined]
    if len(matched) >= 2:
        return True, f"Respiratory distress alert present (keywords: {matched})"
    return False, f"Respiratory distress alert weak or missing (only matched: {matched})"


def check_safety_alerts_have_actions(report: Dict) -> CheckResult:
    """
    Every safety alert that IS present must include a recommended action.
    Zero alerts is not itself a failure here — plenty of genuinely benign
    updates correctly produce no safety alerts at all; that's checked
    elsewhere (e.g. scenario-specific graders), not by this structural rule.
    """
    alerts = report.get("safety_alerts", [])
    if not alerts:
        return True, "No safety alerts present (nothing to check)"
    actionless = []
    for a in alerts:
        if isinstance(a, dict):
            msg = a.get("message", "").lower()
            if not any(kw in msg for kw in
                       ["review", "notify", "monitor", "escalate",
                        "obtain", "reassess", "action", "consider"]):
                actionless.append(msg[:60])
    if actionless:
        return False, f"{len(actionless)} alert(s) missing recommended action"
    return True, f"All {len(alerts)} safety alerts include recommended actions"


def check_safety_alert_severity_red(report: Dict) -> CheckResult:
    alerts = report.get("safety_alerts", [])
    red_alerts = [
        a for a in alerts
        if isinstance(a, dict) and a.get("severity", "").upper() == "RED"
    ]
    if len(red_alerts) >= 1:
        return True, f"{len(red_alerts)} RED safety alert(s) present"
    return False, "No RED severity safety alerts (expected at least 1 for this patient)"


# PENDING ACTIONS CHECKS ───────────────────────────────────────────────────────

def check_pending_actions_count(report: Dict) -> CheckResult:
    actions = report.get("pending_actions", [])
    count = len(actions)
    if count >= 5:
        return True, f"{count} pending actions (expected 5+ for complex patient)"
    return False, f"Only {count} pending actions (expected 5+ for this critically ill patient)"


def check_pending_inr_action(report: Dict) -> CheckResult:
    actions = report.get("pending_actions", [])
    combined = " ".join(
        a.get("action", "") if isinstance(a, dict) else str(a)
        for a in actions
    ).lower()
    if "inr" in combined and any(kw in combined for kw in ["review", "obtain", "check", "urgent"]):
        return True, "INR review pending action present"
    return False, "Missing: CRITICAL pending action to obtain/review INR result"


def check_pending_chest_xray_action(report: Dict) -> CheckResult:
    actions = report.get("pending_actions", [])
    combined = " ".join(
        a.get("action", "") if isinstance(a, dict) else str(a)
        for a in actions
    ).lower()
    if any(kw in combined for kw in ["x-ray", "xray", "chest", "radiology", "imaging"]):
        return True, "Chest X-ray / radiology physician review action present"
    return False, "Missing: pending action for attending physician to review chest X-ray"


def check_pending_respiratory_escalation(report: Dict) -> CheckResult:
    actions = report.get("pending_actions", [])
    combined = " ".join(
        a.get("action", "") if isinstance(a, dict) else str(a)
        for a in actions
    ).lower()
    if any(kw in combined for kw in ["escalat", "oxygen", "respiratory", "o2", "abg"]):
        return True, "Respiratory escalation action present"
    return False, "Missing: CRITICAL action to escalate respiratory distress"


def check_pending_antihypertensive_action(report: Dict) -> CheckResult:
    actions = report.get("pending_actions", [])
    combined = " ".join(
        a.get("action", "") if isinstance(a, dict) else str(a)
        for a in actions
    ).lower()
    if any(kw in combined for kw in ["amlodipine", "antihypertensive", "bp 98", "blood pressure"]):
        return True, "Antihypertensive reassessment action present"
    return False, "Missing: HIGH action to reassess antihypertensive regimen (amlodipine held)"


def check_pending_actions_have_verbs(report: Dict) -> CheckResult:
    """
    Verb list expanded 4 Jul 2026 after a live eval-pack run against the real
    model surfaced clinically legitimate actions this check was wrongly
    flagging (e.g. "Verify lisinopril was administered...", "Perform 12-lead
    ECG...", "Initiate potassium-lowering protocol...", "Contact prescribing
    clinician...") — these are perfectly good actions; the whitelist was
    just incomplete, built around one original hand-written test fixture.
    """
    actions = report.get("pending_actions", [])
    verbs = ["obtain", "notify", "notification", "reassess", "monitor", "hold",
             "escalate", "review", "reconcile", "request", "adjust", "assess",
             "check", "verify", "perform", "initiate", "establish", "contact",
             "continue", "discontinue", "administer", "start", "stop",
             "document", "ensure", "confirm", "recheck", "repeat", "consider",
             "prepare", "evaluate"]
    weak = []
    for a in actions:
        text = (a.get("action", "") if isinstance(a, dict) else str(a)).lower()
        if not any(text.startswith(v) or f" {v} " in f" {text} " for v in verbs):
            weak.append(text[:60])
    if weak:
        return False, f"{len(weak)} action(s) missing action verb: {weak}"
    return True, "All pending actions start with action verbs"


# NARRATIVE CHECKS ─────────────────────────────────────────────────────────────

def check_narrative_length(report: Dict) -> CheckResult:
    narrative = report.get("narrative_summary", "")
    words = len(narrative.split())
    if words >= 200:
        return True, f"Narrative is {words} words (minimum 200)"
    return False, f"Narrative too short: {words} words (minimum 200)"


def check_narrative_contains_vitals(report: Dict) -> CheckResult:
    narrative = report.get("narrative_summary", "")
    checks = {
        "BP 98/62": any(v in narrative for v in ["98/62", "98 over 62"]),
        "HR 112":   "112" in narrative,
        "SpO2 91%": "91" in narrative,
        "RR 26":    "26" in narrative,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        return False, f"Narrative missing vital values: {failed}"
    return True, "Narrative contains all key vital values"


def check_narrative_contains_meds(report: Dict) -> CheckResult:
    narrative = report.get("narrative_summary", "").lower()
    meds = ["warfarin", "omeprazole", "amlodipine"]
    missing = [m for m in meds if m not in narrative]
    if missing:
        return False, f"Narrative missing medication names: {missing}"
    return True, "Narrative mentions all key medications"


def check_narrative_mentions_pending(report: Dict) -> CheckResult:
    narrative = report.get("narrative_summary", "").lower()
    pending = ["inr", "sputum", "radiology", "x-ray", "pending", "culture"]
    matched = [p for p in pending if p in narrative]
    if len(matched) >= 2:
        return True, f"Narrative mentions pending items: {matched}"
    return False, f"Narrative should mention pending results — only found: {matched}"


def check_narrative_critical_action(report: Dict) -> CheckResult:
    narrative = report.get("narrative_summary", "").lower()
    if any(kw in narrative for kw in ["critical action", "urgently", "immediately",
                                       "escalate", "urgent"]):
        return True, "Narrative includes critical action statement"
    return False, "Narrative missing critical action / urgency statement"


# ── test runner ───────────────────────────────────────────────────────────────

CHECKS = [
    # Structure
    ("Structure",  "All required report sections present",     check_all_sections_present),
    # Timeline
    ("Timeline",   "Events in chronological order",            check_timeline_chronological),
    ("Timeline",   "No clinical events wrongly marked GRAY",   check_timeline_no_gray_clinical),
    ("Timeline",   "Exact vital values in event descriptions", check_timeline_has_exact_values),
    ("Timeline",   "Medication names in event descriptions",   check_timeline_medication_names),
    ("Timeline",   "Amlodipine held event recorded",           check_timeline_amlodipine_held),
    # Vitals
    ("Vitals",     "HR 112 → ORANGE (NEWS2)",                  check_vital_hr_severity),
    ("Vitals",     "BP 98/62 → ORANGE (NEWS2)",                check_vital_bp_severity),
    ("Vitals",     "Temp 100.4°F → YELLOW (NEWS2)",            check_vital_temp_severity),
    ("Vitals",     "SpO2 91% → RED (NEWS2)",                   check_vital_spo2_severity),
    ("Vitals",     "SpO2 value notes supplemental oxygen",     check_vital_spo2_notes_oxygen),
    # Medications
    ("Meds",       "Amlodipine → CONFLICTING with held note",  check_amlodipine_conflicting),
    ("Meds",       "Warfarin → VERIFIED",                      check_warfarin_verified),
    # Safety Alerts
    ("Safety",     "Warfarin+Omeprazole alert with mechanism", check_safety_alert_warfarin_omeprazole),
    ("Safety",     "Respiratory distress alert present",       check_safety_alert_respiratory),
    ("Safety",     "All alerts include recommended actions",   check_safety_alerts_have_actions),
    ("Safety",     "At least 1 RED severity alert",            check_safety_alert_severity_red),
    # Pending Actions
    ("Pending",    "5+ pending actions for complex patient",   check_pending_actions_count),
    ("Pending",    "CRITICAL: INR review action",              check_pending_inr_action),
    ("Pending",    "CRITICAL: Chest X-ray physician review",   check_pending_chest_xray_action),
    ("Pending",    "CRITICAL: Respiratory escalation",         check_pending_respiratory_escalation),
    ("Pending",    "HIGH: Antihypertensive reassessment",      check_pending_antihypertensive_action),
    ("Pending",    "All actions start with action verb",       check_pending_actions_have_verbs),
    # Narrative
    ("Narrative",  "200+ words",                               check_narrative_length),
    ("Narrative",  "Contains exact vital values",              check_narrative_contains_vitals),
    ("Narrative",  "Mentions all key medications",             check_narrative_contains_meds),
    ("Narrative",  "Mentions pending results",                 check_narrative_mentions_pending),
    ("Narrative",  "Includes critical action statement",       check_narrative_critical_action),
]

TOTAL_CHECKS = len(CHECKS)

CATEGORY_WEIGHTS = {
    "Structure": 1, "Timeline": 5, "Vitals": 5,
    "Meds": 2, "Safety": 4, "Pending": 6, "Narrative": 5,
}


async def run_quality_test(verbose: bool = False, save: bool = False):
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from draft_generator import DraftGenerator

    print("\n" + "=" * 60)
    print("  CascadeAI Report Quality Test — P087 Brian Harris")
    print("=" * 60)
    print(f"  Checks: {TOTAL_CHECKS}  |  Patient: Brian Harris (P087, Room 355, Age 24)")
    print(f"  Scenario: 5 updates — medications, vitals, X-ray, culture, family")
    print("=" * 60 + "\n")

    # Build updates and organise them
    updates = _build_updates()
    generator = DraftGenerator()
    organised = generator._organize_updates(updates)

    print("⏳ Calling Groq API (3 LLM calls) — please wait...\n")
    t0 = time.time()

    report = await generator._generate_handoff_summary_async(
        PATIENT_DATA, organised, len(updates)
    )

    elapsed = time.time() - t0
    print(f"\n✅ Report generated in {elapsed:.1f}s\n")

    if verbose:
        print("── RAW REPORT JSON ──────────────────────────────────────")
        print(json.dumps(report, indent=2, default=str))
        print("─────────────────────────────────────────────────────────\n")

    # Run all checks
    results: List[Tuple[str, str, bool, str]] = []
    for category, label, fn in CHECKS:
        try:
            passed, detail = fn(report)
        except Exception as e:
            passed, detail = False, f"Check threw exception: {e}"
        results.append((category, label, passed, detail))

    # Print results grouped by category
    current_cat = None
    passed_total = 0

    for category, label, passed, detail in results:
        if category != current_cat:
            current_cat = category
            print(f"\n── {category.upper()} {'─' * (50 - len(category))}")
        icon = "✅" if passed else "❌"
        status = "PASS" if passed else "FAIL"
        print(f"  {icon} {status:4}  {label}")
        if not passed:
            print(f"           ↳ {detail}")
        if passed:
            passed_total += 1

    # Score
    score_10 = round((passed_total / TOTAL_CHECKS) * 10, 1)

    print("\n" + "=" * 60)
    print(f"  RESULT: {passed_total}/{TOTAL_CHECKS} checks passed")
    print(f"  SCORE:  {score_10}/10.0")

    if score_10 == 10.0:
        print("  🏆 PERFECT — 10/10. Production ready.")
    elif score_10 >= 9.0:
        print("  🟡 NEAR PERFECT — fix the ❌ items above.")
    elif score_10 >= 7.0:
        print("  🟠 GOOD BUT NOT ENOUGH — needs work before demo.")
    else:
        print("  🔴 FAILING — significant prompt issues to fix.")

    print(f"  API time: {elapsed:.1f}s")
    print("=" * 60 + "\n")

    if save:
        out = {
            "timestamp": datetime.now().isoformat(),
            "score": score_10,
            "passed": passed_total,
            "total": TOTAL_CHECKS,
            "elapsed_seconds": round(elapsed, 1),
            "results": [
                {"category": c, "check": l, "passed": p, "detail": d}
                for c, l, p, d in results
            ],
            "report": report,
        }
        path = "quality_last_run.json"
        with open(path, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"  💾 Saved to {path}\n")

    return score_10, results, report


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    save    = "--save"    in sys.argv or "-s" in sys.argv
    asyncio.run(run_quality_test(verbose=verbose, save=save))


if __name__ == "__main__":
    main()

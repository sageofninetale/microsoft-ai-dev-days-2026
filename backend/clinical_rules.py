"""
Clinical scoring rule tables (trust stack Phase 2c).

ONE SOURCE OF TRUTH: NEWS2 vital thresholds, the isolated-diastolic trigger,
and the risk weights/threshold live HERE and only here. The runtime pipeline
(risk_pipeline.py), the draft generator's prompt constants, the quality test
suite (test_report_quality.py) and the eval-pack graders all import from this
module — none of them may carry their own copy of these numbers.

All scoring in this module is DETERMINISTIC code / lookup tables. Clinical
scoring is never delegated to LLM judgment: the LLM writes prose, this module
decides severities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# NEWS2 vital thresholds (NHS NEWS2-based, as already used by the report
# prompts and the quality suite). Band = (severity, low, high), inclusive;
# None = unbounded. First matching band wins; a value falling in a gap
# between bands (e.g. Temp 100.35°F) returns None ("unscored") rather than
# being silently rounded into a band.
# ============================================================================

Band = Tuple[str, Optional[float], Optional[float]]

NEWS2_THRESHOLDS: Dict[str, List[Band]] = {
    "hr": [
        ("RED",    131,  None),
        ("RED",    None, 40),
        ("ORANGE", 111,  130),
        ("ORANGE", 41,   50),
        ("YELLOW", 91,   110),
        ("YELLOW", 51,   60),
        ("GREEN",  61,   90),
    ],
    "bp_sys": [
        ("RED",    220,  None),
        ("RED",    None, 90),
        ("ORANGE", 91,   100),
        ("YELLOW", 101,  110),
        ("GREEN",  111,  219),
    ],
    "temp_f": [
        ("RED",    102.3, None),
        ("RED",    None,  95.0),
        ("YELLOW", 100.4, 102.2),
        ("GREEN",  97.9,  100.3),
    ],
    "spo2": [
        ("RED",    None, 91),
        ("ORANGE", 92,   93),
        ("YELLOW", 94,   95),
        ("GREEN",  96,   None),
    ],
}


def classify_vital(vital: str, value: float) -> Optional[str]:
    """
    Deterministically classify a vital reading against the NEWS2 table.
    Returns "RED"/"ORANGE"/"YELLOW"/"GREEN", or None if the vital is unknown
    to the table or the value falls in a gap between bands.
    """
    bands = NEWS2_THRESHOLDS.get(vital)
    if bands is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    for severity, low, high in bands:
        if (low is None or v >= low) and (high is None or v <= high):
            return severity
    return None


# ============================================================================
# Isolated elevated diastolic BP (known NEWS2 gap: NEWS2 scores SYSTOLIC BP
# only, so a high diastolic under a normal systolic is invisible to it).
#
# ⚠️ PLACEHOLDER — needs Sakshi clinical sign-off. These two thresholds were
# agreed as a reasonable starting point by the product owner in a prior
# session; they are NOT clinically validated. Do not rely on them in a real
# deployment until Sakshi (clinical advisor) confirms or corrects them.
# (draft_generator.py's prompt constants alias these — change them HERE only.)
# ============================================================================

DIASTOLIC_BP_HIGH_THRESHOLD = 100      # mmHg — diastolic >= this, systolic normal -> HIGH
DIASTOLIC_BP_CRITICAL_THRESHOLD = 120  # mmHg — diastolic >= this, systolic normal -> CRITICAL


def classify_isolated_diastolic(systolic: Optional[float], diastolic: Optional[float]) -> Optional[str]:
    """
    Deterministic isolated-high-diastolic trigger. Fires only when the
    diastolic is elevated while the systolic is normal per NEWS2 (an abnormal
    systolic is already caught by classify_vital("bp_sys", ...) — this covers
    the reading NEWS2 cannot see). Returns "CRITICAL"/"HIGH"/None.
    """
    if diastolic is None:
        return None
    try:
        dia = float(diastolic)
    except (TypeError, ValueError):
        return None
    # Systolic must be present AND normal for the trigger to be "isolated".
    if systolic is None or classify_vital("bp_sys", systolic) != "GREEN":
        return None
    if dia >= DIASTOLIC_BP_CRITICAL_THRESHOLD:  # PLACEHOLDER threshold — see above
        return "CRITICAL"
    if dia >= DIASTOLIC_BP_HIGH_THRESHOLD:      # PLACEHOLDER threshold — see above
        return "HIGH"
    return None


# ============================================================================
# Risk scoring constants (used by risk_pipeline.calculate_overall_risk —
# the 20/40/40 formula ported from coordinator_agent.py).
# ============================================================================

RISK_WEIGHT_CONFIDENCE = 0.20     # handoff/extraction confidence, inverted
RISK_WEIGHT_VERIFICATION = 0.40   # EMR verification findings
RISK_WEIGHT_PROTOCOL = 0.40       # protocol compliance, inverted

# Severity weights shared by the verification and protocol scorers (identical
# values already used in verification_agent.py and protocol_agent.py).
SEVERITY_WEIGHTS: Dict[str, float] = {
    "CRITICAL": 1.0,
    "HIGH": 0.7,
    "MEDIUM": 0.4,
    "LOW": 0.2,
}

# Risk gate (Phase 2d): at/above this overall score a draft is presented as
# "⚠ NEEDS ATTENTION", never as a clean report. 0.4 matches the existing
# MODERATE boundary in models.FinalHandoff.get_risk_level().
RISK_ATTENTION_THRESHOLD = 0.4


def risk_level(score: float) -> str:
    """Same banding as models.FinalHandoff.get_risk_level()."""
    if score >= 0.7:
        return "HIGH"
    if score >= RISK_ATTENTION_THRESHOLD:
        return "MODERATE"
    return "LOW"


# ============================================================================
# Vital-string parsing (deterministic, shared by runtime + graders)
# ============================================================================

def parse_bp(bp_value: Any) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse a BP reading like "98/62", "98/62 mmHg", "110/70 (diastolic assumed)".
    Returns (systolic, diastolic); either side None if unparseable/absent.
    A missing diastolic must stay None — never guessed (see eval scenario
    'BP diastolic inconsistency', patient P098).
    """
    import re
    s = str(bp_value or "")
    m = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d{2,3})", s)
    if m:
        return float(m.group(1)), None
    return None, None


def parse_number(value: Any) -> Optional[float]:
    """First numeric token from strings like '112 bpm', '91%', '100.4°F'."""
    import re
    m = re.search(r"[\d.]+", str(value or ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None

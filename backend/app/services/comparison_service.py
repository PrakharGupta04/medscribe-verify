import json
import re
from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple

from backend.app.db.models import Consultation, IntakeData
from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ComparisonItem,
    ComparisonResults,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_json_safely(val: Optional[str], default=None):
    if not val:
        return default if default is not None else []
    try:
        return json.loads(val)
    except Exception:
        return default if default is not None else []


def extract_individual_symptom_concepts(
    raw_symptoms,
    chief_complaint: Optional[str] = None,
) -> List[str]:
    """
    Extracts individual normalized clinical symptom concepts without bundling.
    Splits composite/bundled strings (e.g. 'Fever, Sore Throat') into discrete concepts.
    Deduplicates case-insensitively while preserving human-readable casing.
    """
    concepts: List[str] = []
    seen: Set[str] = set()

    def add_token(text: str):
        if not text:
            return
        # Split on commas, semicolons, and newlines
        parts = re.split(r"[,;\n]+", text)
        for part in parts:
            p = part.strip()
            # If part connects short symptom phrases with 'and', split them
            and_parts = [p]
            if " and " in p.lower():
                split_and = re.split(r"\s+and\s+", p, flags=re.IGNORECASE)
                if all(len(sp.strip().split()) <= 4 for sp in split_and):
                    and_parts = split_and

            for ap in and_parts:
                clean_sym = ap.strip().strip(". ")
                if not clean_sym or clean_sym.lower() in {
                    "none",
                    "no",
                    "n/a",
                    "none reported",
                    "no symptoms",
                    "none of the above",
                }:
                    continue
                sym_key = clean_sym.lower()
                if sym_key not in seen:
                    seen.add(sym_key)
                    concepts.append(clean_sym)

    if raw_symptoms:
        if isinstance(raw_symptoms, str):
            add_token(raw_symptoms)
        elif isinstance(raw_symptoms, list):
            for item in raw_symptoms:
                if isinstance(item, dict):
                    add_token(item.get("name") or "")
                elif isinstance(item, str):
                    add_token(item)

    if chief_complaint:
        add_token(chief_complaint)

    return concepts


def concept_matches(c1: str, c2: str) -> bool:
    """Checks if two clinical concept strings refer to the same symptom concept."""
    a = c1.strip().lower()
    b = c2.strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) > 3 and len(b) > 3 and a.rstrip("s") == b.rstrip("s"):
        return True
    # Whole-word substring match: e.g. 'high fever' and 'fever'
    if re.search(r"\b" + re.escape(a) + r"\b", b) or re.search(r"\b" + re.escape(b) + r"\b", a):
        return True
    return False


def concept_in_transcript(concept: str, transcript_lower: str) -> bool:
    """Checks if an individual clinical concept appears in the transcript with word boundaries."""
    c = concept.strip().lower()
    if not c or not transcript_lower:
        return False
    if re.search(r"\b" + re.escape(c) + r"\b", transcript_lower):
        return True
    if c.endswith("s") and len(c) > 3:
        if re.search(r"\b" + re.escape(c[:-1]) + r"\b", transcript_lower):
            return True
    return False


def compare_intake_and_consultation(
    intake_data: Optional[IntakeData],
    consultation: Consultation,
    clinical_data: Optional[ClinicalExtraction] = None,
) -> ComparisonResults:
    """
    Comparison / Conflict Intelligence Agent (Agent 4):
    Compares patient-reported pre-consultation intake data (Module 1)
    with consultation findings, transcript, and clinical extraction (Module 2).
    Surfaces confirmed facts, newly uncovered information, unmentioned items,
    and potential discrepancies in neutral clinical language for doctor review.

    CRITICAL RULES:
    1. Compare symptoms as individual normalized clinical concepts, never as composite bundled strings.
    2. Never infer all concepts in a composite intake string are confirmed merely because one concept matches.
    3. Do not set 'resolution' on automatic system classifications. A doctor resolution is ONLY set
       when a clinician explicitly submits one via the resolution control.
    4. Maintain neutral clinical taxonomy: confirmed, new_in_consultation, not_mentioned_in_consultation, discrepancy.
    """
    if not intake_data:
        return ComparisonResults(
            items=[
                ComparisonItem(
                    id="comp-direct-1",
                    category="general",
                    type="new_in_consultation",
                    label="Direct Clinical Consultation",
                    intake_value="No prior intake form submitted",
                    consultation_value="Direct doctor consultation",
                    severity="info",
                    description="Consultation initiated directly in clinic without a self-reported intake form.",
                    status="unresolved",
                    resolution=None,
                )
            ],
            total_items=1,
            confirmed_count=0,
            new_count=1,
            not_mentioned_count=0,
            discrepancy_count=0,
            compared_at=utc_now(),
        )

    # 1. Parse Module 1 clinical facts into discrete concepts
    m1_symptoms = extract_individual_symptom_concepts(
        raw_symptoms=parse_json_safely(intake_data.symptoms, []),
        chief_complaint=intake_data.chief_complaint,
    )
    m1_duration = (intake_data.duration or "").strip()
    m1_meds = (intake_data.medications or "").strip()
    m1_allergies = (intake_data.allergies or "").strip()
    m1_conditions = parse_json_safely(intake_data.conditions, [])
    if isinstance(m1_conditions, str):
        m1_conditions = [m1_conditions]

    # 2. Parse Module 2 clinical facts
    if not clinical_data and consultation.extracted_clinical_data:
        try:
            clinical_data = ClinicalExtraction.model_validate_json(consultation.extracted_clinical_data)
        except Exception:
            clinical_data = None

    transcript_lower = (consultation.transcript or "").lower()

    # Split and normalize Module 2 symptom names so composite extraction strings are also handled as individual concepts
    m2_symptoms_clean: List[Tuple[str, Optional[str]]] = []
    if clinical_data and clinical_data.symptoms:
        for s in clinical_data.symptoms:
            parts = re.split(r"[,;]+", s.name)
            for p in parts:
                p_c = p.strip()
                if p_c and p_c.lower() not in {"none", "no"}:
                    m2_symptoms_clean.append((p_c, s.details))

    m2_symptom_names = [name for name, _ in m2_symptoms_clean]
    m2_meds = [m.name for m in (clinical_data.medications if clinical_data else [])]
    m2_allergies = [a.substance for a in (clinical_data.allergies if clinical_data else [])]
    m2_history = [h for h in (clinical_data.medical_history if clinical_data else [])]

    items: List[ComparisonItem] = []
    item_idx = 1
    matched_m2_symptoms: Set[str] = set()

    # 1. COMPARE SYMPTOMS INDIVIDUALLY
    for sym_clean in m1_symptoms:
        # Check if sym_clean matches any extracted symptom in M2
        matched_m2_name = None
        for m2_s in m2_symptom_names:
            if concept_matches(sym_clean, m2_s):
                matched_m2_name = m2_s
                break

        is_in_transcript = concept_in_transcript(sym_clean, transcript_lower)
        is_in_m2 = (matched_m2_name is not None) or is_in_transcript

        if is_in_m2:
            if matched_m2_name:
                matched_m2_symptoms.add(matched_m2_name.lower())

            items.append(
                ComparisonItem(
                    id=f"comp-sym-{item_idx}",
                    category="symptoms",
                    type="confirmed",
                    label=f"Symptom: {sym_clean}",
                    intake_value=f"Reported in pre-consult intake ({sym_clean})",
                    consultation_value="Discussed during consultation",
                    severity="info",
                    description=f"Symptom '{sym_clean}' confirmed in both patient intake and consultation discussion.",
                    status="unresolved",
                    resolution=None,
                )
            )
        else:
            items.append(
                ComparisonItem(
                    id=f"comp-sym-{item_idx}",
                    category="symptoms",
                    type="not_mentioned_in_consultation",
                    label=f"Symptom: {sym_clean}",
                    intake_value=f"Reported in pre-consult intake ({sym_clean})",
                    consultation_value="Not explicitly discussed during consultation",
                    severity="neutral",
                    description=f"Symptom '{sym_clean}' was noted in patient intake but not mentioned during the consultation.",
                    status="unresolved",
                    resolution=None,
                )
            )
        item_idx += 1

    # Check for newly discovered symptoms in consultation that were not in Module 1
    for s_name, s_details in m2_symptoms_clean:
        if s_name.lower() in matched_m2_symptoms:
            continue
        # Check if s_name matches any Module 1 symptom concept
        if not any(concept_matches(s_name, m1_s) for m1_s in m1_symptoms):
            details_str = f" ({s_details})" if s_details else ""
            items.append(
                ComparisonItem(
                    id=f"comp-newsym-{item_idx}",
                    category="symptoms",
                    type="new_in_consultation",
                    label=f"New Finding: {s_name}",
                    intake_value="Not reported in intake questionnaire",
                    consultation_value=f"Disclosed during consultation: {s_name}{details_str}",
                    severity="info",
                    description=f"New clinical symptom '{s_name}' was uncovered during the doctor consultation.",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1

    # 2. COMPARE DURATION
    consult_duration = None
    if clinical_data and clinical_data.symptoms:
        for s in clinical_data.symptoms:
            if s.duration:
                consult_duration = s.duration
                break

    if m1_duration and consult_duration:
        m1_num = re.findall(r"\d+", m1_duration)
        m2_num = re.findall(r"\d+", consult_duration)
        # Check if numbers overlap or differ
        if m1_num and m2_num:
            m1_nums_set = set(m1_num)
            m2_nums_set = set(m2_num)
            has_overlap = bool(m1_nums_set.intersection(m2_nums_set))
            if not has_overlap and m1_num[0] != m2_num[0]:
                items.append(
                    ComparisonItem(
                        id=f"comp-dur-{item_idx}",
                        category="duration",
                        type="discrepancy",
                        label="Symptom Duration",
                        intake_value=m1_duration,
                        consultation_value=consult_duration,
                        severity="warning",
                        description=f"Difference detected: Intake reported duration '{m1_duration}', whereas consultation noted '{consult_duration}'.",
                        status="unresolved",
                        resolution=None,
                    )
                )
            else:
                items.append(
                    ComparisonItem(
                        id=f"comp-dur-{item_idx}",
                        category="duration",
                        type="confirmed",
                        label="Symptom Duration",
                        intake_value=m1_duration,
                        consultation_value=consult_duration,
                        severity="info",
                        description=f"Symptom duration is consistent between intake ({m1_duration}) and consultation ({consult_duration}).",
                        status="unresolved",
                        resolution=None,
                    )
                )
        item_idx += 1

    # 3. COMPARE MEDICATIONS
    m1_no_meds = not m1_meds or m1_meds.lower() in {
        "none",
        "no",
        "n/a",
        "none reported",
        "no medications",
        "no current medications",
    }
    m2_has_meds = len(m2_meds) > 0

    if m1_no_meds and m2_has_meds:
        # Patient reported no medications in pre-intake, but active medications disclosed in consultation
        for med in m2_meds:
            items.append(
                ComparisonItem(
                    id=f"comp-med-{item_idx}",
                    category="medications",
                    type="new_in_consultation",
                    label=f"Newly Disclosed Medication: {med}",
                    intake_value=m1_meds if m1_meds else "None reported",
                    consultation_value=med,
                    severity="info",
                    description=f"Medication '{med}' was disclosed during consultation (not listed in pre-intake questionnaire).",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1
    elif not m1_no_meds and not m2_has_meds:
        items.append(
            ComparisonItem(
                id=f"comp-med-{item_idx}",
                category="medications",
                type="not_mentioned_in_consultation",
                label="Current Medications",
                intake_value=m1_meds,
                consultation_value="Not discussed in consultation",
                severity="info",
                description=f"Medications noted in intake ({m1_meds}) were not discussed during the consultation.",
                status="unresolved",
                resolution=None,
            )
        )
        item_idx += 1
    elif not m1_no_meds and m2_has_meds:
        m1_lower = m1_meds.lower()
        matched_meds = [m for m in m2_meds if m.lower() in m1_lower]
        new_meds = [m for m in m2_meds if m.lower() not in m1_lower]
        if matched_meds:
            items.append(
                ComparisonItem(
                    id=f"comp-med-{item_idx}",
                    category="medications",
                    type="confirmed",
                    label="Current Medications",
                    intake_value=m1_meds,
                    consultation_value=", ".join(matched_meds),
                    severity="info",
                    description=f"Medications confirmed in both intake and consultation: {', '.join(matched_meds)}.",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1
        if new_meds:
            items.append(
                ComparisonItem(
                    id=f"comp-med-{item_idx}",
                    category="medications",
                    type="new_in_consultation",
                    label="Newly Disclosed Medication",
                    intake_value=m1_meds,
                    consultation_value=", ".join(new_meds),
                    severity="info",
                    description=f"New medication disclosed during consultation: {', '.join(new_meds)}.",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1

    # 4. COMPARE ALLERGIES
    m1_no_allergies = not m1_allergies or m1_allergies.lower() in {
        "none",
        "no",
        "n/a",
        "no allergies",
        "none reported",
        "no known allergies",
        "no known drug allergies",
    }
    m2_has_allergies = len(m2_allergies) > 0

    if m1_no_allergies and m2_has_allergies:
        items.append(
            ComparisonItem(
                id=f"comp-alg-{item_idx}",
                category="allergies",
                type="discrepancy",
                label="Allergy Disclosure",
                intake_value=m1_allergies if m1_allergies else "No known allergies reported",
                consultation_value=", ".join(m2_allergies),
                severity="warning",
                description=f"Potential discrepancy: Patient reported no known allergies in intake, but disclosed allergy during consultation ({', '.join(m2_allergies)}).",
                status="unresolved",
                resolution=None,
            )
        )
        item_idx += 1
    elif not m1_no_allergies and not m2_has_allergies:
        items.append(
            ComparisonItem(
                id=f"comp-alg-{item_idx}",
                category="allergies",
                type="not_mentioned_in_consultation",
                label="Documented Allergy Alert",
                intake_value=m1_allergies,
                consultation_value="Not explicitly discussed during consultation",
                severity="warning",
                description=f"Safety notice: Allergy '{m1_allergies}' reported in pre-consult intake was not discussed in consultation.",
                status="unresolved",
                resolution=None,
            )
        )
        item_idx += 1
    elif not m1_no_allergies and m2_has_allergies:
        m1_alg_lower = m1_allergies.lower()
        matched = [
            a
            for a in m2_allergies
            if a.lower() in m1_alg_lower or any(w in m1_alg_lower for w in a.lower().split())
        ]
        if matched:
            items.append(
                ComparisonItem(
                    id=f"comp-alg-{item_idx}",
                    category="allergies",
                    type="confirmed",
                    label="Confirmed Allergy",
                    intake_value=m1_allergies,
                    consultation_value=", ".join(matched),
                    severity="info",
                    description=f"Allergy confirmed in both intake and doctor consultation: {', '.join(matched)}.",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1
        new_algs = [a for a in m2_allergies if a not in matched]
        if new_algs:
            items.append(
                ComparisonItem(
                    id=f"comp-alg-{item_idx}",
                    category="allergies",
                    type="discrepancy",
                    label="Additional Allergy Disclosed",
                    intake_value=m1_allergies,
                    consultation_value=", ".join(new_algs),
                    severity="warning",
                    description=f"Potential discrepancy: Additional allergy disclosed during consultation: {', '.join(new_algs)}.",
                    status="unresolved",
                    resolution=None,
                )
            )
            item_idx += 1

    # 5. COMPARE CONDITIONS / MEDICAL HISTORY
    m1_conditions_clean = [
        c
        for c in m1_conditions
        if c and c.lower() not in {"none", "none of the above", "no medical history"}
    ]
    if m1_conditions_clean:
        for cond in m1_conditions_clean:
            is_discussed = (
                any(cond.lower() in h.lower() for h in m2_history)
                or re.search(r"\b" + re.escape(cond.lower()) + r"\b", transcript_lower)
            )
            if is_discussed:
                items.append(
                    ComparisonItem(
                        id=f"comp-cond-{item_idx}",
                        category="history",
                        type="confirmed",
                        label=f"Past Condition: {cond}",
                        intake_value=cond,
                        consultation_value="Discussed during consultation",
                        severity="info",
                        description=f"Past medical condition '{cond}' confirmed in both sources.",
                        status="unresolved",
                        resolution=None,
                    )
                )
            else:
                items.append(
                    ComparisonItem(
                        id=f"comp-cond-{item_idx}",
                        category="history",
                        type="not_mentioned_in_consultation",
                        label=f"Past Condition: {cond}",
                        intake_value=cond,
                        consultation_value="Not discussed in consultation",
                        severity="neutral",
                        description=f"Past medical condition '{cond}' reported in intake was not mentioned during consultation.",
                        status="unresolved",
                        resolution=None,
                    )
                )
            item_idx += 1

    # Summarize metrics
    confirmed_cnt = sum(1 for it in items if it.type == "confirmed")
    new_cnt = sum(1 for it in items if it.type == "new_in_consultation")
    not_mentioned_cnt = sum(1 for it in items if it.type == "not_mentioned_in_consultation")
    discrepancy_cnt = sum(1 for it in items if it.type == "discrepancy")

    return ComparisonResults(
        items=items,
        total_items=len(items),
        confirmed_count=confirmed_cnt,
        new_count=new_cnt,
        not_mentioned_count=not_mentioned_cnt,
        discrepancy_count=discrepancy_cnt,
        compared_at=utc_now(),
    )


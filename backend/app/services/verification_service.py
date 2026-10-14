import re
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.schemas.consultation import (
    ClinicalExtraction,
    SoapDraft,
    VerificationClaim,
    VerificationResults,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def split_into_sentences(text: str) -> List[str]:
    """Splits a paragraph into discrete clinical claim sentences."""
    if not text:
        return []
    # Split by periods, semicolons, or newlines followed by space or end
    raw_sentences = re.split(r"(?<=[.!?;\n])\s+", text.strip())
    sentences = [s.strip().rstrip(".;") for s in raw_sentences if s.strip()]
    return sentences


def find_matching_snippet(claim: str, text: str) -> Optional[str]:
    """Finds an exact or relevant snippet in the transcript matching words in claim."""
    if not claim or not text:
        return None
    claim_clean = re.sub(r"[^\w\s]", "", claim.lower())
    words = [w for w in claim_clean.split() if len(w) > 3]
    if not words:
        return None

    # Stopwords that shouldn't alone count as an evidence match
    common_stopwords = {
        "have", "with", "from", "been", "they", "this", "that", "also", "some",
        "were", "what", "when", "does", "done", "about", "more", "patient",
        "reports", "report", "denies", "stated", "states", "there", "their",
    }
    content_words = [w for w in words if w not in common_stopwords]

    claim_is_negative = any(neg in claim.lower() for neg in ["denies", "denied", "no ", "not ", "without", "never"])

    # Find the sentence in text that shares the most significant keywords
    best_sent = None
    max_score = 0
    text_sentences = re.split(r"(?<=[.!?\n])\s+", text)
    for sent in text_sentences:
        sent_clean = sent.strip()
        if not sent_clean:
            continue
        sent_lower = sent_clean.lower()
        matches = sum(1 for w in words if w in sent_lower)
        content_matches = sum(1 for w in content_words if w in sent_lower)

        # Allow matches >= 2, or for concise claims (<= 2 content words), require at least 1 content word match (e.g. 'vomiting')
        is_candidate = (matches >= 2) or (len(content_words) <= 2 and content_matches >= 1)
        if not is_candidate:
            continue

        score = matches * 2 + content_matches * 3
        # If claim is negative and transcript sentence contains negative keywords, reward alignment
        if claim_is_negative and any(neg in sent_lower for neg in ["not", "no", "never", "dont", "don't", "denies", "without", "nil", "do not"]):
            score += 4

        if score > max_score:
            max_score = score
            best_sent = sent_clean

    return best_sent


def verify_soap_claims(
    transcript: str,
    clinical_data: ClinicalExtraction,
    soap_draft: SoapDraft,
) -> VerificationResults:
    """
    Verification Agent (Agent 3):
    Verifies discrete factual claims in the AI-generated SOAP draft against
    the consultation transcript (source evidence) and structured clinical extraction.
    Strictly verifies evidence boundaries and flags unsupported claims.
    """
    claims: List[VerificationClaim] = []
    claim_idx = 1
    t_clean = (transcript or "").strip()
    t_lower = t_clean.lower()

    # 1. VERIFY SUBJECTIVE CLAIMS
    sub_text = (soap_draft.subjective or "").strip()
    sub_sentences = split_into_sentences(sub_text)

    # Collect known entities from extraction for evidence grounding
    symptom_names = [s.name.lower() for s in clinical_data.symptoms]
    med_names = [m.name.lower() for m in clinical_data.medications]
    allergy_names = [a.substance.lower() for a in clinical_data.allergies]
    neg_findings = [nf.lower() for nf in clinical_data.negative_findings]
    history_items = [h.lower() for h in clinical_data.medical_history]

    for sent in sub_sentences:
        if not sent:
            continue
        sent_lower = sent.lower()

        # Check evidence in transcript and structured clinical facts
        matched_snippet = find_matching_snippet(sent, t_clean)

        # Check if any symptoms, meds, allergies, or negatives match
        has_symptom_match = any(sym in sent_lower for sym in symptom_names)
        has_med_match = any(med in sent_lower for med in med_names)
        has_allergy_match = any(alg in sent_lower for alg in allergy_names)
        has_neg_match = any(nf in sent_lower for nf in neg_findings)
        has_history_match = any(h in sent_lower for h in history_items)

        is_supported = False
        evidence_str = ""
        explanation_str = ""
        source_type = "consultation-transcript"

        if matched_snippet:
            is_supported = True
            evidence_str = f'"{matched_snippet}"'
            explanation_str = "Explicitly documented in consultation transcript."
        elif has_symptom_match or has_med_match or has_allergy_match or has_neg_match or has_history_match:
            is_supported = True
            matched_items = []
            if has_symptom_match:
                matched_items.extend([s.name for s in clinical_data.symptoms if s.name.lower() in sent_lower])
            if has_med_match:
                matched_items.extend([m.name for m in clinical_data.medications if m.name.lower() in sent_lower])
            if has_allergy_match:
                matched_items.extend([a.substance for a in clinical_data.allergies if a.substance.lower() in sent_lower])
            if has_neg_match:
                matched_items.extend([nf for nf in clinical_data.negative_findings if nf.lower() in sent_lower])
            if has_history_match:
                matched_items.extend([h for h in clinical_data.medical_history if h.lower() in sent_lower])

            # Prefer raw transcript sentence if any matched entity is explicitly mentioned in transcript
            direct_transcript_sent = None
            if matched_items:
                for sent_t in re.split(r"(?<=[.!?\n])\s+", t_clean):
                    sent_t_clean = sent_t.strip()
                    if not sent_t_clean:
                        continue
                    sent_t_lower = sent_t_clean.lower()
                    if any(item.lower() in sent_t_lower for item in matched_items):
                        direct_transcript_sent = sent_t_clean
                        break

            if direct_transcript_sent:
                source_type = "consultation-transcript"
                evidence_str = f'"{direct_transcript_sent}"'
                explanation_str = "Explicitly documented in consultation transcript."
            else:
                source_type = "clinical-extraction"
                evidence_str = f"Corresponds to structured extracted facts: {', '.join(matched_items)}"
                explanation_str = "Grounding confirmed via extracted clinical entities."
        else:
            # Check if any significant word appears in transcript
            words_in_transcript = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", sent_lower) if w in t_lower]
            if len(words_in_transcript) >= 3:
                is_supported = True
                evidence_str = f"Supported by transcript context (matched terms: {', '.join(words_in_transcript[:4])})"
                explanation_str = "Contextually supported by transcript discussion."
            else:
                is_supported = False
                source_type = "none"
                evidence_str = "No direct transcript or structured extraction evidence found."
                explanation_str = "Claim contains statements not explicitly found in transcript."

        claims.append(
            VerificationClaim(
                id=f"verif-sub-{claim_idx}",
                section="subjective",
                claim=sent,
                status="supported" if is_supported else "unsupported",
                source=source_type,
                evidence=evidence_str,
                explanation=explanation_str,
            )
        )
        claim_idx += 1

    # 2. VERIFY OBJECTIVE CLAIMS
    obj_text = (soap_draft.objective or "").strip()
    if (
        not obj_text
        or "not documented" in obj_text.lower()
        or obj_text.lower() in {"none", "n/a", "not documented."}
    ):
        # Absence verification: verify that no vitals or exam findings exist
        has_vitals_in_transcript = any(
            v in t_lower
            for v in ["blood pressure", "bp", "pulse", "heart rate", "temperature", "temp", "spo2", "saturation", "exam:", "examination:"]
        )
        has_extracted_obs = len(clinical_data.observations) > 0

        if not has_vitals_in_transcript and not has_extracted_obs:
            claims.append(
                VerificationClaim(
                    id=f"verif-obj-{claim_idx}",
                    section="objective",
                    claim="Objective findings: Not documented.",
                    status="supported",
                    source="not-documented",
                    evidence="Absence confirmed: No vital signs, physical exam findings, or lab values documented in consultation transcript.",
                    explanation="Conservative clinical documentation: absence of objective measurements correctly preserved.",
                )
            )
        else:
            claims.append(
                VerificationClaim(
                    id=f"verif-obj-{claim_idx}",
                    section="objective",
                    claim="Objective findings: Not documented.",
                    status="ambiguous",
                    source="consultation-transcript",
                    evidence=f"Transcript mentions possible observations ({clinical_data.observations}), but objective section recorded 'Not documented.'",
                    explanation="Potential omission: check whether examination findings should be added.",
                )
            )
        claim_idx += 1
    else:
        obj_sentences = split_into_sentences(obj_text)
        for sent in obj_sentences:
            if not sent:
                continue
            matched_snippet = find_matching_snippet(sent, t_clean)
            has_obs_match = any(o.lower() in sent.lower() for o in clinical_data.observations)

            if matched_snippet or has_obs_match:
                ev = f'"{matched_snippet}"' if matched_snippet else f"Extracted observation: {sent}"
                claims.append(
                    VerificationClaim(
                        id=f"verif-obj-{claim_idx}",
                        section="objective",
                        claim=sent,
                        status="supported",
                        source="consultation-transcript",
                        evidence=ev,
                        explanation="Explicitly supported by examination or measurement in transcript.",
                    )
                )
            else:
                claims.append(
                    VerificationClaim(
                        id=f"verif-obj-{claim_idx}",
                        section="objective",
                        claim=sent,
                        status="unsupported",
                        source="none",
                        evidence="No vital signs or physical examination findings documented in consultation transcript.",
                        explanation="CRITICAL FIDELITY ALERT: Objective findings must never be invented or assumed without documentation.",
                    )
                )
            claim_idx += 1

    # 3. VERIFY ASSESSMENT CLAIMS
    ass_text = (soap_draft.assessment or "").strip()
    if (
        not ass_text
        or "not explicitly documented" in ass_text.lower()
        or ass_text.lower() in {"none", "n/a", "not documented."}
    ):
        has_doc_diagnosis = len(clinical_data.diagnoses) > 0 or any(
            d in t_lower
            for d in ["i diagnose", "diagnosis is", "impression is", "assessment is", "looks like acute", "diagnosed with"]
        )
        if not has_doc_diagnosis:
            claims.append(
                VerificationClaim(
                    id=f"verif-ass-{claim_idx}",
                    section="assessment",
                    claim="Assessment: Not explicitly documented.",
                    status="supported",
                    source="not-documented",
                    evidence="Absence confirmed: No clinical diagnosis or impression explicitly stated by clinician in consultation transcript.",
                    explanation="Conservative clinical documentation: absence of clinician diagnosis correctly preserved without AI speculation.",
                )
            )
        else:
            claims.append(
                VerificationClaim(
                    id=f"verif-ass-{claim_idx}",
                    section="assessment",
                    claim="Assessment: Not explicitly documented.",
                    status="ambiguous",
                    source="consultation-transcript",
                    evidence=f"Transcript or extraction contains clinical impression ({clinical_data.diagnoses}), but Assessment section recorded 'Not explicitly documented.'",
                    explanation="Doctor should review whether to add explicit diagnosis to Assessment.",
                )
            )
        claim_idx += 1
    else:
        ass_sentences = split_into_sentences(ass_text)
        for sent in ass_sentences:
            if not sent:
                continue
            matched_snippet = find_matching_snippet(sent, t_clean)
            has_diag_match = any(d.lower() in sent.lower() for d in clinical_data.diagnoses)

            # Check if diagnosis was explicitly stated by clinician vs speculative
            if has_diag_match or (matched_snippet and any(kw in matched_snippet.lower() for kw in ["diagnos", "impression", "think you have", "assessment", "have acute", "suffering from"])):
                claims.append(
                    VerificationClaim(
                        id=f"verif-ass-{claim_idx}",
                        section="assessment",
                        claim=sent,
                        status="supported",
                        source="consultation-transcript",
                        evidence=f'"{matched_snippet}"' if matched_snippet else f"Extracted diagnosis: {sent}",
                        explanation="Clinician diagnosis explicitly stated in consultation.",
                    )
                )
            else:
                claims.append(
                    VerificationClaim(
                        id=f"verif-ass-{claim_idx}",
                        section="assessment",
                        claim=sent,
                        status="unsupported",
                        source="none",
                        evidence="No explicit clinician diagnosis or impression found in consultation transcript.",
                        explanation="DIAGNOSTIC SAFETY ALERT: AI must not infer or deduce a diagnosis from symptoms without explicit clinician authoring.",
                    )
                )
            claim_idx += 1

    # 4. VERIFY PLAN CLAIMS
    plan_text = (soap_draft.plan or "").strip()
    if (
        not plan_text
        or "not documented" in plan_text.lower()
        or plan_text.lower() in {"none", "n/a", "not documented."}
    ):
        has_plan_in_transcript = len(clinical_data.plan) > 0 or any(
            p in t_lower
            for p in ["prescribe", "take this", "i want you to take", "follow-up in", "order a", "blood test", "refer you"]
        )
        if not has_plan_in_transcript:
            claims.append(
                VerificationClaim(
                    id=f"verif-plan-{claim_idx}",
                    section="plan",
                    claim="Plan: Not documented.",
                    status="supported",
                    source="not-documented",
                    evidence="Absence confirmed: No clinician plan, prescription, or investigations stated in consultation transcript.",
                    explanation="Conservative documentation: absence of plan items correctly preserved.",
                )
            )
        else:
            claims.append(
                VerificationClaim(
                    id=f"verif-plan-{claim_idx}",
                    section="plan",
                    claim="Plan: Not documented.",
                    status="ambiguous",
                    source="consultation-transcript",
                    evidence=f"Transcript or extraction mentions clinical plan ({clinical_data.plan}), but Plan section recorded 'Not documented.'",
                    explanation="Doctor should review whether to add plan items.",
                )
            )
        claim_idx += 1
    else:
        plan_sentences = split_into_sentences(plan_text)
        for sent in plan_sentences:
            if not sent:
                continue
            matched_snippet = find_matching_snippet(sent, t_clean)
            has_plan_match = any(p.lower() in sent.lower() for p in clinical_data.plan)

            if matched_snippet or has_plan_match:
                claims.append(
                    VerificationClaim(
                        id=f"verif-plan-{claim_idx}",
                        section="plan",
                        claim=sent,
                        status="supported",
                        source="consultation-transcript",
                        evidence=f'"{matched_snippet}"' if matched_snippet else f"Extracted plan: {sent}",
                        explanation="Clinician plan or instruction explicitly documented in consultation.",
                    )
                )
            else:
                claims.append(
                    VerificationClaim(
                        id=f"verif-plan-{claim_idx}",
                        section="plan",
                        claim=sent,
                        status="unsupported",
                        source="none",
                        evidence="No explicit clinician prescription, investigation, or instruction found in transcript.",
                        explanation="PRESCRIPTION / PLAN SAFETY ALERT: AI must not invent medications, tests, or treatment instructions without clinician authoring.",
                    )
                )
            claim_idx += 1

    # Summarize verification counts
    supported_cnt = sum(1 for c in claims if c.status == "supported")
    unsupported_cnt = sum(1 for c in claims if c.status == "unsupported")
    ambiguous_cnt = sum(1 for c in claims if c.status == "ambiguous")
    conflicting_cnt = sum(1 for c in claims if c.status == "conflicting")

    return VerificationResults(
        claims=claims,
        total_claims=len(claims),
        supported_count=supported_cnt,
        unsupported_count=unsupported_cnt,
        ambiguous_count=ambiguous_cnt,
        conflicting_count=conflicting_cnt,
        provenance="ai-verified",
        verified_at=utc_now(),
    )

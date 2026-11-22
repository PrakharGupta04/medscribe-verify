"""
Module 3: Longitudinal Patient Records — Backend Service.

Provides structured longitudinal record assembly and PDF generation for a patient
across all their consultations. Uses reportlab for PDF rendering.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.models import Consultation, IntakeData, Patient


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fmt_dt(val: Any) -> str:
    """Return a human-readable date string from an ISO string, datetime, or None."""
    if val is None:
        return "Not documented"
    if isinstance(val, datetime):
        return val.strftime("%d %b %Y")
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(val)


def _fmt_datetime(val: Any) -> str:
    """Return date + time string."""
    if val is None:
        return "Not documented"
    if isinstance(val, datetime):
        return val.strftime("%d %b %Y, %H:%M UTC")
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return str(val)


def _load_json(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _load_json_list(text: Optional[str]) -> List[Any]:
    """Load a JSON list safely; return empty list on any failure."""
    result = _load_json(text)
    if isinstance(result, list):
        return result
    return []


def _esc(text: Any) -> str:
    """HTML-escape a value for safe insertion into ReportLab Paragraph markup.

    ReportLab Paragraphs parse a small subset of HTML tags. Any ``<``, ``>``,
    ``&``, or ``"`` in dynamic data must be escaped before embedding.
    None and non-string values are converted to strings first.
    """
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def _is_clinical_allergy(substance: str) -> bool:
    """Mirror of frontend isClinicalAllergy — exclude NKDA and non-allergy strings."""
    if not substance or not substance.strip():
        return False
    lower = substance.strip().lower()
    negative_markers = {
        "nkda",
        "no known drug allergies",
        "no known allergies",
        "no allergies",
        "none reported",
        "none",
        "none known",
        "denies allergies",
        "no allergy",
        "no known drug allergy",
        "not documented",
        "not applicable",
        "n/a",
        "na",
    }
    if lower in negative_markers:
        return False
    for m in negative_markers:
        if lower.startswith(m):
            return False
    return True


# ---------------------------------------------------------------------------
# longitudinal record assembly
# ---------------------------------------------------------------------------

def get_patient_longitudinal_record(db: Session, patient_id: str) -> Dict[str, Any]:
    """
    Assemble a structured longitudinal record for a patient.
    Returns a dict suitable for JSON serialisation or PDF rendering.
    Raises HTTP 404 if the patient does not exist.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found.",
        )

    # All consultations in chronological order
    consultations = (
        db.query(Consultation)
        .filter(Consultation.patient_id == patient_id)
        .order_by(Consultation.created_at)
        .all()
    )

    # Latest intake data for demographics
    intake: Optional[IntakeData] = (
        db.query(IntakeData)
        .filter(IntakeData.patient_id == patient_id)
        .order_by(IntakeData.submitted_at.desc())
        .first()
    )

    visit_records = []
    for idx, c in enumerate(consultations):
        visit_num = idx + 1

        # Chief complaint from intake attached to this session
        chief_complaint = "General Consultation"
        if c.session and c.session.intake_data:
            chief_complaint = c.session.intake_data.chief_complaint or chief_complaint

        extracted = _load_json(c.extracted_clinical_data)
        soap_draft_data = _load_json(c.soap_draft)
        final = _load_json(c.final_record)
        verification = _load_json(c.verification_results)
        comparison = _load_json(c.comparison_results)

        # Determine what SOAP to surface and with what provenance label.
        # Rule: only use final_record.soap as doctor-approved; never silently
        # fall back from a missing final SOAP to the AI draft without saying so.
        is_finalized = bool(final or c.finalized_at)
        final_soap_data = (final or {}).get("soap") if final else None

        if final_soap_data:
            soap_entry = {
                "subjective": final_soap_data.get("subjective") or "Not documented",
                "objective": final_soap_data.get("objective") or "Not documented",
                "assessment": final_soap_data.get("assessment") or "Not documented",
                "plan": final_soap_data.get("plan") or "Not documented",
                "provenance": "doctor-approved",
            }
        elif is_finalized and soap_draft_data:
            # Visit is finalized but no SOAP was saved inside final_record — the
            # draft exists but was not explicitly doctor-approved as final SOAP.
            soap_entry = {
                "subjective": soap_draft_data.get("subjective") or "Not documented",
                "objective": soap_draft_data.get("objective") or "Not documented",
                "assessment": soap_draft_data.get("assessment") or "Not documented",
                "plan": soap_draft_data.get("plan") or "Not documented",
                "provenance": "ai-generated-draft-unverified",
            }
        elif soap_draft_data:
            soap_entry = {
                "subjective": soap_draft_data.get("subjective") or "Not documented",
                "objective": soap_draft_data.get("objective") or "Not documented",
                "assessment": soap_draft_data.get("assessment") or "Not documented",
                "plan": soap_draft_data.get("plan") or "Not documented",
                "provenance": "ai-generated-draft-unverified",
            }
        else:
            soap_entry = None

        # Allergies: AI-extracted only. Finalization of the visit does not imply
        # that individual extracted allergens were doctor-reviewed or confirmed.
        # Always label as ai-extracted-unverified.
        allergies = []
        for a in (extracted or {}).get("allergies", []):
            substance = a.get("substance", "")
            if not _is_clinical_allergy(substance):
                continue
            allergies.append({
                "substance": substance,
                "reaction": a.get("reaction") or "Not documented",
                "provenance": "ai-extracted-unverified",
            })

        # Medications: use explicit status from extraction; never default to "Active".
        medications = []
        for m in (extracted or {}).get("medications", []):
            medications.append({
                "name": m.get("name", ""),
                "dose": m.get("dose"),
                "frequency": m.get("frequency"),
                "status": m.get("status") or "Not documented",
            })

        visit_records.append({
            "visit_number": visit_num,
            "consultation_id": c.id,
            "date": _fmt_dt(c.created_at),
            "status": c.status,
            "is_finalized": is_finalized,
            "finalized_at": _fmt_datetime(c.finalized_at) if c.finalized_at else None,
            "chief_complaint": chief_complaint,
            "doctor_name": (
                (final or {}).get("doctor_name")
                or (final or {}).get("approved_by")
                or "Not documented"
            ),
            "soap": soap_entry,
            "doctor_notes": (final or {}).get("doctor_notes"),
            "allergies": allergies,
            "medications": medications,
            "diagnoses": (extracted or {}).get("diagnoses", []) if extracted else [],
            "symptoms": [
                s.get("name", "") for s in (extracted or {}).get("symptoms", [])
            ] if extracted else [],
            "verification_summary": {
                "total_claims": (verification or {}).get("total_claims", 0),
                "supported": (verification or {}).get("supported_count", 0),
                "unsupported": (verification or {}).get("unsupported_count", 0),
                "ambiguous": (verification or {}).get("ambiguous_count", 0),
            } if verification else None,
            "comparison_summary": {
                "total_items": (comparison or {}).get("total_items", 0),
                "discrepancies": (comparison or {}).get("discrepancy_count", 0),
                "confirmed": (comparison or {}).get("confirmed_count", 0),
            } if comparison else None,
        })

    # Safely parse intake conditions; fall back to [] on malformed JSON.
    intake_conditions: List[str] = []
    if intake and intake.conditions:
        parsed = _load_json(intake.conditions)
        if isinstance(parsed, list):
            intake_conditions = [str(c) for c in parsed]
        # Silently discard malformed JSON — do not crash.

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "patient": {
            "id": patient.id,
            "mrn": patient.mrn,
            "name": patient.name,
            "dob": patient.dob or "Not documented",
            "phone": patient.phone or "Not documented",
            "gender": patient.gender or "Not specified",
        },
        "intake_summary": {
            "chief_complaint": intake.chief_complaint if intake else "Not documented",
            "medications": (intake.medications or "Not documented") if intake else "Not documented",
            "allergies": (intake.allergies or "Not documented") if intake else "Not documented",
            "conditions": intake_conditions,
            "submitted_at": _fmt_datetime(intake.submitted_at) if intake else "Not documented",
        },
        "total_visits": len(consultations),
        "visits": visit_records,
    }


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_patient_pdf(db: Session, patient_id: str) -> bytes:
    """
    Generate a longitudinal patient record PDF and return it as bytes.
    Uses reportlab. Raises HTTP 404 if patient not found, HTTP 400 if no records.

    All dynamic text is HTML-escaped before insertion into Paragraph markup to
    prevent special characters from breaking the ReportLab XML parser.
    """
    record = get_patient_longitudinal_record(db, patient_id)

    if record["total_visits"] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No consultation records available for this patient.",
        )

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation library (reportlab) is not available on this server.",
        )

    buffer = BytesIO()
    # Compact margins leave room for content while the canvas-drawn footer sits
    # at 0.65 cm from the bottom edge, below the 1 cm bottom margin.
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1 * cm,
        title=f"Medscribe Patient Medical Record {record['patient']['mrn']}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MedTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=6,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "MedSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=4,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=6,
        spaceAfter=2,
        leading=14,
        fontName="Helvetica-Bold",
    )
    visit_heading_style = ParagraphStyle(
        "VisitHeading",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=4,
        spaceAfter=2,
        leading=13,
        fontName="Helvetica-Bold",
        backColor=colors.HexColor("#eff6ff"),
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#64748b"),
        fontName="Helvetica-Bold",
        spaceAfter=1,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=2,
        leading=12,
    )
    draft_label_style = ParagraphStyle(
        "DraftLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#b45309"),
        fontName="Helvetica-Bold",
        spaceAfter=1,
    )
    notice_style = ParagraphStyle(
        "Notice",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#92400e"),
        backColor=colors.HexColor("#fffbeb"),
        spaceAfter=4,
        spaceBefore=4,
        leading=12,
    )

    story = []
    patient = record["patient"]
    intake = record["intake_summary"]

    # Footer text drawn on the canvas of every page so it never pushes content
    # onto a new blank page by itself.
    _footer_text = (
        f"Generated by Medscribe \u2022 {record['generated_at']} \u2022 "
        f"Patient: {patient['name']} (MRN: {patient['mrn']})"
    )

    def _draw_page_footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColorRGB(0.58, 0.64, 0.73)  # #94a3b8
        canvas.drawCentredString(A4[0] / 2, 0.65 * cm, _footer_text)
        canvas.restoreState()

    # ----- Header -----
    story.append(Paragraph("Medscribe — Patient Medical Record", title_style))
    story.append(Paragraph(
        f"Generated: {_esc(record['generated_at'])} &nbsp;|&nbsp; "
        f"MRN: <b>{_esc(patient['mrn'])}</b> &nbsp;|&nbsp; "
        f"Total Visits: {_esc(record['total_visits'])}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=6))

    # ----- Patient Demographics -----
    story.append(Paragraph("Patient Demographics", section_heading_style))
    demo_data = [
        ["Name", _esc(patient["name"]), "MRN", _esc(patient["mrn"])],
        ["Date of Birth", _esc(patient["dob"]), "Gender", _esc(patient["gender"])],
        ["Phone", _esc(patient["phone"]), "", ""],
    ]
    demo_table = Table(demo_data, colWidths=[3 * cm, 7 * cm, 3 * cm, 4 * cm])
    demo_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#475569")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 3))

    # ----- Intake Summary -----
    story.append(Paragraph("Patient-Reported Intake Summary", section_heading_style))
    story.append(Paragraph(
        f"<b>Chief Complaint:</b> {_esc(intake['chief_complaint'])}",
        body_style,
    ))
    story.append(Paragraph(
        f"<b>Allergies (Patient-Reported):</b> {_esc(intake['allergies'])}",
        body_style,
    ))
    story.append(Paragraph(
        f"<b>Medications (Patient-Reported):</b> {_esc(intake['medications'])}",
        body_style,
    ))
    if intake.get("conditions"):
        conditions_str = ", ".join(_esc(c) for c in intake["conditions"])
        story.append(Paragraph(f"<b>Conditions:</b> {conditions_str}", body_style))
    story.append(Paragraph(
        f"<b>Submitted:</b> {_esc(intake['submitted_at'])}",
        body_style,
    ))
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=4))

    # ----- Visit Records -----
    story.append(Paragraph("Consultation Visit History", section_heading_style))

    for visit in record["visits"]:
        vn = visit["visit_number"]
        status_label = "Finalized" if visit["is_finalized"] else "In Progress"
        finalized_note = (
            f" — Finalized: {_esc(visit['finalized_at'])}" if visit["finalized_at"] else ""
        )
        story.append(Paragraph(
            f"Visit #{_esc(vn)} — {_esc(visit['date'])} — "
            f"{_esc(visit['chief_complaint'])} [{_esc(status_label)}{finalized_note}]",
            visit_heading_style,
        ))

        story.append(Paragraph(
            f"<b>Doctor:</b> {_esc(visit['doctor_name'])}",
            body_style,
        ))

        # SOAP — label content by its actual provenance; never silently substitute.
        soap = visit.get("soap")
        if soap:
            soap_provenance = soap.get("provenance", "")
            is_doctor_approved_soap = soap_provenance == "doctor-approved"
            if is_doctor_approved_soap:
                story.append(Paragraph("SOAP Note (Doctor-Approved Final)", label_style))
            else:
                story.append(Paragraph(
                    "SOAP Note (AI-Generated Draft — Not Doctor-Approved)",
                    draft_label_style,
                ))
            soap_data = [
                ["Subjective", _esc(soap["subjective"])],
                ["Objective", _esc(soap["objective"])],
                ["Assessment", _esc(soap["assessment"])],
                ["Plan", _esc(soap["plan"])],
            ]
            soap_table = Table(soap_data, colWidths=[3 * cm, 15.3 * cm])
            soap_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(soap_table)
        else:
            story.append(Paragraph(
                "SOAP note not generated for this visit.",
                body_style,
            ))
        story.append(Spacer(1, 4))

        # Allergies — explicitly label as AI-extracted; never claim doctor-reviewed
        # unless the final record confirms the visit was doctor-reviewed.
        if visit["allergies"]:
            story.append(Paragraph(
                "Documented Allergies (AI-Extracted, Unverified)",
                label_style,
            ))
            for a in visit["allergies"]:
                reaction_text = _esc(a["reaction"]) if a["reaction"] != "Not documented" else "reaction not documented"
                story.append(Paragraph(
                    f"\u2022 <b>{_esc(a['substance'])}</b> — {reaction_text}"
                    f" <i>[AI-extracted, unverified]</i>",
                    body_style,
                ))
        else:
            story.append(Paragraph(
                "Allergies: No clinical allergies extracted for this visit.",
                body_style,
            ))

        # Medications — show explicit status only; "Not documented" when unavailable.
        if visit["medications"]:
            story.append(Paragraph("Medications (AI-Extracted, Consultation)", label_style))
            for m in visit["medications"]:
                parts = [_esc(m["name"])]
                if m.get("dose"):
                    parts.append(_esc(m["dose"]))
                if m.get("frequency"):
                    parts.append(_esc(m["frequency"]))
                med_status = _esc(m.get("status") or "Not documented")
                story.append(Paragraph(
                    f"\u2022 {' '.join(parts)} [status: {med_status}]",
                    body_style,
                ))

        # Diagnoses
        if visit["diagnoses"]:
            story.append(Paragraph("Diagnoses / Assessment", label_style))
            for d in visit["diagnoses"]:
                story.append(Paragraph(f"\u2022 {_esc(d)}", body_style))

        # Verification summary
        if visit["verification_summary"]:
            vs = visit["verification_summary"]
            story.append(Paragraph(
                f"<b>Verification:</b> {_esc(vs['total_claims'])} claims — "
                f"{_esc(vs['supported'])} supported, "
                f"{_esc(vs['unsupported'])} unsupported, "
                f"{_esc(vs['ambiguous'])} ambiguous",
                body_style,
            ))

        # Comparison summary
        if visit["comparison_summary"]:
            cs = visit["comparison_summary"]
            story.append(Paragraph(
                f"<b>Comparison (Intake vs Consultation):</b> "
                f"{_esc(cs['total_items'])} items — "
                f"{_esc(cs['confirmed'])} confirmed, "
                f"{_esc(cs['discrepancies'])} discrepancies",
                body_style,
            ))

        # Doctor notes
        if visit.get("doctor_notes"):
            story.append(Paragraph(
                f"<b>Doctor Notes:</b> {_esc(visit['doctor_notes'])}",
                body_style,
            ))

        story.append(Spacer(1, 2))
        story.append(HRFlowable(
            width="100%", thickness=0.3, color=colors.HexColor("#e2e8f0"), spaceAfter=2
        ))

    # ----- Disclaimer — kept as story content; footer line is on the page canvas -----
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "DISCLAIMER — FOR CLINICAL USE ONLY: This document contains AI-assisted information "
        "extracted from consultation recordings and intake data. AI-generated content is marked "
        "with provenance labels (ai-extracted, ai-generated) and is NOT doctor-approved unless "
        "explicitly stated. All clinical decisions must be made exclusively by licensed healthcare "
        "professionals. This record is confidential and may contain protected health information.",
        notice_style,
    ))

    doc.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
    return buffer.getvalue()

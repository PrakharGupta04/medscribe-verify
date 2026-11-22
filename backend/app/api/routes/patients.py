"""
Module 3: Patient-level routes — Longitudinal Record and PDF export.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services import record_service

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/{patient_id}/record/pdf")
def download_patient_record_pdf(
    patient_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate and return a longitudinal patient medical record as a PDF file.

    - Returns HTTP 404 if the patient_id does not match any patient.
    - Returns HTTP 400 if the patient has no consultation records.
    - Returns HTTP 500 if the PDF library is unavailable.
    """
    patient_record = record_service.get_patient_longitudinal_record(db, patient_id)
    mrn = patient_record["patient"]["mrn"]

    pdf_bytes = record_service.generate_patient_pdf(db, patient_id)

    safe_mrn = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in mrn)
    filename = f"medscribe-{safe_mrn}-record.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )

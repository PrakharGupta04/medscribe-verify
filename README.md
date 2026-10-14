# Medscribe — Clinical Documentation & Ambient Scribe Verification System

> **A clinically-grounded ambient documentation platform designed to reduce clinician administrative burden without compromising clinical safety, patient privacy, or physician oversight.**

---

## 🩺 Overview

Medscribe is an intelligent clinical documentation system built for outpatient and clinic environments. It bridges patient intake, consultation dialogue recording/transcription, AI-assisted SOAP drafting, real-time claim-level verification against primary transcript sources, and cross-visit longitudinal reconciliation.

### Core Philosophy: Doctor Authority & Clinical Safety
Unlike naive LLM scribing tools that silently invent or assume negative clinical findings, Medscribe adheres strictly to verified clinical invariants:
1. **Conservative Sentinel Values**: If an item is unmentioned in the consultation, it is explicitly flagged with `"Not documented."` or `"Not explicitly documented."` rather than hallucinating normal findings.
2. **Four-Tier Provenance Tracking**: Every data point carries explicit provenance:
   `patient-reported` ➔ `ai-extracted` ➔ `ai-generated-draft-unverified` ➔ `doctor-approved-final`
3. **Primary Source Claim Verification**: Every statement generated in the SOAP note is cross-referenced directly against the raw consultation transcript to identify supported vs. unsupported claims.
4. **Physician Approval Gate**: AI outputs remain unverified drafts until explicitly reviewed, modified, and signed off by the attending physician. Finalized records are immutable.
5. **Visit Isolation**: Patient encounter boundaries are strictly enforced to prevent cross-patient data leakage.

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────┐
                                  │ Multilingual Patient   │
                                  │ Intake (EN / HI)       │
                                  └───────────┬────────────┘
                                              │
                                              ▼
┌────────────────────────┐       ┌────────────────────────┐
│ Ambient Consultation   │       │ Module 1: Intake &     │
│ Audio / Transcript     │       │ Symptom Normalization  │
└───────────┬────────────┘       └───────────┬────────────┘
            │                                 │
            ▼                                 │
┌────────────────────────┐                    │
│ Module 2: Consultation │                    │
│ Intelligence & SOAP    │                    │
└───────────┬────────────┘                    │
            │                                 │
            ├───────────────┬─────────────────┘
            ▼               ▼
┌────────────────────────┐ ┌────────────────────────┐
│ Verification Engine    │ │ Visit Comparison &     │
│ (Source Grounding)     │ │ Reconciliation         │
└───────────┬────────────┘ └───────────┬────────────┘
            │                          │
            └───────────────┬──────────┘
                            ▼
            ┌────────────────────────┐
            │ Doctor Review &        │
            │ Approval Gate          │
            └───────────┬────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │ Module 3: Longitudinal │
            │ Patient Record         │
            └────────────────────────┘
```

### Modules
- **Module 1: Multilingual Intake & Symptom Normalization**
  - Self-service intake supporting English and Hindi (including colloquial Hinglish).
  - Symptom extraction, urgency scoring, and medical normalization using Groq LLM API with fallback handling.
- **Module 2: Consultation Intelligence, SOAP Generation & Claim Verification**
  - Ingestion of raw doctor-patient encounter transcripts.
  - Extraction of symptoms, medications, allergies, vitals, and diagnoses.
  - Generation of structured SOAP notes adhering to strict sentinel guardrails.
  - Independent verification step calculating evidence support and flagging unsupported claims.
- **Module 3: Longitudinal Patient Record & Clinical Reconciliation**
  - Cross-visit comparison detecting newly mentioned, ongoing, and unmentioned conditions.
  - Longitudinal timeline tracking chronic conditions, allergies, and medication history across visits.

---

## 📁 Repository Structure

```
Medscribe/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI REST endpoints (intake, consultations, queue, doctor, health)
│   │   ├── core/                # App configuration, settings & environment variables
│   │   ├── db/                  # SQLAlchemy base models, session management & SQLite persistence
│   │   ├── schemas/             # Pydantic v2 validation models
│   │   └── services/            # Core business logic:
│   │       ├── intake_service.py         # Patient intake & symptom parsing
│   │       ├── normalization_service.py  # LLM translation & normalization
│   │       ├── consultation_service.py   # Consultation lifecycle management
│   │       ├── extraction_service.py     # Clinical entity extraction
│   │       ├── soap_service.py           # Guarded SOAP note generation
│   │       ├── verification_service.py   # Transcript-grounded claim verifier
│   │       ├── comparison_service.py     # Cross-visit diffing & reconciliation
│   │       └── summary_service.py        # Patient clinical summary builder
│   ├── requirements.txt         # Python dependencies
│   └── tests/                   # Pytest suite (41+ tests across all modules)
├── Frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── doctor/          # Doctor dashboard, patient queue, consultation overview & verification UI
│   │   │   ├── patient/         # Multilingual patient intake flow
│   │   │   └── ui/              # Reusable UI component design system
│   │   ├── services/api.ts      # Frontend API client
│   │   └── types/intake.ts      # TypeScript interfaces
│   ├── package.json             # React dependencies
│   └── vite.config.ts           # Vite bundler configuration
├── medscribe_commercial_readiness_assessment.md # Comprehensive commercial readiness roadmap
├── audit.md                     # Initial codebase audit report
└── README.md                    # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`
- **Groq API Key** (for clinical extraction, normalization, and verification)

---

### Backend Setup

1. **Navigate to the backend directory and activate your virtual environment:**
   ```bash
   cd backend
   # If using an existing venv:
   # ..\.medscribe\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the project root (or inside `backend/`):
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   DATABASE_URL=sqlite:///./medscribe.db
   ```

4. **Run the backend server:**
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```
   Interactive API documentation will be available at:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

### Frontend Setup

1. **Navigate to the Frontend directory:**
   ```bash
   cd Frontend
   ```

2. **Install packages:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   The UI will be accessible at `http://localhost:5173`.

---

## 🧪 Testing & Validation

The test suite validates clinical safety invariants, patient isolation, multilingual parsing, and end-to-end workflows:

```bash
# Run all backend tests
pytest backend/tests -v
```

Key test suites:
- `test_consultation.py` — Lifecycle of consultations, extraction, SOAP formatting, and finalization.
- `test_patient_isolation.py` — Guarantees no cross-patient data exposure.
- `test_provenance_review.py` — Validates the provenance chain and doctor-approval state machine.
- `test_multilingual_voice.py` — Evaluates Hindi/English symptom extraction.
- `test_agentic_workflow.py` — Tests end-to-end multi-step consultation intelligence.

---

## 🗺️ Commercial Roadmap

For the complete technical debt analysis, compliance gaps, and phased development plan, see:
👉 [medscribe_commercial_readiness_assessment.md](medscribe_commercial_readiness_assessment.md)

- **Phase 0:** Foundation Stabilization (Git versioning, 429 retries, age calculation, clean API surface)
- **Phase 1:** Security Foundation (JWT authentication, role-based access, audit logging, input sanitization)
- **Phase 2:** Module 3 Backend (LongitudinalFact database model, cross-visit reconciliation API)
- **Phase 3:** Reliability & Pipeline Orchestration (Single-click pipeline endpoint, circuit breaker)
- **Phase 4:** Deployment Infrastructure (Docker, PostgreSQL migration, TLS, structured logging)
- **Phase 5:** Clinical Validation (Gold-standard clinical transcripts corpus, accuracy measurement)
- **Phase 6:** Interoperability (FHIR export, ICD-10 suggestions, EHR connectivity)

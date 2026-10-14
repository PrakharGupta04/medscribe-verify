import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Tabs, Card, SectionLabel, SourceBadge, VerifBadge, AINotice, Button, AllergyTag, Expandable, VoiceButton
} from '../ui';
import {
  SAMPLE_PATIENT, INTAKE_DATA, SOAP_NOTE,
  VERIFICATION_CLAIMS, CONFLICTS
} from '../../data/sample';
import { api } from '../../services/api';
import type { DoctorIntakeSummaryResponse, PreConsultationSummary, PatientDemographics, ConsultationResponse } from '../../types/intake';

type TabId = 'summary' | 'history' | 'transcript' | 'soap' | 'verification' | 'record';

interface PatientOverviewProps {
  onBack: () => void;
  patientId?: string;
  sessionId?: string;
  onStartNewVisit?: (patient: { id: string; mrn?: string; name: string; dob?: string; phone?: string }) => void;
}

function formatVisitDate(dateStr?: string | null): string {
  if (!dateStr) return '17 Sep 2026';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

/**
 * Validates whether a text string describes a genuine clinical allergy
 * rather than a patient concern, general symptom, or non-allergy note.
 */
export function isClinicalAllergy(text?: string | null): boolean {
  if (!text) return false;
  const lower = text.trim().toLowerCase();
  if (
    lower === 'none' ||
    lower === 'none reported' ||
    lower === 'n/a' ||
    lower === 'no' ||
    lower === 'no allergies' ||
    lower === 'denies' ||
    lower === 'nil' ||
    lower === 'not documented' ||
    lower === 'not documented.' ||
    lower === 'no known allergies' ||
    lower === 'nkda'
  ) {
    return false;
  }

  const allergyTerms = [
    'allergy', 'allergic', 'allergies',
    'penicillin', 'amoxicillin', 'sulfa', 'aspirin', 'ibuprofen', 'nsaid', 'codeine', 'morphine',
    'antibiotic', 'latex', 'peanut', 'egg', 'shellfish', 'seafood', 'dairy', 'pollen', 'dust',
    'hives', 'rash', 'anaphylaxis', 'angioedema', 'swelling'
  ];
  const hasAllergyTerm = allergyTerms.some(term => lower.includes(term));

  const nonAllergyPhrases = [
    'joint pain', 'energy level', 'energy levels', 'fatigue', 'tired', 'weakness',
    'back pain', 'stomach pain', 'chest pain', 'fever', 'headache', 'cough',
    'unsure about', 'never had', 'never checked', 'no medicine'
  ];
  const hasNonAllergyPhrase = nonAllergyPhrases.some(phrase => lower.includes(phrase));

  if (hasNonAllergyPhrase && !hasAllergyTerm) {
    return false;
  }

  if (lower.length > 50 && !hasAllergyTerm) {
    return false;
  }

  return true;
}

export default function PatientOverview({ onBack, patientId, sessionId, onStartNewVisit }: PatientOverviewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('summary');
  const [approved, setApproved] = useState(false);
  const [doctorData, setDoctorData] = useState<DoctorIntakeSummaryResponse | null>(null);
  const [consultation, setConsultation] = useState<ConsultationResponse | null>(null);
  const [visits, setVisits] = useState<ConsultationResponse[]>([]);
  const [creatingVisit, setCreatingVisit] = useState(false);
  const [loading, setLoading] = useState<boolean>(Boolean(patientId || sessionId));
  const [error, setError] = useState<string | null>(null);

  const identifier = patientId || sessionId;

  const refreshVisits = useCallback(async (pId: string) => {
    try {
      const list = await api.getPatientConsultations(pId);
      setVisits(list);
      return list;
    } catch (err) {
      console.warn('Failed to load patient visits:', err);
      return [];
    }
  }, []);

  useEffect(() => {
    if (!identifier) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    api.getDoctorIntakeSummary(identifier)
      .then(res => {
        if (isMounted) {
          setDoctorData(res);
          setLoading(false);
          const targetPatientId = res.patient?.id || patientId;
          const targetSessionId = res.session_id || sessionId;
          if (targetPatientId) {
            refreshVisits(targetPatientId);
            api.startConsultation(targetPatientId, targetSessionId)
              .then(c => {
                if (isMounted) {
                  setConsultation(c);
                  setApproved(Boolean(c.final_record || c.status === 'completed'));
                  refreshVisits(targetPatientId);
                }
              })
              .catch(cErr => {
                console.warn('Consultation initialization:', cErr);
              });
          }
        }
      })
      .catch(err => {
        if (isMounted) {
          // If identifier was a patientId, they may not have an intake form yet; start/load consultation directly
          if (patientId) {
            refreshVisits(patientId);
            api.startConsultation(patientId)
              .then(c => {
                if (isMounted) {
                  setConsultation(c);
                  setApproved(Boolean(c.final_record || c.status === 'completed'));
                  refreshVisits(patientId);
                  setLoading(false);
                }
              })
              .catch(() => {
                if (isMounted) {
                  setError(err instanceof Error ? err.message : 'Failed to load patient');
                  setLoading(false);
                }
              });
          } else {
            setError(err instanceof Error ? err.message : 'Failed to load intake summary');
            setLoading(false);
          }
        }
      });

    return () => {
      isMounted = false;
    };
  }, [identifier, patientId, sessionId, refreshVisits]);

  const handleConsultationUpdated = (updated: ConsultationResponse) => {
    setConsultation(updated);
    if (updated.final_record || updated.status === 'completed') {
      setApproved(true);
    }
    setVisits(prev => prev.map(v => v.id === updated.id ? updated : v));
  };

  const handleSelectVisit = async (v: ConsultationResponse) => {
    setConsultation(v);
    setApproved(Boolean(v.final_record || v.status === 'completed'));
    if (v.session_id) {
      try {
        const summary = await api.getDoctorIntakeSummary(v.session_id);
        setDoctorData(summary);
      } catch (err) {
        console.warn('Failed to load visit intake summary:', err);
      }
    } else {
      setDoctorData(null);
    }
  };

  const handleNewVisit = async () => {
    const targetPatientId = doctorData?.patient?.id || patientId || consultation?.patient_id;
    if (!targetPatientId) return;

    if (onStartNewVisit) {
      onStartNewVisit({
        id: targetPatientId,
        mrn: patient.mrn,
        name: patient.name,
        dob: patient.dob !== '—' ? patient.dob : undefined,
        phone: patient.phone !== '—' ? patient.phone : undefined,
      });
      return;
    }

    try {
      setCreatingVisit(true);
      setError(null);
      const newConsultation = await api.startConsultation(targetPatientId, undefined, true);
      const updatedVisits = await refreshVisits(targetPatientId);
      setConsultation(newConsultation);
      setApproved(false);
      setActiveTab('transcript');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create new visit');
    } finally {
      setCreatingVisit(false);
    }
  };

  const isFinalized = Boolean(approved || consultation?.final_record || consultation?.status === 'completed');

  const handleApproveRecord = async () => {
    if (!consultation?.id || isFinalized) return;
    try {
      const finalized = await api.finalizeConsultation(consultation.id, {
        subjective: consultation.soap_draft?.subjective,
        objective: consultation.soap_draft?.objective,
        assessment: consultation.soap_draft?.assessment,
        plan: consultation.soap_draft?.plan,
        doctor_notes: 'Reviewed, verified against source evidence, and approved by attending clinician.',
        doctor_name: 'Dr. J. Patel',
      });
      handleConsultationUpdated(finalized);
      setApproved(true);
    } catch (err) {
      console.warn('Could not finalize consultation via API:', err);
      try {
        const completed = await api.completeConsultation(consultation.id);
        handleConsultationUpdated(completed);
      } catch {}
      setApproved(true);
    }
  };

  // Active patient demographics (API data if loaded, fallback only if pure demo standalone)
  const patient: PatientDemographics = doctorData?.patient || {
    id: patientId || SAMPLE_PATIENT.id,
    mrn: doctorData?.patient?.mrn || (patientId ? `MRN-2026-${patientId.slice(0, 4)}` : SAMPLE_PATIENT.id),
    name: doctorData?.patient?.name || (patientId ? 'Patient Record' : SAMPLE_PATIENT.name),
    first_name: doctorData?.patient?.first_name || (patientId ? 'Patient' : SAMPLE_PATIENT.firstName),
    age: doctorData?.patient?.age || (patientId ? '—' : String(SAMPLE_PATIENT.age)),
    dob: doctorData?.patient?.dob || (patientId ? '—' : SAMPLE_PATIENT.dob),
    phone: doctorData?.patient?.phone || (patientId ? '—' : SAMPLE_PATIENT.phone),
    gender: doctorData?.patient?.gender || (patientId ? 'Not specified' : SAMPLE_PATIENT.gender),
  };

  const previousVisits = visits.filter(v => v.id !== consultation?.id);
  const previousVisitsCount = previousVisits.length;

  const tabs = [
    { id: 'summary', label: 'Pre-Consult Summary' },
    { id: 'history', label: 'Visit History', badge: previousVisitsCount > 0 ? previousVisitsCount : undefined },
    { id: 'transcript', label: 'Transcript & Extraction' },
    { id: 'soap', label: 'SOAP Draft', badge: consultation?.soap_draft ? undefined : '!' },
    { id: 'verification', label: 'Verification & Conflicts', badge: consultation?.comparison_results?.discrepancy_count ? `⚠ ${consultation.comparison_results.discrepancy_count}` : undefined },
    { id: 'record', label: isFinalized ? '✓ Record' : 'Record' },
  ];

  const consultationAllergies = consultation?.extracted_clinical_data?.allergies?.filter(a => isClinicalAllergy(a.substance)) || [];
  const intakeAllergy = isClinicalAllergy(doctorData?.summary?.allergies) ? doctorData?.summary?.allergies : null;

  const hasAllergy = consultationAllergies.length > 0 || Boolean(intakeAllergy);

  const allergyDisplay = consultationAllergies.length > 0
    ? consultationAllergies.map(a => a.substance).join(', ')
    : (intakeAllergy || 'Allergy Documented');

  const patientIntakeNote = (doctorData?.summary?.allergies && !isClinicalAllergy(doctorData.summary.allergies) && doctorData.summary.allergies.toLowerCase() !== 'none' && doctorData.summary.allergies.toLowerCase() !== 'none reported')
    ? doctorData.summary.allergies
    : null;

  const visitDateLabel = consultation?.created_at
    ? formatVisitDate(consultation.created_at)
    : doctorData?.summary?.submitted_at || '17 Sep 2026';

  const visitNumber = useMemo(() => {
    if (!consultation || visits.length === 0) return 1;
    const sorted = [...visits].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const idx = sorted.findIndex(v => v.id === consultation.id);
    return idx >= 0 ? idx + 1 : visits.length;
  }, [consultation, visits]);

  return (
    <div className="flex flex-col h-full">
      {/* Patient header */}
      <div className="bg-white border-b border-slate-100 px-6 py-4">
        <div className="flex items-center gap-2 text-sm text-slate-400 mb-3">
          <button onClick={onBack} className="hover:text-blue-600 transition-colors">Queue</button>
          <span>›</span>
          <span className="text-slate-700 font-medium">
            {patient.name} — Visit #{visitNumber} ({visitDateLabel})
          </span>
          {doctorData && (
            <span className="ml-2 text-xs bg-sky-50 text-sky-700 px-2 py-0.5 rounded border border-sky-200 font-mono">
              Live Intake Data
            </span>
          )}
          {consultation && (
            <span className="ml-2 text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-200 font-mono">
              Consultation: {consultation.status}
            </span>
          )}
        </div>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold">
              {patient.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-bold text-slate-900 text-lg" style={{ fontFamily: 'DM Sans, sans-serif' }}>{patient.name}</h2>
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${consultation?.status === 'in-progress'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-slate-50 text-slate-600 border-slate-200'
                  }`}>
                  {consultation?.status === 'in-progress' ? 'Active Visit' : 'Completed Visit'}
                </span>
                <span className="text-xs text-slate-400 font-mono-label ml-1">
                  Visit #{visitNumber} of {Math.max(1, visits.length)}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-sm text-slate-500">Age {patient.age} · {patient.gender} · DOB {patient.dob}</span>
                <span className="text-slate-300">|</span>
                <span className="text-xs text-slate-400 font-mono-label">{patient.mrn}</span>
                {hasAllergy && <AllergyTag substance={allergyDisplay} />}
                {patientIntakeNote && (
                  <span
                    className={`px-2 py-0.5 text-xs font-medium rounded-full border flex items-center gap-1 max-w-xs truncate ${
                      hasAllergy
                        ? 'bg-slate-100 text-slate-600 border-slate-200'
                        : 'bg-amber-50 text-amber-800 border-amber-200'
                    }`}
                    title={
                      hasAllergy
                        ? `Historical Intake Note: "${patientIntakeNote}" (Superseded by doctor-confirmed allergy)`
                        : `Patient Intake Statement: "${patientIntakeNote}"`
                    }
                  >
                    <span className="font-semibold text-slate-500">Intake Note:</span>
                    <span className="truncate">{patientIntakeNote}</span>
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleNewVisit}
              disabled={creatingVisit}
              className="text-xs"
            >
              {creatingVisit ? 'Creating…' : '+ New Visit'}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setActiveTab('transcript')}>Upload Transcript</Button>
            <Button variant="secondary" size="sm" onClick={() => setActiveTab('soap')}>SOAP Note</Button>
            {isFinalized ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setActiveTab('record')}
                className="bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100 font-medium text-xs"
              >
                ✓ View Final Record
              </Button>
            ) : (
              <Button size="sm" onClick={() => setActiveTab('record')}>
                Approve Record
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-slate-100 px-6">
        <Tabs tabs={tabs} active={activeTab} onChange={id => setActiveTab(id as TabId)} />
      </div>

      {/* Error notification if API fetch failed */}
      {error && (
        <div className="m-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{error}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => {
            if (identifier) {
              setLoading(true);
              setError(null);
              api.getDoctorIntakeSummary(identifier)
                .then(setDoctorData)
                .catch(err => setError(err.message))
                .finally(() => setLoading(false));
            }
          }}>
            Retry
          </Button>
        </div>
      )}

      {/* Tab content */}
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="text-center py-20 text-slate-400">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <div className="text-sm">Loading verified clinical intake record…</div>
          </div>
        ) : (
          <>
            {activeTab === 'summary' && (
              <SummaryTab
                doctorData={doctorData}
                previousVisits={previousVisits}
                onViewHistory={() => setActiveTab('history')}
              />
            )}
            {activeTab === 'history' && (
              <HistoryTab
                visits={visits}
                currentConsultationId={consultation?.id || null}
                onSelectVisit={handleSelectVisit}
                onNewVisit={handleNewVisit}
                isCreatingVisit={creatingVisit}
                patientName={patient.name}
              />
            )}
            {activeTab === 'transcript' && (
              <TranscriptTab
                consultation={consultation}
                onConsultationUpdated={handleConsultationUpdated}
                onProcessed={() => setActiveTab('soap')}
              />
            )}
            {activeTab === 'soap' && (
              <SOAPTab
                consultation={consultation}
                onConsultationUpdated={handleConsultationUpdated}
                onGoToTranscript={() => setActiveTab('transcript')}
                onGoToVerification={() => setActiveTab('verification')}
              />
            )}
            {activeTab === 'verification' && (
              <VerificationTab
                consultation={consultation}
                doctorData={doctorData}
                onConsultationUpdated={handleConsultationUpdated}
                onProceedToRecord={() => setActiveTab('record')}
                onGoBackToSoap={() => setActiveTab('soap')}
              />
            )}
            {activeTab === 'record' && (
              <RecordTab
                approved={isFinalized}
                onApprove={handleApproveRecord}
                consultation={consultation}
                doctorData={doctorData}
                visits={visits}
                patient={patient}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Summary Tab ───────────────────────────────────────────────────────────────
function SummaryTab({
  doctorData,
  previousVisits,
  onViewHistory,
}: {
  doctorData: DoctorIntakeSummaryResponse | null;
  previousVisits: ConsultationResponse[];
  onViewHistory: () => void;
}) {
  if (!doctorData) {
    return (
      <div className="max-w-2xl bg-white border border-slate-100 rounded-xl p-8 text-center my-4 shadow-xs">
        <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center text-2xl mx-auto mb-3">📋</div>
        <h4 className="font-semibold text-slate-800 text-base" style={{ fontFamily: 'DM Sans, sans-serif' }}>
          Direct Clinical Consultation
        </h4>
        <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
          This consultation was initiated directly in the clinical workspace without a self-reported intake form.
        </p>
        <div className="mt-4">
          <Button size="sm" variant="secondary" onClick={onViewHistory}>
            View Patient History
          </Button>
        </div>
      </div>
    );
  }

  const summary: PreConsultationSummary = doctorData.summary;

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-slate-800" style={{ fontFamily: 'DM Sans, sans-serif' }}>Pre-Consultation Intake</h3>
          <SourceBadge type="patient-reported" />
        </div>
        <div className="text-xs text-slate-400 font-mono-label">Submitted {summary.submitted_at}</div>
      </div>

      <AINotice message={summary.clinical_notice} />

      {summary.allergy_flags.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-center gap-2">
          <span>⚠</span>
          <span><strong>Allergy Alert:</strong> {summary.allergy_flags.join(' · ')}</span>
        </div>
      )}

      <div className="space-y-3">
        <Expandable title="Chief Complaint" defaultOpen>
          <p className="text-sm text-slate-700">{summary.chief_complaint}</p>
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {summary.symptoms.map(s => (
              <span key={s} className="px-2 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded text-xs font-medium">{s}</span>
            ))}
          </div>
        </Expandable>

        <Expandable title="Symptom Details" defaultOpen>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-slate-400 text-xs font-mono-label block mb-0.5">Duration</span>
              <span className="text-slate-800">{summary.duration}</span>
            </div>
            <div>
              <span className="text-slate-400 text-xs font-mono-label block mb-0.5">Severity</span>
              <div className="flex items-center gap-2">
                <div className="w-20 h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-400 rounded-full" style={{ width: `${summary.severity * 10}%` }} />
                </div>
                <span className="text-slate-800 font-medium">{summary.severity_label}</span>
              </div>
            </div>
          </div>
        </Expandable>

        {Object.keys(summary.adaptive_responses).length > 0 && (
          <Expandable title="Follow-Up Questionnaire Details" defaultOpen>
            <div className="space-y-2 text-sm">
              {Object.entries(summary.adaptive_responses).map(([q, a]) => (
                <div key={q} className="flex gap-3">
                  <span className="text-slate-400 font-mono-label w-48 flex-shrink-0 text-xs mt-0.5">{q}</span>
                  <span className="text-slate-800 font-medium">{a}</span>
                </div>
              ))}
            </div>
          </Expandable>
        )}

        <Expandable title="Medical History" defaultOpen>
          <div className="space-y-3 text-sm">
            <div className="flex gap-3">
              <span className="text-slate-400 font-mono-label w-36 flex-shrink-0 text-xs mt-0.5">Existing Conditions</span>
              <span className="text-slate-800 font-medium">{summary.conditions.join(', ') || 'None reported'}</span>
            </div>

            {/* Structured Condition Follow-Ups */}
            {summary.condition_details && Object.keys(summary.condition_details).length > 0 && (
              <div className="pt-2 space-y-2.5">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label">
                  Condition-Specific Follow-Up Details
                </div>
                {Object.entries(summary.condition_details).map(([conditionName, details]) => (
                  <div key={conditionName} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-slate-900 text-sm">{conditionName}</span>
                      <SourceBadge type="patient-reported" />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {Object.entries(details)
                        .filter(([k]) => k !== 'provenance')
                        .map(([k, val]) => {
                          const displayLabel =
                            k === 'type' ? 'Type' :
                            k === 'treatment' ? 'Treatment' :
                            k === 'inhaler_frequency' ? 'Inhaler use' :
                            k === 'recent_flare_up' ? 'Recent flare-up' :
                            k === 'last_reading' ? 'Last reading' :
                            k === 'medication' ? 'Medication' :
                            k === 'dialysis' ? 'Dialysis' :
                            k === 'restrictions' ? 'Dietary restrictions' :
                            k.replace(/_/g, ' ');
                          return (
                            <div key={k} className="flex flex-col">
                              <span className="text-slate-400">{displayLabel}:</span>
                              <span className="text-slate-800 font-medium">{val}</span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <span className="text-slate-400 font-mono-label w-36 flex-shrink-0 text-xs mt-0.5">Current Medications</span>
              <span className="text-slate-800">{summary.medications}</span>
            </div>
          </div>
        </Expandable>

        <Expandable
          title="Allergies"
          badge={summary.allergies && isClinicalAllergy(summary.allergies) ? <AllergyTag substance={summary.allergies} /> : undefined}
        >
          {isClinicalAllergy(summary.allergies) ? (
            <>
              <div className="text-sm text-slate-700">{summary.allergies}</div>
              <div className="mt-2 flex gap-1.5">
                <SourceBadge type="patient-reported" />
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <div className="text-sm text-slate-500 italic">None reported</div>
              {summary.allergies && summary.allergies.toLowerCase() !== 'none' && summary.allergies.toLowerCase() !== 'none reported' && (
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800">
                  <div className="font-semibold text-slate-700 mb-1 flex items-center gap-1">
                    <span>📋 Patient Intake Statement:</span>
                  </div>
                  <div className="italic text-slate-700">"{summary.allergies}"</div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    *Reported during intake question. Raw intake response preserved.
                  </div>
                </div>
              )}
            </div>
          )}
        </Expandable>

        <Expandable title="Additional Notes">
          <blockquote className="text-sm text-slate-700 italic border-l-3 border-slate-200 pl-3 leading-relaxed">
            "{summary.additional_notes}"
          </blockquote>
        </Expandable>
      </div>

      <div className="border-t border-slate-100 pt-4">
        <div className="text-xs text-slate-400 font-mono-label mb-2">PREVIOUS VISITS</div>
        {previousVisits.length === 0 ? (
          <div className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded-lg border border-slate-100">
            No previous visits on file for this patient.
          </div>
        ) : (
          <button
            onClick={onViewHistory}
            className="flex items-center justify-between w-full bg-white border border-slate-100 rounded-xl p-4 hover:border-slate-200 hover:shadow-sm transition-all text-left cursor-pointer"
          >
            <div>
              <div className="text-sm font-medium text-slate-800">
                {formatVisitDate(previousVisits[0].created_at)} — {previousVisits[0].soap_draft?.assessment || previousVisits[0].chief_complaint || 'Previous Consultation'}
              </div>
              <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                <SourceBadge type="doctor-confirmed" />
                <span>Dr. J. Patel</span>
                <span className="text-slate-300">·</span>
                <span>{previousVisits.length} prior visit{previousVisits.length === 1 ? '' : 's'}</span>
              </div>
            </div>
            <span className="text-slate-400 text-sm">→</span>
          </button>
        )}
      </div>
    </div>
  );
}


// ── History Tab ───────────────────────────────────────────────────────────────
interface HistoryTabProps {
  visits: ConsultationResponse[];
  currentConsultationId: string | null;
  onSelectVisit: (visit: ConsultationResponse) => void;
  onNewVisit: () => void;
  isCreatingVisit?: boolean;
  patientName?: string;
}

function HistoryTab({
  visits,
  currentConsultationId,
  onSelectVisit,
  onNewVisit,
  isCreatingVisit,
  patientName,
}: HistoryTabProps) {
  const [expandedVisitId, setExpandedVisitId] = useState<string | null>(null);

  const previousVisits = visits.filter(v => v.id !== currentConsultationId);
  const currentVisit = visits.find(v => v.id === currentConsultationId);

  return (
    <div className="max-w-3xl space-y-6">
      {/* Header with Visit count and New Visit button */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <h3 className="font-bold text-slate-900 text-lg" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            Visit History
          </h3>
          <p className="text-xs text-slate-500">
            {visits.length === 0
              ? 'Zero previous visits on record'
              : `${visits.length} total visit${visits.length === 1 ? '' : 's'} recorded for ${patientName || 'this patient'}`}
          </p>
        </div>
        <Button size="sm" variant="secondary" onClick={onNewVisit} disabled={isCreatingVisit}>
          {isCreatingVisit ? 'Creating…' : '+ Start New Visit'}
        </Button>
      </div>

      {/* Explicit Empty State for new patient with zero previous visits */}
      {previousVisits.length === 0 && (
        <div className="bg-white border border-slate-100 rounded-xl p-8 text-center shadow-xs">
          <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center text-2xl mx-auto mb-3">
            📋
          </div>
          <h4 className="font-semibold text-slate-800 text-base" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            No previous visits
          </h4>
          <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
            This patient has zero historical records, diagnoses, allergies, prescriptions, or previous consultations on file.
          </p>
          {currentVisit && (
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 font-medium">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <span>Current Visit ({formatVisitDate(currentVisit.created_at)}) is currently in progress.</span>
            </div>
          )}
        </div>
      )}

      {/* List of Visits */}
      {visits.length > 0 && (
        <div className="space-y-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono-label">
            All Visits ({visits.length})
          </div>

          <div className="relative pl-6 space-y-4">
            {/* Timeline vertical bar */}
            <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-slate-200" />

            {visits.map((visit, index) => {
              const isCurrent = visit.id === currentConsultationId;
              const visitNum = visits.length - index;
              const isExpanded = expandedVisitId === visit.id;
              const diagnosis =
                visit.soap_draft?.assessment ||
                (visit.extracted_clinical_data?.diagnoses && visit.extracted_clinical_data.diagnoses.length > 0
                  ? visit.extracted_clinical_data.diagnoses.join(', ')
                  : 'Pending clinical assessment');
              const complaint = visit.chief_complaint || 'Consultation visit';

              return (
                <div key={visit.id} className="relative flex items-start gap-4">
                  {/* Timeline dot */}
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 z-10 -ml-6 bg-white ${isCurrent ? 'border-blue-600 bg-blue-50' : 'border-slate-300'
                      }`}
                  >
                    <div className={`w-2 h-2 rounded-full ${isCurrent ? 'bg-blue-600' : 'bg-slate-400'}`} />
                  </div>

                  {/* Visit Card */}
                  <div
                    className={`flex-1 bg-white border rounded-xl overflow-hidden shadow-xs transition-all ${isCurrent ? 'border-blue-300 ring-1 ring-blue-100' : 'border-slate-200 hover:border-slate-300'
                      }`}
                  >
                    <div className="p-4 flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs font-bold text-slate-800 font-mono-label">
                            Visit #{visitNum}
                          </span>
                          <span className="text-xs text-slate-400 font-mono-label">
                            {formatVisitDate(visit.created_at)}
                          </span>
                          {isCurrent && (
                            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-medium">
                              Active / Open
                            </span>
                          )}
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${visit.status === 'in-progress'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              }`}
                          >
                            {visit.status === 'in-progress' ? 'In Progress' : 'Completed'}
                          </span>
                        </div>

                        <div className="text-sm font-semibold text-slate-900 mt-1">
                          {diagnosis}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          Complaint: {complaint} · Dr. J. Patel
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {!isCurrent && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => onSelectVisit(visit)}
                            className="text-xs cursor-pointer"
                          >
                            Open Visit
                          </Button>
                        )}
                        <button
                          onClick={() => setExpandedVisitId(isExpanded ? null : visit.id)}
                          className="text-xs text-slate-400 hover:text-slate-600 px-2 py-1 rounded cursor-pointer"
                          title="Toggle details"
                        >
                          {isExpanded ? '▴ Details' : '▾ Details'}
                        </button>
                      </div>
                    </div>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="border-t border-slate-100 p-4 bg-slate-50/60 space-y-3 text-xs">
                        {visit.soap_draft ? (
                          <div className="space-y-2">
                            <div>
                              <span className="font-semibold text-slate-600 uppercase font-mono-label">Subjective:</span>
                              <p className="text-slate-700 mt-0.5 leading-relaxed">{visit.soap_draft.subjective}</p>
                            </div>
                            <div>
                              <span className="font-semibold text-slate-600 uppercase font-mono-label">Objective:</span>
                              <p className="text-slate-700 mt-0.5 leading-relaxed">{visit.soap_draft.objective}</p>
                            </div>
                            <div>
                              <span className="font-semibold text-slate-600 uppercase font-mono-label">Assessment:</span>
                              <p className="text-slate-700 mt-0.5 leading-relaxed">{visit.soap_draft.assessment}</p>
                            </div>
                            <div>
                              <span className="font-semibold text-slate-600 uppercase font-mono-label">Plan:</span>
                              <p className="text-slate-700 mt-0.5 leading-relaxed">{visit.soap_draft.plan}</p>
                            </div>
                          </div>
                        ) : (
                          <p className="text-slate-500 italic">No SOAP note draft generated for this visit.</p>
                        )}
                        {visit.transcript && (
                          <div className="pt-2 border-t border-slate-200">
                            <span className="font-semibold text-slate-600 uppercase font-mono-label">Transcript Snippet:</span>
                            <p className="text-slate-600 mt-0.5 line-clamp-3 font-sans leading-relaxed">
                              {visit.transcript}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Transcript Tab ────────────────────────────────────────────────────────────
function TranscriptTab({
  consultation,
  onConsultationUpdated,
  onProcessed,
}: {
  consultation: ConsultationResponse | null;
  onConsultationUpdated?: (updated: ConsultationResponse) => void;
  onProcessed: () => void;
}) {
  const [text, setText] = useState(consultation?.transcript || '');
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [extractSuccess, setExtractSuccess] = useState(false);
  const [speakerRole, setSpeakerRole] = useState<'doctor' | 'patient' | 'unlabeled'>('doctor');

  // Sync state with real consultation transcript when loaded or changed
  useEffect(() => {
    if (consultation?.transcript !== undefined) {
      setText(consultation.transcript);
    }
  }, [consultation?.id, consultation?.transcript]);

  const handleVoiceTranscribe = (newSpeech: string) => {
    if (!newSpeech || !newSpeech.trim()) return;
    const speech = newSpeech.trim();
    let formattedSpeech = speech;
    if (speakerRole === 'doctor') {
      formattedSpeech = speech.toLowerCase().startsWith('doctor:') ? speech : `Doctor: ${speech}`;
    } else if (speakerRole === 'patient') {
      formattedSpeech = speech.toLowerCase().startsWith('patient:') ? speech : `Patient: ${speech}`;
    }

    setText(prev => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed}\n\n${formattedSpeech}` : formattedSpeech;
    });
    setSaveSuccess(false);
  };

  const handleSave = async () => {
    if (!consultation?.id) {
      setSaveError('No active consultation session found. Please ensure the consultation has started.');
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);
      const updated = await api.updateConsultationTranscript(consultation.id, text, false);
      if (onConsultationUpdated) {
        onConsultationUpdated(updated);
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
      return updated;
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save transcript');
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const handleExtract = async () => {
    if (!consultation?.id) {
      setExtractError('No active consultation session found. Please select a patient.');
      return;
    }

    if (!text.trim()) {
      setExtractError('Transcript is empty. Please enter, paste, or record a transcript first before extracting.');
      return;
    }

    try {
      setExtracting(true);
      setExtractError(null);

      // If there are unsaved edits, automatically save them first
      if (hasUnsavedChanges) {
        await handleSave();
      }

      const updated = await api.extractClinicalInformation(consultation.id);
      if (onConsultationUpdated) {
        onConsultationUpdated(updated);
      }
      setExtractSuccess(true);
      setTimeout(() => setExtractSuccess(false), 4000);
    } catch (err: unknown) {
      setExtractError(err instanceof Error ? err.message : 'Clinical extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleClear = async () => {
    if (!text.trim()) return;
    if (!window.confirm('Are you sure you want to clear the current transcript?')) {
      return;
    }

    if (!consultation?.id) {
      setText('');
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);
      const updated = await api.updateConsultationTranscript(consultation.id, '', true);
      setText('');
      if (onConsultationUpdated) {
        onConsultationUpdated(updated);
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to clear transcript');
    } finally {
      setSaving(false);
    }
  };

  const hasUnsavedChanges = consultation ? (consultation.transcript || '') !== text : Boolean(text);
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  return (
    <div className="max-w-3xl space-y-4">
      {/* Header bar with Voice Recording and Status */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            Consultation Audio & Transcript
          </span>
          {consultation && (
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              ID: {consultation.id.slice(0, 8)}…
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Speaker role selector for consultation recording */}
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <span className="text-[11px] text-slate-500 font-mono-label px-1">Speaking:</span>
            <button
              type="button"
              onClick={() => setSpeakerRole('doctor')}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-all cursor-pointer ${
                speakerRole === 'doctor'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Doctor
            </button>
            <button
              type="button"
              onClick={() => setSpeakerRole('patient')}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-all cursor-pointer ${
                speakerRole === 'patient'
                  ? 'bg-emerald-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Patient
            </button>
            <button
              type="button"
              onClick={() => setSpeakerRole('unlabeled')}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-all cursor-pointer ${
                speakerRole === 'unlabeled'
                  ? 'bg-slate-700 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Raw
            </button>
          </div>

          {/* Working Module 1 VoiceButton reused directly */}
          <VoiceButton
            onTranscribe={handleVoiceTranscribe}
            className="flex-shrink-0"
          />
          {hasUnsavedChanges && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-50 text-amber-700 border border-amber-200">
              ● Unsaved edits
            </span>
          )}
          {!hasUnsavedChanges && consultation?.transcript && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-green-50 text-green-700 border border-green-200">
              ✓ Saved to record
            </span>
          )}
        </div>
      </div>

      {/* Notifications */}
      {saveSuccess && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-xs flex items-center gap-2">
          <span>✓</span>
          <span>Transcript successfully saved to the consultation record in the database.</span>
        </div>
      )}

      {saveError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{saveError}</span>
          </div>
          <button
            onClick={() => setSaveError(null)}
            className="text-red-600 hover:text-red-800 font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Manual text input / editable transcript area */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-slate-600 uppercase tracking-wide font-mono-label">
              Live Consultation Transcript (Type, Paste, or Dictate)
            </label>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-slate-400 font-mono-label">Quick Tag:</span>
              <button
                type="button"
                onClick={() => {
                  setText(prev => {
                    const trimmed = prev.trim();
                    return trimmed ? `${trimmed}\n\nDoctor: ` : 'Doctor: ';
                  });
                  setSaveSuccess(false);
                }}
                className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 cursor-pointer"
              >
                + Doctor:
              </button>
              <button
                type="button"
                onClick={() => {
                  setText(prev => {
                    const trimmed = prev.trim();
                    return trimmed ? `${trimmed}\n\nPatient: ` : 'Patient: ';
                  });
                  setSaveSuccess(false);
                }}
                className="px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 cursor-pointer"
              >
                + Patient:
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-400 font-mono-label">
            <span>{wordCount} words</span>
            <span>{text.length} characters</span>
          </div>
        </div>

        <textarea
          value={text}
          onChange={e => {
            setText(e.target.value);
            setSaveSuccess(false);
          }}
          placeholder="Start recording consultation audio or type/paste the transcript here...&#10;&#10;Example:&#10;Doctor: How long have you had this fever?&#10;Patient: About 3 days, started Sunday evening."
          rows={16}
          className="w-full px-4 py-3 rounded-lg border border-slate-200 bg-slate-50/50 focus:bg-white text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y font-mono text-slate-800 transition-colors"
          style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px' }}
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <Button
              onClick={handleSave}
              disabled={saving || !consultation}
              size="sm"
            >
              {saving ? 'Saving to Database…' : '💾 Save Transcript'}
            </Button>
            <Button
              onClick={handleExtract}
              disabled={extracting || !text.trim() || !consultation}
              size="sm"
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {extracting ? (
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Extracting Facts…
                </span>
              ) : (
                '⚡ Extract Clinical Information'
              )}
            </Button>
            {text.trim() && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClear}
                disabled={saving || extracting}
              >
                Clear
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">
              Raw speech is preserved without premature translation.
            </span>
          </div>
        </div>
      </div>

      {/* Extraction error notification */}
      {extractError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{extractError}</span>
          </div>
          <button
            onClick={() => setExtractError(null)}
            className="text-red-600 hover:text-red-800 font-bold ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Extraction success notification */}
      {extractSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2">
          <span>✓</span>
          <span>Clinical facts successfully extracted from transcript and saved to consultation record.</span>
        </div>
      )}

      {/* Structured Clinical Information Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                Structured Clinical Facts
              </h3>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 font-mono">
                AI-Generated · Unverified
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Facts strictly extracted from the consultation transcript.
            </p>
          </div>
          {consultation?.extracted_clinical_data && (
            <span className="text-xs text-slate-400 font-mono-label">
              Provenance: {consultation.extracted_clinical_data.provenance}
            </span>
          )}
        </div>

        <AINotice message="These clinical facts were automatically extracted from the raw consultation transcript by AI. They have not been clinically verified or approved by a physician." />

        {consultation?.extracted_clinical_data ? (
          <div className="space-y-4 pt-1">
            {/* Symptoms */}
            {consultation.extracted_clinical_data.symptoms.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Symptoms ({consultation.extracted_clinical_data.symptoms.length})
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {consultation.extracted_clinical_data.symptoms.map((s, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-sky-50/60 border border-sky-100 text-xs">
                      <div className="font-semibold text-sky-950">{s.name}</div>
                      <div className="text-sky-700 mt-1 flex flex-wrap gap-2 text-[11px]">
                        {s.duration && <span>⏱ Duration: <strong>{s.duration}</strong></span>}
                        {s.severity && <span>⚡ Severity: <strong>{s.severity}</strong></span>}
                        {s.onset && <span>Onset: {s.onset}</span>}
                        {s.details && <span>Details: {s.details}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Medications */}
            {consultation.extracted_clinical_data.medications.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Medications ({consultation.extracted_clinical_data.medications.length})
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {consultation.extracted_clinical_data.medications.map((m, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-emerald-50/60 border border-emerald-100 text-xs">
                      <div className="font-semibold text-emerald-950">{m.name}</div>
                      <div className="text-emerald-700 mt-1 flex flex-wrap gap-2 text-[11px]">
                        {m.dose && <span>Dose: <strong>{m.dose}</strong></span>}
                        {m.frequency && <span>Freq: <strong>{m.frequency}</strong></span>}
                        {m.status && <span>Status: <em>{m.status}</em></span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Allergies */}
            {consultation.extracted_clinical_data.allergies.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Allergies ({consultation.extracted_clinical_data.allergies.length})
                </span>
                <div className="flex flex-wrap gap-2">
                  {consultation.extracted_clinical_data.allergies.map((a, idx) => (
                    <div key={idx} className="px-3 py-1.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900">
                      <strong>⚠ {a.substance}</strong>
                      {a.reaction && <span className="ml-1.5 text-rose-700">— Reaction: {a.reaction}</span>}
                      {a.severity && <span className="ml-1.5 text-rose-600">({a.severity})</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Negative Findings */}
            {consultation.extracted_clinical_data.negative_findings.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Explicit Negative Findings / Denied Symptoms
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {consultation.extracted_clinical_data.negative_findings.map((nf, idx) => (
                    <span key={idx} className="px-2.5 py-1 bg-slate-100 text-slate-700 border border-slate-200 rounded-md text-xs">
                      ✕ {nf}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Observations / Vitals / Physical Exam */}
            {consultation.extracted_clinical_data.observations.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Clinical Observations & Exam Findings
                </span>
                <ul className="list-disc list-inside text-xs text-slate-700 space-y-1">
                  {consultation.extracted_clinical_data.observations.map((o, idx) => (
                    <li key={idx}>{o}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Diagnoses (if explicitly stated) */}
            {consultation.extracted_clinical_data.diagnoses.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Explicitly Stated Diagnoses / Clinical Impression
                </span>
                <ul className="list-disc list-inside text-xs text-slate-700 space-y-1">
                  {consultation.extracted_clinical_data.diagnoses.map((d, idx) => (
                    <li key={idx}>{d}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Plan (if explicitly stated) */}
            {consultation.extracted_clinical_data.plan.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Explicitly Stated Plan & Next Steps
                </span>
                <ul className="list-disc list-inside text-xs text-slate-700 space-y-1">
                  {consultation.extracted_clinical_data.plan.map((p, idx) => (
                    <li key={idx}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Past Medical History (if explicitly stated) */}
            {consultation.extracted_clinical_data.medical_history.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider font-mono-label block mb-2">
                  Explicit Past Medical History
                </span>
                <ul className="list-disc list-inside text-xs text-slate-700 space-y-1">
                  {consultation.extracted_clinical_data.medical_history.map((h, idx) => (
                    <li key={idx}>{h}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
            <div className="text-2xl mb-2">📋</div>
            <div className="text-xs font-medium text-slate-700 mb-1">No structured clinical facts extracted yet</div>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              Save your consultation transcript above and click <strong>"Extract Clinical Information"</strong> to parse factual clinical statements.
            </p>
          </div>
        )}

        <div className="pt-2 flex justify-end">
          <Button onClick={onProcessed} size="sm" variant="secondary">
            Next: Review SOAP Note →
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── SOAP Note Tab ─────────────────────────────────────────────────────────────
interface SOAPTabProps {
  consultation: ConsultationResponse | null;
  onConsultationUpdated?: (consultation: ConsultationResponse) => void;
  onGoToTranscript: () => void;
  onGoToVerification?: () => void;
}

function SOAPTab({ consultation, onConsultationUpdated, onGoToTranscript, onGoToVerification }: SOAPTabProps) {
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);

  const [subjective, setSubjective] = useState('');
  const [objective, setObjective] = useState('');
  const [assessment, setAssessment] = useState('');
  const [plan, setPlan] = useState('');

  // Sync draft from consultation
  useEffect(() => {
    if (consultation?.soap_draft) {
      setSubjective(consultation.soap_draft.subjective || '');
      setObjective(consultation.soap_draft.objective || '');
      setAssessment(consultation.soap_draft.assessment || '');
      setPlan(consultation.soap_draft.plan || '');
    } else {
      setSubjective('');
      setObjective('');
      setAssessment('');
      setPlan('');
    }
  }, [consultation?.soap_draft]);

  const hasTranscript = Boolean(consultation?.transcript && consultation.transcript.trim());
  const hasExtraction = Boolean(consultation?.extracted_clinical_data);
  const hasDraft = Boolean(consultation?.soap_draft);

  const hasUnsavedChanges = hasDraft
    ? subjective !== (consultation?.soap_draft?.subjective || '') ||
    objective !== (consultation?.soap_draft?.objective || '') ||
    assessment !== (consultation?.soap_draft?.assessment || '') ||
    plan !== (consultation?.soap_draft?.plan || '')
    : Boolean(subjective || objective || assessment || plan);

  const handleGenerate = async () => {
    if (!consultation?.id) {
      setError('No active consultation record found. Please start a consultation first.');
      return;
    }
    if (!hasTranscript) {
      setError('Consultation transcript is empty. Please enter or record a transcript in the Transcript tab first.');
      return;
    }
    if (!hasExtraction) {
      setError('Clinical information must be extracted before generating a SOAP draft. Please extract clinical information in the Transcript tab first.');
      return;
    }

    try {
      setGenerating(true);
      setError(null);
      setSuccess(null);
      const updated = await api.generateSoapDraft(consultation.id);
      if (onConsultationUpdated) {
        onConsultationUpdated(updated);
      }
      setSuccess('SOAP draft generated successfully.');
      setTimeout(() => setSuccess(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate SOAP draft.');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!consultation?.id) {
      setError('No active consultation record found.');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      const updated = await api.updateSoapDraft(consultation.id, {
        subjective,
        objective,
        assessment,
        plan,
      });
      if (onConsultationUpdated) {
        onConsultationUpdated(updated);
      }
      setSuccess('Draft updated and saved to consultation record.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save SOAP draft.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-4">
      {/* Top Banner: Prominent AI-Generated / Unverified Notice */}
      <div className="p-3.5 bg-amber-50/90 border border-amber-200 rounded-xl text-amber-900 text-xs flex items-start justify-between gap-3 shadow-sm">
        <div className="flex items-start gap-2.5">
          <span className="text-base text-amber-700">⚠</span>
          <div>
            <div className="font-semibold flex items-center gap-2 mb-0.5 text-amber-900">
              <span>AI-Generated · Draft · Unverified</span>
              <span className="px-1.5 py-0.5 bg-amber-200/80 text-amber-900 rounded font-mono text-[10px] uppercase font-semibold">
                Working Draft Only
              </span>
            </div>
            <p className="text-amber-800 leading-relaxed">
              This SOAP note is an automated working draft generated from the consultation transcript and extracted facts.
              It is <strong>unverified</strong> and has <strong>NOT</strong> been reviewed, approved, or signed by a physician.
            </p>
          </div>
        </div>
        {hasDraft && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowEvidence(!showEvidence)}
            className="flex-shrink-0 text-xs"
          >
            {showEvidence ? 'Hide Source Evidence' : 'View Source Evidence'}
          </Button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800 font-bold ml-2">✕</button>
        </div>
      )}

      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>✓</span>
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess(null)} className="text-green-600 hover:text-green-800 font-bold ml-2">✕</button>
        </div>
      )}

      {/* Collapsible Source Evidence Panel */}
      {showEvidence && (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <h4 className="text-xs font-semibold text-slate-800 uppercase tracking-wider font-mono-label">
              Source Evidence (Consultation Record)
            </h4>
            <span className="text-[11px] text-slate-500">Compare draft against raw source</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Raw Transcript */}
            <div className="p-3 bg-white border border-slate-200 rounded-lg">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1 font-mono-label">
                Preserved Raw Transcript
              </span>
              <p className="text-xs text-slate-700 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed font-sans">
                {consultation?.transcript || 'No transcript recorded.'}
              </p>
            </div>

            {/* Extracted Facts */}
            <div className="p-3 bg-white border border-slate-200 rounded-lg">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1 font-mono-label">
                Extracted Clinical Facts
              </span>
              {consultation?.extracted_clinical_data ? (
                <div className="text-xs text-slate-700 space-y-1.5 max-h-48 overflow-y-auto">
                  {consultation.extracted_clinical_data.symptoms.length > 0 && (
                    <div>
                      <strong>Symptoms:</strong>{' '}
                      {consultation.extracted_clinical_data.symptoms.map(s => s.name + (s.duration ? ` (${s.duration})` : '')).join(', ')}
                    </div>
                  )}
                  {consultation.extracted_clinical_data.medications.length > 0 && (
                    <div>
                      <strong>Medications:</strong>{' '}
                      {consultation.extracted_clinical_data.medications.map(m => m.name + (m.frequency ? ` - ${m.frequency}` : '')).join(', ')}
                    </div>
                  )}
                  {consultation.extracted_clinical_data.allergies.length > 0 && (
                    <div>
                      <strong>Allergies:</strong>{' '}
                      {consultation.extracted_clinical_data.allergies.map(a => `${a.substance} (${a.reaction || 'rash'})`).join(', ')}
                    </div>
                  )}
                  {consultation.extracted_clinical_data.negative_findings.length > 0 && (
                    <div>
                      <strong>Negative Findings:</strong>{' '}
                      {consultation.extracted_clinical_data.negative_findings.join(', ')}
                    </div>
                  )}
                  {consultation.extracted_clinical_data.diagnoses.length > 0 && (
                    <div>
                      <strong>Diagnoses:</strong>{' '}
                      {consultation.extracted_clinical_data.diagnoses.join(', ')}
                    </div>
                  )}
                  {consultation.extracted_clinical_data.plan.length > 0 && (
                    <div>
                      <strong>Plan:</strong>{' '}
                      {consultation.extracted_clinical_data.plan.join(', ')}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No clinical facts extracted yet.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      {!hasDraft ? (
        <div className="p-8 bg-white border border-slate-200 rounded-xl shadow-sm text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xl mx-auto">
            📝
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 text-base" style={{ fontFamily: 'DM Sans, sans-serif' }}>
              No SOAP Draft Generated
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
              Generate a structured Subjective, Objective, Assessment, and Plan draft note from the consultation transcript and validated clinical extraction.
            </p>
          </div>

          {/* Preconditions Checklist */}
          <div className="max-w-md mx-auto bg-slate-50 border border-slate-200 rounded-lg p-3 text-left space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                {hasTranscript ? <span className="text-green-600 font-bold">✓</span> : <span className="text-amber-500 font-bold">○</span>}
                <span className={hasTranscript ? 'text-slate-700' : 'text-slate-400'}>1. Saved Consultation Transcript</span>
              </span>
              {!hasTranscript && (
                <button onClick={onGoToTranscript} className="text-blue-600 hover:underline text-[11px] font-medium">
                  Go to Transcript →
                </button>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                {hasExtraction ? <span className="text-green-600 font-bold">✓</span> : <span className="text-amber-500 font-bold">○</span>}
                <span className={hasExtraction ? 'text-slate-700' : 'text-slate-400'}>2. Extracted Clinical Facts (Phase 2.3)</span>
              </span>
              {!hasExtraction && hasTranscript && (
                <button onClick={onGoToTranscript} className="text-blue-600 hover:underline text-[11px] font-medium">
                  Extract Facts →
                </button>
              )}
            </div>
          </div>

          <div className="pt-2">
            <Button
              onClick={handleGenerate}
              disabled={generating || !hasTranscript || !hasExtraction}
              className="px-6"
            >
              {generating ? (
                <span className="flex items-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Generating SOAP Draft…
                </span>
              ) : (
                'Generate SOAP Draft'
              )}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Header Bar with Action Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-white border border-slate-200 rounded-xl shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-800" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                SOAP Working Draft
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-medium">
                Unverified Draft
              </span>
              {hasUnsavedChanges && (
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-50 text-amber-700 border border-amber-200">
                  ● Unsaved edits
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleGenerate}
                disabled={generating}
              >
                {generating ? 'Regenerating…' : 'Regenerate Draft'}
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={saving || !hasUnsavedChanges}
              >
                {saving ? 'Saving…' : 'Save / Update Draft'}
              </Button>
            </div>
          </div>

          {/* 4 SOAP Sections */}
          <div className="space-y-3">
            {/* Subjective */}
            <Card className="overflow-hidden border border-slate-200">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-blue-100 text-blue-700 font-mono font-bold text-xs flex items-center justify-center">
                    S
                  </span>
                  <span className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                    Subjective
                  </span>
                  <span className="text-[11px] text-slate-400">
                    — Patient-reported symptoms, history, meds, allergies, and negative findings
                  </span>
                </div>
                <SourceBadge type="ai-generated" />
              </div>
              <div className="p-3">
                <textarea
                  value={subjective}
                  onChange={e => setSubjective(e.target.value)}
                  rows={4}
                  className="w-full text-xs text-slate-800 bg-transparent border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-sans leading-relaxed resize-y"
                  placeholder="Patient-reported symptoms and history..."
                />
              </div>
            </Card>

            {/* Objective */}
            <Card className="overflow-hidden border border-slate-200">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-emerald-100 text-emerald-700 font-mono font-bold text-xs flex items-center justify-center">
                    O
                  </span>
                  <span className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                    Objective
                  </span>
                  <span className="text-[11px] text-slate-400">
                    — Explicitly documented physical exams, vitals, labs, or "Not documented."
                  </span>
                </div>
                <SourceBadge type="ai-generated" />
              </div>
              <div className="p-3">
                <textarea
                  value={objective}
                  onChange={e => setObjective(e.target.value)}
                  rows={2}
                  className="w-full text-xs text-slate-800 bg-transparent border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-sans leading-relaxed resize-y"
                  placeholder="Not documented."
                />
              </div>
            </Card>

            {/* Assessment */}
            <Card className="overflow-hidden border border-slate-200">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-purple-100 text-purple-700 font-mono font-bold text-xs flex items-center justify-center">
                    A
                  </span>
                  <span className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                    Assessment
                  </span>
                  <span className="text-[11px] text-slate-400">
                    — Clinician-stated diagnosis/impression only, or "Not explicitly documented."
                  </span>
                </div>
                <SourceBadge type="ai-generated" />
              </div>
              <div className="p-3">
                <textarea
                  value={assessment}
                  onChange={e => setAssessment(e.target.value)}
                  rows={2}
                  className="w-full text-xs text-slate-800 bg-transparent border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-sans leading-relaxed resize-y"
                  placeholder="Not explicitly documented."
                />
              </div>
            </Card>

            {/* Plan */}
            <Card className="overflow-hidden border border-slate-200">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-sky-100 text-sky-700 font-mono font-bold text-xs flex items-center justify-center">
                    P
                  </span>
                  <span className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'DM Sans, sans-serif' }}>
                    Plan
                  </span>
                  <span className="text-[11px] text-slate-400">
                    — Clinician-stated treatment, investigations, prescriptions, or "Not documented."
                  </span>
                </div>
                <SourceBadge type="ai-generated" />
              </div>
              <div className="p-3">
                <textarea
                  value={plan}
                  onChange={e => setPlan(e.target.value)}
                  rows={3}
                  className="w-full text-xs text-slate-800 bg-transparent border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 font-sans leading-relaxed resize-y"
                  placeholder="Not documented."
                />
              </div>
            </Card>

            {/* Bottom Actions */}
            <div className="pt-3 flex justify-between items-center border-t border-slate-100">
              <Button onClick={onGoToTranscript} size="sm" variant="secondary">
                ← Back to Transcript
              </Button>
              {onGoToVerification && (
                <Button onClick={onGoToVerification} size="sm">
                  Next: Verify Claims & Conflicts →
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Verification & Conflicts Tab (Agents 3 & 4) ──────────────────────────────
interface VerificationTabProps {
  consultation: ConsultationResponse | null;
  doctorData: DoctorIntakeSummaryResponse | null;
  onConsultationUpdated: (consultation: ConsultationResponse) => void;
  onProceedToRecord: () => void;
  onGoBackToSoap: () => void;
}

function VerificationTab({
  consultation,
  doctorData,
  onConsultationUpdated,
  onProceedToRecord,
  onGoBackToSoap,
}: VerificationTabProps) {
  const [runningVerif, setRunningVerif] = useState(false);
  const [runningComp, setRunningComp] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolutionText, setResolutionText] = useState<{ [id: string]: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const verifResults = consultation?.verification_results;
  const compResults = consultation?.comparison_results;

  const handleRunVerification = async () => {
    if (!consultation?.id) return;
    if (!consultation.soap_draft) {
      setError('Please generate a SOAP draft note before running verification.');
      return;
    }
    try {
      setRunningVerif(true);
      setError(null);
      const updated = await api.verifyConsultation(consultation.id);
      onConsultationUpdated(updated);
      setSuccess('Verification completed.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setRunningVerif(false);
    }
  };

  const handleRunComparison = async () => {
    if (!consultation?.id) return;
    try {
      setRunningComp(true);
      setError(null);
      const updated = await api.compareIntakeConsultation(consultation.id);
      onConsultationUpdated(updated);
      setSuccess('Intake vs Consultation comparison completed.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Comparison failed');
    } finally {
      setRunningComp(false);
    }
  };

  const handleRunBoth = async () => {
    if (!consultation?.id) return;
    if (!consultation.soap_draft) {
      setError('Please generate a SOAP draft note before running verification.');
      return;
    }
    try {
      setRunningVerif(true);
      setRunningComp(true);
      setError(null);
      await api.verifyConsultation(consultation.id);
      const cUpdated = await api.compareIntakeConsultation(consultation.id);
      onConsultationUpdated(cUpdated);
      setSuccess('Claim verification and conflict intelligence completed.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setRunningVerif(false);
      setRunningComp(false);
    }
  };

  const handleResolve = async (itemId: string) => {
    if (!consultation?.id) return;
    const text = resolutionText[itemId]?.trim() || 'Clinician confirmed and resolved discrepancy with patient.';
    try {
      setResolvingId(itemId);
      const updated = await api.resolveDiscrepancy(consultation.id, itemId, text);
      onConsultationUpdated(updated);
      setSuccess('Discrepancy resolved.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resolve discrepancy');
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white border border-slate-200 rounded-xl shadow-xs">
        <div>
          <h3 className="font-bold text-slate-900 text-base" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            Agentic Verification & Comparison Workspace
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Agent 3 (Claim-Level Verification) & Agent 4 (Module 1 vs Module 2 Comparison)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={handleRunVerification}
            disabled={runningVerif || !consultation?.soap_draft}
          >
            {runningVerif ? 'Verifying…' : 'Run Verification (Agent 3)'}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={handleRunComparison}
            disabled={runningComp}
          >
            {runningComp ? 'Comparing…' : 'Run Comparison (Agent 4)'}
          </Button>
          <Button
            size="sm"
            onClick={handleRunBoth}
            disabled={runningVerif || runningComp || !consultation?.soap_draft}
          >
            {runningVerif || runningComp ? 'Analyzing…' : '⚡ Run All Agents'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-800 text-xs flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-red-600 font-bold">✕</button>
        </div>
      )}

      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-xs flex items-center justify-between">
          <span>✓ {success}</span>
          <button onClick={() => setSuccess(null)} className="text-green-600 font-bold">✕</button>
        </div>
      )}

      {/* SECTION 1: CLAIM-LEVEL VERIFICATION (AGENT 3) */}
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded bg-indigo-100 text-indigo-700 font-mono font-bold text-xs flex items-center justify-center">3</span>
            <SectionLabel>Agent 3: Claim-Level Verification & Source Grounding</SectionLabel>
          </div>
          {verifResults && (
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded font-mono font-medium">
                ✓ {verifResults.supported_count} Supported
              </span>
              <span className="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded font-mono font-medium">
                ~ {verifResults.ambiguous_count} Ambiguous
              </span>
              <span className="px-2 py-0.5 bg-red-50 text-red-700 border border-red-200 rounded font-mono font-medium">
                ✕ {verifResults.unsupported_count} Unsupported
              </span>
            </div>
          )}
        </div>

        {!verifResults || verifResults.claims.length === 0 ? (
          <div className="text-center py-8 bg-slate-50/60 rounded-lg border border-dashed border-slate-200">
            <div className="text-2xl mb-1">🔍</div>
            <div className="text-xs font-semibold text-slate-700 mb-1">Verification Agent has not been executed yet</div>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mb-3">
              Click <strong>"Run Verification (Agent 3)"</strong> to verify SOAP claims against transcript evidence.
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={handleRunVerification}
              disabled={runningVerif || !consultation?.soap_draft}
            >
              {runningVerif ? 'Verifying…' : 'Run Verification Now'}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {verifResults.claims.map(claim => {
              const badgeVariant = claim.status === 'supported' ? 'supported' : claim.status === 'unsupported' ? 'unsupported' : 'ambiguous';
              const borderClass = claim.status === 'unsupported' ? 'border-red-200 bg-red-50/20' : claim.status === 'ambiguous' ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200 bg-white';
              return (
                <div key={claim.id} className={`p-3.5 rounded-lg border ${borderClass} space-y-2`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[10px] uppercase font-bold">
                        {claim.section.slice(0, 3)}
                      </span>
                      <p className="text-xs font-semibold text-slate-800 leading-snug">{claim.claim}</p>
                    </div>
                    <VerifBadge status={badgeVariant} />
                  </div>
                  <blockquote className="text-xs text-slate-600 italic border-l-2 border-slate-200 pl-2.5 py-0.5 leading-relaxed">
                    <span className="font-semibold not-italic font-mono-label text-[10px] text-slate-400 uppercase mr-1">Source Evidence:</span>
                    {claim.evidence}
                  </blockquote>
                  {claim.explanation && (
                    <div className="text-[11px] text-slate-500 font-sans leading-normal">
                      {claim.explanation}
                    </div>
                  )}
                  {claim.status === 'unsupported' && (
                    <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2.5 py-1 font-medium">
                      ⚠ CRITICAL SAFETY NOTICE: This claim has no transcript evidence. Review and correct before approving.
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* SECTION 2: MODULE 1 VS MODULE 2 COMPARISON (AGENT 4) */}
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded bg-sky-100 text-sky-700 font-mono font-bold text-xs flex items-center justify-center">4</span>
            <SectionLabel>Agent 4: Module 1 vs Module 2 Comparison & Conflict Detection</SectionLabel>
          </div>
          {compResults && (
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded font-mono font-medium">
                ✓ {compResults.confirmed_count} Confirmed
              </span>
              <span className="px-2 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded font-mono font-medium">
                + {compResults.new_count} New
              </span>
              <span className="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded font-mono font-medium">
                ⚠ {compResults.discrepancy_count} Discrepancies
              </span>
              <span className="px-2 py-0.5 bg-slate-100 text-slate-600 border border-slate-200 rounded font-mono font-medium">
                ○ {compResults.not_mentioned_count ?? compResults.items.filter(i => i.type === 'not_mentioned_in_consultation').length} Not Mentioned
              </span>
            </div>
          )}
        </div>

        {!compResults || compResults.items.length === 0 ? (
          <div className="text-center py-8 bg-slate-50/60 rounded-lg border border-dashed border-slate-200">
            <div className="text-2xl mb-1">⚖️</div>
            <div className="text-xs font-semibold text-slate-700 mb-1">Comparison Agent has not been executed yet</div>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mb-3">
              Click <strong>"Run Comparison (Agent 4)"</strong> to detect differences between intake and consultation.
            </p>
            <Button
              size="sm"
              variant="secondary"
              onClick={handleRunComparison}
              disabled={runningComp}
            >
              {runningComp ? 'Comparing…' : 'Run Comparison Now'}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {compResults.items.map(item => {
              const isDiscrepancy = item.type === 'discrepancy';
              const cardBorder = isDiscrepancy ? 'border-amber-200' : 'border-slate-200';
              const badgeStyle = item.type === 'confirmed'
                ? 'bg-green-50 text-green-700 border-green-200'
                : item.type === 'new_in_consultation'
                ? 'bg-sky-50 text-sky-700 border-sky-200'
                : item.type === 'discrepancy'
                ? 'bg-amber-50 text-amber-800 border-amber-200'
                : 'bg-slate-50 text-slate-600 border-slate-200';

              const typeLabel = item.type === 'confirmed'
                ? 'Confirmed in Both'
                : item.type === 'new_in_consultation'
                ? 'New Finding'
                : item.type === 'discrepancy'
                ? 'Potential Discrepancy'
                : 'Not Mentioned';

              return (
                <div key={item.id} className={`bg-white rounded-lg border ${cardBorder} overflow-hidden shadow-xs`}>
                  <div className="px-4 py-2 bg-slate-50/70 border-b border-slate-100 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700 uppercase font-mono-label tracking-wide">
                      {item.label}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium border font-mono ${badgeStyle}`}>
                      {typeLabel}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                    <div className="p-3 bg-slate-50/30">
                      <div className="text-[11px] text-slate-400 font-mono-label mb-1 uppercase font-semibold">
                        Module 1: Pre-Consult Intake
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed font-sans">{item.intake_value}</p>
                    </div>
                    <div className="p-3 bg-white">
                      <div className="text-[11px] text-slate-400 font-mono-label mb-1 uppercase font-semibold">
                        Module 2: Doctor Consultation
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed font-sans">{item.consultation_value}</p>
                    </div>
                  </div>

                  <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/40 text-xs text-slate-600">
                    {item.description}
                  </div>

                  {/* Resolution state: only displayed when an actual clinician entered a resolution */}
                  {item.resolution && !item.resolution.startsWith('Confirmed consistent') && !item.resolution.startsWith('Documented as new') && !item.resolution.startsWith('Duration consistent') && !item.resolution.startsWith('Medication confirmed') && !item.resolution.startsWith('Allergy confirmed') && !item.resolution.startsWith('Direct clinical') ? (
                    <div className="px-4 py-2 bg-green-50 border-t border-green-100 flex items-center gap-2 text-xs text-green-800">
                      <span className="font-bold">✓ Doctor Resolution:</span>
                      <span>{item.resolution}</span>
                    </div>
                  ) : isDiscrepancy ? (
                    <div className="p-3 bg-amber-50/40 border-t border-amber-100 space-y-2">
                      <div className="text-xs font-semibold text-amber-900">
                        Doctor Clinical Resolution Required:
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={resolutionText[item.id] || ''}
                          onChange={e => setResolutionText({ ...resolutionText, [item.id]: e.target.value })}
                          placeholder="e.g. Confirmed with patient, updated chart..."
                          className="flex-1 text-xs border border-amber-200 rounded px-2.5 py-1.5 bg-white text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                        <Button
                          size="sm"
                          onClick={() => handleResolve(item.id)}
                          disabled={resolvingId === item.id}
                        >
                          {resolvingId === item.id ? 'Saving…' : 'Confirm Resolution'}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Navigation Footer */}
      <div className="pt-2 flex justify-between items-center">
        <Button onClick={onGoBackToSoap} size="sm" variant="secondary">
          ← Back to SOAP Draft
        </Button>
        <Button onClick={onProceedToRecord} size="sm">
          Next: Doctor Review & Approval →
        </Button>
      </div>
    </div>
  );
}


function InlineVerifiedText({ text, section, activeSection, setActiveSection }: {
  text: string; section: string; activeSection: string | null; setActiveSection: (s: string | null) => void;
}) {
  const claims = VERIFICATION_CLAIMS.filter(c => c.section === section);

  const getClaimAtText = (fragment: string) => {
    return claims.find(c =>
      fragment.toLowerCase().includes(c.claim.toLowerCase().split(' ').slice(0, 3).join(' ').toLowerCase())
    );
  };

  const words = text.split(/(\s+)/);
  let highlighted = false;

  return (
    <div className="text-sm text-slate-700 leading-relaxed">
      {text.split('. ').map((sentence, si) => {
        const claim = getClaimAtText(sentence);
        if (claim && !highlighted) {
          highlighted = true;
          return (
            <span key={si}>
              <span
                className={`claim-highlight claim-${claim.status} rounded-sm px-0.5 cursor-pointer`}
                title={`${claim.status.charAt(0).toUpperCase() + claim.status.slice(1)}: ${claim.evidence}`}
                onClick={() => setActiveSection(activeSection === claim.id ? null : claim.id)}
              >
                {sentence}
              </span>
              {si < text.split('. ').length - 1 ? '. ' : ''}
            </span>
          );
        }
        return <span key={si}>{sentence}{si < text.split('. ').length - 1 ? '. ' : ''}</span>;
      })}
    </div>
  );
}

function VerificationPanel({ supported, unsupported, ambiguous }: { supported: number; unsupported: number; ambiguous: number }) {
  const [reviewedIds, setReviewedIds] = useState<string[]>([]);
  const toggleReviewed = (id: string) => setReviewedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  return (
    <div className="bg-white border border-slate-100 rounded-xl shadow-sm overflow-hidden sticky top-0">
      <div className="p-4 border-b border-slate-100">
        <div className="font-semibold text-slate-800 mb-3" style={{ fontFamily: 'DM Sans, sans-serif' }}>
          Verification Results
        </div>
        <div className="flex gap-2 text-xs">
          <span className="px-2 py-1 bg-green-50 text-green-700 border border-green-200 rounded font-mono">✓ {supported} supported</span>
          <span className="px-2 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded font-mono">~ {ambiguous} ambiguous</span>
          <span className="px-2 py-1 bg-red-50 text-red-700 border border-red-200 rounded font-mono">✕ {unsupported} unsupported</span>
        </div>
      </div>

      <div className="max-h-[65vh] overflow-y-auto divide-y divide-slate-50">
        {VERIFICATION_CLAIMS.map(claim => (
          <div key={claim.id} className={`p-4 ${claim.status === 'unsupported' ? 'bg-red-50/30' : claim.status === 'ambiguous' ? 'bg-amber-50/30' : ''}`}>
            <div className="flex items-start justify-between gap-2 mb-2">
              <p className="text-xs font-medium text-slate-800 leading-snug">{claim.claim}</p>
              <VerifBadge status={claim.status as 'supported' | 'unsupported' | 'ambiguous'} />
            </div>
            <blockquote className="text-xs text-slate-500 italic border-l-2 border-slate-200 pl-2 leading-relaxed mb-2">
              {claim.evidence}
            </blockquote>
            {claim.status === 'unsupported' && (
              <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1 mb-2">
                ⚠ No transcript evidence. Verify before approving.
              </div>
            )}
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-slate-500 hover:text-slate-700">
              <input type="checkbox"
                checked={reviewedIds.includes(claim.id)}
                onChange={() => toggleReviewed(claim.id)}
                className="w-3.5 h-3.5 accent-blue-600"
              />
              Mark as reviewed
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConflictsContent() {
  return (
    <div className="mt-4 space-y-3">
      {CONFLICTS.map(c => (
        <div key={c.id} className="bg-white rounded-lg border border-amber-100 overflow-hidden">
          <div className="px-4 py-2 bg-amber-50/50 border-b border-amber-100">
            <span className="text-xs font-semibold text-amber-800 font-mono-label uppercase">{c.field}</span>
          </div>
          <div className="grid grid-cols-2 divide-x divide-amber-100">
            <div className="p-3">
              <div className="text-xs text-slate-400 font-mono-label mb-1">Patient Intake</div>
              <p className="text-xs text-slate-700 leading-relaxed">{c.intakeValue}</p>
            </div>
            <div className="p-3">
              <div className="text-xs text-slate-400 font-mono-label mb-1">Consultation Record</div>
              <p className="text-xs text-slate-700 leading-relaxed">{c.consultationValue}</p>
            </div>
          </div>
          {c.resolution && (
            <div className="px-4 py-2 bg-green-50 border-t border-green-100">
              <div className="flex items-start gap-1.5 text-xs text-green-800">
                <span>✓</span>
                <span>{c.resolution}</span>
              </div>
            </div>
          )}
          {!c.resolution && c.severity === 'info' && (
            <div className="px-4 py-2 bg-blue-50 border-t border-blue-100">
              <div className="flex gap-2">
                <button className="text-xs text-blue-700 font-medium hover:underline">Confirm Resolution</button>
                <button className="text-xs text-red-600 font-medium hover:underline">Escalate</button>
              </div>
            </div>
          )}
        </div>
      ))}
      <div className="flex items-center gap-1.5 text-xs text-green-700">
        <span>✓</span> No further conflicts detected
      </div>
    </div>
  );
}

// ── Record Tab ────────────────────────────────────────────────────────────────
interface RecordTabProps {
  approved: boolean;
  onApprove: () => void;
  consultation: ConsultationResponse | null;
  doctorData: DoctorIntakeSummaryResponse | null;
  visits: ConsultationResponse[];
  patient: PatientDemographics;
}

function RecordTab({
  approved,
  onApprove,
  consultation,
  doctorData,
  visits,
  patient,
}: RecordTabProps) {
  const [checklist, setChecklist] = useState({
    soap: true,
    verification: true,
    conflicts: true,
    allergy: true,
    prescription: false,
  });
  const [recordTab, setRecordTab] = useState('overview');
  const allChecked = Object.values(checklist).every(Boolean);

  const toggle = (key: keyof typeof checklist) => {
    setChecklist(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const isSarahDemo = patient.mrn === 'MRN-2026-0091' && (!consultation || consultation.patient_id === 'sarah-demo-id');
  const claims = consultation?.verification_results?.claims && consultation.verification_results.claims.length > 0
    ? consultation.verification_results.claims
    : (isSarahDemo ? VERIFICATION_CLAIMS : []);

  const compItems = consultation?.comparison_results?.items && consultation.comparison_results.items.length > 0
    ? consultation.comparison_results.items
    : (isSarahDemo ? CONFLICTS : []);

  const confirmedAllergies = useMemo(() => {
    const list: { substance: string; reaction: string; source: 'patient-reported' | 'doctor-confirmed'; firstSeen?: string }[] = [];
    if (consultation?.extracted_clinical_data?.allergies) {
      for (const a of consultation.extracted_clinical_data.allergies) {
        if (isClinicalAllergy(a.substance)) {
          list.push({
            substance: a.substance,
            reaction: a.reaction || 'Explicitly reported allergy',
            source: 'doctor-confirmed',
            firstSeen: formatVisitDate(consultation.created_at),
          });
        }
      }
    }
    if (doctorData?.summary?.allergies && isClinicalAllergy(doctorData.summary.allergies)) {
      if (!list.some(x => x.substance.toLowerCase() === doctorData.summary.allergies.toLowerCase())) {
        list.push({
          substance: doctorData.summary.allergies,
          reaction: doctorData.summary.allergies,
          source: 'patient-reported',
          firstSeen: formatVisitDate(doctorData.summary.submitted_at),
        });
      }
    }
    return list;
  }, [consultation, doctorData]);

  const isDoctorPrescribed = (medName: string): boolean => {
    if (!consultation) return false;
    const lower = medName.toLowerCase();

    // Check extracted clinical data plan
    if (consultation.extracted_clinical_data?.plan && consultation.extracted_clinical_data.plan.length > 0) {
      const inPlan = consultation.extracted_clinical_data.plan.some(p => {
        const lp = p.toLowerCase();
        return lp.includes(lower) && (lp.includes('prescrib') || lp.includes('start') || lp.includes('take') || lp.includes('rx') || lp.includes('give') || lp.includes('administer') || lp.includes('order'));
      });
      if (inPlan) return true;
    }

    // Check SOAP draft plan
    const soapPlan = consultation.soap_draft?.plan?.toLowerCase() || '';
    if (soapPlan && !soapPlan.startsWith('not documented')) {
      if (soapPlan.includes(lower) && (soapPlan.includes('prescrib') || soapPlan.includes('start') || soapPlan.includes('take') || soapPlan.includes('rx') || soapPlan.includes('order'))) {
        return true;
      }
    }

    // Check finalized record plan
    const finalPlan = consultation.final_record?.soap?.plan?.toLowerCase() || '';
    if (finalPlan && !finalPlan.startsWith('not documented')) {
      if (finalPlan.includes(lower) && (finalPlan.includes('prescrib') || finalPlan.includes('start') || finalPlan.includes('take') || finalPlan.includes('rx') || finalPlan.includes('order'))) {
        return true;
      }
    }

    return false;
  };

  const { activePrescriptions, patientReportedMeds } = useMemo(() => {
    const rxList: { drug: string; date: string; status: string; source: 'doctor-confirmed' }[] = [];
    const patientMedsList: { drug: string; date: string; status: string; source: 'patient-reported' }[] = [];

    if (consultation?.extracted_clinical_data?.medications) {
      for (const m of consultation.extracted_clinical_data.medications) {
        const drug = `${m.name} ${m.dose || ''} ${m.frequency || ''}`.trim();
        const date = formatVisitDate(consultation.created_at);
        const status = m.status || 'Active';
        if (isDoctorPrescribed(m.name)) {
          rxList.push({ drug, date, status, source: 'doctor-confirmed' });
        } else {
          patientMedsList.push({ drug, date, status, source: 'patient-reported' });
        }
      }
    }

    return { activePrescriptions: rxList, patientReportedMeds: patientMedsList };
  }, [consultation]);

  const problemList = useMemo(() => {
    const list: { problem: string; date: string; source: 'doctor-confirmed' | 'patient-reported' }[] = [];
    if (consultation?.extracted_clinical_data?.diagnoses) {
      for (const d of consultation.extracted_clinical_data.diagnoses) {
        list.push({
          problem: d,
          date: formatVisitDate(consultation.created_at),
          source: 'doctor-confirmed',
        });
      }
    }
    if (list.length === 0 && consultation?.final_record?.soap?.assessment && consultation.final_record.soap.assessment !== 'Not explicitly documented.') {
      list.push({
        problem: consultation.final_record.soap.assessment,
        date: formatVisitDate(consultation.final_record.approved_at),
        source: 'doctor-confirmed',
      });
    }
    if (list.length === 0 && doctorData?.summary?.chief_complaint) {
      list.push({
        problem: doctorData.summary.chief_complaint,
        date: formatVisitDate(doctorData.summary.submitted_at),
        source: 'patient-reported',
      });
    }
    return list;
  }, [consultation, doctorData]);

  const isCurrentVisitFinalized = Boolean(approved || consultation?.final_record || consultation?.status === 'completed');

  const longitudinalData = useMemo(() => {
    const allergiesSet = new Set<string>();
    const diagnosesSet = new Set<string>();
    const symptomsSet = new Set<string>();

    for (const v of visits) {
      // Only include visits that are finalized/completed, or current visit if approved/finalized
      const isFinal = (v.status === 'completed' || Boolean(v.final_record)) || (v.id === consultation?.id && isCurrentVisitFinalized);
      if (isFinal && v.extracted_clinical_data) {
        v.extracted_clinical_data.allergies?.forEach(a => allergiesSet.add(a.substance + (a.reaction ? ` (${a.reaction})` : '')));
        v.extracted_clinical_data.diagnoses?.forEach(d => diagnosesSet.add(d));
        v.extracted_clinical_data.symptoms?.forEach(s => symptomsSet.add(s.name));
      }
    }

    const result = [];
    if (allergiesSet.size > 0) {
      result.push({
        category: 'Allergies',
        facts: Array.from(allergiesSet).map(f => ({ fact: f, sources: ['doctor-confirmed'] as const, date: 'Documented across visits' }))
      });
    }
    if (diagnosesSet.size > 0) {
      result.push({
        category: 'Diagnoses',
        facts: Array.from(diagnosesSet).map(f => ({ fact: f, sources: ['doctor-confirmed'] as const, date: 'Documented across visits' }))
      });
    }
    if (symptomsSet.size > 0) {
      result.push({
        category: 'Reported Symptoms',
        facts: Array.from(symptomsSet).map(f => ({ fact: f, sources: ['patient-reported'] as const, date: 'Documented across visits' }))
      });
    }
    return result;
  }, [visits, consultation, isCurrentVisitFinalized]);

  const pendingCurrentVisitData = useMemo(() => {
    if (isCurrentVisitFinalized || !consultation?.extracted_clinical_data) return [];
    const allergies = (consultation.extracted_clinical_data.allergies || [])
      .filter(a => isClinicalAllergy(a.substance))
      .map(a => ({
        fact: a.substance + (a.reaction ? ` (${a.reaction})` : ''),
        sources: ['ai-generated'] as const,
        date: 'Current Visit · Pending Final Approval',
      }));

    const diagnoses = (consultation.extracted_clinical_data.diagnoses || []).map(d => ({
      fact: d,
      sources: ['ai-generated'] as const,
      date: 'Current Visit · Pending Final Approval',
    }));

    const symptoms = (consultation.extracted_clinical_data.symptoms || []).map(s => ({
      fact: s.name,
      sources: ['patient-reported'] as const,
      date: 'Current Visit · Pending Final Approval',
    }));

    const list = [];
    if (allergies.length > 0) list.push({ category: 'Allergies (Current Visit Draft)', facts: allergies });
    if (diagnoses.length > 0) list.push({ category: 'Diagnoses (Current Visit Draft)', facts: diagnoses });
    if (symptoms.length > 0) list.push({ category: 'Reported Symptoms (Current Visit)', facts: symptoms });
    return list;
  }, [consultation, isCurrentVisitFinalized]);

  const approvalTimestamp = consultation?.finalized_at
    ? formatVisitDate(consultation.finalized_at)
    : consultation?.updated_at ? formatVisitDate(consultation.updated_at) : 'Today';

  const activeSoap = consultation?.final_record?.soap || consultation?.soap_draft;

  return (
    <div className="flex gap-6 max-w-5xl">
      {/* Record content */}
      <div className="flex-1 space-y-4">
        {!approved && (
          <AINotice message="Review the complete record before approving. AI Draft ≠ Verified Draft ≠ Doctor-Approved Final Record. By approving, you confirm this record is clinically accurate and take full professional responsibility for its contents." />
        )}

        {approved && (
          <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-xl px-5 py-4 shadow-xs">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-700 font-bold text-base">✓</div>
              <div>
                <div className="text-sm font-bold text-green-900 font-sans">
                  Doctor-Approved · Final Medical Record
                </div>
                <div className="text-xs text-green-700 mt-0.5">
                  Approved by {consultation?.final_record?.doctor_name || 'Dr. J. Patel'} on {approvalTimestamp} · Provenance: doctor-approved-final-record
                </div>
              </div>
            </div>
            <span className="px-2.5 py-1 bg-green-600 text-white rounded text-xs font-semibold font-mono tracking-wide uppercase">
              Final Record
            </span>
          </div>
        )}

        {/* Record tabs */}
        <div className="flex gap-1 p-1 bg-slate-100 rounded-lg w-fit text-sm">
          {['overview', 'SOAP Note', 'Verification', 'Discrepancies', 'Longitudinal'].map(t => (
            <button
              key={t}
              onClick={() => setRecordTab(t.toLowerCase())}
              className={`px-3 py-1.5 rounded-md font-medium transition-all capitalize cursor-pointer ${
                recordTab === t.toLowerCase() ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {recordTab === 'overview' && (
          <div className="space-y-4">
            {/* Allergy */}
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <SectionLabel>Confirmed Allergies</SectionLabel>
                {confirmedAllergies.length > 0 && <AllergyTag substance="!" />}
              </div>
              {confirmedAllergies.length === 0 ? (
                <div className="text-sm text-slate-500 italic py-1">
                  No confirmed allergies documented for this patient.
                </div>
              ) : (
                <div className="space-y-3">
                  {confirmedAllergies.map(a => (
                    <div key={a.substance} className="flex items-start gap-3">
                      <AllergyTag substance={a.substance} />
                      <div className="text-sm text-slate-700">
                        <div className="font-medium">{a.substance} — {a.reaction}</div>
                        <div className="flex gap-2 mt-1 flex-wrap items-center">
                          <SourceBadge type={a.source} />
                          {a.firstSeen && (
                            <span className="text-xs text-slate-400 font-mono-label">Documented: {a.firstSeen}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Active prescriptions */}
            <Card className="p-4">
              <SectionLabel>Active Prescriptions</SectionLabel>
              {activePrescriptions.length === 0 ? (
                <div className="text-sm text-slate-500 italic py-1">
                  No active prescriptions documented for this visit.
                </div>
              ) : (
                <div className="space-y-3">
                  {activePrescriptions.map(rx => (
                    <div key={rx.drug} className="flex items-start justify-between py-2 border-b border-slate-50 last:border-0">
                      <div>
                        <div className="text-sm font-medium text-slate-800">{rx.drug}</div>
                        <div className="flex gap-2 mt-1 items-center">
                          <SourceBadge type={rx.source} />
                          <span className="text-xs text-slate-400 font-mono-label">Prescribed {rx.date}</span>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded text-xs font-medium">{rx.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Current / home medications */}
            {patientReportedMeds.length > 0 && (
              <Card className="p-4">
                <SectionLabel>Current / Home Medications</SectionLabel>
                <div className="space-y-3">
                  {patientReportedMeds.map(rx => (
                    <div key={rx.drug} className="flex items-start justify-between py-2 border-b border-slate-50 last:border-0">
                      <div>
                        <div className="text-sm font-medium text-slate-800">{rx.drug}</div>
                        <div className="flex gap-2 mt-1 items-center">
                          <SourceBadge type={rx.source} />
                          <span className="text-xs text-slate-400 font-mono-label">Reported by patient</span>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 bg-slate-100 text-slate-700 border border-slate-200 rounded text-xs font-medium">{rx.status}</span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Problem list */}
            <Card className="p-4">
              <SectionLabel>Problem List</SectionLabel>
              {problemList.length === 0 ? (
                <div className="text-sm text-slate-500 italic py-1">
                  No clinical diagnoses documented yet.
                </div>
              ) : (
                <div className="space-y-2">
                  {problemList.map(p => (
                    <div key={p.problem} className="flex items-start justify-between py-2">
                      <div>
                        <div className="text-sm font-medium text-slate-800">{p.problem}</div>
                        <div className="flex gap-2 mt-1 items-center flex-wrap">
                          <SourceBadge type={p.source} />
                          <span className="text-xs text-slate-400 font-mono-label">{p.date}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Visit summary table */}
            <Card className="overflow-hidden">
              <div className="p-4 border-b border-slate-50">
                <SectionLabel>Visit History</SectionLabel>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-50">
                    {['Date', 'Complaint', 'Diagnosis', 'Doctor', 'Status'].map(h => (
                      <th key={h} className="text-left px-4 py-2 text-xs text-slate-400 font-mono-label uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-sm">
                  {visits.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-4 text-center text-slate-400 italic text-xs">
                        No previous visits on record.
                      </td>
                    </tr>
                  ) : (
                    visits.map((v) => (
                      <tr key={v.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3 text-slate-500 font-mono-label text-xs">{formatVisitDate(v.created_at)}</td>
                        <td className="px-4 py-3 text-slate-700">{v.chief_complaint || 'General Consultation'}</td>
                        <td className="px-4 py-3 text-slate-800 font-medium">
                          {v.soap_draft?.assessment || (v.extracted_clinical_data?.diagnoses?.join(', ') || 'Pending')}
                        </td>
                        <td className="px-4 py-3 text-slate-500 text-xs">Dr. J. Patel</td>
                        <td className="px-4 py-3">
                          {v.status === 'in-progress'
                            ? <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs font-medium">Active</span>
                            : <span className="px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded text-xs font-medium">Finalized</span>
                          }
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {recordTab === 'soap note' && (
          <Card className="p-6 space-y-4">
            <AINotice message={approved ? "This is the doctor-approved final medical record for this visit." : "Review this SOAP note before signing. Approved status will seal this visit record."} />
            {activeSoap ? (
              [
                { label: 'Subjective', content: activeSoap.subjective },
                { label: 'Objective', content: activeSoap.objective },
                { label: 'Assessment', content: activeSoap.assessment },
                { label: 'Plan', content: activeSoap.plan },
              ].map(s => (
                <div key={s.label}>
                  <div className="text-xs font-bold text-slate-400 font-mono-label uppercase mb-1">{s.label}</div>
                  <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{s.content || 'Not documented.'}</p>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-500 italic p-6 text-center">
                No SOAP note draft generated for this visit yet. Generate a draft in the SOAP Note tab.
              </div>
            )}
          </Card>
        )}

        {recordTab === 'verification' && (
          <div className="space-y-3">
            <div className="flex gap-3">
              <span className="px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded text-sm font-mono">
                ✓ {claims.filter(c => c.status === 'supported').length} Supported
              </span>
              <span className="px-3 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-sm font-mono">
                ~ {claims.filter(c => c.status === 'ambiguous').length} Ambiguous
              </span>
              <span className="px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded text-sm font-mono">
                ✕ {claims.filter(c => c.status === 'unsupported').length} Unsupported
              </span>
            </div>
            {claims.length > 0 ? (
              <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-[60vh] overflow-y-auto">
                {claims.map(claim => (
                  <div key={claim.id} className="p-4 space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-slate-800">{claim.claim}</p>
                      <VerifBadge status={claim.status as 'supported' | 'unsupported' | 'ambiguous'} />
                    </div>
                    <blockquote className="text-xs text-slate-500 italic border-l-2 border-slate-200 pl-2 leading-relaxed">
                      {claim.evidence}
                    </blockquote>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white border border-slate-100 rounded-xl p-8 text-center text-sm text-slate-500 italic shadow-xs">
                No claim-level verification items generated for this visit yet. Run Agent 3 in the Verification tab.
              </div>
            )}
          </div>
        )}

        {recordTab === 'discrepancies' && (
          <div className="space-y-3">
            {compItems.length > 0 ? (
              <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-[60vh] overflow-y-auto p-4 space-y-3">
                {compItems.map(item => (
                  <div key={item.id} className="p-3 bg-slate-50/60 rounded-lg border border-slate-200 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800 font-mono-label">
                        {'label' in item ? (item as any).label : (item as any).field || 'Clinical Finding'}
                      </span>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                        {'type' in item ? item.type : ('severity' in item ? (item as any).severity : 'info')}
                      </span>
                    </div>
                    <div className="text-xs text-slate-700">
                      <strong>Intake:</strong> {'intake_value' in item ? item.intake_value : (item as any).intakeValue}
                    </div>
                    <div className="text-xs text-slate-700">
                      <strong>Consultation:</strong> {'consultation_value' in item ? item.consultation_value : (item as any).consultationValue}
                    </div>
                    {item.resolution && (
                      <div className="text-xs text-green-800 bg-green-50 rounded px-2 py-1 border border-green-200">
                        ✓ Resolution: {item.resolution}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white border border-slate-100 rounded-xl p-8 text-center text-sm text-slate-500 italic shadow-xs">
                No comparison items available yet. Run Agent 4 in the Verification tab.
              </div>
            )}
          </div>
        )}


        {recordTab === 'longitudinal' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500">Source-annotated longitudinal view of confirmed facts across all visits for this patient.</p>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-medium border ${
                isCurrentVisitFinalized
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}>
                {isCurrentVisitFinalized ? 'Doctor-Approved Final Record' : 'Active Consultation · Draft State'}
              </span>
            </div>

            {!isCurrentVisitFinalized && (
              <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                <span>ℹ</span>
                <span>
                  <strong>Pre-Approval Notice:</strong> Longitudinal clinical history is permanently committed only upon doctor approval. Findings from the active consultation are shown below as pending drafts.
                </span>
              </div>
            )}

            {longitudinalData.length === 0 ? (
              <div className="bg-white border border-slate-100 rounded-xl p-8 text-center text-sm text-slate-500 italic shadow-xs">
                No finalized longitudinal clinical history recorded yet across visits.
              </div>
            ) : (
              longitudinalData.map(cat => (
                <Card key={cat.category} className="overflow-hidden">
                  <div className="px-4 py-3 bg-slate-50 border-b border-slate-100">
                    <SectionLabel>{cat.category}</SectionLabel>
                  </div>
                  <div className="divide-y divide-slate-50">
                    {cat.facts.map(f => (
                      <div key={f.fact} className="p-4">
                        <div className="text-sm font-medium text-slate-800 mb-1">{f.fact}</div>
                        <div className="flex gap-1.5 flex-wrap mb-1">
                          {f.sources.map(s => <SourceBadge key={s} type={s} />)}
                        </div>
                        <div className="text-xs text-slate-400 font-mono-label">{f.date}</div>
                      </div>
                    ))}
                  </div>
                </Card>
              ))
            )}

            {!isCurrentVisitFinalized && pendingCurrentVisitData.length > 0 && (
              <div className="pt-2 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider font-mono-label">
                    Current Visit Findings (Pending Doctor Approval)
                  </span>
                  <span className="px-1.5 py-0.2 bg-amber-100 text-amber-800 rounded font-mono text-[10px] font-semibold">
                    Unfinalized
                  </span>
                </div>
                {pendingCurrentVisitData.map(cat => (
                  <Card key={cat.category} className="overflow-hidden border-dashed border-amber-200 bg-amber-50/10">
                    <div className="px-4 py-2.5 bg-amber-50/40 border-b border-amber-100">
                      <SectionLabel>{cat.category}</SectionLabel>
                    </div>
                    <div className="divide-y divide-amber-100/50">
                      {cat.facts.map(f => (
                        <div key={f.fact} className="p-3.5">
                          <div className="text-sm font-medium text-slate-800 mb-1">{f.fact}</div>
                          <div className="flex gap-1.5 flex-wrap mb-1">
                            {f.sources.map(s => <SourceBadge key={s} type={s} />)}
                          </div>
                          <div className="text-xs text-amber-700/80 font-mono-label">{f.date}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Approval checklist */}
      {!isCurrentVisitFinalized && (
        <div className="w-64 flex-shrink-0">
          <div className="bg-white border border-slate-100 rounded-xl shadow-sm p-4 sticky top-0">
            <div className="font-semibold text-slate-800 mb-4" style={{ fontFamily: 'DM Sans, sans-serif' }}>Approval Checklist</div>
            <div className="space-y-2.5 mb-5">
              {[
                { key: 'soap', label: 'SOAP note reviewed' },
                { key: 'verification', label: 'Verification results reviewed' },
                { key: 'conflicts', label: 'Conflicts resolved' },
                { key: 'allergy', label: 'Allergy documented' },
                {
                  key: 'prescription',
                  label: activePrescriptions.length > 0
                    ? 'Prescription confirmed'
                    : 'Medication review confirmed (no new prescription)',
                },
              ].map(item => (
                <label key={item.key} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checklist[item.key as keyof typeof checklist]}
                    onChange={() => toggle(item.key as keyof typeof checklist)}
                    className="w-4 h-4 accent-blue-600"
                  />
                  <span className={`text-sm ${checklist[item.key as keyof typeof checklist] ? 'text-slate-500 line-through' : 'text-slate-700'}`}>
                    {item.label}
                  </span>
                </label>
              ))}
            </div>

            {!allChecked && (
              <div className="text-xs text-slate-400 mb-3 text-center">
                Complete all items to approve
              </div>
            )}

            {allChecked && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3 leading-relaxed">
                By approving, you confirm this record is clinically accurate and take responsibility for its contents.
              </div>
            )}

            <Button
              onClick={onApprove}
              disabled={!allChecked}
              className="w-full"
              size="md"
            >
              {allChecked ? '✓ Approve & Save Record' : 'Complete checklist to approve'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

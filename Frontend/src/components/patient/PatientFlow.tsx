import { useState } from 'react';
import { ProgressSteps, Button, Input, Textarea, SymptomTag, Card } from '../ui';
import { api } from '../../services/api';
import type { IntakeSubmitResponse } from '../../types/intake';
import { LOCALIZATION, type PatientLang } from '../../constants/patientLocalization';

type Screen = 'welcome' | 'step1' | 'step2' | 'step3' | 'confirm';

const COMPLAINT_OPTIONS = ['Cough', 'Fever', 'Sore Throat', 'Stomach Pain', 'Headache', 'Chest Pain', 'Dizziness', 'Other'];

const ADAPTIVE_QUESTIONS: Record<string, { label: string; options: string[] }[]> = {
  Fever: [
    { label: 'Did the fever start gradually or suddenly?', options: ['Gradually', 'Suddenly', "I'm not sure"] },
    { label: 'Have you measured your temperature?', options: ['Yes, above 38°C', 'Yes, below 38°C', "No, I haven't measured"] },
  ],
  'Sore Throat': [
    { label: 'Is it painful to swallow?', options: ['Yes, very painful', 'Mildly uncomfortable', 'No'] },
    { label: 'Have you noticed any white patches on your throat?', options: ['Yes', 'No', "I haven't looked"] },
  ],
  Cough: [
    { label: 'Is your cough dry or producing mucus?', options: ['Dry', 'Producing mucus', 'Both'] },
    { label: 'How long have you been coughing?', options: ['Less than 3 days', '3–7 days', 'More than a week'] },
  ],
  'Stomach Pain': [
    { label: 'Where is the pain located?', options: ['Upper abdomen', 'Lower abdomen', 'All over'] },
    { label: 'Is the pain constant or comes and goes?', options: ['Constant', 'Comes and goes', 'Only after eating'] },
  ],
  Headache: [
    { label: 'Where do you feel the headache?', options: ['Forehead', 'Behind eyes', 'Back of head', 'One side only'] },
    { label: 'Is the headache accompanied by nausea or light sensitivity?', options: ['Yes', 'No', 'Only nausea'] },
  ],
  'Chest Pain': [
    { label: 'Where in your chest do you feel the pain?', options: ['Center', 'Left side', 'Right side', 'All over'] },
    { label: 'Does the pain worsen with breathing or movement?', options: ['Yes, with breathing', 'Yes, with movement', 'No, it is constant'] },
  ],
  Dizziness: [
    { label: 'Does the room seem to spin, or do you feel lightheaded?', options: ['Room spins (vertigo)', 'Lightheaded / faint', 'Both'] },
    { label: 'Does the dizziness happen when you change position?', options: ['Yes', 'No', 'Sometimes'] },
  ],
};

const SHARED_SYMPTOMS: { id: string; label: string }[] = [
  { id: 'diff_swallow', label: 'Difficulty swallowing' },
  { id: 'ear_pain', label: 'Ear pain' },
  { id: 'runny_nose', label: 'Runny nose' },
  { id: 'chills', label: 'Chills' },
  { id: 'rash', label: 'Rash' },
  { id: 'nausea', label: 'Nausea' },
  { id: 'fatigue', label: 'Fatigue' },
  { id: 'loss_appetite', label: 'Loss of appetite' },
];

const CONDITIONS = ['Diabetes', 'High blood pressure', 'Asthma', 'Heart disease', 'Thyroid condition', 'Kidney disease', 'None of the above'];

const CONDITION_FOLLOWUPS: Record<string, { label: string; options: string[] }[]> = {
  Diabetes: [
    { label: 'What type of diabetes do you have?', options: ['Type 1', 'Type 2', 'Gestational', 'Not sure'] },
    { label: 'Are you currently taking medication or insulin?', options: ['Insulin', 'Oral medication', 'Both', 'Neither'] },
  ],
  'High blood pressure': [
    { label: 'Are you currently taking blood pressure medication?', options: ['Yes', 'No', 'Not sure'] },
    { label: 'When was your last blood pressure reading taken?', options: ['Within the last week', 'Within the last month', 'More than a month ago'] },
  ],
  Asthma: [
    { label: 'How often do you use your inhaler?', options: ['Daily', 'A few times a week', 'Rarely / emergency only'] },
    { label: 'Have you had any recent asthma flare-ups?', options: ['Yes, within the last week', 'Yes, within the last month', 'No recent flare-ups'] },
  ],
  'Heart disease': [
    { label: 'What type of heart condition do you have?', options: ['Coronary artery disease', 'Heart failure', 'Arrhythmia', 'Other / not sure'] },
    { label: 'Are you currently taking prescribed heart medication?', options: ['Yes', 'No'] },
  ],
  'Thyroid condition': [
    { label: 'Is your thyroid condition overactive or underactive?', options: ['Overactive (Hyperthyroid)', 'Underactive (Hypothyroid)', 'Not sure'] },
    { label: 'Are you currently taking thyroid medication?', options: ['Yes', 'No'] },
  ],
  'Kidney disease': [
    { label: 'Are you currently on dialysis?', options: ['Yes', 'No'] },
    { label: 'Do you have dietary or fluid restrictions for kidney health?', options: ['Yes', 'No', 'Not sure'] },
  ],
};

export interface ReturningPatient {
  id: string;
  mrn?: string;
  name: string;
  dob?: string;
  phone?: string;
}

interface PatientFlowProps {
  onComplete: (patientId?: string, sessionId?: string) => void;
  initialPatient?: ReturningPatient;
}

function formatOrdinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function LanguageSelector({
  lang,
  onChange,
}: {
  lang: PatientLang;
  onChange: (l: PatientLang) => void;
}) {
  return (
    <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 text-xs shadow-2xs">
      {(['en', 'hi', 'hinglish'] as const).map(l => (
        <button
          key={l}
          type="button"
          onClick={() => onChange(l)}
          className={`px-2 py-0.5 rounded transition-all font-medium ${lang === l
              ? 'bg-blue-600 text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900'
            }`}
        >
          {l === 'en' ? 'EN' : l === 'hi' ? 'हिंदी' : 'Hinglish'}
        </button>
      ))}
    </div>
  );
}

export default function PatientFlow({ onComplete, initialPatient }: PatientFlowProps) {
  const [screen, setScreen] = useState<Screen>('welcome');
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [submissionResult, setSubmissionResult] = useState<IntakeSubmitResponse | null>(null);

  // Step 1: Pre-fill demographics only if returning patient
  const [name, setName] = useState(initialPatient?.name || '');
  const [dob, setDob] = useState(initialPatient?.dob || '');
  const [phone, setPhone] = useState(initialPatient?.phone || '');
  const [nameError, setNameError] = useState('');
  const [dobError, setDobError] = useState('');
  const [phoneError, setPhoneError] = useState('');

  // Step 2: Symptoms start completely fresh for new visits
  const [selectedComplaints, setSelectedComplaints] = useState<string[]>(
    initialPatient ? [] : ['Fever', 'Sore Throat']
  );
  const [otherSymptomText, setOtherSymptomText] = useState('');
  const [duration, setDuration] = useState('3–5 days');
  const [severity, setSeverity] = useState(6);
  const [additionalSymptoms, setAdditionalSymptoms] = useState<string[]>(
    initialPatient ? [] : ['diff_swallow', 'runny_nose', 'chills']
  );
  const [adaptiveAnswers, setAdaptiveAnswers] = useState<Record<string, string>>({});

  // Step 3: Medical history starts completely fresh for new visits
  const [conditions, setConditions] = useState<string[]>(['None of the above']);
  const [conditionAnswers, setConditionAnswers] = useState<Record<string, string>>({});
  const [medications, setMedications] = useState('');
  const [allergies, setAllergies] = useState('');
  const [notes, setNotes] = useState('');

  // Current date for HTML max constraint
  const todayStr = new Date().toISOString().split('T')[0];

  // Language state: English, Hindi, Hinglish
  const [lang, setLang] = useState<PatientLang>('en');
  const t = LOCALIZATION[lang];

  // Initialize session when flow starts
  const initSession = async () => {
    if (sessionToken) {
      setScreen('step1');
      return;
    }
    try {
      setIsInitializing(true);
      setApiError(null);
      const res = await api.createSession();
      setSessionToken(res.session_token);
      setScreen('step1');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to initialize intake session';
      setApiError(msg);
    } finally {
      setIsInitializing(false);
    }
  };

  const toggleComplaint = (c: string) => {
    setSelectedComplaints(prev => {
      if (prev.includes(c)) {
        // Deselected: clean up answers for this symptom
        setAdaptiveAnswers(current => {
          const next = { ...current };
          Object.keys(next).forEach(k => {
            if (k.startsWith(`${c}-`)) delete next[k];
          });
          return next;
        });
        if (c === 'Other') setOtherSymptomText('');
        return prev.filter(x => x !== c);
      } else {
        return [...prev, c];
      }
    });
  };

  const toggleSymptom = (id: string) => {
    setAdditionalSymptoms(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const toggleCondition = (c: string) => {
    if (c === 'None of the above') {
      setConditions(['None of the above']);
      setConditionAnswers({});
    } else {
      setConditions(prev => {
        const filtered = prev.filter(x => x !== 'None of the above');
        if (filtered.includes(c)) {
          // Deselected: remove associated condition answers
          setConditionAnswers(current => {
            const next = { ...current };
            Object.keys(next).forEach(k => {
              if (k.startsWith(`${c}-`)) delete next[k];
            });
            return next;
          });
          return filtered.filter(x => x !== c);
        } else {
          return [...filtered, c];
        }
      });
    }
  };

  // Build the effective complaint list, substituting 'Other' with typed text
  const getEffectiveComplaints = (): string[] => {
    return selectedComplaints.map(c =>
      c === 'Other' && otherSymptomText.trim() ? `Other: ${otherSymptomText.trim()}` : c
    );
  };

  // Build structured condition details map
  const getConditionDetailsMap = (): Record<string, Record<string, string>> => {
    const details: Record<string, Record<string, string>> = {};
    Object.entries(conditionAnswers).forEach(([k, ans]) => {
      const [cond, qidx] = k.split('-');
      const q = CONDITION_FOLLOWUPS[cond]?.[Number(qidx)];
      if (q && ans) {
        if (!details[cond]) {
          details[cond] = { provenance: 'patient-reported' };
        }
        let fieldKey = q.label;
        const idx = Number(qidx);
        if (cond === 'Diabetes') {
          fieldKey = idx === 0 ? 'type' : 'treatment';
        } else if (cond === 'High blood pressure') {
          fieldKey = idx === 0 ? 'medication' : 'last_reading';
        } else if (cond === 'Asthma') {
          fieldKey = idx === 0 ? 'inhaler_frequency' : 'recent_flare_up';
        } else if (cond === 'Heart disease') {
          fieldKey = idx === 0 ? 'condition_type' : 'medication';
        } else if (cond === 'Thyroid condition') {
          fieldKey = idx === 0 ? 'condition_type' : 'medication';
        } else if (cond === 'Kidney disease') {
          fieldKey = idx === 0 ? 'dialysis' : 'restrictions';
        }
        details[cond][fieldKey] = ans;
      }
    });
    return details;
  };

  // Structured summary list for displaying in the Review Card
  const getConditionDetailsSummaryList = (): { condition: string; summary: string }[] => {
    const map: Record<string, string[]> = {};
    Object.entries(conditionAnswers).forEach(([k, ans]) => {
      const [cond] = k.split('-');
      if (!map[cond]) map[cond] = [];
      map[cond].push(ans);
    });
    return Object.entries(map).map(([cond, answers]) => ({
      condition: cond,
      summary: answers.join('; '),
    }));
  };

  const handleStep1Next = () => {
    let hasError = false;

    if (!name.trim()) {
      setNameError(t.nameError);
      hasError = true;
    } else {
      setNameError('');
    }

    // Issue 1: Validate DOB - must not be in the future
    if (dob && dob.trim()) {
      const parsed = new Date(dob.trim());
      const today = new Date();
      today.setHours(23, 59, 59, 999);
      if (!isNaN(parsed.getTime()) && parsed > today) {
        setDobError('Date of birth cannot be in the future.');
        hasError = true;
      } else {
        setDobError('');
      }
    } else {
      setDobError('');
    }

    // Issue 2: Validate Phone - optional, but if provided must be 10-digit Indian mobile
    if (phone && phone.trim()) {
      const cleaned = phone.replace(/[\s\-()]/g, '');
      const normalized = cleaned.startsWith('+91')
        ? cleaned.slice(3)
        : cleaned.startsWith('91') && cleaned.length === 12
        ? cleaned.slice(2)
        : cleaned;
      if (!/^[6-9]\d{9}$/.test(normalized)) {
        setPhoneError('Phone number must be a valid 10-digit mobile number.');
        hasError = true;
      } else {
        setPhoneError('');
      }
    } else {
      setPhoneError('');
    }

    if (hasError) return;

    if (sessionToken) {
      api.saveDraft(sessionToken, {
        name: name.trim(),
        dob,
        phone,
        selected_complaints: getEffectiveComplaints(),
        duration,
        severity,
        additional_symptoms: additionalSymptoms,
        adaptive_answers: { ...adaptiveAnswers, ...conditionAnswers },
        conditions,
        condition_details: getConditionDetailsMap(),
        medications,
        allergies,
        additional_notes: notes.trim() || undefined,
      }).catch(console.error);
    }
    setScreen('step2');
  };

  const handleStep2Next = () => {
    if (selectedComplaints.length === 0) {
      setApiError(t.complaintError);
      return;
    }
    // Issue 3: If 'Other' selected, must provide symptom description
    if (selectedComplaints.includes('Other') && !otherSymptomText.trim()) {
      setApiError('Please describe your "Other" symptom.');
      return;
    }
    setApiError(null);
    if (sessionToken) {
      api.saveDraft(sessionToken, {
        name: name.trim(),
        dob,
        phone,
        selected_complaints: getEffectiveComplaints(),
        duration,
        severity,
        additional_symptoms: additionalSymptoms,
        adaptive_answers: { ...adaptiveAnswers, ...conditionAnswers },
        conditions,
        condition_details: getConditionDetailsMap(),
        medications,
        allergies,
        additional_notes: notes.trim() || undefined,
      }).catch(console.error);
    }
    setScreen('step3');
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setApiError(t.nameError);
      return;
    }
    if (selectedComplaints.length === 0) {
      setApiError(t.complaintError);
      return;
    }
    if (selectedComplaints.includes('Other') && !otherSymptomText.trim()) {
      setApiError('Please describe your "Other" symptom.');
      return;
    }

    try {
      setIsSubmitting(true);
      setApiError(null);

      // If no token exists yet, create one first
      let currentToken = sessionToken;
      if (!currentToken) {
        const sessionRes = await api.createSession();
        currentToken = sessionRes.session_token;
        setSessionToken(currentToken);
      }

      const res = await api.submitIntake(currentToken, {
        patient_id: initialPatient?.id,
        mrn: initialPatient?.mrn,
        name: name.trim(),
        dob: dob || undefined,
        phone: phone || undefined,
        selected_complaints: getEffectiveComplaints(),
        duration,
        severity,
        additional_symptoms: additionalSymptoms,
        adaptive_answers: { ...adaptiveAnswers, ...conditionAnswers },
        conditions,
        condition_details: getConditionDetailsMap(),
        medications: medications || 'None',
        allergies: allergies || 'None reported',
        additional_notes: notes.trim() || undefined,
      });

      setSubmissionResult(res);
      setScreen('confirm');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed. Please try again.';
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (screen === 'welcome') {
    return (
      <WelcomeScreen
        onStart={initSession}
        loading={isInitializing}
        error={apiError}
        lang={lang}
        onLangChange={setLang}
        patientName={initialPatient?.name}
      />
    );
  }

  if (screen === 'confirm') {
    return (
      <ConfirmScreen
        result={submissionResult}
        fallbackDetails={{
          complaint: selectedComplaints.map(c => t.complaintLabels[c] || c).join(', '),
          duration: t.durationOptions[duration] || duration,
          severity: `${severity}/10`,
          symptoms: SHARED_SYMPTOMS.filter(s => additionalSymptoms.includes(s.id)).map(s => t.symptomLabels[s.id] || s.label).join(', ') || t.reviewLabels.none,
          conditions: conditions.map(c => t.conditionLabels[c] || c).join(', '),
          medications: medications || t.reviewLabels.none,
          allergies: allergies || t.reviewLabels.none,
        }}
        lang={lang}
        onLangChange={setLang}
        onDoctorView={() => {
          onComplete(submissionResult?.patient_id, submissionResult?.session_token);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center py-8 px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">M</span>
            </div>
            <span className="font-semibold text-slate-700" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.medClinic}</span>
          </div>

          {/* Multilingual Selector: English, Hindi, Hinglish */}
          <LanguageSelector lang={lang} onChange={setLang} />
        </div>

        {apiError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center justify-between">
            <span>⚠️ {apiError}</span>
            <button onClick={() => setApiError(null)} className="text-red-500 font-bold ml-2">✕</button>
          </div>
        )}

        <ProgressSteps
          steps={t.progressSteps}
          current={screen === 'step1' ? 0 : screen === 'step2' ? 1 : 2}
        />

        {screen === 'step1' && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.detailsTitle}</h2>
            <p className="text-sm text-slate-500 mb-6">{t.detailsDesc}</p>
            <div className="flex flex-col gap-4">
              <Input label={t.fullNameLabel} placeholder={t.fullNamePlaceholder} value={name} onChange={setName} error={nameError} required />
              <Input label={t.dobLabel} type="date" value={dob} onChange={v => { setDob(v); setDobError(''); }} placeholder="" max={todayStr} error={dobError} />
              <Input label={t.phoneLabel} placeholder={t.phonePlaceholder} value={phone} onChange={v => { setPhone(v); setPhoneError(''); }} type="tel" error={phoneError} />
            </div>
            <div className="mt-6 flex justify-end">
              <Button onClick={handleStep1Next}>{t.continueBtn}</Button>
            </div>
            <p className="text-xs text-slate-400 mt-4 flex items-center gap-1.5">
              <span>🔒</span> {t.privateEncrypted}
            </p>
          </Card>
        )}

        {screen === 'step2' && (
          <div className="flex flex-col gap-4">
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.symptomsTitle}</h2>
              <p className="text-sm text-slate-500 mb-4">{t.symptomsDesc}</p>
              <div className="flex flex-wrap gap-2">
                {COMPLAINT_OPTIONS.map(c => (
                  <SymptomTag key={c} label={t.complaintLabels[c] || c} selected={selectedComplaints.includes(c)} onClick={() => toggleComplaint(c)} />
                ))}
              </div>
              {selectedComplaints.includes('Other') && (
                <div className="mt-3">
                  <Input
                    label="What else are you experiencing?"
                    placeholder="Describe your symptom (e.g. Body ache, weakness, rash)..."
                    value={otherSymptomText}
                    onChange={setOtherSymptomText}
                    required
                    onVoiceTranscribe={text => setOtherSymptomText(prev => (prev ? `${prev}, ${text}` : text))}
                    voiceLang={lang}
                  />
                </div>
              )}
            </Card>

            {/* General follow-ups */}
            <Card className="p-6">
              <div className="flex flex-col gap-5">
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">{t.durationQuestion}</p>
                  <div className="flex gap-2 flex-wrap">
                    {['1–2 days', '3–5 days', 'More than 5 days'].map(opt => (
                      <button
                        key={opt}
                        onClick={() => setDuration(opt)}
                        className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${duration === opt
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                          }`}
                      >
                        {t.durationOptions[opt] || opt}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">
                    {t.severityQuestion} <span className="text-blue-600 font-semibold">{severity}/10</span>
                  </p>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={severity}
                    onChange={e => setSeverity(Number(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                  <div className="flex justify-between text-xs text-slate-400 mt-1">
                    <span>{t.severityMild}</span><span>{t.severityMod}</span><span>{t.severitySev}</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Adaptive questions */}
            {selectedComplaints.filter(c => ADAPTIVE_QUESTIONS[c]).map(complaint => (
              <Card key={complaint} className="p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    {t.followUpPrefix} {t.complaintLabels[complaint] || complaint}
                  </span>
                </div>
                <div className="flex flex-col gap-4">
                  {ADAPTIVE_QUESTIONS[complaint].map((q, qi) => {
                    const localizedQ = t.adaptiveQuestions[complaint]?.[qi];
                    return (
                      <div key={qi}>
                        <p className="text-sm font-medium text-slate-700 mb-2">{localizedQ?.label || q.label}</p>
                        <div className="flex gap-2 flex-wrap">
                          {q.options.map(opt => {
                            const key = `${complaint}-${qi}`;
                            const localizedOpt = localizedQ?.options[opt] || opt;
                            return (
                              <button
                                key={opt}
                                onClick={() => setAdaptiveAnswers(prev => ({ ...prev, [key]: opt }))}
                                className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${adaptiveAnswers[key] === opt
                                    ? 'bg-blue-600 text-white border-blue-600'
                                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                                  }`}
                              >
                                {localizedOpt}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}

            <Card className="p-6">
              <p className="text-sm font-medium text-slate-700 mb-3">{t.additionalSymptomsQuestion}</p>
              <div className="grid grid-cols-2 gap-2">
                {SHARED_SYMPTOMS.map(s => (
                  <label key={s.id} className="flex items-center gap-2 cursor-pointer text-sm text-slate-700 hover:text-slate-900">
                    <input
                      type="checkbox"
                      checked={additionalSymptoms.includes(s.id)}
                      onChange={() => toggleSymptom(s.id)}
                      className="w-4 h-4 rounded accent-blue-600"
                    />
                    {t.symptomLabels[s.id] || s.label}
                  </label>
                ))}
              </div>
            </Card>

            <div className="flex gap-3 justify-between">
              <Button variant="secondary" onClick={() => setScreen('step1')}>{t.backBtn}</Button>
              <Button onClick={handleStep2Next}>{t.continueBtn}</Button>
            </div>
          </div>
        )}

        {screen === 'step3' && (
          <div className="flex flex-col gap-4">
            {/* Medical History */}
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.historyTitle}</h2>
              <p className="text-sm text-slate-500 mb-4">{t.historyDesc}</p>

              <div className="flex flex-col gap-5">
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">{t.conditionsQuestion}</p>
                  <div className="flex flex-col gap-2">
                    {CONDITIONS.map(c => (
                      <label key={c} className="flex items-center gap-2 cursor-pointer text-sm text-slate-700 hover:text-slate-900">
                        <input
                          type="checkbox"
                          checked={conditions.includes(c)}
                          onChange={() => toggleCondition(c)}
                          className="w-4 h-4 rounded accent-blue-600"
                        />
                        {t.conditionLabels[c] || c}
                      </label>
                    ))}
                  </div>
                </div>

                {/* Condition-specific structured follow-ups */}
                {conditions.filter(c => CONDITION_FOLLOWUPS[c]).map(condition => (
                  <div key={condition} className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        {condition} — Follow-up
                      </span>
                    </div>
                    <div className="flex flex-col gap-4">
                      {CONDITION_FOLLOWUPS[condition].map((q, qi) => {
                        const key = `${condition}-${qi}`;
                        return (
                          <div key={qi}>
                            <p className="text-sm font-medium text-slate-700 mb-2">{q.label}</p>
                            <div className="flex gap-2 flex-wrap">
                              {q.options.map(opt => (
                                <button
                                  key={opt}
                                  type="button"
                                  onClick={() => setConditionAnswers(prev => ({ ...prev, [key]: opt }))}
                                  className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${
                                    conditionAnswers[key] === opt
                                      ? 'bg-emerald-600 text-white border-emerald-600'
                                      : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
                                  }`}
                                >
                                  {opt}
                                </button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}

                <Textarea
                  label={t.medicationsLabel}
                  placeholder={t.medicationsPlaceholder}
                  value={medications}
                  onChange={setMedications}
                  rows={3}
                  onVoiceTranscribe={text =>
                    setMedications(prev => (prev ? `${prev}, ${text}` : text))
                  }
                  voiceLang={lang}
                />

                <Input
                  label={t.allergiesLabel}
                  placeholder={t.allergiesPlaceholder}
                  value={allergies}
                  onChange={setAllergies}
                  onVoiceTranscribe={text =>
                    setAllergies(prev => (prev ? `${prev}, ${text}` : text))
                  }
                  voiceLang={lang}
                />

                <Textarea
                  label={t.notesLabel}
                  placeholder={t.notesPlaceholder}
                  value={notes}
                  onChange={setNotes}
                  rows={3}
                  onVoiceTranscribe={text =>
                    setNotes(prev => (prev ? `${prev} ${text}` : text))
                  }
                  voiceLang={lang}
                />
              </div>
            </Card>

            {/* Review Summary */}
            <Card className="p-6">
              <h3 className="font-semibold text-slate-900 mb-3" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.reviewTitle}</h3>
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
                {t.reviewNotice}
              </div>
              <div className="flex flex-col gap-3">
                {[
                  { label: t.reviewLabels.name, value: name || '—' },
                  { label: t.reviewLabels.dob, value: dob || '—' },
                  { label: t.reviewLabels.phone, value: phone || '—' },
                  { label: t.reviewLabels.complaint, value: getEffectiveComplaints().map(c => t.complaintLabels[c] || c).join(', ') || '—' },
                  { label: t.reviewLabels.duration, value: t.durationOptions[duration] || duration },
                  { label: t.reviewLabels.severity, value: `${severity}/10` },
                  { label: t.reviewLabels.symptoms, value: SHARED_SYMPTOMS.filter(s => additionalSymptoms.includes(s.id)).map(s => t.symptomLabels[s.id] || s.label).join(', ') || t.reviewLabels.none },
                  { label: t.reviewLabels.conditions, value: conditions.map(c => t.conditionLabels[c] || c).join(', ') || '—' },
                  ...(getConditionDetailsSummaryList().length > 0
                    ? [{
                        label: 'Condition Details',
                        customNode: (
                          <div className="space-y-1">
                            {getConditionDetailsSummaryList().map(item => (
                              <div key={item.condition} className="text-slate-800 text-sm">
                                <span className="font-semibold text-slate-900">{item.condition}</span>
                                <span className="text-slate-600"> → {item.summary}</span>
                              </div>
                            ))}
                          </div>
                        ),
                      }]
                    : []),
                  { label: t.reviewLabels.medications, value: medications || t.reviewLabels.none },
                  { label: t.reviewLabels.allergies, value: allergies || t.reviewLabels.none },
                  { label: t.reviewLabels.notes, value: notes.trim() || '—' },
                ].map(row => (
                  <div key={row.label} className="flex gap-3 text-sm">
                    <span className="text-slate-400 w-36 flex-shrink-0 font-mono-label">{row.label}</span>
                    {'customNode' in row && row.customNode ? (
                      row.customNode
                    ) : (
                      <span className="text-slate-800">{row.value}</span>
                    )}
                  </div>
                ))}
              </div>
            </Card>

            <div className="flex gap-3 justify-between">
              <Button variant="secondary" onClick={() => setScreen('step2')}>{t.backBtn}</Button>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting ? t.submittingBtn : t.submitBtn}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function WelcomeScreen({
  onStart,
  loading,
  error,
  lang,
  onLangChange,
  patientName,
}: {
  onStart: () => void;
  loading: boolean;
  error: string | null;
  lang: PatientLang;
  onLangChange: (l: PatientLang) => void;
  patientName?: string;
}) {
  const t = LOCALIZATION[lang];

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Language selector on Welcome Screen */}
        <div className="flex justify-end mb-3">
          <LanguageSelector lang={lang} onChange={onLangChange} />
        </div>

        <div className="bg-white rounded-2xl shadow-md border border-slate-100 p-8 text-center">
          <div className="w-14 h-14 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto mb-4">
            <span className="text-white text-2xl font-bold" style={{ fontFamily: 'DM Sans, sans-serif' }}>M</span>
          </div>
          <div className="text-xs text-slate-400 font-mono-label uppercase tracking-widest mb-1">{t.medClinic}</div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            {patientName ? `Welcome back, ${patientName}!` : t.welcomeTitle}
          </h1>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            {patientName ? 'Starting a new clinical visit check-in. Please update your current symptoms and health status.' : t.welcomeDesc}
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs text-left">
              ⚠️ {error}
            </div>
          )}

          <Button onClick={onStart} disabled={loading} className="w-full" size="lg">
            {loading ? t.startingCheckIn : (patientName ? 'Start New Visit Check-in' : t.startCheckIn)}
          </Button>

          <p className="text-xs text-slate-400 mt-4 flex items-center justify-center gap-1.5">
            <span>🔒</span> {t.privateNote}
          </p>

          <div className="mt-6 pt-6 border-t border-slate-100 flex items-center justify-center gap-3">
            <div className="w-16 h-16 bg-slate-100 rounded-lg flex items-center justify-center text-slate-400 text-xs text-center leading-tight p-1">
              QR<br />Code
            </div>
            <p className="text-xs text-slate-500 text-left">{t.qrScanNote}</p>
          </div>
        </div>
        <p className="text-center text-xs text-slate-400 mt-4">{t.poweredBy}</p>
      </div>
    </div>
  );
}

function ConfirmScreen({
  result,
  fallbackDetails,
  lang,
  onLangChange,
  onDoctorView,
}: {
  result: IntakeSubmitResponse | null;
  fallbackDetails: {
    complaint: string;
    duration: string;
    severity: string;
    symptoms: string;
    conditions: string;
    medications: string;
    allergies: string;
  };
  lang: PatientLang;
  onLangChange: (l: PatientLang) => void;
  onDoctorView: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const t = LOCALIZATION[lang];

  const positionStr = result ? formatOrdinal(result.queue_position) : '1st';
  const waitTimeStr = result ? `~${result.wait_time_minutes} minutes` : '~10–15 minutes';

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Language selector on Confirm Screen */}
        <div className="flex justify-end mb-3">
          <LanguageSelector lang={lang} onChange={onLangChange} />
        </div>

        <div className="bg-white rounded-2xl shadow-md border border-slate-100 p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-green-50 border-2 border-green-200 flex items-center justify-center mx-auto mb-4">
            <span className="text-green-600 text-3xl">✓</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'DM Sans, sans-serif' }}>{t.checkedInTitle}</h1>
          <p className="text-slate-500 text-sm mb-6">
            {t.checkedInDesc(result?.patient_name)}
          </p>

          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-left mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-800">{t.queuePosition}</span>
              <span className="text-2xl font-bold text-blue-600" style={{ fontFamily: 'DM Sans, sans-serif' }}>{positionStr}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-sm text-slate-600">{t.estimatedWait} <strong>{waitTimeStr}</strong></span>
            </div>
            {result?.mrn && (
              <div className="mt-2 text-xs text-slate-400 font-mono-label">
                {t.patientRef} {result.mrn}
              </div>
            )}
          </div>

          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium mb-4 cursor-pointer"
          >
            {expanded ? t.hideSummary : t.showSummary}
          </button>

          {expanded && (
            <div className="text-left bg-slate-50 rounded-lg p-4 text-xs text-slate-600 space-y-1.5 mb-4 border border-slate-100">
              {[
                [t.reviewLabels.complaint, result?.summary.chief_complaint || fallbackDetails.complaint],
                [t.reviewLabels.duration, result?.summary.duration || fallbackDetails.duration],
                [t.reviewLabels.severity, result ? `${result.summary.severity}/10` : fallbackDetails.severity],
                [t.reviewLabels.symptoms, result?.summary.symptoms.join(', ') || fallbackDetails.symptoms],
                [t.reviewLabels.conditions, result?.summary.conditions.join(', ') || fallbackDetails.conditions],
                [t.reviewLabels.medications, result?.summary.medications || fallbackDetails.medications],
                [t.reviewLabels.allergies, result?.summary.allergies || fallbackDetails.allergies],
              ].map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-slate-400 w-24 flex-shrink-0 font-mono-label">{k}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-slate-400 mb-4">{t.doNotClose}</p>

          <button
            onClick={onDoctorView}
            className="text-xs text-slate-400 underline hover:text-slate-600 cursor-pointer"
          >
            {t.switchDoctor}
          </button>
        </div>
      </div>
    </div>
  );
}

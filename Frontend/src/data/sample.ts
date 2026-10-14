export const SAMPLE_PATIENT = {
  id: 'MRN-2026-0091',
  name: 'Sarah M.',
  firstName: 'Sarah',
  age: 28,
  dob: '14 March 1998',
  phone: '+44 7700 900142',
  gender: 'Female',
  allergies: [
    { substance: 'Penicillin', reaction: 'Rash', severity: 'Mild', source: 'patient-reported', firstDocumented: '22 Jun 2023' }
  ],
  queuePosition: 1,
  waitTime: '18 min',
};

export const INTAKE_DATA = {
  chiefComplaint: 'Fever and sore throat',
  symptoms: ['Fever', 'Sore Throat', 'Difficulty Swallowing', 'Runny Nose', 'Chills'],
  duration: '3–5 days',
  severity: 6,
  conditions: ['None of the above'],
  medications: 'None',
  allergies: 'Penicillin — rash',
  additionalNotes: 'Sore throat is getting worse. Had a similar episode last year which resolved on its own after about a week. The fever started two days after the sore throat.',
  submittedAt: '09:14, 17 Sep 2026',
};

export const TRANSCRIPT = `Doctor: Good morning, Sarah. I can see from your intake form you've been having a fever and sore throat. How long has this been going on?

Patient: Good morning. It's been about three days now, started on Sunday evening. The sore throat came first, then the fever hit the next morning.

Doctor: I see. On a scale of one to ten, how would you rate your discomfort overall?

Patient: Probably a six. The swallowing is the worst part — it's quite painful to eat anything solid.

Doctor: Any difficulty breathing or shortness of breath?

Patient: No, breathing is fine.

Doctor: Are you experiencing any ear pain?

Patient: Not really, maybe a tiny bit of pressure on the left side but nothing significant.

Doctor: Any chills or night sweats?

Patient: Yes, chills on the first night especially. I had to use an extra blanket.

Doctor: Runny nose or congestion?

Patient: A bit of a runny nose, yes, but not heavy congestion.

Doctor: Any nausea, vomiting, or stomach upset?

Patient: No, none of that.

Doctor: Are you currently taking any medications, prescribed or over the counter?

Patient: No, nothing. I took paracetamol yesterday for the fever but that's it — I wouldn't count that as a regular medication.

Doctor: That's fine, noted. Any known drug allergies?

Patient: Yes — I had a reaction to penicillin as a child, it came up as a rash. It wasn't severe, just a skin rash. My parents were told to avoid it but I've never been formally tested.

Doctor: Understood. Any other allergies — food, environmental?

Patient: No, nothing else that I know of.

Doctor: Let me take a look at your throat. Can you open wide and say "ahh"?

Patient: [opens mouth]

Doctor: I can see significant redness and tonsillar exudate — that's a white coating on the tonsils. There's also some swelling of the lymph nodes in your neck here. Let me just check your vitals — your temperature is 38.6 degrees, heart rate 88, blood pressure is 118 over 74, and your oxygen saturation is 98 percent, which is perfectly normal.

Patient: Is it serious?

Doctor: The clinical picture is consistent with bacterial pharyngitis, most likely streptococcal — what people commonly call strep throat. I'd like to do a rapid strep test to confirm. We'll get the result within about ten minutes.

Patient: Okay, that's fine.

Doctor: Given your allergy to penicillin, I want to clarify — you said it was a childhood rash. Did you ever have any breathing difficulties, swelling, or a more severe reaction with penicillin?

Patient: No, it was just a skin rash. My mum said I was about four years old and it cleared up with antihistamines.

Doctor: That's important to know. A mild childhood rash with penicillin often represents a non-IgE-mediated reaction — meaning it may not be a true allergy. However, I'll document it carefully and we have safe alternatives. If the strep test is positive, I'll prescribe amoxicillin — it's in the same family but the risk with a mild historical rash is considered low — or we can use azithromycin as an alternative. I'll make a note that this requires monitoring.

Patient: Okay, I'll trust your judgement on that.

Doctor: Good. I'd also recommend rest, plenty of fluids, and you can continue paracetamol for fever and discomfort. Come back in five days if you're not improving, or sooner if your symptoms worsen significantly — particularly any difficulty breathing or if the fever spikes above 39.5.

Patient: Understood. Thank you, doctor.

Doctor: We'll get that swab done now and I'll have the prescription ready once we have the result.`;

export const SOAP_NOTE = {
  subjective: `Patient Sarah M., 28F, presents with a 3-day history of fever and sore throat. Onset was Sunday evening with sore throat preceding fever onset by approximately 24 hours. Reports significant odynophagia (difficulty swallowing), chills on night one, and mild rhinorrhoea. Rates overall discomfort at 6/10. Denies shortness of breath, nausea, vomiting, or significant ear pain. Takes no regular medications. Reports paracetamol use PRN yesterday for fever. History of penicillin allergy — childhood rash only, resolved with antihistamines, no anaphylaxis or severe reaction documented. No other known allergies.`,
  objective: `Vitals: Temperature 38.6°C, HR 88 bpm, BP 118/74 mmHg, SpO₂ 98% on room air. Oropharynx: erythematous with bilateral tonsillar exudates. Anterior cervical lymphadenopathy noted bilaterally. No respiratory distress. Rapid strep test: pending.`,
  assessment: `Acute pharyngitis with clinical features strongly consistent with Group A Streptococcus (Streptococcal pharyngitis). CENTOR criteria score: 4/4 (tonsillar exudates, anterior cervical lymphadenopathy, fever, absence of cough). Penicillin allergy on record — documented as mild childhood cutaneous reaction, likely non-IgE-mediated.`,
  plan: `1. Rapid strep test (result pending — to confirm diagnosis before prescription issue). 2. If strep positive: Amoxicillin 500mg TDS × 7 days (allergy note: mild childhood penicillin rash documented; risk considered low; patient counselled and consents; monitoring advised). Alternative: Azithromycin 500mg OD × 5 days if patient declines amoxicillin. 3. Paracetamol 500–1000mg PRN Q4–6H for fever and analgesia. 4. Rest and increased oral fluid intake. 5. Return if no improvement in 5 days, or earlier if fever >39.5°C, breathing difficulty, or worsening symptoms. 6. Consider formal penicillin allergy assessment at follow-up.`,
};

export const VERIFICATION_CLAIMS = [
  { id: 'c1', claim: 'Fever and sore throat for 3 days', status: 'supported', evidence: 'Patient: "It\'s been about three days now, started on Sunday evening. The sore throat came first, then the fever hit the next morning."', section: 'subjective' },
  { id: 'c2', claim: 'Significant odynophagia — difficulty swallowing', status: 'supported', evidence: 'Patient: "The swallowing is the worst part — it\'s quite painful to eat anything solid."', section: 'subjective' },
  { id: 'c3', claim: 'Chills on night one', status: 'supported', evidence: 'Patient: "Yes, chills on the first night especially. I had to use an extra blanket."', section: 'subjective' },
  { id: 'c4', claim: 'Mild rhinorrhoea', status: 'supported', evidence: 'Patient: "A bit of a runny nose, yes, but not heavy congestion."', section: 'subjective' },
  { id: 'c5', claim: 'Discomfort rated 6/10', status: 'supported', evidence: 'Patient: "Probably a six. The swallowing is the worst part."', section: 'subjective' },
  { id: 'c6', claim: 'No regular medications', status: 'supported', evidence: 'Patient: "No, nothing. I took paracetamol yesterday for the fever but that\'s it."', section: 'subjective' },
  { id: 'c7', claim: 'Penicillin allergy — childhood rash, resolved with antihistamines', status: 'supported', evidence: 'Patient: "I had a reaction to penicillin as a child, it came up as a rash... My mum said I was about four years old and it cleared up with antihistamines."', section: 'subjective' },
  { id: 'c8', claim: 'Temperature 38.6°C, HR 88, BP 118/74, SpO₂ 98%', status: 'supported', evidence: 'Doctor: "your temperature is 38.6 degrees, heart rate 88, blood pressure is 118 over 74, and your oxygen saturation is 98 percent"', section: 'objective' },
  { id: 'c9', claim: 'Bilateral tonsillar exudates', status: 'unsupported', evidence: 'Transcript does not specify "bilateral." Doctor states: "I can see significant redness and tonsillar exudate" — laterality not documented in transcript. Likely from physical examination notes not captured in recording.', section: 'objective' },
  { id: 'c10', claim: 'Anterior cervical lymphadenopathy', status: 'supported', evidence: 'Doctor: "There\'s also some swelling of the lymph nodes in your neck here."', section: 'objective' },
  { id: 'c11', claim: 'Amoxicillin 500mg TDS × 7 days', status: 'ambiguous', evidence: 'Doctor mentions amoxicillin but does not state the dose or frequency in the transcript. Doctor: "I\'ll prescribe amoxicillin... or we can use azithromycin as an alternative." Dose was entered manually.', section: 'plan' },
  { id: 'c12', claim: 'Return if no improvement in 5 days', status: 'supported', evidence: 'Doctor: "Come back in five days if you\'re not improving, or sooner if your symptoms worsen significantly."', section: 'plan' },
];

export const CONFLICTS = [
  {
    id: 'conflict1',
    field: 'Allergy management',
    intakeValue: 'Penicillin allergy documented — patient selected it as a known allergy without qualifying severity',
    consultationValue: 'Amoxicillin (penicillin-family) prescribed — doctor assessed risk as low based on detailed history of mild childhood rash',
    status: 'resolved',
    resolution: 'Patient confirmed rash was mild, non-anaphylactic, childhood reaction. Doctor assessed non-IgE-mediated mechanism. Amoxicillin considered acceptable with monitoring. Azithromycin offered as alternative.',
    severity: 'warning',
  },
  {
    id: 'conflict2',
    field: 'Fever duration',
    intakeValue: '3–5 days selected on form',
    consultationValue: 'Confirmed as 3 days in consultation',
    status: 'consistent',
    resolution: null,
    severity: 'none',
  },
  {
    id: 'conflict3',
    field: 'Ear pain',
    intakeValue: 'Not selected on intake form',
    consultationValue: 'Patient mentioned "maybe a tiny bit of pressure on the left side" in consultation',
    status: 'minor',
    resolution: null,
    severity: 'info',
  }
];

export const VISIT_HISTORY = [
  {
    date: '17 Sep 2026',
    complaint: 'Fever and sore throat',
    diagnosis: 'Acute pharyngitis — Group A Streptococcus (suspected)',
    doctor: 'Dr. J. Patel',
    status: 'active',
    dot: 'blue',
  },
  {
    date: '12 Mar 2025',
    complaint: 'Fever, congestion, cough',
    diagnosis: 'Upper respiratory tract infection (viral)',
    doctor: 'Dr. J. Patel',
    status: 'completed',
    dot: 'gray',
    soap: {
      s: 'Patient presented with 5-day history of cough, nasal congestion, mild fever (37.9°C). No sore throat. No antibiotic indicated.',
      o: 'Temp 37.9°C, HR 82. Clear chest on auscultation. No tonsillar exudates.',
      a: 'Viral URTI. No bacterial features.',
      p: 'Symptomatic management. Rest, fluids. Paracetamol PRN. No antibiotics. Follow up if >10 days.',
    }
  },
  {
    date: '22 Jun 2023',
    complaint: 'Skin rash — drug reaction',
    diagnosis: 'Penicillin hypersensitivity reaction (mild — cutaneous)',
    doctor: 'Dr. A. Singh',
    status: 'completed',
    dot: 'red',
    soap: {
      s: 'Patient (then 25F) presented with diffuse maculopapular rash following penicillin course for dental infection. No facial swelling, no breathing difficulty.',
      o: 'Maculopapular rash on trunk and arms. No urticaria. Vitals stable.',
      a: 'Mild penicillin hypersensitivity — likely non-IgE-mediated. Not anaphylaxis.',
      p: 'Cetirizine 10mg OD × 5 days. Avoid penicillin pending allergy assessment. Refer to allergy clinic.',
    }
  },
  {
    date: '04 Nov 2024',
    complaint: 'Annual check-up',
    diagnosis: 'No significant findings',
    doctor: 'Dr. J. Patel',
    status: 'completed',
    dot: 'green',
  }
];

export const QUEUE_PATIENTS = [
  { position: 1, name: 'Sarah M.', waitTime: '18 min', complaint: 'Fever, Sore Throat', intakeStatus: 'complete', status: 'waiting', id: 'sarah' },
  { position: 2, name: 'James K.', waitTime: '6 min', complaint: 'Knee pain', intakeStatus: 'pending', status: 'waiting', id: 'james' },
  { position: 3, name: 'Mei-Lin C.', waitTime: '31 min', complaint: 'Headache, dizziness', intakeStatus: 'complete', status: 'waiting', id: 'mei' },
  { position: null, name: 'Anne T.', waitTime: '—', complaint: 'Follow-up — hypertension', intakeStatus: 'complete', status: 'in-consultation', id: 'anne' },
  { position: null, name: 'Robert H.', waitTime: '—', complaint: 'Chest tightness', intakeStatus: 'complete', status: 'completed', id: 'robert' },
];

export type PatientLang = 'en' | 'hi' | 'hinglish';

export interface LocalizationDictionary {
  medClinic: string;
  progressSteps: [string, string, string, string];

  // Welcome Screen
  welcomeTitle: string;
  welcomeDesc: string;
  startCheckIn: string;
  startingCheckIn: string;
  privateNote: string;
  qrScanNote: string;
  poweredBy: string;

  // Step 1: Your Details
  detailsTitle: string;
  detailsDesc: string;
  fullNameLabel: string;
  fullNamePlaceholder: string;
  dobLabel: string;
  phoneLabel: string;
  phonePlaceholder: string;
  nameError: string;
  continueBtn: string;
  backBtn: string;
  privateEncrypted: string;

  // Step 2: Symptoms
  symptomsTitle: string;
  symptomsDesc: string;
  complaintLabels: Record<string, string>;
  durationQuestion: string;
  durationOptions: Record<string, string>;
  severityQuestion: string;
  severityMild: string;
  severityMod: string;
  severitySev: string;
  followUpPrefix: string;
  adaptiveQuestions: Record<string, { label: string; options: Record<string, string> }[]>;
  additionalSymptomsQuestion: string;
  symptomLabels: Record<string, string>;
  complaintError: string;

  // Step 3: Medical History
  historyTitle: string;
  historyDesc: string;
  conditionsQuestion: string;
  conditionLabels: Record<string, string>;
  medicationsLabel: string;
  medicationsPlaceholder: string;
  allergiesLabel: string;
  allergiesPlaceholder: string;
  notesLabel: string;
  notesPlaceholder: string;
  reviewTitle: string;
  reviewNotice: string;
  reviewLabels: {
    name: string;
    dob: string;
    phone: string;
    complaint: string;
    duration: string;
    severity: string;
    symptoms: string;
    conditions: string;
    medications: string;
    allergies: string;
    notes: string;
    none: string;
  };
  submitBtn: string;
  submittingBtn: string;

  // Confirm Screen
  checkedInTitle: string;
  checkedInDesc: (name?: string) => string;
  queuePosition: string;
  estimatedWait: string;
  patientRef: string;
  showSummary: string;
  hideSummary: string;
  doNotClose: string;
  switchDoctor: string;
}

export const LOCALIZATION: Record<PatientLang, LocalizationDictionary> = {
  en: {
    medClinic: 'MedClinic',
    progressSteps: ['Your Details', 'Symptoms', 'Medical History', 'Review'],

    welcomeTitle: 'Welcome to Check-In',
    welcomeDesc: 'Please complete your pre-consultation form. Your responses help your doctor prepare for your visit.',
    startCheckIn: 'Start Check-In',
    startingCheckIn: 'Starting Check-In…',
    privateNote: 'Private and encrypted. Your information goes directly to your doctor.',
    qrScanNote: 'Scan from your own device to complete the form on your phone',
    poweredBy: 'Powered by Medscribe-Verify',

    detailsTitle: 'Your Details',
    detailsDesc: 'We only use this to identify your record for your consultation today.',
    fullNameLabel: 'Full name',
    fullNamePlaceholder: 'e.g. Sarah Miller',
    dobLabel: 'Date of birth',
    phoneLabel: 'Phone number (optional)',
    phonePlaceholder: '+44 7700 000 000',
    nameError: 'Please enter your name.',
    continueBtn: 'Continue →',
    backBtn: '← Back',
    privateEncrypted: 'This session is private and encrypted.',

    symptomsTitle: 'What brings you in today?',
    symptomsDesc: "Select all that apply. We'll ask follow-up questions based on your selection.",
    complaintLabels: {
      Cough: 'Cough',
      Fever: 'Fever',
      'Sore Throat': 'Sore Throat',
      'Stomach Pain': 'Stomach Pain',
      Headache: 'Headache',
      'Chest Pain': 'Chest Pain',
      Dizziness: 'Dizziness',
      Other: 'Other',
    },
    durationQuestion: 'How long have you had these symptoms?',
    durationOptions: {
      '1–2 days': '1–2 days',
      '3–5 days': '3–5 days',
      'More than 5 days': 'More than 5 days',
    },
    severityQuestion: 'How would you rate your discomfort?',
    severityMild: 'Mild',
    severityMod: 'Moderate',
    severitySev: 'Severe',
    followUpPrefix: 'Follow-up:',
    adaptiveQuestions: {
      Fever: [
        {
          label: 'Did the fever start gradually or suddenly?',
          options: { Gradually: 'Gradually', Suddenly: 'Suddenly', "I'm not sure": "I'm not sure" },
        },
        {
          label: 'Have you measured your temperature?',
          options: {
            'Yes, above 38°C': 'Yes, above 38°C',
            'Yes, below 38°C': 'Yes, below 38°C',
            "No, I haven't measured": "No, I haven't measured",
          },
        },
      ],
      'Sore Throat': [
        {
          label: 'Is it painful to swallow?',
          options: { 'Yes, very painful': 'Yes, very painful', 'Mildly uncomfortable': 'Mildly uncomfortable', No: 'No' },
        },
        {
          label: 'Have you noticed any white patches on your throat?',
          options: { Yes: 'Yes', No: 'No', "I haven't looked": "I haven't looked" },
        },
      ],
      Cough: [
        {
          label: 'Is your cough dry or producing mucus?',
          options: { Dry: 'Dry', 'Producing mucus': 'Producing mucus', Both: 'Both' },
        },
        {
          label: 'How long have you been coughing?',
          options: { 'Less than 3 days': 'Less than 3 days', '3–7 days': '3–7 days', 'More than a week': 'More than a week' },
        },
      ],
      'Stomach Pain': [
        {
          label: 'Where is the pain located?',
          options: { 'Upper abdomen': 'Upper abdomen', 'Lower abdomen': 'Lower abdomen', 'All over': 'All over' },
        },
        {
          label: 'Is the pain constant or comes and goes?',
          options: { Constant: 'Constant', 'Comes and goes': 'Comes and goes', 'Only after eating': 'Only after eating' },
        },
      ],
      Headache: [
        {
          label: 'Where do you feel the headache?',
          options: { Forehead: 'Forehead', 'Behind eyes': 'Behind eyes', 'Back of head': 'Back of head', 'One side only': 'One side only' },
        },
        {
          label: 'Is the headache accompanied by nausea or light sensitivity?',
          options: { Yes: 'Yes', No: 'No', 'Only nausea': 'Only nausea' },
        },
      ],
    },
    additionalSymptomsQuestion: 'Do you have any of the following? (select all that apply)',
    symptomLabels: {
      diff_swallow: 'Difficulty swallowing',
      ear_pain: 'Ear pain',
      runny_nose: 'Runny nose',
      chills: 'Chills',
      rash: 'Rash',
      nausea: 'Nausea',
      fatigue: 'Fatigue',
      loss_appetite: 'Loss of appetite',
    },
    complaintError: 'Please select at least one reason for your visit.',

    historyTitle: 'Medical History',
    historyDesc: 'This helps your doctor understand your background.',
    conditionsQuestion: 'Do you have any existing conditions? (select all that apply)',
    conditionLabels: {
      Diabetes: 'Diabetes',
      'High blood pressure': 'High blood pressure',
      Asthma: 'Asthma',
      'Heart disease': 'Heart disease',
      'Thyroid condition': 'Thyroid condition',
      'Kidney disease': 'Kidney disease',
      'None of the above': 'None of the above',
    },
    medicationsLabel: 'Current medications',
    medicationsPlaceholder: "List any medications you currently take, or write 'None'",
    allergiesLabel: 'Known allergies',
    allergiesPlaceholder: 'e.g. Penicillin — rash, Peanuts — anaphylaxis',
    notesLabel: "Anything else you'd like your doctor to know?",
    notesPlaceholder: 'Any additional symptoms, concerns, or context...',

    reviewTitle: 'Review Your Responses',
    reviewNotice: 'Please review before submitting. You can go back to change any answer.',
    reviewLabels: {
      name: 'Name',
      dob: 'Date of Birth',
      phone: 'Phone',
      complaint: 'Chief Complaint',
      duration: 'Duration',
      severity: 'Severity',
      symptoms: 'Additional Symptoms',
      conditions: 'Existing Conditions',
      medications: 'Medications',
      allergies: 'Allergies',
      notes: 'Additional Notes',
      none: 'None',
    },
    submitBtn: 'Submit & Join Queue →',
    submittingBtn: 'Submitting to Queue…',

    checkedInTitle: "You're checked in!",
    checkedInDesc: name =>
      name
        ? `Thank you, ${name}. Your doctor has received your information.`
        : 'Your doctor has received your information and will call you shortly.',
    queuePosition: 'Queue Position',
    estimatedWait: 'Estimated wait:',
    patientRef: 'Patient Ref:',
    showSummary: '▼ View your submitted summary',
    hideSummary: '▲ Hide submitted summary',
    doNotClose: 'Do not close this page. Your queue position is tied to this session.',
    switchDoctor: '[Switch to Doctor View →]',
  },

  hi: {
    medClinic: 'मेडक्लिनिक',
    progressSteps: ['आपकी जानकारी', 'लक्षण', 'चिकित्सा इतिहास', 'समीक्षा'],

    welcomeTitle: 'चेक-इन में आपका स्वागत है',
    welcomeDesc: 'कृपया अपना परामर्श-पूर्व फॉर्म भरें। आपके उत्तर डॉक्टर को आपकी जांच की तैयारी में मदद करते हैं।',
    startCheckIn: 'चेक-इन शुरू करें',
    startingCheckIn: 'चेक-इन शुरू हो रहा है…',
    privateNote: 'सुरक्षित और गोपनीय। आपकी जानकारी सीधे आपके डॉक्टर के पास जाती है।',
    qrScanNote: 'अपने मोबाइल पर फॉर्म भरने के लिए इस कोड को स्कैन करें',
    poweredBy: 'पावर्ड बाय मेडस्क्राइब-वेरीफाई',

    detailsTitle: 'आपकी जानकारी',
    detailsDesc: 'हम इसका उपयोग केवल आज के परामर्श के लिए आपके रिकॉर्ड की पहचान हेतु करते हैं।',
    fullNameLabel: 'पूरा नाम',
    fullNamePlaceholder: 'उदा. राहुल शर्मा',
    dobLabel: 'जन्म तिथि',
    phoneLabel: 'फ़ोन नंबर (वैकल्पिक)',
    phonePlaceholder: '+91 98765 43210',
    nameError: 'कृपया अपना नाम दर्ज करें।',
    continueBtn: 'आगे बढ़ें →',
    backBtn: '← वापस',
    privateEncrypted: 'यह सत्र पूरी तरह निजी और सुरक्षित (एन्क्रिप्टेड) है।',

    symptomsTitle: 'आज आप किस समस्या के लिए आए हैं?',
    symptomsDesc: 'जो भी लक्षण हों उन्हें चुनें। आपके चयन के आधार पर हम कुछ आसान सवाल पूछेंगे।',
    complaintLabels: {
      Cough: 'खांसी',
      Fever: 'बुखार',
      'Sore Throat': 'गले में दर्द / खराश',
      'Stomach Pain': 'पेट दर्द',
      Headache: 'सिरदर्द',
      'Chest Pain': 'सीने में दर्द',
      Dizziness: 'चक्कर आना',
      Other: 'अन्य समस्या',
    },
    durationQuestion: 'आपको यह लक्षण कितने समय से हैं?',
    durationOptions: {
      '1–2 days': '1–2 दिन',
      '3–5 days': '3–5 दिन',
      'More than 5 days': '5 दिन से अधिक',
    },
    severityQuestion: 'आप अपनी तकलीफ़ की तीव्रता को कैसे आंकेंगे?',
    severityMild: 'हल्की',
    severityMod: 'मध्यम',
    severitySev: 'गंभीर',
    followUpPrefix: 'विस्तृत प्रश्न:',
    adaptiveQuestions: {
      Fever: [
        {
          label: 'बुखार धीरे-धीरे शुरू हुआ या अचानक?',
          options: { Gradually: 'धीरे-धीरे', Suddenly: 'अचानक', "I'm not sure": 'निश्चित नहीं' },
        },
        {
          label: 'क्या आपने तापमान नापा है?',
          options: {
            'Yes, above 38°C': 'हाँ, 38°C (100.4°F) से अधिक',
            'Yes, below 38°C': 'हाँ, 38°C से कम',
            "No, I haven't measured": 'नहीं, तापमान नहीं नापा',
          },
        },
      ],
      'Sore Throat': [
        {
          label: 'क्या कुछ भी निगलने में दर्द होता है?',
          options: { 'Yes, very painful': 'हाँ, बहुत तेज दर्द है', 'Mildly uncomfortable': 'हल्की तकलीफ़ है', No: 'नहीं' },
        },
        {
          label: 'क्या गले में सफेद धब्बे या छाले दिखे हैं?',
          options: { Yes: 'हाँ', No: 'नहीं', "I haven't looked": 'देखा नहीं है' },
        },
      ],
      Cough: [
        {
          label: 'क्या खांसी सूखी है या बलगम आ रहा है?',
          options: { Dry: 'सूखी खांसी', 'Producing mucus': 'बलगम आ रहा है', Both: 'दोनों' },
        },
        {
          label: 'आपको खांसी कितने समय से है?',
          options: { 'Less than 3 days': '3 दिन से कम', '3–7 days': '3–7 दिन', 'More than a week': 'एक सप्ताह से अधिक' },
        },
      ],
      'Stomach Pain': [
        {
          label: 'पेट में दर्द किस जगह हो रहा है?',
          options: { 'Upper abdomen': 'ऊपरी पेट में', 'Lower abdomen': 'निचले पेट में', 'All over': 'पूरे पेट में' },
        },
        {
          label: 'दर्द लगातार बना रहता है या रुक-रुक कर होता है?',
          options: { Constant: 'लगातार', 'Comes and goes': 'रुक-रुक कर', 'Only after eating': 'केवल खाने के बाद' },
        },
      ],
      Headache: [
        {
          label: 'सिरदर्द किस हिस्से में महसूस हो रहा है?',
          options: { Forehead: 'माथे पर', 'Behind eyes': 'आंखों के पीछे', 'Back of head': 'सिर के पिछले हिस्से में', 'One side only': 'केवल एक तरफ' },
        },
        {
          label: 'क्या सिरदर्द के साथ जी मिचलाना या तेज रोशनी से परेशानी है?',
          options: { Yes: 'हाँ', No: 'नहीं', 'Only nausea': 'केवल जी मिचलाना' },
        },
      ],
    },
    additionalSymptomsQuestion: 'क्या आपको इनमें से कोई अन्य लक्षण भी हैं? (जो भी हों चुनें)',
    symptomLabels: {
      diff_swallow: 'निगलने में कठिनाई',
      ear_pain: 'कान में दर्द',
      runny_nose: 'बहती नाक / जुकाम',
      chills: 'ठंड लगना / कंपकंपी',
      rash: 'त्वचा पर चकत्ते / रैश',
      nausea: 'जी मिचलाना / उल्टी जैसा',
      fatigue: 'अत्यधिक थकान / कमजोरी',
      loss_appetite: 'भूख न लगना',
    },
    complaintError: 'कृपया कम से कम एक कारण या लक्षण अवश्य चुनें।',

    historyTitle: 'चिकित्सा इतिहास',
    historyDesc: 'इससे आपके डॉक्टर को आपकी स्वास्थ्य पृष्ठभूमि समझने में मदद मिलती है।',
    conditionsQuestion: 'क्या आपको पहले से कोई बीमारी है? (जो भी हों चुनें)',
    conditionLabels: {
      Diabetes: 'मधुमेह (Diabetes)',
      'High blood pressure': 'उच्च रक्तचाप (High BP)',
      Asthma: 'अस्थमा / दमा (Asthma)',
      'Heart disease': 'हृदय रोग (Heart condition)',
      'Thyroid condition': 'थायराइड (Thyroid)',
      'Kidney disease': 'गुर्दे की बीमारी (Kidney disease)',
      'None of the above': 'इनमें से कोई नहीं',
    },
    medicationsLabel: 'वर्तमान दवाइयां (Current medications)',
    medicationsPlaceholder: 'दवाइयों के नाम लिखें या बोलकर दर्ज करें, या "कोई नहीं" लिखें...',
    allergiesLabel: 'ज्ञात एलर्जी (Known allergies)',
    allergiesPlaceholder: 'उदा. पेनिसिलिन — चकत्ते, मूंगफली — सांस की तकलीफ',
    notesLabel: 'डॉक्टर के लिए कोई अन्य जानकारी या लक्षण?',
    notesPlaceholder: 'कोई अन्य लक्षण, चिंता या विवरण (बोलकर या लिखकर दर्ज करें)...',

    reviewTitle: 'अपने उत्तरों की समीक्षा करें',
    reviewNotice: 'कृपया जमा करने से पहले जांच लें। उत्तर बदलने के लिए आप वापस जा सकते हैं।',
    reviewLabels: {
      name: 'नाम',
      dob: 'जन्म तिथि',
      phone: 'फ़ोन नंबर',
      complaint: 'मुख्य समस्या',
      duration: 'अवधि',
      severity: 'तीव्रता / गंभीरता',
      symptoms: 'अन्य लक्षण',
      conditions: 'पुरानी बीमारियां',
      medications: 'दवाइयां',
      allergies: 'एलर्जी',
      notes: 'अतिरिक्त विवरण',
      none: 'कोई नहीं',
    },
    submitBtn: 'जमा करें और कतार में शामिल हों →',
    submittingBtn: 'कतार में जोड़ा जा रहा है…',

    checkedInTitle: 'आपका चेक-इन पूरा हो गया है!',
    checkedInDesc: name =>
      name
        ? `धन्यवाद, ${name}। आपके डॉक्टर को आपकी जानकारी मिल गई है।`
        : 'आपके डॉक्टर को आपकी जानकारी मिल गई है और वे जल्द ही आपको बुलाएंगे।',
    queuePosition: 'कतार में स्थान',
    estimatedWait: 'अनुमानित प्रतीक्षा समय:',
    patientRef: 'मरीज संदर्भ संख्या:',
    showSummary: '▼ जमा किया गया विवरण देखें',
    hideSummary: '▲ विवरण छिपाएं',
    doNotClose: 'कृपया इस पृष्ठ को बंद न करें। आपकी कतार का नंबर इस सत्र से जुड़ा है।',
    switchDoctor: '[डॉक्टर दृश्य पर जाएं →]',
  },

  hinglish: {
    medClinic: 'MedClinic',
    progressSteps: ['Aapki Details', 'Symptoms (Lakshan)', 'Medical History (Itihas)', 'Review Karein'],

    welcomeTitle: 'Check-In me Aapka Swagat Hai',
    welcomeDesc: 'Kripya apna pre-consultation form complete karein. Isse doctor ko aapki visit ke liye prepare karne me madad milti hai.',
    startCheckIn: 'Check-In Shuru Karein',
    startingCheckIn: 'Check-In Shuru Ho Raha Hai…',
    privateNote: 'Private aur encrypted. Aapki information direct doctor ke paas secure tarike se jayegi.',
    qrScanNote: 'Apne mobile se scan karke phone par form complete karein',
    poweredBy: 'Powered by Medscribe-Verify',

    detailsTitle: 'Aapki Details',
    detailsDesc: 'Yeh details sirf aaj ke consultation record ko pehchanne ke liye use hongi.',
    fullNameLabel: 'Full name (Pura naam)',
    fullNamePlaceholder: 'Jaise: Rahul Sharma',
    dobLabel: 'Date of birth (Janam tithi)',
    phoneLabel: 'Phone number (Optional)',
    phonePlaceholder: '+91 98765 43210',
    nameError: 'Kripya apna naam enter karein.',
    continueBtn: 'Aage Badhein →',
    backBtn: '← Peeche',
    privateEncrypted: 'Yeh session private aur encrypted hai.',

    symptomsTitle: 'Aaj kya takleef hai?',
    symptomsDesc: 'Jo symptoms hain unhe select karein. Hum aage kuch simple follow-up sawal sochenge.',
    complaintLabels: {
      Cough: 'Khansi (Cough)',
      Fever: 'Bukhar (Fever)',
      'Sore Throat': 'Gale me dard (Sore throat)',
      'Stomach Pain': 'Pet me dard (Stomach pain)',
      Headache: 'Sar dard (Headache)',
      'Chest Pain': 'Seene me dard (Chest pain)',
      Dizziness: 'Chakkar aana (Dizziness)',
      Other: 'Koi aur dikkat (Other)',
    },
    durationQuestion: 'Yeh symptoms kitne dino se hain?',
    durationOptions: {
      '1–2 days': '1–2 din',
      '3–5 days': '3–5 din',
      'More than 5 days': '5 din se zyada',
    },
    severityQuestion: 'Takleef kitni zyada feel ho rahi hai?',
    severityMild: 'Kam (Mild)',
    severityMod: 'Thodi zyada (Moderate)',
    severitySev: 'Bohot zyada (Severe)',
    followUpPrefix: 'Follow-up sawal:',
    adaptiveQuestions: {
      Fever: [
        {
          label: 'Bukhar dheere-dheere shuru hua ya achanak?',
          options: { Gradually: 'Dheere-dheere', Suddenly: 'Achanak', "I'm not sure": 'Sure nahi hoon' },
        },
        {
          label: 'Kya aapne temperature measure kiya hai?',
          options: {
            'Yes, above 38°C': 'Haan, 38°C (100.4°F) se zyada',
            'Yes, below 38°C': 'Haan, 38°C se kam',
            "No, I haven't measured": 'Nahi, naapa nahi',
          },
        },
      ],
      'Sore Throat': [
        {
          label: 'Khane ya nigalne me dard hota hai?',
          options: { 'Yes, very painful': 'Haan, bohot zyada dard hai', 'Mildly uncomfortable': 'Thoda uncomfortable', No: 'Nahi' },
        },
        {
          label: 'Gale me koi white spots / chhale notice kiye hain?',
          options: { Yes: 'Haan', No: 'Nahi', "I haven't looked": 'Check nahi kiya' },
        },
      ],
      Cough: [
        {
          label: 'Khansi sukhi hai ya balgam (mucus) aa raha hai?',
          options: { Dry: 'Sukhi khansi', 'Producing mucus': 'Balgam ke sath', Both: 'Dono' },
        },
        {
          label: 'Khansi kitne dino se ho rahi hai?',
          options: { 'Less than 3 days': '3 din se kam', '3–7 days': '3–7 din', 'More than a week': '1 hafte se zyada' },
        },
      ],
      'Stomach Pain': [
        {
          label: 'Pet me dard kahan par ho raha hai?',
          options: { 'Upper abdomen': 'Upar pet me', 'Lower abdomen': 'Neeche pet me', 'All over': 'Pure pet me' },
        },
        {
          label: 'Dard lagatar rehta hai ya aata-jaata hai?',
          options: { Constant: 'Lagatar bana rehta hai', 'Comes and goes': 'Aata-jaata hai', 'Only after eating': 'Sirf khane ke baad' },
        },
      ],
      Headache: [
        {
          label: 'Sar dard kahan par feel ho raha hai?',
          options: { Forehead: 'Maathe par', 'Behind eyes': 'Aankhon ke peeche', 'Back of head': 'Sar ke peeche', 'One side only': 'Sirf ek side' },
        },
        {
          label: 'Sar dard ke sath ulti jaisa lagna ya light se problem hai?',
          options: { Yes: 'Haan', No: 'Nahi', 'Only nausea': 'Sirf ulti jaisa lagna' },
        },
      ],
    },
    additionalSymptomsQuestion: 'Kya inme se koi aur symptoms bhi hain? (select all that apply)',
    symptomLabels: {
      diff_swallow: 'Nigalne me dikkat',
      ear_pain: 'Kaan me dard',
      runny_nose: 'Naak behna / z जुकाम',
      chills: 'Thand lagna (Chills)',
      rash: 'Chakatte ya rash',
      nausea: 'Ulti jaisa lagna (Nausea)',
      fatigue: 'Bohot zyada thakan',
      loss_appetite: 'Bhookh na lagna',
    },
    complaintError: 'Kripya kam se kam ek chief complaint zaroor select karein.',

    historyTitle: 'Medical History (Purani bimariyan aur dawaiyan)',
    historyDesc: 'Isse doctor ko aapki health background samajhne me asani hogi.',
    conditionsQuestion: 'Kya pehle se koi bimari ya health condition hai? (select karein)',
    conditionLabels: {
      Diabetes: 'Diabetes / Sugar (मधुमेह)',
      'High blood pressure': 'High BP / Hypertension (उच्च रक्तचाप)',
      Asthma: 'Asthma / Dama (दमा)',
      'Heart disease': 'Heart condition / Dil ki bimari',
      'Thyroid condition': 'Thyroid problem (थायराइड)',
      'Kidney disease': 'Kidney disease / Gurde ki bimari',
      'None of the above': 'Inme se koi nahi (None of the above)',
    },
    medicationsLabel: 'Current medications (Dawaiyan jo le rahe hain)',
    medicationsPlaceholder: 'Jo dawaiyan lete hain likhein ya bolkar batayein, ya "None" likhein...',
    allergiesLabel: 'Known allergies (Dawai ya khane se allergy)',
    allergiesPlaceholder: 'Jaise: Penicillin se rash, ya koi dawai se reaction',
    notesLabel: 'Doctor ke liye koi aur jankari ya symptoms?',
    notesPlaceholder: 'Koi aur problem, symptoms ya details (bolkar ya type karke likhein)...',

    reviewTitle: 'Apne Jawabo Ko Review Karein',
    reviewNotice: 'Submit karne se pehle review kar lein. Change karne ke liye back ja sakte hain.',
    reviewLabels: {
      name: 'Naam',
      dob: 'Date of Birth',
      phone: 'Phone',
      complaint: 'Mukhya Complaint',
      duration: 'Kitne din se',
      severity: 'Severity / Takleef',
      symptoms: 'Anya Symptoms',
      conditions: 'Existing Conditions',
      medications: 'Medications',
      allergies: 'Allergies',
      notes: 'Extra Notes',
      none: 'None',
    },
    submitBtn: 'Submit Karein & Queue Join Karein →',
    submittingBtn: 'Queue me add ho raha hai…',

    checkedInTitle: 'Aapka check-in complete ho gaya!',
    checkedInDesc: name =>
      name
        ? `Thank you, ${name}. Doctor ke paas aapki information pahunch gayi hai.`
        : 'Doctor ke paas aapki information pahunch gayi hai aur wo jald hi bulayenge.',
    queuePosition: 'Queue Position',
    estimatedWait: 'Estimated wait time:',
    patientRef: 'Patient Ref:',
    showSummary: '▼ Submitted summary dekhein',
    hideSummary: '▲ Summary chupayein',
    doNotClose: 'Yeh page close na karein. Aapka queue number is session se juda hai.',
    switchDoctor: '[Switch to Doctor View →]',
  },
};

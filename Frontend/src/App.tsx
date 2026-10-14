import { useState } from 'react';
import PatientFlow from './components/patient/PatientFlow';
import DoctorLogin from './components/doctor/DoctorLogin';
import DoctorLayout from './components/doctor/DoctorLayout';
import PatientQueue from './components/doctor/PatientQueue';
import PatientOverview from './components/doctor/PatientOverview';

type AppScreen =
  | 'landing'
  | 'patient-flow'
  | 'doctor-login'
  | 'doctor-queue'
  | 'doctor-patient';

export default function App() {
  const [screen, setScreen] = useState<AppScreen>('landing');
  const [navActive, setNavActive] = useState('queue');
  const [selectedPatientId, setSelectedPatientId] = useState<string | undefined>();
  const [selectedSessionId, setSelectedSessionId] = useState<string | undefined>();
  const [returningPatient, setReturningPatient] = useState<{
    id: string;
    mrn?: string;
    name: string;
    dob?: string;
    phone?: string;
  } | undefined>();

  const handleNav = (id: string) => {
    setNavActive(id);
    setScreen('doctor-queue');
  };

  if (screen === 'patient-flow') {
    return (
      <PatientFlow
        initialPatient={returningPatient}
        onComplete={(patientId, sessionId) => {
          setReturningPatient(undefined);
          setSelectedPatientId(patientId);
          setSelectedSessionId(sessionId);
          setScreen(patientId ? 'doctor-patient' : 'doctor-queue');
        }}
      />
    );
  }

  if (screen === 'doctor-login') {
    return <DoctorLogin onLogin={() => setScreen('doctor-queue')} />;
  }

  if (screen === 'doctor-queue') {
    return (
      <DoctorLayout activeNav={navActive} onNav={handleNav} onLogout={() => setScreen('landing')}>
        <PatientQueue
          onOpenPatient={(patientId, sessionId) => {
            setSelectedPatientId(patientId);
            setSelectedSessionId(sessionId);
            setScreen('doctor-patient');
          }}
        />
      </DoctorLayout>
    );
  }

  if (screen === 'doctor-patient') {
    return (
      <DoctorLayout activeNav={navActive} onNav={handleNav} onLogout={() => setScreen('landing')}>
        <PatientOverview
          patientId={selectedPatientId}
          sessionId={selectedSessionId}
          onBack={() => setScreen('doctor-queue')}
          onStartNewVisit={(patient) => {
            setReturningPatient(patient);
            setScreen('patient-flow');
          }}
        />
      </DoctorLayout>
    );
  }


  // Landing / demo navigation
  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl">
        {/* Logo */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center">
              <span className="text-white text-xl font-bold" style={{ fontFamily: 'DM Sans, sans-serif' }}>M</span>
            </div>
            <div className="text-left">
              <div className="text-white text-xl font-bold" style={{ fontFamily: 'DM Sans, sans-serif' }}>Medscribe-Verify</div>
              <div className="text-slate-400 text-xs" style={{ fontFamily: 'DM Mono, monospace' }}>AI-assisted clinical workflow</div>
            </div>
          </div>
          <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
            A source-aware, conflict-aware patient record system. Every claim traced. Every record accountable.
          </p>
        </div>

        {/* Demo flows */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <button
            onClick={() => setScreen('patient-flow')}
            className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/50 rounded-2xl p-6 text-left transition-all group"
          >
            <div className="text-2xl mb-3">🧑‍⚕️</div>
            <div className="text-white font-semibold mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>Patient Intake Flow</div>
            <div className="text-slate-400 text-sm leading-relaxed">Welcome screen → adaptive questionnaire → symptom follow-ups → medical history → confirmation & queue</div>
            <div className="mt-4 text-blue-400 text-sm font-medium group-hover:text-blue-300 transition-colors">
              Start patient flow →
            </div>
          </button>

          <button
            onClick={() => setScreen('doctor-login')}
            className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/50 rounded-2xl p-6 text-left transition-all group"
          >
            <div className="text-2xl mb-3">🏥</div>
            <div className="text-white font-semibold mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>Doctor Workspace</div>
            <div className="text-slate-400 text-sm leading-relaxed">Login → patient queue → pre-consult summary → history timeline → transcript → SOAP note with verification → approval → record</div>
            <div className="mt-4 text-blue-400 text-sm font-medium group-hover:text-blue-300 transition-colors">
              Open doctor view →
            </div>
          </button>
        </div>

        {/* Feature highlights */}
        <div className="mt-10 grid grid-cols-3 gap-4">
          {[
            { icon: '🔍', label: 'Claim-level verification', desc: 'Every SOAP claim traced to transcript evidence' },
            { icon: '⚡', label: 'Conflict detection', desc: 'Intake vs consultation discrepancies surfaced automatically' },
            { icon: '📋', label: 'Source-aware records', desc: 'Patient-reported vs doctor-confirmed vs test-supported' },
          ].map(f => (
            <div key={f.label} className="text-center">
              <div className="text-xl mb-2">{f.icon}</div>
              <div className="text-white text-xs font-semibold mb-1">{f.label}</div>
              <div className="text-slate-500 text-xs leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>

        <div className="text-center mt-8 text-slate-600 text-xs" style={{ fontFamily: 'DM Mono, monospace' }}>
          Final-year project — Medscribe-Verify prototype
        </div>
      </div>
    </div>
  );
}

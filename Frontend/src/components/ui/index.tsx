import React, { useState, useRef, useEffect, useId, ReactNode } from 'react';
import { api } from '../../services/api';

// ── Source Badge ──────────────────────────────────────────────────────────────
type SourceType = 'patient-reported' | 'doctor-confirmed' | 'test-supported' | 'needs-confirmation' | 'ai-generated';

const SOURCE_CONFIG: Record<SourceType, { label: string; dot: string; bg: string; text: string; border: string }> = {
  'patient-reported': { label: 'Patient-Reported', dot: '#0EA5E9', bg: '#F0F9FF', text: '#0369A1', border: '#BAE6FD' },
  'doctor-confirmed': { label: 'Doctor-Confirmed', dot: '#16A34A', bg: '#F0FDF4', text: '#15803D', border: '#BBF7D0' },
  'test-supported': { label: 'Test-Supported', dot: '#7C3AED', bg: '#F5F3FF', text: '#6D28D9', border: '#DDD6FE' },
  'needs-confirmation': { label: 'Needs Confirmation', dot: '#D97706', bg: '#FFFBEB', text: '#B45309', border: '#FDE68A' },
  'ai-generated': { label: 'AI-Generated', dot: '#6366F1', bg: '#EEF2FF', text: '#4338CA', border: '#C7D2FE' },
};

export function SourceBadge({ type }: { type: SourceType }) {
  const c = SOURCE_CONFIG[type];
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium font-mono-label"
      style={{ backgroundColor: c.bg, color: c.text, border: `1px solid ${c.border}` }}>
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: c.dot }} />
      {c.label}
    </span>
  );
}

// ── Status Badge ──────────────────────────────────────────────────────────────
type VerifStatus = 'supported' | 'unsupported' | 'ambiguous';

const VERIF_CONFIG: Record<VerifStatus, { label: string; bg: string; text: string; border: string }> = {
  supported: { label: 'Supported', bg: '#F0FDF4', text: '#15803D', border: '#BBF7D0' },
  unsupported: { label: 'Unsupported', bg: '#FEF2F2', text: '#DC2626', border: '#FECACA' },
  ambiguous: { label: 'Ambiguous', bg: '#FFFBEB', text: '#B45309', border: '#FDE68A' },
};

export function VerifBadge({ status }: { status: VerifStatus }) {
  const c = VERIF_CONFIG[status];
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ backgroundColor: c.bg, color: c.text, border: `1px solid ${c.border}` }}>
      {status === 'supported' && '✓ '}
      {status === 'unsupported' && '✕ '}
      {status === 'ambiguous' && '~ '}
      {c.label}
    </span>
  );
}

// ── AI Notice Strip ───────────────────────────────────────────────────────────
export function AINotice({ message }: { message?: string }) {
  return (
    <div className="flex items-start gap-2.5 px-4 py-3 rounded-lg text-sm mb-4"
      style={{ backgroundColor: '#FEF9C3', border: '1px solid #FDE047', color: '#713F12' }}>
      <span className="text-base leading-none flex-shrink-0">⚠</span>
      <span>{message ?? 'AI-generated — review and approve before saving to patient record. You are responsible for the final record.'}</span>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-100 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

// ── Section Label ─────────────────────────────────────────────────────────────
export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3" style={{ fontFamily: 'DM Mono, monospace' }}>
      {children}
    </div>
  );
}

// ── Expandable Section ────────────────────────────────────────────────────────
export function Expandable({ title, children, defaultOpen = false, badge }: {
  title: string; children: ReactNode; defaultOpen?: boolean; badge?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-800 text-sm">{title}</span>
          {badge}
        </div>
        <span className="text-slate-400 text-sm transition-transform" style={{ transform: open ? 'rotate(180deg)' : 'none' }}>▾</span>
      </button>
      {open && <div className="px-4 pb-4 pt-2 bg-white border-t border-slate-50">{children}</div>}
    </div>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
export function Tabs({ tabs, active, onChange }: {
  tabs: { id: string; label: string; badge?: string | number }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex border-b border-slate-200 gap-0">
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${active === tab.id
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
        >
          {tab.label}
          {tab.badge !== undefined && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full font-mono ${active === tab.id ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'
              }`}>{tab.badge}</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Progress Steps ────────────────────────────────────────────────────────────
export function ProgressSteps({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center gap-0 w-full mb-8">
      {steps.map((step, i) => (
        <React.Fragment key={i}>
          <div className="flex flex-col items-center gap-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all ${i < current ? 'bg-blue-600 border-blue-600 text-white' :
                i === current ? 'bg-white border-blue-600 text-blue-600' :
                  'bg-white border-slate-200 text-slate-400'
              }`}>
              {i < current ? '✓' : i + 1}
            </div>
            <span className={`text-xs font-medium whitespace-nowrap ${i === current ? 'text-blue-600' : i < current ? 'text-slate-600' : 'text-slate-400'}`}>
              {step}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-0.5 mx-2 mb-4 ${i < current ? 'bg-blue-600' : 'bg-slate-200'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
export function Button({
  children, onClick, variant = 'primary', disabled = false, className = '', type = 'button', size = 'md'
}: {
  children: ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean; className?: string; type?: 'button' | 'submit'; size?: 'sm' | 'md' | 'lg';
}) {
  const base = 'inline-flex items-center justify-center font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-1';
  const sizes = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2.5 text-sm', lg: 'px-6 py-3 text-base' };
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 disabled:bg-blue-300',
    secondary: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 focus:ring-slate-300 disabled:opacity-50',
    ghost: 'text-slate-600 hover:bg-slate-100 focus:ring-slate-300',
    danger: 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 focus:ring-red-400',
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`${base} ${sizes[size]} ${variants[variant]} ${disabled ? 'cursor-not-allowed' : ''} ${className}`}>
      {children}
    </button>
  );
}

// ── Voice Button ──────────────────────────────────────────────────────────────
export function VoiceButton({
  onTranscribe,
  language,
  className = '',
}: {
  onTranscribe: (text: string) => void;
  language?: string;
  className?: string;
}) {
  const buttonId = useId();
  const [isStarting, setIsStarting] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);

  // Auto-dismiss errors after 5 seconds
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  // Isolate error state: when another voice button starts recording, clear this button's error
  useEffect(() => {
    const handleOtherVoiceStart = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: string }>;
      if (customEvent.detail?.id !== buttonId) {
        setError(null);
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          try {
            mediaRecorderRef.current.stop();
          } catch {
            // ignore
          }
          setRecording(false);
        }
      }
    };
    window.addEventListener('medscribe-voice-start', handleOtherVoiceStart);
    return () => window.removeEventListener('medscribe-voice-start', handleOtherVoiceStart);
  }, [buttonId]);

  const startRecording = async () => {
    if (isStarting || recording) return;
    setIsStarting(true);
    setError(null);

    // Notify all other voice buttons to clear their error and reset state
    window.dispatchEvent(new CustomEvent('medscribe-voice-start', { detail: { id: buttonId } }));

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          autoGainControl: true,
        },
      });
      chunksRef.current = [];

      let mimeType = 'audio/webm';
      if (typeof MediaRecorder !== 'undefined') {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          mimeType = 'audio/webm;codecs=opus';
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = 'audio/webm';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          mimeType = 'audio/mp4';
        } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
          mimeType = 'audio/ogg';
        }
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstart = () => {
        startTimeRef.current = Date.now();
        setIsStarting(false);
        setRecording(true);
      };

      recorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());

        const durationMs = Date.now() - startTimeRef.current;
        const audioBlob = new Blob(chunksRef.current, { type: mimeType });

        // Ensure minimum recording length (300ms) and meaningful data size before calling API
        if (durationMs < 300 || audioBlob.size < 800) {
          setError(
            language === 'hi'
              ? 'आवाज़ सुनाई नहीं दी, कृपया थोड़ा बोलकर रोकें'
              : language === 'hinglish'
                ? 'Awaaz sunayi nahi di, please thoda bolkar stop karein'
                : 'Could not detect clear speech, please speak again'
          );
          return;
        }

        const ext = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm';
        const filename = `voice_recording.${ext}`;

        try {
          setTranscribing(true);
          const res = await api.transcribeAudio(audioBlob, language, filename);
          if (res.text && res.text.trim()) {
            onTranscribe(res.text.trim());
          } else {
            setError(
              language === 'hi'
                ? 'आवाज़ समझ नहीं आई, कृपया दोबारा बोलें'
                : language === 'hinglish'
                  ? 'Awaaz samajh nahi aayi, please dobara bolein'
                  : 'Could not detect clear speech, please speak again'
            );
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Transcription failed';
          setError(msg);
        } finally {
          setTranscribing(false);
        }
      };

      // Collect data continuously in 100ms chunks so audio is always collected reliably
      recorder.start(100);
    } catch (err: unknown) {
      setIsStarting(false);
      const msg = err instanceof Error ? err.message : 'Microphone access denied';
      setError(
        language === 'hi'
          ? 'माइक्रोफ़ोन की अनुमति नहीं मिली'
          : language === 'hinglish'
            ? 'Microphone permission nahi mili'
            : msg
      );
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const idleLabel =
    language === 'hi'
      ? 'बोलकर लिखें'
      : language === 'hinglish'
        ? 'बोलकर लिखें (Voice)'
        : 'Voice';
  const stopLabel =
    language === 'hi'
      ? 'रोकें'
      : language === 'hinglish'
        ? 'रोकें (Stop)'
        : 'Stop';
  const transcribingLabel =
    language === 'hi'
      ? 'लिखा जा रहा है…'
      : language === 'hinglish'
        ? 'लिखा जा रहा है…'
        : 'Transcribing…';

  return (
    <div className={`inline-flex items-center gap-1.5 ${className}`}>
      {isStarting ? (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
          <span>{language === 'hi' ? 'शुरू हो रहा है…' : 'Starting…'}</span>
        </span>
      ) : recording ? (
        <button
          type="button"
          onClick={stopRecording}
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full hover:bg-red-100 transition-colors animate-pulse cursor-pointer"
          title="Recording voice. Click to stop and transcribe."
        >
          <span className="w-2 h-2 rounded-full bg-red-600 animate-ping" />
          <span>{stopLabel}</span>
        </button>
      ) : transcribing ? (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-full">
          <span className="w-2.5 h-2.5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <span>{transcribingLabel}</span>
        </span>
      ) : (
        <button
          type="button"
          onClick={startRecording}
          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-slate-600 hover:text-blue-700 bg-slate-100 hover:bg-blue-50 border border-slate-200 hover:border-blue-200 rounded-md transition-colors cursor-pointer"
          title={language === 'hi' ? 'बोलकर दर्ज करें (हिंदी / Hinglish / English)' : 'Speak in English, Hindi, or Hinglish'}
        >
          <span>🎙️</span>
          <span>{idleLabel}</span>
        </button>
      )}
      {error && (
        <span className="text-[11px] text-red-500 font-medium">⚠️ {error}</span>
      )}
    </div>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────────
export function Input({
  label,
  placeholder,
  value,
  onChange,
  error,
  type = 'text',
  required,
  onVoiceTranscribe,
  voiceLang,
  max,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  type?: string;
  required?: boolean;
  onVoiceTranscribe?: (text: string) => void;
  voiceLang?: string;
  max?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-700">
          {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
        {onVoiceTranscribe && (
          <VoiceButton onTranscribe={onVoiceTranscribe} language={voiceLang} />
        )}
      </div>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        max={max}
        className={`px-3 py-2.5 rounded-lg border text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${error ? 'border-red-400 bg-red-50' : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
      />
      {error && <span className="text-xs text-red-600 flex items-center gap-1">⚠️ {error}</span>}
    </div>
  );
}

// ── Textarea ──────────────────────────────────────────────────────────────────
export function Textarea({
  label,
  placeholder,
  value,
  onChange,
  rows = 4,
  onVoiceTranscribe,
  voiceLang,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  onVoiceTranscribe?: (text: string) => void;
  voiceLang?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-700">{label}</label>
        {onVoiceTranscribe && (
          <VoiceButton onTranscribe={onVoiceTranscribe} language={voiceLang} />
        )}
      </div>
      <textarea
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={rows}
        className="px-3 py-2.5 rounded-lg border border-slate-200 bg-white text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none hover:border-slate-300"
      />
    </div>
  );
}

// ── Status Queue Badge ────────────────────────────────────────────────────────
export function QueueBadge({ status }: { status: 'waiting' | 'in-consultation' | 'completed' }) {
  const configs = {
    waiting: { label: 'Waiting', bg: '#F1F5F9', text: '#475569', dot: '#94A3B8' },
    'in-consultation': { label: 'In Consultation', bg: '#EFF6FF', text: '#1D4ED8', dot: '#2563EB' },
    completed: { label: 'Completed', bg: '#F0FDF4', text: '#15803D', dot: '#16A34A' },
  };
  const c = configs[status];
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
      style={{ backgroundColor: c.bg, color: c.text }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: c.dot }} />
      {c.label}
    </span>
  );
}

// ── Intake Badge ──────────────────────────────────────────────────────────────
export function IntakeBadge({ status }: { status: 'complete' | 'pending' }) {
  return status === 'complete'
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700 border border-green-200">✓ Intake Complete</span>
    : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">⏳ Intake Pending</span>;
}

// ── Allergy Tag ───────────────────────────────────────────────────────────────
export function AllergyTag({ substance }: { substance: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
      ⚠ {substance}
    </span>
  );
}

// ── Symptom Tag ───────────────────────────────────────────────────────────────
export function SymptomTag({ label, selected, onClick }: { label: string; selected?: boolean; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${selected
          ? 'bg-blue-600 text-white border-blue-600'
          : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
        }`}
    >
      {label}
    </button>
  );
}

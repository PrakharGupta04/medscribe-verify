import { useState } from 'react';
import { Button } from '../ui';

interface DoctorLoginProps {
  onLogin: () => void;
}

export default function DoctorLogin({ onLogin }: DoctorLoginProps) {
  const [email, setEmail] = useState('j.patel@medclinic.nhs.uk');
  const [password, setPassword] = useState('••••••••');
  const [loading, setLoading] = useState(false);

  const handleLogin = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); onLogin(); }, 800);
  };

  return (
    <div className="min-h-screen flex">
      {/* Left sidebar */}
      <div className="hidden md:flex w-80 flex-col justify-between p-10 bg-blue-700 text-white">
        <div>
          <div className="flex items-center gap-2 mb-16">
            <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
              <span className="text-white font-bold text-sm">M</span>
            </div>
            <span className="font-semibold text-lg" style={{ fontFamily: 'DM Sans, sans-serif' }}>Medscribe-Verify</span>
          </div>
          <h1 className="text-3xl font-bold mb-3 leading-tight" style={{ fontFamily: 'DM Sans, sans-serif' }}>
            Clinical workflow,<br />verified.
          </h1>
          <p className="text-blue-200 text-sm leading-relaxed">
            AI-assisted documentation with source-aware verification. Every claim traced, every record accountable.
          </p>
        </div>
        <div className="space-y-3">
          {[
            { icon: '🔒', text: 'All activity is audit-logged' },
            { icon: '✓', text: 'AI output is always doctor-reviewed' },
            { icon: '📋', text: 'Source-aware patient records' },
          ].map(item => (
            <div key={item.text} className="flex items-center gap-2.5 text-sm text-blue-100">
              <span>{item.icon}</span>
              <span>{item.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center px-8 py-12 bg-slate-50">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold text-slate-900 mb-1" style={{ fontFamily: 'DM Sans, sans-serif' }}>Sign in</h2>
          <p className="text-slate-500 text-sm mb-8">Access is restricted to registered clinical staff.</p>

          <div className="flex flex-col gap-4 mb-6">
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1">Email address</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <Button onClick={handleLogin} disabled={loading} className="w-full" size="lg">
            {loading ? 'Signing in…' : 'Sign In'}
          </Button>

          <div className="mt-6 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs text-amber-800">⚠ All activity in this system is logged for clinical audit purposes.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

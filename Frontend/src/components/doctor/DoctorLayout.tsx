import { ReactNode } from 'react';

type NavItem = { id: string; label: string; icon: string; badge?: number };

const NAV_ITEMS: NavItem[] = [
  { id: 'queue', label: 'Queue', icon: '👥', badge: 3 },
  { id: 'patients', label: 'Patients', icon: '📋' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
];

interface DoctorLayoutProps {
  children: ReactNode;
  activeNav: string;
  onNav: (id: string) => void;
  onLogout: () => void;
}

export default function DoctorLayout({ children, activeNav, onNav, onLogout }: DoctorLayoutProps) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-100 flex flex-col">
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">M</span>
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-800" style={{ fontFamily: 'DM Sans, sans-serif' }}>Medscribe</div>
              <div className="text-xs text-slate-400 font-mono-label">Verify</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-0.5">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => onNav(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeNav === item.id
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {item.badge !== undefined && (
                <span className="ml-auto bg-blue-100 text-blue-700 text-xs rounded-full px-1.5 py-0.5 font-mono">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-100">
          <div className="flex items-center gap-2 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold">JP</div>
            <div>
              <div className="text-xs font-medium text-slate-800">Dr. J. Patel</div>
              <div className="text-xs text-slate-400">GP</div>
            </div>
          </div>
          <button onClick={onLogout} className="w-full text-left px-3 py-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}

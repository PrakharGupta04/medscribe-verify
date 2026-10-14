import { useState, useEffect, useCallback, useMemo } from 'react';
import { QueueBadge, IntakeBadge, Button } from '../ui';
import { api } from '../../services/api';
import type { QueueItem } from '../../types/intake';

interface PatientQueueProps {
  onOpenPatient: (patientId: string, sessionId: string) => void;
}

export default function PatientQueue({ onOpenPatient }: PatientQueueProps) {
  const [filter, setFilter] = useState<'all' | 'waiting' | 'in-consultation' | 'completed'>('all');
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [patientToRemove, setPatientToRemove] = useState<QueueItem | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const filters = ['all', 'waiting', 'in-consultation', 'completed'] as const;

  const todayFormatted = useMemo(() => {
    return new Intl.DateTimeFormat('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(new Date());
  }, []);

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getQueue();
      setQueue(res.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch queue';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleSeedDemo = async () => {
    try {
      setSeeding(true);
      setError(null);
      await api.seedDemoQueue();
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to seed demo patients';
      setError(msg);
    } finally {
      setSeeding(false);
    }
  };

  const filtered = filter === 'all' ? queue : queue.filter(p => p.status === filter);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs text-slate-400 font-mono-label mb-1">{todayFormatted}</div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'DM Sans, sans-serif' }}>Today's Queue</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={fetchQueue} disabled={loading}>
            {loading ? 'Refreshing…' : '↻ Refresh Queue'}
          </Button>
          {queue.length === 0 && !loading && (
            <Button variant="secondary" size="sm" onClick={handleSeedDemo} disabled={seeding}>
              {seeding ? 'Seeding Demo…' : '⚡ Load Demo Patients'}
            </Button>
          )}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>⚠</span>
            <span>{error}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={fetchQueue}>
            Try Again
          </Button>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 p-1 bg-slate-100 rounded-lg w-fit">
        {filters.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-all ${
              filter === f ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {f.replace('-', ' ')}
          </button>
        ))}
      </div>

      {/* Queue table */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="text-center py-16 text-slate-400">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <div className="text-sm">Loading clinical queue from server…</div>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                {['#', 'Patient', 'Wait', 'Chief Complaint', 'Pre-Consultation', 'Status', ''].map(col => (
                  <th key={col} className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono-label">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map(patient => (
                <tr key={patient.id} className="hover:bg-slate-50 transition-colors group">
                  <td className="px-4 py-4 text-sm text-slate-400 font-mono">
                    {patient.position ?? '—'}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-semibold text-slate-600">
                        {patient.patient_name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <span className="text-sm font-medium text-slate-800">{patient.patient_name}</span>
                        <div className="text-xs text-slate-400 font-mono-label">{patient.mrn}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-500 font-mono-label">{patient.wait_time}</td>
                  <td className="px-4 py-4 text-sm text-slate-700">{patient.complaint}</td>
                  <td className="px-4 py-4">
                    <IntakeBadge status={patient.intake_status} />
                  </td>
                  <td className="px-4 py-4">
                    <QueueBadge status={patient.status} />
                  </td>
                  <td className="px-4 py-4 text-right">
                    {patient.status === 'waiting' ? (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          onClick={() => onOpenPatient(patient.patient_id, patient.session_id)}
                          size="sm"
                        >
                          Start Consultation
                        </Button>
                        <button
                          type="button"
                          onClick={() => setPatientToRemove(patient)}
                          disabled={removingId === patient.id}
                          className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-red-700 hover:bg-red-50 border border-slate-200 hover:border-red-200 transition-colors cursor-pointer disabled:opacity-50"
                          title="Remove patient from today's queue"
                        >
                          Remove
                        </button>
                      </div>
                    ) : patient.status === 'completed' ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onOpenPatient(patient.patient_id, patient.session_id)}
                      >
                        View Record
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => onOpenPatient(patient.patient_id, patient.session_id)}
                      >
                        View
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-16 text-slate-400">
            <div className="text-3xl mb-2">📋</div>
            <div className="text-sm font-medium text-slate-600 mb-1">No patients in this view</div>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mb-4">
              Patients who complete the pre-consultation intake form will appear here automatically.
            </p>
            <Button variant="secondary" size="sm" onClick={handleSeedDemo} disabled={seeding}>
              {seeding ? 'Seeding…' : 'Load Demo Patients for Testing'}
            </Button>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Removing from Queue */}
      {patientToRemove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-slate-100">
            <div className="w-10 h-10 rounded-full bg-red-50 text-red-600 flex items-center justify-center text-lg font-bold mb-3">
              ⚠️
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-2">Remove from Today's Queue?</h3>
            <p className="text-sm text-slate-600 mb-2">
              Are you sure you want to remove <strong>{patientToRemove.patient_name}</strong> ({patientToRemove.mrn}) from today's queue?
            </p>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 mb-5">
              ✓ The patient's record, submitted intake responses, and historical visits will be safely preserved.
            </div>
            <div className="flex justify-end gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPatientToRemove(null)}
                disabled={removingId !== null}
              >
                Cancel
              </Button>
              <button
                type="button"
                disabled={removingId !== null}
                onClick={async () => {
                  try {
                    setRemovingId(patientToRemove.id);
                    await api.removeFromQueue(patientToRemove.id);
                    setPatientToRemove(null);
                    await fetchQueue();
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : 'Failed to remove patient from queue');
                  } finally {
                    setRemovingId(null);
                  }
                }}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50"
              >
                {removingId ? 'Removing…' : 'Remove from Queue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

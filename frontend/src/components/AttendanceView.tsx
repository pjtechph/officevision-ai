import React, { useState, useEffect } from 'react';
import { UserCheck, ShieldCheck, CheckCircle2, KeyRound } from 'lucide-react';
import type { AttendanceRecord } from '../types';

export const AttendanceView: React.FC = () => {
  const [employeeId, setEmployeeId] = useState('EMP-1042');
  const [workstationId, setWorkstationId] = useState('DESK-01');
  const [method, setMethod] = useState('BADGE_OR_WEB_PORTAL');
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const fetchRecords = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/attendance/records');
      if (res.ok) {
        const data = await res.json();
        setRecords(data.reverse());
      }
    } catch {
      // API offline
    }
  };

  useEffect(() => {
    fetchRecords();
  }, []);

  const handleCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!employeeId) return;

    setIsSubmitting(true);
    setMessage(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/attendance/check-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_id_code: employeeId,
          workstation_id: workstationId,
          verification_method: method,
        }),
      });

      if (res.ok) {
        setMessage(`Verified Check-In confirmed for ${employeeId} at ${workstationId}!`);
        fetchRecords();
      } else {
        setMessage('Failed to register check-in.');
      }
    } catch {
      setMessage('Error connecting to backend.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Policy Compliance Callout */}
      <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start space-x-3">
          <ShieldCheck className="h-6 w-6 text-emerald-600 dark:text-emerald-400 mt-1 flex-shrink-0" />
          <div>
            <h3 className="text-base font-bold text-emerald-900 dark:text-emerald-200">
              Responsible Workplace Monitoring Standard
            </h3>
            <p className="text-sm text-emerald-800 dark:text-emerald-300 mt-1 leading-relaxed">
              In accordance with OfficeVision AI governance principles, <strong>physical desk presence is strictly separated from verified attendance</strong>. Camera pose detections never assign personal biometric identity. Official employee attendance must be confirmed voluntarily via authorized check-in (badge, employee portal, or SSO). Absence from a desk is never automatically penalized or counted as absenteeism.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Check-In Submission Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <KeyRound className="h-5 w-5 text-emerald-500" />
            <span>Verified Attendance Portal</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Simulate a deliberate employee badge scan or portal check-in.
          </p>

          <form onSubmit={handleCheckIn} className="mt-5 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                Employee ID Code
              </label>
              <input
                type="text"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="e.g. EMP-1042"
                required
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                Assigned Workstation
              </label>
              <select
                value={workstationId}
                onChange={(e) => setWorkstationId(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="DESK-01">DESK-01 (Primary Workstation)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1">
                Verification Channel
              </label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="BADGE_OR_WEB_PORTAL">Employee Web Portal</option>
                <option value="RFID_BADGE_TAP">RFID Badge Tap</option>
                <option value="QR_MOBILE_PASS">Mobile QR Pass</option>
              </select>
            </div>

            {message && (
              <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
                {message}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 rounded-xl font-semibold text-sm bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all disabled:opacity-50"
            >
              {isSubmitting ? 'Recording...' : 'Record Verified Check-In'}
            </button>
          </form>
        </div>

        {/* Verified Attendance History Table */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <UserCheck className="h-5 w-5 text-emerald-500" />
                <span>Verified Attendance Records</span>
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Official operational logs established via authorized verification channels.
              </p>
            </div>
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              Total: {records.length}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-xs uppercase font-semibold text-slate-500">
                  <th className="py-2.5">Employee ID</th>
                  <th className="py-2.5">Workstation</th>
                  <th className="py-2.5">Channel</th>
                  <th className="py-2.5">Timestamp</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-xs">
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400 font-sans">
                      No attendance check-ins recorded yet today.
                    </td>
                  </tr>
                ) : (
                  records.map((rec) => (
                    <tr key={rec.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                      <td className="py-3 font-semibold text-slate-900 dark:text-white font-sans">
                        {rec.employee_id_code}
                      </td>
                      <td className="py-3 text-slate-600 dark:text-slate-300">{rec.workstation_id}</td>
                      <td className="py-3 text-slate-500 font-sans text-xs">{rec.verification_method}</td>
                      <td className="py-3 text-slate-500">{rec.check_in_time.slice(11, 19)}</td>
                      <td className="py-3 font-sans">
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>VERIFIED</span>
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

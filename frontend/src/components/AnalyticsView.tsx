import React from 'react';
import { BarChart3, TrendingUp, Activity, ShieldCheck, Clock, UserCheck } from 'lucide-react';
import type { Workstation, PresenceEvent, SystemHealth } from '../types';

interface AnalyticsViewProps {
  workstations: Workstation[];
  events: PresenceEvent[];
  health: SystemHealth | null;
  fps: number;
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({
  workstations,
  events,
  health,
  fps,
}) => {
  const occupiedCount = workstations.filter((w) => w.current_state.includes('OCCUPIED')).length;
  const occupancyRate = workstations.length > 0 ? Math.round((occupiedCount / workstations.length) * 100) : 0;

  const seatedCount = workstations.filter((w) => w.current_state === 'OCCUPIED_SEATED').length;
  const standingCount = workstations.filter((w) => w.current_state === 'OCCUPIED_STANDING').length;
  const transitionEvents = events.filter((e) => e.event_type === 'WORKSTATION_STATE_CHANGE');

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Utilization Rate</span>
            <TrendingUp className="h-5 w-5 text-emerald-500" />
          </div>
          <div className="mt-2 flex items-baseline">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">{occupancyRate}%</span>
            <span className="ml-2 text-xs text-slate-500">of capacity</span>
          </div>
          <div className="mt-3 w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2">
            <div className="bg-emerald-500 h-2 rounded-full transition-all duration-500" style={{ width: `${occupancyRate}%` }} />
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">State Transitions</span>
            <Activity className="h-5 w-5 text-cyan-500" />
          </div>
          <div className="mt-2 flex items-baseline">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">{transitionEvents.length}</span>
            <span className="ml-2 text-xs text-slate-500">Debounced events</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">Filtered with 3.0s anti-flicker hysteresis</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Posture Breakdown</span>
            <UserCheck className="h-5 w-5 text-purple-500" />
          </div>
          <div className="mt-2 flex items-baseline space-x-3">
            <div>
              <span className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">{seatedCount}</span>
              <span className="ml-1 text-xs text-slate-500">Seated</span>
            </div>
            <div>
              <span className="text-2xl font-extrabold text-amber-600 dark:text-amber-400">{standingCount}</span>
              <span className="ml-1 text-xs text-slate-500">Standing</span>
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-400">Classified by YOLO26-Pose geometry</p>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vision Engine FPS</span>
            <Clock className="h-5 w-5 text-amber-500" />
          </div>
          <div className="mt-2 flex items-baseline">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">{fps.toFixed(1)}</span>
            <span className="ml-2 text-xs text-slate-500">Frames/Sec</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">YOLO26-Pose + ByteTrack</p>
        </div>
      </div>

      {/* Main Analytics Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workstation Status Breakdown */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <BarChart3 className="h-5 w-5 text-emerald-500" />
            <span>Workstation Occupancy Status</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time status of all configured spatial zones.
          </p>

          <div className="mt-6 space-y-4">
            {workstations.map((desk) => {
              const isOccupied = desk.current_state.includes('OCCUPIED');
              const isSeated = desk.current_state === 'OCCUPIED_SEATED';
              return (
                <div key={desk.id} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div>
                    <span className="font-semibold text-sm text-slate-900 dark:text-white">{desk.name}</span>
                    <span className="ml-2 text-xs font-mono text-slate-500">{desk.id}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                        isOccupied
                          ? isSeated
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                          : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {desk.current_state.replace('OCCUPIED_', '')}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Operational Guardrails & Capacity Policy */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <ShieldCheck className="h-5 w-5 text-emerald-500" />
              <span>Operational Analytics Safeguards</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Responsible workplace monitoring guidelines enforced in system reporting.
            </p>

            <ul className="mt-5 space-y-3 text-xs text-slate-600 dark:text-slate-300">
              <li className="flex items-start space-x-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span><strong>No Individual Productivity Scoring:</strong> Camera-derived seated times are strictly used for office capacity and desk ergonomics, never for performance appraisals.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span><strong>Zero Facial Recognition:</strong> Vision models strictly process 17 anonymous skeletal coordinates.</span>
              </li>
              <li className="flex items-start space-x-2">
                <span className="text-emerald-500 font-bold">✓</span>
                <span><strong>Absence Debouncing:</strong> Temporary departure from a desk for coffee or discussion is protected by hysteresis debouncing.</span>
              </li>
            </ul>
          </div>

          <div className="mt-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-500">
            <strong>System Uptime:</strong> {health?.uptime_seconds ? `${Math.round(health.uptime_seconds / 60)} minutes` : 'Active'} | <strong>Total Desks Registered:</strong> {workstations.length}
          </div>
        </div>
      </div>
    </div>
  );
};

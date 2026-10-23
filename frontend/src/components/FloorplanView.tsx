import React, { useState } from 'react';
import { User, Armchair, Clock, ShieldAlert, Video, Eye, EyeOff, Settings } from 'lucide-react';
import type { Workstation } from '../types';

interface FloorplanViewProps {
  workstations: Workstation[];
  activeGracePeriod: boolean;
  gracePeriodRemaining: number;
  onNavigateToManager?: () => void;
}

export const FloorplanView: React.FC<FloorplanViewProps> = ({
  workstations,
  activeGracePeriod,
  gracePeriodRemaining,
  onNavigateToManager,
}) => {
  const [showCameraStream, setShowCameraStream] = useState(true);
  const occupiedCount = workstations.filter((w) => w.current_state.includes('OCCUPIED')).length;
  const vacantCount = workstations.filter((w) => w.current_state === 'VACANT').length;

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Desks */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Monitored Desks</span>
            <Armchair className="h-5 w-5 text-slate-400" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <div>
              <span className="text-3xl font-extrabold text-slate-900 dark:text-white">{workstations.length}</span>
              <span className="ml-2 text-xs text-slate-500">Active Zones</span>
            </div>
            {onNavigateToManager && (
              <button
                onClick={onNavigateToManager}
                className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline flex items-center space-x-1"
              >
                <Settings className="h-3.5 w-3.5" />
                <span>Manage</span>
              </button>
            )}
          </div>
        </div>

        {/* Occupied Now */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Occupied Desks</span>
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <div className="mt-2 flex items-baseline">
            <span className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">{occupiedCount}</span>
            <span className="ml-2 text-xs text-slate-500">
              ({workstations.length ? Math.round((occupiedCount / workstations.length) * 100) : 0}% Occupancy)
            </span>
          </div>
        </div>

        {/* Vacant Desks */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Vacant Desks</span>
            <div className="h-2.5 w-2.5 rounded-full bg-slate-300 dark:bg-slate-700" />
          </div>
          <div className="mt-2 flex items-baseline">
            <span className="text-3xl font-extrabold text-slate-700 dark:text-slate-300">{vacantCount}</span>
            <span className="ml-2 text-xs text-slate-500">Available</span>
          </div>
        </div>

        {/* Anti-Flicker Grace Status */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider">Anti-Flicker Status</span>
            <Clock className="h-5 w-5 text-amber-500" />
          </div>
          <div className="mt-2 flex items-baseline">
            {activeGracePeriod ? (
              <>
                <span className="text-2xl font-bold text-amber-600 dark:text-amber-400">{gracePeriodRemaining.toFixed(1)}s</span>
                <span className="ml-2 text-xs text-amber-600 font-medium animate-pulse">Grace Period Active</span>
              </>
            ) : (
              <>
                <span className="text-xl font-bold text-slate-900 dark:text-white">Active</span>
                <span className="ml-2 text-xs text-slate-500">Hysteresis (3.0s)</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Embedded Live Camera Feed inside Dashboard */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="px-5 py-3.5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/80 dark:bg-slate-800/40">
          <div className="flex items-center space-x-2.5">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 flex items-center space-x-1.5">
              <Video className="h-4 w-4 text-rose-500" />
              <span>Live Camera Stream (CAM-01)</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              YOLO26-Pose + ByteTrack
            </span>
          </div>

          <button
            onClick={() => setShowCameraStream(!showCameraStream)}
            className="flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-700/60 transition-colors"
          >
            {showCameraStream ? (
              <>
                <EyeOff className="h-3.5 w-3.5" />
                <span>Hide Stream</span>
              </>
            ) : (
              <>
                <Eye className="h-3.5 w-3.5" />
                <span>Show Stream</span>
              </>
            )}
          </button>
        </div>

        {showCameraStream && (
          <div className="relative aspect-video max-h-[500px] w-full flex items-center justify-center bg-slate-950">
            <img
              src="http://127.0.0.1:8000/api/v1/video-feed"
              alt="Live Camera Video Stream"
              className="w-full h-full object-contain"
              onError={(e) => {
                // If edge worker is offline, show fallback placeholder
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          </div>
        )}
      </div>

      {/* Privacy Notice Banner */}
      <div className="bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-800/60 rounded-xl p-4 flex items-start space-x-3">
        <ShieldAlert className="h-5 w-5 text-cyan-600 dark:text-cyan-400 mt-0.5 flex-shrink-0" />
        <div className="text-xs text-cyan-800 dark:text-cyan-300 leading-relaxed">
          <strong>Privacy Guardrail:</strong> Workstation presence is monitored through anonymous body keypoint geometry. No facial recognition or biometric identification is performed. Workstation presence reflects physical desk occupancy, not individual employee productivity.
        </div>
      </div>

      {/* Workstation Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
        {workstations.map((desk) => {
          const isOccupied = desk.current_state.includes('OCCUPIED');
          const isSeated = desk.current_state === 'OCCUPIED_SEATED';
          const isStanding = desk.current_state === 'OCCUPIED_STANDING';

          return (
            <div
              key={desk.id}
              className={`relative overflow-hidden rounded-2xl border transition-all duration-300 p-6 bg-white dark:bg-slate-900 ${
                isOccupied
                  ? isSeated
                    ? 'border-emerald-400/80 shadow-lg shadow-emerald-500/10'
                    : 'border-amber-400/80 shadow-lg shadow-amber-500/10'
                  : 'border-slate-200 dark:border-slate-800'
              }`}
            >
              {/* Header: Desk Code & Pulse */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">{desk.name}</h3>
                  <span className="text-xs font-mono text-slate-500">{desk.id}</span>
                </div>
                <div
                  className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5 ${
                    isOccupied
                      ? isSeated
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                      : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                  }`}
                >
                  <div
                    className={`h-2 w-2 rounded-full ${
                      isOccupied ? (isSeated ? 'bg-emerald-500' : 'bg-amber-500') : 'bg-slate-400'
                    }`}
                  />
                  <span>
                    {isOccupied ? (isSeated ? 'OCCUPIED (SEATED)' : 'OCCUPIED (STANDING)') : 'VACANT'}
                  </span>
                </div>
              </div>

              {/* Status Details */}
              <div className="mt-6 space-y-3">
                <div className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-500 dark:text-slate-400 flex items-center space-x-1.5">
                    <User className="h-4 w-4" />
                    <span>Tracked Occupant:</span>
                  </span>
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {desk.active_track_id ? `Person #${desk.active_track_id}` : 'None'}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm py-1.5 border-b border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-500 dark:text-slate-400 flex items-center space-x-1.5">
                    <Clock className="h-4 w-4" />
                    <span>Session Duration:</span>
                  </span>
                  <span className="font-mono font-medium text-slate-900 dark:text-white">
                    {formatDuration(desk.time_in_state_sec || 0)}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm py-1.5">
                  <span className="text-slate-500 dark:text-slate-400">Posture Classification:</span>
                  <span
                    className={`font-semibold ${
                      isSeated
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : isStanding
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-slate-400'
                    }`}
                  >
                    {isSeated ? 'Seated (Desk)' : isStanding ? 'Standing (Active)' : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Mini SVG Floorplan Polygon Schematic */}
              <div className="mt-5 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex items-center justify-center">
                <svg viewBox="0 0 100 100" className="h-20 w-36">
                  {/* Outer boundaries */}
                  <rect x="5" y="5" width="90" height="90" rx="8" fill="none" stroke="currentColor" className="text-slate-200 dark:text-slate-700" strokeDasharray="3 3" />
                  {/* Desk Polygon */}
                  {desk.polygon_normalized && desk.polygon_normalized.length >= 3 && (
                    <polygon
                      points={desk.polygon_normalized.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                      className={
                        isOccupied
                          ? isSeated
                            ? 'fill-emerald-500/20 stroke-emerald-500'
                            : 'fill-amber-500/20 stroke-amber-500'
                          : 'fill-slate-500/10 stroke-slate-400'
                      }
                      strokeWidth="2"
                    />
                  )}
                  {/* Person Anchor Marker */}
                  {isOccupied && (
                    <circle cx="50" cy="55" r="4" className={isSeated ? 'fill-emerald-500' : 'fill-amber-500'} />
                  )}
                </svg>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

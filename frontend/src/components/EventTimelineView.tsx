import React, { useState } from 'react';
import { Clock, ArrowRight, RefreshCw, UserCheck } from 'lucide-react';
import type { PresenceEvent } from '../types';

interface EventTimelineViewProps {
  events: PresenceEvent[];
  onRefresh: () => void;
}

export const EventTimelineView: React.FC<EventTimelineViewProps> = ({ events, onRefresh }) => {
  const [filterWorkstation, setFilterWorkstation] = useState<string>('ALL');

  // Extract unique workstation IDs present in events
  const uniqueWorkstations = Array.from(new Set(events.map((e) => e.workstation_id).filter(Boolean)));

  const filteredEvents = events.filter((ev) => {
    if (filterWorkstation === 'ALL') return true;
    return ev.workstation_id === filterWorkstation;
  });

  return (
    <div className="space-y-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <Clock className="h-5 w-5 text-emerald-500" />
            <span>Presence & State Change Timeline</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time chronological audit trail received over WebSocket from the AI Edge Service.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Workstation Filter Pills */}
          <div className="flex items-center space-x-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
            <button
              onClick={() => setFilterWorkstation('ALL')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                filterWorkstation === 'ALL'
                  ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
              }`}
            >
              All Desks
            </button>
            {uniqueWorkstations.map((wid) => (
              <button
                key={wid}
                onClick={() => setFilterWorkstation(wid)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  filterWorkstation === wid
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                }`}
              >
                {wid}
              </button>
            ))}
          </div>

          <button
            onClick={onRefresh}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
            title="Refresh Timeline"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Events List */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        {filteredEvents.length === 0 ? (
          <div className="p-12 text-center text-slate-500 dark:text-slate-400">
            <Clock className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p className="font-medium">No state change events logged yet.</p>
            <p className="text-xs mt-1">Occupancy state changes will appear here in real time.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {filteredEvents.map((ev, idx) => {
              const isOccupied = ev.new_state?.includes('OCCUPIED');

              return (
                <div key={idx} className="p-5 flex items-start space-x-4 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                  {/* Event Icon Badge */}
                  <div
                    className={`h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      isOccupied
                        ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-400'
                        : 'bg-amber-100 text-amber-600 dark:bg-amber-950/80 dark:text-amber-400'
                    }`}
                  >
                    <UserCheck className="h-5 w-5" />
                  </div>

                  {/* Event Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
                        {ev.formatted_time || new Date((ev.timestamp || 0) * 1000).toLocaleTimeString()}
                      </span>
                      <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                        {ev.workstation_id || 'DESK-01'}
                      </span>
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-mono text-xs text-slate-500">{ev.previous_state || 'UNKNOWN'}</span>
                      <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                      <span className="font-bold text-slate-900 dark:text-white">{ev.new_state}</span>
                      {ev.track_id && (
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300">
                          Person #{ev.track_id}
                        </span>
                      )}
                      {ev.duration_in_prev_state_sec && ev.duration_in_prev_state_sec > 0 && (
                        <span className="text-xs text-slate-400">
                          (was {ev.previous_state} for {ev.duration_in_prev_state_sec.toFixed(1)}s)
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

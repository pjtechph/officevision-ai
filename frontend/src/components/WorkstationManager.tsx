import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Plus,
  Trash2,
  Edit2,
  Play,
  Square,
  RotateCw,
  Video,
  CheckCircle2,
  AlertCircle,
  PenTool,
  Armchair,
  Info,
} from 'lucide-react';
import type { Workstation, ServiceStatus } from '../types';

interface WorkstationManagerProps {
  workstations: Workstation[];
  onRefresh: () => void;
  onNavigateToEditor: (deskId: string) => void;
}

export const WorkstationManager: React.FC<WorkstationManagerProps> = ({
  workstations,
  onRefresh,
  onNavigateToEditor,
}) => {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [cameraSource, setCameraSource] = useState<string>('0');
  const [isControlling, setIsControlling] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modal states
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedDesk, setSelectedDesk] = useState<Workstation | null>(null);

  // Form states
  const [newId, setNewId] = useState('');
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');

  const fetchServiceStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/service/status');
      if (res.ok) {
        const data = await res.json();
        setServiceStatus(data);
        if (data.camera_source) {
          setCameraSource(data.camera_source);
        }
      }
    } catch {
      // Backend offline
    }
  };

  useEffect(() => {
    fetchServiceStatus();
    const interval = setInterval(fetchServiceStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleServiceAction = async (action: 'start' | 'stop' | 'restart') => {
    setIsControlling(true);
    setFeedback(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/service/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          camera_source: cameraSource,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setFeedback({
          type: 'success',
          message: data.message || `Service action '${action}' completed successfully!`,
        });
        fetchServiceStatus();
      } else {
        setFeedback({
          type: 'error',
          message: data.detail || `Failed to execute ${action}.`,
        });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Failed to communicate with API server.' });
    } finally {
      setIsControlling(false);
    }
  };

  const handleAddWorkstation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newId.trim() || !newName.trim()) return;

    // Default centered normalized polygon quad
    const defaultPoly: [number, number][] = [
      [0.25, 0.25],
      [0.75, 0.25],
      [0.75, 0.75],
      [0.25, 0.75],
    ];

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/workstations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: newId.trim().toUpperCase(),
          name: newName.trim(),
          description: newDesc.trim(),
          polygon_normalized: defaultPoly,
        }),
      });

      if (res.ok) {
        setFeedback({
          type: 'success',
          message: `Workstation '${newId.trim().toUpperCase()}' created and synced with Edge AI Engine!`,
        });
        setIsAddOpen(false);
        setNewId('');
        setNewName('');
        setNewDesc('');
        onRefresh();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to create workstation.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error connecting to API.' });
    }
  };

  const handleEditWorkstation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDesk || !editName.trim()) return;

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/workstations/${selectedDesk.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName.trim(),
          description: editDesc.trim(),
        }),
      });

      if (res.ok) {
        setFeedback({
          type: 'success',
          message: `Workstation '${selectedDesk.id}' updated and hot-reloaded!`,
        });
        setIsEditOpen(false);
        setSelectedDesk(null);
        onRefresh();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to update workstation.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error connecting to API.' });
    }
  };

  const handleDeleteWorkstation = async (wid: string) => {
    if (!window.confirm(`Are you sure you want to delete workstation zone '${wid}'?`)) {
      return;
    }

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/workstations/${wid}`, {
        method: 'DELETE',
      });

      if (res.ok) {
        setFeedback({
          type: 'success',
          message: `Workstation '${wid}' removed and Edge AI Engine hot-reloaded!`,
        });
        onRefresh();
      } else {
        const err = await res.json();
        setFeedback({ type: 'error', message: err.detail || 'Failed to delete workstation.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error connecting to API.' });
    }
  };

  const openEditModal = (desk: Workstation) => {
    setSelectedDesk(desk);
    setEditName(desk.name);
    setEditDesc(desk.description || '');
    setIsEditOpen(true);
  };

  const isAiConnected = serviceStatus?.ai_vision_connected ?? false;
  const isProcRunning = serviceStatus?.running ?? false;

  return (
    <div className="space-y-8">
      {/* Feedback Banner */}
      {feedback && (
        <div
          className={`p-4 rounded-xl flex items-center justify-between text-sm ${
            feedback.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
              : 'bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-xs font-semibold underline ml-4 hover:opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Edge AI Vision Service Control Panel */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <Sliders className="h-5 w-5 text-emerald-500" />
              <span>Edge AI Vision Service Control</span>
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Control the local or edge inference microservice and switch camera stream sources dynamically.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5 ${
                isAiConnected
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                  : 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
              }`}
            >
              <div
                className={`h-2 w-2 rounded-full ${
                  isAiConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                }`}
              />
              <span>{isAiConnected ? 'AI STREAMING' : isProcRunning ? 'STARTING UP' : 'OFFLINE / STANDBY'}</span>
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          {/* Camera Source Selector */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
              <Video className="h-4 w-4 text-emerald-500" />
              <span>Camera Stream Source</span>
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={cameraSource}
                onChange={(e) => setCameraSource(e.target.value)}
                placeholder="0 (webcam) or http://<ip>:8080/video"
                className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button
                onClick={() => handleServiceAction('restart')}
                disabled={isControlling}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-white dark:bg-slate-700 hover:bg-slate-700 transition-colors disabled:opacity-50 flex items-center space-x-1"
                title="Restart with new source"
              >
                <RotateCw className={`h-3.5 w-3.5 ${isControlling ? 'animate-spin' : ''}`} />
                <span>Apply Source</span>
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Enter <code>0</code> or <code>1</code> for local webcam, or an HTTP / RTSP stream URL for IP cameras.
            </p>
          </div>

          {/* Service Process Actions */}
          <div className="space-y-3 flex flex-col justify-end">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
              Microservice Execution Controls
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => handleServiceAction('start')}
                disabled={isControlling || isProcRunning}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm transition-all disabled:opacity-40"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Start Service</span>
              </button>

              <button
                onClick={() => handleServiceAction('stop')}
                disabled={isControlling || !isProcRunning}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-sm transition-all disabled:opacity-40"
              >
                <Square className="h-3.5 w-3.5" />
                <span>Stop Service</span>
              </button>

              <button
                onClick={() => handleServiceAction('restart')}
                disabled={isControlling}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 transition-all disabled:opacity-40"
              >
                <RotateCw className={`h-3.5 w-3.5 ${isControlling ? 'animate-spin' : ''}`} />
                <span>Restart</span>
              </button>
            </div>
            <div className="text-xs text-slate-400 flex items-center space-x-2">
              <Info className="h-3.5 w-3.5" />
              <span>
                {serviceStatus?.pid
                  ? `Managed PID: ${serviceStatus.pid} (Uptime: ${serviceStatus.uptime_seconds || 0}s)`
                  : 'Independent edge process connection supported'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Workstations Management Table & Actions */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <Armchair className="h-5 w-5 text-emerald-500" />
              <span>Registered Workstations ({workstations.length})</span>
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Add, rename, or delete desk detection zones. All changes are hot-reloaded into the AI engine instantly.
            </p>
          </div>

          <button
            onClick={() => setIsAddOpen(true)}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all"
          >
            <Plus className="h-4 w-4" />
            <span>Add Workstation</span>
          </button>
        </div>

        {workstations.length === 0 ? (
          <div className="p-12 text-center text-slate-500 dark:text-slate-400">
            <Armchair className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p className="font-medium">No workstations configured.</p>
            <p className="text-xs mt-1">Click "Add Workstation" above to register your first desk zone.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {workstations.map((desk) => {
              const vertexCount = desk.polygon_normalized?.length || 0;
              const isOccupied = desk.current_state.includes('OCCUPIED');

              return (
                <div
                  key={desk.id}
                  className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex items-start space-x-4">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center flex-shrink-0 font-bold font-mono text-xs ${
                      isOccupied
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                    }`}>
                      {desk.id.replace('DESK-', 'D')}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-base text-slate-900 dark:text-white">{desk.name}</span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                          {desk.id}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                        {desk.description || 'No description provided'}
                      </p>
                      <div className="mt-2 flex items-center space-x-3 text-xs text-slate-400">
                        <span>Vertices: {vertexCount}</span>
                        <span>•</span>
                        <span>State: {desk.current_state}</span>
                      </div>
                    </div>
                  </div>

                  {/* Actions for Workstation */}
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => onNavigateToEditor(desk.id)}
                      className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
                      title="Adjust boundary polygon"
                    >
                      <PenTool className="h-3.5 w-3.5 text-emerald-500" />
                      <span>Calibrate Zone</span>
                    </button>

                    <button
                      onClick={() => openEditModal(desk)}
                      className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
                      title="Edit name and description"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>

                    <button
                      onClick={() => handleDeleteWorkstation(desk.id)}
                      className="p-1.5 rounded-lg border border-rose-200 dark:border-rose-900/60 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 dark:text-rose-400 transition-colors"
                      title="Delete workstation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal: Add Workstation */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <Plus className="h-5 w-5 text-emerald-500" />
              <span>Add New Workstation</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Create a new monitoring zone. Boundary polygon will be initialized with a standard quad and can be calibrated afterwards.
            </p>

            <form onSubmit={handleAddWorkstation} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase mb-1">
                  Workstation ID (Unique)
                </label>
                <input
                  type="text"
                  required
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  placeholder="e.g. DESK-03"
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Workstation 3 (Window)"
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase mb-1">
                  Description (Optional)
                </label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="e.g. Stand-up focus workstation"
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsAddOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20"
                >
                  Create & Hot-Reload
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit Workstation */}
      {isEditOpen && selectedDesk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <Edit2 className="h-5 w-5 text-emerald-500" />
              <span>Edit {selectedDesk.id}</span>
            </h3>

            <form onSubmit={handleEditWorkstation} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsEditOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

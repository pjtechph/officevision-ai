import React, { useState, useRef, useEffect } from 'react';
import { Save, RotateCcw, Check, PenTool, Info, Video, ChevronDown } from 'lucide-react';
import type { Workstation } from '../types';

interface PolygonEditorProps {
  workstations: Workstation[];
  onSaveSuccess: () => void;
}

export const PolygonEditor: React.FC<PolygonEditorProps> = ({ workstations, onSaveSuccess }) => {
  const [selectedDeskId, setSelectedDeskId] = useState<string>(workstations[0]?.id || 'DESK-01');
  const [points, setPoints] = useState<[number, number][]>([]);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const svgRef = useRef<SVGSVGElement | null>(null);

  // Sync selected desk
  const selectedDesk = workstations.find((w) => w.id === selectedDeskId) || workstations[0] || null;

  // Load points when selected workstation changes
  useEffect(() => {
    if (selectedDesk && selectedDesk.polygon_normalized) {
      setPoints([...selectedDesk.polygon_normalized]);
      setSaveMessage(null);
    }
  }, [selectedDeskId, selectedDesk]);

  const handlePointerDown = (e: React.PointerEvent, index: number) => {
    e.stopPropagation();
    try {
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    } catch {
      // ignore
    }
    setDraggingIndex(index);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (draggingIndex === null || !svgRef.current) return;

    const rect = svgRef.current.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const nx = Math.max(0.01, Math.min(0.99, (e.clientX - rect.left) / rect.width));
    const ny = Math.max(0.01, Math.min(0.99, (e.clientY - rect.top) / rect.height));

    setPoints((prev) => {
      const next: [number, number][] = prev.map((pt, i) =>
        i === draggingIndex ? [parseFloat(nx.toFixed(4)), parseFloat(ny.toFixed(4))] : pt
      );
      return next;
    });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (draggingIndex !== null) {
      try {
        if ((e.currentTarget as Element).hasPointerCapture(e.pointerId)) {
          (e.currentTarget as Element).releasePointerCapture(e.pointerId);
        }
      } catch {
        // ignore
      }
      setDraggingIndex(null);
    }
  };

  const handleReset = () => {
    if (selectedDesk) {
      setPoints([...selectedDesk.polygon_normalized]);
      setSaveMessage(null);
    }
  };

  const handleSave = async () => {
    if (!selectedDesk || points.length < 3) return;

    setIsSaving(true);
    setSaveMessage(null);

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/workstations/${selectedDesk.id}/polygon`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ polygon_normalized: points }),
      });

      if (res.ok) {
        setSaveMessage(`Polygon updated for ${selectedDesk.name || selectedDesk.id}! Saved to configuration.`);
        onSaveSuccess();
      } else {
        setSaveMessage('Failed to save polygon.');
      }
    } catch {
      setSaveMessage('Error connecting to backend API.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Control Bar Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <PenTool className="h-5 w-5 text-emerald-500" />
            <span>Interactive Desk Polygon Editor</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Drag the corner handles directly over the live camera backdrop to calibrate detection zones.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Workstation Selector Dropdown */}
          <div className="relative">
            <select
              value={selectedDeskId}
              onChange={(e) => setSelectedDeskId(e.target.value)}
              className="appearance-none bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white text-sm font-semibold rounded-xl pl-4 pr-10 py-2 hover:bg-slate-200/60 dark:hover:bg-slate-700/60 cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {workstations.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.id})
                </option>
              ))}
            </select>
            <ChevronDown className="h-4 w-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <button
            onClick={handleReset}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            <span>Reset</span>
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center space-x-1.5 px-5 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all disabled:opacity-50"
          >
            {isSaving ? (
              <span>Saving...</span>
            ) : (
              <>
                <Save className="h-4 w-4" />
                <span>Save to Backend</span>
              </>
            )}
          </button>
        </div>
      </div>

      {saveMessage && (
        <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl p-4 flex items-center space-x-2 text-sm text-emerald-800 dark:text-emerald-300">
          <Check className="h-5 w-5 text-emerald-500 flex-shrink-0" />
          <span>{saveMessage}</span>
        </div>
      )}

      {/* Interactive Canvas Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="relative aspect-video max-w-4xl mx-auto rounded-xl overflow-hidden border border-slate-700 bg-black select-none">
          {/* Real Live Camera Backdrop */}
          <img
            src="http://127.0.0.1:8000/api/v1/video-feed"
            alt="Live Camera Calibration Feed"
            className="absolute inset-0 w-full h-full object-contain pointer-events-none opacity-85"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />

          {/* Guide Overlay Info Badge */}
          <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2 text-xs text-white z-10 pointer-events-none">
            <Video className="h-3.5 w-3.5 text-emerald-400" />
            <span>Editing: <strong>{selectedDesk?.name || selectedDeskId}</strong></span>
          </div>

          {/* SVG Interactive Canvas Layer */}
          <svg
            ref={svgRef}
            viewBox="0 0 1000 1000"
            preserveAspectRatio="none"
            className="absolute inset-0 w-full h-full cursor-crosshair z-20 touch-none"
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          >
            {/* Draw other workstations as reference (semi-transparent) */}
            {workstations
              .filter((w) => w.id !== selectedDeskId && w.polygon_normalized && w.polygon_normalized.length >= 3)
              .map((other) => (
                <polygon
                  key={other.id}
                  points={other.polygon_normalized.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                  fill="rgba(100, 116, 139, 0.15)"
                  stroke="#64748b"
                  strokeWidth="2"
                  strokeDasharray="6 4"
                  className="pointer-events-none"
                />
              ))}

            {/* Selected Workstation Polygon Fill & Outline */}
            {points.length >= 3 && (
              <polygon
                points={points.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                fill="rgba(16, 185, 129, 0.25)"
                stroke="#10b981"
                strokeWidth="4"
              />
            )}

            {/* Corner Draggable Handles */}
            {points.map(([x, y], idx) => (
              <g
                key={idx}
                className="cursor-grab active:cursor-grabbing"
                onPointerDown={(e) => handlePointerDown(e, idx)}
              >
                {/* Outer Glow Circle */}
                <circle
                  cx={x * 1000}
                  cy={y * 1000}
                  r="28"
                  fill="rgba(16, 185, 129, 0.35)"
                />
                {/* Inner Pin */}
                <circle
                  cx={x * 1000}
                  cy={y * 1000}
                  r="14"
                  fill="#ffffff"
                  stroke="#10b981"
                  strokeWidth="4"
                />
                {/* Vertex Label */}
                <text
                  x={x * 1000 + 18}
                  y={y * 1000 - 14}
                  fill="#10b981"
                  fontSize="32"
                  fontWeight="bold"
                  className="select-none pointer-events-none"
                >
                  P{idx + 1}
                </text>
              </g>
            ))}
          </svg>
        </div>

        {/* Normalized Coordinates Readout */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-slate-500 bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
          <div className="flex items-center space-x-2">
            <Info className="h-4 w-4 text-slate-400" />
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Normalized Vertex Coordinates for {selectedDesk?.id}:
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {points.map(([x, y], i) => (
              <span key={i} className="bg-white dark:bg-slate-900 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700">
                <strong>P{i + 1}:</strong> [{x.toFixed(4)}, {y.toFixed(4)}]
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

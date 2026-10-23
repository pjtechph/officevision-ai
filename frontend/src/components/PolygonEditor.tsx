import React, { useState, useRef, useEffect } from 'react';
import {
  Save,
  RotateCcw,
  Check,
  PenTool,
  Info,
  Video,
  PlusCircle,
  MinusCircle,
  Crosshair,
  Maximize2,
  Armchair,
} from 'lucide-react';
import type { Workstation } from '../types';

interface PolygonEditorProps {
  workstations: Workstation[];
  initialSelectedId?: string;
  onSaveSuccess: () => void;
}

const getApiBaseUrl = () => {
  const host = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
  return `http://${host}:8000/api/v1`;
};

export const PolygonEditor: React.FC<PolygonEditorProps> = ({
  workstations,
  initialSelectedId,
  onSaveSuccess,
}) => {
  const [selectedDeskId, setSelectedDeskId] = useState<string>(
    initialSelectedId || workstations[0]?.id || 'DESK-01'
  );
  const [points, setPoints] = useState<[number, number][]>([]);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Click-to-draw 4 corners mode
  const [isDrawMode, setIsDrawMode] = useState<boolean>(false);
  const [drawnPoints, setDrawnPoints] = useState<[number, number][]>([]);

  const svgRef = useRef<SVGSVGElement | null>(null);
  const loadedDeskIdRef = useRef<string | null>(null);

  // Sync initialSelectedId when prop changes
  useEffect(() => {
    if (initialSelectedId && workstations.some((w) => w.id === initialSelectedId)) {
      setSelectedDeskId(initialSelectedId);
    }
  }, [initialSelectedId, workstations]);

  const selectedDesk = workstations.find((w) => w.id === selectedDeskId) || workstations[0] || null;

  // Crucial fix: Only load points from selectedDesk when selectedDeskId actually changes,
  // NOT on every background telemetry update (which updates object references every 500ms!)
  useEffect(() => {
    if (selectedDesk && loadedDeskIdRef.current !== selectedDesk.id) {
      loadedDeskIdRef.current = selectedDesk.id;
      setPoints([...(selectedDesk.polygon_normalized || [])]);
      setSaveMessage(null);
      setIsDrawMode(false);
      setDrawnPoints([]);
    }
  }, [selectedDeskId, selectedDesk]);

  const handlePointerDown = (e: React.PointerEvent, index: number) => {
    if (isDrawMode) return;
    e.stopPropagation();
    try {
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    } catch {
      // ignore
    }
    setDraggingIndex(index);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (isDrawMode || draggingIndex === null || !svgRef.current) return;

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

  // Canvas click handler for click-to-draw 4-point calibration
  const handleCanvasClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawMode || !svgRef.current) return;

    const rect = svgRef.current.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const nx = parseFloat(Math.max(0.01, Math.min(0.99, (e.clientX - rect.left) / rect.width)).toFixed(4));
    const ny = parseFloat(Math.max(0.01, Math.min(0.99, (e.clientY - rect.top) / rect.height)).toFixed(4));

    const nextDrawn: [number, number][] = [...drawnPoints, [nx, ny]];
    setDrawnPoints(nextDrawn);

    if (nextDrawn.length === 4) {
      // 4 points collected! Finalize polygon and exit draw mode
      setPoints(nextDrawn);
      setIsDrawMode(false);
      setDrawnPoints([]);
      setSaveMessage('All 4 corners placed! You can fine-tune handles or click Save & Hot-Reload.');
    }
  };

  const startDrawMode = () => {
    setIsDrawMode(true);
    setDrawnPoints([]);
    setSaveMessage('Click 4 corners on the camera view: Top-Left, Top-Right, Bottom-Right, Bottom-Left.');
  };

  const cancelDrawMode = () => {
    setIsDrawMode(false);
    setDrawnPoints([]);
    setSaveMessage(null);
  };

  const handleReset = () => {
    if (selectedDesk) {
      setPoints([...(selectedDesk.polygon_normalized || [])]);
      setSaveMessage(null);
      setIsDrawMode(false);
      setDrawnPoints([]);
    }
  };

  const handlePresetQuad = () => {
    // Generates a centered, well-proportioned rectangular quad
    const quad: [number, number][] = [
      [0.25, 0.25],
      [0.75, 0.25],
      [0.75, 0.75],
      [0.25, 0.75],
    ];
    setPoints(quad);
    setSaveMessage('Reset to centered rectangular quad.');
  };

  const handleAddVertex = () => {
    if (points.length >= 8) return;
    const pLast = points[points.length - 1] || [0.5, 0.5];
    const pFirst = points[0] || [0.5, 0.5];
    const newPt: [number, number] = [
      parseFloat(((pLast[0] + pFirst[0]) / 2 + 0.05).toFixed(4)),
      parseFloat(((pLast[1] + pFirst[1]) / 2 + 0.05).toFixed(4)),
    ];
    setPoints([...points, newPt]);
  };

  const handleRemoveVertex = () => {
    if (points.length <= 3) return;
    setPoints(points.slice(0, points.length - 1));
  };

  const handleSave = async () => {
    if (!selectedDesk || points.length < 3) return;

    setIsSaving(true);
    setSaveMessage(null);

    try {
      const res = await fetch(`${getApiBaseUrl()}/workstations/${selectedDesk.id}/polygon`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ polygon_normalized: points }),
      });

      if (res.ok) {
        setSaveMessage(`Workstation ${selectedDesk.name || selectedDesk.id} successfully calibrated and hot-reloaded!`);
        // Reset ref so fresh data from server is acknowledged
        loadedDeskIdRef.current = null;
        onSaveSuccess();
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to save polygon' }));
        setSaveMessage(`Error: ${err.detail || 'Failed to save polygon.'}`);
      }
    } catch {
      setSaveMessage('Error connecting to backend API.');
    } finally {
      setIsSaving(false);
    }
  };

  // Distinct colors for other workstations when rendered as background references
  const getDeskColor = (deskId: string, index: number) => {
    if (deskId === selectedDeskId) return '#10b981'; // emerald
    const colors = ['#38bdf8', '#a855f7', '#f59e0b', '#ec4899', '#06b6d4'];
    return colors[index % colors.length];
  };

  return (
    <div className="space-y-6">
      {/* Control Bar Header */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <PenTool className="h-5 w-5 text-emerald-500" />
              <span>Multi-Workstation Polygon Calibration</span>
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Calibrate any workstation detection zone by clicking 4 corners on the live camera or dragging boundary handles.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!isDrawMode ? (
              <button
                onClick={startDrawMode}
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-sm transition-all"
                title="Click 4 corners on camera to redraw"
              >
                <Crosshair className="h-4 w-4" />
                <span>Click 4 Corners</span>
              </button>
            ) : (
              <button
                onClick={cancelDrawMode}
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-sm transition-all"
              >
                <span>Cancel Draw ({drawnPoints.length}/4)</span>
              </button>
            )}

            <button
              onClick={handlePresetQuad}
              disabled={isDrawMode}
              className="flex items-center space-x-1 px-3 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40"
              title="Reset to centered rectangle"
            >
              <Maximize2 className="h-3.5 w-3.5 text-indigo-500" />
              <span>Preset Box</span>
            </button>

            <button
              onClick={handleAddVertex}
              disabled={isDrawMode || points.length >= 8}
              className="flex items-center space-x-1 px-3 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40"
              title="Add point"
            >
              <PlusCircle className="h-3.5 w-3.5 text-emerald-500" />
              <span>+ Point</span>
            </button>

            <button
              onClick={handleRemoveVertex}
              disabled={isDrawMode || points.length <= 3}
              className="flex items-center space-x-1 px-3 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40"
              title="Remove point"
            >
              <MinusCircle className="h-3.5 w-3.5 text-rose-500" />
              <span>- Point</span>
            </button>

            <button
              onClick={handleReset}
              className="flex items-center space-x-1 px-3 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset</span>
            </button>

            <button
              onClick={handleSave}
              disabled={isSaving || isDrawMode || points.length < 3}
              className="flex items-center space-x-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all disabled:opacity-50"
            >
              {isSaving ? (
                <span>Saving...</span>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  <span>Save & Hot-Reload</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Workstations Quick Selector Pills */}
        <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center space-x-2 overflow-x-auto">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center space-x-1 flex-shrink-0">
            <Armchair className="h-3.5 w-3.5" />
            <span>Select Desk:</span>
          </span>
          {workstations.map((desk) => {
            const isSelected = desk.id === selectedDeskId;
            const ptsCount = desk.polygon_normalized?.length || 0;
            return (
              <button
                key={desk.id}
                onClick={() => setSelectedDeskId(desk.id)}
                className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                <span>{desk.name}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${isSelected ? 'bg-emerald-700 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}`}>
                  {ptsCount} pts
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Save / Status Message Banner */}
      {saveMessage && (
        <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl p-4 flex items-center space-x-2 text-sm text-emerald-800 dark:text-emerald-300">
          <Check className="h-5 w-5 text-emerald-500 flex-shrink-0" />
          <span>{saveMessage}</span>
        </div>
      )}

      {/* Interactive Calibration Canvas Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="relative aspect-video max-w-4xl mx-auto rounded-xl overflow-hidden border border-slate-700 bg-black select-none">
          {/* Real Live Camera Stream Backdrop */}
          <img
            src={`${getApiBaseUrl()}/video-feed`}
            alt="Live Camera Calibration Feed"
            className="absolute inset-0 w-full h-full object-contain pointer-events-none opacity-85"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />

          {/* Guide Overlay Info Badge */}
          <div className="absolute top-3 left-3 bg-slate-900/85 backdrop-blur border border-slate-700 rounded-lg px-3 py-1.5 flex items-center space-x-2 text-xs text-white z-10 pointer-events-none">
            <Video className="h-3.5 w-3.5 text-emerald-400" />
            <span>
              Active Calibration: <strong>{selectedDesk?.name || selectedDeskId}</strong>
            </span>
            {isDrawMode && (
              <span className="ml-2 px-2 py-0.5 rounded bg-cyan-600 text-[10px] font-bold uppercase animate-pulse">
                Click Corner {drawnPoints.length + 1} of 4
              </span>
            )}
          </div>

          {/* SVG Interactive Layer */}
          <svg
            ref={svgRef}
            viewBox="0 0 1000 1000"
            preserveAspectRatio="none"
            className={`absolute inset-0 w-full h-full z-20 touch-none ${
              isDrawMode ? 'cursor-crosshair' : 'cursor-default'
            }`}
            onClick={handleCanvasClick}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          >
            {/* Draw ALL OTHER workstations so user can see and click them directly */}
            {workstations
              .filter((w) => w.id !== selectedDeskId && w.polygon_normalized && w.polygon_normalized.length >= 3)
              .map((other, idx) => {
                const color = getDeskColor(other.id, idx);
                const firstPt = other.polygon_normalized[0] || [0.5, 0.5];
                return (
                  <g key={other.id} className="cursor-pointer" onClick={() => setSelectedDeskId(other.id)}>
                    <polygon
                      points={other.polygon_normalized.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                      fill={`${color}22`}
                      stroke={color}
                      strokeWidth="2.5"
                      strokeDasharray="6 4"
                    />
                    <text
                      x={firstPt[0] * 1000 + 10}
                      y={firstPt[1] * 1000 - 10}
                      fill={color}
                      fontSize="24"
                      fontWeight="bold"
                    >
                      {other.name} ({other.id})
                    </text>
                  </g>
                );
              })}

            {/* Currently Selected Workstation Polygon Fill & Outline (in normal drag mode) */}
            {!isDrawMode && points.length >= 3 && (
              <polygon
                points={points.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                fill="rgba(16, 185, 129, 0.25)"
                stroke="#10b981"
                strokeWidth="4"
              />
            )}

            {/* In Click-to-Draw mode: draw connected lines as user clicks points */}
            {isDrawMode && drawnPoints.length > 0 && (
              <>
                <polyline
                  points={drawnPoints.map(([x, y]) => `${x * 1000},${y * 1000}`).join(' ')}
                  fill="none"
                  stroke="#06b6d4"
                  strokeWidth="4"
                  strokeDasharray="8 4"
                />
                {drawnPoints.map(([x, y], idx) => (
                  <g key={idx}>
                    <circle cx={x * 1000} cy={y * 1000} r="18" fill="#06b6d4" stroke="#ffffff" strokeWidth="3" />
                    <text
                      x={x * 1000 + 14}
                      y={y * 1000 - 12}
                      fill="#06b6d4"
                      fontSize="28"
                      fontWeight="bold"
                    >
                      P{idx + 1}
                    </text>
                  </g>
                ))}
              </>
            )}

            {/* Corner Draggable Handles (when NOT in draw mode) */}
            {!isDrawMode &&
              points.map(([x, y], idx) => (
                <g
                  key={idx}
                  className="cursor-grab active:cursor-grabbing"
                  onPointerDown={(e) => handlePointerDown(e, idx)}
                >
                  <circle cx={x * 1000} cy={y * 1000} r="28" fill="rgba(16, 185, 129, 0.35)" />
                  <circle cx={x * 1000} cy={y * 1000} r="14" fill="#ffffff" stroke="#10b981" strokeWidth="4" />
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
              Calibrated Vertices for {selectedDesk?.name || selectedDeskId} ({points.length} points):
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {points.map(([x, y], i) => (
              <span
                key={i}
                className="bg-white dark:bg-slate-900 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700"
              >
                <strong>P{i + 1}:</strong> [{x.toFixed(4)}, {y.toFixed(4)}]
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

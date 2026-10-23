import React from 'react';
import {
  LayoutGrid,
  PenTool,
  Clock,
  Video,
  Wifi,
  WifiOff,
  Sun,
  Moon,
  ShieldCheck,
  Sliders,
} from 'lucide-react';
import type { SystemHealth } from '../types';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
  isConnected: boolean;
  health: SystemHealth | null;
  fps: number;
  trackedPeopleCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  isDark,
  setIsDark,
  isConnected,
  health,
  fps,
  trackedPeopleCount = 0,
}) => {
  const tabs = [
    { id: 'floorplan', label: 'Floorplan & Camera', icon: LayoutGrid },
    { id: 'workstations', label: 'Workstation & AI Control', icon: Sliders },
    { id: 'polygon_editor', label: 'Polygon Editor', icon: PenTool },
    { id: 'timeline', label: 'Event Timeline', icon: Clock },
  ];

  const cameraOnline = health?.camera_status === 'ONLINE';

  return (
    <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md sticky top-0 z-30 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Name */}
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-md shadow-emerald-500/20">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-xl tracking-tight text-slate-900 dark:text-white">
                  OfficeVision <span className="text-emerald-500 font-extrabold">AI</span>
                </span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800">
                  YOLO26-Pose
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">Workspace Presence & Edge AI Monitoring</p>
            </div>
          </div>

          {/* Real-time Status Badges */}
          <div className="hidden md:flex items-center space-x-3">
            {/* Camera Status */}
            <div
              className={`flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium border ${
                cameraOnline
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
                  : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800'
              }`}
            >
              <Video className="h-3.5 w-3.5" />
              <span>Camera 1: {cameraOnline ? `ONLINE (${fps.toFixed(1)} FPS | ${trackedPeopleCount} In View)` : 'OFFLINE / STANDBY'}</span>
            </div>

            {/* WebSocket Sync Status */}
            <div
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
                isConnected
                  ? 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950/40 dark:text-cyan-300 dark:border-cyan-800'
                  : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
              }`}
            >
              {isConnected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              <span>{isConnected ? 'Live Sync Active' : 'Disconnected'}</span>
            </div>

            {/* Dark / Light Toggle */}
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-800 transition-colors"
              title="Toggle Theme"
            >
              {isDark ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-slate-600" />}
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-1 overflow-x-auto py-2 border-t border-slate-100 dark:border-slate-800/80">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/30'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};

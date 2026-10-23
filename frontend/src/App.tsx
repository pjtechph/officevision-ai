import { useState, useEffect } from 'react';
import { usePresenceWebSocket } from './hooks/usePresenceWebSocket';
import { Header } from './components/Header';
import { FloorplanView } from './components/FloorplanView';
import { WorkstationManager } from './components/WorkstationManager';
import { PolygonEditor } from './components/PolygonEditor';
import { EventTimelineView } from './components/EventTimelineView';

export function App() {
  const [activeTab, setActiveTab] = useState('floorplan');
  const [isDark, setIsDark] = useState(true);
  const [editorSelectedDeskId, setEditorSelectedDeskId] = useState<string | undefined>(undefined);

  const {
    workstations,
    events,
    health,
    isConnected,
    fps,
    trackedPeopleCount,
    activeGracePeriod,
    gracePeriodRemaining,
    refreshData,
  } = usePresenceWebSocket();

  // Apply dark class to <html> element
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const handleNavigateToEditor = (deskId: string) => {
    setEditorSelectedDeskId(deskId);
    setActiveTab('polygon_editor');
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors duration-200">
      {/* Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isDark={isDark}
        setIsDark={setIsDark}
        isConnected={isConnected}
        health={health}
        fps={fps}
        trackedPeopleCount={trackedPeopleCount}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'floorplan' && (
          <FloorplanView
            workstations={workstations}
            activeGracePeriod={activeGracePeriod}
            gracePeriodRemaining={gracePeriodRemaining}
            onNavigateToManager={() => setActiveTab('workstations')}
          />
        )}

        {activeTab === 'workstations' && (
          <WorkstationManager
            workstations={workstations}
            onRefresh={refreshData}
            onNavigateToEditor={handleNavigateToEditor}
          />
        )}

        {activeTab === 'polygon_editor' && (
          <PolygonEditor
            workstations={workstations}
            initialSelectedId={editorSelectedDeskId}
            onSaveSuccess={refreshData}
          />
        )}

        {activeTab === 'timeline' && (
          <EventTimelineView
            events={events}
            onRefresh={refreshData}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 dark:border-slate-800 py-6 mt-12 bg-white/50 dark:bg-slate-900/50 text-xs text-slate-500 text-center">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>OfficeVision AI v1.0.0 — Powered by Ultralytics YOLO26-Pose & ByteTrack</span>
          <span>Responsible Workspace Presence & Multi-Workstation Edge AI Monitoring</span>
        </div>
      </footer>
    </div>
  );
}

export default App;

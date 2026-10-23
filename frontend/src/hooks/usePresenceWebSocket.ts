import { useState, useEffect, useRef, useCallback } from 'react';
import type { Workstation, PresenceEvent, SystemHealth } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const WS_URL = 'ws://127.0.0.1:8000/api/v1/ws/live-dashboard';

export function usePresenceWebSocket() {
  const [workstations, setWorkstations] = useState<Workstation[]>([]);
  const [events, setEvents] = useState<PresenceEvent[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [fps, setFps] = useState<number>(0);
  const [trackedPeopleCount, setTrackedPeopleCount] = useState<number>(0);
  const [activeGracePeriod, setActiveGracePeriod] = useState<boolean>(false);
  const [gracePeriodRemaining, setGracePeriodRemaining] = useState<number>(0);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Initial REST fetch
  const fetchInitialData = useCallback(async () => {
    try {
      const [resWs, resEvents, resHealth] = await Promise.all([
        fetch(`${API_BASE_URL}/workstations`),
        fetch(`${API_BASE_URL}/events`),
        fetch(`${API_BASE_URL}/health`),
      ]);

      if (resWs.ok) {
        const wsData = await resWs.json();
        setWorkstations(wsData);
      }
      if (resEvents.ok) {
        const eventsData = await resEvents.json();
        setEvents(eventsData.reverse()); // most recent first
      }
      if (resHealth.ok) {
        const healthData = await resHealth.json();
        setHealth(healthData);
      }
    } catch {
      // Backend not yet reachable
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    try {
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'INITIAL_SNAPSHOT') {
            if (data.workstations) setWorkstations(data.workstations);
            if (data.recent_events) setEvents(data.recent_events.reverse());
            if (data.health) setHealth(data.health);
          } else if (data.type === 'WORKSTATIONS_UPDATED') {
            if (Array.isArray(data.workstations)) {
              setWorkstations(data.workstations);
            }
          } else if (data.type === 'TELEMETRY') {
            setFps(data.fps || 0);
            setTrackedPeopleCount(data.tracked_people_count || 0);
            setActiveGracePeriod(data.active_grace_period || false);
            setGracePeriodRemaining(data.grace_period_remaining || 0);

            // Update workstation states from telemetry
            if (Array.isArray(data.workstation_states)) {
              setWorkstations((prev) =>
                prev.map((desk) => {
                  const match = data.workstation_states.find((w: { id: string }) => w.id === desk.id);
                  if (match) {
                    return {
                      ...desk,
                      current_state: match.current_state,
                      active_track_id: match.active_track_id,
                      time_in_state_sec: match.time_in_state_sec,
                    };
                  }
                  return desk;
                })
              );
            }
          } else if (data.type === 'WORKSTATION_STATE_CHANGE') {
            // New transition event
            const newEvent: PresenceEvent = {
              event_type: data.event_type,
              workstation_id: data.workstation_id,
              previous_state: data.previous_state,
              new_state: data.new_state,
              track_id: data.track_id,
              duration_in_prev_state_sec: data.duration_in_prev_state_sec,
              confidence: data.confidence,
              timestamp: data.timestamp,
              formatted_time: data.formatted_time,
            };
            setEvents((prev) => [newEvent, ...prev.slice(0, 49)]);

            // Update matched workstation
            setWorkstations((prev) =>
              prev.map((desk) => {
                if (desk.id === data.workstation_id) {
                  return {
                    ...desk,
                    current_state: data.new_state,
                    active_track_id: data.track_id,
                    time_in_state_sec: 0,
                  };
                }
                return desk;
              })
            );
          } else if (data.type === 'CAMERA_STATUS') {
            setHealth((prev) => (prev ? { ...prev, camera_status: data.status, ai_vision_connected: false } : null));
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Retry connection after 2 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectWebSocket();
        }, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      setIsConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectWebSocket();
      }, 3000);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
    connectWebSocket();

    // Periodic heartbeat to fetch health stats
    const healthInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (res.ok) {
          const hData = await res.json();
          setHealth(hData);
        }
      } catch {
        // Ignored
      }
    }, 5000);

    return () => {
      clearInterval(healthInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [fetchInitialData, connectWebSocket]);

  return {
    workstations,
    setWorkstations,
    events,
    health,
    isConnected,
    fps,
    trackedPeopleCount,
    activeGracePeriod,
    gracePeriodRemaining,
    refreshData: fetchInitialData,
  };
}

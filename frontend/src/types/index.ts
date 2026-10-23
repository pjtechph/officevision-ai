export interface Workstation {
  id: string;
  name: string;
  description?: string;
  polygon_normalized: [number, number][];
  current_state: 'VACANT' | 'OCCUPIED_SEATED' | 'OCCUPIED_STANDING' | 'UNKNOWN';
  active_track_id: number | null;
  time_in_state_sec: number;
  latest_gesture?: {
    reason: string;
    confirmed_at: string;
    track_id?: number;
  } | null;
  last_updated: string;
}

export interface PresenceEvent {
  id?: number;
  event_type: string;
  workstation_id: string;
  previous_state?: string;
  new_state?: string;
  track_id?: number | null;
  duration_in_prev_state_sec?: number;
  confidence?: number;
  timestamp: number;
  formatted_time: string;
  gesture_type?: string;
  selected_reason?: string;
  confirmed_at?: string;
}

export interface SystemHealth {
  status: 'HEALTHY' | 'DEGRADED' | 'INITIALIZING';
  ai_vision_connected: boolean;
  camera_status: string;
  seconds_since_last_heartbeat: number | null;
  uptime_seconds: number;
  total_desks_registered: number;
  total_events_recorded: number;
  total_check_ins: number;
}

export interface AttendanceRecord {
  id: number;
  employee_id_code: string;
  workstation_id: string;
  verification_method: string;
  check_in_time: string;
  date: string;
}

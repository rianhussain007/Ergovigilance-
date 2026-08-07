import type { CameraInfo, WorkerSummary } from '@/src/types/api';

export const DEMO_CAMERAS: CameraInfo[] = [
  { id: 'CAM-001', name: 'Assembly Line A — Station 1', worker: 'Marcus Thorne', fps: 30, risk: 'moderate', recording: true, uptime: '12h 34m', status: 'streaming' as const },
  { id: 'CAM-002', name: 'Assembly Line B — Station 3', worker: 'Chen Wei', fps: 28, risk: 'low', recording: true, uptime: '8h 12m', status: 'streaming' as const },
  { id: 'CAM-003', name: 'Loading Dock — Bay 2', worker: 'James Kowalski', fps: 30, risk: 'high', recording: true, uptime: '6h 45m', status: 'streaming' as const },
  { id: 'CAM-004', name: 'Quality Control — Table 3', worker: 'Priya Sharma', fps: 25, risk: 'low', recording: false, uptime: '4h 20m', status: 'streaming' as const },
  { id: 'CAM-005', name: 'Fabrication — Welding Bay', worker: 'Sarah Jenkins', fps: 30, risk: 'high', recording: true, uptime: '10h 05m', status: 'streaming' as const },
  { id: 'CAM-006', name: 'Packaging — Line 2', worker: 'Maria Santos', fps: 27, risk: 'moderate', recording: true, uptime: '7h 30m', status: 'streaming' as const },
];

export const DEMO_WORKERS: WorkerSummary[] = [
  { id: 'WA-4092', name: 'Marcus Thorne', status: 'moderate', task: 'Assembly Line B', risk: 42 },
  { id: 'WA-2104', name: 'Elena Rodriguez', status: 'low', task: 'Loading Dock', risk: 18 },
  { id: 'WA-3381', name: 'Chen Wei', status: 'low', task: 'Quality Control', risk: 12 },
  { id: 'WA-5562', name: 'Sarah Jenkins', status: 'high', task: 'Fabrication', risk: 68 },
  { id: 'WA-1099', name: 'James Kowalski', status: 'low', task: 'Assembly Line A', risk: 22 },
  { id: 'WA-6712', name: 'Priya Sharma', status: 'moderate', task: 'Packaging', risk: 38 },
  { id: 'WA-4431', name: 'Ahmed Hassan', status: 'low', task: 'Inspection', risk: 15 },
  { id: 'WA-8876', name: 'Lisa Chen', status: 'high', task: 'Welding', risk: 72 },
  { id: 'WA-3321', name: 'David Park', status: 'moderate', task: 'Assembly Line A', risk: 45 },
  { id: 'WA-7789', name: 'Maria Santos', status: 'low', task: 'Packing', risk: 20 },
];

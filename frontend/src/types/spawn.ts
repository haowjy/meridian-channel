export type SpawnStatus =
  | 'running'
  | 'queued'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'finalizing'

export interface SpawnSummary {
  spawn_id: string
  status: SpawnStatus
  agent: string | null
  model: string | null
  harness: string
  work_id: string | null
  desc: string | null
  started_at: string        // ISO 8601
  finished_at: string | null
  cost_usd: number | null
}

export interface WorkItemSummary {
  work_id: string
  name: string
  status: string
  spawns: SpawnSummary[]
}

const KNOWN_STATUSES: ReadonlySet<string> = new Set<string>([
  'running',
  'queued',
  'succeeded',
  'failed',
  'cancelled',
  'finalizing',
])

export function parseStatus(s: string): SpawnStatus {
  return KNOWN_STATUSES.has(s) ? (s as SpawnStatus) : 'queued'
}

/**
 * Typed REST API client for AutoFix Agent backend.
 * Non-streaming endpoints: /api/health, /api/analyze
 *
 * The base URL is read from NEXT_PUBLIC_API_URL environment variable.
 * Falls back to http://localhost:8000 for local development.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Shared types (mirror backend Pydantic schemas)
// ---------------------------------------------------------------------------

export interface ExecutionResult {
  success: boolean
  stdout: string
  stderr: string
  exit_code: number
  execution_time: number
  language: string
  error_type?: string | null
}

export interface ErrorObservation {
  language: string
  error_type: string
  error_message: string
  file_name?: string | null
  line_number?: number | null
  column_number?: number | null
  stack_trace?: string | null
  stdout: string
  stderr: string
}

export interface ValidationResult {
  passed: boolean
  total_tests: number
  passed_tests: number
  failed_tests: number
  stdout: string
  stderr: string
  failure_details: Array<{ test_name: string; message: string }>
}

export interface RepairDiagnosis {
  diagnosis: string
  root_cause: string
  error_category: string
  confidence: number
  repair_strategy: string
  affected_lines: number[]
}

// ---------------------------------------------------------------------------
// Request / response shapes
// ---------------------------------------------------------------------------

export interface AnalyzeRequest {
  source_code: string
  language?: string
  timeout?: number
}

export interface AnalyzeResponse {
  language: string
  execution_result: ExecutionResult
  error_observation: ErrorObservation | null
}

export interface HealthResponse {
  status: string
  service: string
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API ${path} failed (${res.status}): ${detail}`)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const api = {
  /**
   * Check backend health.
   */
  health(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>('/api/health')
  },

  /**
   * Execute code and analyse errors — no repair performed.
   */
  analyze(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    return apiFetch<AnalyzeResponse>('/api/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },

  /**
   * Return the full SSE stream URL for /api/repair/stream.
   * The caller is responsible for opening the EventSource / fetch stream.
   */
  repairStreamUrl(): string {
    return `${BASE_URL}/api/repair/stream`
  },
}

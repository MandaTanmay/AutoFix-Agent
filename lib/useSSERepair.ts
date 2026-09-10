/**
 * useSSERepair — React hook for real-time AutoFix Agent streaming.
 *
 * Uses the Fetch API to open a POST /api/repair/stream request and reads
 * the SSE response line-by-line as the agent executes. Translates backend
 * SSEEvent objects into frontend AgentState transitions and timeline events.
 *
 * Returns everything the dashboard components need to render live progress.
 */

'use client'

import { useCallback, useRef, useState } from 'react'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// SSE event types (mirror backend SSEEventType enum)
// ---------------------------------------------------------------------------

export type SSEEventType =
  | 'session_started'
  | 'language_mismatch'
  | 'execute_started'
  | 'execute_completed'
  | 'error_detected'
  | 'diagnosis_started'
  | 'diagnosis_completed'
  | 'patch_started'
  | 'patch_generated'
  | 'validation_started'
  | 'validation_completed'
  | 'retry_started'
  | 'repair_success'
  | 'repair_failed'
  | 'stream_error'

export interface SSEEvent {
  type: SSEEventType
  attempt: number
  status: string
  message: string
  timestamp: string
  details?: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Frontend-facing types
// ---------------------------------------------------------------------------

export type AgentPhase =
  | 'idle'
  | 'language_mismatch'
  | 'executing'
  | 'observing'
  | 'diagnosing'
  | 'patching'
  | 'validating'
  | 'retrying'
  | 'success'
  | 'failed'

export interface TimelineEvent {
  type: SSEEventType
  tone: 'blue' | 'red' | 'violet' | 'amber' | 'green' | 'gray'
  title: string
  detail: string
  time: string
}

export interface DiagnosisInfo {
  rootCause: string
  confidence: number       // 0–100 integer
  category: string
  strategy: string
}

export interface ValidationInfo {
  passed: boolean
  total: number
  passedCount: number
  failedCount: number
}

export interface RepairResult {
  status: 'success' | 'failed' | 'language_mismatch'
  attempts: number
}

export interface LanguageMismatchInfo {
  selectedLanguage: string
  detectedLanguage: string
  message: string
}

// ---------------------------------------------------------------------------
// SSE event → tone mapping
// ---------------------------------------------------------------------------

const EVENT_TONE: Record<SSEEventType, TimelineEvent['tone']> = {
  session_started:      'blue',
  language_mismatch:    'red',
  execute_started:      'blue',
  execute_completed:    'blue',
  error_detected:       'red',
  diagnosis_started:    'violet',
  diagnosis_completed:  'violet',
  patch_started:        'amber',
  patch_generated:      'amber',
  validation_started:   'blue',
  validation_completed: 'green',
  retry_started:        'amber',
  repair_success:       'green',
  repair_failed:        'red',
  stream_error:         'red',
}

const EVENT_TITLE: Record<SSEEventType, string> = {
  session_started:      'Session started',
  language_mismatch:    'Language mismatch',
  execute_started:      'Execute',
  execute_completed:    'Execution complete',
  error_detected:       'Error detected',
  diagnosis_started:    'AI Diagnosis',
  diagnosis_completed:  'Diagnosis complete',
  patch_started:        'Patch generation',
  patch_generated:      'Patch generated',
  validation_started:   'Validation',
  validation_completed: 'Validation complete',
  retry_started:        'Retry',
  repair_success:       'Success',
  repair_failed:        'Repair failed',
  stream_error:         'Error',
}

function sseToTimeline(event: SSEEvent): TimelineEvent {
  return {
    type:   event.type,
    tone:   EVENT_TONE[event.type] ?? 'gray',
    title:  EVENT_TITLE[event.type] ?? event.type,
    detail: event.message,
    time:   new Date(event.timestamp).toLocaleTimeString(),
  }
}

// ---------------------------------------------------------------------------
// SSE event → AgentPhase
// ---------------------------------------------------------------------------

function sseToPhase(type: SSEEventType): AgentPhase | null {
  switch (type) {
    case 'execute_started':
    case 'execute_completed': return 'executing'
    case 'error_detected':    return 'observing'
    case 'diagnosis_started':
    case 'diagnosis_completed': return 'diagnosing'
    case 'patch_started':
    case 'patch_generated':   return 'patching'
    case 'validation_started':
    case 'validation_completed': return 'validating'
    case 'retry_started':     return 'retrying'
    case 'repair_success':    return 'success'
    case 'repair_failed':     return 'failed'
    case 'language_mismatch': return 'language_mismatch'
    default:                  return null
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface RepairOptions {
  sourceCode: string
  language?: string
  maxAttempts?: number
  timeout?: number
  testCode?: string
}

export interface UseSSERepairReturn {
  /** Start a new repair run */
  run: (options: RepairOptions) => void
  /** Abort the current run */
  abort: () => void
  /** Timeline events accumulated so far */
  events: TimelineEvent[]
  /** Current agent phase for flow visualisation */
  phase: AgentPhase
  /** Current repair attempt index */
  attempt: number
  /** Latest AI diagnosis data (available after diagnose node) */
  diagnosis: DiagnosisInfo | null
  /** Latest validation info (available after validate node) */
  validation: ValidationInfo | null
  /** Final repair outcome once stream closes */
  result: RepairResult | null
  /** Language validation details when source and selection differ */
  languageMismatch: LanguageMismatchInfo | null
  /** True while a stream is open */
  running: boolean
  /** Non-null when a fatal stream/network error occurs */
  error: string | null
}

export function useSSERepair(): UseSSERepairReturn {
  const [events,     setEvents]     = useState<TimelineEvent[]>([])
  const [phase,      setPhase]      = useState<AgentPhase>('idle')
  const [attempt,    setAttempt]    = useState(0)
  const [diagnosis,  setDiagnosis]  = useState<DiagnosisInfo | null>(null)
  const [validation, setValidation] = useState<ValidationInfo | null>(null)
  const [result,     setResult]     = useState<RepairResult | null>(null)
  const [languageMismatch, setLanguageMismatch] = useState<LanguageMismatchInfo | null>(null)
  const [running,    setRunning]    = useState(false)
  const [error,      setError]      = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setRunning(false)
    setPhase('idle')
  }, [])

  const run = useCallback(async (options: RepairOptions) => {
    // Reset all state
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setEvents([])
    setPhase('idle')
    setAttempt(0)
    setDiagnosis(null)
    setValidation(null)
    setResult(null)
    setLanguageMismatch(null)
    setError(null)
    setRunning(true)

    try {
      const response = await fetch(api.repairStreamUrl(), {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_code:  options.sourceCode,
          language:     options.language ?? 'python',
          max_attempts: options.maxAttempts ?? 5,
          timeout:      options.timeout ?? 5,
          test_code:    options.testCode ?? null,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const detail = await response.text().catch(() => response.statusText)
        throw new Error(`Backend error (${response.status}): ${detail}`)
      }

      if (!response.body) {
        throw new Error('No response body received from SSE stream.')
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE lines end with \n\n — process all complete events
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''        // last part may be incomplete

        for (const part of parts) {
          for (const line of part.split('\n')) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue

            const jsonStr = trimmed.slice('data:'.length).trim()
            let event: SSEEvent
            try {
              event = JSON.parse(jsonStr) as SSEEvent
            } catch {
              continue    // skip malformed lines
            }

            // Update timeline
            setEvents(prev => [...prev, sseToTimeline(event)])

            // Update attempt
            if (event.attempt > 0) {
              setAttempt(event.attempt)
            }

            // Update phase
            const nextPhase = sseToPhase(event.type)
            if (nextPhase) setPhase(nextPhase)

            // Update diagnosis from diagnosis_completed
            if (event.type === 'diagnosis_completed' && event.details) {
              setDiagnosis({
                rootCause:  event.message,
                confidence: (event.details.confidence as number) ?? 0,
                category:   (event.details.error_category as string) ?? '',
                strategy:   '',
              })
            }

            // Update validation from validation_completed
            if (event.type === 'validation_completed' && event.details) {
              setValidation({
                passed:      (event.details.passed as boolean) ?? false,
                total:       (event.details.total_tests as number) ?? 0,
                passedCount: (event.details.passed_tests as number) ?? 0,
                failedCount: (event.details.failed_tests as number) ?? 0,
              })
            }

            if (event.type === 'language_mismatch' && event.details) {
              setLanguageMismatch({
                selectedLanguage: (event.details.selected_language as string) ?? options.language ?? 'python',
                detectedLanguage: (event.details.detected_language as string) ?? 'unknown',
                message: event.message,
              })
              setResult({ status: 'language_mismatch', attempts: 0 })
              setRunning(false)
              setPhase('language_mismatch')
              controller.abort()
              return
            }

            // Terminal events — close stream
            if (event.type === 'repair_success') {
              setResult({ status: 'success', attempts: event.attempt })
              setRunning(false)
              controller.abort()
              return
            }
            if (event.type === 'repair_failed' || event.type === 'stream_error') {
              setResult({ status: 'failed', attempts: event.attempt })
              setRunning(false)
              controller.abort()
              return
            }
          }
        }
      }

      // Stream closed without a terminal event (edge case)
      setResult(prev => prev ?? { status: 'success', attempts: 0 })
      setRunning(false)

    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        // User-initiated abort — silently stop
        return
      }
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      setRunning(false)
      setPhase('failed')
    }
  }, [])

  return { run, abort, events, phase, attempt, diagnosis, validation, result, languageMismatch, running, error }
}

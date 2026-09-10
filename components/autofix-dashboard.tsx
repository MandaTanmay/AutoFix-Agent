'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  Clock3,
  Code2,
  Copy,
  FileCode2,
  GitBranch,
  Info,
  Loader2,
  Play,
  RotateCcw,
  Settings2,
  Sparkles,
  Terminal,
  Upload,
  WandSparkles,
  X,
  Zap,
} from 'lucide-react'
import { useSSERepair, type AgentPhase, type TimelineEvent, type LanguageMismatchInfo } from '@/lib/useSSERepair'

const initialCode = `def calculate_total(price, quantity):
    return priice * quantity

price = 100
quantity = 5

print(calculate_total(price, quantity))`

// AgentPhase now comes from the hook (idle | executing | observing | diagnosing | patching | validating | retrying | success | failed)
type AgentState = AgentPhase

const stages: { key: AgentState; label: string; description: string; icon: typeof Play }[] = [
  { key: 'executing', label: 'Execute', description: 'Running code in sandbox', icon: Play },
  { key: 'observing', label: 'Observe', description: 'Capturing stdout/stderr', icon: Activity },
  { key: 'diagnosing', label: 'Diagnose', description: 'Analyzing traceback', icon: Sparkles },
  { key: 'patching', label: 'Patch', description: 'Generating repair', icon: WandSparkles },
  { key: 'validating', label: 'Validate', description: 'Running patched code', icon: Check },
  { key: 'success', label: 'Success', description: 'Code passes validation', icon: Check },
]

// Tone icon map for timeline
const TONE_ICON: Record<TimelineEvent['tone'], typeof Play> = {
  blue: Play,
  red: AlertTriangle,
  violet: Sparkles,
  amber: WandSparkles,
  green: Check,
  gray: Info,
}

function LogoMark() {
  return <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#3568e8] text-white shadow-sm shadow-blue-200"><Bot className="h-4 w-4" /></div>
}

function SectionHeader({ icon: Icon, title, eyebrow, action }: { icon: typeof Code2; title: string; eyebrow?: string; action?: React.ReactNode }) {
  return <div className="flex items-center justify-between border-b border-[#e7eaf0] px-5 py-4"><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0f4ff] text-[#3568e8]"><Icon className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#202938]">{title}</p>{eyebrow && <p className="text-[11px] text-[#8a94a6]">{eyebrow}</p>}</div></div>{action}</div>
}

function AgentFlow({ state, attempt, running, maxAttempts }: { state: AgentState; attempt: number; running: boolean; maxAttempts: number }) {
  const currentIndex = state === 'idle' || state === 'language_mismatch' ? -1 : (state === 'retrying' || state === 'failed') ? 0 : stages.findIndex((stage) => stage.key === state)
  return <section className="panel min-h-[500px] overflow-hidden"><SectionHeader icon={Zap} title="Agent Execution" action={<span className="badge-blue"><span className="status-dot" /> {running ? 'Live session' : 'Ready'}</span>} /><div className="px-5 pb-5 pt-4"><div className="mb-7 flex items-center justify-between"><div><p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#8791a3]">Current attempt</p><p className="mt-1 text-xl font-semibold tracking-tight text-[#202938]">Attempt {attempt || 1} <span className="text-sm font-normal text-[#9ba4b2]">/ {maxAttempts}</span></p></div><div className="flex items-center gap-1.5">{Array.from({ length: maxAttempts }, (_, i) => i + 1).map((item) => <span key={item} className={`h-1.5 w-8 rounded-full ${item <= attempt ? 'bg-[#3568e8]' : 'bg-[#e8ebf0]'}`} />)}</div></div><div className="relative mx-auto max-w-[360px]">{stages.map((stage, index) => { const Icon = stage.icon; const complete = currentIndex > index || state === 'success'; const active = currentIndex === index; return <div key={stage.key} className="relative flex gap-4"><div className="flex w-10 shrink-0 flex-col items-center"><div className={`node ${complete ? 'node-complete' : ''} ${active ? 'node-active' : ''}`}>{complete ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</div>{index < stages.length - 1 && <div className={`flow-line ${currentIndex > index ? 'flow-line-complete' : ''}`} />}</div><div className={`mb-4 flex min-h-[58px] flex-1 items-center justify-between rounded-xl border px-4 py-3 transition-all ${active ? 'border-[#9db7ff] bg-[#f5f8ff] shadow-sm shadow-blue-100' : complete ? 'border-[#d8eee1] bg-[#f8fcf9]' : 'border-[#edf0f4] bg-white'}`}><div><p className={`text-sm font-semibold ${active ? 'text-[#2858ce]' : complete ? 'text-[#328255]' : 'text-[#536074]'}`}>{stage.label}</p><p className="mt-0.5 text-[11px] text-[#8b95a5]">{active ? stage.description : complete ? 'Completed' : 'Waiting'}</p></div>{active && <Loader2 className="h-4 w-4 animate-spin text-[#3568e8]" />}{complete && <Check className="h-4 w-4 text-[#3a9a62]" />}</div></div> })}</div>{state === 'success' && <div className="success-banner"><div className="success-icon"><Check className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#257348]">Execution successful</p><p className="text-xs text-[#58936f]">Fixed and validated in {attempt} attempt(s)</p></div></div>}{state === 'failed' && <div className="success-banner" style={{ background: '#fff8f8', borderColor: '#ffd0d0' }}><div className="success-icon" style={{ background: '#fee2e2', color: '#dc2626' }}><X className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#dc2626]">Repair unsuccessful</p><p className="text-xs text-[#ef4444]">Max attempts reached without a passing solution.</p></div></div>}{state === 'idle' && <div className="flow-hint"><CircleDashed className="h-4 w-4 text-[#8da6dd]" /><span>Start a run to watch the agent work through the issue.</span></div>}</div></section>
}

function CodeInput({
  code, setCode, onRun, onExample, running, onReset,
  language, setLanguage, maxAttempts, setMaxAttempts,
}: {
  code: string; setCode: (value: string) => void
  onRun: () => void; onExample: () => void
  running: boolean; onReset: () => void
  language: string; setLanguage: (v: string) => void
  maxAttempts: number; setMaxAttempts: (v: number) => void
}) {
  return <section className="panel overflow-hidden"><SectionHeader icon={FileCode2} title="Source Code" eyebrow={`${language}.${language === 'java' ? 'java' : language === 'javascript' ? 'js' : 'py'}`} action={<button className="icon-button" aria-label="More file options"><Settings2 className="h-4 w-4" /></button>} /><div className="flex items-center gap-1 border-b border-[#edf0f4] px-4 py-2"><button className="tool-button"><Upload className="h-3.5 w-3.5" /> Upload</button><button className="tool-button" onClick={onExample}><Copy className="h-3.5 w-3.5" /> Paste example</button><button className="tool-button ml-auto" onClick={onReset}><X className="h-3.5 w-3.5" /> Clear</button></div><div className="code-editor"><div className="line-numbers">{code.split('\n').map((_, index) => <span key={index}>{index + 1}</span>)}</div><textarea aria-label="Source code input" value={code} onChange={(event) => setCode(event.target.value)} spellCheck={false} /></div><div className="border-t border-[#edf0f4] px-5 py-4"><div className="mb-4 flex flex-wrap items-center gap-3"><label className="flex items-center gap-2 text-xs text-[#687487]">Language<select className="select-control" value={language} onChange={e => setLanguage(e.target.value)}><option value="python">Python</option><option value="javascript">JavaScript</option><option value="java">Java</option></select></label><label className="flex items-center gap-2 text-xs text-[#687487]">Max attempts<select className="select-control" value={maxAttempts} onChange={e => setMaxAttempts(Number(e.target.value))}><option value={3}>3</option><option value={5}>5</option><option value={10}>10</option></select></label><span className="flex items-center gap-1.5 text-xs text-[#687487]"><Clock3 className="h-3.5 w-3.5" /> Timeout <strong className="font-medium text-[#384458]">5 sec</strong></span></div><button className="primary-button w-full" onClick={onRun} disabled={running}>{running ? <><Loader2 className="h-4 w-4 animate-spin" /> Agent running...</> : <><Play className="h-4 w-4 fill-current" /> Run AutoFix Agent</>}</button></div></section>
}

function DiagnosisAndDiff({ visible, rootCause, confidence, category }: { visible: boolean; rootCause?: string; confidence?: number; category?: string }) {
  const hasData = !!(rootCause)
  return <div className="space-y-4"><section className={`panel overflow-hidden transition-all ${visible ? 'animate-slide-up' : ''}`}><SectionHeader icon={Sparkles} title="AI Diagnosis" action={confidence != null ? <span className="badge-purple">{confidence}% confidence</span> : undefined} /><div className="space-y-4 px-5 py-4"><div><p className="label">Root cause</p><p className="mt-1 text-sm leading-6 text-[#465267]">{hasData ? rootCause : <span className="italic text-[#9ba4b2]">Waiting for diagnosis…</span>}</p></div>{confidence != null && <><div className="confidence-track"><span style={{ width: `${confidence}%` }} /></div><p className="text-[11px] text-[#8993a4]">{category ? `${category} · ` : ''}{confidence >= 85 ? 'High confidence · likely fix identified' : confidence >= 60 ? 'Moderate confidence' : 'Low confidence · needs more context'}</p></>}</div></section></div>
}

function Timeline({ events }: { events: TimelineEvent[] }) {
  const hasEvents = events.length > 0
  return <section className="panel overflow-hidden"><SectionHeader icon={Activity} title="Agent Activity" action={<span className="text-[11px] text-[#8b95a5]">Live timeline</span>} /><div className="px-5 py-5">{!hasEvents ? <div className="empty-activity"><Activity className="h-5 w-5 text-[#aeb8c8]" /><p>Activity will appear here when a run begins.</p></div> : <div className="space-y-0">{events.map((event, index) => { const Icon = TONE_ICON[event.tone] ?? Info; return <div key={`${event.type}-${index}`} className="timeline-item animate-slide-up" style={{ animationDelay: `${Math.min(index, 10) * 60}ms` }}><div className={`timeline-icon tone-${event.tone}`}><Icon className="h-3.5 w-3.5" /></div><div className="min-w-0 flex-1 pb-5"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-[#39465a]">{event.title}</p><time className="text-[10px] text-[#adb5c1]">{event.time}</time></div><p className="mt-1 text-xs leading-5 text-[#788496]">{event.detail}</p></div></div> })}</div>}</div></section>
}

function LanguageMismatch({ mismatch }: { mismatch: LanguageMismatchInfo }) {
  return <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-950 animate-slide-up"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /><div><p className="text-sm font-semibold">Language Mismatch</p><p className="mt-1 text-sm text-amber-900">Selected language: <strong>{mismatch.selectedLanguage}</strong></p><p className="text-sm text-amber-900">Detected language: <strong>{mismatch.detectedLanguage}</strong></p><p className="mt-2 text-sm text-amber-800">Please select {mismatch.detectedLanguage} to continue.</p></div></div></section>
}

function Console({ events, running }: { events: TimelineEvent[]; running: boolean }) {
  const [open, setOpen] = useState(true)
  const execCompleted = events.find(e => e.type === 'execute_completed')
  const errorEvent    = events.find(e => e.type === 'error_detected')
  const successEvent  = events.find(e => e.type === 'repair_success')

  return <section className="panel overflow-hidden"><button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-4 text-left"><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f2f4f7] text-[#536074]"><Terminal className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#202938]">Execution Console</p><p className="text-[11px] text-[#8a94a6]">subprocess · isolated sandbox</p></div></div>{open ? <ChevronDown className="h-4 w-4 text-[#9aa4b3]" /> : <ChevronRight className="h-4 w-4 text-[#9aa4b3]" />}</button>{open && <div className="console-body">{events.length === 0 ? <><p><span className="console-prompt">$</span> waiting for run…</p></> : <><p><span className="console-prompt">$</span> autofix --language {events[0]?.detail?.split('Language: ')?.[1]?.split('.')?.[0] ?? 'python'}</p>{errorEvent && <p className="console-error">{errorEvent.detail}</p>}{execCompleted && <p className="console-muted">{execCompleted.detail}</p>}{successEvent ? <><p className="console-success">Repair successful</p><p className="console-muted">Process exited with code 0</p></> : (running && <p className="console-muted"><Loader2 className="inline h-3 w-3 animate-spin mr-1" />Running…</p>)}</>}</div>}</section>
}

export default function AutoFixDashboard() {
  const [code, setCode] = useState(initialCode)
  const [language, setLanguage] = useState('python')
  const [maxAttempts, setMaxAttempts] = useState(5)

  const { run, abort, events, phase, attempt, diagnosis, validation, languageMismatch, running, error } = useSSERepair()

  const handleRun = () => {
    run({ sourceCode: code, language, maxAttempts, timeout: 5 })
  }

  const handleReset = () => {
    abort()
    setCode(initialCode)
    setLanguage('python')
    setMaxAttempts(5)
  }

  const state: AgentState = phase
  const visible = state !== 'idle' && state !== 'language_mismatch'

  const headerStatus = useMemo(
    () => state === 'success' ? 'Run complete' : state === 'failed' ? 'Repair failed' : running ? 'Agent active' : 'Workspace ready',
    [state, running],
  )

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#202938]">
      <header className="sticky top-0 z-10 border-b border-[#e7eaf0] bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 lg:px-8">
          <div className="flex items-center gap-3">
            <LogoMark />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold tracking-tight text-[#202938]">AutoFix Agent</span>
                <span className="rounded-full bg-[#eef3ff] px-2 py-0.5 text-[10px] font-medium text-[#3568e8]">AI Code Repair</span>
              </div>
              <p className="hidden text-[10px] text-[#98a1ae] sm:block">Autonomous debugging workspace</p>
            </div>
          </div>
          <nav className="hidden items-center gap-1 md:flex">
            <a className="nav-link" href="#activity">Documentation</a>
            <a className="nav-link" href="#console"><GitBranch className="h-3.5 w-3.5" /> GitHub</a>
            <a className="nav-link" href="#about">About</a>
            <div className="ml-3 h-7 w-7 rounded-full bg-[#dce5f8] text-center text-[11px] font-semibold leading-7 text-[#3568e8]">JD</div>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-5 py-8 lg:px-8">
        <div className="mb-7 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-[#6d7890]">
              <span className={`status-dot ${state === 'success' ? 'bg-[#3b9a62]' : state === 'failed' ? 'bg-red-500' : running ? 'bg-[#3568e8]' : 'bg-[#3b9a62]'}`} />
              {headerStatus}
            </div>
            <h1 className="text-balance text-2xl font-semibold tracking-[-0.03em] text-[#202938] sm:text-3xl">Let your code fix itself.</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[#788496]">Upload a script and let AutoFix Agent diagnose, repair, and validate it automatically.</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="secondary-button" onClick={handleReset}><RotateCcw className="h-3.5 w-3.5" /> Reset</button>
            <button className="secondary-button" onClick={() => { setCode(initialCode); setLanguage('python') }}><Sparkles className="h-3.5 w-3.5 text-[#3568e8]" /> Try demo</button>
          </div>
        </div>

        {error && (
          <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">
            <strong>Connection error:</strong> {error}. Make sure the backend is running on{' '}
            <code className="font-mono text-xs">{process.env.NEXT_API_URL ?? 'http://localhost:8000'}</code>.
          </div>
        )}

        {languageMismatch && <LanguageMismatch mismatch={languageMismatch} />}

        <div className="grid gap-5 xl:grid-cols-[minmax(320px,1fr)_minmax(380px,1.08fr)]">
          <CodeInput
            code={code} setCode={setCode}
            onRun={handleRun} onExample={() => setCode(initialCode)}
            running={running} onReset={handleReset}
            language={language} setLanguage={setLanguage}
            maxAttempts={maxAttempts} setMaxAttempts={setMaxAttempts}
          />
          <AgentFlow state={state} attempt={attempt} running={running} maxAttempts={maxAttempts} />
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,.92fr)]" id="activity">
          <Timeline events={events} />
          <DiagnosisAndDiff
            visible={state === 'patching' || state === 'validating' || state === 'success' || state === 'failed'}
            rootCause={diagnosis?.rootCause}
            confidence={diagnosis?.confidence}
            category={diagnosis?.category}
          />
        </div>

        <div className="mt-5" id="console">
          <Console events={events} running={running} />
        </div>

        <div className="mt-8 flex flex-col gap-2 border-t border-[#e5e8ed] pt-5 text-[11px] text-[#9aa3b0] sm:flex-row sm:items-center sm:justify-between">
          <span>AutoFix Agent · Live backend integration</span>
          <span className="flex items-center gap-1.5">
            <Info className="h-3 w-3" />
            Backend: {process.env.NEXT_API_URL ?? 'http://localhost:8000'}
          </span>
        </div>
      </main>
    </div>
  )
}

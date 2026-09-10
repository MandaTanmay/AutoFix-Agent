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

const initialCode = `def calculate_total(price, quantity):
    return priice * quantity

price = 100
quantity = 5

print(calculate_total(price, quantity))`

type AgentState = 'idle' | 'executing' | 'observing' | 'diagnosing' | 'patching' | 'validating' | 'retrying' | 'success'

const stages: { key: AgentState; label: string; description: string; icon: typeof Play }[] = [
  { key: 'executing', label: 'Execute', description: 'Running Python script', icon: Play },
  { key: 'observing', label: 'Observe', description: 'Capturing stdout/stderr', icon: Activity },
  { key: 'diagnosing', label: 'Diagnose', description: 'Analyzing traceback', icon: Sparkles },
  { key: 'patching', label: 'Patch', description: 'Generating repair', icon: WandSparkles },
  { key: 'validating', label: 'Validate', description: 'Running patched code', icon: Check },
  { key: 'success', label: 'Success', description: 'Code passes validation', icon: Check },
]

const timelineEvents = [
  { icon: Play, tone: 'blue', title: 'Execute', detail: 'Running Python script...', time: '10:42:03' },
  { icon: AlertTriangle, tone: 'red', title: 'Error detected', detail: "NameError: name 'priice' is not defined", time: '10:42:04' },
  { icon: Sparkles, tone: 'violet', title: 'AI Diagnosis', detail: 'Variable "priice" appears to be a typo. Expected variable: "price"', time: '10:42:05' },
  { icon: WandSparkles, tone: 'amber', title: 'Patch generated', detail: 'Changed line 2 · 94% confidence', time: '10:42:06' },
  { icon: Check, tone: 'green', title: 'Validation', detail: '500 · Process exited with code 0', time: '10:42:07' },
]

function LogoMark() {
  return <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#3568e8] text-white shadow-sm shadow-blue-200"><Bot className="h-4 w-4" /></div>
}

function SectionHeader({ icon: Icon, title, eyebrow, action }: { icon: typeof Code2; title: string; eyebrow?: string; action?: React.ReactNode }) {
  return <div className="flex items-center justify-between border-b border-[#e7eaf0] px-5 py-4"><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0f4ff] text-[#3568e8]"><Icon className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#202938]">{title}</p>{eyebrow && <p className="text-[11px] text-[#8a94a6]">{eyebrow}</p>}</div></div>{action}</div>
}

function AgentFlow({ state, attempt, running }: { state: AgentState; attempt: number; running: boolean }) {
  const currentIndex = state === 'idle' ? -1 : state === 'retrying' ? 0 : stages.findIndex((stage) => stage.key === state)
  return <section className="panel min-h-[500px] overflow-hidden"><SectionHeader icon={Zap} title="Agent Execution" action={<span className="badge-blue"><span className="status-dot" /> {running ? 'Live session' : 'Ready'}</span>} /><div className="px-5 pb-5 pt-4"><div className="mb-7 flex items-center justify-between"><div><p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#8791a3]">Current attempt</p><p className="mt-1 text-xl font-semibold tracking-tight text-[#202938]">Attempt {attempt} <span className="text-sm font-normal text-[#9ba4b2]">/ 5</span></p></div><div className="flex items-center gap-1.5">{[1, 2, 3, 4, 5].map((item) => <span key={item} className={`h-1.5 w-8 rounded-full ${item <= attempt ? 'bg-[#3568e8]' : 'bg-[#e8ebf0]'}`} />)}</div></div><div className="relative mx-auto max-w-[360px]">{stages.map((stage, index) => { const Icon = stage.icon; const complete = currentIndex > index || state === 'success'; const active = currentIndex === index; return <div key={stage.key} className="relative flex gap-4"><div className="flex w-10 shrink-0 flex-col items-center"><div className={`node ${complete ? 'node-complete' : ''} ${active ? 'node-active' : ''}`}>{complete ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}</div>{index < stages.length - 1 && <div className={`flow-line ${currentIndex > index ? 'flow-line-complete' : ''}`} />}</div><div className={`mb-4 flex min-h-[58px] flex-1 items-center justify-between rounded-xl border px-4 py-3 transition-all ${active ? 'border-[#9db7ff] bg-[#f5f8ff] shadow-sm shadow-blue-100' : complete ? 'border-[#d8eee1] bg-[#f8fcf9]' : 'border-[#edf0f4] bg-white'}`}><div><p className={`text-sm font-semibold ${active ? 'text-[#2858ce]' : complete ? 'text-[#328255]' : 'text-[#536074]'}`}>{stage.label}</p><p className="mt-0.5 text-[11px] text-[#8b95a5]">{active ? stage.description : complete ? 'Completed' : 'Waiting'}</p></div>{active && <Loader2 className="h-4 w-4 animate-spin text-[#3568e8]" />}{complete && <Check className="h-4 w-4 text-[#3a9a62]" />}</div></div> })}</div>{state === 'success' && <div className="success-banner"><div className="success-icon"><Check className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#257348]">Execution successful</p><p className="text-xs text-[#58936f]">Fixed and validated in 2 attempts</p></div></div>}{state === 'idle' && <div className="flow-hint"><CircleDashed className="h-4 w-4 text-[#8da6dd]" /><span>Start a run to watch the agent work through the issue.</span></div>}</div></section>
}

function CodeInput({ code, setCode, onRun, onExample, running, onReset }: { code: string; setCode: (value: string) => void; onRun: () => void; onExample: () => void; running: boolean; onReset: () => void }) {
  return <section className="panel overflow-hidden"><SectionHeader icon={FileCode2} title="Python Script" eyebrow="main.py" action={<button className="icon-button" aria-label="More file options"><Settings2 className="h-4 w-4" /></button>} /><div className="flex items-center gap-1 border-b border-[#edf0f4] px-4 py-2"><button className="tool-button"><Upload className="h-3.5 w-3.5" /> Upload .py</button><button className="tool-button" onClick={onExample}><Copy className="h-3.5 w-3.5" /> Paste code</button><button className="tool-button ml-auto" onClick={onReset}><X className="h-3.5 w-3.5" /> Clear</button><button className="tool-button" onClick={onExample}>Example</button></div><div className="code-editor"><div className="line-numbers">{code.split('\n').map((_, index) => <span key={index}>{index + 1}</span>)}</div><textarea aria-label="Python source code" value={code} onChange={(event) => setCode(event.target.value)} spellCheck={false} /></div><div className="border-t border-[#edf0f4] px-5 py-4"><div className="mb-4 flex flex-wrap items-center gap-3"><label className="flex items-center gap-2 text-xs text-[#687487]">Max attempts<select className="select-control" defaultValue="5"><option>3</option><option>5</option><option>10</option></select></label><span className="flex items-center gap-1.5 text-xs text-[#687487]"><Clock3 className="h-3.5 w-3.5" /> Timeout <strong className="font-medium text-[#384458]">5 sec</strong></span><label className="ml-auto flex cursor-pointer items-center gap-2 text-xs text-[#687487]"><span className="toggle"><span /></span> Run tests</label></div><button className="primary-button w-full" onClick={onRun} disabled={running}>{running ? <><Loader2 className="h-4 w-4 animate-spin" /> Agent running...</> : <><Play className="h-4 w-4 fill-current" /> Run AutoFix Agent</>}</button></div></section>
}

function DiagnosisAndDiff({ visible }: { visible: boolean }) {
  return <div className="space-y-4"><section className={`panel overflow-hidden transition-all ${visible ? 'animate-slide-up' : ''}`}><SectionHeader icon={Sparkles} title="AI Diagnosis" action={<span className="badge-purple">94% confidence</span>} /><div className="space-y-4 px-5 py-4"><div><p className="label">Root cause</p><p className="mt-1 text-sm leading-6 text-[#465267]">The variable <code>priice</code> is not defined. This appears to be a typo in the <code>calculate_total()</code> function.</p></div><div className="confidence-track"><span style={{ width: '94%' }} /></div><p className="text-[11px] text-[#8993a4]">High confidence · likely fix identified</p></div></section><section className={`panel overflow-hidden transition-all ${visible ? 'animate-slide-up delay-100' : ''}`}><SectionHeader icon={Code2} title="Proposed Fix" action={<span className="badge-green"><Check className="h-3 w-3" /> Patch applied</span>} /><div className="diff-viewer"><div className="diff-line diff-removed"><span>−</span><code>return priice * quantity</code></div><div className="diff-line diff-added"><span>+</span><code>return price * quantity</code></div></div><div className="flex items-center gap-2 border-t border-[#edf0f4] px-5 py-3 text-xs text-[#7d8797]"><Check className="h-3.5 w-3.5 text-[#3b9a62]" /> Changed line 2 in main.py <button className="ml-auto text-[#3568e8] hover:underline">View final code <ChevronRight className="inline h-3 w-3" /></button></div></section></div>
}

function Timeline({ visible }: { visible: boolean }) { return <section className="panel overflow-hidden"><SectionHeader icon={Activity} title="Agent Activity" action={<span className="text-[11px] text-[#8b95a5]">Live timeline</span>} /><div className="px-5 py-5">{!visible ? <div className="empty-activity"><Activity className="h-5 w-5 text-[#aeb8c8]" /><p>Activity will appear here when a run begins.</p></div> : <div className="space-y-0">{timelineEvents.map((event, index) => { const Icon = event.icon; return <div key={event.title} className="timeline-item animate-slide-up" style={{ animationDelay: `${index * 100}ms` }}><div className={`timeline-icon tone-${event.tone}`}><Icon className="h-3.5 w-3.5" /></div><div className="min-w-0 flex-1 pb-5"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-[#39465a]">{event.title}</p><time className="text-[10px] text-[#adb5c1]">{event.time}</time></div><p className="mt-1 text-xs leading-5 text-[#788496]">{event.detail}</p></div></div> })}</div>}</div></section> }

function Console({ visible }: { visible: boolean }) { const [open, setOpen] = useState(true); return <section className="panel overflow-hidden"><button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-4 text-left"><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f2f4f7] text-[#536074]"><Terminal className="h-4 w-4" /></div><div><p className="text-sm font-semibold text-[#202938]">Execution Console</p><p className="text-[11px] text-[#8a94a6]">python main.py · light output</p></div></div>{open ? <ChevronDown className="h-4 w-4 text-[#9aa4b3]" /> : <ChevronRight className="h-4 w-4 text-[#9aa4b3]" />}</button>{open && <div className="console-body"><p><span className="console-prompt">$</span> python main.py</p>{visible ? <><p className="console-success">500</p><p className="console-muted">Process exited with code 0</p></> : <><p className="console-error">Traceback (most recent call last):</p><p className="console-muted">  File &quot;main.py&quot;, line 2, in &lt;module&gt;</p><p className="console-muted">    return priice * quantity</p><p className="console-error">NameError: name &apos;priice&apos; is not defined</p><p className="console-muted">Process exited with code 1</p></>}</div>}</section> }

export default function AutoFixDashboard() { const [code, setCode] = useState(initialCode); const [state, setState] = useState<AgentState>('idle'); const [attempt, setAttempt] = useState(1); const timers = useRef<ReturnType<typeof setTimeout>[]>([]); const visible = state !== 'idle'; const running = state !== 'idle' && state !== 'success'; const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = []; }; const runDemo = () => { clearTimers(); setAttempt(1); setState('executing'); const sequence: [number, AgentState, number?][] = [[700, 'observing'], [1400, 'diagnosing'], [2200, 'patching'], [3000, 'validating'], [3900, 'retrying', 2], [4600, 'executing'], [5300, 'observing'], [6000, 'diagnosing'], [6700, 'patching'], [7400, 'validating'], [8200, 'success']]; sequence.forEach(([delay, next, nextAttempt]) => { timers.current.push(setTimeout(() => { setState(next); if (nextAttempt) setAttempt(nextAttempt); }, delay)); }); }; const reset = () => { clearTimers(); setState('idle'); setAttempt(1); setCode(initialCode); }; useEffect(() => () => clearTimers(), []); const headerStatus = useMemo(() => state === 'success' ? 'Run complete' : running ? 'Agent active' : 'Workspace ready', [state, running]); return <div className="min-h-screen bg-[#f7f8fa] text-[#202938]"><header className="sticky top-0 z-10 border-b border-[#e7eaf0] bg-white/95 backdrop-blur"><div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 lg:px-8"><div className="flex items-center gap-3"><LogoMark /><div><div className="flex items-center gap-2"><span className="text-sm font-semibold tracking-tight text-[#202938]">AutoFix Agent</span><span className="rounded-full bg-[#eef3ff] px-2 py-0.5 text-[10px] font-medium text-[#3568e8]">AI Code Repair</span></div><p className="hidden text-[10px] text-[#98a1ae] sm:block">Autonomous debugging workspace</p></div></div><nav className="hidden items-center gap-1 md:flex"><a className="nav-link" href="#activity">Documentation</a><a className="nav-link" href="#console"><GitBranch className="h-3.5 w-3.5" /> GitHub</a><a className="nav-link" href="#about">About</a><div className="ml-3 h-7 w-7 rounded-full bg-[#dce5f8] text-center text-[11px] font-semibold leading-7 text-[#3568e8]">JD</div></nav></div></header><main className="mx-auto max-w-[1440px] px-5 py-8 lg:px-8"><div className="mb-7 flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div><div className="mb-2 flex items-center gap-2 text-xs font-medium text-[#6d7890]"><span className="status-dot bg-[#3b9a62]" /> {headerStatus}</div><h1 className="text-balance text-2xl font-semibold tracking-[-0.03em] text-[#202938] sm:text-3xl">Let your code fix itself.</h1><p className="mt-2 max-w-xl text-sm leading-6 text-[#788496]">Upload a Python script and let AutoFix Agent diagnose, repair, and validate it automatically.</p></div><div className="flex items-center gap-2"><button className="secondary-button" onClick={reset}><RotateCcw className="h-3.5 w-3.5" /> Reset</button><button className="secondary-button" onClick={runDemo}><Sparkles className="h-3.5 w-3.5 text-[#3568e8]" /> Try demo</button></div></div><div className="grid gap-5 xl:grid-cols-[minmax(320px,1fr)_minmax(380px,1.08fr)]"><CodeInput code={code} setCode={setCode} onRun={runDemo} onExample={() => setCode(initialCode)} running={running} onReset={reset} /><AgentFlow state={state} attempt={attempt} running={running} /></div><div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,.92fr)]" id="activity"><Timeline visible={visible} /><DiagnosisAndDiff visible={state === 'patching' || state === 'validating' || state === 'success'} /></div><div className="mt-5" id="console"><Console visible={state === 'success'} /></div><div className="mt-8 flex flex-col gap-2 border-t border-[#e5e8ed] pt-5 text-[11px] text-[#9aa3b0] sm:flex-row sm:items-center sm:justify-between"><span>AutoFix Agent · Frontend demo</span><span className="flex items-center gap-1.5"><Info className="h-3 w-3" /> Backend execution will connect here</span></div></main></div> }

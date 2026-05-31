'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..900;1,14..32,300..900&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg0:    #06080d;
  --bg1:    #0b0e15;
  --bg2:    #111520;
  --bg3:    #171c2b;
  --line:   #1c2235;
  --text:   #dde4f0;
  --dim:    #5a6480;
  --dim2:   #8290aa;
  --a:      #818cf8;
  --a2:     #05d88e;
  --a3:     #f59e0b;
  --red:    #f87171;
  --mono:   'JetBrains Mono', 'Fira Code', monospace;
  --sans:   'Inter', system-ui, -apple-system, sans-serif;
  --r:      10px;
  --rL:     16px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body { background: var(--bg0); color: var(--text); font-family: var(--sans);
       font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
       -webkit-font-smoothing: antialiased; overflow-x: hidden; }
a { text-decoration: none; color: inherit; }
button { font-family: inherit; cursor: pointer; border: none; outline: none; }
::selection { background: rgba(129,140,248,.25); }

/* ── TOKENS ─────────────────────────────────────── */
.t-a   { color: var(--a); }
.t-a2  { color: var(--a2); }
.t-a3  { color: var(--a3); }
.t-red { color: var(--red); }
.t-dim { color: var(--dim); }
.t-dim2{ color: var(--dim2); }
.t-text{ color: var(--text); }
.bold  { font-weight: 700; }
.mono  { font-family: var(--mono); }

/* ── NAV ─────────────────────────────────────────── */
.nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 900;
  height: 56px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 clamp(20px, 4vw, 56px);
  background: rgba(6,8,13,.75);
  border-bottom: 1px solid rgba(255,255,255,.05);
  backdrop-filter: blur(18px) saturate(1.4);
  -webkit-backdrop-filter: blur(18px) saturate(1.4);
}
.nav-brand { font-size: 17px; font-weight: 800; letter-spacing: -0.4px;
  background: linear-gradient(135deg, #a5b4fc 0%, #67e8b0 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.nav-right  { display: flex; align-items: center; gap: 6px; }
.nav-link   { padding: 7px 13px; border-radius: 8px; font-size: 13px; font-weight: 500;
  color: var(--dim2); transition: color .15s, background .15s; }
.nav-link:hover { color: var(--text); background: rgba(255,255,255,.05); }
.nav-gh { padding: 7px 14px; border-radius: 8px; font-size: 13px; font-weight: 600;
  color: var(--text); border: 1px solid var(--line); transition: all .15s; }
.nav-gh:hover { border-color: var(--a); color: var(--a); background: rgba(129,140,248,.06); }
.nav-cta { padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
  background: var(--a); color: #fff; transition: all .15s; }
.nav-cta:hover { background: #6366f1; box-shadow: 0 0 20px rgba(129,140,248,.35); }

/* ── HERO ────────────────────────────────────────── */
.hero {
  position: relative; overflow: hidden;
  padding: calc(56px + 90px) 24px 80px;
  text-align: center;
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 0;
}
.hero::before {
  content: ''; position: absolute; inset: 0; z-index: 0;
  background:
    radial-gradient(ellipse 70% 55% at 50% -5%, rgba(99,102,241,.16) 0%, transparent 65%),
    radial-gradient(ellipse 40% 35% at 80% 80%, rgba(5,216,142,.07) 0%, transparent 60%);
}
.hero::after {
  content: ''; position: absolute; inset: 0; z-index: 0;
  background-image: radial-gradient(circle, rgba(255,255,255,.03) 1px, transparent 1px);
  background-size: 32px 32px;
}
.hero > * { position: relative; z-index: 1; }

.pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 14px 5px 8px; border-radius: 999px;
  border: 1px solid rgba(129,140,248,.25);
  background: rgba(129,140,248,.07);
  font-size: 12px; font-weight: 500; color: #a5b4fc;
  margin-bottom: 32px;
}
.pill-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--a2);
  animation: blink 2.2s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:.3;} }

h1 {
  font-size: clamp(40px, 7.5vw, 78px); font-weight: 900;
  letter-spacing: -3px; line-height: 1.06; margin-bottom: 22px;
}
h1 em { font-style: normal;
  background: linear-gradient(135deg, #a5b4fc 0%, #67e8b0 55%, #fcd34d 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

.hero-sub {
  font-size: clamp(16px, 2.2vw, 19px); color: var(--dim2);
  max-width: 580px; margin: 0 auto 40px; line-height: 1.75; font-weight: 400;
}

.cta-row { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 64px; }
.btn-pri {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 13px 26px; border-radius: var(--r); font-size: 14px; font-weight: 600;
  background: linear-gradient(135deg, #6366f1, #818cf8); color: #fff;
  box-shadow: 0 4px 20px rgba(99,102,241,.3), inset 0 1px 0 rgba(255,255,255,.15);
  transition: all .2s; cursor: pointer; border: none;
}
.btn-pri:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(99,102,241,.4), inset 0 1px 0 rgba(255,255,255,.2); }
.btn-sec {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 13px 26px; border-radius: var(--r); font-size: 14px; font-weight: 500;
  color: var(--dim2); border: 1px solid var(--line); background: transparent;
  transition: all .2s; cursor: pointer;
}
.btn-sec:hover { color: var(--text); border-color: rgba(255,255,255,.15); background: rgba(255,255,255,.04); }

.stat-row { display: flex; gap: 52px; justify-content: center; flex-wrap: wrap;
  padding-top: 40px; border-top: 1px solid var(--line); }
.stat { text-align: center; }
.stat-n { font-size: 30px; font-weight: 800; letter-spacing: -1px; }
.stat-l { font-size: 12px; color: var(--dim); margin-top: 4px; font-weight: 500; letter-spacing: .2px; }

/* ── TAB SECTION ─────────────────────────────────── */
.section { max-width: 1160px; margin: 0 auto; padding: 0 clamp(20px, 4vw, 48px) 100px; }

.tabs-nav {
  display: flex; border-bottom: 1px solid var(--line); margin-bottom: 48px; gap: 4px;
}
.t-btn {
  padding: 13px 22px; font-size: 14px; font-weight: 600; cursor: pointer;
  color: var(--dim); border: none; background: none;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  transition: color .15s, border-color .15s;
}
.t-btn.on { color: var(--text); border-bottom-color: var(--a); }

.tab-layout { display: grid; grid-template-columns: 1.1fr 1fr; gap: 48px; align-items: start; }
@media (max-width: 900px) { .tab-layout { grid-template-columns: 1fr; } }

/* ── TERMINAL ────────────────────────────────────── */
.term {
  background: #05070c; border: 1px solid var(--line); border-radius: var(--rL);
  overflow: hidden; font-family: var(--mono);
  box-shadow: 0 24px 64px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.03);
}
.term-tb {
  background: var(--bg2); padding: 11px 16px;
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--line);
}
.td { width: 11px; height: 11px; border-radius: 50%; }
.term-label { margin-left: auto; font-size: 11px; color: var(--dim); font-family: var(--sans);
  letter-spacing: .3px; }
.term-body { padding: 20px 22px; min-height: 390px; font-size: 12.5px; line-height: 1.9;
  overflow-y: auto; max-height: 420px; }
.tl { white-space: pre-wrap; word-break: break-all; }

.cursor { display: inline-block; width: 7px; height: 13px; background: var(--a2);
  vertical-align: text-bottom; margin-left: 1px;
  animation: cur 1.1s step-end infinite; }
@keyframes cur { 0%,100%{opacity:1;} 50%{opacity:0;} }

/* ── INFO PANEL ──────────────────────────────────── */
.info-head { font-size: clamp(22px, 3vw, 32px); font-weight: 800; letter-spacing: -0.8px;
  line-height: 1.25; margin-bottom: 18px; }
.info-body { color: var(--dim2); font-size: 15px; line-height: 1.75; margin-bottom: 32px; }
.steps { display: flex; flex-direction: column; gap: 22px; margin-bottom: 34px; }
.step-row { display: flex; gap: 14px; align-items: flex-start; }
.sn { width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; margin-top: 2px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: var(--a);
  background: rgba(129,140,248,.12); border: 1px solid rgba(129,140,248,.25); }
.s-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.s-desc  { color: var(--dim2); font-size: 13px; }
.cmd { font-family: var(--mono); background: var(--bg2); border: 1px solid var(--line);
  border-radius: 8px; padding: 10px 14px; font-size: 12.5px; color: var(--a2);
  margin-top: 8px; }

/* ── ORG DASHBOARD ───────────────────────────────── */
.dash {
  background: var(--bg1); border: 1px solid var(--line); border-radius: var(--rL);
  padding: 22px;
  box-shadow: 0 24px 64px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.03);
}
.dash-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.dash-title { font-size: 14px; font-weight: 700; }
.live { background: rgba(5,216,142,.12); color: var(--a2); border: 1px solid rgba(5,216,142,.2);
  padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
  display: flex; align-items: center; gap: 5px; }
.live-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--a2);
  animation: blink 2s ease infinite; }

.kpi { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 18px; }
.kpi-card { background: var(--bg0); border: 1px solid var(--line); border-radius: var(--r);
  padding: 14px 16px; }
.kpi-l { font-size: 10px; color: var(--dim); text-transform: uppercase;
  letter-spacing: .6px; font-weight: 600; margin-bottom: 7px; }
.kpi-v { font-size: 21px; font-weight: 800; letter-spacing: -0.5px; }

.chart-h { height: 160px; position: relative; margin-bottom: 20px; }

.users-hed { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--dim);
  letter-spacing: .6px; margin-bottom: 12px; }
.u-row { display: flex; align-items: center; gap: 11px; margin-bottom: 10px; }
.u-av { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-size: 10px; font-weight: 700; color: #fff; flex-shrink: 0; }
.u-info { flex: 1; }
.u-nm { font-size: 12px; font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 5px; }
.u-tk { font-size: 11px; color: var(--dim); }
.u-trk { height: 4px; background: var(--line); border-radius: 2px; overflow: hidden; }
.u-fill { height: 100%; border-radius: 2px; transition: width 1.2s cubic-bezier(.16,1,.3,1); }

/* ── FEATURE GRID ────────────────────────────────── */
.feats { max-width: 1160px; margin: 0 auto;
  padding: 0 clamp(20px,4vw,48px) 100px; }
.sec-label { font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; color: var(--a); margin-bottom: 16px; text-align: center; }
.sec-head { font-size: clamp(26px, 4vw, 40px); font-weight: 800; letter-spacing: -1px;
  text-align: center; margin-bottom: 56px; line-height: 1.15; }
.sec-head span { color: var(--dim2); }

.fgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 860px) { .fgrid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 540px) { .fgrid { grid-template-columns: 1fr; } }

.fcard {
  background: var(--bg1); border: 1px solid var(--line); border-radius: var(--rL);
  padding: 24px; position: relative; overflow: hidden;
  transition: border-color .2s, transform .2s;
}
.fcard::before { content: ''; position: absolute; inset: 0; opacity: 0;
  background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(129,140,248,.06), transparent);
  transition: opacity .25s; pointer-events: none; }
.fcard:hover { border-color: rgba(129,140,248,.2); transform: translateY(-3px); }
.fcard:hover::before { opacity: 1; }
.fcard-icon { font-size: 26px; margin-bottom: 14px; display: block; }
.fcard-name { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.fcard-desc { font-size: 13px; color: var(--dim2); line-height: 1.65; }

/* ── INSTALL CTA ─────────────────────────────────── */
.install-sec {
  border-top: 1px solid var(--line); padding: 80px clamp(20px,4vw,48px);
  text-align: center; position: relative; overflow: hidden;
}
.install-sec::before { content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 80% at 50% 100%, rgba(99,102,241,.07), transparent); }
.install-sec > * { position: relative; z-index: 1; }
.install-head { font-size: clamp(24px, 4vw, 38px); font-weight: 800; letter-spacing: -1px;
  margin-bottom: 12px; }
.install-sub { color: var(--dim2); font-size: 15px; margin-bottom: 36px; }

.cmd-line {
  display: inline-flex; align-items: center; gap: 14px;
  background: var(--bg1); border: 1px solid var(--line); border-radius: var(--r);
  padding: 13px 20px; cursor: pointer; transition: border-color .2s;
  font-family: var(--mono); font-size: 14px; max-width: 100%;
}
.cmd-line:hover { border-color: rgba(129,140,248,.3); }
.cmd-line .cp { width: 34px; height: 34px; border-radius: 6px; background: rgba(129,140,248,.12);
  border: 1px solid rgba(129,140,248,.2); color: var(--a); display: flex; align-items: center;
  justify-content: center; font-size: 14px; transition: all .15s; flex-shrink: 0; }
.cmd-line:hover .cp { background: rgba(129,140,248,.2); }
.cmd-install { display: flex; flex-direction: column; gap: 14px; align-items: center; margin-bottom: 28px; }

/* ── FOOTER ──────────────────────────────────────── */
footer {
  border-top: 1px solid var(--line); padding: 28px clamp(20px,4vw,56px);
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
}
.f-brand { font-size: 14px; font-weight: 800; letter-spacing: -0.3px; color: var(--dim2); }
.f-links { display: flex; gap: 20px; }
.f-link { font-size: 13px; color: var(--dim); transition: color .15s; }
.f-link:hover { color: var(--text); }
`

// ── Terminal frames ────────────────────────────────────────────────────────────
type Seg = { t: string; c?: string }
type Frame = { segs: Seg[]; ms: number }

const FRAMES: Frame[] = [
  { ms: 200,  segs: [{ t: '$ ', c: 't-a2' }, { t: 'skim proxy --port 7474 --path .', c: 't-text bold' }] },
  { ms: 900,  segs: [{ t: '' }] },
  { ms: 1000, segs: [{ t: '  skim proxy', c: 'bold t-text' }, { t: ' — token interceptor + optimizer', c: 't-dim' }] },
  { ms: 1100, segs: [{ t: '  ─────────────────────────────────────────────', c: 't-dim' }] },
  { ms: 1200, segs: [{ t: '  Listening ', c: 't-dim' }, { t: 'http://localhost:7474', c: 't-a' }] },
  { ms: 1300, segs: [{ t: '  Model     ', c: 't-dim' }, { t: 'claude', c: 't-text' }, { t: '  (200,000 token limit)', c: 't-dim' }] },
  { ms: 1400, segs: [{ t: '  Caching   ', c: 't-dim' }, { t: 'on', c: 't-a2' }, { t: ' — auto-injects cache_control', c: 't-dim' }] },
  { ms: 1500, segs: [{ t: '' }] },
  { ms: 1600, segs: [{ t: '  Set: ', c: 't-a3' }, { t: 'export ANTHROPIC_BASE_URL=http://localhost:7474', c: 't-a2' }] },
  { ms: 1700, segs: [{ t: '' }] },
  { ms: 3200, segs: [{ t: '  ─────────────────────────────────────────────', c: 't-dim' }] },
  { ms: 3300, segs: [{ t: '  [skim] ', c: 'bold t-a' }, { t: '14:23:01', c: 't-dim' }, { t: '  call #1', c: 't-text' }, { t: '  1,247ms', c: 't-dim' }] },
  { ms: 3400, segs: [{ t: '  Context  ', c: 't-dim' }, { t: '████░░░░░░░░░░░░░░░░░░ 12.4%  ', c: 't-a2' }, { t: '24.8k / 200k', c: 't-dim' }] },
  { ms: 3500, segs: [{ t: '  In / Out ', c: 't-dim' }, { t: '24.8k', c: 't-text' }, { t: ' / ', c: 't-dim' }, { t: '1.2k', c: 't-text' }] },
  { ms: 3600, segs: [{ t: '  Stripped ', c: 't-dim' }, { t: '122k waste tokens', c: 't-a2' }, { t: ' (package-lock.json)', c: 't-dim' }] },
  { ms: 3700, segs: [{ t: '' }] },
  { ms: 5200, segs: [{ t: '  [skim] ', c: 'bold t-a' }, { t: '14:23:45', c: 't-dim' }, { t: '  call #2', c: 't-text' }, { t: '  892ms', c: 't-dim' }] },
  { ms: 5300, segs: [{ t: '  Context  ', c: 't-dim' }, { t: '███████░░░░░░░░░░░░░░░ 38.1%  ', c: 't-a2' }, { t: '76.2k / 200k', c: 't-dim' }] },
  { ms: 5400, segs: [{ t: '  In / Out ', c: 't-dim' }, { t: '51.4k / 2.1k', c: 't-text' }] },
  { ms: 5500, segs: [{ t: '  Cache hit', c: 't-dim' }, { t: ' 18.6k tokens free', c: 't-a' }, { t: ' (system prompt cached)', c: 't-dim' }] },
  { ms: 5600, segs: [{ t: '' }] },
  { ms: 7100, segs: [{ t: '  [skim] ', c: 'bold t-a' }, { t: '14:24:12', c: 't-dim' }, { t: '  call #3', c: 't-text' }, { t: '  1,033ms', c: 't-dim' }] },
  { ms: 7200, segs: [{ t: '  Context  ', c: 't-dim' }, { t: '███████████░░░░░░░░░░░ 59.2%  ', c: 't-a3' }, { t: '118k / 200k', c: 't-dim' }] },
  { ms: 7300, segs: [{ t: '  →  ', c: 't-a3' }, { t: '59% full — consider /compact soon', c: 't-a3' }] },
  { ms: 7400, segs: [{ t: '' }] },
  { ms: 8900, segs: [{ t: '  [skim] ', c: 'bold t-a' }, { t: '14:24:55', c: 't-dim' }, { t: '  call #4', c: 't-text' }, { t: '  788ms', c: 't-dim' }] },
  { ms: 9000, segs: [{ t: '  Context  ', c: 't-dim' }, { t: '████████████████░░░░░░ 78.4%  ', c: 't-red' }, { t: '157k / 200k', c: 't-dim' }] },
  { ms: 9100, segs: [{ t: '  ⚠  ', c: 't-red bold' }, { t: '78% full — run /compact NOW', c: 't-red' }] },
]

function Terminal() {
  const [n, setN] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    setN(0)
    const ts = FRAMES.map((f, i) => setTimeout(() => setN(v => Math.max(v, i + 1)), f.ms))
    return () => ts.forEach(clearTimeout)
  }, [])
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [n])
  return (
    <div className="term">
      <div className="term-tb">
        <div className="td" style={{ background: '#ff5f57' }} />
        <div className="td" style={{ background: '#ffbd2e' }} />
        <div className="td" style={{ background: '#28ca41' }} />
        <span className="term-label">skim proxy — live</span>
      </div>
      <div className="term-body" ref={ref}>
        {FRAMES.slice(0, n).map((f, i) => (
          <div key={i} className="tl">
            {f.segs.map((s, j) =>
              <span key={j} className={s.c || ''}>{s.t}</span>
            )}
          </div>
        ))}
        {n > 0 && n < FRAMES.length && <div className="tl"><span className="cursor" /></div>}
      </div>
    </div>
  )
}

// ── Org Dashboard ─────────────────────────────────────────────────────────────
const TEAM = [
  { n: 'Arjun S.',  role: 'Backend', tok: 1840, color: '#818cf8' },
  { n: 'Yuki T.',   role: 'ML Eng',  tok: 1520, color: '#05d88e' },
  { n: 'Mia K.',    role: 'Frontend',tok: 980,  color: '#f59e0b' },
  { n: 'Omar R.',   role: 'DevOps',  tok: 760,  color: '#3b82f6' },
  { n: 'Priya N.',  role: 'Backend', tok: 620,  color: '#a78bfa' },
]

function OrgDash() {
  const cRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => { setReady(true) }, [])
  useEffect(() => {
    if (!ready || !cRef.current) return
    const w = window as any
    if (!w.Chart) { const t = setInterval(() => { if (w.Chart) { setReady(r => !r); clearInterval(t) } }, 200); return () => clearInterval(t) }
    const lbs = ['May 19','May 21','May 23','May 25','May 27','May 29','May 31'].map(d => d)
    const sent  = [820,940,1080,990,1240,1180,1340].map(v => v * 1000)
    const saved = [165,195,224,208,258,244,282].map(v => v * 1000)
    const ctx   = cRef.current.getContext('2d')!
    const chart = new w.Chart(ctx, {
      type: 'line',
      data: {
        labels: lbs,
        datasets: [
          { label: 'Sent', data: sent, borderColor: '#818cf8', backgroundColor: 'rgba(129,140,248,.07)', fill: true, tension: 0.45, pointRadius: 0, borderWidth: 2 },
          { label: 'Saved', data: saved, borderColor: '#05d88e', backgroundColor: 'rgba(5,216,142,.04)', fill: true, tension: 0.45, pointRadius: 0, borderWidth: 2, borderDash: [4,3] },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#5a6480', font: { size: 11, family: 'Inter' }, boxWidth: 14, padding: 16 } } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,.03)' }, ticks: { color: '#5a6480', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,.03)' }, ticks: { color: '#5a6480', font: { size: 10 }, callback: (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : (v/1e3)+'k' } },
        },
      },
    })
    return () => chart.destroy()
  }, [ready])

  const max = TEAM[0].tok
  return (
    <div className="dash">
      <div className="dash-hdr">
        <span className="dash-title">Team Token Intelligence</span>
        <span className="live"><span className="live-dot" />LIVE</span>
      </div>
      <div className="kpi">
        <div className="kpi-card">
          <div className="kpi-l">Monthly cost</div>
          <div className="kpi-v t-text">$4,820</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-l">Saved by skim</div>
          <div className="kpi-v t-a2">$1,940</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-l">Team size</div>
          <div className="kpi-v" style={{ color: '#e1e8f0' }}>47</div>
        </div>
      </div>
      <div className="chart-h"><canvas ref={cRef} /></div>
      <div className="users-hed">Top users this month</div>
      {TEAM.map(u => (
        <div key={u.n} className="u-row">
          <div className="u-av" style={{ background: u.color }}>{u.n[0]}</div>
          <div className="u-info">
            <div className="u-nm">
              <span>{u.n} <span style={{ color: '#5a6480', fontWeight: 400 }}>· {u.role}</span></span>
              <span className="u-tk">{(u.tok / 1000).toFixed(1)}M tok</span>
            </div>
            <div className="u-trk">
              <div className="u-fill" style={{ width: `${u.tok / max * 100}%`, background: u.color }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Page() {
  const [tab, setTab] = useState<'dev'|'org'>('dev')
  const [copied, setCopied] = useState('')

  const copy = (s: string, key: string) => {
    navigator.clipboard.writeText(s).catch(() => {})
    setCopied(key)
    setTimeout(() => setCopied(''), 2000)
  }

  const FEATS = [
    { i: '⚡', n: 'Runtime proxy', d: 'Intercepts every LLM API call. No code changes — just one env var. Works with Claude Code, Cursor, and any OpenAI-compatible tool.' },
    { i: '🧠', n: 'Prompt caching auto-inject', d: 'Adds cache_control to your system prompt and large context blocks. Claude caches them transparently — 50–90% cheaper on repeat calls.' },
    { i: '📊', n: 'Team dashboard', d: 'Per-user, per-team cost attribution. Budget alerts. Usage trends. Self-hosted with Docker. JWT + SSO / LDAP / Azure AD.' },
    { i: '🔑', n: 'Secrets detection', d: 'Scans for AWS keys, OpenAI tokens, GitHub PATs, and private keys before they reach an LLM. CI-ready with --fail for hard blocks.' },
    { i: '📐', n: 'Baseline regression', d: 'Save a token snapshot before a refactor. Compare after. Catch context bloat in PR review before it ships to production.' },
    { i: '🔒', n: 'CI budget gate', d: 'skim check exits 1 if the project exceeds its token budget. Drop into GitHub Actions in 3 lines.' },
  ]

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      <nav className="nav">
        <div className="nav-brand">skim</div>
        <div className="nav-right">
          <button className="nav-link" onClick={() => setTab('dev')}>Individual</button>
          <button className="nav-link" onClick={() => setTab('org')}>Enterprise</button>
          <a className="nav-gh" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">
            GitHub ↗
          </a>
          <a className="nav-cta" href="https://github.com/bb1nfosec/skim#readme" target="_blank" rel="noopener">
            Get started
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="pill"><div className="pill-dot" />Open source · MIT License</div>
        <h1>The runtime layer<br />your LLM tools<br /><em>don't have.</em></h1>
        <p className="hero-sub">
          skim intercepts every API call between your tools and Claude / GPT.
          It strips token waste in real-time, auto-injects prompt caching, shows live
          context fill %, and gives teams a full cost dashboard — without touching a line of code.
        </p>
        <div className="cta-row">
          <button className="btn-pri" onClick={() => copy('pip install skim-llm', 'hero')}>
            {copied === 'hero' ? '✓ Copied' : '$ pip install skim-llm'}
          </button>
          <a className="btn-sec" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">
            ★ Star on GitHub
          </a>
        </div>
        <div className="stat-row">
          <div className="stat"><div className="stat-n t-a2">96%</div><div className="stat-l">context reduction</div></div>
          <div className="stat"><div className="stat-n t-a">50–90%</div><div className="stat-l">cost savings via caching</div></div>
          <div className="stat"><div className="stat-n" style={{ color: '#e1e8f0' }}>1 var</div><div className="stat-l">to activate everything</div></div>
          <div className="stat"><div className="stat-n t-a3">0ms</div><div className="stat-l">latency on cache hits</div></div>
        </div>
      </section>

      {/* Demo tabs */}
      <div className="section">
        <div className="tabs-nav">
          <button className={`t-btn${tab === 'dev' ? ' on' : ''}`} onClick={() => setTab('dev')}>
            👤 Individual  &nbsp;<span style={{ fontSize: 11, color: 'var(--dim)' }}>Claude Code Pro</span>
          </button>
          <button className={`t-btn${tab === 'org' ? ' on' : ''}`} onClick={() => setTab('org')}>
            🏢 Team / Enterprise
          </button>
        </div>

        {tab === 'dev' && (
          <div className="tab-layout">
            <Terminal />
            <div>
              <h2 className="info-head">See exactly when your<br />context window fills up</h2>
              <p className="info-body">
                Claude Code Pro users hit a silent quality cliff: context fills up, the model
                starts forgetting context, and responses degrade — with no warning.
                skim shows you live context fill % and auto-strips waste before it counts.
                It also injects Anthropic prompt caching so your system prompt is free on every call after the first.
              </p>
              <div className="steps">
                {[
                  { s: '1', h: 'Install', d: 'Zero hard dependencies — just Python 3.10+.', cmd: 'pip install skim-llm' },
                  { s: '2', h: 'Start the proxy', d: 'Runs locally. Nothing leaves your machine except the actual API call.', cmd: 'skim proxy --port 7474 --path .' },
                  { s: '3', h: 'Point Claude Code at it', d: 'One env var. Every call now goes through skim — fully transparent.', cmd: 'export ANTHROPIC_BASE_URL=http://localhost:7474' },
                ].map(step => (
                  <div key={step.s} className="step-row">
                    <div className="sn">{step.s}</div>
                    <div>
                      <div className="s-title">{step.h}</div>
                      <div className="s-desc">{step.d}</div>
                      <div className="cmd" onClick={() => copy(step.cmd, step.s)} style={{ cursor: 'pointer' }}>
                        {copied === step.s ? '✓ Copied' : step.cmd}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <a className="btn-pri" href="https://github.com/bb1nfosec/skim#readme" target="_blank" rel="noopener" style={{ fontSize: 13, padding: '10px 20px', display: 'inline-flex' }}>
                Full documentation →
              </a>
            </div>
          </div>
        )}

        {tab === 'org' && (
          <div className="tab-layout">
            <OrgDash />
            <div>
              <h2 className="info-head">Cost attribution &amp;<br />budget enforcement<br />for your whole org</h2>
              <p className="info-body">
                500 developers all using Claude. Zero visibility into who's spending what.
                skim gives you a per-developer, per-team cost dashboard, budget alerts,
                and hard budget enforcement — with a single Docker container and one env var per developer.
                SSO, LDAP, and Azure AD are supported out of the box.
              </p>
              <div className="steps">
                {[
                  { s: '1', h: 'Deploy the skim server', d: 'Self-hosted. Your data stays on your infrastructure.', cmd: 'docker run -p 7475:7475 -e SKIM_ADMIN_EMAIL=you@corp.com ghcr.io/bb1nfosec/skim' },
                  { s: '2', h: 'One env var per developer', d: 'Or set it org-wide via your MDM / env management.', cmd: 'export SKIM_SERVER_URL=https://skim.corp.internal' },
                  { s: '3', h: 'Open the dashboard', d: 'Real-time cost breakdown, trends, and budget status.' },
                ].map(step => (
                  <div key={step.s} className="step-row">
                    <div className="sn">{step.s}</div>
                    <div>
                      <div className="s-title">{step.h}</div>
                      <div className="s-desc">{step.d}</div>
                      {step.cmd && <div className="cmd" style={{ fontSize: 11 }}>{step.cmd}</div>}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <a className="btn-pri" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener" style={{ fontSize: 13, padding: '10px 20px', display: 'inline-flex' }}>
                  View on GitHub →
                </a>
                <a className="btn-sec" href="https://github.com/bb1nfosec/skim/issues" target="_blank" rel="noopener" style={{ fontSize: 13, padding: '10px 20px', display: 'inline-flex' }}>
                  Request a feature
                </a>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Features */}
      <section className="feats">
        <p className="sec-label">Everything included</p>
        <h2 className="sec-head">One tool. <span>The whole stack.</span></h2>
        <div className="fgrid">
          {FEATS.map(f => (
            <div key={f.n} className="fcard">
              <span className="fcard-icon">{f.i}</span>
              <div className="fcard-name">{f.n}</div>
              <div className="fcard-desc">{f.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Install CTA */}
      <section className="install-sec">
        <h2 className="install-head">Start in 30 seconds</h2>
        <p className="install-sub">Open source. Self-hostable. No account required. No tracking.</p>
        <div className="cmd-install">
          <div className="cmd-line" onClick={() => copy('pip install skim-llm', 'install')}>
            <span style={{ color: 'var(--a2)' }}>$</span>
            <span style={{ fontFamily: 'var(--mono)' }}> pip install skim-llm</span>
            <div className="cp">{copied === 'install' ? '✓' : '⎘'}</div>
          </div>
          <div className="cmd-line" onClick={() => copy('export ANTHROPIC_BASE_URL=http://localhost:7474', 'env')}>
            <span style={{ color: 'var(--a2)' }}>$</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 13 }}> export ANTHROPIC_BASE_URL=http://localhost:7474</span>
            <div className="cp">{copied === 'env' ? '✓' : '⎘'}</div>
          </div>
        </div>
        <a className="btn-pri" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">
          View full docs on GitHub →
        </a>
      </section>

      <footer>
        <div className="f-brand">skim — MIT License · by bb1nfosec</div>
        <div className="f-links">
          <a className="f-link" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">GitHub</a>
          <a className="f-link" href="https://github.com/bb1nfosec/skim/issues" target="_blank" rel="noopener">Issues</a>
          <a className="f-link" href="https://github.com/bb1nfosec/skim/blob/main/CHANGELOG.md" target="_blank" rel="noopener">Changelog</a>
          <a className="f-link" href="https://github.com/bb1nfosec/skim/blob/main/LICENSE" target="_blank" rel="noopener">License</a>
        </div>
      </footer>
    </>
  )
}

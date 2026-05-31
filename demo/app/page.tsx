'use client'
import { useEffect, useRef, useState } from 'react'

/* ─────────────────────────────────────────────────────────────────────────────
   Color psychology notes (for future contributors):

   Background:  #0c0d10  — near-black with a very slight cool undertone.
                Cooler than "warm black" but not harsh. Like carbon fiber.
   Surface:     #13151a  — a step lighter, same temperature
   Blue accent: #2563eb  — Royal/ocean blue. Associated with trust, depth,
                reliability. IBM, PayPal, LinkedIn all use this family.
                NOT electric indigo — that reads as "AI tool".
   Green:       #059669  — Forest/emerald green. Feels like health, growth,
                savings. The neon green from AI palettes feels artificial.
   Amber:       #d97706  — Warm amber, not yellow. Energy without alarm.
                Traffic lights use amber for "pay attention" — right for
                context fill warnings.
   Red:         #dc2626  — Proper signal red. Clear and calm, not hot pink.
   Text:        #e2e8f0  — Slate-200. Has the tiniest blue cast which
                reads as "technical" without feeling cold.
   Muted:       #64748b  — Slate-500. Warm mid-gray with blue tint.
───────────────────────────────────────────────────────────────────────────── */

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300..800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg0:    #0c0d10;
  --bg1:    #13151a;
  --bg2:    #1a1d25;
  --bg3:    #22262f;
  --line:   #2a2f3a;
  --text:   #e2e8f0;
  --muted:  #64748b;
  --dim:    #94a3b8;

  /* Ocean blue — trust, depth, reliability */
  --blue:   #2563eb;
  --blue-l: #3b82f6;
  --blue-d: #1d4ed8;

  /* Forest green — health, savings, success */
  --green:  #059669;
  --green-l:#10b981;

  /* Amber — warm attention, not alarm */
  --amber:  #d97706;
  --amber-l:#f59e0b;

  /* Signal red — clear without being harsh */
  --red:    #dc2626;
  --red-l:  #ef4444;

  --mono: 'JetBrains Mono', 'Fira Code', monospace;
  --sans: 'Inter', system-ui, sans-serif;
  --r:  8px;
  --rL: 14px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg0); color: var(--text);
  font-family: var(--sans); font-size: 15px;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: 'cv02','cv03','cv04';
  overflow-x: hidden;
}
a { text-decoration: none; color: inherit; }
button { font-family: inherit; border: none; outline: none; cursor: pointer; }
::selection { background: rgba(37,99,235,.3); }

/* ── NAV ────────────────── */
.nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 900;
  height: 58px; display: flex; align-items: center;
  justify-content: space-between;
  padding: 0 clamp(16px, 4vw, 52px);
  background: rgba(12,13,16,.8);
  border-bottom: 1px solid rgba(255,255,255,.06);
  backdrop-filter: blur(20px);
}
.nav-brand {
  font-size: 16px; font-weight: 800; letter-spacing: -0.3px;
  color: var(--blue-l);
}
.nav-right { display: flex; align-items: center; gap: 4px; }
.nav-link {
  padding: 7px 12px; border-radius: var(--r);
  font-size: 13px; font-weight: 500; color: var(--muted);
  transition: color .15s, background .15s; background: none;
}
.nav-link:hover { color: var(--text); background: rgba(255,255,255,.05); }
.nav-gh {
  padding: 7px 14px; border-radius: var(--r);
  font-size: 13px; font-weight: 600; color: var(--dim);
  border: 1px solid var(--line); transition: all .15s; background: none;
}
.nav-gh:hover { color: var(--text); border-color: var(--blue-l); }
.nav-cta {
  padding: 8px 18px; border-radius: var(--r);
  font-size: 13px; font-weight: 600;
  background: var(--blue); color: #fff;
  transition: background .15s, box-shadow .15s;
}
.nav-cta:hover {
  background: var(--blue-d);
  box-shadow: 0 0 0 3px rgba(37,99,235,.25);
}

/* ── HERO ───────────────── */
.hero {
  padding: calc(58px + 80px) 24px 72px;
  text-align: center; position: relative; overflow: hidden;
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.hero-glow {
  position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 65% 50% at 50% -2%,  rgba(37,99,235,.13)  0%, transparent 65%),
    radial-gradient(ellipse 35% 30% at 85% 75%,  rgba(5,150,105,.06)  0%, transparent 55%),
    radial-gradient(ellipse 25% 25% at 15% 85%,  rgba(217,119,6,.05)  0%, transparent 55%);
}
.hero-grid {
  position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 80%);
}
.hero > * { position: relative; z-index: 1; }

.pill {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 5px 14px 5px 8px; border-radius: 999px;
  border: 1px solid rgba(37,99,235,.3);
  background: rgba(37,99,235,.08);
  font-size: 12px; font-weight: 500; color: var(--blue-l);
  margin-bottom: 28px;
}
.pill-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--green-l);
  animation: blink 2.4s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:.25;} }

h1 {
  font-size: clamp(38px, 7vw, 76px);
  font-weight: 800; letter-spacing: -2.5px;
  line-height: 1.07; margin-bottom: 20px;
  color: var(--text);
}
h1 .hl {
  background: linear-gradient(135deg, var(--blue-l) 0%, #60a5fa 40%, var(--green-l) 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-p {
  font-size: clamp(15px, 2vw, 18px); color: var(--muted);
  max-width: 560px; margin: 0 auto 36px; line-height: 1.75; font-weight: 400;
}

.cta-wrap { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 60px; }

.btn-p {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border-radius: var(--r); font-size: 14px; font-weight: 600;
  background: var(--blue); color: #fff; border: none;
  box-shadow: 0 1px 3px rgba(0,0,0,.4), 0 4px 16px rgba(37,99,235,.3);
  transition: all .2s; cursor: pointer;
}
.btn-p:hover { background: var(--blue-d); box-shadow: 0 2px 6px rgba(0,0,0,.4), 0 8px 24px rgba(37,99,235,.4); transform: translateY(-1px); }

.btn-s {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border-radius: var(--r); font-size: 14px; font-weight: 500;
  background: transparent; color: var(--dim); border: 1px solid var(--line);
  transition: all .2s; cursor: pointer;
}
.btn-s:hover { color: var(--text); border-color: rgba(255,255,255,.15); background: rgba(255,255,255,.03); }

.stats {
  display: flex; gap: 48px; justify-content: center; flex-wrap: wrap;
  padding-top: 36px; border-top: 1px solid var(--line);
}
.stat-n { font-size: 28px; font-weight: 800; letter-spacing: -1px; }
.stat-l { font-size: 12px; color: var(--muted); margin-top: 3px; font-weight: 500; }
.c-blue  { color: var(--blue-l); }
.c-green { color: var(--green-l); }
.c-amber { color: var(--amber-l); }
.c-red   { color: var(--red-l); }

/* ── SECTION WRAPPER ────── */
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 clamp(16px,4vw,48px); }

/* ── TABS ───────────────── */
.tabs-nav {
  display: flex; border-bottom: 1px solid var(--line);
  margin-bottom: 48px; gap: 2px;
}
.tab-btn {
  padding: 12px 22px; font-size: 14px; font-weight: 600;
  color: var(--muted); background: none; border: none;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  transition: color .15s, border-color .15s; cursor: pointer;
}
.tab-btn.on { color: var(--text); border-bottom-color: var(--blue-l); }

.tab-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 48px; align-items: start; }
@media(max-width:880px){ .tab-grid { grid-template-columns: 1fr; } }

/* ── TERMINAL ───────────── */
.term {
  background: #070810; border: 1px solid var(--line);
  border-radius: var(--rL); overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.025);
}
.term-bar {
  background: var(--bg2); padding: 10px 16px;
  display: flex; align-items: center; gap: 7px;
  border-bottom: 1px solid var(--line);
}
.td { width: 11px; height: 11px; border-radius: 50%; }
.term-lbl { margin-left: auto; font-size: 11px; color: var(--muted);
  font-family: var(--sans); letter-spacing: .2px; }
.term-body {
  padding: 18px 20px; min-height: 380px;
  font-family: var(--mono); font-size: 12.5px; line-height: 1.85;
  overflow-y: auto; max-height: 410px;
}
.tl { white-space: pre-wrap; word-break: break-all; }
.tc-blue   { color: var(--blue-l); }
.tc-green  { color: var(--green-l); }
.tc-amber  { color: var(--amber-l); }
.tc-red    { color: var(--red-l); }
.tc-muted  { color: var(--muted); }
.tc-dim    { color: var(--dim); }
.tc-white  { color: var(--text); }
.tc-b      { font-weight: 700; }
.cur {
  display: inline-block; width: 7px; height: 13px;
  background: var(--green-l); vertical-align: text-bottom; margin-left: 1px;
  animation: blink-c 1.1s step-end infinite;
}
@keyframes blink-c { 0%,100%{opacity:1;} 50%{opacity:0;} }

/* ── INFO PANEL ─────────── */
.info-h {
  font-size: clamp(22px,3vw,30px); font-weight: 800;
  letter-spacing: -0.6px; line-height: 1.25; margin-bottom: 16px;
}
.info-p { color: var(--muted); font-size: 14.5px; line-height: 1.75; margin-bottom: 28px; }

.steps { display: flex; flex-direction: column; gap: 20px; margin-bottom: 30px; }
.s-row { display: flex; gap: 14px; align-items: flex-start; }
.sn {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; margin-top: 1px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: var(--blue-l);
  background: rgba(37,99,235,.1); border: 1px solid rgba(37,99,235,.25);
}
.s-h { font-size: 14px; font-weight: 600; margin-bottom: 3px; }
.s-d { color: var(--muted); font-size: 13px; line-height: 1.6; }
.cmd {
  font-family: var(--mono); background: var(--bg1); border: 1px solid var(--line);
  border-radius: var(--r); padding: 9px 14px; font-size: 12.5px;
  color: var(--green-l); margin-top: 8px; cursor: pointer;
  transition: border-color .15s; display: block;
}
.cmd:hover { border-color: rgba(5,150,105,.4); }

/* ── ORG DASH ───────────── */
.dash {
  background: var(--bg1); border: 1px solid var(--line);
  border-radius: var(--rL); padding: 20px;
  box-shadow: 0 20px 60px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.025);
}
.dash-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.dash-t { font-size: 13px; font-weight: 700; }
.live-chip {
  display: flex; align-items: center; gap: 5px;
  background: rgba(5,150,105,.1); border: 1px solid rgba(5,150,105,.2);
  color: var(--green-l); padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
}
.live-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--green-l); animation: blink 2s infinite; }
.kpi { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 16px; }
.k {
  background: var(--bg0); border: 1px solid var(--line);
  border-radius: var(--r); padding: 12px 14px;
}
.kl { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; font-weight: 600; margin-bottom: 6px; }
.kv { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
.ch  { height: 150px; position: relative; margin-bottom: 18px; }
.uh  { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--muted); letter-spacing: .6px; margin-bottom: 10px; }
.ur  { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
.uav { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #fff; flex-shrink: 0; }
.ui  { flex: 1; }
.unm { font-size: 12px; font-weight: 600; display: flex; justify-content: space-between; margin-bottom: 4px; }
.utk { font-size: 11px; color: var(--muted); }
.utr { height: 4px; background: var(--line); border-radius: 2px; overflow: hidden; }
.uf  { height: 100%; border-radius: 2px; }

/* ── FEATURE GRID ───────── */
.sec-label {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; color: var(--blue-l); margin-bottom: 14px; text-align: center;
}
.sec-h {
  font-size: clamp(26px,4vw,38px); font-weight: 800;
  letter-spacing: -0.8px; text-align: center; margin-bottom: 48px;
  line-height: 1.18; color: var(--text);
}
.sec-h .muted-h { color: var(--muted); }

.fgrid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; }
@media(max-width:840px){ .fgrid { grid-template-columns: repeat(2,1fr); } }
@media(max-width:520px){ .fgrid { grid-template-columns: 1fr; } }

.fc {
  background: var(--bg1); border: 1px solid var(--line);
  border-radius: var(--rL); padding: 22px;
  transition: border-color .2s, transform .2s;
  position: relative; overflow: hidden;
}
.fc::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 70% 50% at 50% 0%, rgba(37,99,235,.04), transparent);
  opacity: 0; transition: opacity .25s; pointer-events: none;
}
.fc:hover { border-color: rgba(37,99,235,.25); transform: translateY(-2px); }
.fc:hover::after { opacity: 1; }
.fc-icon { font-size: 24px; margin-bottom: 12px; display: block; }
.fc-n { font-size: 14px; font-weight: 700; margin-bottom: 7px; }
.fc-d { font-size: 13px; color: var(--muted); line-height: 1.65; }

/* ── CTA INSTALL ────────── */
.install-sec {
  border-top: 1px solid var(--line); padding: 72px clamp(16px,4vw,48px);
  text-align: center; position: relative; overflow: hidden;
}
.install-glow {
  position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse 55% 75% at 50% 100%, rgba(37,99,235,.07), transparent);
}
.install-sec > * { position: relative; z-index: 1; }
.install-h { font-size: clamp(24px,4vw,36px); font-weight: 800; letter-spacing: -0.8px; margin-bottom: 10px; }
.install-s { color: var(--muted); font-size: 14px; margin-bottom: 32px; }
.cmd-stack { display: flex; flex-direction: column; gap: 12px; align-items: center; margin-bottom: 28px; }
.cmd-row {
  display: inline-flex; align-items: center; gap: 12px;
  background: var(--bg1); border: 1px solid var(--line);
  border-radius: var(--r); padding: 11px 18px; cursor: pointer;
  transition: border-color .15s; max-width: 100%;
}
.cmd-row:hover { border-color: rgba(37,99,235,.3); }
.cmd-row code { font-family: var(--mono); font-size: 13px; color: var(--dim); }
.cp {
  width: 30px; height: 30px; border-radius: 6px; flex-shrink: 0;
  background: rgba(37,99,235,.1); border: 1px solid rgba(37,99,235,.2);
  color: var(--blue-l); display: flex; align-items: center; justify-content: center;
  font-size: 13px; transition: all .15s;
}
.cmd-row:hover .cp { background: rgba(37,99,235,.2); }

/* ── FOOTER ─────────────── */
footer {
  border-top: 1px solid var(--line); padding: 26px clamp(16px,4vw,52px);
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;
}
.f-b { font-size: 13px; font-weight: 700; color: var(--muted); }
.f-l { display: flex; gap: 18px; }
.f-a { font-size: 13px; color: var(--muted); transition: color .15s; }
.f-a:hover { color: var(--text); }

/* padding sections */
.pb80 { padding-bottom: 80px; }
.pb96 { padding-bottom: 96px; }
`

// ── Terminal frames ─────────────────────────────────────────────────────────
type Seg = { t: string; c?: string }
type Frame = { segs: Seg[]; ms: number }

const FRAMES: Frame[] = [
  { ms: 300,  segs: [{ t: '$ ', c: 'tc-green' }, { t: 'skim proxy --port 7474 --path .', c: 'tc-white tc-b' }] },
  { ms: 1000, segs: [{ t: '' }] },
  { ms: 1100, segs: [{ t: '  skim proxy', c: 'tc-white tc-b' }, { t: ' — runtime token interceptor', c: 'tc-muted' }] },
  { ms: 1200, segs: [{ t: '  ─────────────────────────────────────────', c: 'tc-muted' }] },
  { ms: 1300, segs: [{ t: '  Listening  ', c: 'tc-muted' }, { t: 'http://localhost:7474', c: 'tc-blue' }] },
  { ms: 1400, segs: [{ t: '  Model      ', c: 'tc-muted' }, { t: 'claude', c: 'tc-white' }, { t: '  (200k limit)', c: 'tc-muted' }] },
  { ms: 1500, segs: [{ t: '  Caching    ', c: 'tc-muted' }, { t: 'on', c: 'tc-green' }, { t: ' — auto-injects cache_control', c: 'tc-muted' }] },
  { ms: 1600, segs: [{ t: '  Filtering  ', c: 'tc-muted' }, { t: 'on', c: 'tc-green' }, { t: ' — strips waste from tool results', c: 'tc-muted' }] },
  { ms: 1700, segs: [{ t: '' }] },
  { ms: 1800, segs: [{ t: '  Activate: ', c: 'tc-amber' }, { t: 'export ANTHROPIC_BASE_URL=http://localhost:7474', c: 'tc-green' }] },
  { ms: 1900, segs: [{ t: '' }] },
  { ms: 3400, segs: [{ t: '  [skim] ', c: 'tc-blue tc-b' }, { t: '14:23:01', c: 'tc-muted' }, { t: '  call #1  1,247ms', c: 'tc-dim' }] },
  { ms: 3500, segs: [{ t: '  Context  ', c: 'tc-muted' }, { t: '████░░░░░░░░░░░░░░░░░░ 12.4%', c: 'tc-green' }, { t: '  24.8k/200k', c: 'tc-muted' }] },
  { ms: 3600, segs: [{ t: '  In/Out   ', c: 'tc-muted' }, { t: '24.8k / 1.2k', c: 'tc-white' }] },
  { ms: 3700, segs: [{ t: '  Stripped ', c: 'tc-muted' }, { t: '122k waste', c: 'tc-green' }, { t: ' (package-lock.json)', c: 'tc-muted' }] },
  { ms: 3800, segs: [{ t: '' }] },
  { ms: 5300, segs: [{ t: '  [skim] ', c: 'tc-blue tc-b' }, { t: '14:23:45', c: 'tc-muted' }, { t: '  call #2  892ms', c: 'tc-dim' }] },
  { ms: 5400, segs: [{ t: '  Context  ', c: 'tc-muted' }, { t: '███████░░░░░░░░░░░░░░░ 38.1%', c: 'tc-green' }, { t: '  76.2k/200k', c: 'tc-muted' }] },
  { ms: 5500, segs: [{ t: '  In/Out   ', c: 'tc-muted' }, { t: '51.4k / 2.1k', c: 'tc-white' }] },
  { ms: 5600, segs: [{ t: '  Cache hit', c: 'tc-muted' }, { t: ' 18.6k tokens free', c: 'tc-blue' }, { t: ' (system prompt)', c: 'tc-muted' }] },
  { ms: 5700, segs: [{ t: '' }] },
  { ms: 7200, segs: [{ t: '  [skim] ', c: 'tc-blue tc-b' }, { t: '14:24:12', c: 'tc-muted' }, { t: '  call #3  1,033ms', c: 'tc-dim' }] },
  { ms: 7300, segs: [{ t: '  Context  ', c: 'tc-muted' }, { t: '███████████░░░░░░░░░░░ 59.2%', c: 'tc-amber' }, { t: '  118k/200k', c: 'tc-muted' }] },
  { ms: 7400, segs: [{ t: '  →  ', c: 'tc-amber tc-b' }, { t: '59% full — consider /compact soon', c: 'tc-amber' }] },
  { ms: 7500, segs: [{ t: '' }] },
  { ms: 9000, segs: [{ t: '  [skim] ', c: 'tc-blue tc-b' }, { t: '14:24:55', c: 'tc-muted' }, { t: '  call #4  788ms', c: 'tc-dim' }] },
  { ms: 9100, segs: [{ t: '  Context  ', c: 'tc-muted' }, { t: '████████████████░░░░░░ 78.4%', c: 'tc-red' }, { t: '  157k/200k', c: 'tc-muted' }] },
  { ms: 9200, segs: [{ t: '  ⚠  ', c: 'tc-red tc-b' }, { t: '78% full — run /compact NOW before quality drops', c: 'tc-red' }] },
]

function Terminal() {
  const [n, setN] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    setN(0)
    const ts = FRAMES.map((f, i) => setTimeout(() => setN(v => Math.max(v, i + 1)), f.ms))
    return () => ts.forEach(clearTimeout)
  }, [])
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [n])
  return (
    <div className="term">
      <div className="term-bar">
        <div className="td" style={{ background: '#ff5f57' }} />
        <div className="td" style={{ background: '#febc2e' }} />
        <div className="td" style={{ background: '#28c840' }} />
        <span className="term-lbl">skim proxy</span>
      </div>
      <div className="term-body" ref={ref}>
        {FRAMES.slice(0, n).map((f, i) => (
          <div key={i} className="tl">
            {f.segs.map((s, j) => <span key={j} className={s.c || ''}>{s.t}</span>)}
          </div>
        ))}
        {n > 0 && n < FRAMES.length && <div className="tl"><span className="cur" /></div>}
      </div>
    </div>
  )
}

// ── Org Dashboard ──────────────────────────────────────────────────────────
const TEAM = [
  { n: 'Arjun S.',  team: 'Backend',  tok: 1840, color: '#3b82f6' },
  { n: 'Yuki T.',   team: 'ML Eng',   tok: 1520, color: '#10b981' },
  { n: 'Mia K.',    team: 'Frontend', tok:  980, color: '#d97706' },
  { n: 'Omar R.',   team: 'DevOps',   tok:  760, color: '#8b5cf6' },
  { n: 'Priya N.',  team: 'Backend',  tok:  620, color: '#ec4899' },
]

function OrgDash() {
  const cRef = useRef<HTMLCanvasElement>(null)
  const [tick, setTick] = useState(0)
  useEffect(() => { setTick(t => t + 1) }, [])
  useEffect(() => {
    if (!cRef.current) return
    const w = window as any
    if (!w.Chart) {
      const id = setInterval(() => { if (w.Chart) { setTick(t => t + 1); clearInterval(id) } }, 300)
      return () => clearInterval(id)
    }
    const lbs = ['May 19', 'May 21', 'May 23', 'May 25', 'May 27', 'May 29', 'May 31']
    const sent  = [820, 940, 1080, 990, 1240, 1180, 1340].map(v => v * 1000)
    const saved = [165, 195, 224, 208, 258, 244, 282].map(v => v * 1000)
    const ctx = cRef.current.getContext('2d')!
    const chart = new w.Chart(ctx, {
      type: 'line',
      data: {
        labels: lbs,
        datasets: [
          { label: 'Tokens sent', data: sent, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.06)', fill: true, tension: 0.45, pointRadius: 0, borderWidth: 2 },
          { label: 'Saved', data: saved, borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,.04)', fill: true, tension: 0.45, pointRadius: 0, borderWidth: 2, borderDash: [4, 3] },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#64748b', font: { size: 11, family: 'Inter' }, boxWidth: 12, padding: 14 } } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,.03)' }, ticks: { color: '#64748b', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,.03)' }, ticks: { color: '#64748b', font: { size: 10 }, callback: (v: number) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : (v/1e3)+'k' } },
        },
      },
    })
    return () => chart.destroy()
  }, [tick])
  const max = TEAM[0].tok
  return (
    <div className="dash">
      <div className="dash-hdr">
        <span className="dash-t">Team Token Dashboard</span>
        <span className="live-chip"><span className="live-dot" />LIVE</span>
      </div>
      <div className="kpi">
        {[['Monthly cost','$4,820','tc-white'],['Saved by skim','$1,940','c-green'],['Developers','47','tc-white']].map(([l,v,c])=>(
          <div key={l} className="k"><div className="kl">{l}</div><div className={`kv ${c}`}>{v}</div></div>
        ))}
      </div>
      <div className="ch"><canvas ref={cRef} /></div>
      <div className="uh">Top users — May</div>
      {TEAM.map(u => (
        <div key={u.n} className="ur">
          <div className="uav" style={{ background: u.color }}>{u.n[0]}</div>
          <div className="ui">
            <div className="unm">
              <span>{u.n} <span className="utk">· {u.team}</span></span>
              <span className="utk">{(u.tok/1000).toFixed(1)}M</span>
            </div>
            <div className="utr">
              <div className="uf" style={{ width: `${u.tok/max*100}%`, background: u.color }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function Page() {
  const [tab, setTab] = useState<'dev'|'org'>('dev')
  const [cp, setCp] = useState('')
  const copy = (s: string, k: string) => {
    navigator.clipboard.writeText(s).catch(() => {})
    setCp(k); setTimeout(() => setCp(''), 2000)
  }

  const FEATS = [
    { i: '⚡', n: 'Runtime proxy', d: 'Intercepts every API call. No code changes. Works with Claude Code, Cursor, and any OpenAI-compatible tool — one env var.' },
    { i: '🧠', n: 'Prompt caching', d: 'Auto-injects cache_control into your system prompt. Anthropic caches it; subsequent calls read it for free. 50–90% savings on repeated context.' },
    { i: '📊', n: 'Team dashboard', d: 'Per-user, per-team cost attribution, budget alerts, trend charts. Self-hosted. JWT auth + SSO / LDAP / Azure AD.' },
    { i: '🔑', n: 'Secrets detection', d: 'Scans for AWS keys, OpenAI tokens, GitHub PATs, private keys. CI-ready — pass --fail to block builds with exposed credentials.' },
    { i: '📐', n: 'Baseline regression', d: 'Save a token snapshot before a refactor. Compare after. Catch context bloat in PR review before it ships.' },
    { i: '🔒', n: 'CI budget gate', d: 'skim check exits 1 if context exceeds your limit. Three lines in GitHub Actions. Hooks into pre-commit as well.' },
  ]

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      <nav className="nav">
        <div className="nav-brand">skim</div>
        <div className="nav-right">
          <button className="nav-link" onClick={() => setTab('dev')}>Individual</button>
          <button className="nav-link" onClick={() => setTab('org')}>Enterprise</button>
          <a className="nav-gh" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">GitHub ↗</a>
          <a className="nav-cta" href="https://github.com/bb1nfosec/skim#quickstart" target="_blank" rel="noopener">Get started</a>
        </div>
      </nav>

      <section className="hero">
        <div className="hero-glow" />
        <div className="hero-grid" />
        <div className="pill"><div className="pill-dot" />Open source · MIT · Zero hard dependencies</div>
        <h1>
          The runtime layer<br />
          your AI tools<br />
          <span className="hl">don't have.</span>
        </h1>
        <p className="hero-p">
          skim sits between Claude Code (or any LLM tool) and the API.
          It strips token waste in real-time, injects prompt caching automatically,
          and tells you live when your context window is filling up —
          without changing a single line of code.
        </p>
        <div className="cta-wrap">
          <button className="btn-p" onClick={() => copy('pip install skim-llm', 'hero')}>
            {cp === 'hero' ? '✓ Copied' : '$ pip install skim-llm'}
          </button>
          <a className="btn-s" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">
            ★ Star on GitHub
          </a>
        </div>
        <div className="stats">
          <div className="stat"><div className="stat-n c-green">96%</div><div className="stat-l">context reduction</div></div>
          <div className="stat"><div className="stat-n c-blue">50–90%</div><div className="stat-l">cost savings via caching</div></div>
          <div className="stat"><div className="stat-n" style={{color:'var(--text)'}}>1 var</div><div className="stat-l">to activate everything</div></div>
          <div className="stat"><div className="stat-n c-amber">$0</div><div className="stat-l">on cache hit calls</div></div>
        </div>
      </section>

      <div className="wrap pb80">
        <div className="tabs-nav">
          <button className={`tab-btn${tab==='dev'?' on':''}`} onClick={() => setTab('dev')}>
            👤 Individual &nbsp;<span style={{fontSize:11,color:'var(--muted)'}}>Claude Code Pro</span>
          </button>
          <button className={`tab-btn${tab==='org'?' on':''}`} onClick={() => setTab('org')}>
            🏢 Team / Enterprise
          </button>
        </div>

        {tab === 'dev' && (
          <div className="tab-grid">
            <Terminal />
            <div>
              <h2 className="info-h">See your context window fill up — in real-time</h2>
              <p className="info-p">
                Claude Code Pro users run into a hidden problem: context fills up, the model
                quietly starts forgetting earlier work, and response quality drops — with no signal.
                skim shows you live context fill % after every call and automatically strips waste
                before it counts. It also caches your system prompt so it costs nothing on calls 2+.
              </p>
              <div className="steps">
                {[
                  { n:'1', h:'Install', d:'Zero hard dependencies. Python 3.10+.', cmd:'pip install skim-llm' },
                  { n:'2', h:'Start the proxy', d:'Runs locally on your machine.', cmd:'skim proxy --port 7474 --path .' },
                  { n:'3', h:'Activate', d:'Every Claude Code call now goes through skim.', cmd:'export ANTHROPIC_BASE_URL=http://localhost:7474' },
                ].map(s => (
                  <div key={s.n} className="s-row">
                    <div className="sn">{s.n}</div>
                    <div>
                      <div className="s-h">{s.h}</div>
                      <div className="s-d">{s.d}</div>
                      <div className="cmd" onClick={() => copy(s.cmd, s.n)}>{cp===s.n?'✓ Copied':s.cmd}</div>
                    </div>
                  </div>
                ))}
              </div>
              <a className="btn-p" href="https://github.com/bb1nfosec/skim#readme" target="_blank" rel="noopener" style={{fontSize:13,padding:'9px 18px',display:'inline-flex'}}>
                Read the docs →
              </a>
            </div>
          </div>
        )}

        {tab === 'org' && (
          <div className="tab-grid">
            <OrgDash />
            <div>
              <h2 className="info-h">Cost attribution &amp; budget enforcement for your whole org</h2>
              <p className="info-p">
                500 developers using Claude. Zero visibility into who's spending what.
                skim gives you a live per-developer, per-team cost dashboard, budget alerts,
                and policy enforcement — with one Docker container and one env var per developer.
                SSO, LDAP, and Azure AD out of the box.
              </p>
              <div className="steps">
                {[
                  { n:'1', h:'Deploy the server', d:'Self-hosted. Your data stays on your infra.', cmd:'docker run -p 7475:7475 -e SKIM_ADMIN_EMAIL=you@corp.com ghcr.io/bb1nfosec/skim' },
                  { n:'2', h:'Connect each proxy', d:'One env var per developer (or push via MDM).', cmd:'export SKIM_SERVER_URL=https://skim.corp.internal' },
                  { n:'3', h:'Open the dashboard', d:'Real-time cost breakdown, trends, budget status.' },
                ].map(s => (
                  <div key={s.n} className="s-row">
                    <div className="sn">{s.n}</div>
                    <div>
                      <div className="s-h">{s.h}</div>
                      <div className="s-d">{s.d}</div>
                      {s.cmd && <div className="cmd" style={{fontSize:11,wordBreak:'break-all'}} onClick={() => copy(s.cmd,s.n)}>{cp===s.n?'✓ Copied':s.cmd}</div>}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
                <a className="btn-p" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener" style={{fontSize:13,padding:'9px 18px',display:'inline-flex'}}>View on GitHub →</a>
                <a className="btn-s" href="https://github.com/bb1nfosec/skim/issues" target="_blank" rel="noopener" style={{fontSize:13,padding:'9px 18px',display:'inline-flex'}}>Request a feature</a>
              </div>
            </div>
          </div>
        )}
      </div>

      <section className="wrap pb96">
        <p className="sec-label">Everything included</p>
        <h2 className="sec-h">One install. <span className="muted-h">The full stack.</span></h2>
        <div className="fgrid">
          {FEATS.map(f => (
            <div key={f.n} className="fc">
              <span className="fc-icon">{f.i}</span>
              <div className="fc-n">{f.n}</div>
              <div className="fc-d">{f.d}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="install-sec">
        <div className="install-glow" />
        <h2 className="install-h">Start in 30 seconds</h2>
        <p className="install-s">Open source. Self-hostable. No account required.</p>
        <div className="cmd-stack">
          {[
            { cmd:'pip install skim-llm',                               k:'i1' },
            { cmd:'export ANTHROPIC_BASE_URL=http://localhost:7474',    k:'i2' },
          ].map(({cmd,k}) => (
            <div key={k} className="cmd-row" onClick={() => copy(cmd, k)}>
              <code><span style={{color:'var(--green-l)'}}>$</span> {cmd}</code>
              <div className="cp">{cp===k?'✓':'⎘'}</div>
            </div>
          ))}
        </div>
        <a className="btn-p" href="https://github.com/bb1nfosec/skim" target="_blank" rel="noopener">
          View full docs on GitHub →
        </a>
      </section>

      <footer>
        <div className="f-b">skim · MIT License · by bb1nfosec</div>
        <div className="f-l">
          {[['GitHub','https://github.com/bb1nfosec/skim'],['Issues','https://github.com/bb1nfosec/skim/issues'],['Changelog','https://github.com/bb1nfosec/skim/blob/main/CHANGELOG.md'],['License','https://github.com/bb1nfosec/skim/blob/main/LICENSE']].map(([l,h])=>(
            <a key={l} className="f-a" href={h} target="_blank" rel="noopener">{l}</a>
          ))}
        </div>
      </footer>
    </>
  )
}

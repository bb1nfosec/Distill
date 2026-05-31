'use client'
import { useState, useEffect, useRef } from 'react'

/* ── design tokens ─────────────────────────────────────────────────────── */
const C = {
  bg: '#0a0c10', surface: '#111318', surface2: '#161920',
  border: '#1e2130', border2: '#252a3a',
  text: '#e4e6f0', muted: '#6b7280',
  accent: '#6c63ff', accent2: '#00d4aa', warn: '#f5a623', danger: '#ff4d6d', blue: '#3b82f6',
}
const FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
const MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"

/* ── count-up hook ─────────────────────────────────────────────────────── */
function useCountUp(to: number, dur = 1400, decimals = 0) {
  const [v, setV] = useState(0)
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const t0 = performance.now()
    const tick = (now: number) => {
      const p = Math.min((now - t0) / dur, 1)
      setV(to * (1 - Math.pow(1 - p, 3)))
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [to, dur])
  return decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString()
}

function Badge({ children, color = C.accent }: any) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 11px',
      borderRadius: 99, fontSize: 12, fontWeight: 600, color,
      background: color + '18', border: `1px solid ${color}33`,
    }}>{children}</span>
  )
}

function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: 6, borderRadius: 99, background: C.border, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, borderRadius: 99, background: color, transition: 'width 1s ease' }} />
    </div>
  )
}

export default function Home() {
  const [mode, setMode] = useState<'individual' | 'enterprise'>('individual')
  const saved = useCountUp(160300)
  const pct = useCountUp(96, 1600)
  const cost = useCountUp(0.48, 1600, 2)

  return (
    <main style={{ background: C.bg, color: C.text, fontFamily: FONT, minHeight: '100vh', overflowX: 'hidden' }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      <style>{`
        * { box-sizing: border-box; }
        ::selection { background: ${C.accent}44; }
        a { color: inherit; }
        .glow { position: absolute; border-radius: 50%; filter: blur(90px); opacity: .2; pointer-events: none; }
        .card { background: ${C.surface}; border: 1px solid ${C.border}; border-radius: 14px; transition: border-color .2s, transform .2s; }
        .card:hover { border-color: ${C.border2}; transform: translateY(-2px); }
        .btn { display:inline-flex; align-items:center; gap:8px; padding:12px 22px; border-radius:10px; font-weight:600; font-size:15px; cursor:pointer; text-decoration:none; border:none; transition:all .15s; }
        .btn-primary { background:${C.accent}; color:#fff; }
        .btn-primary:hover { background:#5a52e0; transform:translateY(-1px); }
        .btn-ghost { background:transparent; color:${C.text}; border:1px solid ${C.border2}; }
        .btn-ghost:hover { border-color:${C.muted}; }
      `}</style>

      {/* nav */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 50, backdropFilter: 'blur(12px)',
        background: 'rgba(10,12,16,.7)', borderBottom: `1px solid ${C.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, background: C.accent, display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 18 }}>≈</div>
            <span style={{ fontWeight: 800, fontSize: 19, letterSpacing: -0.5 }}>skim</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, fontSize: 14 }}>
            <a href="https://github.com/bb1nfosec/skim" style={{ color: C.muted, textDecoration: 'none' }}>GitHub</a>
            <a href="https://pypi.org/project/skim-llm/" style={{ color: C.muted, textDecoration: 'none' }}>PyPI</a>
            <a href="https://github.com/bb1nfosec/skim/tree/main/docs" style={{ color: C.muted, textDecoration: 'none' }}>Docs</a>
            <a className="btn btn-primary" style={{ padding: '8px 16px', fontSize: 14 }} href="https://github.com/bb1nfosec/skim#-quickstart">Get started</a>
          </div>
        </div>
      </nav>

      {/* hero */}
      <section style={{ position: 'relative', maxWidth: 1000, margin: '0 auto', padding: '90px 24px 64px', textAlign: 'center' }}>
        <div className="glow" style={{ width: 520, height: 520, background: C.accent, top: -120, left: '50%', transform: 'translateX(-50%)' }} />
        <div style={{ position: 'relative' }}>
          <Badge color={C.accent2}>● &nbsp;v0.5.1 · MIT · pip install skim-llm</Badge>
          <h1 style={{ fontSize: 'clamp(2.4rem, 6vw, 4.4rem)', fontWeight: 800, letterSpacing: -2, lineHeight: 1.04, margin: '26px 0 18px' }}>
            Stop paying for tokens<br />you never meant to send.
          </h1>
          <p style={{ fontSize: 'clamp(1rem, 2.5vw, 1.3rem)', color: C.muted, maxWidth: 620, margin: '0 auto 34px', lineHeight: 1.6 }}>
            The runtime layer between your AI tools and the LLM API — stripping waste,
            injecting caching, and showing exactly where every token goes.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <a className="btn btn-primary" href="https://github.com/bb1nfosec/skim#-quickstart">⚡ Quickstart</a>
            <a className="btn btn-ghost" href="https://github.com/bb1nfosec/skim/tree/main/docs/enterprise.md">🏢 Enterprise</a>
          </div>

          {/* terminal */}
          <div className="card" style={{ marginTop: 50, textAlign: 'left', maxWidth: 660, marginLeft: 'auto', marginRight: 'auto', overflow: 'hidden' }}>
            <div style={{ display: 'flex', gap: 7, padding: '12px 16px', borderBottom: `1px solid ${C.border}` }}>
              <span style={{ width: 11, height: 11, borderRadius: 99, background: '#ff5f56' }} />
              <span style={{ width: 11, height: 11, borderRadius: 99, background: '#ffbd2e' }} />
              <span style={{ width: 11, height: 11, borderRadius: 99, background: '#27c93f' }} />
            </div>
            <pre style={{ margin: 0, padding: '18px', fontFamily: MONO, fontSize: 12.5, lineHeight: 1.85, color: C.text, overflowX: 'auto' }}>
<span style={{ color: C.muted }}>$ </span>pip install skim-llm{'\n'}
<span style={{ color: C.muted }}>$ </span>skim proxy{'  '}<span style={{ color: C.muted }}># dashboard opens in your browser</span>{'\n'}
<span style={{ color: C.muted }}>$ </span>export ANTHROPIC_API_KEY=<span style={{ color: C.warn }}>sk-ant-…</span>{'\n'}
<span style={{ color: C.muted }}>$ </span>export ANTHROPIC_BASE_URL=<span style={{ color: C.accent2 }}>http://localhost:7474</span>{'\n\n'}
<span style={{ color: C.accent2 }}>  ⠿ LIVE</span>  call #4  788ms{'\n'}
<span style={{ color: C.muted }}>  ctx </span><span style={{ color: C.accent }}>███████░░░░░░░</span> 38%  <span style={{ color: C.accent2 }}>▼ stripped 122k</span>{'\n'}
<span style={{ color: C.muted }}>  in 51.4k · out 2.1k · </span><span style={{ color: C.accent2 }}>◈ cache hit 18.6k free</span>
            </pre>
          </div>
          <div style={{ marginTop: 14, fontSize: 12.5, color: C.muted }}>
            Works with Claude Code, Cursor, the SDK &amp; any OpenAI-compatible tool.
          </div>
        </div>
      </section>

      {/* impact stats */}
      <section style={{ maxWidth: 1000, margin: '0 auto', padding: '0 24px 70px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 16 }}>
          {[
            [saved, 'tokens stripped / session', C.accent2],
            [`${pct}%`, 'context reduction', C.accent],
            [`$${cost}`, 'saved / session', C.warn],
            ['0', 'code changes required', C.blue],
          ].map(([v, l, c], i) => (
            <div key={i} className="card" style={{ padding: 26, textAlign: 'center' }}>
              <div style={{ fontSize: 38, fontWeight: 800, color: c as string, letterSpacing: -1 }}>{v as string}</div>
              <div style={{ color: C.muted, fontSize: 13, marginTop: 6 }}>{l as string}</div>
            </div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px 70px' }}>
        <h2 style={{ fontSize: 'clamp(1.6rem,4vw,2.4rem)', fontWeight: 800, letterSpacing: -1, textAlign: 'center', marginBottom: 12 }}>One env var. Everything in the path.</h2>
        <p style={{ color: C.muted, textAlign: 'center', maxWidth: 560, margin: '0 auto 44px', fontSize: 16 }}>
          skim sits between your tool and the API. Every call flows through four stages.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16 }}>
          {[
            { i: '✂️', t: 'Strip waste', d: 'Lock files & build artifacts removed from tool results before they hit context. 122k → 12 tokens.', c: C.accent },
            { i: '◈', t: 'Inject caching', d: 'System prompt + large context wrapped with cache_control. First call caches, every call after is free.', c: C.accent2 },
            { i: '🛡️', t: 'Enforce budgets', d: 'Per-user & per-team token / cost limits. Hard 429 block when exceeded. Enterprise mode.', c: C.warn },
            { i: '📊', t: 'Show everything', d: 'Live dashboard opens on start. Real-time SSE. Every token, cost & cache hit — visible.', c: C.blue },
          ].map((s, i) => (
            <div key={i} className="card" style={{ padding: 26 }}>
              <div style={{ width: 46, height: 46, borderRadius: 11, display: 'grid', placeItems: 'center', fontSize: 22, background: s.c + '18', border: `1px solid ${s.c}33`, marginBottom: 16 }}>{s.i}</div>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 8 }}>{s.t}</h3>
              <p style={{ color: C.muted, fontSize: 14, lineHeight: 1.7, margin: 0 }}>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* individual vs enterprise */}
      <section style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px 70px' }}>
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <h2 style={{ fontSize: 'clamp(1.6rem,4vw,2.4rem)', fontWeight: 800, letterSpacing: -1, marginBottom: 18 }}>Built for one dev or a thousand.</h2>
          <div style={{ display: 'inline-flex', background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 5, gap: 4 }}>
            {(['individual', 'enterprise'] as const).map(m => (
              <button key={m} onClick={() => setMode(m)} style={{
                padding: '9px 22px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontWeight: 600, fontSize: 14, fontFamily: FONT, textTransform: 'capitalize',
                background: mode === m ? C.accent : 'transparent',
                color: mode === m ? '#fff' : C.muted, transition: 'all .15s',
              }}>{m}</button>
            ))}
          </div>
        </div>

        {mode === 'individual' ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 20, alignItems: 'start' }}>
            <div>
              <Badge color={C.accent2}>Solo developers · API key</Badge>
              <h3 style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.5, margin: '16px 0 12px' }}>Zero setup. Opens in your browser.</h3>
              <p style={{ color: C.muted, fontSize: 15, lineHeight: 1.7, marginBottom: 16 }}>
                Run <code style={{ color: C.accent2, fontFamily: MONO }}>skim proxy</code> and a live dashboard opens automatically — no login,
                no server. Point any API-key client at it and every call is filtered, cached, and tracked.
                Data stays local in <code style={{ color: C.accent2, fontFamily: MONO }}>~/.skim/events.db</code>.
              </p>
              <div style={{ background: C.warn + '12', border: `1px solid ${C.warn}33`, borderRadius: 10, padding: '12px 14px', marginBottom: 18, fontSize: 13, lineHeight: 1.6 }}>
                <b style={{ color: C.warn }}>⚠ Claude Code on a Pro/Max subscription</b> routes to Anthropic
                directly and can&apos;t use a local proxy. Use <code style={{ color: C.accent2, fontFamily: MONO }}>ANTHROPIC_API_KEY</code> to
                intercept Claude Code — Cursor, the SDK &amp; OpenAI-compatible tools work either way.
              </div>
              {[
                ['Live local dashboard', '5 pages: overview, sessions, usage, models, savings'],
                ['Real-time updates', 'SSE stream — watch tokens & cost as they happen'],
                ['100% private', 'Nothing leaves your machine'],
              ].map(([t, d], i) => (
                <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <span style={{ color: C.accent2, fontWeight: 700 }}>✓</span>
                  <div><b style={{ fontSize: 14 }}>{t}</b><div style={{ color: C.muted, fontSize: 13 }}>{d}</div></div>
                </div>
              ))}
            </div>
            <div className="card" style={{ padding: 22 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                <b style={{ fontSize: 14 }}>Overview</b><Badge color={C.accent2}>● LIVE</Badge>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 18 }}>
                {[['Tokens sent', '1.8M', C.accent], ['Saved', '441k', C.accent2], ['Cost', '$5.47', C.warn], ['Cache hits', '52%', C.blue]].map(([l, v, c], i) => (
                  <div key={i} style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 10, padding: 14 }}>
                    <div style={{ color: C.muted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5 }}>{l}</div>
                    <div style={{ fontSize: 22, fontWeight: 800, color: c as string, letterSpacing: -0.5 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ color: C.muted, fontSize: 11, marginBottom: 8 }}>Context fill</div>
              <Bar pct={38} color={C.accent} />
              <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 70, marginTop: 22 }}>
                {[40, 65, 35, 80, 55, 90, 70, 48, 75, 60].map((h, i) => (
                  <div key={i} style={{ flex: 1, height: `${h}%`, background: i % 2 ? C.accent2 + '88' : C.accent + '88', borderRadius: 3 }} />
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 20, alignItems: 'start' }}>
            <div>
              <Badge color={C.accent}>Teams · Orgs · Self-hosted</Badge>
              <h3 style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.5, margin: '16px 0 12px' }}>A control plane for org-wide spend.</h3>
              <p style={{ color: C.muted, fontSize: 15, lineHeight: 1.7, marginBottom: 20 }}>
                Point every developer&apos;s proxy at one <code style={{ color: C.accent2, fontFamily: MONO }}>skim server</code>.
                Set hard budgets, get Slack alerts before limits hit, invite users with single-use links,
                scope API keys, and export everything for finance. Open source, self-hosted, no telemetry.
              </p>
              {[
                ['Budget enforcement', 'Hard 429 block per user / team / global'],
                ['Webhook alerts', 'Slack & Teams on budget.warning / exceeded'],
                ['SSO + LDAP', 'OIDC (Google, GitHub, Azure AD, Okta) & AD'],
                ['RBAC + audit log', 'admin / team_admin / user, every action logged'],
                ['Data export + retention', 'CSV / JSON for finance; purge for compliance'],
                ['skim admin CLI', 'Manage it all from the terminal'],
              ].map(([t, d], i) => (
                <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <span style={{ color: C.accent, fontWeight: 700 }}>✓</span>
                  <div><b style={{ fontSize: 14 }}>{t}</b><div style={{ color: C.muted, fontSize: 13 }}>{d}</div></div>
                </div>
              ))}
            </div>
            <div className="card" style={{ padding: 22 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                <b style={{ fontSize: 14 }}>Team leaderboard</b><Badge color={C.warn}>3 over 80%</Badge>
              </div>
              {[
                ['platform-team', 82, C.danger, '$1,204'],
                ['core-api', 64, C.warn, '$892'],
                ['frontend', 41, C.accent2, '$510'],
                ['data', 28, C.accent2, '$340'],
              ].map(([name, p, c, spend], i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                    <span style={{ fontWeight: 600 }}>{name}</span>
                    <span style={{ color: C.muted }}>{spend} · {p}%</span>
                  </div>
                  <Bar pct={p as number} color={c as string} />
                </div>
              ))}
              <div style={{ marginTop: 18, padding: 12, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 10, fontFamily: MONO, fontSize: 12, color: C.muted }}>
                <span style={{ color: C.warn }}>🔔 webhook</span> → platform-team hit 80% (Slack)
              </div>
            </div>
          </div>
        )}
      </section>

      {/* cta */}
      <section style={{ maxWidth: 760, margin: '0 auto', padding: '0 24px 80px', textAlign: 'center' }}>
        <div className="card" style={{ padding: '44px 32px', position: 'relative', overflow: 'hidden' }}>
          <div className="glow" style={{ width: 300, height: 300, background: C.accent2, bottom: -150, left: '50%', transform: 'translateX(-50%)' }} />
          <div style={{ position: 'relative' }}>
            <h2 style={{ fontSize: 'clamp(1.5rem,4vw,2.2rem)', fontWeight: 800, letterSpacing: -1, marginBottom: 14 }}>Start in 60 seconds.</h2>
            <p style={{ color: C.muted, marginBottom: 26, fontSize: 15 }}>Zero hard dependencies. Self-hosted. MIT licensed.</p>
            <div style={{ display: 'inline-block', background: C.bg, border: `1px solid ${C.border2}`, borderRadius: 10, padding: '14px 24px', fontFamily: MONO, fontSize: 15, marginBottom: 26 }}>
              <span style={{ color: C.muted }}>$ </span>pip install skim-llm
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
              <a className="btn btn-primary" href="https://github.com/bb1nfosec/skim">⭐ Star on GitHub</a>
              <a className="btn btn-ghost" href="https://github.com/bb1nfosec/skim/tree/main/docs">Read the docs</a>
            </div>
          </div>
        </div>
      </section>

      {/* footer */}
      <footer style={{ borderTop: `1px solid ${C.border}`, padding: '32px 24px', textAlign: 'center', color: C.muted, fontSize: 13 }}>
        <div style={{ display: 'flex', gap: 18, justifyContent: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
          <a href="https://github.com/bb1nfosec/skim" style={{ color: C.muted, textDecoration: 'none' }}>GitHub</a>
          <a href="https://pypi.org/project/skim-llm/" style={{ color: C.muted, textDecoration: 'none' }}>PyPI</a>
          <a href="https://github.com/bb1nfosec/skim/tree/main/docs" style={{ color: C.muted, textDecoration: 'none' }}>Docs</a>
          <a href="https://github.com/bb1nfosec/skim/blob/main/CHANGELOG.md" style={{ color: C.muted, textDecoration: 'none' }}>Changelog</a>
        </div>
        <div>Open source · Self-hosted · MIT licensed · skim v0.5.1</div>
      </footer>
    </main>
  )
}

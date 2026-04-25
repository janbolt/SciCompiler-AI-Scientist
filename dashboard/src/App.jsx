import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, ReferenceLine,
} from 'recharts'
import {
  Upload, Activity, Zap, Shield, Brain, Dna, Heart,
  FlaskConical, Target, Wifi, Layers, Cpu,
} from 'lucide-react'
import './index.css'

// ── Constants ────────────────────────────────────────────────────────
const CHRON_AGE = 42
const BIO_AGE_TARGET = 34

// ── Static Data ──────────────────────────────────────────────────────
const trajectoryData = [
  { age: 25, standard: 92, optimized: 95 },
  { age: 30, standard: 88, optimized: 93 },
  { age: 34, standard: 84, optimized: 91 },
  { age: 40, standard: 76, optimized: 87 },
  { age: 50, standard: 63, optimized: 80 },
  { age: 60, standard: 50, optimized: 71 },
  { age: 70, standard: 37, optimized: 59 },
  { age: 80, standard: 25, optimized: 45 },
  { age: 90, standard: 15, optimized: 32 },
]

const radarData = [
  { subject: 'Mitochondrial', A: 82 },
  { subject: 'Telomere', A: 74 },
  { subject: 'Low Inflam.', A: 69 },
  { subject: 'NAD+ Levels', A: 71 },
  { subject: 'Autophagy', A: 65 },
  { subject: 'Proteostasis', A: 78 },
]

const hallmarks = [
  { name: 'Genomic Instability',          score: 72 },
  { name: 'Telomere Attrition',           score: 68 },
  { name: 'Epigenetic Alterations',       score: 58 },
  { name: 'Loss of Proteostasis',         score: 75 },
  { name: 'Deregulated Nutrient Sensing', score: 62 },
  { name: 'Mitochondrial Dysfunction',    score: 80 },
  { name: 'Cellular Senescence',          score: 55 },
  { name: 'Stem Cell Exhaustion',         score: 70 },
  { name: 'Altered Cell Communication',   score: 65 },
  { name: 'Disabled Macroautophagy',      score: 72 },
  { name: 'Chronic Inflammation',         score: 60 },
  { name: 'Dysbiosis',                    score: 68 },
]

const interventions = [
  { name: 'Rapamycin Protocol',  confidence: 94, Icon: FlaskConical, tag: 'mTOR Inhibitor'      },
  { name: 'NAD+ Optimization',   confidence: 89, Icon: Zap,          tag: 'Metabolic Boost'     },
  { name: 'Zone 2 Training',     confidence: 87, Icon: Activity,     tag: 'Exercise RX'          },
  { name: 'Senolytics (D+Q)',    confidence: 82, Icon: Shield,        tag: 'Cellular Clearance'  },
  { name: 'Caloric Restriction', confidence: 78, Icon: Target,        tag: 'Dietary Protocol'    },
  { name: 'HBOT Sessions',       confidence: 71, Icon: Brain,         tag: 'Oxygen Therapy'      },
]

const LOG_ENTRIES = [
  { time: '0.0s', msg: 'Initializing epigenetic clock analysis...',   type: 'info'     },
  { time: '0.4s', msg: 'Loading Horvath methylation model v3.2',      type: 'info'     },
  { time: '0.8s', msg: 'Sequencing CpG sites (850k array)',           type: 'process'  },
  { time: '1.2s', msg: 'Identifying methylation patterns...',         type: 'process'  },
  { time: '1.6s', msg: 'Cross-referencing Hannum clock model',        type: 'info'     },
  { time: '2.1s', msg: 'Calculating GrimAge acceleration score',      type: 'process'  },
  { time: '2.5s', msg: 'Mortality risk reduction: −31.4%',            type: 'result'   },
  { time: '3.0s', msg: 'Telomere length analysis via Q-FISH',         type: 'info'     },
  { time: '3.4s', msg: 'mtDNA copy number: 1842 (optimal range)',     type: 'result'   },
  { time: '3.9s', msg: 'SASP biomarker panel: 62/68 nominal',         type: 'info'     },
  { time: '4.3s', msg: 'mTOR pathway activity: suppressed ✓',         type: 'result'   },
  { time: '4.8s', msg: 'Biological age delta: −8 years',              type: 'result'   },
  { time: '5.2s', msg: 'Generating intervention response matrix...',  type: 'process'  },
  { time: '5.7s', msg: 'Rapamycin dosing: 5 mg/week optimized',       type: 'result'   },
  { time: '6.1s', msg: 'NAD+ precursor: NMN 500 mg/day confirmed',    type: 'result'   },
  { time: '6.5s', msg: 'Analysis complete — Confidence: 97.3%',       type: 'complete' },
]

const LOG_COLOR = {
  info:     '#6b7280',
  process:  '#22D3EE',
  result:   '#22c55e',
  complete: '#8B5CF6',
}

// ── Biological Age Dial ──────────────────────────────────────────────
function AgeDial({ bioAge }) {
  const r = 88
  const cx = 120
  const cy = 120
  const C = 2 * Math.PI * r          // full circumference ≈ 553
  const arc = C * 0.75               // 270° arc length    ≈ 415
  const scale = { min: 20, max: 100 }

  const pct    = (bioAge  - scale.min) / (scale.max - scale.min)
  const cPct   = (CHRON_AGE - scale.min) / (scale.max - scale.min)
  const fill   = Math.max(4, pct  * arc)
  const cFill  = cPct * arc

  // rotate(135) starts the arc at the 7:30 clock position (bottom-left)
  const rot = `rotate(135 ${cx} ${cy})`

  return (
    <div className="relative w-60 h-60 mx-auto">
      <svg viewBox="0 0 240 240" width="240" height="240" className="absolute inset-0">
        <defs>
          <linearGradient id="cyanGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#8B5CF6" />
            <stop offset="100%" stopColor="#22D3EE" />
          </linearGradient>
          <filter id="cyanGlow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Outer decorative ring */}
        <circle cx={cx} cy={cy} r={r + 16} fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />

        {/* Background track */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke="#111827" strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${arc} ${C - arc}`}
          transform={rot}
        />

        {/* Chronological age (amber, behind) */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke="#f59e0b" strokeWidth="10" strokeLinecap="round" strokeOpacity="0.45"
          strokeDasharray={`${cFill} ${C - cFill}`}
          transform={rot}
          style={{ transition: 'stroke-dasharray 0.1s ease-out' }}
        />

        {/* Biological age (cyan gradient, animated) */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke="url(#cyanGrad)" strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${fill} ${C - fill}`}
          transform={rot}
          filter="url(#cyanGlow)"
          style={{ transition: 'stroke-dasharray 0.08s ease-out' }}
        />

        {/* Scale end labels */}
        <text x="26"  y="200" textAnchor="middle" fill="#374151" fontSize="9" fontFamily="system-ui">20</text>
        <text x="214" y="200" textAnchor="middle" fill="#374151" fontSize="9" fontFamily="system-ui">100</text>
      </svg>

      {/* Centered text overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center select-none">
        <span style={{ fontSize: 9, letterSpacing: '0.2em', color: '#4b5563', textTransform: 'uppercase' }}>
          Biological Age
        </span>
        <span
          style={{
            fontSize: 60,
            fontWeight: 900,
            lineHeight: 1,
            color: '#22D3EE',
            textShadow: '0 0 24px rgba(34,211,238,0.55)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {bioAge}
        </span>
        <span style={{ fontSize: 10, color: '#4b5563', marginTop: 2 }}>
          chronological: {CHRON_AGE}
        </span>
      </div>
    </div>
  )
}

// ── Chart Tooltip ────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card px-3 py-2" style={{ fontSize: 11 }}>
      <p style={{ color: '#6b7280', marginBottom: 4 }}>Age: {label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.dataKey === 'optimized' ? 'Optimized' : 'Standard'}: {p.value}
        </p>
      ))}
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────────────────
export default function App() {
  const [bioAge, setBioAge] = useState(CHRON_AGE)

  useEffect(() => {
    const delay = setTimeout(() => {
      let cur = CHRON_AGE
      const iv = setInterval(() => {
        cur -= 1
        setBioAge(cur)
        if (cur <= BIO_AGE_TARGET) clearInterval(iv)
      }, 75)
      return () => clearInterval(iv)
    }, 900)
    return () => clearTimeout(delay)
  }, [])

  return (
    <div style={{ background: '#0D0D0D', minHeight: '100vh', color: '#f0f0f0', padding: '20px 24px' }}>

      {/* ── Header ── */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            padding: 8, borderRadius: 12,
            background: 'rgba(139,92,246,0.15)',
            border: '1px solid rgba(139,92,246,0.3)',
          }}>
            <Dna size={20} color="#8B5CF6" />
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px', color: '#fff' }}>
              PredictiveBio
            </h1>
            <p style={{ fontSize: 9, color: '#4b5563', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              Longevity Intelligence Platform
            </p>
          </div>
          <span style={{
            marginLeft: 8, padding: '2px 8px', borderRadius: 999,
            fontSize: 10, fontFamily: 'monospace',
            background: 'rgba(34,211,238,0.1)',
            color: '#22D3EE',
            border: '1px solid rgba(34,211,238,0.2)',
          }}>v2.4.1</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#4b5563' }}>
            <Wifi size={11} color="#22c55e" />
            Illumina NovaSeq 6000 · Connected
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div className="ping-slow" style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e' }} />
            <span style={{ fontSize: 11, color: '#22c55e', fontWeight: 600 }}>Analysis Active</span>
          </div>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'linear-gradient(135deg, #22D3EE, #8B5CF6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: '#000',
          }}>JL</div>
        </div>
      </header>

      {/* ── Stat Bar ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 16 }}>
        {[
          { label: 'Biological Age',    value: `${BIO_AGE_TARGET}`, unit: 'yrs',  color: '#22D3EE', sub: '↓ 8 from chronological'  },
          { label: 'Age Delta',         value: '−8',                unit: 'yrs',  color: '#22c55e', sub: 'Top 12th percentile'      },
          { label: 'Healthspan Proj.',  value: '+12.4',             unit: 'yrs',  color: '#8B5CF6', sub: 'vs. standard trajectory'  },
          { label: 'Mortality Risk Δ',  value: '−31',               unit: '%',    color: '#f59e0b', sub: '10-year projection window' },
          { label: 'Confidence Score',  value: '97.3',              unit: '%',    color: '#22D3EE', sub: 'Epigenetic + blood panel'  },
        ].map(s => (
          <div key={s.label} className="glass-card" style={{ padding: '12px 16px' }}>
            <p style={{ fontSize: 9, color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{s.label}</p>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontSize: 26, fontWeight: 900, color: s.color, fontVariantNumeric: 'tabular-nums' }}>{s.value}</span>
              <span style={{ fontSize: 11, color: '#4b5563' }}>{s.unit}</span>
            </div>
            <p style={{ fontSize: 9, color: '#374151', marginTop: 2 }}>{s.sub}</p>
          </div>
        ))}
      </div>

      {/* ── Row 2: Dial + Trajectory + Log ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 260px', gap: 16, marginBottom: 16 }}>

        {/* The Pulse */}
        <div className="glass-card glow-cyan" style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: 12 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>The Pulse</span>
            <Heart size={13} color="#22D3EE" />
          </div>

          <AgeDial bioAge={bioAge} />

          <div style={{ width: '100%', marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { label: 'Chronological', val: CHRON_AGE, dot: '#f59e0b', color: '#f59e0b' },
              { label: 'Biological',    val: bioAge,    dot: '#22D3EE', color: '#22D3EE' },
            ].map(r => (
              <div key={r.label} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 12px', borderRadius: 10,
                background: 'rgba(34,211,238,0.06)',
                border: '1px solid rgba(34,211,238,0.12)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 7, height: 7, borderRadius: '50%', background: r.dot }} />
                  <span style={{ fontSize: 11, color: '#9ca3af' }}>{r.label}</span>
                </div>
                <span style={{ fontSize: 14, fontWeight: 800, color: r.color }}>{r.val}</span>
              </div>
            ))}

            <button style={{
              width: '100%', padding: '12px 0', borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #8B5CF6, #22D3EE)',
              color: '#000', fontSize: 13, fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              marginTop: 4,
            }}>
              <Upload size={14} />
              Upload Biomarker Data
            </button>
            <p style={{ fontSize: 9, color: '#374151', textAlign: 'center' }}>Blood · Epigenetic · Proteomics</p>
          </div>
        </div>

        {/* Aging Trajectory */}
        <div className="glass-card" style={{ padding: '20px 20px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
            <div>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Aging Trajectory
              </span>
              <p style={{ fontSize: 9, color: '#4b5563', marginTop: 2 }}>Predicted healthspan curve · 65-year projection</p>
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: '#4b5563' }}>
                <svg width="22" height="2"><line x1="0" y1="1" x2="22" y2="1" stroke="#374151" strokeWidth="2" strokeDasharray="4,2" /></svg>
                Standard Aging
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: '#22D3EE' }}>
                <svg width="22" height="2"><line x1="0" y1="1" x2="22" y2="1" stroke="#22D3EE" strokeWidth="2.5" /></svg>
                Optimized Path
              </div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trajectoryData} margin={{ top: 4, right: 8, left: -24, bottom: 16 }}>
              <defs>
                <filter id="lineGlow">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 5" />
              <XAxis
                dataKey="age"
                stroke="#1f2937"
                tick={{ fill: '#4b5563', fontSize: 9 }}
                label={{ value: 'Age (years)', position: 'insideBottom', offset: -8, fill: '#374151', fontSize: 9 }}
              />
              <YAxis
                stroke="#1f2937"
                tick={{ fill: '#4b5563', fontSize: 9 }}
                domain={[10, 100]}
                label={{ value: 'Health Score', angle: -90, position: 'insideLeft', offset: 16, fill: '#374151', fontSize: 9 }}
              />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine
                x={CHRON_AGE}
                stroke="rgba(245,158,11,0.35)"
                strokeDasharray="4 2"
                label={{ value: 'Now', position: 'top', fill: '#f59e0b', fontSize: 9 }}
              />
              <Line type="monotone" dataKey="standard" stroke="#2d3748" strokeWidth={2}
                strokeDasharray="6 3" dot={false}
                activeDot={{ r: 4, fill: '#4b5563' }}
              />
              <Line type="monotone" dataKey="optimized" stroke="#22D3EE" strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, fill: '#22D3EE', stroke: '#0D0D0D', strokeWidth: 2 }}
                style={{ filter: 'url(#lineGlow)' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Live Log */}
        <div className="glass-card" style={{ padding: '16px 14px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Live Analysis Log
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div className="ping-slow" style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
              <span style={{ fontSize: 9, color: '#22c55e' }}>Live</span>
            </div>
          </div>
          <div className="mask-log" style={{ flex: 1, overflow: 'hidden', minHeight: 0, height: 310 }}>
            <div className="scroll-log">
              {[...LOG_ENTRIES, ...LOG_ENTRIES].map((e, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 8, padding: '5px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <span style={{ fontSize: 9, fontFamily: 'monospace', color: '#22D3EE', opacity: 0.65, flexShrink: 0 }}>
                    [{e.time}]
                  </span>
                  <span style={{ fontSize: 9, lineHeight: 1.4, color: LOG_COLOR[e.type] }}>
                    {e.msg}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>

      {/* ── Bento Grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16 }}>

        {/* Cellular Health Radar */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Cellular Health
            </span>
            <Cpu size={13} color="#8B5CF6" />
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <RadarChart data={radarData} margin={{ top: 0, right: 16, bottom: 0, left: 16 }}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#4b5563', fontSize: 9 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar dataKey="A" stroke="#22D3EE" fill="#22D3EE" fillOpacity={0.1} strokeWidth={1.5}
                dot={{ fill: '#22D3EE', r: 3 }}
              />
            </RadarChart>
          </ResponsiveContainer>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', marginTop: 8 }}>
            {radarData.map(d => (
              <div key={d.subject} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#22D3EE', opacity: 0.7, flexShrink: 0 }} />
                <span style={{ fontSize: 9, color: '#4b5563', flex: 1 }}>{d.subject}</span>
                <span style={{ fontSize: 9, fontWeight: 700, color: d.A >= 70 ? '#22c55e' : '#f59e0b' }}>{d.A}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* 12 Hallmarks */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              12 Hallmarks of Aging
            </span>
            <Layers size={13} color="#8B5CF6" />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {hallmarks.map(h => {
              const color = h.score >= 70 ? '#22D3EE' : h.score >= 60 ? '#8B5CF6' : '#f59e0b'
              return (
                <div key={h.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontSize: 9, color: '#6b7280' }}>{h.name}</span>
                    <span style={{ fontSize: 9, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>{h.score}%</span>
                  </div>
                  <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                    <div style={{
                      height: '100%', borderRadius: 2,
                      width: `${h.score}%`,
                      background: h.score >= 70 ? 'linear-gradient(90deg, #8B5CF6, #22D3EE)' : color,
                      boxShadow: h.score >= 70 ? `0 0 6px ${color}55` : 'none',
                    }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Intervention Engine */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
            <div>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Intervention Engine
              </span>
              <p style={{ fontSize: 9, color: '#374151', marginTop: 2 }}>AI-ranked longevity protocols</p>
            </div>
            <Brain size={13} color="#8B5CF6" />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {interventions.map(({ name, confidence, Icon, tag }, i) => (
              <div key={name} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 12, cursor: 'pointer',
                background: i === 0 ? 'rgba(139,92,246,0.12)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${i === 0 ? 'rgba(139,92,246,0.28)' : 'rgba(255,255,255,0.06)'}`,
                transition: 'background 0.15s',
              }}>
                <div style={{ padding: 6, borderRadius: 8, background: 'rgba(139,92,246,0.18)', flexShrink: 0 }}>
                  <Icon size={13} color="#8B5CF6" />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#e5e7eb', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</p>
                  <p style={{ fontSize: 9, color: '#4b5563' }}>{tag}</p>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <p style={{ fontSize: 14, fontWeight: 900, color: confidence >= 85 ? '#22D3EE' : '#8B5CF6', fontVariantNumeric: 'tabular-nums' }}>
                    {confidence}%
                  </p>
                  <p style={{ fontSize: 9, color: '#374151' }}>conf.</p>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  )
}

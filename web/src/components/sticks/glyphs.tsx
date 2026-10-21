/**
 * Stick diagram pictograms. Each glyph is drawn in a 20 x 20 box centred on (0, 0),
 * ink strokes only (severity colour is reserved for the severity row). The "usual"
 * state of each row is drawn faint so unusual conditions stand out.
 */
import type { ReactNode } from 'react'

import type { JunctionGlyph, LightGlyph, ManoeuvreGlyph, SurfaceGlyph, WeatherGlyph } from '../../lib/sticks'

const INK = 'var(--ink)'
const FAINT = 'var(--rule-strong)'
const S = { fill: 'none', stroke: INK, strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' } as const
const faint = { ...S, stroke: FAINT, strokeWidth: 1.4 }

function Head({ x, y, angle }: { x: number; y: number; angle: number }) {
  return <path d="M-3.2,2.6 L0,-1.6 L3.2,2.6" {...S} transform={`translate(${x},${y}) rotate(${angle})`} />
}

const Q = ({ dy = 4 }: { dy?: number }) => (
  <text x={0} y={dy} textAnchor="middle" fontSize={11} fill="var(--ink-3)">
    ?
  </text>
)

export function LightIcon({ g }: { g: LightGlyph }): ReactNode {
  if (g === 'day') return <circle r={3.5} {...faint} />
  if (g === 'unknown') return <Q />
  return (
    <g>
      {/* dark = filled disc; lamp post beside it says whether street lights were lit */}
      <circle cx={g === 'dark-none' ? 0 : -3} r={5} fill={INK} />
      {g === 'dark-lit' && (
        <g transform="translate(6,0)">
          <line x1={0} y1={-6} x2={0} y2={6} {...S} />
          <circle cx={0} cy={-6} r={1.8} fill={INK} />
        </g>
      )}
      {g === 'dark-unlit' && (
        <g transform="translate(6,0)">
          <line x1={0} y1={-6} x2={0} y2={6} {...S} />
          <line x1={-3} y1={-3} x2={3} y2={3} {...S} />
        </g>
      )}
      {g === 'dark-unknown' && (
        <text x={7} y={4} fontSize={9} fill={INK}>
          ?
        </text>
      )}
    </g>
  )
}

const Rain = () => (
  <g>
    {[-5, 0, 5].map((x) => (
      <line key={x} x1={x + 1.5} y1={-5} x2={x - 1.5} y2={2} {...S} />
    ))}
  </g>
)
const Flake = ({ r = 5.5 }: { r?: number }) => (
  <g>
    {[0, 60, 120].map((a) => (
      <line key={a} x1={0} y1={-r} x2={0} y2={r} {...S} transform={`rotate(${a})`} />
    ))}
  </g>
)
const Wind = () => <path d="M-7,6 C-3,4 1,8 7,5" {...S} />

export function WeatherIcon({ g }: { g: WeatherGlyph }): ReactNode {
  switch (g) {
    case 'fine':
      return <line x1={-3} y1={0} x2={3} y2={0} {...faint} />
    case 'rain':
      return <Rain />
    case 'snow':
      return <Flake />
    case 'fine-wind':
      return <Wind />
    case 'rain-wind':
      return (
        <g>
          <g transform="translate(0,-2)">
            <Rain />
          </g>
          <Wind />
        </g>
      )
    case 'snow-wind':
      return (
        <g>
          <g transform="translate(0,-3) scale(0.8)">
            <Flake />
          </g>
          <Wind />
        </g>
      )
    case 'fog':
      return (
        <g>
          {[-4, 0, 4].map((y) => (
            <line key={y} x1={-6} y1={y} x2={6} y2={y} {...S} />
          ))}
        </g>
      )
    default:
      return <Q />
  }
}

export function SurfaceIcon({ g }: { g: SurfaceGlyph }): ReactNode {
  switch (g) {
    case 'dry':
      return <line x1={-3} y1={0} x2={3} y2={0} {...faint} />
    case 'wet':
      return <path d="M0,-7 C3,-2 5,1 5,3 A5,5 0 0 1 -5,3 C-5,1 -3,-2 0,-7 Z" fill={INK} />
    case 'snow':
      return <Flake />
    case 'ice':
      return (
        <g>
          <Flake r={6} />
          <circle r={2.2} fill={INK} />
        </g>
      )
    case 'flood':
      return (
        <g>
          <path d="M-7,-2 C-4,-5 -1,1 2,-2 S6,-4 7,-2" {...S} />
          <path d="M-7,3 C-4,0 -1,6 2,3 S6,1 7,3" {...S} />
        </g>
      )
    case 'oil':
    case 'mud':
      return (
        <text x={0} y={3.5} textAnchor="middle" fontSize={8.5} fontWeight={600} fill={INK}>
          {g === 'oil' ? 'Oil' : 'Mud'}
        </text>
      )
    default:
      return <Q />
  }
}

export function JunctionIcon({ g }: { g: JunctionGlyph }): ReactNode {
  switch (g) {
    case 'none':
      return <line x1={0} y1={-7} x2={0} y2={7} {...faint} />
    case 't':
      return <path d="M-7,-5 H7 M0,-5 V7" {...S} />
    case 'cross':
      return <path d="M-7,0 H7 M0,-7 V7" {...S} />
    case 'multi':
      return (
        <g>
          {[0, 60, 120].map((a) => (
            <line key={a} x1={0} y1={-7} x2={0} y2={7} {...S} transform={`rotate(${a})`} />
          ))}
        </g>
      )
    case 'drive':
      return (
        <g>
          <line x1={0} y1={-7} x2={0} y2={7} {...S} />
          <path d="M0,0 H4" {...S} />
          <rect x={4} y={-2.5} width={4} height={5} {...S} />
        </g>
      )
    case 'roundabout':
      return (
        <g>
          <circle r={3.8} {...S} />
          <path d="M0,-4 V-7.5 M0,4 V7.5 M-4,0 H-7.5 M4,0 H7.5" {...S} />
        </g>
      )
    case 'slip':
      return <path d="M-2,-7 V7 M-2,4 L5,-5" {...S} />
    case 'other':
      return (
        <g>
          <path d="M-7,0 H-2 M0,-7 V7" {...S} />
          <text x={5} y={3.5} textAnchor="middle" fontSize={9} fill={INK}>
            ?
          </text>
        </g>
      )
    default:
      return <Q />
  }
}

/** Manoeuvre arrows centred on (0, 0), drawn ~20 x 22; direction of travel is up. */
export function ManoeuvreIcon({ g }: { g: ManoeuvreGlyph }): ReactNode {
  return <g transform="scale(0.88)">{manoeuvre(g)}</g>
}

function manoeuvre(g: ManoeuvreGlyph): ReactNode {
  switch (g) {
    case 'ahead':
      return (
        <g>
          <line x1={0} y1={10} x2={0} y2={-9} {...S} />
          <Head x={0} y={-9} angle={0} />
        </g>
      )
    case 'bend-left':
    case 'bend-right': {
      const d = g === 'bend-left' ? -1 : 1
      return (
        <g>
          <path d={`M0,10 C0,0 ${7 * d},-2 ${7 * d},-9`} {...S} />
          <Head x={7 * d} y={-9} angle={0} />
        </g>
      )
    }
    case 'turn-left':
    case 'turn-right':
    case 'wait-left':
    case 'wait-right': {
      const d = g.endsWith('left') ? -1 : 1
      const waiting = g.startsWith('wait')
      return (
        <g>
          <path d={`M0,10 V-2 Q0,-6 ${4 * d},-6 H${9 * d}`} {...S} strokeDasharray={waiting ? '2.5 2' : undefined} />
          <Head x={9 * d} y={-6} angle={90 * d} />
          {waiting && <line x1={-5} y1={10} x2={5} y2={10} {...S} strokeWidth={2.4} />}
        </g>
      )
    }
    case 'u-turn':
      return (
        <g>
          <path d="M-4,10 V-3 A4,4 0 0 1 4,-3 V7" {...S} />
          <Head x={4} y={7} angle={180} />
        </g>
      )
    case 'lane-left':
    case 'lane-right': {
      const d = g === 'lane-left' ? -1 : 1
      return (
        <g>
          <path d={`M${-3 * d},10 V4 C${-3 * d},0 ${4 * d},0 ${4 * d},-4 V-9`} {...S} />
          <Head x={4 * d} y={-9} angle={0} />
        </g>
      )
    }
    case 'overtake-moving':
    case 'overtake-stationary':
    case 'overtake-nearside': {
      const d = g === 'overtake-nearside' ? -1 : 1
      return (
        <g>
          <rect x={-3} y={-5} width={6} height={9} rx={1} {...S} fill={g === 'overtake-stationary' ? INK : 'none'} />
          <path d={`M0,11 C0,7 ${8 * d},7 ${8 * d},0 C${8 * d},-6 0,-6 0,-10`} {...S} />
          <Head x={0} y={-10} angle={0} />
        </g>
      )
    }
    case 'reverse':
      return (
        <g>
          <line x1={0} y1={-9} x2={0} y2={9} {...S} />
          <Head x={0} y={9} angle={180} />
          <text x={6} y={-3} fontSize={8} fontWeight={600} fill={INK}>
            R
          </text>
        </g>
      )
    case 'parked':
    case 'parking':
      return (
        <g>
          <rect x={-6} y={-7} width={12} height={14} rx={2} {...S} />
          <text x={0} y={4} textAnchor="middle" fontSize={10} fontWeight={700} fill={INK}>
            P
          </text>
          {g === 'parking' && <path d="M7,4 L10,1" {...S} />}
        </g>
      )
    case 'waiting':
      return (
        <g>
          <line x1={0} y1={10} x2={0} y2={-1} {...S} strokeDasharray="2.5 2" />
          <line x1={-5} y1={-3} x2={5} y2={-3} {...S} strokeWidth={2.4} />
        </g>
      )
    case 'slowing':
      return (
        <g>
          <line x1={0} y1={10} x2={0} y2={-9} {...S} />
          <Head x={0} y={-9} angle={0} />
          <path d="M-4,3 H4 M-4,6.5 H4" {...S} />
        </g>
      )
    case 'moving-off':
      return (
        <g>
          <line x1={-5} y1={10} x2={5} y2={10} {...S} strokeWidth={2.4} />
          <line x1={0} y1={8} x2={0} y2={-9} {...S} />
          <Head x={0} y={-9} angle={0} />
        </g>
      )
    default:
      return <Q dy={5} />
  }
}

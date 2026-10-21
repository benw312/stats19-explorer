import type { ReactNode } from 'react'

import { SEVERITIES } from '../../lib/severity'
import { JunctionIcon, LightIcon, ManoeuvreIcon, SurfaceIcon, WeatherIcon } from './glyphs'
import styles from './sticks.module.css'

function Item({ icon, label, box = 22 }: { icon: ReactNode; label: string; box?: number }) {
  return (
    <li>
      <svg width={box} height={box} viewBox={`${-box / 2} ${-box / 2} ${box} ${box}`} aria-hidden>
        {icon}
      </svg>
      {label}
    </li>
  )
}

/** Legend for the stick diagram pictograms. */
export function StickKey() {
  return (
    <div className={styles.key}>
      <section>
        <h4>Severity</h4>
        <ul>
          {SEVERITIES.map((s) => (
            <Item
              key={s.code}
              icon={
                <g>
                  <rect x={-8} y={-6} width={16} height={12} rx={2} fill={s.cssVar} />
                  <text textAnchor="middle" dy={3.5} fontSize={9} fontWeight={700} fill="#fff">
                    {{ 1: 'F', 2: 'S', 3: 's' }[s.code]}
                  </text>
                </g>
              }
              label={s.label}
            />
          ))}
        </ul>
      </section>
      <section>
        <h4>Light · weather · surface</h4>
        <ul>
          <Item icon={<LightIcon g="dark-lit" />} label="Dark, lights lit" />
          <Item icon={<LightIcon g="dark-unlit" />} label="Dark, lights unlit" />
          <Item icon={<LightIcon g="dark-none" />} label="Dark, no lighting" />
          <Item icon={<WeatherIcon g="rain" />} label="Rain" />
          <Item icon={<WeatherIcon g="snow" />} label="Snow" />
          <Item icon={<WeatherIcon g="fog" />} label="Fog or mist" />
          <Item icon={<WeatherIcon g="fine-wind" />} label="High winds" />
          <Item icon={<SurfaceIcon g="wet" />} label="Wet or damp" />
          <Item icon={<SurfaceIcon g="ice" />} label="Frost or ice" />
          <Item icon={<SurfaceIcon g="flood" />} label="Flood" />
          <Item icon={<LightIcon g="day" />} label="Daylight · fine · dry (faint)" />
        </ul>
      </section>
      <section>
        <h4>Junction</h4>
        <ul>
          <Item icon={<JunctionIcon g="t" />} label="T / staggered" />
          <Item icon={<JunctionIcon g="cross" />} label="Crossroads" />
          <Item icon={<JunctionIcon g="multi" />} label="More than 4 arms" />
          <Item icon={<JunctionIcon g="roundabout" />} label="Roundabout" />
          <Item icon={<JunctionIcon g="slip" />} label="Slip road" />
          <Item icon={<JunctionIcon g="drive" />} label="Private drive" />
          <Item icon={<JunctionIcon g="none" />} label="Not at a junction (faint)" />
        </ul>
      </section>
      <section>
        <h4>Vehicle manoeuvre (travel is up the page)</h4>
        <ul>
          <Item box={26} icon={<ManoeuvreIcon g="ahead" />} label="Going ahead" />
          <Item box={26} icon={<ManoeuvreIcon g="bend-left" />} label="Left-hand bend (pre-2024)" />
          <Item box={26} icon={<ManoeuvreIcon g="turn-right" />} label="Turning right" />
          <Item box={26} icon={<ManoeuvreIcon g="wait-right" />} label="Waiting to turn right" />
          <Item box={26} icon={<ManoeuvreIcon g="u-turn" />} label="U-turn" />
          <Item box={26} icon={<ManoeuvreIcon g="lane-right" />} label="Changing lane" />
          <Item box={26} icon={<ManoeuvreIcon g="overtake-moving" />} label="Overtaking (offside)" />
          <Item box={26} icon={<ManoeuvreIcon g="slowing" />} label="Slowing or stopping" />
          <Item box={26} icon={<ManoeuvreIcon g="waiting" />} label="Waiting to go ahead" />
          <Item box={26} icon={<ManoeuvreIcon g="moving-off" />} label="Moving off" />
          <Item box={26} icon={<ManoeuvreIcon g="reverse" />} label="Reversing" />
          <Item box={26} icon={<ManoeuvreIcon g="parked" />} label="Parked" />
        </ul>
        <p className={styles.keyNote}>
          The heavy edge of each vehicle box marks the first point of impact (top = front, bottom = back, right =
          offside, left = nearside). Flags: <b>S</b> skidded, <b>O</b> overturned, <b>J</b> jack-knifed, <b>Off</b> left
          the carriageway. Text: vehicle type and driver age (Car, MC motorcycle, PC pedal cycle, Van, HGV, Bus, Taxi,
          PPT e-scooter). Casualties: <b>D</b> driver/rider, <b>P</b> passenger, <b>Ped</b> pedestrian, with age; dot =
          severity.
        </p>
      </section>
    </div>
  )
}

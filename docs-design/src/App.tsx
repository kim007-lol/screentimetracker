import { useEffect, useRef, useState } from 'react'
import { useRive, useStateMachineInput, Layout, Fit, Alignment } from '@rive-app/react-canvas'

type Theme = 'brutal' | 'arcade' | 'clay' | 'midnight'
type Mood = 'Segar' | 'Lelah' | 'Kritis'
type Stage = 1 | 2 | 3
type RenderMode = '3d' | 'rive'
type IconName = 'chart' | 'flag' | 'home' | 'bolt' | 'user' | 'flame' | 'heart' | 'sparkle' | 'moon'

const stageConfig: Record<Stage, { name: string; level: number; glb: string; poster: string; description: string }> = {
  1: {
    name: 'Bayi',
    level: 2,
    glb: '/assets/3d/momo_bayi.glb',
    poster: '/assets/3d/momo_bayi.png',
    description: 'Napas canggung, goyang 2.4s',
  },
  2: {
    name: 'Remaja',
    level: 8,
    glb: '/assets/3d/momo_remaja.glb',
    poster: '/assets/3d/momo_remaja.png',
    description: 'Lincah & ekspresif, goyang 2.0s',
  },
  3: {
    name: 'Dewasa',
    level: 12,
    glb: '/assets/3d/momo_dewasa.glb',
    poster: '/assets/3d/momo_dewasa.png',
    description: 'Tenang & stabil, goyang 3.0s',
  },
}

const themes: { id: Theme; name: string }[] = [
  { id: 'brutal', name: 'Brutal Pop' },
  { id: 'arcade', name: 'Pixel Arcade' },
  { id: 'clay', name: 'Soft Clay' },
  { id: 'midnight', name: 'Midnight' },
]

const states: { id: string; mood: Mood; hp: number; line: string }[] = [
  { id: 'S4', mood: 'Segar', hp: 72, line: 'Hari ini masih aman, lanjut ya!' },
  { id: 'S5', mood: 'Lelah', hp: 38, line: 'Udah lumayan banyak scroll nih, istirahat dikit yuk?' },
  { id: 'S6', mood: 'Kritis', hp: 9, line: 'Aku butuh istirahat...' },
]

function Icon({ name, size = 21 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    chart: <path d="M4 19V9m6 10V5m6 14v-7m4 7H2" />,
    flag: <path d="M5 21V4m0 1h11l-2.3 3L16 11H5" />,
    home: <><path d="m3 11 9-8 9 8" /><path d="M5 10v11h14V10M9 21v-7h6v7" /></>,
    bolt: <path d="m13 2-8 11h6l-1 9 9-12h-6V2Z" />,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c.7-4.2 3.4-6 8-6s7.3 1.8 8 6" /></>,
    flame: <path d="M12 22c4 0 7-2.8 7-7.1 0-3.2-1.8-6.4-5.3-9.5.1 2.6-1 4.2-2.5 5.1.2-3.7-1.5-6.6-3.1-8.5.1 4.1-3.1 6.7-3.1 11.9C5 18.7 8.1 22 12 22Z" />,
    heart: <path d="M20.8 5.8c-1.7-2-4.8-2.1-6.7-.3L12 7.4 9.9 5.5C8 3.7 4.9 3.8 3.2 5.8c-1.6 1.9-1.4 4.8.4 6.5L12 20l8.4-7.7c1.8-1.7 2-4.6.4-6.5Z" />,
    sparkle: <path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8L12 3Z" />,
    moon: <path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.4 2.26 5.403 5.403 0 0 1-3.14-9.8A9.04 9.04 0 0 0 12 3Z" />,
  }
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

const moodImages: Record<Mood, string> = {
  Segar: '/assets/pet/momo_fresh.png',
  Lelah: '/assets/pet/momo_tired.png',
  Kritis: '/assets/pet/momo_critical.png',
}

function Pet3D({
  stage,
  hp,
  isResting,
  overrideClip,
  theme,
  onTap,
}: {
  stage: Stage
  hp: number
  isResting: boolean
  overrideClip: string | null
  theme: Theme
  onTap: () => void
}) {
  const viewerRef = useRef<any>(null)
  const currentStage = stageConfig[stage]

  const baseClip = isResting
    ? 'sleep'
    : hp < 30
    ? 'idle_critical'
    : hp <= 60
    ? 'idle_tired'
    : 'idle_fresh'

  const activeClip = overrideClip || baseClip

  useEffect(() => {
    const el = viewerRef.current
    if (!el) return

    el.animationName = activeClip
    if (typeof el.play === 'function') {
      const isOneShot = activeClip === 'tap_reaction' || activeClip === 'celebrate'
      el.play({ repetitions: isOneShot ? 1 : Infinity })
    }
  }, [activeClip, stage])

  const handleModelLoad = () => {
    const el = viewerRef.current
    if (el && typeof el.play === 'function') {
      el.animationName = activeClip
      el.play()
    }
  }

  return (
    <div
      className={`pet pet-3d-wrapper theme-${theme}-pet`}
      onClick={onTap}
      title="Sentuh Momo atau putar dengan drag 3D"
    >
      <model-viewer
        ref={viewerRef}
        src={currentStage.glb}
        poster={currentStage.poster}
        animation-name={activeClip}
        autoplay
        camera-controls
        touch-action="pan-y"
        shadow-intensity="0.8"
        shadow-softness="0.5"
        exposure="1.05"
        loading="eager"
        reveal="auto"
        onLoad={handleModelLoad}
        className="pet-3d-canvas"
      />
      <div className="pet-3d-badge">
        <span>3D: {activeClip} (30 FPS)</span>
      </div>
    </div>
  )
}

function PetRive({
  theme,
  mood,
  hp,
  stage,
  isResting,
  onTap,
}: {
  theme: Theme
  mood: Mood
  hp: number
  stage: Stage
  isResting: boolean
  onTap: () => void
}) {
  const [loadError, setLoadError] = useState(false)
  const variantRef = useRef(0)

  const { rive, RiveComponent } = useRive({
    src: '/assets/pet/momo.riv',
    artboard: 'Momo',
    stateMachines: 'MomoStateMachine',
    autoplay: true,
    layout: new Layout({
      fit: Fit.Contain,
      alignment: Alignment.Center,
    }),
    onLoadError: () => setLoadError(true),
  })

  const hpInput = useStateMachineInput(rive, 'MomoStateMachine', 'hp', hp)
  const stageInput = useStateMachineInput(rive, 'MomoStateMachine', 'stage', stage)
  const isRestingInput = useStateMachineInput(rive, 'MomoStateMachine', 'isResting', isResting)
  const petTrigger = useStateMachineInput(rive, 'MomoStateMachine', 'pet')
  const petVariantInput = useStateMachineInput(rive, 'MomoStateMachine', 'petVariant', 0)

  useEffect(() => {
    if (hpInput) hpInput.value = hp
  }, [hpInput, hp])

  useEffect(() => {
    if (stageInput) stageInput.value = stage
  }, [stageInput, stage])

  useEffect(() => {
    if (isRestingInput) isRestingInput.value = isResting
  }, [isRestingInput, isResting])

  const handlePetAction = () => {
    if (petTrigger && petVariantInput) {
      const nextVariant = (variantRef.current + 1) % 3
      variantRef.current = nextVariant
      petVariantInput.value = nextVariant
      petTrigger.fire()
    }
    onTap()
  }

  if (loadError) {
    return (
      <img
        src={moodImages[mood]}
        alt={`Momo sedang ${mood}`}
        className={`pet pet-image theme-${theme}-pet`}
        loading="eager"
      />
    )
  }

  return (
    <div
      className={`pet pet-rive-wrapper theme-${theme}-pet`}
      onClick={handlePetAction}
      title="Sentuh Momo"
    >
      <RiveComponent className="pet-rive-canvas" />
    </div>
  )
}

function Bar({ kind, value }: { kind: 'hp' | 'xp'; value: number }) {
  return (
    <div className={`bar-block ${kind}`}>
      <div className="bar-label">
        <span>{kind === 'hp' ? <><Icon name="heart" size={14} /> HP</> : 'XP · menuju Lv. 9'}</span>
        <strong>{kind === 'hp' ? `${value}/100` : '240/400 XP'}</strong>
      </div>
      <div className="bar-track"><span style={{ width: `${value}%` }} /></div>
    </div>
  )
}

const nav: { label: string; icon: IconName }[] = [
  { label: 'Rekap', icon: 'chart' }, { label: 'Misi', icon: 'flag' },
  { label: 'Beranda', icon: 'home' }, { label: 'Duel', icon: 'bolt' }, { label: 'Profil', icon: 'user' },
]

function HomeScreen({
  theme,
  state,
  stage,
  renderMode,
}: {
  theme: Theme
  state: typeof states[number]
  stage: Stage
  renderMode: RenderMode
}) {
  const [bouncing, setBouncing] = useState(false)
  const [isResting, setIsResting] = useState(false)
  const [overrideClip, setOverrideClip] = useState<string | null>(null)
  const [customLine, setCustomLine] = useState<string | null>(null)

  const activeStage = stageConfig[stage]

  const triggerTapReaction = () => {
    setBouncing(true)
    setOverrideClip('tap_reaction')
    setCustomLine('Hehe, geli! Sentuh lagi dong!')
    window.setTimeout(() => {
      setBouncing(false)
      setOverrideClip(null)
      setCustomLine(null)
    }, 850)
  }

  const triggerCelebrate = () => {
    setBouncing(true)
    setOverrideClip('celebrate')
    setCustomLine('Horeee! Misi selesai, kamu hebat!')
    window.setTimeout(() => {
      setBouncing(false)
      setOverrideClip(null)
      setCustomLine(null)
    }, 1850)
  }

  const toggleRest = () => {
    setIsResting(!isResting)
    if (!isResting) {
      setCustomLine('Zzz... istirahat sebentar ya...')
    } else {
      setCustomLine(null)
    }
  }

  return (
    <article className={`phone theme-${theme} mood-${state.mood.toLowerCase()}`}>
      <header className="topbar">
        <div><p className="date">Selasa, 24 Juni</p><h2>Hai, Raka!</h2></div>
        <div className="streak"><Icon name="flame" size={18} /><strong>7</strong><span>hari</span></div>
      </header>

      <div className="badge-row">
        <span className="stage">{activeStage.name} (Lv. {activeStage.level})</span>
        <span className="mood-mark"><i />{isResting ? 'Tidur (Rest)' : state.mood}</span>
      </div>

      <section className="pet-stage">
        <div className="pet-halo" />
        <button
          className={`pet-button ${bouncing ? 'bouncing' : ''}`}
          onClick={triggerTapReaction}
          aria-label="Sentuh Momo"
        >
          {renderMode === '3d' ? (
            <Pet3D
              stage={stage}
              hp={state.hp}
              isResting={isResting}
              overrideClip={overrideClip}
              theme={theme}
              onTap={triggerTapReaction}
            />
          ) : (
            <PetRive
              theme={theme}
              mood={state.mood}
              hp={state.hp}
              stage={stage}
              isResting={isResting}
              onTap={triggerTapReaction}
            />
          )}
        </button>
        <div className="pet-title">
          <strong>Momo</strong>
          <span>Lv. {activeStage.level}</span>
        </div>
        <p className="speech">“{customLine || (isResting ? 'Zzz... istirahat sebentar ya...' : state.line)}”</p>

        <div className="pet-action-bar">
          <button
            type="button"
            className="pet-action-btn"
            onClick={triggerTapReaction}
            title="Uji animasi respon sentuhan"
          >
            👋 Sentuh (Tap)
          </button>
          <button
            type="button"
            className="pet-action-btn"
            onClick={triggerCelebrate}
            title="Uji animasi selebrasi misi/level up"
          >
            ✨ Rayakan
          </button>
          <button
            type="button"
            className={`pet-action-btn ${isResting ? 'active' : ''}`}
            onClick={toggleRest}
            title="Uji mode tidur pemulihan HP"
          >
            🌙 {isResting ? 'Bangun' : 'Tidur'}
          </button>
        </div>
      </section>

      <section className="vitals">
        <Bar kind="hp" value={state.hp} />
        <Bar kind="xp" value={60} />
        {state.mood === 'Kritis' && (
          <button className="rest-button" onClick={toggleRest}>
            {isResting ? 'Bangunkan Momo' : 'Istirahatkan HP (Tidur)'}
          </button>
        )}
        <div className="stats">
          <div><span>Total waktu</span><strong>3j 24m</strong><small>↓ 18m dari kemarin</small></div>
          <div><span>App teratas</span><strong>1j 12m</strong><small>TikTok</small></div>
          <div><span>Hit scroll</span><strong>387</strong><small>hari ini</small></div>
        </div>
      </section>

      <nav className="bottom-nav" aria-label="Navigasi utama">
        {nav.map((item) => (
          <button key={item.label} className={`nav-item ${item.label === 'Beranda' ? 'active' : ''}`}>
            <span><Icon name={item.icon} /></span>
            <small>{item.label}</small>
          </button>
        ))}
      </nav>
    </article>
  )
}

export default function App() {
  const [filter, setFilter] = useState<'all' | Mood>('all')
  const [stage, setStage] = useState<Stage>(2) // Default: Remaja
  const [renderMode, setRenderMode] = useState<RenderMode>('3d') // Default: 3D Realtime
  const visibleStates = filter === 'all' ? states : states.filter((state) => state.mood === filter)

  return (
    <main className="showcase">
      <header className="showcase-header">
        <div>
          <span className="kicker">Screen Time Companion · 3D Interactive Pipeline</span>
          <h1>Evolusi Momo & Karakter Visual</h1>
          <p>
            Momo hadir dalam 3 tahap evolusi (Bayi, Remaja, Dewasa) dengan 6 klip animasi 3D realtime
            (idle_fresh, idle_tired, idle_critical, sleep, tap_reaction, celebrate).
          </p>
        </div>

        <div className="global-controls">
          <div className="control-group">
            <span className="control-label">Tahap Evolusi:</span>
            <div className="button-pills">
              {([1, 2, 3] as Stage[]).map((s) => (
                <button
                  key={s}
                  className={`pill-btn ${stage === s ? 'selected' : ''}`}
                  onClick={() => setStage(s)}
                >
                  {s === 1 ? '👶 Bayi' : s === 2 ? '🧒 Remaja' : '🧓 Dewasa'} (Lv. {stageConfig[s].level})
                </button>
              ))}
            </div>
          </div>

          <div className="control-group">
            <span className="control-label">Engine Rendering:</span>
            <div className="button-pills">
              <button
                className={`pill-btn ${renderMode === '3d' ? 'selected' : ''}`}
                onClick={() => setRenderMode('3d')}
              >
                🌟 3D Realtime (.glb)
              </button>
              <button
                className={`pill-btn ${renderMode === 'rive' ? 'selected' : ''}`}
                onClick={() => setRenderMode('rive')}
              >
                🎨 2D Rive / Fallback
              </button>
            </div>
          </div>

          <div className="control-group">
            <span className="control-label">Filter HP:</span>
            <div className="button-pills">
              <button className={`pill-btn ${filter === 'all' ? 'selected' : ''}`} onClick={() => setFilter('all')}>
                Semua Kondisi
              </button>
              {states.map((state) => (
                <button
                  key={state.mood}
                  className={`pill-btn ${filter === state.mood ? 'selected' : ''}`}
                  onClick={() => setFilter(state.mood)}
                >
                  {state.mood} ({state.hp} HP)
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      {visibleStates.map((state) => (
        <section className="state-section" key={state.id}>
          <div className="state-heading">
            <span>{state.id}</span>
            <h2>Kondisi HP {state.mood}</h2>
            <p>
              HP {state.hp}/100 · Animasi: {state.hp > 60 ? 'idle_fresh' : state.hp >= 30 ? 'idle_tired' : 'idle_critical'}
            </p>
          </div>
          <div className="theme-grid">
            {themes.map((theme) => (
              <div className="preview" key={theme.id}>
                <div className="preview-label">
                  <strong>{theme.name}</strong>
                  <span>{stageConfig[stage].name} · {state.id} / {state.mood}</span>
                </div>
                <HomeScreen
                  theme={theme.id}
                  state={state}
                  stage={stage}
                  renderMode={renderMode}
                />
              </div>
            ))}
          </div>
        </section>
      ))}
    </main>
  )
}

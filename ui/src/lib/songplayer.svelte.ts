// Song preview: a game song or an imported MIDI played in the browser with the game's instruments
// (server: decomp/midi.py reads the MIDI, decomp/instruments.py the voicegroup and its samples).
// It follows the game's sound engine where it is simple (sampled notes resampled from C4, fixed-rate drums, fixed
// voice pan, volume = velocity x CC7 x the song's master volume, pitch bend and its range, the "[" "]" loop) and
// approximates the rest (envelopes at 60 steps a second, GB square, wave and noise channels; no reverb, no vibrato).
import type { SongRef } from './api'

type Voice = {
  kind: 'sample' | 'fixed' | 'square' | 'wave' | 'noise' | 'drums' | 'none' | 'split'
  key?: number; pan?: number; sample?: string; env?: number[]; duty?: number; wave?: string; period?: number
  voices?: Voice[]
}
type Bank = { voices: Voice[]; samples: Record<string, { rate: number; loop: number | null; frames: number }>; waves: Record<string, number[]> }
type MidiEvent = [number, 'n', number, number, number] | [number, 'p', number] | [number, 'c', number, number] | [number, 'b', number]
type Song = {
  midi: { division: number; tempos: [number, number][]; loop: [number, number] | null; end: number; channels: Record<string, MidiEvent[]> }
  voicegroup: number | string; volume: number
}

export const songPlayer = $state<{ playing: SongRef | null; loading: boolean; error: string }>({ playing: null, loading: false, error: '' })

const FRAME = 1 / 60
const CGB_GAIN = 0.3
const banks = new Map<number | string, Promise<Bank>>()
const buffers = new Map<string, Promise<AudioBuffer>>()
let ctx: AudioContext | null = null
let session: Session | null = null

function bank(n: number | string): Promise<Bank> {
  if (!banks.has(n)) banks.set(n, fetch(`/api/music/voicegroups/${n}`).then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json() }))
  return banks.get(n)!
}

function sampleBuffer(audio: AudioContext, name: string): Promise<AudioBuffer> {
  if (!buffers.has(name)) {
    buffers.set(name, fetch(`/api/music/samples/${encodeURIComponent(name)}`)
      .then((r) => r.arrayBuffer()).then((data) => audio.decodeAudioData(data)))
  }
  return buffers.get(name)!
}

/** Exponential envelope step of the game (value x step/256 each frame) as a Web Audio time constant. */
function tau(step: number): number {
  return step <= 0 ? 0.002 : step >= 255 ? 30 : -FRAME / Math.log(step / 256)
}

class Session {
  master: GainNode
  sources = new Set<AudioScheduledSourceNode>()
  channels = new Map<number, { program: number; volume: number; bendRange: number; bend: number; gain: GainNode; fixed: GainNode; panner: StereoPannerNode; notes: Set<AudioScheduledSourceNode> }>()
  events: [number, number, MidiEvent][] = []
  index = 0
  offset = 0   // seconds added at each loop
  start = 0
  timer = 0
  noise: AudioBuffer[] = []
  squares = new Map<number, PeriodicWave>()
  gbWaves = new Map<string, PeriodicWave>()

  constructor(public audio: AudioContext, public song: Song, public bank: Bank, public samples: Map<string, AudioBuffer>, public onend: () => void) {
    this.master = audio.createGain()
    this.master.gain.value = 0.5
    const limiter = audio.createDynamicsCompressor()
    this.master.connect(limiter).connect(audio.destination)
    for (const [channel, list] of Object.entries(song.midi.channels)) {
      for (const e of list) this.events.push([this.seconds(e[0]), Number(channel), e])
    }
    this.events.sort((a, b) => a[0] - b[0] || a[2][0] - b[2][0])
    this.start = audio.currentTime + 0.1
    this.timer = window.setInterval(() => this.schedule(), 50)
    this.schedule()
  }

  /** Seconds from the song's start to a tick, through the tempo changes. */
  seconds(tick: number): number {
    const { division, tempos } = this.song.midi
    let time = 0, last = 0, tempo = 500000
    for (const [at, value] of tempos) {
      if (at >= tick) break
      time += ((at - last) * tempo) / division / 1e6
      last = at
      tempo = value
    }
    return time + ((tick - last) * tempo) / division / 1e6
  }

  channel(n: number) {
    let c = this.channels.get(n)
    if (!c) {
      const gain = this.audio.createGain(), fixed = this.audio.createGain(), panner = this.audio.createStereoPanner()
      gain.connect(panner).connect(this.master)
      fixed.connect(this.master)
      const volume = (100 * this.song.volume) / 127 / 127
      gain.gain.value = volume
      fixed.gain.value = volume
      c = { program: 0, volume, bendRange: 2, bend: 0, gain, fixed, panner, notes: new Set() }
      this.channels.set(n, c)
    }
    return c
  }

  schedule() {
    const horizon = this.audio.currentTime + 0.3
    const loop = this.song.midi.loop
    const loopStart = loop ? this.seconds(loop[0]) : 0, loopEnd = loop ? this.seconds(loop[1]) : 0
    for (;;) {
      if (loop && (this.index >= this.events.length || this.events[this.index][0] >= loopEnd)) {
        if (this.start + this.offset + loopEnd > horizon) return
        this.offset += loopEnd - loopStart
        this.index = this.events.findIndex((e) => e[0] >= loopStart)
        if (this.index < 0) return this.finish()
        continue
      }
      if (this.index >= this.events.length) {
        const end = this.start + this.offset + this.seconds(this.song.midi.end) + 2
        if (this.audio.currentTime > end) this.finish()
        return
      }
      const [time, channel, event] = this.events[this.index]
      const at = this.start + this.offset + time
      if (at > horizon) return
      this.index++
      this.handle(Math.max(at, this.audio.currentTime), channel, event)
    }
  }

  handle(at: number, n: number, event: MidiEvent) {
    const c = this.channel(n)
    if (event[1] === 'p') c.program = event[2]
    else if (event[1] === 'c') {
      if (event[2] === 7) {
        c.volume = (event[3] * this.song.volume) / 127 / 127
        c.gain.gain.setValueAtTime(c.volume, at)
        c.fixed.gain.setValueAtTime(c.volume, at)
      } else if (event[2] === 10) c.panner.pan.setValueAtTime(Math.max(-1, (event[3] - 64) / 63), at)
      else if (event[2] === 20) c.bendRange = event[3]
    } else if (event[1] === 'b') {
      c.bend = event[2]
      const cents = (c.bend / 8192) * c.bendRange * 100
      for (const note of c.notes) (note as AudioBufferSourceNode | OscillatorNode).detune.setValueAtTime(cents, at)
    } else if (event[1] === 'n') {
      const length = this.seconds(event[0] + event[4]) - this.seconds(event[0])
      this.note(at, c, event[2], event[3], Math.max(length, 0.01))
    }
  }

  note(at: number, c: ReturnType<Session['channel']>, key: number, velocity: number, length: number) {
    let voice = this.bank.voices[c.program] ?? { kind: 'none' }
    if (voice.kind === 'drums') {
      voice = voice.voices?.[key] ?? { kind: 'none' }
      key = voice.key ?? 60
    }
    if (voice.kind === 'none' || voice.kind === 'drums' || voice.kind === 'split') return
    const audio = this.audio
    let source: AudioBufferSourceNode | OscillatorNode
    let cgb = false
    if (voice.kind === 'sample' || voice.kind === 'fixed') {
      const buffer = this.samples.get(voice.sample!)
      if (!buffer) return
      const s = audio.createBufferSource()
      s.buffer = buffer
      const info = this.bank.samples[voice.sample!]
      if (info?.loop != null && info.loop < info.frames) {
        s.loop = true
        s.loopStart = info.loop / info.rate   // the browser may resample the buffer: the loop is in the sample's frames
        s.loopEnd = buffer.duration
      }
      if (voice.kind === 'sample') s.playbackRate.value = 2 ** ((key - 60) / 12)
      source = s
    } else if (voice.kind === 'noise') {
      const s = audio.createBufferSource()
      s.buffer = this.noiseBuffer(voice.period ?? 0)
      s.loop = true
      s.playbackRate.value = Math.min(4, 2 ** ((key - 60) / 12))
      source = s
      cgb = true
    } else {
      const o = audio.createOscillator()
      o.frequency.value = 440 * 2 ** ((key - 69) / 12)
      const wave = voice.kind === 'square' ? this.squareWave(voice.duty ?? 2) : this.gbWave(voice.wave ?? '')
      if (wave) o.setPeriodicWave(wave)
      source = o
      cgb = true
    }
    source.detune.value = (c.bend / 8192) * c.bendRange * 100
    const env = audio.createGain()
    const peak = (velocity / 127) * (cgb ? CGB_GAIN : 1)
    const [a, d, s, r] = voice.env ?? [255, 0, 255, 0]
    const g = env.gain
    g.setValueAtTime(0, at)
    let release: number
    if (cgb) {
      const attackEnd = at + (a ? a * 4 * FRAME : 0.003)
      g.linearRampToValueAtTime(peak, attackEnd)
      g.setTargetAtTime(peak * (s / 15), attackEnd, d ? d * 4 * FRAME : 0.003)
      release = r ? r * 4 * FRAME : 0.01
    } else {
      const attackEnd = at + (a >= 255 ? 0.003 : (255 / Math.max(a, 1)) * FRAME)
      g.linearRampToValueAtTime(peak, attackEnd)
      g.setTargetAtTime(peak * (s / 255), attackEnd, tau(d))
      release = tau(r)
    }
    const off = at + length
    g.cancelScheduledValues(off)
    g.setTargetAtTime(0, off, release)
    source.connect(env)
    if (voice.pan) {
      const panner = audio.createStereoPanner()
      panner.pan.value = Math.max(-1, Math.min(1, ((voice.pan & 0x7f) - 64) / 63))
      env.connect(panner).connect(c.fixed)
    } else env.connect(c.gain)
    source.start(at)
    source.stop(off + Math.min(release * 6, 4))
    this.sources.add(source)
    c.notes.add(source)
    source.onended = () => { this.sources.delete(source); c.notes.delete(source); env.disconnect() }
  }

  squareWave(duty: number): PeriodicWave {
    if (!this.squares.has(duty)) {
      const width = [0.125, 0.25, 0.5, 0.75][duty] ?? 0.5
      const real = new Float32Array(64), imag = new Float32Array(64)
      for (let n = 1; n < 64; n++) imag[n] = (2 / (n * Math.PI)) * Math.sin(n * Math.PI * width) * Math.cos(n * Math.PI * width)
      for (let n = 1; n < 64; n++) real[n] = (2 / (n * Math.PI)) * Math.sin(n * Math.PI * width) * Math.sin(n * Math.PI * width)
      this.squares.set(duty, this.audio.createPeriodicWave(real, imag))
    }
    return this.squares.get(duty)!
  }

  gbWave(name: string): PeriodicWave | null {
    const steps = this.bank.waves[name]
    if (!steps) return null
    if (!this.gbWaves.has(name)) {
      const size = steps.length, real = new Float32Array(16), imag = new Float32Array(16)
      for (let n = 1; n < 16; n++) {
        for (let i = 0; i < size; i++) {
          const v = steps[i] / 7.5 - 1
          real[n] += (v * Math.cos((2 * Math.PI * n * i) / size)) / size
          imag[n] += (v * Math.sin((2 * Math.PI * n * i) / size)) / size
        }
      }
      this.gbWaves.set(name, this.audio.createPeriodicWave(real, imag))
    }
    return this.gbWaves.get(name)!
  }

  /** GB noise: the 15-bit generator (white) or the 7-bit one (metallic). */
  noiseBuffer(period: number): AudioBuffer {
    if (!this.noise[period]) {
      const rate = this.audio.sampleRate, buffer = this.audio.createBuffer(1, rate, rate), data = buffer.getChannelData(0)
      let lfsr = 0x7fff
      const width = period ? 7 : 15
      for (let i = 0; i < data.length; i++) {
        const bit = (lfsr ^ (lfsr >> 1)) & 1
        lfsr = (lfsr >> 1) | (bit << (width - 1))
        data[i] = bit ? 0.5 : -0.5
      }
      this.noise[period] = buffer
    }
    return this.noise[period]
  }

  finish() {
    this.stop()
    this.onend()
  }

  stop() {
    window.clearInterval(this.timer)
    const now = this.audio.currentTime
    this.master.gain.setTargetAtTime(0, now, 0.03)
    for (const s of this.sources) {
      try { s.stop(now + 0.15) } catch { /* already stopped */ }
    }
    window.setTimeout(() => this.master.disconnect(), 300)
  }
}

/** The samples a song needs: those of the programs (and drum keys) its channels play. */
function neededSamples(song: Song, b: Bank): Set<string> {
  const names = new Set<string>()
  for (const list of Object.values(song.midi.channels)) {
    let program = 0
    for (const e of list) {
      if (e[1] === 'p') program = e[2]
      else if (e[1] === 'n') {
        let voice = b.voices[program]
        if (voice?.kind === 'drums') voice = voice.voices?.[e[2]] ?? { kind: 'none' }
        if (voice?.sample && (voice.kind === 'sample' || voice.kind === 'fixed')) names.add(voice.sample)
      }
    }
  }
  return names
}

export function stopSong() {
  session?.stop()
  session = null
  songPlayer.playing = null
}

/** Plays a song (game song number or imported key); the one playing stops. */
export async function playSong(ref: SongRef) {
  stopSong()
  songPlayer.playing = ref
  songPlayer.loading = true
  songPlayer.error = ''
  try {
    ctx ??= new AudioContext()
    if (ctx.state === 'suspended') await ctx.resume()
    const response = await fetch(`/api/music/play/${encodeURIComponent(String(ref))}`)
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail ?? response.statusText)
    const song: Song = await response.json()
    const b = await bank(song.voicegroup)
    const audio = ctx
    const names = [...neededSamples(song, b)]
    const loaded = await Promise.all(names.map((n) => sampleBuffer(audio, n).catch(() => null)))
    const samples = new Map<string, AudioBuffer>()
    names.forEach((n, i) => { if (loaded[i]) samples.set(n, loaded[i]!) })
    if (songPlayer.playing !== ref) return   // another song was asked meanwhile
    session = new Session(audio, song, b, samples, () => { if (songPlayer.playing === ref) { session = null; songPlayer.playing = null } })
  } catch (e) {
    songPlayer.error = String(e instanceof Error ? e.message : e)
    if (songPlayer.playing === ref) songPlayer.playing = null
  } finally {
    songPlayer.loading = false
  }
}

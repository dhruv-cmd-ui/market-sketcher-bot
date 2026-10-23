"""One-off generator for the Reels' royalty-free audio (all synthesized, no samples).

Writes WAVs into reels/<project>/assets/audio/. Re-run only to change the sound:
    .venv/Scripts/python scripts/make_audio.py
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(7)


def _t(seconds):
    return np.arange(int(SR * seconds)) / SR


def _lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def _write(path: Path, left, right=None, peak=0.89):
    right = left if right is None else right
    stereo = np.stack([left, right], axis=1)
    stereo = stereo / (np.max(np.abs(stereo)) + 1e-9) * peak
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    print("wrote", path.relative_to(ROOT))


def _saw(freq, t, harmonics=10):
    return sum(np.sin(2 * np.pi * freq * n * t) / n for n in range(1, harmonics + 1))


def _pluck(freq, t_rel, dur=0.26):
    """Bright, fast-attack plucked/bell tone -- the arpeggio voice that gives
    corporate-motivational tracks their signature "inspirational" character."""
    env = np.exp(-t_rel / 0.17)
    tone = (np.sin(2 * np.pi * freq * t_rel) + 0.5 * np.sin(2 * np.pi * freq * 2 * t_rel)
           + 0.25 * np.sin(2 * np.pi * freq * 3 * t_rel))
    return tone * env * (t_rel < dur)


def _note(f):
    return 440.0 * 2 ** ((f - 69) / 12)


def _energy_gate(bar_index: int, layer: str) -> float:
    """Builds from a sparse intro (pad + soft bass only) through a "drop" (drums and
    the arpeggio enter) into full, sustained energy by bar 3 -- the intro/build/peak
    shape motivational/corporate tracks use, instead of looping at one flat energy
    level the whole way through."""
    stage = min(bar_index, 3)
    return {
        "pad": 1.0,
        "bass": 0.7 if stage == 0 else 1.0,
        "kick": [0.0, 0.7, 1.0, 1.0][stage],
        "hats": [0.0, 0.5, 1.0, 1.0][stage],
        "clap": 0.0 if stage < 2 else 1.0,
        "arp": [0.0, 0.5, 0.8, 1.0][stage],
    }[layer]


def music(seconds, bpm, chords, bass_roots):
    """Corporate-motivational: warm major-key pad chords, a bright plucked arpeggio
    lead, sub bass, kick/clap/hats, sidechained -- builds from a sparse intro into a
    driving, sustained-energy groove (see _energy_gate) for an uplifting finance/
    success-content feel rather than a laid-back, flat-energy lo-fi loop."""
    t = _t(seconds)
    beat = 60 / bpm
    bar = beat * 4
    pad_l = np.zeros_like(t)
    pad_r = np.zeros_like(t)
    bass = np.zeros_like(t)
    arp = np.zeros_like(t)
    for i, (chord, root) in enumerate(zip(chords * 20, bass_roots * 20)):
        start = i * bar
        if start >= seconds:
            break
        seg = (t >= start) & (t < start + bar + 0.4)
        lt = t[seg] - start
        env = np.minimum(1, lt / 0.35) * np.exp(-np.maximum(0, lt - bar) / 0.15) * _energy_gate(i, "pad")
        for n in chord:
            f = _note(n)
            pad_l[seg] += _saw(f * 0.998, lt, 4) * env
            pad_r[seg] += _saw(f * 1.002, lt, 4) * env
        g_bass = _energy_gate(i, "bass")
        for b in range(4):
            bs = start + b * beat
            m = (t >= bs) & (t < bs + beat)
            bt = t[m] - bs
            bass[m] += np.sin(2 * np.pi * _note(root) * bt) * np.exp(-bt / 0.35) * g_bass
        # Arpeggio: steps up through the chord tones (one octave above the pad) on
        # each 8th note of the bar -- the plucked, rising-and-falling melodic hook.
        g_arp = _energy_gate(i, "arp")
        if g_arp > 0:
            arp_tones = [_note(n + 12) for n in chord] + [_note(chord[0] + 24)]
            for step in range(8):
                st = start + step * (beat / 2)
                if st >= seconds:
                    break
                m = (t >= st) & (t < st + beat / 2 + 0.3)
                at = t[m] - st
                arp[m] += _pluck(arp_tones[step % len(arp_tones)], at) * g_arp
    pad_l, pad_r = _lowpass(pad_l, 1400), _lowpass(pad_r, 1400)
    arp = _lowpass(arp, 7000)

    kick = np.zeros_like(t)
    clap = np.zeros_like(t)
    hats = np.zeros_like(t)
    duck = np.ones_like(t)
    n_beats = int(seconds / beat) + 1
    for k in range(n_beats):
        bar_i = int((k * beat) // bar)
        s = k * beat
        m = (t >= s) & (t < s + beat)
        kt = t[m] - s
        g_kick = _energy_gate(bar_i, "kick")
        if g_kick > 0:
            freq = 45 + 75 * np.exp(-kt / 0.04)
            kick[m] += np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-kt / 0.22) * g_kick
            duck[m] = 1 - 0.55 * g_kick * np.exp(-kt / 0.12)
        g_clap = _energy_gate(bar_i, "clap")
        if k % 2 == 1 and g_clap > 0:
            noise = rng.standard_normal(m.sum())
            clap[m] += (noise - _lowpass(noise, 900)) * np.exp(-kt / 0.05) * g_clap
        g_hats = _energy_gate(bar_i, "hats")
        if g_hats > 0:
            hm = (t >= s + beat / 2) & (t < s + beat / 2 + 0.06)
            if hm.any():
                ht = t[hm] - (s + beat / 2)
                noise = rng.standard_normal(hm.sum())
                hats[hm] += (noise - _lowpass(noise, 6000)) * np.exp(-ht / 0.015) * g_hats

    left = 0.20 * pad_l * duck + 0.45 * bass * duck + 0.9 * kick + 0.11 * clap + 0.10 * hats + 0.30 * arp * duck
    right = 0.20 * pad_r * duck + 0.45 * bass * duck + 0.9 * kick + 0.11 * clap + 0.10 * hats + 0.30 * arp * duck
    fade = np.minimum(1, np.minimum(t / 0.5, (seconds - t) / 1.5))
    return left * fade, right * fade


def whoosh(seconds=0.75):
    t = _t(seconds)
    noise = rng.standard_normal(t.size)
    sweep_lo = _lowpass(noise, 600)
    sweep_hi = _lowpass(noise, 4000)
    mix = np.linspace(0, 1, t.size) ** 1.5
    body = sweep_lo * (1 - mix) + (sweep_hi - sweep_lo) * mix * 1.6
    env = np.sin(np.pi * np.clip(t / seconds, 0, 1)) ** 2
    return body * env


def pop(seconds=0.18):
    t = _t(seconds)
    freq = 300 + 900 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.05)


def riser(seconds=1.4):
    t = _t(seconds)
    freq = 200 * 2 ** (2.5 * t / seconds)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    noise = rng.standard_normal(t.size)
    airy = noise - _lowpass(noise, 2500)
    env = (t / seconds) ** 2.2
    return (0.6 * tone + 0.5 * airy) * env


def impact(seconds=1.2):
    t = _t(seconds)
    freq = 35 + 70 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.45)
    noise = rng.standard_normal(t.size)
    crack = _lowpass(noise, 2500) * np.exp(-t / 0.05)
    return boom + 0.7 * crack


def tick(seconds=0.05):
    t = _t(seconds)
    return np.sin(2 * np.pi * 2200 * t) * np.exp(-t / 0.008)


if __name__ == "__main__":
    sfx = {"whoosh": whoosh(), "pop": pop(), "riser": riser(), "impact": impact(), "tick": tick()}
    news_dir = ROOT / "reels" / "news" / "assets" / "audio"
    fii_dir = ROOT / "reels" / "fii_dii" / "assets" / "audio"
    # Major-key, uplifting "four chords" progressions (the classic corporate/
    # motivational sound) -- C-G-Am-F at 112 bpm for news; F-C-G-Am at 116 bpm
    # for FII/DII, so the two tracks are related but distinguishable.
    _write(news_dir / "music.wav", *music(12.5, 112, [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]],
                                           [48, 43, 45, 41]), peak=0.7)
    # 12.1s so it fully covers the 11.6s FII/DII reel (hook overlay + panel reveal)
    # plus a little margin for the fade-out tail, same pattern as the news track.
    _write(fii_dir / "music.wav", *music(12.1, 116, [[53, 57, 60], [60, 64, 67], [55, 59, 62], [57, 60, 64]],
                                          [41, 48, 43, 45]), peak=0.7)
    for name, sig in sfx.items():
        _write(news_dir / f"{name}.wav", sig)
        _write(fii_dir / f"{name}.wav", sig)

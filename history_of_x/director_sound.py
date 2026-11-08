"""Restrained recorded scoring, silence, and explicitly directed original foley.

Music is licensed, bundled audio rather than a generated four-note loop.  This
module builds quiet stereo stems; narration-aware ducking belongs to audio_edit.
No sound is added merely because a shot or visual event starts.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .core import ROOT, PipelineError, read_json, save_json

RATE = 48000
CATALOG = ROOT / "assets" / "music" / "catalog.json"
TRAGIC = re.compile(
    r"\b(?:massacre\w*|famine\w*|starv\w*|atrocit\w*|genocide\w*|"
    r"terror|repression|civilian deaths|killed|deaths|victims)\b", re.I
)
FOLEY = {"paper", "stamp", "soft_impact", "sting"}


def _track(shot):
    mood = shot.get("music_mood", "neutral")
    if mood in ("somber", "reflective"):
        return "celestial"
    if mood == "tense":
        return "titan"
    return "aurora"


def _load(path):
    data, rate = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    else:
        data = data[:, :2]
    if rate != RATE:
        divisor = math.gcd(rate, RATE)
        data = resample_poly(data, RATE // divisor, rate // divisor, axis=0).astype("float32")
    if not len(data) or not np.all(np.isfinite(data)):
        raise PipelineError(f"Invalid bundled music: {path}")
    rms = float(np.sqrt(np.mean(data.astype("float64") ** 2)))
    peak = float(np.max(np.abs(data)))
    # Subtle underbed, with the source's musical dynamics retained. Even the
    # busiest source stays well below the voice before sidechain ducking.
    data *= min(.017 / max(rms, 1e-9), .075 / max(peak, 1e-9))
    return data


def _loop(data, length, offset=0):
    """Extend an excerpt using overlap crossfades, including at every loop seam."""
    if length <= 0:
        return np.zeros((0, 2), dtype="float32")
    offset = min(max(0, offset), max(0, len(data) - RATE * 12))
    first = data[offset:]
    if length <= len(first):
        return first[:length].copy()
    result = np.zeros((length, 2), dtype="float32")
    result[:len(first)] = first
    cursor = len(first)
    overlap = min(RATE * 5, len(data) // 4)
    while cursor < length:
        begin = cursor - overlap
        count = min(len(data), length - begin)
        blended = min(overlap, count)
        ramp = np.linspace(0, 1, blended, dtype="float32")[:, None]
        result[begin:begin + blended] *= 1 - ramp
        result[begin:begin + blended] += data[:blended] * ramp
        result[begin + blended:begin + count] = data[blended:count]
        cursor = begin + count
    return result


def _silences(shots, total):
    intervals = []
    for shot in shots:
        serious = TRAGIC.search(shot.get("narration_context", shot.get("text", "")))
        if shot.get("music_silence") is True or serious:
            begin, end = max(0., float(shot["global_start"])), min(total, float(shot["global_end"]))
            if intervals and begin <= intervals[-1][1] + .25:
                intervals[-1][1] = max(intervals[-1][1], end)
            else:
                intervals.append([begin, end])
    return intervals


def _silence_envelope(buffer, intervals):
    # Fade down BEFORE a difficult passage and resume AFTER it; the actual
    # passage is silent, rather than merely scored in a minor key.
    length = len(buffer)
    for start, end in intervals:
        a, b = round(start * RATE), min(length, round(end * RATE))
        fade = round(1.5 * RATE)
        before = max(0, a - fade)
        after = min(length, b + fade)
        if a > before:
            buffer[before:a] *= np.linspace(1, 0, a - before, dtype="float32")[:, None]
        buffer[a:b] = 0
        if after > b:
            buffer[b:after] *= np.linspace(0, 1, after - b, dtype="float32")[:, None]


def _foley(kind, seed=0):
    """Very short original noise-based prop sounds, never borrowed jingles."""
    seconds = {"paper": .25, "stamp": .12, "soft_impact": .2, "sting": .45}[kind]
    t = np.arange(round(seconds * RATE), dtype="float32") / RATE
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, len(t)).astype("float32")
    # A lightly filtered noise texture avoids bright electronic ticks.
    noise = np.convolve(noise, np.ones(7, dtype="float32") / 7, mode="same")
    if kind == "paper":
        wave = noise * np.sin(np.pi * t / seconds) ** 2 * .025
    elif kind == "sting":
        # One muted wooden resonance with a soft attack, not a tune.
        wave = (np.sin(2 * np.pi * 196 * t) + .2 * noise) * np.exp(-t * 12) * .024
    else:
        wave = (.55 * noise + .45 * np.sin(2 * np.pi * 90 * t)) * np.exp(-t * 35) * .045
    wave *= np.minimum(1, t * 500) * np.minimum(1, (seconds - t) * 500)
    return np.repeat(wave[:, None].astype("float32"), 2, axis=1)


def compose(speech, shots, directory):
    """Write music.wav/sfx.wav plus off-screen attribution and return duration."""
    if not shots:
        raise PipelineError("Cannot score an empty timeline")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    shots = sorted(shots, key=lambda s: s["global_start"])
    for shot in shots:
        a, b = float(shot["global_start"]), float(shot["global_end"])
        if not math.isfinite(a + b) or a < 0 or b <= a:
            raise PipelineError("Invalid scoring timeline")
    total = max(float(s["global_end"]) for s in shots)
    length = round(total * RATE)
    music = np.zeros((length, 2), dtype="float32")
    sfx = np.zeros_like(music)
    silences = _silences(shots, total)
    catalog = read_json(CATALOG)

    # Musical phrases survive individual cuts. A new mood gets a cue only
    # after a meaningful span; chapter changes can deliberately reset it.
    cues = [{"start": 0., "track": _track(shots[0]), "chapter": shots[0].get("chapter")}]
    for shot in shots[1:]:
        at = float(shot["global_start"])
        chapter = shot.get("chapter")
        changed_chapter = chapter is not None and chapter != cues[-1].get("chapter")
        desired = _track(shot)
        if desired != cues[-1]["track"] and (at - cues[-1]["start"] >= 28 or changed_chapter):
            cues.append({"start": at, "track": desired, "chapter": chapter})
    tracks = {}
    for i, cue in enumerate(cues):
        cue["end"] = cues[i + 1]["start"] if i + 1 < len(cues) else total
        name = cue["track"]
        if name not in catalog:
            raise PipelineError(f"Missing licensed music cue: {name}")
        if name not in tracks:
            tracks[name] = _load(CATALOG.parent / catalog[name]["file"])
        # Slow overlapping transitions, not hard changes at scene boundaries.
        start = max(0., cue["start"] - (3 if i else 0))
        end = min(total, cue["end"] + (3 if i + 1 < len(cues) else 0))
        a, b = round(start * RATE), round(end * RATE)
        segment = _loop(tracks[name], b - a, offset=(i * 7 % 24) * RATE)
        fade = min(round(6 * RATE), len(segment) // 2)
        if fade:
            segment[:fade] *= np.linspace(0, 1, fade, dtype="float32")[:, None]
            segment[-fade:] *= np.linspace(1, 0, fade, dtype="float32")[:, None]
        # Titan is used only for tension and restrained further to avoid
        # turning every conflict into a trailer.
        if name == "titan":
            segment *= .65
        music[a:b] += segment
    _silence_envelope(music, silences)

    directed = []
    for shot in shots:
        start, end = float(shot["global_start"]), float(shot["global_end"])
        events = list(shot.get("events", []))
        if shot.get("sfx_cue") in FOLEY:
            events.append({"time": 0., "sfx": shot["sfx_cue"]})
        if shot.get("sting") is True:
            events.append({"time": max(0., end - start - .6), "sfx": "sting"})
        for event in events:
            kind = event.get("sfx")
            if kind not in FOLEY:
                continue
            local = float(event.get("time", 0))
            if not math.isfinite(local) or not 0 <= local < end - start:
                raise PipelineError("Explicit sound event falls outside its scene")
            at = start + local
            if any(a - 1 <= at <= b + 1 for a, b in silences):
                continue
            wave = _foley(kind, len(directed))
            a = round(at * RATE)
            count = min(len(wave), length - a)
            sfx[a:a + count] += wave[:count]
            directed.append({"at": at, "type": kind})
    # Conservative stem headroom even if several explicit events coincide.
    for buffer in (music, sfx):
        peak = float(np.max(np.abs(buffer))) if buffer.size else 0
        if peak > .12:
            buffer *= .12 / peak
    sf.write(directory / "music.wav", music, RATE, subtype="PCM_16")
    sf.write(directory / "sfx.wav", sfx, RATE, subtype="PCM_16")
    audible = [cue for cue in cues if not any(a <= cue["start"] and b >= cue["end"] for a, b in silences)]
    used = sorted({cue["track"] for cue in audible})
    credits = [{"id": name, **catalog[name]} for name in used]
    save_json(directory / "music-credits.json", credits)
    (directory / "music-credits.txt").write_text("\n\n".join(
        f'{c["title"]} by {c["artist"]} — {c["license"]}\n{c["source"]}\n{c["license_url"]}\n'
        'Excerpted, normalized, looped with crossfades and ducked under narration.' for c in credits
    ) + ("\n" if credits else ""))
    save_json(directory / "soundtrack.json", {
        "duration": total, "sample_rate": RATE, "channels": 2,
        "approach": "Licensed recorded underbed; long crossfades; silence for tragic passages; explicit foley only",
        "cues": cues, "silence_intervals": silences, "explicit_sfx": directed, "music_credits": credits,
    })
    return total

from pathlib import Path
import random
import numpy as np
import wave

def save_wav(path, audio, sample_rate):
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())

def load_wav(path, sample_rate):
    """Carga un WAV como float32 mono a SAMPLE_RATE."""
    with wave.open(str(path), "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = pcm.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != sample_rate and len(audio) > 1:
        n = int(len(audio) * sample_rate / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n),
                          np.arange(len(audio)), audio).astype(np.float32)
    return audio

def chirp(sample_rate):
    """Un 'pio' de loro: barrido de tono corto con envolvente suave."""
    dur = random.uniform(0.15, 0.35)
    t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
    f0 = random.uniform(1200, 2200)
    f1 = random.uniform(2500, 3600) if random.random() < 0.5 else random.uniform(600, 1100)
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * dur))
    return (0.4 * np.sin(phase) * np.sin(np.pi * t / dur)).astype(np.float32)

def mutate(audio, pitch_range, sample_rate, truncate_prob):
    """Pequeñas variaciones para que suene a loro y no a grabadora."""
    if random.random() < truncate_prob and len(audio) > sample_rate:
        audio = audio[int(len(audio) * random.uniform(0.4, 0.6)):]
    factor = random.uniform(*pitch_range)
    idx = np.arange(0, len(audio) - 1, factor)
    return np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)

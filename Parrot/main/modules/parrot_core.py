from collections import deque
import queue
import random
import re
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from modules.database import init_db, prune_db
from modules.audio_utils import save_wav, load_wav, chirp, mutate
from modules.tts import synthesize

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.05
MIN_PHRASE_S = 0.4
MAX_PHRASE_S = 8.0
END_SILENCE_S = 0.8
PREROLL_S = 0.3
NOISE_FACTOR = 3.0
MIN_THRESHOLD = 0.01

ECHO_PROB = 0.6
ECHO_DELAY_S = (2, 12)
IDLE_INTERVAL_S = (60, 240)
TRUNCATE_PROB = 0.15

VOICE_MODE = "mixed"
PITCH_RANGE = (1.10, 1.30)
SYNTH_PITCH_RANGE = (1.15, 1.35)
CHIRP_PROB = 0.3
IDLE_CHIRP_ONLY_PROB = 0.15

TTS_ENGINE = "espeak"
ESPEAK_VOICE = "es"
ESPEAK_PITCH = 85
ESPEAK_SPEED = 185
PIPER_MODEL = "es_ES-davefx-medium.onnx"

MAX_CLIPS = 300
WHISPER_MODEL = "tiny"
LANGUAGE = "es"
DATA_DIR = Path("parrot_data")

BLOCK = int(SAMPLE_RATE * BLOCK_SECONDS)

class Parrot:
    def __init__(self, use_stt=True, voice_mode=VOICE_MODE):
            (DATA_DIR / "clips").mkdir(parents=True, exist_ok=True)
            self.voice_mode = voice_mode
            self.db = init_db(DATA_DIR)
            self.playing = False
            self.stt = None
            if use_stt:
                from faster_whisper import WhisperModel
                print(f"Cargando Whisper '{WHISPER_MODEL}'...")
                self.stt = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

    def transcribe(self, audio):
        if self.stt is None or audio is None or len(audio) == 0:
            return ""
        try:
            audio = np.asarray(audio, dtype=np.float32)
            if audio.ndim > 1:
                 audio = audio.mean(axis=1)
            segments, _ = self.stt.transcribe(audio, language=LANGUAGE, beam_size=1)
            text = " ".join(s.text for s in segments).lower()
            return re.sub(r"[^\w\s]", "", text).strip()
        except Exception as e:
            print(f"Error en la transcripción: {e}")
            return ""

    def learn(self, audio):
        text = None
        if self.stt:
            text = self.transcribe(audio)
            if len(text) < 2:
                return None
        now = time.time()
        if text:
            row = self.db.execute("SELECT id FROM phrases WHERE text=?", (text,)).fetchone()
            if row:
                self.db.execute(
                    "UPDATE phrases SET times_heard=times_heard+1, last_heard=? WHERE id=?",
                    (now, row[0]),
                )
                self.db.commit()
                print(f"[oído de nuevo] #{row[0]}: {text}")
                return row[0]
        path = DATA_DIR / "clips" / f"{int(now * 1000)}.wav"
        save_wav(path, audio, SAMPLE_RATE)
        cur = self.db.execute(
            "INSERT INTO phrases (text, path, created_at, last_heard) VALUES (?,?,?,?)",
            (text, str(path), now, now),
        )
        self.db.commit()
        print(f"[nueva] #{cur.lastrowid}: {text or '(sin transcribir)'}")
        prune_db(self.db, DATA_DIR, MAX_CLIPS)
        return cur.lastrowid

    def resolve_voice(self, kind):
        if self.voice_mode == "original":
            return "original"
        if self.voice_mode == "synthetic":
            return "synthetic"
        return "original" if kind == "echo" else "synthetic"

    def output(self, audio):
        self.playing = True
        try:
            sd.play(audio, SAMPLE_RATE)
            sd.wait()
            time.sleep(0.3)
        finally:
            self.playing = False

    def play(self, clip_id=None, kind="idle", voice=None):
        speech, label = None, "(ruidos de loro)"
        if clip_id is not None:
            row = self.db.execute("SELECT path, text FROM phrases WHERE id=?", (clip_id,)).fetchone()
            if not row:
                return
            path, text = row
            voice = voice or self.resolve_voice(kind)
            if voice == "synthetic" and text:
                speech = synthesize(text, DATA_DIR, TTS_ENGINE, ESPEAK_VOICE, ESPEAK_PITCH, ESPEAK_SPEED, PIPER_MODEL, SAMPLE_RATE)
                if speech is not None:
                    speech = mutate(speech, SYNTH_PITCH_RANGE, SAMPLE_RATE, TRUNCATE_PROB)
            if speech is None:
                if not Path(path).exists():
                    return
                voice = "original"
                speech = mutate(load_wav(path, SAMPLE_RATE), PITCH_RANGE, SAMPLE_RATE, TRUNCATE_PROB)
            label = f"#{clip_id} [{voice}]: {text or ''}"
        parts = []
        if speech is None or random.random() < CHIRP_PROB:
            parts += [chirp(SAMPLE_RATE), np.zeros(int(0.08 * SAMPLE_RATE), dtype=np.float32)]
        if speech is not None:
            parts.append(speech)
        print(f"[LORO dice] {label}")
        self.output(np.concatenate(parts))
        if clip_id is not None:
            self.db.execute("UPDATE phrases SET times_played=times_played+1 WHERE id=?", (clip_id,))
            self.db.commit()

    def speak_text(self, text):
        audio = synthesize(text, DATA_DIR, TTS_ENGINE, ESPEAK_VOICE, ESPEAK_PITCH, ESPEAK_SPEED, PIPER_MODEL, SAMPLE_RATE)
        if audio is None:
            return
        self.output(np.concatenate([chirp(SAMPLE_RATE),
                                    np.zeros(int(0.08 * SAMPLE_RATE), dtype=np.float32),
                                    mutate(audio, SYNTH_PITCH_RANGE, SAMPLE_RATE, TRUNCATE_PROB)]))

    def pick_random(self):
        rows = self.db.execute("SELECT id, times_heard FROM phrases").fetchall()
        if not rows:
            return None
        return random.choices([r[0] for r in rows], weights=[r[1] for r in rows])[0]

    def run(self):
        q = queue.Queue()

        def callback(indata, frames, t, status):
            if not self.playing:
                q.put(indata[:, 0].copy())

        def flush():
            while not q.empty():
                q.get_nowait()

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=BLOCK, callback=callback):
            print("Calibrando ruido ambiente (1 s, silencio por favor)...")
            levels = [float(np.sqrt(np.mean(q.get() ** 2))) for _ in range(int(1 / BLOCK_SECONDS))]
            threshold = max(MIN_THRESHOLD, float(np.mean(levels)) * NOISE_FACTOR)
            print(f"Umbral de voz: {threshold:.4f}. Voz: {self.voice_mode}. "
                  "Loro escuchando. (Ctrl+C para salir)")

            preroll = deque(maxlen=int(PREROLL_S / BLOCK_SECONDS))
            frames, recording, silent = [], False, 0
            pending = []
            next_idle = time.time() + random.uniform(*IDLE_INTERVAL_S)

            while True:
                try:
                    chunk = q.get(timeout=0.2)
                except queue.Empty:
                    chunk = None
                now = time.time()

                if chunk is not None:
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    if recording:
                        frames.append(chunk)
                        silent = silent + 1 if rms < threshold else 0
                        too_long = len(frames) * BLOCK_SECONDS >= MAX_PHRASE_S
                        if silent * BLOCK_SECONDS >= END_SILENCE_S or too_long:
                            audio = np.concatenate(frames)
                            keep = len(audio) - silent * BLOCK + int(0.2 * SAMPLE_RATE)
                            audio = audio[:max(keep, 0)]
                            recording, frames, silent = False, [], 0
                            if len(audio) / SAMPLE_RATE >= MIN_PHRASE_S:
                                clip_id = self.learn(audio)
                                if clip_id and random.random() < ECHO_PROB:
                                    pending.append((now + random.uniform(*ECHO_DELAY_S), clip_id))
                    elif rms >= threshold:
                        recording, silent = True, 0
                        frames = list(preroll) + [chunk]
                    else:
                        preroll.append(chunk)

                if not recording:
                    for item in [p for p in pending if p[0] <= now]:
                        pending.remove(item)
                        self.play(item[1], kind="echo")
                        flush()
                        preroll.clear()
                    if now >= next_idle:
                        clip_id = self.pick_random()
                        if clip_id is None or random.random() < IDLE_CHIRP_ONLY_PROB:
                            self.play(None)
                        else:
                            self.play(clip_id, kind="idle")
                        flush()
                        preroll.clear()
                        next_idle = time.time() + random.uniform(*IDLE_INTERVAL_S)

    def list_phrases(self):
        rows = self.db.execute(
            "SELECT id, times_heard, times_played, text FROM phrases ORDER BY times_heard DESC"
        ).fetchall()
        print(f"{'id':>4} {'oído':>5} {'dicho':>6}  texto")
        for r in rows:
            print(f"{r[0]:>4} {r[1]:>5} {r[2]:>6}  {r[3] or '(sin transcribir)'}")

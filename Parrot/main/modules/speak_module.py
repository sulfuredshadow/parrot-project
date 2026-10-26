
#ONLY WORKS W/INTERNET CONNECTION
# IT WILL BE CHANGED
import os
from gtts import gTTS
from pathlib import Path

tempaudio = Path("/Parrot/audio")
tempaudio.mkdir(parents=True, exist_ok=True)
file_wav = tempaudio  / "test.wav"

text2voice = ""
language = "es_ES"

def gen_audio():
    print("Gen audio func used")
    if file_wav.is_file():
        file_wav.unlink()

    tts = gTTS(text=text2voice, lang=language, slow=False)
    tts.save("test.wav")
    print("Audio saved")

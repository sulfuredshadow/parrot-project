from pathlib import Path
import subprocess
from modules.audio_utils import load_wav

def synthesize(text, data_dir, tts_engine, espeak_voice, espeak_pitch, espeak_speed, piper_model, sample_rate):
    """Texto -> audio con voz sintética. Devuelve None si falla."""
    tmp = data_dir / "tts_tmp.wav"
    try:
        if tts_engine == "piper":
            cmd = ["piper", "--model", piper_model, "--output_file", str(tmp)]
        else:
            cmd = ["espeak-ng", "-v", espeak_voice, "-p", str(espeak_pitch),
                   "-s", str(espeak_speed), "--stdin", "-w", str(tmp)]
        subprocess.run(cmd, input=text.encode("utf-8"), check=True,
                       capture_output=True, timeout=30)
        return load_wav(tmp, sample_rate)
    except FileNotFoundError:
        print(f"[aviso] no encuentro '{cmd[0]}'. Instálalo o usa VOICE_MODE='original'.")
    except Exception as e:
        print(f"[aviso] falló la voz sintética: {e}")
    return None

#!/usr/bin/env python3
import argparse
import sounddevice as sd
import os; os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
from modules.parrot_core import Parrot, VOICE_MODE

def main():
    ap = argparse.ArgumentParser(description="Loro local")
    ap.add_argument("--no-stt", action="store_true", help="no transcribir (mas ligero)")
    ap.add_argument("--voice", choices=["original", "synthetic", "mixed"],
                    help="modo de voz (por defecto el de VOICE_MODE)")
    ap.add_argument("--list", action="store_true", help="listar frases aprendidas")
    ap.add_argument("--say", type=int, metavar="ID", help="reproducir una frase")
    ap.add_argument("--speak", metavar="TEXTO", help="probar la voz sintetica con un texto")
    ap.add_argument("--devices", action="store_true", help="listar dispositivos de audio")
    args = ap.parse_args()

    if args.devices:
        print(sd.query_devices())
        return
    quick = args.list or args.say or args.speak
    parrot = Parrot(use_stt=not (args.no_stt or quick), voice_mode=args.voice or VOICE_MODE)
    if args.list:
        parrot.list_phrases()
    elif args.say:
        parrot.play(args.say, voice=args.voice if args.voice in ("original", "synthetic") else None)
    elif args.speak:
        parrot.speak_text(args.speak)
    else:
        try:
            parrot.run()
        except KeyboardInterrupt:
            print("\nSaliendo...")

if __name__ == "__main__":
    main()

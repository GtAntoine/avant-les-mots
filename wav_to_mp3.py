#!/usr/bin/env python3
"""Convertit les WAV de l'audiobook en MP3 via lameenc."""

import wave
import lameenc
from pathlib import Path

INPUT_DIR = Path("audiobook")
OUTPUT_DIR = Path("audiobook_mp3")
BITRATE = 128


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(BITRATE)
    encoder.set_in_sample_rate(framerate)
    encoder.set_channels(channels)
    encoder.set_quality(2)

    mp3_data = encoder.encode(frames) + encoder.flush()
    mp3_path.write_bytes(mp3_data)


# Chapitres
chapters_out = OUTPUT_DIR / "chapitres"
chapters_out.mkdir(parents=True, exist_ok=True)

for wav in sorted((INPUT_DIR / "chapitres").glob("*.wav")):
    mp3 = chapters_out / (wav.stem + ".mp3")
    print(f"  {wav.name} -> {mp3.name}...", end=" ", flush=True)
    wav_to_mp3(wav, mp3)
    print("OK")

# Fichier final
final_wav = INPUT_DIR / "Avant_les_mots.wav"
final_mp3 = OUTPUT_DIR / "Avant_les_mots.mp3"
print(f"\n  {final_wav.name} -> {final_mp3.name}...", end=" ", flush=True)
wav_to_mp3(final_wav, final_mp3)
print(f"OK ({final_mp3.stat().st_size // (1024*1024)} MB)")

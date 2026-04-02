#!/usr/bin/env python3
"""
Génère le livre audio français de "Avant les mots" via OpenAI TTS (voix onyx).

Usage:
    set OPENAI_API_KEY=sk-...
    python generer_audiobook_fr.py [-n NB_CHAPITRES]
"""

import argparse
import os
import re
import time
import wave as wave_mod
from pathlib import Path

from openai import OpenAI

# ── Configuration ──────────────────────────────────────────────

VOICE = "onyx"
MODEL = "tts-1-hd"
MAX_CHARS = 4000

# Durées de silence (secondes)
SILENCE_SCENE_BREAK = 1.2    # entre deux scènes (---)
SILENCE_BETWEEN_CHAPTERS = 3.0

CHAPITRES_DIR = Path("chapitres")
OUTPUT_DIR = Path("audiobook")
CHAPTERS_OUT = OUTPUT_DIR / "chapitres"
CHUNKS_OUT = OUTPUT_DIR / "chunks"

CHAPTERS = [
    (f"chapitre_{i:02d}.md", f"{i:02d}_chapitre_{i:02d}")
    for i in range(1, 20)
]


# ── Nettoyage du Markdown ──────────────────────────────────────

def clean_markdown(text: str) -> str:
    # Titre de chapitre : pause avant + après
    text = re.sub(
        r'^(#{1,6})\s+(.+)$',
        lambda m: f'\n<<TITRE:{len(m.group(1))}:{m.group(2)}>>',
        text, flags=re.MULTILINE
    )

    # Coupures de scène --- → marqueur silence
    text = re.sub(r'^---\s*$', '<<SCENE>>', text, flags=re.MULTILINE)

    # Italique/gras
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.+?)_{1,3}', r'\1', text)

    # Nettoyer sauts de ligne multiples
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# ── Découpage en chunks ────────────────────────────────────────

def parse_chunks(text: str, max_chars: int = MAX_CHARS) -> list[dict]:
    """Découpe le texte en chunks en respectant les marqueurs.

    Retourne une liste de dicts :
      {'text': str, 'silence_before': float}
    """
    # Séparer d'abord par les marqueurs spéciaux
    # On tokenize : liste de (type, contenu)
    tokens = []
    for part in re.split(r'(<<SCENE>>|<<TITRE:\d+:[^>]+>>)', text):
        part = part.strip()
        if not part:
            continue
        m_titre = re.match(r'<<TITRE:(\d+):(.+)>>', part)
        if m_titre:
            tokens.append(('titre', int(m_titre.group(1)), m_titre.group(2) + '.'))
        elif part == '<<SCENE>>':
            tokens.append(('scene',))
        else:
            tokens.append(('text', part))

    # Maintenant construire les chunks
    chunks = []
    current_text = ''
    current_silence = 0.0
    pending_silence = 0.0  # silence à insérer avant le prochain chunk

    def flush(silence_before):
        nonlocal current_text
        t = current_text.strip()
        if t:
            chunks.append({'text': t, 'silence_before': silence_before})
        current_text = ''

    for token in tokens:
        if token[0] == 'scene':
            # Pas de flush : juste un séparateur pour pause naturelle OpenAI
            if current_text.strip():
                current_text += '\n\n'

        elif token[0] == 'titre':
            level, title = token[1], token[2]
            # Couper avant le titre, puis le titre démarre le prochain chunk
            flush(pending_silence)
            silence_before = {1: 2.0, 2: 1.5}.get(level, 1.0)
            pending_silence = silence_before
            current_text = title + '\n\n'

        else:  # texte normal
            segment = token[1] + '\n\n'
            # Si ajouter ce segment dépasse la limite, couper
            if current_text and len(current_text) + len(segment) > max_chars:
                flush(pending_silence)
                pending_silence = 0.0
            current_text += segment

    flush(pending_silence)
    return chunks


# ── Génération TTS (OpenAI WAV) ────────────────────────────────

def generate_tts(client: OpenAI, text: str, output_path: Path) -> None:
    """Génère un WAV via OpenAI TTS."""
    padded = text + "\n\n\n . . . . . . . . . . . . . . . . . . . . . . . . . . . . . ."
    with client.audio.speech.with_streaming_response.create(
        model=MODEL,
        voice=VOICE,
        input=padded,
        response_format="wav",
    ) as response:
        response.stream_to_file(str(output_path))


# ── Utilitaires WAV ───────────────────────────────────────────

def get_wav_params(path: Path) -> tuple:
    with wave_mod.open(str(path), 'rb') as wf:
        return wf.getnchannels(), wf.getsampwidth(), wf.getframerate()


def make_silence_frames(channels: int, sampwidth: int, framerate: int, duration_s: float) -> bytes:
    n = int(framerate * duration_s)
    return b'\x00' * (n * channels * sampwidth)


def concatenate_wav_entries(entries: list[tuple[Path, float]], output_path: Path) -> None:
    """entries = [(chemin_wav, silence_avant_en_secondes), ...]"""
    channels, sampwidth, framerate = get_wav_params(entries[0][0])
    with wave_mod.open(str(output_path), 'wb') as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        for wav_path, silence_before in entries:
            if silence_before > 0:
                out.writeframes(make_silence_frames(channels, sampwidth, framerate, silence_before))
            with wave_mod.open(str(wav_path), 'rb') as wf:
                out.writeframes(wf.readframes(wf.getnframes()))


# ── Pipeline principal ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--max-chapters", type=int, default=None)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR : Definissez OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)

    OUTPUT_DIR.mkdir(exist_ok=True)
    CHAPTERS_OUT.mkdir(exist_ok=True)
    CHUNKS_OUT.mkdir(exist_ok=True)

    chapters_to_process = CHAPTERS[:args.max_chapters] if args.max_chapters else CHAPTERS
    chapter_entries: list[tuple[Path, float]] = []

    first_chapter = True

    for md_file, chapter_name in chapters_to_process:
        chapter_wav = CHAPTERS_OUT / f"{chapter_name}.wav"

        if chapter_wav.exists():
            print(f"  [OK] {chapter_name} existe deja, on passe")
            silence = SILENCE_BETWEEN_CHAPTERS if chapter_entries else 0.0
            chapter_entries.append((chapter_wav, silence))
            continue

        print(f"\n{'='*60}")
        print(f"  Chapitre : {chapter_name}")
        print(f"{'='*60}")

        md_path = CHAPITRES_DIR / md_file
        if not md_path.exists():
            print(f"  ERREUR : {md_file} introuvable")
            continue

        raw = md_path.read_text(encoding="utf-8")
        clean = clean_markdown(raw)
        chunks = parse_chunks(clean)

        # Préfixer le titre du livre au premier chunk du premier chapitre
        if first_chapter and chunks:
            chunks[0]['text'] = "Avant les mots.\n\n" + chunks[0]['text']
            chunks[0]['silence_before'] = 0.0
            first_chapter = False

        print(f"  {len(chunks)} morceaux")

        chunk_dir = CHUNKS_OUT / chapter_name
        chunk_dir.mkdir(exist_ok=True)

        chunk_entries: list[tuple[Path, float]] = []

        for i, chunk in enumerate(chunks):
            chunk_wav = chunk_dir / f"chunk_{i:03d}.wav"
            silence_before = chunk['silence_before']

            if chunk_wav.exists():
                print(f"    [OK] Chunk {i+1}/{len(chunks)} existe deja")
                chunk_entries.append((chunk_wav, silence_before))
                continue

            # Lire le .txt si édité manuellement
            chunk_txt = chunk_dir / f"chunk_{i:03d}.txt"
            if chunk_txt.exists():
                chunk_text = chunk_txt.read_text(encoding="utf-8")
            else:
                chunk_text = chunk['text']
                chunk_txt.write_text(chunk_text, encoding="utf-8")

            print(f"    > Chunk {i+1}/{len(chunks)} ({len(chunk_text)} chars, silence={silence_before}s)...", end=" ", flush=True)

            retries = 4
            for attempt in range(retries):
                try:
                    generate_tts(client, chunk_text, chunk_wav)
                    print("OK")
                    break
                except Exception as e:
                    if attempt < retries - 1:
                        wait = 5 * (attempt + 1)
                        print(f"\n      Retry dans {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"\n      ECHEC: {e}")
                        raise

            chunk_entries.append((chunk_wav, silence_before))

        print(f"  Fusion -> {chapter_name}.wav...")
        concatenate_wav_entries(chunk_entries, chapter_wav)
        silence = SILENCE_BETWEEN_CHAPTERS if chapter_entries else 0.0
        chapter_entries.append((chapter_wav, silence))
        print(f"  [OK] {chapter_name} termine")

    if chapter_entries:
        final = OUTPUT_DIR / "Avant_les_mots.wav"
        print(f"\n{'='*60}")
        print(f"  Fusion finale -> {final.name}")
        print(f"{'='*60}")
        concatenate_wav_entries(chapter_entries, final)
        print(f"\n  [OK] {final.name} - {final.stat().st_size // (1024*1024)} MB")


if __name__ == "__main__":
    main()

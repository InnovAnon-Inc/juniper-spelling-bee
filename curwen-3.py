#! /usr/bin/env python3

import os
import json
import subprocess

# ==========================================
# CONFIGURATION
# ==========================================
RAW_DIR = "raw_vocal_takes"       # Contains your spoken Title_01_C_Ionian.wav files
EXERCISES_DIR = "exercise_videos" # Contains generated exercise clips
OUTPUT_DIR = "modal_choir_videos" # Final output folder for full videos
TEMP_DIR = "processed_slices"     # Temporary storage for title video cards
MANIFEST_FILE = "modes_manifest.json"

FPS = 30
WIDTH = 1920
HEIGHT = 1080
SAMPLE_RATE = 44100

for d in [TEMP_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ==========================================
# HELPER: CONVERT SPOKEN WAV TO BLACK TITLE VIDEO
# ==========================================
def wav_to_blank_video(wav_filename: str) -> str:
    """
    Takes a raw spoken title .wav file and pairs it with a blank black 1080p canvas.
    Applies audio envelope fades so title intros/outros enter and leave smoothly.
    """
    wav_path = os.path.join(RAW_DIR, wav_filename)
    base_name = os.path.splitext(wav_filename)[0]
    output_mp4 = os.path.join(TEMP_DIR, f"{base_name}_card.mp4")

    if not os.path.exists(wav_path):
        return ""

    # Generate black video canvas matching exact audio duration with a 50ms fade-in / 150ms fade-out
    filter_complex = (
        f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}[v];"
        f"[0:a]afade=t=in:ss=0:d=0.05,afade=t=out:st=0.85:d=0.15,aresample={SAMPLE_RATE}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_mp4

# ==========================================
# HELPER: STITCH PREFIX + EXERCISE + SUFFIX
# ==========================================
def assemble_full_video(prefix_file: str, exercise_file: str, suffix_file: str, output_name: str):
    """
    Concatenates [Title Intro Card] -> [Exercise Video] -> [Title Outro Card].
    """
    list_file_path = os.path.join(TEMP_DIR, "modal_concat_list.txt")
    clips = [prefix_file, exercise_file, suffix_file]

    with open(list_file_path, "w") as f:
        for clip in clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    output_path = os.path.join(OUTPUT_DIR, output_name)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# ==========================================
# MAIN EXECUTION ROUTINE
# ==========================================
def main():
    print("==========================================================================")
    print(" MODAL CHOIR VIDEO PIPELINE: PREFIX & SUFFIX TITLE STITCHER")
    print("==========================================================================\n")

    if not os.path.exists(MANIFEST_FILE):
        print(f"ERROR: '{MANIFEST_FILE}' not found. Please run the manifest generator first.")
        return

    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)

    exercise_types = ["Full_Scale", "Leaps", "Three_Notes", "Diatonic_7th_Arpeggios"]
    completed_count = 0

    for slug, mode_info in manifest.items():
        spoken_wav_name = f"Title_{mode_info['id']:02d}_{slug}.wav"
        spoken_wav_path = os.path.join(RAW_DIR, spoken_wav_name)

        if not os.path.exists(spoken_wav_path):
            print(f"[-] Missing spoken title WAV: '{spoken_wav_name}'. Skipping {mode_info['full_key_name']}.")
            continue

        print(f"[+] Creating blank video title card for: {mode_info['full_key_name']}...")
        title_card_path = wav_to_blank_video(spoken_wav_name)

        if not title_card_path:
            continue

        # Process each exercise pattern for this mode
        for ex_type in exercise_types:
            exercise_video_name = f"{slug}_{ex_type}.mp4"
            exercise_video_path = os.path.join(EXERCISES_DIR, exercise_video_name)

            if os.path.exists(exercise_video_path):
                final_output_name = f"{mode_info['id']:02d}_{slug}_{ex_type}_FULL.mp4"
                print(f"  -> Stitching Prefix + {ex_type} + Suffix -> {final_output_name}")

                # Using title card as both Prefix (intro) and Suffix (outro anchor)
                assemble_full_video(
                    prefix_file=title_card_path,
                    exercise_file=exercise_video_path,
                    suffix_file=title_card_path,
                    output_name=final_output_name
                )
                completed_count += 1
            else:
                print(f"  [!] Note: Exercise video '{exercise_video_name}' not found in '{EXERCISES_DIR}/'.")

    print(f"\n==========================================================================")
    print(f"[COMPLETE] Assembled {completed_count} final modal choir videos into '{OUTPUT_DIR}/'.")
    print(f"==========================================================================")

if __name__ == "__main__":
    main()

#! /usr/bin/env python3

import os
import json
import math
import struct
import subprocess
import wave

# ==========================================
# CONFIGURATION & DIRECTORY SETUP
# ==========================================
RAW_DIR = "raw_vocal_takes"                          # Directory for .mp4 note takes & Title_XX_.wav takes
TEMP_DIR = "processed_slices"                        # Intermediate cut slices and title cards
OUTPUT_DIR = "../storage/downloads/exercise_videos"  # Final stitched videos
CONFIG_FILE = "onset_offsets.json"
MANIFEST_FILE = "modes_manifest.json"

BPM = 60
TARGET_DUR = 60.0 / BPM  # 1.0 Second per beat
FPS = 30
WIDTH = 1920
HEIGHT = 1080
SAMPLE_RATE = 44100

WINDOW_MS = 20
THRESHOLD_RATIO = 4.0

PITCH_MAP = {
    0: "C4",  1: "Db4", 2: "D4",  3: "Eb4", 
    4: "E4",  5: "F4",  6: "F#4", 7: "G4", 
    8: "Ab4", 9: "A4", 10: "Bb4", 11: "B4", 12: "C5"
}

for d in [TEMP_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ==========================================
# HELPER: ACCURATE AUDIO DURATION PROBER
# ==========================================
def get_media_duration(file_path: str) -> float:
    """Gets exact duration of an audio/video file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())

# ==========================================
# 1. RMS ATTACK ONSET DETECTOR & CONFIG
# ==========================================
def extract_temp_wav(mp4_path: str) -> str:
    wav_path = os.path.join(TEMP_DIR, "temp_analysis.wav")
    cmd = [
        "ffmpeg", "-y", "-i", mp4_path,
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le", wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path

def detect_attack_offset(mp4_path: str) -> float:
    wav_path = extract_temp_wav(mp4_path)
    with wave.open(wav_path, 'rb') as wf:
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw_bytes)
        
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    if not samples:
        return 0.0

    window_size = int(SAMPLE_RATE * (WINDOW_MS / 1000.0))
    baseline_samples = samples[:int(SAMPLE_RATE * 0.1)]
    baseline_rms = math.sqrt(sum(s * s for s in baseline_samples) / len(baseline_samples)) if baseline_samples else 100.0
    baseline_rms = max(baseline_rms, 50.0)
    target_threshold = baseline_rms * THRESHOLD_RATIO

    for i in range(0, len(samples) - window_size, window_size // 2):
        window = samples[i:i + window_size]
        rms = math.sqrt(sum(s * s for s in window) / len(window))
        if rms >= target_threshold:
            return round(i / float(SAMPLE_RATE), 3)

    return 0.0

def load_or_create_config() -> dict[str, float]:
    offsets = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                offsets = json.load(f)
                print(f"[CONFIG] Loaded attack offsets from '{CONFIG_FILE}'")
            except json.JSONDecodeError:
                print(f"[CONFIG] Warning: Could not parse '{CONFIG_FILE}'. Rebuilding.")

    updated = False
    clip_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.mp4', '.mov'))]

    for clip in sorted(clip_files):
        if clip not in offsets:
            print(f"[RMS ANALYZER] Calculating onset for: {clip}...")
            clip_path = os.path.join(RAW_DIR, clip)
            detected_offset = detect_attack_offset(clip_path)
            offsets[clip] = detected_offset
            print(f"  -> Onset: {detected_offset:.3f}s")
            updated = True

    if updated or not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(offsets, f, indent=4)
        print(f"[CONFIG] Saved offsets to '{CONFIG_FILE}'\n")

    return offsets

# ==========================================
# 2. SLICE & TITLE CARD RENDERING
# ==========================================
def process_clip_to_grid(note_file: str, offset_sec: float) -> str:
    """Trims note take at onset, shapes audio envelope, standardizes to 1.0s."""
    input_path = os.path.join(RAW_DIR, note_file)
    output_slice = os.path.join(TEMP_DIR, f"slice_{note_file}")

    filter_complex = (
        f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={FPS},tpad=stop_duration=1.0:stop_mode=clone,trim=duration={TARGET_DUR},setpts=PTS-STARTPTS[v];"
        f"[0:a]apad=pad_dur=1.0,atrim=duration={TARGET_DUR},"
        f"afade=t=in:ss=0:d=0.05,afade=t=out:st=0.85:d=0.15,aresample={SAMPLE_RATE}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(offset_sec),
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        output_slice
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_slice

def wav_to_blank_video(wav_filename: str) -> str:
    """Converts a spoken title WAV into a black 1080p video card matching full duration."""
    wav_path = os.path.join(RAW_DIR, wav_filename)
    base_name = os.path.splitext(wav_filename)[0]
    output_mp4 = os.path.join(TEMP_DIR, f"{base_name}_card.mp4")

    if not os.path.exists(wav_path):
        return ""

    # Measure real WAV duration so the black canvas doesn't truncate prematurely
    duration = get_media_duration(wav_path)

    filter_complex = (
        f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration}[v];"
        f"[0:a]afade=t=in:ss=0:d=0.05,afade=t=out:st={max(0, duration - 0.15):.2f}:d=0.15,aresample={SAMPLE_RATE}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_mp4

# ==========================================
# 3. EXERCISE PATTERN GENERATOR & STITCHER
# ==========================================
def concatenate_video_list(clip_paths: list[str], output_filename: str):
    """Concatenates title and exercise slices with full audio/video re-encoding."""
    list_file_path = os.path.join(TEMP_DIR, f"concat_{output_filename}.txt")
    with open(list_file_path, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # Re-encoding during concat ensures smooth audio/video binding without dropped streams
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file_path,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(list_file_path):
        os.remove(list_file_path)

def generate_exercise_sequences(pitch_classes: list[int], slice_map: dict[str, str]) -> dict[str, list[str]]:
    scale_files = [f"{PITCH_MAP[pc]}.mp4" for pc in pitch_classes]
    scale_files.append(f"{PITCH_MAP[12]}.mp4")  # Top octave C5

    scale_slices = []
    for f in scale_files:
        if f in slice_map:
            scale_slices.append(slice_map[f])
        else:
            return {}

    patterns = {}
    patterns["Full_Scale"] = scale_slices + list(reversed(scale_slices[:-1]))
    
    three_notes = []
    for i in range(len(scale_slices) - 2):
        three_notes.extend([scale_slices[i], scale_slices[i+1], scale_slices[i+2]])
    patterns["Three_Notes"] = three_notes
    
    if len(scale_slices) >= 8:
        patterns["Diatonic_7th_Arpeggios"] = [scale_slices[0], scale_slices[2], scale_slices[4], scale_slices[6], scale_slices[7]]

    return patterns

# ==========================================
# MASTER RUNNER
# ==========================================
def main():
    print("==========================================================================")
    print(" UNIFIED MODAL CHOIR PIPELINE (ACCURATE TIMING & AUDIO FIX)")
    print("==========================================================================\n")

    if not os.path.exists(MANIFEST_FILE):
        print(f"ERROR: '{MANIFEST_FILE}' missing. Please generate the manifest first.")
        return

    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)

    offsets_dict = load_or_create_config()

    print("[1/3] Pre-processing raw pitch takes into 60 BPM envelope slices...")
    slice_map = {}
    for note_file, offset in offsets_dict.items():
        raw_path = os.path.join(RAW_DIR, note_file)
        if os.path.exists(raw_path):
            slice_path = process_clip_to_grid(note_file, offset)
            slice_map[note_file] = slice_path
            
    print(f"  -> {len(slice_map)} pitch takes slice-ready.\n")

    print("[2/3] Processing Modes, Building Exercises, and Stitching Videos...")
    total_rendered = 0

    for slug, mode_info in manifest.items():
        mode_id = mode_info['id']
        spoken_wav_name = f"Title_{mode_id:02d}_{slug}.wav"
        spoken_wav_path = os.path.join(RAW_DIR, spoken_wav_name)

        if not os.path.exists(spoken_wav_path):
            print(f"[-] Skipping Mode {mode_id:02d} ({mode_info['full_key_name']}): Spoken WAV missing.")
            continue

        title_card = wav_to_blank_video(spoken_wav_name)
        if not title_card:
            continue

        exercise_patterns = generate_exercise_sequences(mode_info['pitch_classes'], slice_map)

        for ex_name, pattern_slices in exercise_patterns.items():
            final_filename = f"{mode_id:02d}_{slug}_{ex_name}_FULL.mp4"
            print(f"  [+] Rendering: {final_filename}")

            full_sequence = [title_card] + pattern_slices + [title_card]
            concatenate_video_list(full_sequence, final_filename)
            total_rendered += 1

    print("\n==========================================================================")
    print(f"[COMPLETE] Rendered {total_rendered} full exercise videos to '{OUTPUT_DIR}/'.")
    print("==========================================================================")

if __name__ == "__main__":
    main()

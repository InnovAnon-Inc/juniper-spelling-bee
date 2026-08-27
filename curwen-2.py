#! /usr/bin/env python3

import os
import json
import math
import struct
import subprocess
import wave

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_CLIPS_DIR = "raw_vocal_takes"
TEMP_DIR = "processed_slices"
OUTPUT_DIR = "../storage/downloads/exercise_videos"
CONFIG_FILE = "onset_offsets.json"

BPM = 60
TARGET_DUR = 60.0 / BPM  # 1.0 Second per beat
FPS = 30
SAMPLE_RATE = 44100

# RMS Onset Detection Parameters
WINDOW_MS = 20          # 20ms sliding window for RMS energy calculation
THRESHOLD_RATIO = 4.0   # Onset is triggered when RMS exceeds 4x baseline room noise

# Setup directories
for d in [TEMP_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ==========================================
# WAV RMS ONSET DETECTOR
# ==========================================
def extract_temp_wav(mp4_path: str) -> str:
    """Extracts a temporary 16-bit 44.1kHz mono WAV for audio analysis."""
    wav_path = os.path.join(TEMP_DIR, "temp_analysis.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", mp4_path,
        "-vn",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path

def detect_attack_offset(mp4_path: str) -> float:
    """
    Calculates the onset timestamp (in seconds) by computing sliding RMS energy.
    Sets baseline noise floor from the first 100ms and detects attack entry.
    """
    wav_path = extract_temp_wav(mp4_path)
    
    with wave.open(wav_path, 'rb') as wf:
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)
        samples = struct.unpack(f"{n_frames}h", raw_bytes)
        
    os.remove(wav_path)
    if not samples:
        return 0.0

    window_size = int(SAMPLE_RATE * (WINDOW_MS / 1000.0))
    
    # 1. Calculate baseline room noise from first 100ms
    baseline_samples = samples[:int(SAMPLE_RATE * 0.1)]
    if baseline_samples:
        baseline_rms = math.sqrt(sum(s * s for s in baseline_samples) / len(baseline_samples))
    else:
        baseline_rms = 100.0

    # Ensure min floor threshold to avoid division by near-zero room silence
    baseline_rms = max(baseline_rms, 50.0)
    target_threshold = baseline_rms * THRESHOLD_RATIO

    # 2. Slide window forward to locate attack
    for i in range(0, len(samples) - window_size, window_size // 2):
        window = samples[i:i + window_size]
        rms = math.sqrt(sum(s * s for s in window) / len(window))
        
        if rms >= target_threshold:
            # Found attack entry point
            offset_sec = i / float(SAMPLE_RATE)
            return round(offset_sec, 3)

    return 0.0

# ==========================================
# CONFIG MANAGEMENT
# ==========================================
def load_or_create_config() -> dict[str, float]:
    """Loads existing onset_offsets.json, or creates/populates it with computed RMS values."""
    offsets = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                offsets = json.load(f)
                print(f"[CONFIG] Loaded existing offsets from '{CONFIG_FILE}'")
            except json.JSONDecodeError:
                print(f"[CONFIG] Warning: Could not parse '{CONFIG_FILE}'. Regenerating.")

    updated = False
    clip_files = [f for f in os.listdir(INPUT_CLIPS_DIR) if f.lower().endswith(('.mp4', '.mov'))]

    for clip in sorted(clip_files):
        if clip not in offsets:
            print(f"[RMS ANALYZER] Calculating attack onset for: {clip}...")
            clip_path = os.path.join(INPUT_CLIPS_DIR, clip)
            detected_offset = detect_attack_offset(clip_path)
            offsets[clip] = detected_offset
            print(f"  -> Detected Attack Onset: {detected_offset:.3f}s")
            updated = True

    if updated or not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(offsets, f, indent=4)
        print(f"[CONFIG] Saved updated offsets to '{CONFIG_FILE}'\n")

    return offsets

# ==========================================
# PROCESSING SLICES WITH ATTACK ALIGNMENT
# ==========================================
def process_clip_to_grid(note_file: str, offset_sec: float) -> str:
    """
    Trims raw clip starting exact at the onset timestamp, pads to 1.0s,
    and applies smooth 50ms fade-in / 150ms fade-out audio/video envelope.
    """
    input_path = os.path.join(INPUT_CLIPS_DIR, note_file)
    output_slice = os.path.join(TEMP_DIR, f"slice_{note_file}")

    filter_complex = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
        f"fps={FPS},tpad=stop_duration=1.0:stop_mode=clone,trim=duration={TARGET_DUR},setpts=PTS-STARTPTS[v];"
        f"[0:a]apad=pad_dur=1.0,atrim=duration={TARGET_DUR},"
        f"afade=t=in:ss=0:d=0.05,afade=t=out:st=0.85:d=0.15,aresample={SAMPLE_RATE}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(offset_sec), # Fast seek directly to attack onset
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        output_slice
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_slice

def concatenate_sequence(slice_files: list[str], output_filename: str):
    list_file_path = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(list_file_path, "w") as f:
        for sf in slice_files:
            f.write(f"file '{os.path.abspath(sf)}'\n")

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file_path,
        "-c", "copy",
        output_path
    ]

    print(f"  -> Concatenating final video: {output_filename}...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# ==========================================
# MAIN EXECUTION ROUTINE
# ==========================================
def main():
    print("==========================================================================")
    print(" VOCAL/SIGN ATTACK ALIGNER & EXERCISE BUILDER (60 BPM)")
    print("==========================================================================\n")

    if not os.path.exists(INPUT_CLIPS_DIR):
        print(f"ERROR: Input directory '{INPUT_CLIPS_DIR}' missing. Please create it and add raw .mp4 takes.")
        return

    # 1. Populate/read the config dictionary with calculated RMS values
    offsets_dict = load_or_create_config()

    # 2. Example scale sequence mapping to your available raw files
    example_scale_notes = ["C4.mp4", "D4.mp4", "E4.mp4", "F4.mp4", "G4.mp4", "A4.mp4", "B4.mp4", "C5.mp4"]
    
    processed_slices = []
    for note_file in example_scale_notes:
        if note_file in offsets_dict and os.path.exists(os.path.join(INPUT_CLIPS_DIR, note_file)):
            offset = offsets_dict[note_file]
            print(f"Processing {note_file:<10} | Seeking to Attack Onset: {offset:.3f}s")
            slice_path = process_clip_to_grid(note_file, offset)
            processed_slices.append(slice_path)
        else:
            print(f"Skipping {note_file} (file missing from '{INPUT_CLIPS_DIR}')")

    # 3. Build example aligned exercise video
    if processed_slices:
        full_pattern = processed_slices + list(reversed(processed_slices[:-1]))
        concatenate_sequence(full_pattern, "C_Major_Aligned_Exercise.mp4")
        print("\n[COMPLETE] Successfully generated attack-aligned video exercise!")

if __name__ == "__main__":
    main()

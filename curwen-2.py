#! /usr/bin/env python3

import os
import subprocess

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_CLIPS_DIR = "raw_vocal_takes"   # Directory with your Bb3.mp4, C4.mp4, etc.
TEMP_DIR = "processed_slices"
OUTPUT_DIR = "exercise_videos"
BPM = 60
TARGET_DUR = 60.0 / BPM               # 1.0 Second per note

# Standardize output video settings
FPS = 30
SAMPLE_RATE = 44100

# Setup directories
for d in [TEMP_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ==========================================
# PROCESSING A SINGLE NOTE CLIP TO 1.0s GRID
# ==========================================
def process_clip_to_grid(note_file: str) -> str:
    """
    Takes a raw note clip (e.g., C4.mp4), trims audio/video to exact 1.0s,
    applies a fade-in/fade-out envelope to prevent clicks, and standardizes format.
    """
    input_path = os.path.join(INPUT_CLIPS_DIR, note_file)
    output_slice = os.path.join(TEMP_DIR, f"slice_{note_file}")

    # FFmpeg Filtergraph:
    # 1. Trim/pad video to exactly 1.0s, set FPS to 30, scale to standard 1080p
    # 2. Apply audio fade-in (0.05s) and fade-out (0.15s) starting at 0.85s to shape the attack/decay
    filter_complex = (
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
        f"fps={FPS},tpad=stop_duration=1.0:stop_mode=clone,trim=duration={TARGET_DUR},setpts=PTS-STARTPTS[v];"
        f"[0:a]apad=pad_dur=1.0,atrim=duration={TARGET_DUR},"
        f"afade=t=in:ss=0:d=0.05,afade=t=out:st=0.85:d=0.15,aresample={SAMPLE_RATE}[a]"
    )

    cmd = [
        "ffmpeg", "-y",
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

# ==========================================
# SPLICING SLICES INTO FULL EXERCISES
# ==========================================
def concatenate_sequence(slice_files: list[str], output_filename: str):
    """
    Stitches processed 1.0s slices into a continuous exercise video file.
    """
    list_file_path = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(list_file_path, "w") as f:
        for sf in slice_files:
            # Absolute paths for ffmpeg concat demuxer
            f.write(f"file '{os.path.abspath(sf)}'\n")

    output_path = os.path.join(OUTPUT_DIR, output_filename)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file_path,
        "-c", "copy",
        output_path
    ]

    print(f"  -> Rendering exercise video: {output_filename}...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# ==========================================
# EXAMPLE ROUTINE: BUILDING A C MAJOR SCALE VIDEO
# ==========================================
def main():
    print("==========================================================================")
    print(" PROCESSING RAW VOCAL TAKES INTO 60 BPM SYNCHRONIZED EXERCISES")
    print("==========================================================================\n")

    # Example sequence of available files matching notes
    c_major_scale_notes = [
        "C4.mp4", "D4.mp4", "E4.mp4", "F4.mp4",
        "G4.mp4", "A4.mp4", "B4.mp4", "C5.mp4"
    ]

    # 1. Process each individual note clip into a clean 1.0s envelope-shaped slice
    processed_slices = []
    for note_file in c_major_scale_notes:
        if os.path.exists(os.path.join(INPUT_CLIPS_DIR, note_file)):
            print(f"Normalizing & Enveloping: {note_file}")
            slice_path = process_clip_to_grid(note_file)
            processed_slices.append(slice_path)
        else:
            print(f"WARNING: File {note_file} not found in {INPUT_CLIPS_DIR}/. Skipping.")

    # 2. Build Ascending + Descending Full Scale Video
    if processed_slices:
        full_pattern = processed_slices + list(reversed(processed_slices[:-1]))
        concatenate_sequence(full_pattern, "C_Major_Full_Scale_Exercise.mp4")
        print("\n[SUCCESS] Render complete!")

if __name__ == "__main__":
    main()

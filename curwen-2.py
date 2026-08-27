#! /usr/bin/env python3

import json
import os

# ==========================================
# 12-EDO PARENT SCALE DEFINITIONS
# ==========================================
PARENT_SCALES = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor": [0, 2, 3, 5, 7, 9, 11],
    "Harmonic Major": [0, 2, 4, 5, 7, 8, 11],
    "Double Harmonic Major": [0, 1, 4, 5, 7, 8, 11],
    "Neapolitan Major": [0, 1, 3, 5, 7, 9, 11],
    "Neapolitan Minor": [0, 1, 3, 5, 7, 8, 11],
}

# Systematic Naming for All 49 Modes
MODE_NAMES = {
    "Major": [
        "Ionian",
        "Dorian",
        "Phrygian",
        "Lydian",
        "Mixolydian",
        "Aeolian",
        "Locrian"
    ],
    "Harmonic Minor": [
        "Harmonic Minor",
        "Locrian Natural 6",
        "Ionian Sharp 5",
        "Dorian Sharp 4",
        "Phrygian Dominant",
        "Lydian Sharp 2",
        "Super Locrian Double Flat 7"
    ],
    "Melodic Minor": [
        "Melodic Minor",
        "Dorian Flat 2",
        "Lydian Augmented",
        "Lydian Dominant",
        "Mixolydian Flat 6",
        "Half-Diminished",
        "Altered Scale"
    ],
    "Harmonic Major": [
        "Harmonic Major",
        "Dorian Flat 5",
        "Phrygian Flat 4",
        "Lydian Flat 3",
        "Mixolydian Flat 2",
        "Lydian Augmented Sharp 2",
        "Locrian Double Flat 7"
    ],
    "Double Harmonic Major": [
        "Double Harmonic Major",
        "Lydian Sharp 2 Sharp 6",
        "Ultra Phrygian",
        "Hungarian Minor",
        "Harmonic Minor Flat 5",
        "Ionian Sharp 2 Sharp 5",
        "Locrian Double Flat 3 Double Flat 7"
    ],
    "Neapolitan Major": [
        "Neapolitan Major",
        "Lydian Sharp 6",
        "Major Augmented Sharp 5",
        "Lydian Dominant Flat 6",
        "Major Locrian",
        "Half-Diminished Flat 4",
        "Altered Dominant Double Flat 3"
    ],
    "Neapolitan Minor": [
        "Neapolitan Minor",
        "Lydian Sharp 6 Sharp 3",
        "Major Sharp 5",
        "Hungarian Gypsy",
        "Locrian Major",
        "Ionian Sharp 2",
        "Ultra Locrian"
    ]
}

# Reference Major Scale Intervals for Alteration Mapping
MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]

# Fixed-Do Solfège Lookup Dictionary
EXACT_SOLFEGE = {
    (1,  0): "Do",
    (2, -1): "Ra",  (2, 0): "Re",  (2, 1): "Ri",
    (3, -2): "Rri", (3, -1): "Me",  (3, 0): "Mi",
    (4, -1): "Fe",  (4, 0): "Fa",  (4, 1): "Fi",
    (5, -1): "Se",  (5, 0): "So",  (5, 1): "Si",
    (6, -2): "Leh", (6, -1): "Le",  (6, 0): "La",
    (7, -2): "Tas", (7, -1): "Te",  (7, 0): "Ti"
}

# Pitch Class Names for Parallel C Output
PITCH_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# ==========================================
# SOLFEGE & SCALE CALCULATOR
# ==========================================
def compute_mode_details(parent_name: str, mode_deg: int, root_midi: int = 60):
    parent_pcs = PARENT_SCALES[parent_name]
    num_notes = len(parent_pcs)
    mode_offset = parent_pcs[mode_deg - 1]

    solfege_spelling = []
    pitch_classes = []
    midi_notes = []

    for i in range(num_notes):
        degree = i + 1
        parent_idx = (i + mode_deg - 1) % num_notes
        
        semitones_from_tonic = (parent_pcs[parent_idx] - mode_offset) % 12
        pitch_classes.append(semitones_from_tonic)
        midi_notes.append(root_midi + semitones_from_tonic)

        expected_semitones = MAJOR_INTERVALS[i]
        alteration = semitones_from_tonic - expected_semitones
        
        if alteration > 6:
            alteration -= 12
        if alteration < -6:
            alteration += 12

        syllable = EXACT_SOLFEGE.get((degree, alteration), f"Deg{degree}({alteration})")
        solfege_spelling.append(syllable)

    solfege_spelling.append("Do'")  # Top octave tonic
    midi_notes.append(root_midi + 12)

    return pitch_classes, midi_notes, solfege_spelling

# ==========================================
# MANIFEST BUILDER
# ==========================================
def build_49_modes_manifest():
    manifest = {}
    mode_counter = 1

    print("==========================================================================")
    print(" COMPREHENSIVE 49 MODES OF 12-EDO (PARALLEL C REFERENCE)")
    print("==========================================================================\n")

    for family_name, modes in MODE_NAMES.items():
        print(f"--- PARENT FAMILY: {family_name.upper()} ---")
        
        for deg, mode_name in enumerate(modes, start=1):
            pcs, midis, solfege = compute_mode_details(family_name, deg)
            
            # Formatting file slugs and spoken script names
            slug = f"C_{mode_name.replace(' ', '_')}"
            title_video_filename = f"Title_{mode_counter:02d}_{slug}.mp4"
            spoken_title = f"C {mode_name}, Mode {deg} of {family_name}"
            
            mode_data = {
                "id": mode_counter,
                "parent_family": family_name,
                "mode_degree": deg,
                "mode_name": mode_name,
                "full_key_name": f"C {mode_name}",
                "spoken_title_text": spoken_title,
                "title_video_file": title_video_filename,
                "file_slug": slug,
                "pitch_classes": pcs,
                "midi_notes": midis,
                "solfege_spelling": solfege,
                "solfege_string": " - ".join(solfege)
            }
            
            manifest[slug] = mode_data
            
            print(f"[{mode_counter:02d}] {spoken_title:<60}")
            print(f"     Solfège: {mode_data['solfege_string']}")
            print(f"     Title Clip Needed: {title_video_filename}\n")
            
            mode_counter += 1

    # Save to JSON manifest for automated pipeline stitching
    manifest_file = "modes_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=4)
        
    print(f"==========================================================================")
    print(f"[COMPLETE] Saved full 49-mode manifest to '{manifest_file}'")
    print(f"==========================================================================")

if __name__ == "__main__":
    build_49_modes_manifest()

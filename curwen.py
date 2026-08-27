#! /usr/bin/env python3

import os
import math
import struct
import wave

# ==========================================
# CONFIGURATION & METRICS
# ==========================================
OUTPUT_DIR = "../storage/downloads/output_warmups"
BPM = 60
TICK_DURATION = 60.0 / BPM     # 1.0 second per note
SAMPLE_RATE = 44100            # Standard WAV Sample Rate
A4_FREQ = 432.0                # Master Reference Pitch

def midi_to_freq(midi_note: int) -> float:
    # A4 (MIDI 69) = 432.0 Hz
    return A4_FREQ * (2.0 ** ((midi_note - 69) / 12.0))

# ==========================================
# DIATONIC SOLFEGE & MODAL DEFINITIONS
# ==========================================
MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]

EXACT_SOLFEGE = {
    (1,  0): "Do",
    (2, -1): "Ra", (2, 0): "Re", (2, 1): "Ri",
    (3, -2): "Rri", (3, -1): "Me", (3, 0): "Mi",
    (4, -1): "Fe", (4, 0): "Fa", (4, 1): "Fi",
    (5, -1): "Se", (5, 0): "So", (5, 1): "Si",
    (6, -2): "Leh", (6, -1): "Le", (6, 0): "La",
    (7, -2): "Tas", (7, -1): "Te", (7, 0): "Ti"
}

PARENT_FAMILIES = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor": [0, 2, 3, 5, 7, 9, 11],
    "Harmonic Major": [0, 2, 4, 5, 7, 8, 11],
    "Double Harmonic Major": [0, 1, 4, 5, 7, 8, 11],
    "Neapolitan Major": [0, 1, 3, 5, 7, 9, 11],
    "Neapolitan Minor": [0, 1, 3, 5, 7, 8, 11],
}

MODE_NAMES = {
    "Major": ["Ionian", "Dorian", "Phrygian", "Lydian", "Mixolydian", "Aeolian", "Locrian"],
    "Harmonic Minor": ["Harmonic Minor", "Locrian Natural 6", "Ionian Sharp 5", "Dorian Sharp 4", "Phrygian Dominant", "Lydian Sharp 2", "Super Locrian Double Flat 7"],
    "Melodic Minor": ["Melodic Minor", "Dorian Flat 2", "Lydian Augmented", "Lydian Dominant", "Mixolydian Flat 6", "Half-Diminished", "Altered Scale"],
    "Harmonic Major": ["Harmonic Major", "Dorian Flat 5", "Phrygian Flat 4", "Lydian Flat 3", "Mixolydian Flat 2", "Lydian Augmented Sharp 2", "Locrian Double Flat 7"],
    "Double Harmonic Major": ["Double Harmonic Major", "Lydian Sharp 2 Sharp 6", "Ultra Phrygian", "Hungarian Minor", "Harmonic Minor Flat 5", "Ionian Sharp 2 Sharp 5", "Locrian Double Flat 3 Double Flat 7"],
    "Neapolitan Major": ["Neapolitan Major", "Lydian Sharp 6", "Major Augmented Sharp 5", "Lydian Dominant Flat 6", "Major Locrian", "Half-Diminished Flat 4", "Altered Dominant Double Flat 3"],
    "Neapolitan Minor": ["Neapolitan Minor", "Lydian Sharp 6 Sharp 3", "Major Sharp 5", "Hungarian Gypsy", "Locrian Major", "Ionian Sharp 2", "Ultra Locrian"]
}

CHORD_PROGRESSION_ORDER = [0, 4, 3, 5, 2, 1, 6]

def get_exact_modal_solfege(parent_name: str, mode_degree: int) -> list[str]:
    parent_pcs = PARENT_FAMILIES[parent_name]
    num_notes = len(parent_pcs)
    mode_offset = parent_pcs[mode_degree - 1]

    solfege_spelling = []
    for i in range(num_notes):
        degree = i + 1
        parent_idx = (i + mode_degree - 1) % num_notes
        actual_semitones = (parent_pcs[parent_idx] - mode_offset) % 12
        expected_semitones = MAJOR_INTERVALS[i]

        alteration = actual_semitones - expected_semitones
        if alteration > 6: alteration -= 12
        if alteration < -6: alteration += 12

        s_syllable = EXACT_SOLFEGE.get((degree, alteration), f"Deg{degree}({alteration})")
        solfege_spelling.append(s_syllable)

    solfege_spelling.append("Do'") # Octave tonic
    return solfege_spelling

def get_parallel_mode_midis(parent_name: str, mode_degree: int, tonic_midi: int = 60) -> list[int]:
    scale = PARENT_FAMILIES[parent_name]
    num_notes = len(scale)
    mode_offset = scale[mode_degree - 1]

    midis = []
    for i in range(num_notes):
        parent_idx = (i + mode_degree - 1) % num_notes
        interval = (scale[parent_idx] - mode_offset) % 12
        midis.append(tonic_midi + interval)

    midis.append(tonic_midi + 12)
    return midis

# ==========================================
# COMBINED PATTERN BUILDERS
# ==========================================
def build_combined_scale(midis: list[int], solfege: list[str]):
    # Ascending then Descending
    up = list(zip(midis, solfege))
    down = list(zip(reversed(midis[:-1]), reversed(solfege[:-1])))
    return up + down

def build_combined_leaps(midis: list[int], solfege: list[str]):
    """
    Leaps Up & Down seamlessly without duplicating top note.
    Ascending: Up 3rd, Down Step (Do - Mi, Re - Fa, Mi - So...)
    Turn: ... So - Ti - La - Do' - Ti - Re' - Ti - Do' ...
    Descending: Down 3rd, Up Step (... Do' - La, Ti - So, La - Fa ... Do)
    """
    sequence = []
    n = len(midis) - 1 # 7 steps

    # Ascending leaps
    for i in range(n - 1):
        sequence.append((midis[i], solfege[i]))
        sequence.append((midis[i+2], solfege[i+2]))

    # Over-shoot turn at the top (... Ti - Do' - La - Ti - So ...)
    # midis[-2] = 7th (Ti), midis[-1] = Octave (Do')
    sequence.append((midis[-2], solfege[-2]))
    sequence.append((midis[-1], solfege[-1]))

    # Descending leaps
    rev_m = list(reversed(midis))
    rev_s = list(reversed(solfege))

    for i in range(1, n - 1):
        sequence.append((rev_m[i-1], rev_s[i-1]))
        sequence.append((rev_m[i+1], rev_s[i+1]))

    # Final grounding step to tonic
    sequence.append((rev_m[-2], rev_s[-2]))
    sequence.append((rev_m[-1], rev_s[-1]))

    return sequence

def build_combined_three_notes(midis: list[int], solfege: list[str]):
    # 3 notes up, 3 notes down (Do-Re-Mi, Re-Mi-Fa ... Fa-Mi-Re, Mi-Re-Do)
    sequence = []
    n = len(midis) - 1

    # Ascending 3-note groups
    for i in range(n - 1):
        sequence.append((midis[i], solfege[i]))
        sequence.append((midis[i+1], solfege[i+1]))
        sequence.append((midis[i+2], solfege[i+2]))

    # Descending 3-note groups
    rev_m = list(reversed(midis))
    rev_s = list(reversed(solfege))

    for i in range(n - 1):
        sequence.append((rev_m[i], rev_s[i]))
        sequence.append((rev_m[i+1], rev_s[i+1]))
        sequence.append((rev_m[i+2], rev_s[i+2]))

    return sequence

def build_chord_arpeggios(midis: list[int], solfege: list[str]):
    # I-V-IV-VI-III-II-VII 7th Chords (Arpeggiated Up and Down)
    extended_midis = midis[:-1] + [m + 12 for m in midis]
    extended_solfege = solfege[:-1] + [s + "'" for s in solfege]

    sequence = []
    for deg_idx in CHORD_PROGRESSION_ORDER:
        chord_indices = [
            deg_idx,
            deg_idx + 2,
            deg_idx + 4,
            deg_idx + 6,
            deg_idx + 4,
            deg_idx + 2,
            deg_idx
        ]
        for idx in chord_indices:
            sequence.append((extended_midis[idx], extended_solfege[idx]))

    return sequence

# ==========================================
# AUDIO SYNTHESIS ENGINE
# ==========================================
def synthesize_tone(freq: float, duration: float, sample_rate: int = 44100) -> list[float]:
    num_samples = int(sample_rate * duration)
    samples = []

    attack_samples = int(sample_rate * 0.05)
    release_samples = int(sample_rate * 0.15)

    for i in range(num_samples):
        t = i / sample_rate
        val = 0.7 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)

        envelope = 1.0
        if i < attack_samples:
            envelope = i / attack_samples
        elif i > (num_samples - release_samples):
            envelope = (num_samples - i) / release_samples

        samples.append(val * envelope * 0.5)

    return samples

def write_wav_file(filename: str, pattern: list[tuple[int, str]]):
    filepath = os.path.join(OUTPUT_DIR, filename)
    all_samples = []

    for midi_note, _ in pattern:
        freq = midi_to_freq(midi_note)
        samples = synthesize_tone(freq, TICK_DURATION, SAMPLE_RATE)
        all_samples.extend(samples)

    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)

        for sample in all_samples:
            packed_sample = struct.pack('h', int(sample * 32767))
            wav_file.writeframes(packed_sample)

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("==========================================================================")
    print(" GENERATING PARALLEL C UNIFIED VOCAL WARMUPS (A4 = 432 Hz | 60 BPM)")
    print("==========================================================================\n")

    exercise_builders = {
        "Full_Scale": build_combined_scale,
        "Leaps": build_combined_leaps,
        "Three_Notes": build_combined_three_notes,
        "Diatonic_7th_Arpeggios": build_chord_arpeggios
    }

    file_count = 0

    for family_name, mode_list in MODE_NAMES.items():
        for mode_deg, mode_label in enumerate(mode_list, start=1):
            key_name = f"C_{mode_label.replace(' ', '_')}"
            midis = get_parallel_mode_midis(family_name, mode_deg, tonic_midi=60)
            solfege = get_exact_modal_solfege(family_name, mode_deg)

            print(f"Key: C {mode_label} (Parent: {family_name}, Mode {mode_deg})")
            print(f"Solfège: {' - '.join(solfege)}")

            for ex_name, builder_func in exercise_builders.items():
                pattern = builder_func(midis, solfege)
                filename = f"{key_name}_{ex_name}.wav"
                write_wav_file(filename, pattern)
                file_count += 1

            print(f" -> Generated 4 combined WAV files for {key_name}\n")

    print(f"[COMPLETE] Successfully generated {file_count} unified WAV files in '{OUTPUT_DIR}/'.")

if __name__ == "__main__":
    main()

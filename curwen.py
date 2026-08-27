#! /usr/bin/env python3

import os
import math
import struct
import wave

# ==========================================
# CONFIGURATION & METRICS
# ==========================================
OUTPUT_DIR = "output_warmups"
BPM = 60
TICK_DURATION = 60.0 / BPM     # 1.0 second per note
SAMPLE_RATE = 44100            # Standard WAV Sample Rate
A4_FREQ = 432.0                # Master Tuning

NOTE_SEMITONES = {
    'C': -9, 'C#': -8, 'Db': -8, 'D': -7, 'D#': -6, 'Eb': -6,
    'E': -5, 'F': -4, 'F#': -3, 'Gb': -3, 'G': -2, 'G#': -1,
    'Ab': -1, 'A': 0, 'A#': 1, 'Bb': 1, 'B': 2
}

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

# 1 - 5 - 4 - 6 - 3 - 2 - 7 Chord Progression Order
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
        
    midis.append(tonic_midi + 12) # Octave completion
    return midis

# ==========================================
# PATTERN BUILDING LOGIC
# ==========================================
def build_scale_ascending(midis: list[int], solfege: list[str]):
    return list(zip(midis, solfege))

def build_scale_descending(midis: list[int], solfege: list[str]):
    return list(zip(reversed(midis), reversed(solfege)))

def build_leaps_ascending(midis: list[int], solfege: list[str]):
    # Up a leap (3rd), down a step, up a leap...
    sequence = []
    n = len(midis) - 1 # excluding octave top for index stepping
    for i in range(n - 1):
        sequence.append((midis[i], solfege[i]))
        sequence.append((midis[i+2], solfege[i+2]))
    sequence.append((midis[-1], solfege[-1]))
    return sequence

def build_leaps_descending(midis: list[int], solfege: list[str]):
    # Down a leap (3rd), up a step, down a leap...
    rev_m = list(reversed(midis))
    rev_s = list(reversed(solfege))
    sequence = []
    n = len(rev_m) - 1
    for i in range(n - 1):
        sequence.append((rev_m[i], rev_s[i]))
        sequence.append((rev_m[i+2], rev_s[i+2]))
    sequence.append((rev_m[-1], rev_s[-1]))
    return sequence

def build_three_notes_ascending(midis: list[int], solfege: list[str]):
    # 2 steps up, 1 step down: (Do Re Mi, Re Mi Fa, Mi Fa So...)
    sequence = []
    n = len(midis) - 1
    for i in range(n - 1):
        sequence.append((midis[i], solfege[i]))
        sequence.append((midis[i+1], solfege[i+1]))
        sequence.append((midis[i+2], solfege[i+2]))
    sequence.append((midis[-1], solfege[-1]))
    return sequence

def build_three_notes_descending(midis: list[int], solfege: list[str]):
    rev_m = list(reversed(midis))
    rev_s = list(reversed(solfege))
    sequence = []
    n = len(rev_m) - 1
    for i in range(n - 1):
        sequence.append((rev_m[i], rev_s[i]))
        sequence.append((rev_m[i+1], rev_s[i+1]))
        sequence.append((rev_m[i+2], rev_s[i+2]))
    sequence.append((rev_m[-1], rev_s[-1]))
    return sequence

def build_chord_arpeggios(midis: list[int], solfege: list[str]):
    # I-V-IV-VI-III-II-VII 7th Chords
    # Arpeggiated: Root-3rd-5th-7th-5th-3rd-Root
    extended_midis = midis[:-1] + [m + 12 for m in midis]
    extended_solfege = solfege[:-1] + [s + "'" for s in solfege]
    
    sequence = []
    num_notes = len(midis) - 1

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
# AUDIO SYNTHESIS & WAV EXPORT ENGINE
# ==========================================
def synthesize_tone(freq: float, duration: float, sample_rate: int = 44100) -> list[float]:
    num_samples = int(sample_rate * duration)
    samples = []
    
    # ADSR Envelope for smooth vocal-like tracking
    attack_samples = int(sample_rate * 0.05)
    release_samples = int(sample_rate * 0.15)
    
    for i in range(num_samples):
        t = i / sample_rate
        # Warm dual-harmonic tone synthesis
        val = 0.7 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)
        
        # Envelope calculation to eliminate clicks
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
        
    # Pack into 16-bit PCM WAV
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1) # Mono
        wav_file.setsampwidth(2) # 16-bit
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
    print(" GENERATING PARALLEL C VOCAL WARMUPS (A4 = 432 Hz | 60 BPM)")
    print("==========================================================================\n")

    exercise_builders = {
        "Ascending_Scale": build_scale_ascending,
        "Descending_Scale": build_scale_descending,
        "Ascending_Leaps": build_leaps_ascending,
        "Descending_Leaps": build_leaps_descending,
        "Ascending_Three_Notes": build_three_notes_ascending,
        "Descending_Three_Notes": build_three_notes_descending,
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
                
            print(f" -> Generated 7 WAV files for {key_name}\n")

    print(f"[COMPLETE] Successfully generated {file_count} individual WAV files in '{OUTPUT_DIR}/'.")

if __name__ == "__main__":
    main()

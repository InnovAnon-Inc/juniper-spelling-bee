#! /usr/bin/env python3

import os
import math
import struct
import wave

# ==========================================
# CONFIGURATION & TUNING
# ==========================================
OUTPUT_DIR = "../storage/downloads/chromatic_reference_pitches"
DURATION_SEC = 5.0             # Length of each pitch sample
SAMPLE_RATE = 44100            # Standard WAV Sample Rate
A4_FREQ = 432.0                # Master Reference Pitch

# Chromatic scale definitions starting at C4 (MIDI 60)
CHROMATIC_NOTES = [
    (60, "01_C4",  "Do"),
    (61, "02_Db4", "Ra / Di"),
    (62, "03_D4",  "Re"),
    (63, "04_Eb4", "Me / Ri"),
    (64, "05_E4",  "Mi"),
    (65, "06_F4",  "Fa"),
    (66, "07_F#4", "Fi / Se"),
    (67, "08_G4",  "So"),
    (68, "09_Ab4", "Le / Si"),
    (69, "10_A4",  "La"),
    (70, "11_Bb4", "Te / Li"),
    (71, "12_B4",  "Ti")
]

TONIC_DRONE_MIDI = 48  # C3 (Tonic drone, 1 octave below C4 pitch bed)

def midi_to_freq(midi_note: int) -> float:
    # A4 (MIDI 69) = 432.0 Hz
    return A4_FREQ * (2.0 ** ((midi_note - 69) / 12.0))

# ==========================================
# AUDIO SYNTHESIS ENGINE
# ==========================================
def synthesize_reference_pair(note_freq: float, drone_freq: float, duration: float, sample_rate: int = 44100) -> list[float]:
    num_samples = int(sample_rate * duration)
    samples = []
    
    # Envelope to smoothly fade in/out without pops
    attack_samples = int(sample_rate * 0.1)
    release_samples = int(sample_rate * 0.3)
    
    for i in range(num_samples):
        t = i / sample_rate
        
        # Upper reference pitch (warm dual sine blend)
        melody_wave = 0.6 * math.sin(2 * math.pi * note_freq * t) + 0.2 * math.sin(4 * math.pi * note_freq * t)
        
        # Sub-tonic drone (pure smooth sine foundation)
        drone_wave = 0.5 * math.sin(2 * math.pi * drone_freq * t)
        
        mix = melody_wave + drone_wave
        
        # ADSR Envelope
        envelope = 1.0
        if i < attack_samples:
            envelope = i / attack_samples
        elif i > (num_samples - release_samples):
            envelope = (num_samples - i) / release_samples
            
        samples.append(mix * envelope * 0.4)
        
    return samples

def write_wav_file(filepath: str, samples: list[float]):
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(SAMPLE_RATE)
        
        for sample in samples:
            packed_sample = struct.pack('h', int(sample * 32767))
            wav_file.writeframes(packed_sample)

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    drone_freq = midi_to_freq(TONIC_DRONE_MIDI)

    print("==========================================================================")
    print(" GENERATING CHROMATIC REFERENCE PITCHES WITH SUB-TONIC DRONE")
    print(f" Master Tuning: A4 = {A4_FREQ} Hz | Drone: C3 ({drone_freq:.2f} Hz)")
    print("==========================================================================\n")

    for midi_note, note_name, solfege in CHROMATIC_NOTES:
        note_freq = midi_to_freq(midi_note)
        filename = f"{note_name}.wav"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        samples = synthesize_reference_pair(note_freq, drone_freq, DURATION_SEC, SAMPLE_RATE)
        write_wav_file(filepath, samples)
        
        print(f"Generated: {filename:<12} | Pitch: {note_freq:.2f} Hz | Solfège: {solfege}")

    print(f"\n[COMPLETE] 12 reference WAV files saved to '{OUTPUT_DIR}/'.")

if __name__ == "__main__":
    main()

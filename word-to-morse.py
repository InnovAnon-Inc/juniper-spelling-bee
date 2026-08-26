#! /usr/bin/env python

import time
import re
import random
import wave
import numpy as np
import sounddevice as sd

# --- Standard Morse Code Dictionary ---
MORSE_CODE_DICT = {
    'A': '.-',     'B': '-...',   'C': '-.-.',   'D': '-..',    'E': '.',
    'F': '..-.',   'G': '--.',    'H': '....',   'I': '..',     'J': '.---',
    'K': '-.-',    'L': '.-..',   'M': '--',     'N': '-.',     'O': '---',
    'P': '.--.',   'Q': '--.-',   'R': '.-.',    'S': '...',    'T': '-',
    'U': '..-',    'V': '...-',   'W': '.--',    'X': '-..-',   'Y': '-.--',
    'Z': '--..',   '1': '.----',  '2': '..---',  '3': '...--',  '4': '....-',
    '5': '.....',  '6': '-....',  '7': '--...',  '8': '---..',  '9': '----.',
    '0': '-----',  ',': '--..--', '.': '.-.-.-', '?': '..--..', '/': '-..-.',
    '-': '-....-', '(': '-.--.',  ')': '-.--.-'
}

class MorsePlayer:
    def __init__(self, frequency=432.0, char_wpm=20, overall_wpm=10, sample_rate=44100):
        """
        :param frequency: Pitch of the tone in Hz.
        :param char_wpm: Speed at which individual characters are sounded (>= 18 WPM recommended).
        :param overall_wpm: Effective overall speed incorporating extra spacing (Farnsworth timing).
        :param sample_rate: Audio sampling rate.
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        
        # Standard PARIS timing formula: Dit Duration (s) = 1.2 / WPM
        self.char_wpm = max(char_wpm, 5)
        self.dit_duration = 1.2 / self.char_wpm
        self.dah_duration = self.dit_duration * 3.0
        
        # Standard relative gaps within a character
        self.intra_char_gap = self.dit_duration  # 1 unit between dits/dahs
        
        # Farnsworth Timing Adjustment for inter-character and inter-word gaps
        self.overall_wpm = min(overall_wpm, self.char_wpm)
        if self.overall_wpm < self.char_wpm:
            # Calculate expanded spaces based on ITU / ARRL Farnsworth standards
            farnsworth_factor = (1.2 / self.overall_wpm - 1.2 / self.char_wpm) / (19 / 60)
            self.char_gap = (3 * self.dit_duration) + (farnsworth_factor * 3)
            self.word_gap = (7 * self.dit_duration) + (farnsworth_factor * 7)
        else:
            # Standard timing (3 units between characters, 7 units between words)
            self.char_gap = 3 * self.dit_duration
            self.word_gap = 7 * self.dit_duration

    def _generate_tone(self, duration):
        """Generates a sine wave with a 5ms anti-click fade envelope."""
        num_samples = int(self.sample_rate * duration)
        if num_samples <= 0:
            return np.array([], dtype=np.float32)
            
        t = np.linspace(0, duration, num_samples, endpoint=False)
        sine = np.sin(2 * np.pi * self.frequency * t).astype(np.float32)
        
        # Apply anti-click envelope
        fade_len = min(int(self.sample_rate * 0.005), num_samples // 2)
        if fade_len > 0:
            fade_in = np.linspace(0, 1, fade_len, dtype=np.float32)
            fade_out = np.linspace(1, 0, fade_len, dtype=np.float32)
            sine[:fade_len] *= fade_in
            sine[-fade_len:] *= fade_out
            
        return sine

    def _build_audio_buffer(self, text):
        """Helper method to synthesize floating-point audio array from text string."""
        text = text.upper().strip()
        text = re.sub(r'\s+', ' ', text)
        
        words = text.split(' ')
        audio_chunks = []

        for i, word in enumerate(words):
            for j, char in enumerate(word):
                if char in MORSE_CODE_DICT:
                    pattern = MORSE_CODE_DICT[char]
                    
                    # Synthesize dits and dahs for the current letter
                    for k, symbol in enumerate(pattern):
                        dur = self.dit_duration if symbol == '.' else self.dah_duration
                        audio_chunks.append(self._generate_tone(dur))
                        
                        # Intra-character element gap (1 dit length)
                        if k < len(pattern) - 1:
                            audio_chunks.append(np.zeros(int(self.sample_rate * self.intra_char_gap), dtype=np.float32))
                    
                    # Inter-character gap (between letters)
                    if j < len(word) - 1:
                        audio_chunks.append(np.zeros(int(self.sample_rate * self.char_gap), dtype=np.float32))
            
            # Inter-word gap (between words)
            if i < len(words) - 1:
                audio_chunks.append(np.zeros(int(self.sample_rate * self.word_gap), dtype=np.float32))

        if audio_chunks:
            return np.concatenate(audio_chunks)
        return np.array([], dtype=np.float32)

    def play_text(self, text):
        """Converts text to audio buffer and plays it out cleanly."""
        full_audio = self._build_audio_buffer(text)
        if len(full_audio) > 0:
            sd.play(full_audio, self.sample_rate)
            sd.wait()  # Wait for playback to finish

    def export_wav(self, text, filename="output.wav"):
        """Converts text to audio buffer and exports it directly to a 16-bit PCM WAV file."""
        full_audio = self._build_audio_buffer(text)
        if len(full_audio) == 0:
            print(f"Warning: No valid Morse code content to export to {filename}.")
            return

        # Convert float32 array (-1.0 to 1.0) to 16-bit PCM signed integers
        pcm16_data = (full_audio * 32767).astype(np.int16)

        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)      # Mono
            wav_file.setsampwidth(2)      # 2 bytes per sample (16-bit)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm16_data.tobytes())

        print(f"Saved audio to: {filename}")


# --- Example Usage ---
if __name__ == "__main__":
    player = MorsePlayer(
        frequency=432.0, 
        char_wpm=20, 
        overall_wpm=10
    )

    phrase = input('phrase: ')
    print(f"Generating drill sequence at 432 Hz ({player.char_wpm} WPM chars / {player.overall_wpm} WPM overall):")
    print(phrase)
    code = [MORSE_CODE_DICT[letter.upper()] if letter in MORSE_CODE_DICT else ' ' for letter in phrase]
    print(f"{code} {phrase}")
    player.export_wav(phrase, filename=f"morse_432hz_{phrase}.wav")
    #player.play_text(phrase)

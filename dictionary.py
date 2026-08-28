#! /usr/bin/env python3

import os
import time
import re
import numpy as np
import json
import urllib.request
from scipy.io import wavfile
import pyttsx3
import nltk
from nltk.corpus import wordnet, words
import pronouncing
from collections import defaultdict
import random

# Ensure NLTK datasets are downloaded
nltk.download('wordnet', quiet=True)
nltk.download('words', quiet=True)


# ==========================================
# 1. Phonetic Rhyme Engine
# ==========================================
class UnifiedPhonicsEngine:
    """Generates exact rhyme families grouped by meter and rhyme tail."""
    def __init__(self, max_word_length=8):
        self.max_word_length = max_word_length
        self.vowel_phonemes = {
            'AA', 'AE', 'AH', 'AO', 'AW', 'AY',
            'EH', 'ER', 'EY', 'IH', 'IY', 'OW',
            'OY', 'UH', 'UW'
        }
        self.word_profiles = {}
        self.rhyme_matrix = defaultdict(lambda: defaultdict(list))
        self.phone_to_words = defaultdict(list)
        self._build_indices()

    def _clean_word(self, word):
        return re.sub(r'[^a-z]', '', word.lower())

    def _extract_phonetic_parts(self, phones_str):
        tokens = phones_str.split()
        stresses = "".join([char for token in tokens for char in token if char.isdigit()])
        onset = tokens[0] if tokens else ""

        stressed_idx = -1
        primary_vowel = ""
        for i, t in enumerate(tokens):
            clean_p = "".join([c for c in t if not c.isdigit()])
            if clean_p in self.vowel_phonemes:
                if '1' in t or stressed_idx == -1:
                    stressed_idx = i
                    primary_vowel = clean_p
                    if '1' in t:
                        break

        if stressed_idx == -1:
            return None

        rhyme_tokens = ["".join([c for c in t if not c.isdigit()]) for t in tokens[stressed_idx:]]
        rhyme_tail = "_".join(rhyme_tokens)

        return {
            "stress": stresses,
            "syllables": len(stresses),
            "onset": onset,
            "vowel": primary_vowel,
            "rhyme_tail": rhyme_tail
        }

    def _build_indices(self):
        all_words = pronouncing.search(".*")
        for word in all_words:
            clean = self._clean_word(word)
            if not clean or len(clean) > self.max_word_length or clean in self.word_profiles:
                continue

            phones_list = pronouncing.phones_for_word(clean)
            if not phones_list:
                continue

            raw_phones = phones_list[0]
            parts = self._extract_phonetic_parts(raw_phones)
            if not parts:
                continue

            self.word_profiles[clean] = parts
            self.rhyme_matrix[parts["stress"]][parts["rhyme_tail"]].append(clean)
            
            # Key for finding Homophones (Identical full phoneme string)
            clean_phones = re.sub(r'\d+', '', raw_phones)
            self.phone_to_words[clean_phones].append(clean)

    def get_homophones(self, target_word):
        """Finds words that sound identical but are spelled differently."""
        clean = self._clean_word(target_word)
        phones_list = pronouncing.phones_for_word(clean)
        if not phones_list:
            return []
        
        clean_phones = re.sub(r'\d+', '', phones_list[0])
        matches = self.phone_to_words.get(clean_phones, [])
        return [w for w in matches if w != clean]

    def generate_rhyme_groups(self, max_syllables=2, min_rhymes=3):
        """Returns list of rhyming groups: [(group_label, [word_list]), ...]"""
        groups = []
        for stress in sorted(self.rhyme_matrix.keys(), key=lambda s: (len(s), s)):
            if len(stress) > max_syllables:
                continue
            for tail, word_list in self.rhyme_matrix[stress].items():
                if len(word_list) >= min_rhymes:
                    label = f"Stress {stress}, Tail {tail}"
                    groups.append((label, word_list))
        random.shuffle(groups)
        return groups


# ==========================================
# 2. 432 Hz Morse Code Audio Generator
# ==========================================
class MorseAudioGenerator:
    """Generates 432 Hz Morse Code audio signals."""
    def __init__(self, freq=432, sample_rate=44100):
        self.freq = freq
        self.sample_rate = sample_rate
        self.morse_code = {
            'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
            'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
            'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
            'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
            'Y': '-.--', 'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
            '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
            '9': '----.', '0': '-----'
        }

    def _generate_tone(self, duration_ms):
        t = np.linspace(0, duration_ms / 1000.0, int(self.sample_rate * (duration_ms / 1000.0)), False)
        tone = np.sin(2 * np.pi * self.freq * t)
        fade_len = int(self.sample_rate * 0.005)
        if len(tone) > 2 * fade_len:
            tone[:fade_len] *= np.linspace(0, 1, fade_len)
            tone[-fade_len:] *= np.linspace(1, 0, fade_len)
        return tone

    def spell_to_morse_wav(self, word, dot_ms=60, filename="temp_morse.wav"):
        dash_ms = dot_ms * 3
        elem_space = np.zeros(int(self.sample_rate * (dot_ms / 1000.0)))
        char_space = np.zeros(int(self.sample_rate * (dash_ms / 1000.0)))

        audio_chunks = []
        for char in word.upper():
            if char in self.morse_code:
                pattern = self.morse_code[char]
                for symbol in pattern:
                    audio_chunks.append(self._generate_tone(dot_ms if symbol == '.' else dash_ms))
                    audio_chunks.append(elem_space)
                audio_chunks.append(char_space)

        if audio_chunks:
            full_audio = np.concatenate(audio_chunks)
            scaled = np.int16(full_audio / np.max(np.abs(full_audio)) * 32767)
            wavfile.write(filename, self.sample_rate, scaled)
            return filename
        return None


# ==========================================
# 3. Phonics & Dictionary Audio Narrator
# ==========================================
class PhonicsAudioNarrator:
    def __init__(self, engine_ref, speech_rate=120, ollama_url="http://127.0.0.1:11434", model_name="qwen3"):
        self.phonics_engine = engine_ref
        self.morse_gen = MorseAudioGenerator(freq=432)
        self.engine = pyttsx3.init()
        self.ollama_url = ollama_url
        self.model_name = model_name
        
        self.engine.setProperty('rate', speech_rate)
        self._configure_voice()
        self.valid_english = set(words.words())
        
        self.pos_map = {
            'n': 'noun',
            'v': 'verb',
            'a': 'adjective',
            's': 'adjective',
            'r': 'adverb'
        }

    def _configure_voice(self):
        voices = self.engine.getProperty('voices')
        preferred_voices = ['samantha', 'zira', 'victoria', 'david', 'hazel', 'caren', 'alex']
        
        selected_voice = None
        for pref in preferred_voices:
            for v in voices:
                if pref in v.name.lower():
                    selected_voice = v.id
                    break
            if selected_voice:
                break

        if selected_voice:
            self.engine.setProperty('voice', selected_voice)

    def _generate_ollama_example(self, word):
        """Queries local Ollama instance for a brief kid-friendly example sentence."""
        prompt = f"Write one very short, simple, kid-friendly sentence using the word '{word}'. Output only the sentence."
        payload = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data.get("response", "").strip()
        except Exception:
            return None

    def clean_and_deduplicate_list(self, raw_words):
        filtered = []
        for w in raw_words:
            w_clean = w.lower().strip()
            has_definition = bool(wordnet.synsets(w_clean))
            if w_clean in self.valid_english or has_definition:
                filtered.append(w_clean)
        return list(dict.fromkeys(filtered))

    def get_word_details(self, word):
        """Fetches POS, definition, example, synonyms, antonyms, hypernyms, hyponyms, and homophones."""
        synsets = wordnet.synsets(word)
        homophones = self.phonics_engine.get_homophones(word)
        
        if not synsets:
            example = self._generate_ollama_example(word)
            return {
                "pos": "word",
                "definition": f"The word is {word}.",
                "example": example,
                "synonyms": [],
                "antonyms": [],
                "hypernyms": [],
                "hyponyms": [],
                "homophones": homophones
            }

        syn = synsets[0]
        pos_full = self.pos_map.get(syn.pos(), 'word')
        definition = syn.definition()
        
        # Determine Example (NLTK -> Ollama fallback)
        examples = syn.examples()
        if examples:
            example = examples[0]
        else:
            example = self._generate_ollama_example(word)

        synonyms = set()
        antonyms = set()
        hypernyms = set()
        hyponyms = set()

        for s in synsets:
            # Synonyms & Antonyms
            for lemma in s.lemmas():
                clean_lemma = lemma.name().replace('_', ' ')
                if clean_lemma.lower() != word.lower():
                    synonyms.add(clean_lemma)
                if lemma.antonyms():
                    for ant in lemma.antonyms():
                        antonyms.add(ant.name().replace('_', ' '))

            # Hypernyms (broader categories)
            for hyp in s.hypernyms():
                for lemma in hyp.lemmas():
                    hypernyms.add(lemma.name().replace('_', ' '))

            # Hyponyms (more specific types)
            for hyp in s.hyponyms():
                for lemma in hyp.lemmas():
                    hyponyms.add(lemma.name().replace('_', ' '))

        return {
            "pos": pos_full,
            "definition": definition,
            "example": example,
            "synonyms": list(synonyms)[:5],
            "antonyms": list(antonyms)[:5],
            "hypernyms": list(hypernyms)[:5],
            "hyponyms": list(hyponyms)[:5],
            "homophones": homophones[:5]
        }

    def _play_wav(self, filepath):
        if filepath and os.path.exists(filepath):
            if os.name == 'posix':
                os.system("afplay temp_morse.wav" if "darwin" in os.sys.platform else "aplay temp_morse.wav > /dev/null 2>&1")
            elif os.name == 'nt':
                os.system("powershell -c (New-Object Media.SoundPlayer 'temp_morse.wav').PlaySync()")
            time.sleep(0.2)

    def _say_and_wait(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def narrate_rhyme_group(self, group_label, raw_word_list):
        """Narrates a rhyming word group following the comprehensive educational sequence."""
        group_words = self.clean_and_deduplicate_list(raw_word_list)
        if not group_words:
            return

        words_str = ", ".join(group_words)
        print(f"\n==========================================")
        print(f"GROUP: {group_label}")
        print(f"WORDS: {words_str}")
        print(f"==========================================")

        for word in group_words:
            print(f"\n--- [Narrating Word]: {word.upper()} ---")
            details = self.get_word_details(word)

            # 1. Narrate the full list of words in that group
            self._say_and_wait(f"Group list: {words_str}.")
            time.sleep(0.3)

            # 2. Say the word
            self._say_and_wait(f"Word: {word}.")

            # 3. Spell the word with Morse code
            print("  ➜ Playing Morse Code spelling...")
            morse_file = self.morse_gen.spell_to_morse_wav(word)
            self._play_wav(morse_file)

            # 4. Part of Speech
            self._say_and_wait(f"Part of speech: {details['pos']}.")

            # 5. Definition
            self._say_and_wait(f"Definition: {details['definition']}")

            # 6. Usage Example Sentence
            if details['example']:
                self._say_and_wait(f"Example: {details['example']}")

            # 7. Synonyms
            if details['synonyms']:
                self._say_and_wait(f"Synonyms: {', '.join(details['synonyms'])}.")

            # 8. Antonyms
            if details['antonyms']:
                self._say_and_wait(f"Antonyms: {', '.join(details['antonyms'])}.")

            # 9. Homophones (Same sound, different spelling)
            if details['homophones']:
                self._say_and_wait(f"Homophones: {', '.join(details['homophones'])}.")

            # 10. Hypernyms (Broader categories)
            if details['hypernyms']:
                self._say_and_wait(f"Broader types: {', '.join(details['hypernyms'])}.")

            # 11. Hyponyms (Specific sub-types)
            if details['hyponyms']:
                self._say_and_wait(f"Specific kinds: {', '.join(details['hyponyms'])}.")

            self._say_and_wait(f"Word: {word}.")
            self._play_wav(morse_file)

            time.sleep(0.8)

        if os.path.exists("temp_morse.wav"):
            os.remove("temp_morse.wav")


# ==========================================
# Execution Loop
# ==========================================
if __name__ == "__main__":
    print("Building Phonetic Rhyme Matrix & Indexing Homophones...")
    phonics_engine = UnifiedPhonicsEngine(max_word_length=12)
    narrator = PhonicsAudioNarrator(engine_ref=phonics_engine, speech_rate=120, model_name="qwen3")

    # Generate exact rhyme groups
    rhyme_groups = phonics_engine.generate_rhyme_groups(max_syllables=5, min_rhymes=3)

    # Narrate rhyming groups
    for label, word_list in rhyme_groups[:2]:
        narrator.narrate_rhyme_group(label, word_list)

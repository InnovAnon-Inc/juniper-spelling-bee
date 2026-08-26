#! /usr/bin/env python3

import pronouncing
import re
from collections import defaultdict

class UnifiedPhonicsEngine:
    def __init__(self, max_word_length=8):
        self.max_word_length = max_word_length
        self.vowel_phonemes = {
            'AA', 'AE', 'AH', 'AO', 'AW', 'AY',
            'EH', 'ER', 'EY', 'IH', 'IY', 'OW',
            'OY', 'UH', 'UW'
        }
        # In-memory indices for zero-latency queries
        self.word_profiles = {}
        self.rhyme_matrix = defaultdict(lambda: defaultdict(list))
        self.vowel_matrix = defaultdict(lambda: defaultdict(list))
        self._build_indices()

    def _clean_word(self, word):
        return re.sub(r'[^a-z]', '', word.lower())

    def _extract_phonetic_parts(self, phones_str):
        """
        Deconstructs ARPAbet sequence into:
        - stress_pattern (e.g., '10')
        - onset (initial sound)
        - primary_vowel (e.g., 'AE')
        - rhyme_tail (stressed vowel + all remaining phonemes without stress digits)
        """
        tokens = phones_str.split()
        stresses = "".join([char for token in tokens for char in token if char.isdigit()])
        onset = tokens[0] if tokens else ""

        # Find position of primary stressed vowel (digit '1') or first vowel
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

        # Build rhyme tail: strip stress numbers from remaining tokens
        #rhyme_tokens = ["".join([c for c in t if not c.isdigit()]) for t t in tokens[stressed_idx:]]
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
        """Performs a single pass over CMUdict to index all words."""
        all_words = pronouncing.search(".*")
        for word in all_words:
            clean = self._clean_word(word)
            if not clean or len(clean) > self.max_word_length:
                continue

            # Skip duplicate variants like 'word(1)'
            if clean in self.word_profiles:
                continue

            phones_list = pronouncing.phones_for_word(clean)
            if not phones_list:
                continue

            parts = self._extract_phonetic_parts(phones_list[0])
            if not parts:
                continue

            self.word_profiles[clean] = parts
            
            # Key 1: Exact Rhyme Matrix [Stress][Rhyme Tail]
            self.rhyme_matrix[parts["stress"]][parts["rhyme_tail"]].append(clean)
            
            # Key 2: Slant/Internal Rhyme Matrix [Stress][Vowel]
            self.vowel_matrix[parts["stress"]][parts["vowel"]].append(clean)

    # ------------------ Query Interfaces ------------------

    def get_exact_rhymes(self, target_word, same_meter=True):
        """Returns all exact rhymes matching the target word's meter/tail."""
        clean = self._clean_word(target_word)
        profile = self.word_profiles.get(clean)
        if not profile:
            return []

        stress = profile["stress"] if same_meter else None
        tail = profile["rhyme_tail"]

        if same_meter:
            return [w for w in self.rhyme_matrix[stress][tail] if w != clean]
        else:
            matches = []
            for s in self.rhyme_matrix:
                matches.extend(self.rhyme_matrix[s][tail])
            return [w for w in matches if w != clean]

    def get_alliterations(self, target_word, word_pool=None):
        """Finds words sharing the same initial onset sound."""
        clean = self._clean_word(target_word)
        profile = self.word_profiles.get(clean)
        if not profile:
            return []

        target_onset = profile["onset"]
        candidates = word_pool if word_pool else self.word_profiles.keys()

        return [
            w for w in candidates 
            if w != clean and self.word_profiles[w]["onset"] == target_onset
        ]

    def generate_comprehensive_rhyme_matrix(self, max_syllables=2, min_rhymes_in_family=3):
        """
        Outputs every exact rhyme family in English, grouped by:
        Meter -> Vowel Nucleus -> Rhyme Tail Cluster
        """
        curriculum = {}

        for stress in sorted(self.rhyme_matrix.keys(), key=lambda s: (len(s), s)):
            if len(stress) > max_syllables:
                continue

            curriculum[stress] = defaultdict(dict)

            for tail, words in self.rhyme_matrix[stress].items():
                if len(words) >= min_rhymes_in_family:
                    vowel = tail.split("_")[0]
                    curriculum[stress][vowel][tail] = words

        return curriculum

engine = UnifiedPhonicsEngine(max_word_length=7)

## 1. Query Exact Rhymes (Same Meter & Stress)
#print("Exact 1-Syllable Rhymes for 'cat':", engine.get_exact_rhymes("cat"))
## Output: ['bat', 'fat', 'hat', 'mat', 'pat', 'rat', 'sat', ...]
#
#print("\nExact Trochaic (10) Rhymes for 'power':", engine.get_exact_rhymes("power"))
## Output: ['cower', 'flower', 'hour', 'sour', 'tower']
#
#
## 2. Combine Alliteration + Rhyme for a Specific Target
#cat_rhymes = engine.get_exact_rhymes("cat")
#cat_alliterative_rhymes = engine.get_alliterations("cat", word_pool=cat_rhymes)
#print("\nAlliterative Rhymes for 'cat' starting with 'k/c' sound:", cat_alliterative_rhymes)


# 3. Generate the Complete Exhaustive Rhyme Matrix
matrix = engine.generate_comprehensive_rhyme_matrix(max_syllables=5, min_rhymes_in_family=4)

for stress, vowels in matrix.items():
    if all(not vowels[vowel] for vowel in vowels.keys()): continue
    syllable_count = len(stress)
    meter_label = "Monosyllabic (1)" if stress == "1" else ("Trochaic (10)" if stress == "10" else f"Meter '{stress}'")
    
    print(f"\n==========================================")
    print(f"STRESS PATTERN: {meter_label}")
    print(f"==========================================")
    
    for vowel in sorted(vowels.keys()):
        print(f"\n  --- VOWEL FAMILY: [{vowel}] ---")
        for tail, words in vowels[vowel].items():
            #print(f"    • Tail '{tail}': {', '.join(words[:8])}")
            print(f"    • Tail '{tail}': {', '.join(words)}")

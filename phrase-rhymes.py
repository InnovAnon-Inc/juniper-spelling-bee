#! /usr/bin/env python3

import pronouncing
import re
import random
from collections import defaultdict
import nltk
from nltk.corpus import cmudict, words, wordnet

# Download NLTK data if not present
nltk.download('cmudict', quiet=True)
nltk.download('words', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

nltk.download('punkt_tab')

class CadenceMirror:
    def __init__(self, max_word_length=8):
        self.vowels = {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'}
        self.cmu = cmudict.dict()
        
        # We build a dictionary mapping (stress_signature, vowel_signature) -> list of valid English words
        # e.g., ("10", ("EH", "AH")) -> ["yellow", "hello"]
        self.pattern_to_words = defaultdict(list)
        self.word_pos = {}
        
        print("Indexing vocabulary for cadence matching...")
        self._build_vocab_index(max_word_length)
        print("Index ready.")

    def _clean(self, text):
        return re.sub(r'[^a-z\s]', '', text.lower()).strip()

    def _get_word_phonetics(self, word):
        """Extracts stress pattern string and tuple of main vowel phonemes."""
        phones_list = pronouncing.phones_for_word(word)
        if not phones_list:
            return None, None
        
        tokens = phones_list[0].split()
        stresses = "".join([c for t in tokens for c in t if c.isdigit()])
        vowels = tuple("".join([c for c in t if not c.isdigit()]) for t in tokens if any(c.isdigit() for c in t))
        return stresses, vowels

    def _build_vocab_index(self, max_length):
        # Sample real English words to avoid raw CMUdict gibberish
        english_words = set(words.words())
        
        for word in english_words:
            word_clean = word.lower()
            if len(word_clean) > max_length or not word_clean.isalpha():
                continue
            
            stresses, vowels = self._get_word_phonetics(word_clean)
            if stresses and vowels:
                pattern_key = (stresses, vowels)
                self.pattern_to_words[pattern_key].append(word_clean)

    def analyze_phrase(self, phrase):
        """Converts an input phrase into target stress and vowel sequences."""
        words_in_phrase = self._clean(phrase).split()
        full_stresses = ""
        full_vowels = []
        
        for w in words_in_phrase:
            stresses, vowels = self._get_word_phonetics(w)
            if stresses:
                full_stresses += stresses
                full_vowels.extend(vowels)
                
        return full_stresses, tuple(full_vowels)

    def generate_soundalikes(self, phrase, num_matches=5, max_words=4):
        """Finds multi-word combinations matching the exact rhythm and assonance of the input."""
        target_stresses, target_vowels = self.analyze_phrase(phrase)
        if not target_stresses:
            return [f"Could not parse phonetics for: '{phrase}'"]

        results = []
        
        def backtrack(remaining_stresses, remaining_vowels, current_chain):
            if len(results) >= num_matches * 3:  # Stop early once we have enough candidates
                return
            
            if not remaining_stresses and not remaining_vowels:
                results.append(" ".join(current_chain))
                return

            if len(current_chain) >= max_words:
                return

            # Try to match sub-segments of the target phonetic profile
            for i in range(1, len(remaining_stresses) + 1):
                sub_stress = remaining_stresses[:i]
                sub_vowels = remaining_vowels[:i]
                
                key = (sub_stress, sub_vowels)
                if key in self.pattern_to_words:
                    candidates = self.pattern_to_words[key]
                    # Sample random word match
                    chosen_word = random.choice(candidates)
                    backtrack(
                        remaining_stresses[i:], 
                        remaining_vowels[i:], 
                        current_chain + [chosen_word]
                    )

        backtrack(target_stresses, target_vowels, [])
        
        # Rank candidates by grammatical likelihood using POS tags
        ranked_results = sorted(results, key=self._score_grammar_pos, reverse=True)
        return list(dict.fromkeys(ranked_results))[:num_matches]

    def _score_grammar_pos(self, phrase):
        """Simple grammatical sanity score using NLTK Part-of-Speech tags."""
        tokens = nltk.word_tokenize(phrase)
        tags = [tag for _, tag in nltk.pos_tag(tokens)]
        
        score = 0
        # Reward natural sequences (e.g., Adjective + Noun, Noun + Verb)
        for i in range(len(tags) - 1):
            t1, t2 = tags[i], tags[i+1]
            if t1.startswith('JJ') and t2.startswith('NN'): score += 2  # Adj -> Noun
            if t1.startswith('NN') and t2.startswith('VB'): score += 2  # Noun -> Verb
            if t1.startswith('DT') and t2.startswith('NN'): score += 2  # Article -> Noun
            if t1 == t2: score -= 1  # Penalize duplicate POS back-to-back
            
        return score

# --- Example Usage ---
if __name__ == "__main__":
    mirror = CadenceMirror(max_word_length=7)
    
    #test_phrases = [
    #    "forget",       # Target sound pattern: [01], ("ER", "EH")
    #    "apple pie",    # Target sound pattern: [10 1], ("AE", "AH", "AY")
    #]
    #
    #for phrase in test_phrases:
    while True:
        phrase = input('Phrase: ')
        if not phrase:
            break
        print(f"\nTarget Phrase: '{phrase}'")
        print("Generated Sound-Alikes (Matching Stress + Vowel Sequence):")
        matches = mirror.generate_soundalikes(phrase, num_matches=4)
        for m in matches:
            print(f"  ➜ {m}")

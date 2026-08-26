#! /usr/bin/env bash
# 1) run word-to-morse.sh (or number-to-morse.sh)
# 2) record Video A: spoken number & ASL sign
# 3) record Video B: play Morse code for number while doing ASL sign
# 4) record Video C: play Morse code spelling while ASL fingerspelling
# 5) run this file with the output name: ./merge-number-spelling-bee-videos.sh "forty_two"

set -euxo nounset -o pipefail
(( UID ))
(( $# == 2 ))

v="storage/movies/Messages"
v1="$v/$(ls -tr1 "$v" | tail -n3 | head -n1)"  # Video A
v2="$v/$(ls -tr1 "$v" | tail -n2 | head -n1)"  # Video B
v3="$v/$(ls -tr1 "$v" | tail -n1)"             # Video C
vout="storage/downloads/$1.mp4"

# FFmpeg 6-segment concat graph: A -> B -> A -> C -> A -> B -> A
ffmpeg -i "$v1" -i "$v2" -i "$v3" -filter_complex \
"[0:v]fps=30,format=yuv420p[va]; \
 [1:v]fps=30,format=yuv420p[vb]; \
 [2:v]fps=30,format=yuv420p[vc]; \
 [0:a]volume=0.7,loudnorm[aa]; \
 [1:a]loudnorm[ab]; \
 [2:a]loudnorm[ac]; \
 [va][aa][vb][ab][va][aa][vc][ac][va][aa][vb][ab][va][aa]concat=n=7:v=1:a=1[v][a]" \
-map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac "$vout"

# Cleanup inputs and generated wav files
rm -v "$v1" "$v2" "$v3"
rm -v "storage/downloads/morse_432hz_$1.wav" "storage/downloads/morse_432hz_$2.wav"

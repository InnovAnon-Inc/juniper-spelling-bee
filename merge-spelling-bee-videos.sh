#! /usr/bin/env bash
# 1) run word-to-morse.sh
# 2) record word & asl sign
# 3) record fingerspelling while playing "storage/downloads/morse_432hz_$phrase _.wav"
# 4) run this file (merge-spelling-bee-videos.sh)
set -euxo nounset -o pipefail
(( UID ))
(( $# == 1 ))

v=../storage/movies/Messages
v1="$v/$(ls -tr1 $v | tail -n2 | head -n1)"
v2="$v/$(ls -tr1 $v | tail -n1)"
v3="../storage/downloads/$1.mp4"

ffmpeg -i "$v1" -i "$v2" -filter_complex \
"[0:v]fps=30,format=yuv420p[v0]; \
 [1:v]fps=30,format=yuv420p[v1]; \
 [0:v]fps=30,format=yuv420p[v2]; \
 [0:a]volume=0.7,loudnorm[a0]; \
 [1:a]loudnorm[a1]; \
 [0:a]volume=0.7,loudnorm[a2]; \
 [v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]" \
-map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac "$v3"

rm -v "$v1" "$v2" "../storage/downloads/morse_432hz_$1 _.wav"

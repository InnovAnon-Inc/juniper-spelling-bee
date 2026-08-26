#! /usr/bin/env bash
# 1) run this file (word-to-morse.sh)
# 2) record word & asl sign
# 3) record fingerspelling while playing "storage/downloads/morse_432hz_$phrase _.wav"
# 4) run merge-spelling-bee-videos.sh
set -euxo nounset -o pipefail
(( UID ))
(( $# ))
#[[ -n ${VIRTUAL_ENV:-} ]] ||
#. ~/venv/bin/activate

#read -r phrase
for phrase in "$@" ; do
#echo "$phrase _" | ssh lunchbox venv/bin/python Downloads/morse-3.py
#scp "lunchbox:morse_432hz_$phrase _.wav" storage/downloads/
env -C storage/downloads python word-to-morse.py <<< "$phrase _"
done

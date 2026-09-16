#!/usr/bin/env bash
# Sourced by the runner scripts' --quiet modes: print a command the way you
# would type it, so the summary that follows is never a mystery. Only words
# containing spaces get quotes.
show_cmd() {
    local word out=""
    for word in "$@"; do
        [[ "$word" == *" "* ]] && word="'$word'"
        out+="$word "
    done
    echo "+ ${out% }"
}

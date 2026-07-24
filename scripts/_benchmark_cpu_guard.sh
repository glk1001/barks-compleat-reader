# Shared preflight guard for benchmark scripts. Source this, then call
# require_stable_cpu before running pytest-benchmark.
#
# Benchmark wall-times are ~linear in CPU clock, and this laptop's clock swings
# from ~400 MHz (powersave governor) to several GHz (performance governor). The
# governor — not AC vs battery — is what determines a stable, high clock: with the
# performance governor the CPU reaches full turbo even on battery. So the hard gate
# is the governor; running on battery only earns a warning (turbo residency may dip
# slightly under a tighter power budget, but the clock is comparable).

require_stable_cpu() {
    # On battery? Warn but continue — the performance governor still clocks up.
    local on_ac=1 found_adapter=0 online
    for online in /sys/class/power_supply/A*/online; do
        [[ -e "$online" ]] || continue
        found_adapter=1
        if [[ "$(cat "$online")" == "1" ]]; then
            on_ac=1
            break
        fi
        on_ac=0
    done
    if [[ "$found_adapter" == "1" && "$on_ac" != "1" ]]; then
        echo "WARNING: Running on battery. The performance governor still reaches full" >&2
        echo "         clock, but turbo residency may dip slightly under a tighter power" >&2
        echo "         budget — plug in for the most repeatable numbers." >&2
    fi

    # Governor == performance on every core? (Skipped if cpufreq is unavailable.)
    local bad_governor="" gov g
    for gov in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        [[ -e "$gov" ]] || continue
        g="$(cat "$gov")"
        if [[ "$g" != "performance" ]]; then
            bad_governor="$g"
            break
        fi
    done
    if [[ -n "$bad_governor" ]]; then
        local cur_khz
        cur_khz="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo '?')"
        echo "ERROR: CPU governor is '$bad_governor', not 'performance' (cpu0 @ ${cur_khz} kHz)." >&2
        echo "       Set it before benchmarking, e.g.:" >&2
        echo "         sudo cpupower frequency-set -g performance" >&2
        echo "       or: echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor" >&2
        exit 1
    fi
}

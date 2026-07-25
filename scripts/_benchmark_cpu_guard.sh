# Shared preflight guard for benchmark scripts. Source this, then call
# require_stable_cpu before running pytest-benchmark.
#
# Benchmark wall-times are ~linear in CPU clock, so a comparison against a recorded
# baseline is only meaningful if the CPU actually reaches near its rated peak.
#
# We measure that directly rather than inferring it from the governor name, because
# the name means opposite things on different machines: under an active-mode pstate
# driver (amd-pstate-epp, intel_pstate) the "powersave" governor is EPP-driven and
# boosts to full turbo - this desktop idles at 3.7 GHz and hits 99% of its 4.67 GHz
# ceiling under load while nominally in "powersave" - whereas under acpi-cpufreq or a
# passive pstate setup the same name pins the clock low (~400 MHz on the laptop this
# guard was originally written for). Measuring also catches thermal throttling and
# battery-capped clocks, which no governor check can see.

# Minimum share of the rated max clock a loaded core must reach, in percent.
_BENCHMARK_MIN_CLOCK_PCT=85

# Briefly saturate one core and report the highest clock any core reached, in kHz.
_peak_clock_under_load() {
    local peak=0 sample f v

    # Busy-spin in the background, then sample while it runs. The first sleep gives
    # the scheduler and the frequency governor a moment to respond to the load.
    (while :; do :; done) &
    local busy_pid=$!

    for sample in 1 2 3 4 5 6; do
        sleep 0.1
        for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do
            [[ -r "$f" ]] || continue
            v="$(cat "$f" 2>/dev/null || echo 0)"
            if [[ "$v" =~ ^[0-9]+$ ]] && ((v > peak)); then
                peak=$v
            fi
        done
    done

    kill "$busy_pid" 2>/dev/null || true
    wait "$busy_pid" 2>/dev/null || true

    echo "$peak"
}

require_stable_cpu() {
    # On battery? Warn but continue - the measured check below is the real gate, and
    # it will fail on its own if the power budget actually costs us clock speed.
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
        echo "WARNING: Running on battery. Turbo residency may dip under a tighter" >&2
        echo "         power budget - plug in for the most repeatable numbers." >&2
    fi

    # Skip entirely where cpufreq isn't exposed (containers, VMs, some CI runners):
    # there is nothing to verify and nothing the user could set.
    local cap_file=/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq
    local cap
    [[ -r "$cap_file" ]] || return 0
    cap="$(cat "$cap_file")"
    [[ "$cap" =~ ^[0-9]+$ ]] && ((cap > 0)) || return 0

    local peak pct
    peak="$(_peak_clock_under_load)"
    ((peak > 0)) || return 0
    pct=$((100 * peak / cap))

    if ((pct < _BENCHMARK_MIN_CLOCK_PCT)); then
        local governor driver
        governor="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo '?')"
        driver="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null || echo '?')"
        echo "ERROR: Under load the CPU reached only ${pct}% of its rated max clock" >&2
        echo "       ($((peak / 1000)) MHz of $((cap / 1000)) MHz); ${_BENCHMARK_MIN_CLOCK_PCT}% is required for the" >&2
        echo "       timings to be comparable against a recorded baseline." >&2
        echo "       Governor '${governor}', driver '${driver}'." >&2
        echo "       If the driver is acpi-cpufreq or a passive pstate setup, switch to" >&2
        echo "       the performance governor:" >&2
        echo "         sudo cpupower frequency-set -g performance" >&2
        echo "       Otherwise suspect thermal throttling or a power/battery cap." >&2
        exit 1
    fi
}

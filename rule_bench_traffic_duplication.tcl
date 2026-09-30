#!/usr/bin/env tclsh
# ==============================================================================
# Standalone tclsh port of the serialization benchmark iRule
#
# Usage:  tclsh serialization_benchmark_tclsh.tcl ?iterations? ?rounds?
#         (defaults: 250000 iterations, 5 rounds)
#
# Shims stand in for F5-only commands so the iRule body runs nearly unchanged:
#   when RULE_INIT {...}  -> body compiled as a proc and invoked once
#   TMM::cmp_unit         -> always returns 0
#   log <facility> <msg>  -> timestamped line on stdout
#   static:: namespace    -> plain Tcl namespace
# Timing uses clock clicks -microseconds (Tcl 8.5+), falling back to
# milliseconds on 8.4.
#
# CAVEAT: this measures your local Tcl interpreter, not TMM. BIG-IP runs a
# modified Tcl 8.4, and string/bytearray handling differs between 8.4 and
# 8.6/9.0, so treat results as indicative of relative cost only.
# ==============================================================================

# ------------------------------------------------------------------------------
# F5 command shims
# ------------------------------------------------------------------------------
namespace eval ::static {}

namespace eval ::TMM {
    proc cmp_unit {} { return 0 }
}

proc log {facility message} {
    set ts [clock format [clock seconds] -format "%b %d %H:%M:%S"]
    puts [format "%s %-15s %s" $ts $facility $message]
}

# Compile the event body as a proc so its variables are fast locals, as in an
# iRule, rather than slower global lookups.
proc when {event body} {
    proc ::__irule_event_$event {} $body
}

# ------------------------------------------------------------------------------
# Timer: microsecond resolution where available
# ------------------------------------------------------------------------------
if {[catch {clock clicks -microseconds}]} {
    proc now_us {} { expr {[clock clicks -milliseconds] * 1000} }
    set ::timer_res "1ms"
} else {
    proc now_us {} { clock clicks -microseconds }
    set ::timer_res "1us"
}

# ------------------------------------------------------------------------------
# Command-line configuration
# ------------------------------------------------------------------------------
# Only accept positive integers; anything else (e.g. flags passed to tclsh, or
# leftover argv when pasting into an interactive shell) falls back to defaults.
proc cfg_arg {index default} {
    set value [lindex $::argv $index]
    if {[string is integer -strict $value] && $value > 0} {
        return $value
    }
    if {$value ne ""} {
        puts "Ignoring non-numeric argument '$value'; using default $default"
    }
    return $default
}
set ::cfg_iterations [cfg_arg 0 250000]
set ::cfg_rounds     [cfg_arg 1 5]

# ==============================================================================
# Benchmark (iRule body)
# ==============================================================================
when RULE_INIT {
    switch -- [TMM::cmp_unit] {
        0 {
            set iterations $::cfg_iterations
            set rounds     $::cfg_rounds
            set noise_pct  3.0      ;# differences below this % are reported as noise

            set test_ip      "10.1.10.20"
            set test_dest    "pool_security_analytics_primary"
            set test_payload {<134>1 2026-09-09T17:00:00Z web01 app - - [token@123] Live production log event}

            set best_base -1
            set best_a    -1
            set best_b    -1
            set err_a     0
            set err_b     0

            log local0.info "=== STARTING SERIALIZATION BENCHMARK (Tcl [info patchlevel], timer $::timer_res, $rounds rounds x $iterations iterations per test) ==="

            for {set r 0} {$r < $rounds} {incr r} {

                # ---- BASELINE: empty loop (loop overhead only) ----
                set t0 [now_us]
                for {set i 0} {$i < $iterations} {incr i} { }
                set el [expr {[now_us] - $t0}]
                if {$best_base < 0 || $el < $best_base} { set best_base $el }

                # ---- TEST A: Legacy length-prefixed binary format ----
                set t0 [now_us]
                for {set i 0} {$i < $iterations} {incr i} {
                    set cli_ip_len [binary format S [string length $test_ip]]
                    set dest_len   [binary format S [string length $test_dest]]
                    set packet "$cli_ip_len$dest_len$test_ip$test_dest$test_payload"

                    binary scan $packet SS dec_ip_len dec_dest_len
                    set dest_start [expr {4 + $dec_ip_len}]
                    set data_start [expr {$dest_start + $dec_dest_len}]
                    set dec_ip   [string range $packet 4 [expr {$dest_start - 1}]]
                    set dec_dest [string range $packet $dest_start [expr {$data_start - 1}]]
                    set dec_data [string range $packet $data_start end]

                    if {$dec_ip ne $test_ip || $dec_dest ne $test_dest || $dec_data ne $test_payload} {
                        incr err_a
                    }
                }
                set el [expr {[now_us] - $t0}]
                if {$best_a < 0 || $el < $best_a} { set best_a $el }

                # ---- TEST B: Delimited string format ----
                set t0 [now_us]
                for {set i 0} {$i < $iterations} {incr i} {
                    set packet "${test_ip}#${test_dest}#${test_payload}"

                    set h1 [string first "#" $packet]
                    set h2 [string first "#" $packet [expr {$h1 + 1}]]
                    set dec_ip   [string range $packet 0 [expr {$h1 - 1}]]
                    set dec_dest [string range $packet [expr {$h1 + 1}] [expr {$h2 - 1}]]
                    set dec_data [string range $packet [expr {$h2 + 1}] end]

                    if {$dec_ip ne $test_ip || $dec_dest ne $test_dest || $dec_data ne $test_payload} {
                        incr err_b
                    }
                }
                set el [expr {[now_us] - $t0}]
                if {$best_b < 0 || $el < $best_b} { set best_b $el }
            }

            # ------------------------------------------------------------------
            # Results (all times in microseconds)
            # ------------------------------------------------------------------
            set net_a [expr {$best_a - $best_base}]
            set net_b [expr {$best_b - $best_base}]
            set total [expr {$rounds * $iterations}]

            log local0.info "--- BENCHMARK RESULTS (best of $rounds rounds; [format %.1f [expr {$best_base / 1000.0}]]ms loop overhead subtracted) ---"

            if {$net_a < 0 || $net_b < 0} {
                log local0.warning "Performance : INVALID - timer went backwards (Legacy=${net_a}us, Modern=${net_b}us)."
            } elseif {$net_a == 0 || $net_b == 0} {
                log local0.warning "Performance : INVALID - zero elapsed time (Legacy=${net_a}us, Modern=${net_b}us). Increase iterations."
            } else {
                set avg_a_us [expr {double($net_a) / $iterations}]
                set avg_b_us [expr {double($net_b) / $iterations}]

                log local0.info [format "Legacy Binary Approach    : Total=%.1fms | Avg=%.3fus/pkt" [expr {$net_a / 1000.0}] $avg_a_us]
                log local0.info [format "Modern Delimited Approach : Total=%.1fms | Avg=%.3fus/pkt" [expr {$net_b / 1000.0}] $avg_b_us]

                # Change in time per packet relative to legacy (negative = modern is faster)
                set pct_change [expr {(double($net_b) - $net_a) * 100.0 / $net_a}]

                if {abs($pct_change) < $noise_pct} {
                    log local0.info [format "Performance : No significant difference (%+.1f%%, within %.1f%% noise threshold)" $pct_change $noise_pct]
                } elseif {$net_b < $net_a} {
                    set ratio [expr {double($net_a) / $net_b}]
                    log local0.info [format "Performance : Modern approach is %.2fx FASTER (%.1f%% less time per packet)" $ratio [expr {-$pct_change}]]
                } else {
                    set ratio [expr {double($net_b) / $net_a}]
                    log local0.info [format "Performance : Modern approach is %.2fx SLOWER (%.1f%% more time per packet)" $ratio $pct_change]
                }
            }

            if {$err_a == 0 && $err_b == 0} {
                log local0.info "Integrity   : Both approaches round-tripped all fields correctly ($total/$total each)"
            } else {
                log local0.warning "Integrity   : ERRORS DETECTED - Legacy=$err_a/$total, Modern=$err_b/$total"
            }
            log local0.info "=========================================================================="
        }
        default {
            return
        }
    }
}

# ------------------------------------------------------------------------------
# Fire the event (TMM does this on rule load)
# ------------------------------------------------------------------------------
::__irule_event_RULE_INIT

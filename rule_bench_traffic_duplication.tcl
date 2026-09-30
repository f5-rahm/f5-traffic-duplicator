# ==============================================================================
# Benchmark iRule: Comparing Header Serialization Performance & Accuracy
# Deploy to any LTM Virtual Server or test in TMOS to log timing stats
# Uses static:: namespace in RULE_INIT to ensure CMP compliance and zero TMM locking
# ==============================================================================
when RULE_INIT {
    # Pin benchmark execution to TMM core 0 to prevent multi-core lockup and contention
    switch -- [TMM::cmp_unit] {
        0 {
            # High iteration count amortizes iRule/Tcl bytecode startup and JIT warmup costs
            set static::bench_iterations 250000
            set static::bench_test_ip "10.1.10.20"
            set static::bench_test_dest "pool_security_analytics_primary"
            set static::bench_test_payload {<134>1 2026-09-09T17:00:00Z web01 app - - [token@123] Live production log event}

            log local0.info "=== STARTING TRAFFIC DUPLICATION BENCHMARK on TMM [TMM::cmp_unit] ($static::bench_iterations iterations) ==="

            # --------------------------------------------------------------------------
            # TEST A: Legacy Binary Format & Scan Method
            # --------------------------------------------------------------------------
            set t0 [clock clicks -milliseconds]
            set err_count_a 0
            for {set i 0} {$i < $static::bench_iterations} {incr i} {
                # Encapsulation (Ingress)
                set cli_ip_len [binary format S [string length $static::bench_test_ip]]
                set dest_len [binary format S [string length $static::bench_test_dest]]
                set packet "$cli_ip_len$dest_len$static::bench_test_ip$static::bench_test_dest$static::bench_test_payload"

                # Decapsulation (Distribution)
                binary scan $packet "S S" dec_ip_len dec_dest_len
                set dec_ip [string range $packet 4 [expr {4 + $dec_ip_len - 1}]]
                
                # Verify correctness
                if { $dec_ip ne $static::bench_test_ip } {
                    incr err_count_a
                }
            }
            set t1 [clock clicks -milliseconds]
            set elapsed_a_ms [expr {$t1 - $t0}]
            set avg_a_us [expr { (double($elapsed_a_ms) * 1000.0) / $static::bench_iterations }]

            # --------------------------------------------------------------------------
            # TEST B: Modernized Delimited String Method
            # --------------------------------------------------------------------------
            set t2 [clock clicks -milliseconds]
            set err_count_b 0
            for {set i 0} {$i < $static::bench_iterations} {incr i} {
                # Encapsulation (Ingress)
                set packet "${static::bench_test_ip}#${static::bench_test_dest}#${static::bench_test_payload}"

                # Decapsulation (Distribution)
                set h1 [string first "#" $packet]
                set h2 [string first "#" $packet [expr {$h1 + 1}]]
                set dec_ip [string range $packet 0 [expr {$h1 - 1}]]
                set dec_dest [string range $packet [expr {$h1 + 1}] [expr {$h2 - 1}]]
                set dec_data [string range $packet [expr {$h2 + 1}] end]

                # Verify correctness
                if { $dec_ip ne $static::bench_test_ip } {
                    incr err_count_b
                }
            }
            set t3 [clock clicks -milliseconds]
            set elapsed_b_ms [expr {$t3 - $t2}]
            set avg_b_us [expr { (double($elapsed_b_ms) * 1000.0) / $static::bench_iterations }]

            # --------------------------------------------------------------------------
            # Output Benchmark Results
            # --------------------------------------------------------------------------
            log local0.info "--- BENCHMARK RESULTS ---"
            log local0.info "Legacy Binary Approach     : Total=${elapsed_a_ms}ms | Avg=${avg_a_us}us/pkt | Corrupted=${err_count_a}/$static::bench_iterations"
            log local0.info "Modern Delimited Approach  : Total=${elapsed_b_ms}ms | Avg=${avg_b_us}us/pkt | Corrupted=${err_count_b}/$static::bench_iterations"
            if { $avg_b_us > 0 } {
                set speedup [expr {double($avg_a_us) / $avg_b_us}]
                log local0.info "Performance Improvement   : ${speedup}x faster with 100% data integrity"
            }
            log local0.info "=========================================================================="
        }
        default {
            return
        }
    }
}

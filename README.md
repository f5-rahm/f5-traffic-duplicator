# f5-traffic-duplicator
iApp that deploys front-end and back-end iRules to duplicate packets on BIG-IP

- [iApp Template](f5.traffic_duplication.tmpl)

## Deploy App Services
I created separate version deploy scripts so I could test all versions at once, this is not likely a requirement for you but the details are here if you want to do the same. One of these is probably sufficient, however.
- [17.1 App Services Deployment](deploy_171.sh) | [17.1 App Services Teardown](teardown_171.sh)
- [17.5 App Services Deployment](deploy_175.sh) | [17.5 App Services Teardown](teardown_175.sh)
- [21.1 App Services Deployment](deploy_211.sh) | [21.1 App Services Teardown](teardown_211.sh)

## Diagrams
- [Use Case diagrams](f5_traffic_duplication_walkthrough.md)

## App Services Test Harness
I had a single Ubuntu server on both sides of BIG-IP, ingress and egress, so I could deploy a single test harness to send and receive the traffic. This script handles it all.
- [Test Harness](run_all_tests.py)

## iRule Changes Benchmark Script
I wanted to make sure the changes from binary stuffing and extraction to string commands wouldn't negatively impact performance. I started with a RULE_INIT based iRule to do the tests but the startup penalties to save iRules (plus a repeatable TMM core if I tried too many "requests") led me to just isolate the Tcl-based changes and run the test in the Tcl shell. This script accomplishes that.
- [Tclsh script to test the significant iRules changes in Tcl-based commands](rule_bench_traffic_duplication.tcl)

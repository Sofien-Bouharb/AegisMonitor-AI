P11 — Prometheus Alert Rules Report

Status: Complete

Objective:

* Implement automatic infrastructure alerts in Prometheus for abnormal CPU, memory, disk-space, disk-I/O, and host-availability conditions.
* Validate that each alert correctly transitions from inactive to pending to firing where applicable.
* Keep the production thresholds unchanged after testing.

Production rules implemented in `prometheus/alert_rules.yml`:

* HighCPUUsage

  * Condition: CPU usage > 85%
  * Duration: 2 minutes
  * Severity: warning
  * Purpose: Detect sustained high CPU utilization.

* HighMemoryUsage

  * Condition: memory usage > 90%
  * Duration: 2 minutes
  * Severity: warning
  * Purpose: Detect sustained high memory utilization.

* LowDiskSpace

  * Condition: root filesystem available space < 10%
  * Duration: 2 minutes
  * Severity: warning
  * Purpose: Detect critically low available disk space.

* HostDown

  * Condition: `up{job="node-exporter"} == 0`
  * Duration: 1 minute
  * Severity: critical
  * Purpose: Detect when Prometheus can no longer scrape Node Exporter.

* HighDiskReadRate

  * Condition: aggregate disk read throughput > 100,000,000 bytes/s
  * Duration: 2 minutes
  * Severity: warning
  * Purpose: Detect sustained high disk-read activity.
  * Loop and RAM devices are excluded.

* HighDiskWriteRate

  * Condition: aggregate disk write throughput > 100,000,000 bytes/s
  * Duration: 2 minutes
  * Severity: warning
  * Purpose: Detect sustained high disk-write activity.
  * Loop and RAM devices are excluded.

What was done during P11:

* Created the Prometheus alert-rule configuration.
* Configured a 15-second alert evaluation interval.
* Validated the rules with `promtool`.
* Confirmed all six production rules load correctly.
* Tested `HighCPUUsage` using the controlled CPU workload:

  * Confirmed Pending → Firing.
* Tested `HighMemoryUsage` using the RAM-aware memory workload:

  * Confirmed Pending → Firing.
* Tested `LowDiskSpace` safely using a temporary higher threshold instead of filling hundreds of GB of storage:

  * Confirmed the alert fires correctly.
  * Removed the temporary rule afterward.
* Tested `HostDown` by temporarily stopping Node Exporter:

  * Confirmed `up == 0`.
  * Confirmed Pending → Firing.
  * Restarted Node Exporter and confirmed recovery.
* Tested `HighDiskReadRate` using a temporary lower threshold because generating 100 MB/s of physical reads was not practical with the existing workload:

  * Confirmed the alert fires correctly.
  * Removed the temporary rule afterward.
* Tested `HighDiskWriteRate` using a temporary lower threshold:

  * Confirmed the alert fires correctly.
  * Removed the temporary rule afterward.
* Discovered that the existing disk workload writes continuously to a temporary file and can hit a filesystem/quota limit during long runs; no leftover AegisMonitor temporary files remained after the failed test.
* Restored the final Prometheus configuration to exactly six production alert rules.

Final P11 state:

* 6 production alert rules implemented.
* 6 rules validated with Prometheus.
* Temporary test rules removed.
* Production thresholds restored.
* Alert lifecycle and recovery behavior verified where applicable.
* No PostgreSQL persistence or AI correlation was implemented, keeping P11 within its intended scope.
* P11 is complete.

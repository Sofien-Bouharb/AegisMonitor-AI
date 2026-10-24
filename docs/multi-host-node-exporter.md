# Multi-host Node Exporter Configuration

Prometheus discovers additional Node Exporter targets from `prometheus/targets/node-exporters.yml`.

## Add a target

Replace the example IP with the remote machine's reachable IP address:

    - targets: ["192.168.1.20:9100"]
      labels:
        host: "server-1"
        env: "home"

The remote machine must run Node Exporter on port 9100, and that port must be reachable from the Prometheus container. Restrict access to trusted monitoring systems.

Prometheus refreshes the target file every 30 seconds. Keep `[]` in the file when no additional targets are configured.

## Verify target health

Open http://localhost:9090/targets and inspect the `node-exporter` job. A successfully scraped target should show `UP`.

Alternatively, query:

    up{job="node-exporter"}

The `host` and `env` labels help distinguish targets in queries and dashboards.

## Validation status

The file-based discovery configuration and local target have been validated. Remote-host scraping has not yet been integration-tested.

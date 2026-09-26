* P12 objective:

  * Add Alertmanager to AegisMonitor.
  * Use Alertmanager for alert grouping, deduplication, routing, inhibition, and silencing.
  * Keep notification delivery separate from P12; Telegram notifications are deferred to P13.

* Alertmanager deployment:

  * Added Alertmanager as a Docker Compose service.
  * Image pinned to `prom/alertmanager:v0.29.0`.
  * Alertmanager is enabled under the existing `dev` and `full` Compose profiles.
  * Alertmanager exposes port `9093`.
  * Container restart policy is `unless-stopped`.

* Alertmanager configuration:

  * Configuration file is `alertmanager/alertmanager.yml`.
  * The configuration is mounted into the container at `/etc/alertmanager/alertmanager.yml`.
  * The configuration is mounted read-only.
  * SELinux `:Z` labeling is used because the project runs on Fedora.
  * Alertmanager explicitly uses:

    * `--config.file=/etc/alertmanager/alertmanager.yml`
    * `--storage.path=/alertmanager`

* Alertmanager persistence:

  * Added the named Docker volume `alertmanager-data`.
  * The volume is mounted at `/alertmanager`.
  * This provides persistent Alertmanager state for features such as silences.

* Alertmanager global configuration:

  * `resolve_timeout` is set to `5m`.

* Alert grouping:

  * Alertmanager groups alerts using:

    * `alertname`
    * `instance`
  * This means alerts with the same alert name and instance are placed in the same notification group.

* Default routing:

  * The default receiver is named `default`.
  * Alerts that do not match a more specific route are sent to the `default` receiver.
  * The default `group_wait` is `30s`.
  * `group_interval` is `5m`.
  * `repeat_interval` is `4h`.

* Critical routing:

  * A dedicated route exists for alerts where:

    * `severity="critical"`
  * Critical alerts are routed to the `critical` receiver.
  * Critical alerts use a shorter `group_wait` of `10s`.
  * This creates a distinction between normal warning alerts and critical alerts.

* Receiver design:

  * Two receivers were deliberately created:

    * `default`
    * `critical`
  * Neither receiver currently contains a notification integration.
  * This was intentional because actual notification delivery is deferred to P13.
  * Telegram credentials and notification configuration should therefore not be added during P12.

* Prometheus integration:

  * Prometheus was configured to send alerts to:

    * `http://alertmanager:9093`
  * The Docker Compose service name `alertmanager` is used instead of `localhost`.
  * This is because Prometheus communicates with Alertmanager through the Docker Compose network.

* Prometheus validation:

  * `docker compose --profile dev config --quiet` was used to validate the Compose configuration.
  * `promtool check config` confirmed that `prometheus.yml` is valid.
  * The six existing Prometheus alert rules remained valid.
  * Prometheus had to be force-recreated after changing its bind-mounted configuration because a normal `up -d` did not reload the configuration.
  * The Prometheus API confirmed:

    * `activeAlertmanagers` contains `http://alertmanager:9093/api/v2/alerts`.
  * Therefore the Prometheus-to-Alertmanager connection was explicitly verified.

* Alertmanager validation:

  * Alertmanager readiness was verified through:

    * `http://localhost:9093/-/ready`
  * The endpoint returned `OK`.
  * Alertmanager logs confirmed that `alertmanager.yml` was successfully loaded.
  * Alertmanager's `/api/v2/status` endpoint confirmed:

    * cluster status is `ready`
    * version is `0.29.0`
    * grouping configuration is loaded
    * default routing is loaded
    * critical routing is loaded.

* End-to-end alert test:

  * The existing `HighCPUUsage` alert was used rather than creating a temporary test alert.
  * The workload generator syntax was corrected to use:

    * `python3 scripts/load_gen.py cpu --duration 180 --intensity 100`
  * The CPU workload pushed CPU usage to approximately 100%.
  * The `HighCPUUsage` rule correctly transitioned from `pending` to `firing`.
  * The existing `for: 2m` behavior was therefore validated.
  * Prometheus reported:

    * `alertname=HighCPUUsage`
    * `severity=warning`
    * `state=firing`
  * Alertmanager's `/api/v2/alerts` endpoint confirmed that the same alert was received and active.

* Alert routing validation:

  * The `HighCPUUsage` alert has severity `warning`.
  * It therefore correctly followed the default route rather than the critical route.
  * Alertmanager reported the receiver as `default`.
  * This confirmed that the routing configuration is being applied.

* Alert identity and deduplication:

  * Alertmanager generated a fingerprint for the `HighCPUUsage` alert.
  * The fingerprint observed during testing was:

    * `8b8bbc74d7b6ddbd`
  * This confirms that Alertmanager is assigning a stable identity to the alert for its alert-management and deduplication mechanisms.

* Silencing and inhibition state:

  * The received alert showed:

    * `inhibitedBy=[]`
    * `mutedBy=[]`
    * `silencedBy=[]`
  * This confirms that the alert was not inhibited, muted, or silenced during the test.
  * The configuration and runtime API therefore expose the mechanisms needed for these Alertmanager features.

* Important distinction established during P12:

  * Prometheus is responsible for evaluating alert rules and determining when an alert becomes pending or firing.
  * Alertmanager is responsible for managing firing alerts after Prometheus sends them.
  * Alertmanager handles grouping, routing, deduplication, silencing, and inhibition.
  * Notification integrations are a separate concern and are not part of the P12 implementation.

* Validation principle used:

  * We validated the real alert pipeline using an existing AegisMonitor alert instead of creating artificial production rules solely for testing.
  * We did not modify the existing alert rules to manufacture a critical alert.
  * Because notification integrations are intentionally empty until P13, we did not consider the absence of an actual notification as a P12 failure.

* Final P12 architecture:

  * Node Exporter collects host metrics.
  * Prometheus evaluates the metrics and alert rules.
  * Prometheus sends firing alerts to Alertmanager.
  * Alertmanager groups alerts by `alertname` and `instance`.
  * Alertmanager routes critical alerts separately from other severities.
  * Alertmanager maintains alert identity and state for deduplication and management.
  * Alertmanager supports inhibition and silencing.
  * Alertmanager state is persisted through `alertmanager-data`.
  * Telegram notification delivery is intentionally postponed to P13.

* P12 status:

  * Alertmanager deployment: complete.
  * Alertmanager configuration: complete.
  * Persistent state: configured.
  * Prometheus integration: verified.
  * End-to-end alert delivery: verified.
  * Default routing: verified.
  * Critical routing configuration: verified at configuration/runtime level.
  * Grouping configuration: verified.
  * Alert fingerprint/deduplication mechanism: observed.
  * Silencing/inhibition mechanisms: configured and exposed.
  * Telegram notification: not implemented; reserved for P13.

## P13 — Telegram Notifications: Complete Recap

* **P13 objective**

  * Integrate AegisMonitor's existing alerting pipeline with **Telegram**.
  * The intended flow is:

    * Prometheus detects an alert
    * Prometheus sends it to Alertmanager
    * Alertmanager routes it
    * Alertmanager sends a Telegram notification
    * When the alert clears, Telegram receives a resolved notification

* **Telegram bot**

  * Created a dedicated Telegram bot through **BotFather**.
  * Started the bot so Telegram could provide the chat information.
  * Retrieved the bot token using `getUpdates`.
  * The bot token was **never pasted into the conversation**.
  * Chat ID was identified as `7686787736`.

* **Secret-storage decision**

  * We deliberately **did not put the Telegram bot token in Git**.
  * Secrets are stored locally on each Fedora machine under:

    * `~/.config/aegismonitor/secrets/telegram_bot_token`
    * `~/.config/aegismonitor/secrets/telegram_chat_id`
  * The project repository therefore contains the Alertmanager configuration but **not the actual credentials**.
  * This is particularly important because you're synchronizing the project between two PCs using Git.

* **Docker Compose secrets**

  * Added Telegram secrets to the Compose configuration.
  * The bot token is mounted into Alertmanager through Docker Secrets.
  * The chat ID is also defined as a Compose secret, although Alertmanager v0.29 ultimately doesn't consume it directly through `chat_id_file`.

* **Important Alertmanager version discovery**

  * We're using:

    * `prom/alertmanager:v0.29.0`
  * We initially tried:

    * `chat_id_file`
  * Alertmanager rejected this configuration because **v0.29.0 does not support `chat_id_file`**.
  * The container entered a restart loop with:

    * `field chat_id_file not found in type config.plain`
  * We corrected the configuration to use:

    * `bot_token_file`
    * literal `chat_id`
  * We kept `send_resolved: true`.

* **Final Telegram receiver configuration concept**

  * Both the `default` and `critical` Alertmanager receivers send to the same Telegram chat.
  * Both use:

    * `/run/secrets/telegram_bot_token`
    * `chat_id: 7686787736`
    * `send_resolved: true`

* **Alert routing decision**

  * Existing Alertmanager routing was preserved.
  * Default route handles normal alerts.
  * `severity="critical"` has a dedicated critical route.
  * Both ultimately notify Telegram.
  * Default grouping is based on:

    * `alertname`
    * `instance`
  * Default:

    * `group_wait: 30s`
    * `group_interval: 5m`
    * `repeat_interval: 4h`
  * Critical:

    * `group_wait: 10s`

* **Secret permission problem**

  * The first firing notification failed because Alertmanager runs as:

    * `uid=65534(nobody)`
    * `gid=65534(nobody)`
  * The token initially belonged exclusively to your Fedora user:

    * `sofien:sofien`
    * mode `600`
  * Therefore Alertmanager could not read it.

* **Permission solution**

  * We changed the token file's group to `nobody`:

    * `sudo chgrp 65534 ~/.config/aegismonitor/secrets/telegram_bot_token`
  * Changed permissions to:

    * `640`
  * Final effective permission model:

    * owner `sofien` → read/write
    * group `nobody` → read
    * everyone else → no access
  * Inside the Alertmanager container, we verified that the `nobody` user could actually read the secret.
  * We **did not weaken the permissions further**.

* **Compose validation**

  * We repeatedly used the correct profile:

    * `docker compose --profile dev ...`
  * `docker compose --profile dev config --quiet` passed after the configuration was corrected.
  * Alertmanager successfully started.
  * `http://localhost:9093/-/ready` returned:

    * `OK`

* **Prometheus → Alertmanager verification**

  * We used the existing `HighCPUUsage` rule from P11.
  * CPU workload was generated using:

    * `python3 scripts/load_gen.py cpu --duration 420 --intensity 100`
  * Prometheus first showed the alert as **pending**.
  * After the required `for: 2m` period, it became **firing**.
  * Alertmanager received the alert.
  * The alert had:

    * `alertname = HighCPUUsage`
    * `instance = node-exporter:9100`
    * `severity = warning`
  * Alertmanager correctly routed it to the default receiver.

* **Firing notification verification**

  * After fixing the secret permissions, the Telegram firing notification was successfully received.
  * The notification contained:

    * alert name
    * instance
    * severity
    * description
    * summary
    * Prometheus source link
  * This proved the complete:

    * **Prometheus → Alertmanager → Telegram**
      pipeline.

* **Resolved notification verification**

  * After the CPU workload finished, we checked:

    * `curl -s http://localhost:9090/api/v1/alerts`
  * Prometheus returned:

    * `"alerts": []`
  * This confirmed that the alert had resolved.
  * Telegram subsequently delivered:

    * **Alerts Resolved**
  * The resolved message contained the same alert metadata.
  * Therefore `send_resolved: true` was independently verified.

* **Final P13 validation**

  * P13 is now **fully complete**.
  * We have verified both directions:

    * **Firing → Telegram** ✅
    * **Resolved → Telegram** ✅

* **What P13 did NOT change**

  * We did not introduce PostgreSQL persistence yet.
  * We did not introduce Redis state yet.
  * We did not introduce anomaly detection.
  * We did not introduce FastAPI.
  * We did not introduce Ollama/LLM analysis.
  * We did not modify the P1/P2/P4 database design decisions.
  * Those remain later roadmap stages.

* **Current roadmap position**

  * P1 → P12: ✅ complete
  * **P13: ✅ complete**
  * **P14: ⏳ next**
  * P14 is **Retention validation**.

* **Two-PC synchronization decision**

  * Git synchronizes the **project configuration and code**.
  * Git does **not** synchronize the Telegram credentials.
  * On the second Fedora PC, we will recreate the local secret files manually.
  * This means both PCs can use the same AegisMonitor repository while keeping the Telegram bot token outside Git.

So the key architectural result of P13 is:

**Controlled workload → Prometheus rule → Alertmanager → Telegram notification**, with **secure local secret handling** and verified **firing + resolved lifecycle notifications**.

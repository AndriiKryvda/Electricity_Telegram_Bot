# Electricity Status Telegram Bot Requirements

## 1. Goal
1. Provide a Telegram bot that indicates whether electricity is available at home.
2. The bot monitors a local smart device (e.g., smart meter, UPS, or power monitor) via TCP connection.
3. The bot stores electricity status history and provides statistics to authorized Telegram users.
4. The bot runs on a home server on the same network as the monitored device.

## 2. Platform and Delivery
1. Target platform: Telegram messaging app (all Telegram clients: mobile, desktop, web).
2. Delivery format: Telegram bot with interactive keyboard commands and inline buttons.

## 3. File-Based Configuration

### 3.1 Configuration File
1. All settings are stored in a single YAML configuration file: `config.yaml` (or `config.yml`).
2. The file is located in the bot's working directory.
3. The bot loads the configuration on startup and applies settings immediately.
4. The bot monitors the configuration file for changes using a file watcher.
5. On file change, the bot gracefully reloads configuration without restart.

### 3.2 Configuration File Structure
```yaml
# config.yaml

# Telegram Bot Settings
bot:
  token: "YOUR_BOT_TOKEN_HERE"
  admin_user_ids:
    - 123456789
    - 987654321

# Home Device to Monitor
device:
  host: "192.168.1.100"       # IP address or hostname
  port: 8080                   # TCP port (1-65535)
  poll_interval: 60            # Poll interval in seconds (30-120)

# Server Settings
server:
  last_state_file: "./data/last_state.json"   # Path to restore state on restart

## 4. Electricity Status Detection Logic
1. The bot checks connectivity to the configured IP/hostname and Port periodically, according to the poll interval.
2. Each check attempts a TCP connection with a timeout of up to 15 seconds.
3. The poll interval for the next check starts only after the current connection attempt is closed (success or failure).
4. **Successful check:**
   1. Connection established within timeout.
   2. Connection is closed immediately after successful connect.
   3. Consecutive success counter increases by 1.
5. **Failed check:**
   1. Connection not established within timeout, or socket/connect error occurs.
   2. Consecutive failure counter increases by 1.
6. **OFF decision rule:**
   1. Electricity status becomes OFF only after 2 failed checks in a row.
   2. A successful check resets the consecutive failure counter to 0.
7. **ON decision rule:**
   1. Electricity status becomes ON only after 2 successful checks in a row.
   2. A failed check resets the consecutive success counter to 0.

## 5. Bot User Interface

### 5.1 Status Display
1. **Visual states:**
   1. **ON** — 💡 (light bulb emoji) + "Electricity: ON" text.
   2. **OFF** — ⚫ (black circle emoji) + "Electricity: OFF" text.
   3. **N/A** (initial/unknown) — ⚪ (white circle emoji) + "Electricity: Unknown" text.
2. **Last check time** — shown below the status (e.g., "Last check: 2026-05-25 09:15"). Displays "N/A" until the first check completes.
3. **Inline keyboard** with a "🔄 Refresh" button that triggers an immediate TCP check and updates the status.

### 5.2 Bot Commands
1. `/status` — Show current electricity status (default command, also sent on first interaction).
2. `/stats` — Show current electricity status and outage history table.
3. `/reload` — Trigger a manual reload of the configuration file. Responds with "Configuration reloaded." on success.
4. `/help` — Show list of available commands and brief descriptions.

### 5.3 Statistics (via /stats)
1. Display the following:
   1. **Current status** — ON / OFF / N/A (with emoji indicator).
   2. **Outage history table** — a table showing all recorded status changes with the following columns:
      1. **Date & Time** — timestamp when the status changed (format: `dd-MMM-yyyy HH:mm`).
      2. **Status** — `ON` (green-colored text) or `OFF` (red-colored text).
      3. **Duration** — how long the previous status lasted before this change (e.g., `3d 19h`, `3m`, `1h 42m`). Empty for the very first recorded event.
2. Table displayed in reverse-chronological order (newest first).
3. Events older than **3 days** are automatically purged from the table.
4. Inline keyboard with "🔄 Refresh" button to reload the table from storage.
5. Inline keyboard with "🗑️ Clear" button to clear all events (with confirmation prompt: "Are you sure you want to clear all events?").

## 6. Configuration Validation
1. **IP/hostname validation:**
   1. Accept valid IPv4 addresses or hostnames.
   2. Hostname resolution is supported.
   3. Reject invalid format with a log warning and fall back to last known good configuration.
2. **Port validation:**
   1. Integer range 1 to 65535.
   2. Reject values outside range with a log warning and fall back to last known good configuration.
3. **Poll interval validation:**
   1. Integer range 30 to 120 seconds.
   2. Reject values outside range with a log warning and fall back to last known good configuration.
4. **Bot token validation:**
   1. Reject empty or malformed tokens.
   2. On invalid token, log error and do not start the bot.
5. **Admin user IDs validation:**
   1. Accept valid Telegram user IDs (positive integers).
   2. Reject non-numeric or negative values with a log warning.
6. **Config reload behavior:**
   1. Changes to `device.*` (host, port, poll_interval) are applied immediately on file save.
   2. Changes to `bot.token` and `bot.admin_user_ids` require a bot restart for security reasons.
   3. The `/reload` command triggers a config reload; only `device.*` changes take effect immediately.
   4. On invalid config reload, the bot retains the previous valid configuration and logs an error.

## 7. Background Execution and Polling
1. Polling must run according to the configured poll interval as closely as possible.
2. Use an in-process scheduler (e.g., cron job, interval timer, or async task) since the bot runs on a home server with full control over background processes.
3. The bot must survive restarts and resume polling from the last configured state.
4. If the home server restarts, restore the last known electricity state immediately (do not reset to N/A).
5. The poll interval for the next check begins only after the current connection attempt is closed.

## 8. Push Notifications on State Change
1. When electricity status changes (ON → OFF or OFF → ON):
   1. Send a message to all authorized users: "⚡ Electricity changed: [ON/OFF] at [HH:mm]."
   2. Include the current status and last check timestamp.
2. Avoid duplicate notifications for the same state change.
3. If a user recently checked status (within 30 seconds), skip notification to that user to avoid redundancy.

## 9. Error Handling
1. Network errors must not crash the bot.
2. If configuration is missing or invalid:
   1. Show N/A/unknown state until valid settings are loaded from config file.
   2. Log error with instructions to check `config.yaml`.
3. Log failures for troubleshooting (keep logs for last 24 hours only).
4. Handle Telegram API errors gracefully (retry with backoff, show user-friendly messages).
5. On config file parse error, retain previous valid configuration and log the error.

## 10. Authentication and Access Control
1. Authorized Telegram user IDs are defined in `config.yaml` under `bot.admin_user_ids`.
2. Deny all commands from unauthorized users with a message: "Access denied. Contact the bot administrator."
3. The bot token is read from `config.yaml` under `bot.token`.
4. No dynamic user management via bot commands — all access control is file-based.

## 11. Hosting and Deployment
1. The bot runs on a home server on the same network as the monitored electricity device.
2. The bot uses Telegram Bot API (long polling) to communicate with Telegram servers.
3. The bot must be configurable to run as:
   1. A standalone process (e.g., systemd service on Linux).
   2. A Docker container.
4. Include a `docker-compose.yml` for containerized deployment (optional but recommended).
5. Include a `config.yaml.example` file for configuration template (bot token, device settings, etc.).
6. The config file path defaults to `./config.yaml` in the working directory.

## 12. Data Storage
1. Use a local SQLite database for persistence:
   1. Electricity event log (status changes with timestamps).
   2. Electricity statistics (computed from event log).
2. Settings (IP, port, poll interval) and authorized user IDs are stored in `config.yaml`, NOT in the database.
3. Last known electricity state is stored in a JSON file (path configured via `server.last_state_file`) for state restoration on restart.
4. Database file stored locally on the home server.
5. Automatic cleanup of events older than 3 days.
6. Automatic cleanup of logs older than 24 hours.

## 13. Performance and Reliability
1. Connection check must release resources immediately after each attempt.
2. No persistent open socket after success or failure.
3. Battery/resource usage on the home server should be minimized.
4. Bot should remain stable during long-running operation (multiple days/weeks).
5. Implement graceful shutdown handling (save state, close connections).

## 14. Acceptance Criteria
1. Given valid IP/hostname, Port (in config.yaml), and reachable service, bot shows ON status within one polling cycle.
2. Given unreachable service, bot changes to OFF after exactly 2 consecutive failed checks.
3. Given service recovers after OFF, bot changes back to ON after exactly 2 consecutive successful checks.
4. Default poll interval is 60 seconds (from config.yaml).
5. Config file validation rejects poll interval outside 30 to 120 seconds.
6. Each successful connection is closed immediately.
7. Each check uses a timeout of up to 15 seconds.
8. Settings in config.yaml persist across bot restarts.
9. Bot shows N/A state and "N/A" timestamp before the first check completes.
10. "🔄 Refresh" inline button triggers an immediate TCP check and UI update.
11. Device configuration (host, port, poll_interval) is read from config.yaml, not from bot commands.
12. Poll interval for the next check begins only after the current connection attempt is closed.
13. Push notifications are sent on every state change to all authorized users.
14. Unauthorized users are denied access to all bot commands.
15. Event history is purged automatically after 3 days.
16. Config file changes to `device.*` fields are applied without bot restart.
17. Changes to `bot.token` or `bot.admin_user_ids` require a bot restart.

## 15. Nice-to-Have (Optional Future Enhancements)
1. Daily summary message (sent at a user-configured time) with previous day's electricity stats.
2. Optional Telegram notification (vibration/sound) on state change.
3. Multiple device monitoring (monitor multiple homes/devices).
4. Webhook mode support for production deployments.
5. Export event history as CSV.
6. Custom notification message templates.
7. Grafana/Metrics integration for external monitoring.
8. Telegram Story/Photo sharing on state change.
# Electricity Status Telegram Bot

A Telegram bot that monitors electricity availability by checking TCP connectivity to a local smart device (smart meter, UPS, or power monitor) and notifies authorized users of status changes.

## Features

- **Real-time Electricity Monitoring** - Checks device connectivity via TCP with configurable poll interval
- **Smart Status Detection** - Uses consecutive check logic (2 failures = OFF, 2 successes = ON) to avoid false positives
- **Push Notifications** - Alerts all authorized users when electricity status changes
- **Event History** - Stores status change history with duration tracking (auto-purged after 3 days)
- **Statistics** - View outage history via `/stats` command
- **Hot Config Reload** - Device settings update without bot restart via config file watcher
- **State Persistence** - Restores last known state on restart from JSON file
- **Docker Support** - Easy containerized deployment

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  Telegram    │────▶│  Bot API     │────▶│  Monitor  │
│  Users       │     │  (Long Poll) │     │  (TCP)    │
└─────────────┘     └──────────────┘     └───────────┘
                            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌───────────┐
                     │  Handlers    │     │  SQLite   │
                     │  & Notifier  │     │  Storage  │
                     └──────────────┘     └───────────┘
```

## Prerequisites

- Python 3.11 or higher
- Telegram Bot Token (get one from [@BotFather](https://t.me/BotFather))
- A network device with TCP service (smart meter, UPS, power monitor, etc.)

## Installation

### Option 1: Direct Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/AndriiKryvda/Electricity_Telegram_Bot.git
   cd Electricity_Telegram_Bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create configuration file:
   ```bash
   cp config.yaml.example config.yaml
   ```

4. Edit `config.yaml` with your settings (see Configuration section below).

5. Run the bot:
   ```bash
   python -m src.main
   ```

### Option 2: Docker Deployment

1. Clone the repository:
   ```bash
   git clone https://github.com/AndriiKryvda/Electricity_Telegram_Bot.git
   cd Electricity_Telegram_Bot
   ```

2. Create configuration file:
   ```bash
   cp config.yaml.example config.yaml
   ```

3. Edit `config.yaml` with your settings.

4. Build and start with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Configuration

Edit `config.yaml`:

```yaml
# Telegram Bot Settings
bot:
  token: "YOUR_BOT_TOKEN_HERE"          # Bot token from @BotFather
  admin_user_ids:                       # Authorized Telegram user IDs
    - 123456789                         # Get your ID from @userinfobot

# Home Device to Monitor
device:
  host: "192.168.1.100"                # IP address or hostname of the device
  port: 8080                           # TCP port (1-65535)
  poll_interval: 60                    # Check interval in seconds (30-120)

# Server Settings
server:
  last_state_file: "./data/last_state.json"  # Path for state persistence
```

### Configuration Options

| Setting | Description | Valid Range | Default |
|---------|-------------|-------------|---------|
| `bot.token` | Telegram bot API token | Non-empty string | Required |
| `bot.admin_user_ids` | Authorized Telegram user IDs | Positive integers | Empty |
| `device.host` | Device IP or hostname | Valid IPv4/hostname | `127.0.0.1` |
| `device.port` | Device TCP port | 1-65535 | `8080` |
| `device.poll_interval` | Check interval | 30-120 seconds | `60` |
| `server.last_state_file` | State file path | File path | `./data/last_state.json` |

## Bot Commands

| Command | Description |
|---------|-------------|
| `/status` | Show current electricity status |
| `/stats` | Show electricity status and outage history |
| `/reload` | Reload configuration file |
| `/help` | Show available commands |

## How It Works

### Status Detection

1. **TCP Check** - Bot attempts to connect to the configured device IP/port
2. **Connection closed immediately** after successful check
3. **Status Decision**:
   - **2 consecutive failures** → Electricity: OFF
   - **2 consecutive successes** → Electricity: ON
   - **Before threshold** → Electricity: Unknown

### Polling Cycle

1. TCP connection attempt (15s timeout)
2. On success/failure, state machine processes result
3. Wait for configured `poll_interval` seconds
4. Repeat

### Hot Configuration Reload

- Changes to `device.*` settings (host, port, poll_interval) take effect immediately
- Changes to `bot.*` settings (token, admin_user_ids) require a bot restart

## Data Storage

- **SQLite Database** (`./data/electricity.db`) - Status change event history
- **JSON State File** (`./data/last_state.json`) - Last known electricity state for restoration on restart
- Events older than 3 days are automatically purged

## Running as a Systemd Service (Linux)

1. Create `/etc/systemd/system/electricity-bot.service`:
   ```ini
   [Unit]
   Description=Electricity Status Telegram Bot
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/path/to/Electricity_Telegram_Bot
   ExecStart=/usr/bin/python -m src.main
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start:
   ```bash
   sudo systemctl enable electricity-bot
   sudo systemctl start electricity-bot
   ```

3. Check status:
   ```bash
   sudo systemctl status electricity-bot
   ```

## Troubleshooting

- **Bot not responding**: Verify bot token is correct and bot was created via @BotFather
- **Access denied**: Add your Telegram user ID to `admin_user_ids` in config.yaml
- **Status always Unknown**: Wait for 2 consecutive checks (up to 2x poll_interval seconds)
- **Config changes not applied**: Only `device.*` settings hot-reload; `bot.*` changes require restart

## License

MIT
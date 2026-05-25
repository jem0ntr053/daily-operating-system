# daily-operating-system

Minimal CLI for tracking daily non-negotiables: fasting, gym, app work, and music production.

## Install

```bash
pip install -e .
```

## Usage

### Core

```bash
day init                          # Create today's plan (auto-detects schedule)
day show                          # Display today's plan
day check fast                    # Mark fasting complete
day check gym                     # Mark gym complete
day check app                     # Mark app work complete
day check music                   # Mark music complete
day uncheck gym                   # Undo a check
day score                         # Show today's score (0-4)
```

### Set fields

```bash
day set focus "Deep work on auth" # Set today's focus
day set energy high               # Set energy level
day set sleep 7.5                 # Set sleep hours
```

### Manage tasks

```bash
day app add "Ship login"          # Add an app task
day app 1 done                    # Complete app task #1
day app 1 undo                    # Uncomplete app task #1
day music add "Mix verse 2"       # Add a music task
day music 1 done                  # Complete music task #1
```

### Notes

```bash
day note "Leg day felt strong"    # Add a note
```

### Views

```bash
day week                          # Scores for past 7 days
day summary                       # Current week Mon–Sun
day history                       # All tracked days
```

### Schedule profiles

The schedule and fasting window are auto-detected from the day of the week:

| Day       | Profile            | Fasting Window       |
|-----------|--------------------|----------------------|
| Mon–Thu   | Mon-Thu Standard   | 9:00 PM → 2:00 PM   |
| Friday    | Friday Flexible    | 11:00 PM → 4:00 PM  |
| Saturday  | Saturday No-Show   | 10:00 PM → 3:00 PM  |
| Sunday    | Sunday Reset       | 9:00 PM → 2:00 PM   |

Toggle show night on Friday or Saturday (preserves tasks, notes, and progress):

```bash
day tonight              # Toggle between show/no-show
day tonight show         # Switch to show night profile
day tonight off          # Switch back to regular profile
```

The web UI also shows a "Playing a show tonight?" toggle in the sidebar on Fri/Sat.

Override any day's profile manually:

```bash
day init --profile saturday_show
```

Available profiles: `weekday`, `friday`, `friday_show`, `saturday_show`, `saturday_no_show`, `sunday`

### Themes

Output is colorized using the Dracula palette by default. Switch themes with:

```bash
day config theme              # View current theme
day config theme nord         # Switch to Nord
```

Available themes: `dracula`, `catppuccin`, `gruvbox`, `nord`, `mono`

Theme preference is saved to `~/.dayctl/config.json`.

### Date targeting

All commands accept `--date` with a `YYYY-MM-DD` value, `today`, or `yesterday`:

```bash
day show --date yesterday
day check gym --date 2026-03-16
```

### Automation

Two launchd agents run in the background:

**Auto-init** — creates today's plan at 6:00 AM so it's ready before your earliest wake time.

**Schedule notifications** — sends a macOS notification 5 minutes before each schedule block.

```bash
# Install (already done if you followed setup)
cp scripts/com.dayos.autoinit.plist ~/Library/LaunchAgents/
cp scripts/com.dayos.notify.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dayos.autoinit.plist
launchctl load ~/Library/LaunchAgents/com.dayos.notify.plist

# Pause/resume notifications
launchctl unload ~/Library/LaunchAgents/com.dayos.notify.plist
launchctl load ~/Library/LaunchAgents/com.dayos.notify.plist

# Logs
cat /tmp/dayos-autoinit.log
cat /tmp/dayos-notify.log
```

### Calendar export

Generate `.ics` files for all 6 schedule profiles (importable into Apple/Google Calendar):

```bash
python export_calendars.py    # outputs to calendars/
```

## Data

Plans are stored as JSON in `~/.dayctl/days/`. Both `day` and `dayctl` work as commands.

## Run the web dashboard locally (macOS — free)

Run the FastAPI dashboard as a background service that auto-starts on login and restarts if it crashes. It binds `127.0.0.1:8000` (this Mac only — not exposed to your network), at no cost.

```bash
pip install -e '.[server]'

# 1. Install the LaunchAgent
cp scripts/com.dayos.web.plist ~/Library/LaunchAgents/
#    Edit ~/Library/LaunchAgents/com.dayos.web.plist:
#      - replace <DAYCTL_TOKEN> with a token you generate:  openssl rand -hex 24
#      - adjust the uvicorn path / WorkingDirectory if your checkout differs

# 2. Load it (starts now, on every login, and restarts on crash)
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist

# 3. First-time login (sets an auth cookie; afterwards just open http://127.0.0.1:8000)
open "http://127.0.0.1:8000/login?token=<DAYCTL_TOKEN>"
```

Manage the service:

```bash
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # stop
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dayos.web.plist   # start
```

Logs: `/tmp/dayos-web.log`. The dashboard shares data with the `day`/`dayctl` CLI (`~/.dayctl/`).

For a one-off foreground run (development):

```bash
DAYCTL_TOKEN=dev .venv/bin/uvicorn dayctl.server.app:create_app --factory --port 8000
```

> **Phone access:** the local service is `localhost`-only by design. Reaching it from a phone for free (via Tailscale) is tracked in [#11](../../issues/11). The paid always-on option is Fly.io, below.

## Remote deployment (Fly.io)

The FastAPI server can be deployed to Fly.io for phone access and push reminders via ntfy.sh.

1. `pip install -e '.[server]'` locally to verify the server boots.
2. `fly launch --no-deploy` (edit generated `fly.toml` to match the one in this repo, or accept ours).
3. `fly volumes create dayctl_data --size 1`
4. `fly secrets set DAYCTL_TOKEN=$(openssl rand -hex 32) NTFY_TOPIC=https://ntfy.sh/<your-private-topic>`
5. `fly deploy`
6. Open `https://<app>.fly.dev/login?token=<token>` on your phone and Add to Home Screen.

On your laptop, point the CLI at the server when you want shared state:

```
export DAYCTL_REMOTE=https://<app>.fly.dev
export DAYCTL_TOKEN=<token>
day today
```

Manual sync between local JSON and remote: `day push <date>` / `day pull <date>`.

### Reminders (ntfy.sh)

Set `NTFY_TOPIC` to a private ntfy topic URL (e.g., `https://ntfy.sh/longrandomstring`). Subscribe to the topic on your phone via the ntfy iOS/Android app. The server posts a notification at each schedule block boundary. Optional env: `NTFY_AUTH` (bearer token for protected topics), `DAYCTL_QUIET_UNTIL=YYYY-MM-DD` (suppress reminders through that date).

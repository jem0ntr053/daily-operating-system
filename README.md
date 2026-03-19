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

Override on Saturdays with a show:

```bash
day init --profile saturday_show
```

Available profiles: `weekday`, `friday`, `saturday_show`, `saturday_no_show`, `sunday`

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

## Data

Plans are stored as JSON in `~/.dayctl/days/`. Both `day` and `dayctl` work as commands.

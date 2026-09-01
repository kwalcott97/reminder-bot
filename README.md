# Lab duty reminder bot

Posts to `#general`, driven entirely by `schedule.csv`.

**Every Monday morning** — who is on duty this week:

```
*Lab duties for the week of September 14*

• *Autoclaving tips:* @Sam Ghaffari
• *Restock TC room:* @Keith W (for September)
```

**The 1st of the month** — the TC handover, on its own:

```
*TC stocker for October is @Anthony Khalifeh*
```

The whole thing is one Python file with no dependencies.

## The schedule

Both rotas live in `schedule.csv`, two pairs of columns side by side:

| Autoclaving tips | Date Assigned | Restock TC room | Date Assigned |
| --- | --- | --- | --- |
| @Cole Tharp | 8/31/26 | @Keith W | 9/1/26 |

Each date is the day that person's turn *starts*. The weekly dates are
Mondays; the monthly ones are the first of the month. The two columns are
independent, so the TC column can be much shorter than the other one.

To extend a rota, add rows — dates can be `9/7/26` or `2026-09-07`. If a
month has no row, the bot stays quiet on the 1st rather than
re-announcing last month's person as if they were new. After editing the
file, run `railway up` again to push it live.

## Previewing without posting

`--dry-run` prints the message instead of sending it, and `--date`
pretends it is any day you like:

```bash
python3 /Users/keith_tetrad/reminder-bot/reminder_bot.py --dry-run --date 2026-10-05
```

## Setup

**1. The Slack app.** At <https://api.slack.com/apps> create an app in
the lab's workspace, add the `chat:write` bot scope under *OAuth &
Permissions*, install it, and copy the bot token (`xoxb-…`). In Slack,
invite it to the channel: `/invite @your-bot-name` in `#general`.

**2. Member IDs, optional.** A bare `@Keith W` in a Slack message is just
text — a real ping needs the person's member ID (click their profile →
**⋮** → *Copy member ID*). Fill in `users.example.json` and give it to
the bot as the `SLACK_USER_MAP` variable below. Anyone left out falls
back to plain text, so you can add people gradually.

**3. Deploy to Railway.**

```bash
cd /Users/keith_tetrad/reminder-bot && railway login && railway init && railway up
```

Then add the token, which lives in Railway rather than in this folder:

```bash
railway variables --set "SLACK_BOT_TOKEN=xoxb-your-token-here"
```

`railway.json` tells Railway to run `python reminder_bot.py` once a day
at 16:00 UTC and then stop — 9am Pacific in summer, 8am in winter. The
bot decides whether that day deserves a message, so most days it prints
`Nothing to announce` and exits. `railway logs` shows what happened.

To post immediately instead of waiting for Monday:

```bash
railway run python3 reminder_bot.py --kind weekly
```

## Options

| Flag | Default | Purpose |
| --- | --- | --- |
| `--dry-run` | off | Print the message instead of posting it |
| `--date YYYY-MM-DD` | today | Pretend it is another day |
| `--kind` | `auto` | `auto` picks by date; `weekly` or `monthly` force one |
| `--channel` | `#general` | Where to post |
| `--schedule` | `schedule.csv` | Alternate rota file |

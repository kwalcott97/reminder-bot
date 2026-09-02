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
| Cole | 9/7/26 | Anthony | 9/1/26 |

Each date is the day that person's turn *starts*. The weekly dates are
Mondays; the monthly ones are the first of the month. The two columns are
independent, so the TC column can be much shorter than the other one.

To extend a rota, add rows — dates can be `9/7/26` or `2026-09-07`.
Lookups are exact: the weekly task matches the Monday itself, the monthly
one matches the calendar month. A week or month with no row reads as
*nobody assigned* rather than silently repeating whoever went last, and
the logs warn you. Push the change to GitHub and Railway redeploys.

## Previewing without posting

`--dry-run` prints the message instead of sending it, and `--date`
pretends it is any day you like:

```bash
python3 /Users/keith_tetrad/reminder-bot/reminder_bot.py --dry-run --date 2026-10-05
```

## Setup

**1. The Slack app.** At <https://api.slack.com/apps> choose *Create New
App → From an app manifest*, pick the lab's workspace, and paste in
`slack-app-manifest.yaml` from this folder — that sets the name and the
one permission it needs (`chat:write`). Install it, then copy the **Bot
User OAuth Token** (`xoxb-…`) from *OAuth & Permissions*. Finally, in
Slack, invite it to the channel: `/invite @reminder-bot` in `#general`.

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

**Why `--only-at-hour 16` is in the start command:** Railway reruns the
container on *every* deploy, not just on the schedule. Without the guard,
deploying on a Monday or the 1st posts a duplicate. With it, a deploy at
any other time logs `not a scheduled run` and stays quiet. If you ever
change `cronSchedule`, change the guard to match.

The logs also carry health warnings that never reach Slack: anyone in the
schedule with no Slack ID, and a heads-up when either rota is within
three weeks of running out.

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
| `--only-at-hour H` | off | Exit unless the clock reads hour H — stops deploys from posting duplicates |
| `--channel` | `#general` | Where to post |
| `--schedule` | `schedule.csv` | Alternate rota file |

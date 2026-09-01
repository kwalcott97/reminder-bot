#!/usr/bin/env python3
"""Post the lab-duty reminders to Slack.

Two messages, both driven by schedule.csv: the weekly duty roundup every
Monday, and a one-line note naming the new TC stocker on the 1st of each
month. Run daily at 9am and it picks whichever applies to that day.
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCHEDULE = os.path.join(HERE, "schedule.csv")
DEFAULT_USER_MAP = os.path.join(HERE, "users.json")
SLACK_URL = "https://slack.com/api/chat.postMessage"

WEEKLY_TASK = "Autoclaving tips"
MONTHLY_TASK = "Restock TC room"
# What the 1st-of-the-month announcement calls the job.
MONTHLY_ROLE = "TC stocker"


class ScheduleError(Exception):
    pass


def load_schedule(path):
    """Return (weekly, monthly) as lists of (date, name), sorted by date.

    The CSV holds two independent rotas side by side: columns 0/1 are the
    weekly task and its start date, columns 2/3 the monthly one. Either
    column pair may run out of rows before the other.
    """
    weekly, monthly = [], []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise ScheduleError("%s is empty" % path)

    for lineno, row in enumerate(rows[1:], start=2):
        row = [cell.strip() for cell in row] + [""] * 4
        for name, date_str, bucket in (
            (row[0], row[1], weekly),
            (row[2], row[3], monthly),
        ):
            if not name and not date_str:
                continue
            if not name or not date_str:
                raise ScheduleError(
                    "%s line %d: name and date must both be filled in "
                    "(got name=%r date=%r)" % (path, lineno, name, date_str)
                )
            bucket.append((parse_date(date_str, path, lineno), clean_name(name)))

    for bucket, label in ((weekly, WEEKLY_TASK), (monthly, MONTHLY_TASK)):
        if not bucket:
            raise ScheduleError("no assignments found for %s in %s" % (label, path))
        bucket.sort(key=lambda pair: pair[0])
    return weekly, monthly


def parse_date(value, path, lineno):
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ScheduleError(
        "%s line %d: could not read the date %r (expected e.g. 9/7/26)"
        % (path, lineno, value)
    )


def clean_name(name):
    return name.strip().lstrip("@").strip()


def monday_of(day):
    return day - dt.timedelta(days=day.weekday())


def assignment_on(schedule, day):
    """The entry in effect on `day`: the latest one that has already started."""
    current = None
    for start, name in schedule:
        if start <= day:
            current = (start, name)
        else:
            break
    return current


def weekly_assignment(schedule, monday):
    """Prefer the row dated exactly this Monday, else whatever is in effect."""
    for start, name in schedule:
        if start == monday:
            return (start, name)
    return assignment_on(schedule, monday)


def next_assignment(schedule, day):
    for start, name in schedule:
        if start > day:
            return (start, name)
    return None


def load_user_map(path):
    """Optional {"Keith W": "U01ABCDEF"} map so mentions actually ping.

    Comes from $SLACK_USER_MAP when set, so a hosted deploy needs no file;
    otherwise from `path` on disk.
    """
    source = "$SLACK_USER_MAP"
    try:
        inline = os.environ.get("SLACK_USER_MAP", "").strip()
        if inline:
            raw = json.loads(inline)
        elif os.path.exists(path):
            source = path
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        else:
            return {}
    except (ValueError, OSError) as exc:
        # A broken map costs pings, not the reminder itself — carry on.
        print("Ignoring the user map from %s: %s" % (source, exc), file=sys.stderr)
        return {}
    return {clean_name(k).lower(): v.strip() for k, v in raw.items()}


def mention(name, user_map):
    user_id = user_map.get(name.lower())
    if user_id:
        return "<@%s>" % user_id
    return "@%s" % name


def build_weekly_message(monday, weekly, monthly, user_map):
    """Return the Monday roundup for the week beginning `monday`."""
    lines = [
        "*Lab duties for the week of %s*" % monday.strftime("%B %-d"),
        "",
    ]

    this_week = weekly_assignment(weekly, monday)
    if this_week:
        lines.append("• *%s:* %s" % (WEEKLY_TASK, mention(this_week[1], user_map)))
    else:
        lines.append("• *%s:* _nobody assigned — the rota needs updating_" % WEEKLY_TASK)

    this_month = assignment_on(monthly, monday)
    if this_month:
        lines.append(
            "• *%s:* %s (for %s)"
            % (
                MONTHLY_TASK,
                mention(this_month[1], user_map),
                this_month[0].strftime("%B"),
            )
        )
    else:
        upcoming = next_assignment(monthly, monday)
        if upcoming:
            lines.append(
                "• *%s:* %s starts %s"
                % (
                    MONTHLY_TASK,
                    mention(upcoming[1], user_map),
                    upcoming[0].strftime("%B %-d"),
                )
            )
        else:
            lines.append(
                "• *%s:* _nobody assigned — the rota needs updating_" % MONTHLY_TASK
            )

    return "\n".join(lines)


def build_monthly_message(today, monthly, user_map):
    """Return the 1st-of-the-month announcement, or None if nobody is on."""
    current = assignment_on(monthly, today)
    if not current:
        return None
    return "*%s for %s is %s*" % (
        MONTHLY_ROLE,
        today.strftime("%B"),
        mention(current[1], user_map),
    )


def post_to_slack(token, channel, text):
    payload = json.dumps(
        {
            "channel": channel,
            "text": text,
            # Turns plain "@name" fallbacks into real mentions when the
            # name happens to match a Slack handle.
            "link_names": True,
            "unfurl_links": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        SLACK_URL,
        data=payload,
        headers={
            "Authorization": "Bearer %s" % token,
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError("Slack rejected the message: %s" % body.get("error", body))
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", default=DEFAULT_SCHEDULE)
    parser.add_argument("--users", default=DEFAULT_USER_MAP)
    parser.add_argument(
        "--channel",
        default=os.environ.get("SLACK_CHANNEL", "#general"),
        help="channel name or ID (default: $SLACK_CHANNEL or #general)",
    )
    parser.add_argument(
        "--date",
        help="pretend today is this YYYY-MM-DD date; useful for previewing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the message instead of posting it",
    )
    parser.add_argument(
        "--kind",
        choices=("auto", "weekly", "monthly", "both"),
        default="auto",
        help="which message to send; auto (the default) sends the weekly "
        "roundup on Mondays and the TC stocker note on the 1st",
    )
    args = parser.parse_args(argv)

    today = (
        dt.datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else dt.date.today()
    )

    try:
        weekly, monthly = load_schedule(args.schedule)
    except (ScheduleError, OSError) as exc:
        print("Could not read the schedule: %s" % exc, file=sys.stderr)
        return 1
    user_map = load_user_map(args.users)

    messages = []
    if args.kind in ("weekly", "both") or (args.kind == "auto" and today.weekday() == 0):
        messages.append(
            ("weekly", build_weekly_message(monday_of(today), weekly, monthly, user_map))
        )
    if args.kind in ("monthly", "both") or (
        # Only on the 1st, and only when someone's turn actually starts today
        # — otherwise a month missing from the CSV would re-announce the
        # previous month's person as if they were new.
        args.kind == "auto"
        and today.day == 1
        and any(start == today for start, _ in monthly)
    ):
        messages.append(("monthly", build_monthly_message(today, monthly, user_map)))

    messages = [(kind, text) for kind, text in messages if text]
    if not messages:
        print("Nothing to announce on %s" % today)
        return 0

    if args.dry_run:
        print("\n\n".join(text for _, text in messages))
        return 0

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("SLACK_BOT_TOKEN is not set", file=sys.stderr)
        return 1
    for kind, text in messages:
        try:
            post_to_slack(token, args.channel, text)
        except (urllib.error.URLError, RuntimeError) as exc:
            print("Could not post the %s message: %s" % (kind, exc), file=sys.stderr)
            return 1
        print("Posted the %s message for %s to %s" % (kind, today, args.channel))
    return 0


if __name__ == "__main__":
    sys.exit(main())

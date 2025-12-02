import datetime


def format_timedelta(td: datetime.timedelta) -> str:
    total_us = int(td.total_seconds() * 1_000_000)
    sign = "-" if total_us < 0 else ""
    total_us = abs(total_us)

    # Break down
    us = total_us % 1_000_000
    total_seconds = total_us // 1_000_000

    days, seconds = divmod(total_seconds, 24 * 3600)
    years, days = divmod(days, 365)   # choose your definition of "year"

    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    ms, us = divmod(us, 1000)

    # Build parts
    parts = []

    if years:
        parts.append(f"{years}y")
    if days:
        parts.append(f"{days}d")

    # Time: HH:MM:SS.mmmuuu
    time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
    if ms or us:
        time_str += f".{ms:03}{us:03}"
    parts.append(time_str)

    return sign + " ".join(parts)

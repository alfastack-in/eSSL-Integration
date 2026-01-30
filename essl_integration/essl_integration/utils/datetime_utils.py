import datetime

import frappe


def now_datetime():
    # Frappe returns timezone-aware in user's tz; this is OK for Employee Checkin time storage
    return frappe.utils.now_datetime()


def to_soap_format(dt):
    # SOAP needs: YYYY-MM-DD HH:mm (no seconds)
    return dt.strftime("%Y-%m-%d %H:%M")


def clamp_start_datetime(start_dt, max_days_per_call):
    # ensures a call does not exceed max_days_per_call
    if not max_days_per_call:
        return start_dt

    if max_days_per_call < 1:
        return start_dt

    delta = datetime.timedelta(days=max_days_per_call)
    min_dt = now_datetime() - delta

    if start_dt < min_dt:
        return min_dt

    return start_dt


def subtract_minutes(dt, minutes):
    if not minutes:
        return dt
    if minutes < 0:
        return dt

    delta = datetime.timedelta(minutes=minutes)
    return dt - delta


def add_days(dt, days):
    if not days:
        return dt
    delta = datetime.timedelta(days=days)
    return dt + delta
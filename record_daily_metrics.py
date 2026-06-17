#!/usr/bin/env python3
"""
Pull yesterday's traffic from GA4 and record it in Supabase (daily_metrics).
The Supabase write also keeps the free project from pausing.
"""

import os
import json
import datetime
import requests
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric

# Config comes from GitHub Actions secrets
GA4_PROPERTY_ID = os.environ["GA4_PROPERTY_ID"]              
GA_CREDS_JSON   = os.environ["GA_SERVICE_ACCOUNT_JSON"]      
SUPABASE_URL    = os.environ["SUPABASE_URL"]                
SUPABASE_KEY    = os.environ["SUPABASE_SERVICE_ROLE_KEY"]   

yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def pull_ga4():
    """Return (pageviews, users, sessions, raw_dict) for yesterday."""
    creds = service_account.Credentials.from_service_account_info(
        json.loads(GA_CREDS_JSON),
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
        metrics=[
            Metric(name="screenPageViews"),  # pageviews
            Metric(name="totalUsers"),       # unique visitors
            Metric(name="sessions"),         # sessions
        ],
    )
    resp = client.run_report(request)

    if not resp.rows:
        # No traffic rows (rare). Record zeros so the day is still logged.
        return 0, 0, 0, {"note": "no rows returned by GA4"}

    vals = resp.rows[0].metric_values
    pageviews = int(vals[0].value)
    users     = int(vals[1].value)
    sessions  = int(vals[2].value)
    raw = {"screenPageViews": pageviews, "totalUsers": users, "sessions": sessions}
    return pageviews, users, sessions, raw


def record_in_supabase(pageviews, users, sessions, raw):
    """Call the record_daily_metric function, which upserts one row per day."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/record_daily_metric"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "p_metric_date": yesterday,
        "p_pageviews": pageviews,
        "p_unique_visitors": users,
        "p_sessions": sessions,
        "p_source": "ga4",
        "p_raw_payload": raw,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    print(f"Recorded {yesterday}: pageviews={pageviews} users={users} sessions={sessions}")


def main():
    pv, users, sessions, raw = pull_ga4()
    record_in_supabase(pv, users, sessions, raw)


if __name__ == "__main__":
    main()

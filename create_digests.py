#!/usr/bin/env python
import sys
from digestif.models import Subscription
from digestif import processes
from datetime import datetime

if __name__ == "__main__":
    today = None
    previous = None
    if len(sys.argv) > 1:
        previous = datetime.strptime(sys.argv[1], "%Y%m%d")
        today = datetime.strptime(sys.argv[2], "%Y%m%d")

    for subscription in Subscription.query.all():
        if subscription.active and subscription.frequency != 0:
            digest = processes.create_digest(subscription, previous_dt=previous, today_dt=today)

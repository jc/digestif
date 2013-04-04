#!/usr/bin/env python
import sys
from digestif.models import Subscription
from digestif import processes

if __name__ == "__main__":
    for subscription in Subscription.query.all():
        digest = processes.create_digest(subscription)

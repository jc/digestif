#!/usr/bin/env python
import sys
from datetime import datetime

from digestif.models import Publication
from digestif import processes

if __name__ == "__main__":
    since = None
    if len(sys.argv) > 1:
        since = datetime.strptime(sys.argv[1], "%Y%m%d")
            
    for pub in Publication.query.all():
        processes.retrieve_photos(pub, since=since)

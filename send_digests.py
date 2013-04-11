#!/usr/bin/env python
import sys
from digestif import app
from digestif.models import Digest
from digestif import processes

if __name__ == "__main__":
    for digest in Digest.query.filter(Digest.delivered == False).all():
        processes.send_digest(digest, app.jinja_env)

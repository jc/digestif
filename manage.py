#!/usr/bin/env python

from flask.ext.script import Manager

from datetime import datetime

from digestif import app
from digestif.models import Stream, Subscription, Digest
from digestif import processes
from digestif import db

manager = Manager(app)

@manager.command
def db_drop():
    "Drops database tables"
    if prompt_bool("Are you sure you want to lose all your data"):
        db.drop_all()


@manager.command
def db_create():
    "Creates database tables from sqlalchemy models"
    db.create_all()

@manager.command
def update(since=None):
    "Retrieves new photographs from streams"
    if since:
        since = datetime.strptime(sys.argv[1], "%Y%m%d")

    for stream in Stream.query.all():
        processes.retrieve_photos(stream, since=since)

@manager.command
def generate(today=None, previous=None):
    "Grenerates new digests"
    if previous:
        previous = datetime.strptime(sys.argv[1], "%Y%m%d")
    if today:
        today = datetime.strptime(sys.argv[2], "%Y%m%d")

    for subscription in Subscription.query.all():
        if subscription.active and subscription.frequency != 0:
            digest = processes.create_digest(subscription, previous_dt=previous, today_dt=today)

@manager.command
def send():
    "Sends unsent digets"
    for digest in Digest.query.filter(Digest.delivered == False).all():
        processes.send_digest(digest, app.jinja_env)

if __name__ == "__main__":
    manager.run()
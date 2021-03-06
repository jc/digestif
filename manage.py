#!/usr/bin/env python

from flask.ext.script import Manager, prompt_bool

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
        since = datetime.strptime(since, "%Y%m%d")

    for stream in Stream.query.all():
        try:
            processes.retrieve_photos(stream, since=since)
        except:
            app.logger.error("Error updating stream: {}".format(stream.id), exc_info=True)

@manager.command
def generate(today=None, previous=None, imprecise=False):
    "Grenerates new digests"
    if previous:
        previous = datetime.strptime(previous, "%Y%m%d")
    if today:
        today = datetime.strptime(today, "%Y%m%d")
    if imprecise:
        # utc then an attempt to make it close for EST morning
        today = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)

    for subscription in Subscription.query.all():
        if subscription.active and subscription.frequency != 0:
            try:
                digest = processes.create_digest(subscription, previous_dt=previous, today_dt=today)
            except:
                app.logger.error("Error generating digest for subscription: {}".format(subscription.id), exc_info=True)

@manager.command
def send():
    "Sends unsent digest"
    for digest in Digest.query.filter(Digest.delivered == False).all():
        try:
            processes.send_digest(digest, app.jinja_env)
        except:
            app.logger.error("Error sending digest: {}".format(digest.id), exc_info=True)

@manager.command
def stream_welcome(streamid):
    "Sends the welcome for a new stream"
    stream = Stream.query.filter(Stream.id == streamid).first()
    if stream:
        user = stream.user
        processes.send_stream(user, stream, app.jinja_env)

@manager.command
def subscription_welcome(subscriptionid):
    "Sends the welcome for a new subscription"
    subscription = Subscription.query.filter(Subscription.id == subscriptionid).first()
    if subscription:
        stream = subscription.stream
        processes.send_welcome(subscription, stream, app.jinja_env)


if __name__ == "__main__":
    manager.run()

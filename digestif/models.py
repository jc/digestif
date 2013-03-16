import datetime

from digestif import db

def generate_secret():
    return "secret"


class Publisher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret = db.Column(db.String)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    publications = db.relationship("Publication", backref="publisher")

class Publication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    oauth_token = db.Column(db.String, nullable=False)
    oauth_token_secret = db.Column(db.String, nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey("publisher.id"))
    remote_id = db.Column(db.String, nullable=False)
    service = db.Column(db.Integer, nullable=False)
    processes = db.relationship("ExternalProcess", backref="publication", order_by="ExternalProcess.date")

class ExternalProcess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.Integer, db.ForeignKey("publication.id"))
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    successful = db.Column(db.Boolean, nullable=False)

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret = db.Column(db.String)
    email = db.Column(db.String, unique=True)
    
class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey("subscriber.id"))
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"))
    frequency = db.Column(db.Integer, nullable=False)

class Digest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"))
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    
    
class Entry(object):
    def __init__(self, d):
        self.d = d
    def __getattr__(self, attr):
        return self.d[attr]


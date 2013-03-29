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
    last_updated = db.Column(db.DateTime)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    processes = db.relationship("ExternalProcess", backref="publication", order_by="ExternalProcess.date")

class ExternalProcess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pub_id = db.Column(db.Integer, db.ForeignKey("publication.id"))
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    successful = db.Column(db.Boolean, nullable=False)
    msg = db.Column(db.String)

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
    end_date = db.Column(db.DateTime, default=datetime.datetime.now)
    start_date = db.Column(db.DateTime)

class FlickrPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publication_id = db.Column(db.Integer, db.ForeignKey("publication.id"))
    date_uploaded = db.Column(db.DateTime, nullable=False)
    date_taken = db.Column(db.DateTime, nullable=False)
    date_fetched = db.Column(db.DateTime, default=datetime.datetime.now)
    farm = db.Column(db.Integer)
    server = db.Column(db.Integer)
    secret = db.Column(db.String)
    title = db.Column(db.String)
    description = db.Column(db.String)
    remote_id = db.Column(db.String)
    video = db.Column(db.Boolean)
    
class Entry(object):
    def __init__(self, d):
        self.d = d
    def __getattr__(self, attr):
        return self.d[attr]


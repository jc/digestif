import datetime

from digestif import db

def generate_secret():
    return "secret"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret = db.Column(db.String)
    email = db.Column(db.String, unique=True)
    created = db.Column(db.DateTime, default=datetime.datetime.now)

class Stream(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    oauth_token = db.Column(db.String, nullable=False)
    oauth_token_secret = db.Column(db.String, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    service = db.Column(db.Integer, nullable=False)
    foreign_key = db.Column(db.String, nullable=False)
    last_updated = db.Column(db.DateTime)
    last_checked = db.Column(db.DateTime)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    authorized = db.Column(db.Boolean)
 
class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    stream_id = db.Column(db.Integer, db.ForeignKey("stream.id"))
    frequency = db.Column(db.Integer, nullable=False)
    last_digest = db.Column(db.DateTime)

class Digest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"))
    end_date = db.Column(db.DateTime, default=datetime.datetime.now)
    start_date = db.Column(db.DateTime)
    delivered = db.Column(db.Boolean, default=False)
    opened = db.Column(db.Boolean, default=False)

class FlickrPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey("stream.id"))
    date_uploaded = db.Column(db.DateTime, nullable=False)
    date_taken = db.Column(db.DateTime, nullable=False)
    date_fetched = db.Column(db.DateTime, default=datetime.datetime.now)
    farm = db.Column(db.Integer)
    server = db.Column(db.Integer)
    secret = db.Column(db.String)
    title = db.Column(db.String)
    description = db.Column(db.String)
    foreign_key = db.Column(db.String)
    video = db.Column(db.Boolean)
    



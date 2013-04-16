import datetime

from digestif import db
from digestif.constants import *

def generate_secret():
    return "secret"


class Base(object):
    def __repr__(self):
        return "<{0}: {1}>".format(self.__class__.__name__,
                                  ", ".join(["%s=%r" % (key, getattr(self, key)) 
                                             for key in sorted(self.__dict__.keys()) 
                                             if not key.startswith('_')]))

class User(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret = db.Column(db.String)
    email = db.Column(db.String, unique=True)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    
class Stream(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    oauth_token = db.Column(db.String, nullable=False)
    oauth_token_secret = db.Column(db.String, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    service = db.Column(db.Integer, nullable=False)
    foreign_key = db.Column(db.String, nullable=False)
    last_updated = db.Column(db.DateTime)
    last_checked = db.Column(db.DateTime)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    authorized = db.Column(db.Boolean)
    user = db.relationship("User")
 
class Subscription(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey("stream.id"), nullable=False)
    frequency = db.Column(db.Integer, nullable=False)
    last_digest = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    user = db.relationship("User")
    stream = db.relationship("Stream")


class Digest(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"), nullable=False)
    end_date = db.Column(db.DateTime, default=datetime.datetime.now)
    start_date = db.Column(db.DateTime)
    delivered = db.Column(db.Boolean, default=False)
    opened = db.Column(db.Boolean, default=False)
    subscription = db.relationship("Subscription")

class FlickrPhoto(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey("stream.id"), nullable=False)
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
    stream = db.relationship("Stream")
    

def make_user(email, user=None):
    """ Make or get user by email address """
    if not user:
        user = User.query.filter_by(email=email).first()
    elif user.email != email:
        user.email = email
        db.session.commit()
        print "updated user", user.id, user.email
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
        print "creted user", user.id, user.email
    return user

def make_subscription(stream, user, frequency):
    """ Make or get or update subscription by frequency, user, stream """
    subscription = Subscription.query.filter(Subscription.user_id == user.id, 
                              Subscription.stream_id == stream.id).first()
    if not subscription:
        subscription = Subscription(user_id=user.id, stream_id=stream.id,
                                    frequency=frequency, last_digest=datetime.datetime.now())
        db.session.add(subscription)
        db.session.commit()
        print "created subscription", subscription.id, subscription.user_id, subscription.stream_id
    elif subscription.frequency != frequency:
        subscription.frequency = frequency
        db.session.add(subscription)
        db.session.commit()
        print "update subscription frequency", subscription.id, subscription.user_id, subscription.stream_id
    return subscription

def make_stream(foreign_key, user, oauth_token, oauth_token_secret, last_checked=None): 
    stream = Stream.query.filter_by(foreign_key=foreign_key).first()
    if not stream:
        stream = Stream(user_id=user.id, oauth_token=oauth_token,
                        oauth_token_secret=oauth_token_secret, foreign_key=foreign_key,
                        service=FLICKR)
        if last_checked:
            stream.last_checked = last_checked
        db.session.add(stream)
        db.session.commit()
        print "created stream", stream.id, stream.foreign_key
    elif stream.oauth_token != oauth_token and stream.oauth_token_secret != oauth_token_secret:
        stream.oauth_token = oauth_token
        stream.oauth_token_secret = oauth_token_secret
        db.session.commit()
    return stream
        


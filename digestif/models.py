import datetime

from flask import url_for
from werkzeug.routing import BuildError

from digestif import db, app
from digestif.constants import *
from digestif import hash_gen


def generate_secret():
    return "secret"

def permalink(function):
    def inner(*args, **kwargs):
        endpoint, values = function(*args, **kwargs)
        try:
            return url_for(endpoint, **values)
        except BuildError:
            return
    return inner


class Base(object):
    def __repr__(self):
        return "<{0}: {1}>".format(self.__class__.__name__,
                                  ", ".join(["%s=%r" % (key, getattr(self, key)) 
                                             for key in sorted(self.__dict__.keys()) 
                                             if not key.startswith('_')]))

class User(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    secret = db.Column(db.String(25))
    email = db.Column(db.String(255), unique=True)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    
class Stream(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    oauth_token = db.Column(db.String(255), nullable=False)
    oauth_token_secret = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    service = db.Column(db.Integer, nullable=False)
    foreign_key = db.Column(db.String(255), nullable=False)
    last_updated = db.Column(db.DateTime)
    last_checked = db.Column(db.DateTime)
    created = db.Column(db.DateTime, default=datetime.datetime.now)
    authorized = db.Column(db.Boolean)
    user = db.relationship("User")

    @permalink
    def subscribe_url(self):
        encoded = hash_gen.encrypt(self.user_id, self.id)
        return 'subscribe', {'stream_encoded': encoded}

    def remote_url(self):
        from digestif import processes
        if self.service == FLICKR:
            return "http://www.flickr.com/photos/{}".format(self.foreign_key)
        elif self.service == INSTAGRAM:
            return "http://instagram.com/{}".format(processes.instagram_metadata(self, True))
        return "/"

 
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
    secret = db.Column(db.String(255))
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    foreign_key = db.Column(db.String(255))
    video = db.Column(db.Boolean)
    stream = db.relationship("Stream")
    
class InstagramPhoto(Base, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey("stream.id"), nullable=False)
    date_taken = db.Column(db.DateTime, nullable=False) #created_time
    date_uploaded = db.Column(db.DateTime, nullable=False) #created_time
    date_fetched = db.Column(db.DateTime, default=datetime.datetime.now)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    foreign_key = db.Column(db.String(255))
    low_resolution = db.Column(db.String(255))
    standard_resolution = db.Column(db.String(255))
    thumbnail = db.Column(db.String(255))
    video = db.Column(db.Boolean)
    link = db.Column(db.String(255))
    stream = db.relationship("Stream")    

def make_user(email, user=None):
    """ Make or get user by email address """
    if not user:
        user = User.query.filter_by(email=email).first()
    elif user.email != email:
        user.email = email
        db.session.commit()
        app.logger.info("updated user id: %s, email: %s" % (user.id, user.email))
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
        app.logger.info("created user id: %s, email: %s" % (user.id, user.email))
    return user

def make_subscription(stream, user, frequency):
    """ Make or get or update subscription by frequency, user, stream """
    subscription = Subscription.query.filter(Subscription.user_id == user.id, 
                              Subscription.stream_id == stream.id).first()
    if not subscription:
        subscription = Subscription(user_id=user.id, stream_id=stream.id,
                                    frequency=frequency, last_digest=datetime.datetime.now() - datetime.timedelta(days=frequency))
        db.session.add(subscription)
        db.session.commit()
        app.logger.info("created subscription id: %s, user id: %s, stream id: %s" % (subscription.id, subscription.user_id, subscription.stream_id))
    elif subscription.frequency != frequency:
        subscription.frequency = frequency
        db.session.add(subscription)
        db.session.commit()
        app.logger.info("updated subscription frequency id: %s, user id: %s, stream id: %s" % (subscription.id, subscription.user_id, subscription.stream_id))
    return subscription

def make_stream(foreign_key, user, oauth_token, oauth_token_secret, last_checked=None, service=FLICKR): 
    stream = Stream.query.filter_by(foreign_key=foreign_key).first()
    if not stream:
        stream = Stream(user_id=user.id, oauth_token=oauth_token,
                        oauth_token_secret=oauth_token_secret, foreign_key=foreign_key,
                        service=service)
        if last_checked:
            stream.last_checked = last_checked
        db.session.add(stream)
        db.session.commit()
        app.logger.info("created stream id: %s, key: %s" % (stream.id, stream.foreign_key))
    elif stream.oauth_token != oauth_token and stream.oauth_token_secret != oauth_token_secret:
        stream.oauth_token = oauth_token
        stream.oauth_token_secret = oauth_token_secret
        db.session.commit()
    return stream
        

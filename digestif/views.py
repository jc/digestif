import re
from datetime import datetime
from datetime import timedelta

from flask import session, request, g, redirect, url_for, abort, render_template, flash
from flask_oauth import OAuthException

from jinja2 import evalcontextfilter, Markup

import premailer 
import short_url

from digestif import app
from digestif import flickr_oauth
from digestif.models import User, Stream, FlickrPhoto, Subscription, Digest
from digestif import db
from digestif import processes
from digestif.constants import *



@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    #pass return (token, secret) or None
    return token

@app.route('/subscribe/flickr')
def login():
    return flickr_oauth.authorize(callback=url_for('oauth_flickr_authorized', \
      next=request.args.get('next') or request.referrer or None))

@app.route('/flickr/oauth-authorized')
@flickr_oauth.authorized_handler
def oauth_flickr_authorized(resp):
    next_url = request.args.get('next') or url_for('index')
    if resp is None:
        flash(u'You denied the request to sign in.')
        return redirect(next_url)

    remote_id = resp["user_nsid"]
    stream = Stream.query.filter_by(foreign_key=remote_id).first()

    if not stream:
        user = User()
        stream = Stream(oauth_token=resp["oauth_token"], 
                        oauth_token_secret=resp["oauth_token_secret"],
                        user_id=user.id, foreign_key=remote_id, service=FLICKR)
        stream.last_checked = datetime.utcnow()
        db.session.add(user)
        db.session.add(stream)
    if stream.oauth_token != resp["oauth_token"] or stream.oauth_token_secret != resp["oauth_token_secret"]:
        stream.oauth_token = resp["oauth_token"]
        stream.oauth_token_secret = resp["oauth_token_secret"]
        db.session.add(stream)
    db.session.commit()
    return redirect(url_for('subscribe', externalid=stream.id))

#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>%s</p><p>%s</p><p>%s</p>" % (error.message, error.type, error.data)

@app.route("/subscribe/<externalid>/<email>")
def subscribe(externalid, email):
    stream = Stream.query.filter_by(id=externalid).first()
    if not stream:
        return "Unknown stream"
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
        print "created user", user.id
    subscription = Subscription.query.filter(Subscription.user_id == user.id, 
                              Subscription.stream_id == stream.id).first()
    if not subscription:
        subscription = Subscription(user_id=user.id, stream_id=stream.id,
                                    frequency=4, last_digest=datetime(2010, 01, 01))
        db.session.add(subscription)
        db.session.commit()
        print "created subscription", subscription.id
    db.session.commit()
    return "subscribed to %s?" % (stream.foreign_key)

@app.route("/")
def index():
    return "Hello World!"

@app.route("/digest/<digest_encoded>")
def display_digest(digest_encoded):
    digest_id = short_url.decode_url(digest_encoded)
    digest = Digest.query.filter_by(id=digest_id).first()
    if not digest:
        return "Unknown digest"
    subscription = Subscription.query.filter_by(id=digest.subscription_id).first()
    if not subscription:
        return "Unknown subscription"
    stream = Stream.query.filter_by(id=subscription.stream_id).first()
    entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > digest.start_date,
                                       FlickrPhoto.date_uploaded <= digest.end_date,
                                       FlickrPhoto.stream_id == stream.id).order_by(FlickrPhoto.date_uploaded).all()
    meta = {"stream" : stream, "digest_encoded" : digest_encoded}
    return render_template("show_entries.html", entries=entries, email=None, meta=meta)

@app.route("/view/<username>/<previous>/<frequency>/<today>")
def digest_dt(username, previous, frequency, today):
    previous_dt = datetime.strptime(previous, "%Y%m%d")
    today_dt = datetime.strptime(today, "%Y%m%d")
    frequency_td = timedelta(days=int(frequency))
    if today_dt - previous_dt < frequency_td:
        return "Too soon since last check!"
    entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > previous_dt,
                                       FlickrPhoto.date_uploaded <= today_dt,
                                       FlickrPhoto.stream_id == username).order_by(FlickrPhoto.date_uploaded).all()
    stream = Stream.query.filter(Stream.id == username).first()
    meta = {"username" : username, "previous" : previous,
            "frequency" : frequency, "today" : today,
            "stream" : stream }
    return render_template("show_entries.html", entries=entries, email=None, meta=meta)

@app.route("/email/<username>/<previous>/<frequency>/<today>")
def email_digest(username, previous, frequency, today):
    previous_dt = datetime.strptime(previous, "%Y%m%d")
    today_dt = datetime.strptime(today, "%Y%m%d")
    frequency_td = timedelta(days=int(frequency))
    if today_dt - previous_dt < frequency_td:
        return "Too soon since last check!"
    entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > previous_dt,
                                       FlickrPhoto.date_uploaded <= today_dt,
                                       FlickrPhoto.stream_id == username).order_by(FlickrPhoto.date_uploaded).all()
    stream = Stream.query.filter(Stream.id == username).first()
    meta = {"username" : username, "previous" : previous,
            "frequency" : frequency, "today" : today,
            "stream" : stream }

    return premailer.transform(render_template("show_entries.html", entries=entries, meta=meta, email=True))

@app.template_filter("imgurl")
def imgurl_filter(value, meta=None, email=False):
    if email:
        return "http://farm%s.staticflickr.com/%s/%s_%s.jpg" % (value.farm, value.server, value.foreign_key, value.secret)
    size = "z"
    if value.date_uploaded >= datetime(2012, 03, 01):
        size = "c"
    return "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg" % (value.farm, value.server, value.foreign_key, value.secret, size)

@app.template_filter("permalink")
def permalink_filter(value, meta=None, email=False):
    if email:
        return "http://localhost:5000/digest/%s" % (meta["digest_encoded"])
    return "http://www.flickr.com/photos/%s/%s" % (meta["stream"].foreign_key, value.foreign_key)

@app.template_filter()
@evalcontextfilter
def nl2br(eval_ctx, value):
    """ Converts new line to br """
    result = re.sub(r'\r\n|\r|\n', '<br/>\n', value)
    if eval_ctx.autoescape:
        result = Markup(result)
    return result

@app.template_filter("datetime")
def format_datetime(value):
    return value.strftime("%A %d %B %Y")

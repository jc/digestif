import re
from datetime import datetime
from datetime import timedelta

from flask import session, request, g, redirect, url_for, abort, render_template, flash
from flask_oauth import OAuthException

from jinja2 import evalcontextfilter, Markup

import premailer 

from digestif import app
from digestif import flickr_oauth
from digestif.models import Entry
from digestif.models import Publisher, Publication, FlickrPhoto
from digestif import db
from digestif import models
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
    pub = Publication.query.filter_by(remote_id=remote_id).first()

    if not pub:
        publisher = Publisher()
        pub = Publication(oauth_token=resp["oauth_token"], oauth_token_secret=resp["oauth_token_secret"],
                          publisher_id=publisher.id, remote_id=remote_id, service=FLICKR)
        publisher.publications.append(pub)
        pub.last_updated = datetime.utcnow()
        db.session.add(publisher)
        db.session.add(pub)
        print "created %s" % publisher
        print "created %s" % pub
    if pub.oauth_token != resp["oauth_token"] or pub.oauth_token_secret != resp["oauth_token_secret"]:
        print "updating %s" % pub
        pub.oauth_token = resp["oauth_token"]
        pub.oauth_token_secret = resp["oauth_token_secret"]
        db.session.add(pub)
        print "changed to %s" % pub
    db.session.commit()
    flash('You were signed in as %s' % resp['username'])
    return redirect(url_for('subscribe', externalid=pub.id))

#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>%s</p><p>%s</p><p>%s</p>" % (error.message, error.type, error.data)

@app.route("/subscribe/<externalid>")
def subscribe(externalid):
    pub = Publication.query.filter_by(id=externalid).first()
    if not pub:
        return "Unknown digest"
    return "Want to subscribe to %s?" % (pub.remote_id)

@app.route("/")
def index():
    return "Hello World!"

@app.route("/view/<username>/<previous>/<frequency>/<today>")
def digest(username, previous, frequency, today):
    previous_dt = datetime.strptime(previous, "%Y%m%d")
    today_dt = datetime.strptime(today, "%Y%m%d")
    frequency_td = timedelta(days=int(frequency))
    if today_dt - previous_dt < frequency_td:
        return "Too soon since last check!"
    entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > previous_dt,
                                       FlickrPhoto.date_uploaded <= today_dt,
                                       FlickrPhoto.publication_id == username).order_by(FlickrPhoto.date_uploaded).all()
    pub = Publication.query.filter(Publication.id == username).first()
    meta = {"username" : username, "previous" : previous,
            "frequency" : frequency, "today" : today,
            "publication" : pub }
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
                                       FlickrPhoto.publication_id == username).order_by(FlickrPhoto.date_uploaded).all()
    pub = Publication.query.filter(Publication.id == username).first()
    meta = {"username" : username, "previous" : previous,
            "frequency" : frequency, "today" : today,
            "publication" : pub }

    return premailer.transform(render_template("show_entries.html", entries=entries, meta=meta, email=True))

@app.template_filter("imgurl")
def imgurl_filter(value, meta=None, email=False):
    if email:
        return "http://farm%s.staticflickr.com/%s/%s_%s.jpg" % (value.farm, value.server, value.remote_id, value.secret)
    size = "z"
    if value.date_uploaded >= datetime(2012, 03, 01):
        size = "c"
    return "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg" % (value.farm, value.server, value.remote_id, value.secret, size)

@app.template_filter("permalink")
def permalink_filter(value, meta=None, email=False):
    if email:
        return "http://localhost:5000/view/%s/%s/%s/%s" % (meta["username"], meta["previous"], 
                                                           meta["frequency"], meta["today"])
    return "http://www.flickr.com/photos/%s/%s" % (meta["publication"].remote_id, value.remote_id)

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

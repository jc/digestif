from flask import session, request, g, redirect, url_for, abort, render_template, flash
from flask_oauth import OAuthException

from digestif import app
from digestif import flickr_oauth
from digestif.models import Entry
from digestif.models import Publisher, Publication
from digestif import db
from digestif import models
from digestif.constants import *

@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    #pass return (token, secret) or None
    return None

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
def show_entries():
    entries = [Entry({"main_src" : "http://michelleandjames.net/p/hjc1.jpg", "caption" : "Hello"})] * 3
    return render_template("show_entries.html", entries=entries)

@app.route("/index")
def index():
    return "Hello World!"

@app.route("/view/<username>/<previous>/<frequency>/<today>")
def digest(username, previous, frequency, today):
    previous_dt = datetime.strptime(previous, "%Y%m%d")
    today_dt = datetime.strptime(today, "%Y%m%d")
    frequency_td = timedelta(days=int(frequency))
    entries = []
    for entry in database:
        if entry.date >= previous_dt and entry.date <= today_dt:
            entries.append(entry)
    if today_dt - previous_dt < frequency_td:
        entries = []
    return render_template("show_entries.html", entries=entries)

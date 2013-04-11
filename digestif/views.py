import re
from datetime import datetime
from datetime import timedelta

from flask import session, request, g, redirect, url_for, abort, render_template, flash, escape
from flask_oauth import OAuthException

from jinja2 import evalcontextfilter, Markup

import premailer 

from digestif import app
from digestif import flickr_oauth
from digestif.models import User, Stream, FlickrPhoto, Subscription, Digest
from digestif import db
from digestif.constants import *
from digestif.models import make_user, make_subscription, make_stream
from digestif.forms import RegisterStream, SubscribeForm
from digestif import hash_gen


@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    #pass return (token, secret) or None
    return token

#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>%s</p><p>%s</p><p>%s</p>" % (error.message, error.type, error.data)

@app.route('/signup/flickr')
def signup_flickr():
    return flickr_oauth.authorize(callback=url_for('oauth_flickr_authorized', \
      next=request.args.get('next') or request.referrer or None))

@app.route('/register/flickr', methods=('GET', 'POST'))
@flickr_oauth.authorized_handler
def oauth_flickr_authorized(resp):
    next_url = request.args.get('next') or url_for('index')
    
    form = RegisterStream()
    if form.validate_on_submit():
        email = form.email.data
        user = make_user(email)
        stream = make_stream(form.remote.data, user,
                             form.ot.data, form.ots.data,
                             last_checked=datetime.utcnow())
        #TODO welcome screen next?
        return "Woohoo!"

    if resp is None and not form.is_submitted():
        return redirect(next_url) # bail from register

    if resp is not None:
        form.remote.data = resp["user_nsid"] 
        form.ots.data = resp["oauth_token_secret"]
        form.ot.data = resp["oauth_token"]
    elif not form.is_submitted():
        return redirect(next_url) # bail from register

    stream = Stream.query.filter_by(foreign_key=form.remote.data).first()
    if not stream:
        return render_template("new_user.html", form=form) # new user sign-up
    elif stream.oauth_token != form.ot.data and stream.oauth_token_secret != form.ots.data:
        stream.oauth_token = form.ot.data
        stream.oauth_token_secret = form.ots.data
        db.session.commit()
        print "stream updated", stream.id, stream.foreign_key
        return redirect(next_url) # continue to index
    else:
        return redirect(next_url) # continue to index

@app.route("/subscribe/<stream_encoded>", methods=("GET", "POST"))
def subscribe(stream_encoded):
    values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    if values:
        user_id, stream_id = values
    else:
        user_id, stream_id = None, -1

    stream = Stream.query.filter_by(id=stream_id).first_or_404()

    if stream.user_id != user_id:
        # TODO handle error case.
        return "Mismatching user and stream!"

    subscribe_form = SubscribeForm()

    if subscribe_form.validate_on_submit():
        email = subscribe_form.email.data;
        frequency = int(subscribe_form.frequency.data)
        user = make_user(email)
        subscription = make_subscription(stream, user, frequency)
        # TODO page to describe subscription
        return "Success"
    else:
        return render_template("subscribe.html", form=subscribe_form, stream_encoded=stream_encoded)


# TODO index
@app.route("/")
def index():
    data = ["<pre><code>"]
    for stream in Stream.query.all():
        data.append(hash_gen.encrypt(stream.user_id, stream.id))
        data.append(escape(stream.__repr__()))
    for user in User.query.all():
        data.append(escape(user.__repr__()))
    for subscription in Subscription.query.all():
        data.append(escape(subscription.__repr__()))
    for digest in Digest.query.all():
        data.append(hash_gen.encrypt(digest.id))
        data.append(escape(digest.__repr__()))
    data.append("</code></pre>")
    return "\n".join(data)

@app.route("/digest/<digest_encoded>")
def display_digest(digest_encoded):
    values = hash_gen.decrypt(str(digest_encoded))
    if not values:
        digest_id = -1
    else:
        digest_id = values[0]
    digest = Digest.query.filter_by(id=digest_id).first_or_404()
    subscription = Subscription.query.filter_by(id=digest.subscription_id).first()
    if not subscription:
        return "Unknown subscription"
    stream = Stream.query.filter_by(id=subscription.stream_id).first()
    entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > digest.start_date,
                                       FlickrPhoto.date_uploaded <= digest.end_date,
                                       FlickrPhoto.stream_id == stream.id).order_by(FlickrPhoto.date_taken).all()
    meta = {"stream" : stream, "digest_encoded" : digest_encoded}
    return render_template("show_entries.html", entries=entries, email=None, meta=meta)


#
#
#
# -------------- template filters -----------------
#
#

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

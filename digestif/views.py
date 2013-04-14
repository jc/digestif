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
from digestif.forms import SubscribeForm, SignUpStream
from digestif import hash_gen
from digestif import processes

@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    #pass return (token, secret) or None
    return token

#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>%s</p><p>%s</p><p>%s</p>" % (error.message, error.type, error.data)

@app.route('/new/flickr')
@flickr_oauth.authorized_handler
def handle_flickr_authorization(resp):
    if resp is None:
        print "no response"
        return url_for("landing")
    
    flickr_id = resp.get("user_nsid")
    oauth_token_secret = resp.get("oauth_token_secret")
    oauth_token = resp.get("oauth_token")
    
    if not flickr_id or not oauth_token_secret or not oauth_token:
        # TODO error handling
        print "no flickr auth", flickr_id, oauth_token, oauth_token_secret
        return redirect(url_for("landing"))
    
    email = request.args.get("email")
    if email:
        user = None
        stream = Stream.query.filter_by(foreign_key=flickr_id).first()
        if stream:
            user = User.query.filter_by(id=stream.user_id).first()
        user = make_user(email, user=user)
        stream = make_stream(flickr_id, user, oauth_token, oauth_token_secret,
                             last_checked=datetime.utcnow())
        return redirect(url_for("subscribe", stream_encoded=hash_gen.encrypt(stream.user_id, stream.id)))
    return redirect(url_for("landing"))

@app.route("/subscribe/<stream_encoded>", methods=("GET", "POST"))
def subscribe(stream_encoded):
    values = None
    try:
        values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    except TypeError:
        print "Error in hash_gen.decrypt again!"
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
        return render_template("subscribe.html", 
                               form=subscribe_form, 
                               stream_encoded=stream_encoded, 
                               digestname=processes.metadata(stream),
                               perma="http://www.flickr.com/photos/%s" % stream.foreign_key)


@app.route("/", methods=("GET", "POST"))
def landing():
    form = SignUpStream()
    if form.validate_on_submit():
        if form.stream.data == "flickr":
            return flickr_oauth.authorize(callback=url_for('handle_flickr_authorization', email=form.email.data))
        else:
            return "service unsupported"
    return render_template("landing.html", form=form)

@app.route("/_dump")
def dump():
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
    return render_template("show_entries.html", entries=entries, email=request.args.get("email", None), meta=meta)


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

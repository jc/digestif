import re
from datetime import datetime
from datetime import timedelta

from flask import session, request, g, redirect, url_for, abort, render_template, flash, escape
from flask_oauth import OAuthException

from jinja2 import evalcontextfilter, Markup

import premailer 

from digestif import app
from digestif import flickr_oauth, instagram_oauth
from digestif.models import User, Stream, FlickrPhoto, Subscription, Digest, InstagramPhoto
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

@instagram_oauth.tokengetter
def get_instagram_token(token=None):
    return token

#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>%s</p><p>%s</p><p>%s</p>" % (error.message, error.type, error.data)

@app.route('/auth/flickr')
@flickr_oauth.authorized_handler
def handle_flickr_authorization(resp):
    if resp is None:
        return redirect(url_for("landing"))
    
    flickr_id = resp.get("user_nsid")
    oauth_token_secret = resp.get("oauth_token_secret")
    oauth_token = resp.get("oauth_token")
    
    if not flickr_id or not oauth_token_secret or not oauth_token:
        app.logger.warning("no flickr auth %s, %s, %s" % (flickr_id, oauth_token, oauth_token_secret))
        return redirect(url_for("landing"))
    
    session["digestif"] = {"a" : oauth_token }

    email = request.args.get("email")

    if email:
        user = None
        stream = Stream.query.filter_by(foreign_key=flickr_id).first()
        if stream:
            user = stream.user
            if user.email != email:
                flash("We've updated the email address associated with your Flickr account. <a href\"http://digestif.me/stats\">View your subscriber statistics</a>", "info")

        flash("Great! We are all set. Tell your friends and family to visit this page to subscribe. <a href\"http://digestif.me/stats\">View your subscriber statistics</a>", "success")
        user = make_user(email, user=user)
        stream = make_stream(flickr_id, user, oauth_token, oauth_token_secret,
                             last_checked=datetime.utcnow())
        return redirect(stream.subscribe_url())

    # stats means we redirect to statistics page
    stats = request.args.get("stats")
    if stats:
        stream = Stream.query.filter_by(foreign_key=flickr_id).first()
        if stream:
            return redirect(url_for("stats", stream_encoded=hash_gen.encrypt(stream.user_id, stream.id)))

    return redirect(url_for("landing"))

@app.route('/auth/instagram',  methods=("GET", "POST"))
@instagram_oauth.authorized_handler
def handle_instagram_authorization(resp):
    if resp is None:
        return redirect(url_for("landing"))
    instagram_user = resp.get("user")
    instagram_id = instagram_user["id"]
    access_token = resp.get("access_token")
    
    if not instagram_user or not access_token:
        app.logger.warning("no instagram auth %s, %s, %s" % (instagram_user, access_token))
        return redirect(url_for("landing"))
    
    session["digestif"] = {"a" : access_token }

    # email means we create a new account
    email = request.args.get("email")
    if email:
        user = None
        stream = Stream.query.filter_by(foreign_key=instagram_id).first()
        if stream:
            user = stream.user
            if user.email != email:
                flash("We've updated the email address associated with your Instagram account.", "info")

        flash("Great! We are all set. Tell your friends and family to visit this page to subscribe.", "success")
        user = make_user(email, user=user)
        stream = make_stream(instagram_id, user, access_token, "",
                             last_checked=datetime.utcnow(), service=INSTAGRAM)
        return redirect(stream.subscribe_url())

    # stats means we redirect to statistics page
    stats = request.args.get("stats")
    if stats:
        stream = Stream.query.filter_by(foreign_key=instagram_id).first()
        if stream:
            return redirect(url_for("stats", stream_encoded=hash_gen.encrypt(stream.user_id, stream.id)))

    return redirect(url_for("landing"))


@app.route("/subscribe/<stream_encoded>", methods=("GET", "POST"))
def subscribe(stream_encoded):
    values = None
    try:
        values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    except TypeError:
        app.logger.error("Error in hashids.decrypt! %s" % stream_encoded)
    if values:
        user_id, stream_id = values
    else:
        user_id, stream_id = None, -1

    stream = Stream.query.filter_by(id=stream_id).first_or_404()

    if stream.user_id != user_id:
        app.logger.error("Mismatching user and stream! %s, %s" % (stream.user_id, user_id))
        return "Mismatching user and stream!"

    subscribe_form = SubscribeForm()

    if subscribe_form.validate_on_submit():
        email = subscribe_form.email.data;
        frequency = int(subscribe_form.frequency.data)
        user = make_user(email)
        subscription = make_subscription(stream, user, frequency)
        return render_template("welcome.html", stream=stream, subscription=subscription,
                               user=user)
    else:
        flash_errors(subscribe_form)
        unsubscribe = False
        address = request.args.get("address", "")
        if request.args.get("unsubscribe", None) == "1":
            unsubscribe = True
        return render_template("subscribe.html", 
                               form=subscribe_form, 
                               stream=stream, unsubscribe=unsubscribe, address=address)


@app.route("/", methods=("GET", "POST"))
def landing():
    form = SignUpStream()
    if form.validate_on_submit():
        if form.stream.data == "flickr":
            return flickr_oauth.authorize(callback=url_for('handle_flickr_authorization', email=form.email.data))
        elif form.stream.data == "instagram":
            return instagram_oauth.authorize(callback="http://digestif.me"+url_for('handle_instagram_authorization', email=form.email.data))
        else:
            return "service unsupported"
    flash_errors(form)
    return render_template("landing.html", form=form)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/stats/<stream_encoded>", methods=("GET", "POST"))
def stats(stream_encoded):
    values = None
    try:
        values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    except TypeError:
        app.logger.error("Error in hashids.decrypt! %s" % stream_encoded)
    if values:
        user_id, stream_id = values
    else:
        user_id, stream_id = None, -1

    stream = Stream.query.filter_by(id=stream_id).first_or_404()
    if session.get('digestif') is None:
        return redirect(url_for("stats_auth", service=stream.service))
    oauth_token = session.get("digestif")["a"]
    if oauth_token != stream.oauth_token:
        # we'll 404 for now but should have better logic
        # it is possible the token we have stored is invalid and the
        # user may need to reauthorize
        other_stream = Stream.query.filter_by(oauth_token=oauth_token).first_or_404()
        return redirect(url_for("stats", stream_encoded=hash_gen.encrypt(other_stream.user_id, other_stream.id)))

    if stream.user_id != user_id:
        app.logger.error("Mismatching user and stream! %s, %s" % (stream.user_id, user_id))
        return "Mismatching user and stream!"

    owner = stream.user.email
    subscribers = Subscription.query.filter_by(stream_id=stream.id).filter(Subscription.frequency != 0).all()
    digest_counts = {}
    for subscriber in subscribers:
        digest_counts[subscriber] = Digest.query.filter_by(subscription_id=subscriber.id).count()
    return render_template("stats.html", stream=stream, owner=owner, subscribers=subscribers, digest_counts=digest_counts)

@app.route("/stats/")
def stats_auth():
    service = request.args.get("service", None)
    if service == str(FLICKR):
        return flickr_oauth.authorize(callback=url_for('handle_flickr_authorization', stats="1"))
    elif service == str(INSTAGRAM):
        return instagram_oauth.authorize(callback="http://digestif.me"+url_for('handle_instagram_authorization', stats="1"))
    elif session.get('digestif'):
        oauth_token = session.get("digestif")["a"]
        other_stream = Stream.query.filter_by(oauth_token=oauth_token).first_or_404()
        return redirect(url_for("stats", stream_encoded=hash_gen.encrypt(other_stream.user_id, other_stream.id)))

    else:
        return render_template("general_stats.html")

@app.route("/signout")
def signout():
    session.pop("digestif", None)
    return redirect(url_for("landing"))

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
    subscription = digest.subscription
    if not subscription:
        return "Unknown subscription"
    stream = subscription.stream
    if stream.service == FLICKR:
        entries = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > digest.start_date,
                                           FlickrPhoto.date_uploaded <= digest.end_date,
                                           FlickrPhoto.stream_id == stream.id).order_by(FlickrPhoto.date_taken).all()
    elif stream.service == INSTAGRAM:
        entries = InstagramPhoto.query.filter(InstagramPhoto.date_uploaded > digest.start_date,
                                              InstagramPhoto.date_uploaded <= digest.end_date,
                                              InstagramPhoto.stream_id == stream.id).order_by(InstagramPhoto.date_taken).all()
    else:
        entries = None
    meta = {"stream" : stream, "digest_encoded" : digest_encoded, "digest" : digest}
    return render_template("show_entries.html", entries=entries, email=request.args.get("email", None), meta=meta)


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, "error")

    

#
#
#
# -------------- template filters -----------------
#
#

@app.template_filter("videosrc")
def videosrc_filter(value, size="hd", meta=None):
    if value.video and meta["stream"].service == INSTAGRAM:
        return value.standard_resolution
    elif value.video and meta["stream"].service == FLICKR:
        return "http://www.flickr.com/photos/%s/%s/play/%s/%s/" % (value.stream.foreign_key, value.foreign_key, size, value.secret)
    else:
        return ""

@app.template_filter("imgurl")
def imgurl_filter(value, meta=None, email=False):
    if meta["stream"].service == FLICKR:
        if email:
            return "http://farm%s.staticflickr.com/%s/%s_%s.jpg" % (value.farm, value.server, value.foreign_key, value.secret)
        if value.date_uploaded >= datetime(2012, 03, 01):
            size = "c"
        return "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg" % (value.farm, value.server, value.foreign_key, value.secret, size)
    elif meta["stream"].service == INSTAGRAM:
        if email:
            return value.low_resolution
        return value.standard_resolution
    else:
        return ""

@app.template_filter("permalink")
def permalink_filter(value, meta=None, email=False):
    if email:
        return url_for("display_digest", digest_encoded=meta["digest_encoded"])
    if meta["stream"].service == FLICKR:
        return "http://www.flickr.com/photos/%s/%s" % (meta["stream"].foreign_key, value.foreign_key)
    elif meta["stream"].service == INSTAGRAM:
        return value.link
    else:
        return ""

@app.template_filter("days2words")
def days2words_filter(value):
    value = int(value)
    if value == 0:
        return "never"
    if value == 1:
        return "daily"
    if value == 2:
        return "every two days"
    if value == 3:
        return "every three days"
    if value == 7:
        return "weekly"
    if value == 14:
        return "biweekly"
    if value == 30:
        return "monthly"
    return value

@app.template_filter("stream2name")
def stream2name_filter(value):
    return processes.metadata(value)

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

@app.template_filter("service2name")
def service2name_filter(value):
    if value.service == FLICKR:
        return "Flickr"
    elif value.service == INSTAGRAM:
        return "Instagram"
    else:
        return "Unknown service"

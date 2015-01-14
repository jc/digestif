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

#################
##### oauth #####
#################
@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    return token

@instagram_oauth.tokengetter
def get_instagram_token(token=None):
    return token

@app.route('/auth/flickr')
@flickr_oauth.authorized_handler
def handle_flickr_authorization(resp):
    if resp is None:
        return redirect(url_for("landing"))
    flickr_id = resp.get("user_nsid")
    oauth_token_secret = resp.get("oauth_token_secret")
    oauth_token = resp.get("oauth_token")
    if not flickr_id or not oauth_token_secret or not oauth_token:
        app.logger.warning("no flickr auth {}, {}, {}".format(flickr_id, oauth_token, oauth_token_secret))
        return redirect(url_for("landing"))
    session["digestif"] = {"a" : oauth_token }
    email = request.args.get("email")
    if email:
        stream = build_user_stream(email, flickr_id, FLICKR, oauth_token, oauth_token_secret)
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
        app.logger.warning("no instagram auth {}, {}".format(instagram_user, access_token))
        return redirect(url_for("landing"))
    session["digestif"] = {"a" : access_token }
    # email means we create a new account
    email = request.args.get("email")
    if email:
        stream = build_user_stream(email, instagram_id, INSTAGRAM, access_token, "")
        return redirect(stream.subscribe_url())
    # stats means we redirect to statistics page
    stats = request.args.get("stats")
    if stats:
        stream = Stream.query.filter_by(foreign_key=instagram_id).first()
        if stream:
            return redirect(url_for("stats", stream_encoded=hash_gen.encrypt(stream.user_id, stream.id)))
    return redirect(url_for("landing"))

# Uncomment to enable oauth debugging
#@app.errorhandler(OAuthException)
def handle_oauth_exception(error):
    return "<p>{}</p><p>{}</p><p>{}</p>".format(error.message, error.type, error.data)

#######################################
# creates a user and stream as required
def build_user_stream(email, foreign_key, service, oauth_token, oauth_token_secret):
    user = None
    stream = Stream.query.filter_by(foreign_key=foreign_key).first()
    if stream:
        service_name = stream2service_filter(stream)
        user = stream.user
        if user.email != email:
            flash("We've updated the email address associated with your {} account. <a href=\"{}\">View your subscriber statistics</a>".format(service_name, url_for("stats_auth")), "info")
        else:
            flash("Tell your friends and family to visit this page to subscribe. <a href=\"{}\">View your subscriber statistics</a>".format(url_for("stats_auth")), "info")
    else:
        flash("Great! We are all set. Tell your friends and family to visit this page to subscribe. <a href=\"{}\">View your subscriber statistics</a>".format(url_for("stats_auth")), "success")
    user = make_user(email, user=user)
    stream = make_stream(foreign_key, user, oauth_token, oauth_token_secret,
                         last_checked=datetime.utcnow())
    return stream

#################
##### user  #####
#################

@app.route("/", methods=("GET", "POST"))
def landing():
    form = SignUpStream()
    if form.validate_on_submit():
        if form.stream.data == "flickr":
            return flickr_oauth.authorize(callback=url_for("handle_flickr_authorization", email=form.email.data), perms="read")
        elif form.stream.data == "instagram":
            return instagram_oauth.authorize(callback=url_for("handle_instagram_authorization", _external=True, email=form.email.data))
        else:
            return "service unsupported"
    flash_errors(form)
    return render_template("landing.html", form=form)

@app.route("/subscribe/<stream_encoded>", methods=("GET", "POST"))
def subscribe(stream_encoded):
    values = None
    try:
        values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    except TypeError:
        app.logger.error("Error in hashids.decrypt! {}".format(stream_encoded))
    if values:
        user_id, stream_id = values
    else:
        user_id, stream_id = None, -1
    stream = Stream.query.filter_by(id=stream_id).first_or_404()
    if stream.user_id != user_id:
        app.logger.error("Mismatching user and stream! {}, {}".format(stream.user_id, user_id))
        return "Mismatching user and stream!"
    subscribe_form = SubscribeForm()
    if subscribe_form.validate_on_submit():
        email = subscribe_form.email.data;
        frequency = int(subscribe_form.frequency.data)
        user = make_user(email)
        subscription = make_subscription(stream, user, frequency)
        return render_template("welcome.html", stream=stream, subscription=subscription, user=user)
    else:
        flash_errors(subscribe_form)
        unsubscribe = False
        address = request.args.get("address", "")
        if request.args.get("unsubscribe", None) == "1":
            unsubscribe = True
        frequency_index = request.args.get("f", None)
        try:
            frequency_index = int(frequency_index)
        except (ValueError, TypeError):
            frequency_index = None
        return render_template("subscribe.html",
                               form=subscribe_form,
                               stream=stream, unsubscribe=unsubscribe, address=address, frequency_index=frequency_index)

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
        entries = []
    return render_template("digest.html", entries=entries, email=request.args.get("email", None), stream=stream, digest_encoded=digest_encoded, digest=digest)




#################
##### meta  #####
#################

@app.route("/about")
def about():
    return render_template("about.html")

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
        stream_encoded = hash_gen.encrypt(other_stream.user_id, other_stream.id)
        return redirect(url_for("stats", stream_encoded=stream_encoded))
    else:
        return render_template("stats_login.html")

@app.route("/stats/<stream_encoded>", methods=("GET", "POST"))
def stats(stream_encoded):
    values = None
    try:
        values = hash_gen.decrypt(str(stream_encoded)) #values stores user_id, stream_id
    except TypeError:
        app.logger.error("Error in hashids.decrypt! {}".format(stream_encoded))
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
        stream_encoded=hash_gen.encrypt(other_stream.user_id, other_stream.id)
        return redirect(url_for("stats", stream_encoded=stream_encoded))
    if stream.user_id != user_id:
        app.logger.error("Mismatching user and stream! {}, {}".format(stream.user_id, user_id))
        return "Mismatching user and stream!"
    owner = stream.user.email
    subscribers = Subscription.query.filter_by(stream_id=stream.id).filter(Subscription.frequency != 0).all()
    digest_counts = {}
    for subscriber in subscribers:
        digest_counts[subscriber] = Digest.query.filter_by(subscription_id=subscriber.id).count()
    return render_template("stats.html", stream=stream, owner=owner, subscribers=subscribers, digest_counts=digest_counts)


@app.route("/signout")
def signout():
    session.pop("digestif", None)
    return redirect(url_for("landing"))

#################
### god mode  ###
#################

# for the database lazy
# @app.route("/_dump")
# def dump():
#     data = ["<pre><code>"]
#     for stream in Stream.query.all():
#         data.append(hash_gen.encrypt(stream.user_id, stream.id))
#         data.append(escape(stream.__repr__()))
#     for user in User.query.all():
#         data.append(escape(user.__repr__()))
#     for subscription in Subscription.query.all():
#         data.append(escape(subscription.__repr__()))
#     for digest in Digest.query.all():
#         data.append(hash_gen.encrypt(digest.id))
#         data.append(escape(digest.__repr__()))
#     data.append("</code></pre>")
#     return "\n".join(data)


#################
#### errors  ####
#################

@app.errorhandler(502)
def bad_gateway(error):
    return render_template("502.html"), 502

def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, "error")

#################
#### filters ####
#################
@app.template_filter("videosrc")
def videosrc_filter(video, size="hd"):
    if video.video and video.stream.service == INSTAGRAM:
        return video.standard_resolution
    elif video.video and video.stream.service == FLICKR:
        return "http://www.flickr.com/photos/{}/{}/play/{}/{}/".format(video.stream.foreign_key, video.foreign_key, size, video.secret)
    else:
        return ""

@app.template_filter("imgurl")
def imgurl_filter(photo, email=False):
    if photo.stream.service == FLICKR:
        if email:
            return "http://farm{}.staticflickr.com/{}/{}_{}.jpg".format(photo.farm, photo.server, photo.foreign_key, photo.secret)
        # use bigger size for flickr photos after 2012-03-01
        size = "z"
        if photo.date_uploaded >= datetime(2012, 03, 01):
            size = "c"
        return "http://farm{}.staticflickr.com/{}/{}_{}_{}.jpg".format(photo.farm, photo.server, photo.foreign_key, photo.secret, size)
    elif photo.stream.service == INSTAGRAM:
        if email:
            return photo.low_resolution
        return photo.standard_resolution
    else:
        return ""

@app.template_filter("permalink")
def permalink_filter(photo, digest_encoded=None, email=False):
    if email:
        return url_for("display_digest", digest_encoded=digest_encoded)
    if photo.stream.service == FLICKR:
        return "http://www.flickr.com/photos/{}/{}".format(photo.stream.foreign_key, photo.foreign_key)
    elif photo.stream.service == INSTAGRAM:
        return photo.link
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
def stream2name_filter(stream):
    return processes.metadata(stream)

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

@app.template_filter("stream2service")
def stream2service_filter(stream):
    if stream.service == FLICKR:
        return "Flickr"
    elif stream.service == INSTAGRAM:
        return "Instagram"
    else:
        return "Unknown service"
    

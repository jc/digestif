from datetime import datetime, timedelta
from time import sleep
import json

from flask import render_template, abort
import premailer
import sendgrid
import mandrill

from digestif import flickr_oauth as flickr
from digestif import instagram_oauth as instagram
from digestif.models import InstagramPhoto, FlickrPhoto, Digest, Subscription
from digestif.constants import *
from digestif import db, hash_gen, app
from digestif import keys

FLICKR_DATE = "%Y-%m-%d %H:%M:%S"

def metadata(stream):
    if stream.service == FLICKR:
        return flickr_metadata(stream)
    elif stream.service == INSTAGRAM:
        return instagram_metadata(stream)

def flickr_metadata(stream):
    token = (stream.oauth_token, stream.oauth_token_secret)
    # build the query
    query = {"method" : "flickr.people.getInfo",
             "user_id" : stream.foreign_key,
             "format" : "json",
             "nojsoncallback" : 1}
    # make the call and get the response
    resp = flickr.get("", data=query, token=token)
    if isinstance(resp.data, str):
        try:
            resp.data = json.loads(resp.data)
        except ValueError:
            app.logger.warn("Could not decode json: {}".format(resp.data))
            return "[flickr error]"
    if resp.status == 200 and resp.data["stat"] == "ok":
        return resp.data["person"]["realname"]["_content"] or resp.data["person"]["username"]
    app.logger.error("Error in flickr_metadata, {}, {}".format(resp.status, resp.data))
    #abort(502)
    return "[flickr error]"
    
def instagram_metadata(stream, username=False):
    token = (stream.oauth_token, stream.oauth_token_secret)
    # build the query
    query = "users/{}".format(stream.foreign_key)
    # make the call and get the response
    resp = instagram.get(query, token=token, data={"access_token" : token[0]})
    
    if resp.status == 200:
        if username:
            return resp.data["data"]["username"]
        return resp.data["data"]["full_name"] or resp.data["data"]["username"]
    app.logger.error("Error in instagram_metadata, {}, {}".format(resp.status, resp.data))
    #abort(502)    
    return "[instagram error]"

def retrieve_photos(stream, since=None):
    # if since date not specified we'll default to last time we checked
    # the stream
    if not since:
        since = stream.last_checked
    app.logger.info("Checking stream: {} with since {}".format(stream.id, since))

    if stream.service == FLICKR:
        return flickr_retrieve_photos(stream, since)
    elif stream.service == INSTAGRAM:
        return instagram_retrieve_photos(stream, since)

def instagram_retrieve_photos(stream, since):
    now = datetime.utcnow()
    token = (stream.oauth_token, stream.oauth_token_secret)
    query = "users/{}/media/recent".format(stream.foreign_key)
    data = {"min_timestamp" : int((since - datetime(1970, 1, 1)).total_seconds()),
            "access_token" : token[0]}
    resp = instagram.get(query, data=data, token=token)
    more = True
    successful = False
    while resp.status == 200 and more:
        for photo in resp.data["data"]:
            create_instagram_photo(photo, stream)
        successful = True
        if resp.data["pagination"]:
            resp = instagram.get(resp.data["pagination"]["next_url"], token=token)
        else:
            more = False
        sleep(1) # do not spam the api
    if resp.status != 200:
        successful = False
        app.logger.warning("Response code: {}; data: {}".format(resp.status, resp.data))
    if successful:
        stream.last_checked = now
        db.session.add(stream)
    db.session.commit()
    return resp.status

def flickr_retrieve_photos(stream, since):
    now = datetime.utcnow()
    token = (stream.oauth_token, stream.oauth_token_secret)
    # build the query
    query = {"method" : "flickr.people.getPhotos",
             "user_id" : stream.foreign_key,
             "extras" : "date_upload, date_taken, description, media, tags",
             "format" : "json",
             "nojsoncallback" : 1,
             "min_upload_date" :  (since - datetime(1970, 1, 1)).total_seconds()}
    # make the call and get the response
    resp = flickr.get("", data=query, token=token)
    successful = False
    page = None
    pages = None
    if isinstance(resp.data, str):
        resp.data = json.loads(resp.data)
    # on successful response get the paging data
    if resp.status == 200 and resp.data["stat"] == "ok":
        page = int(resp.data["photos"]["page"])
        pages = int(resp.data["photos"]["pages"])
    more = True
    # do the page dance!
    while resp.status == 200 and more and resp.data["stat"] == "ok":
        for photo in resp.data["photos"]["photo"]:
            photo_visible = str(photo["ispublic"]) == "1" or str(photo["isfriend"]) == "1" or str(photo["isfamily"]) == "1"
            if photo_visible and "digestif:ignore=true" not in photo["tags"]:
                flickrphoto = create_flickr_photo(photo, stream)
        query["page"] = page + 1
        if page >= pages:
            more = False
        else:
            # dance dance dance
            resp = flickr.get("", data=query, token=token)
            if isinstance(resp.data, str):
                resp.data = json.loads(resp.data)
            if resp.status == 200 and resp.data["stat"] == "ok":
                page = int(resp.data["photos"]["page"])
                pages = int(resp.data["photos"]["pages"])
        successful = True
        sleep(1) # do not spam the api
    if resp.status != 200 or resp.data["stat"] != "ok":
        successful = False
        app.logger.warning("Response code: {}; data: {}".format(resp.status, resp.data))
    if successful:
        stream.last_checked = now
        db.session.add(stream)
    db.session.commit()
    return resp.status
    
def create_instagram_photo(photo, stream):
    id = photo["id"]
    date_taken = datetime.fromtimestamp(float(photo["created_time"]))
    title = ""
    description = photo["caption"]["text"] if photo["caption"] else ""
    link = photo["link"]
    if photo["type"] == "image":
        low_resolution = photo["images"]["low_resolution"]["url"]
        standard_resolution = photo["images"]["standard_resolution"]["url"]
        thumbnail = photo["images"]["thumbnail"]["url"]
        video = False
    elif photo["type"] == "video":
        low_resolution = photo["videos"]["low_resolution"]["url"]
        standard_resolution = photo["videos"]["standard_resolution"]["url"]
        thumbnail = photo["images"]["thumbnail"]["url"]
        video = True
    instagramphoto = None
    instagramphoto = InstagramPhoto.query.filter_by(foreign_key=id).first()
    if not instagramphoto:
        instagramphoto = InstagramPhoto(foreign_key=id, stream_id=stream.id,
                                        date_taken=date_taken, 
                                        date_uploaded=date_taken,
                                        title=title,
                                        description=description, video=video,
                                        low_resolution=low_resolution,
                                        standard_resolution=standard_resolution,
                                        thumbnail=thumbnail, link=link)
        db.session.add(instagramphoto)
        stream.last_updated = datetime.now()
        db.session.commit()
        app.logger.info("Added Instagram photo {}".format(id))
    else:
        # already present
        pass
    return instagramphoto
    
def create_flickr_photo(photo, stream):
    id = photo["id"]
    farm = photo["farm"]
    server = photo["server"]
    secret = photo["secret"]
    date_uploaded = datetime.fromtimestamp(float(photo["dateupload"]))
    date_taken = datetime.strptime(photo["datetaken"], FLICKR_DATE)
    title = photo["title"]
    description = photo["description"]["_content"]
    flickrphoto = None
    flickrphoto = FlickrPhoto.query.filter_by(foreign_key=id).first()
    video = False
    if "media" in photo and photo["media"] == "video":
        video = True
    if not flickrphoto:
        flickrphoto = FlickrPhoto(foreign_key=id, stream_id=stream.id,
                                  farm=farm, server=server, secret=secret,
                                  title=title, description=description,
                                  date_uploaded=date_uploaded,
                                  date_taken=date_taken, video=video)
        db.session.add(flickrphoto)
        stream.last_updated = datetime.now()
        db.session.commit()
        app.logger.info("Added Flickr photo {}".format(id))
    else:
        # already present
        pass
    return flickrphoto

def create_digest(subscription, previous_dt=None, today_dt=None):
    if not subscription.active:
        return None
    if not previous_dt:
        previous_dt = subscription.last_digest
    if not today_dt:
        today_dt = datetime.now()
    frequency_td = timedelta(days=subscription.frequency)
    digest = None
    stream = subscription.stream
    if today_dt - previous_dt >= frequency_td:
        if stream.service == FLICKR:
            count = FlickrPhoto.query.filter(FlickrPhoto.date_uploaded > previous_dt,
                                             FlickrPhoto.date_uploaded <= today_dt,
                                             FlickrPhoto.stream_id == stream.id).count()
        elif stream.service == INSTAGRAM:
            count = InstagramPhoto.query.filter(InstagramPhoto.date_uploaded > previous_dt,
                                             InstagramPhoto.date_uploaded <= today_dt,
                                             InstagramPhoto.stream_id == stream.id).count()
        if count > 0:
            digest = Digest(subscription_id=subscription.id, end_date=today_dt,
                            start_date=previous_dt)
            db.session.add(digest)
            subscription.last_digest = today_dt
            db.session.add(subscription)
            db.session.commit()
            app.logger.info("Digest created.")
    return digest

def send_digest(digest, env):
    digest_encoded = hash_gen.encrypt(digest.id)
    subscription = digest.subscription
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
    user = subscription.user
    template = env.get_template("email_digest.html")
    html = template.render(entries=entries, stream=stream, digest_encoded=digest_encoded, digest=digest, email=True, max_images=10)
    html_email = premailer.transform(html, base_url="http://digestif.me")
    title = "A new photo digest from {}".format(metadata(stream))
    text_email =  "Digestif\n\nYou have a new digest of photographs to view from {}. View this email as HTML or visit http://digestif.me/digest/{}\n\nWant to change the delivery rate? Adjust your subscription at http://digestif.me{}\n\n Digestif converts your photostream into an email digest. Your friends and family subscribe and decide how frequently they want digests delivered. That way, when you post new photographs your friends and family are notified on their terms.".format(metadata(stream), digest_encoded, stream.subscribe_url())

    if sendgrid_send(user.email, title, text_email, html_email):
        digest.delivered = True
        app.logger.info("Digest delivered to {}".format(user.email))
        db.session.commit()

def send_welcome(subscription, stream, env):
    user = subscription.user
    template = env.get_template("email_subscribe.html")
    html = template.render(stream=stream, subscription=subscription)
    html_email = premailer.transform(html, base_url="http://digestif.me")
    title = "Welcome to {}'s photo digests!".format(metadata(stream))
    text_email = "Welcome to Digestif!\n\nWe will start sending digests of {}'s photographs. Add us to your contact list to avoid our emails being marked as spam.\n\nIf you received this email by mistake, visit http://digestif.me{} to adjust your subscription.".format(metadata(stream),  stream.subscribe_url())

    if mandrill_send(user.email, title, text_email, html_email):
        app.logger.info("Subscription welcome delivered to {}".format(user.email))
        return True
    else:
        return False

def send_stream(user, stream, env):
    template = env.get_template("email_stream.html")
    html = template.render(stream=stream)
    html_email = premailer.transform(html, base_url="http://digestif.me")
    title = "Share your photographs with friends and family"
    text_email = "Welcome to Digestif!\n\nWe will make your photographs into great email digests.\n\nTell your friends and family to visit http://digestif.me{} to subscribe. You can keep track of your subscriber stats by visiting http://digestif.me/stats".format(stream.subscribe_url())
    if mandrill_send(user.email, title, text_email, html_email):
        app.logger.info("Stream welcome delivered to {}".format(user.email))
        return True
    else:
        return False
        
def sendgrid_send(to_address, title, text, html):
    s = sendgrid.Sendgrid(keys.SENDGRID_USER, keys.SENDGRID, secure=True)
    message = sendgrid.Message(("digests@digestif.me", "Digestif"), title, text, html)
    message.add_to(to_address)
    return s.web.send(message)
    
def mandrill_send(to_address, title, text, html):
    m = mandrill.Mandrill(keys.MANDRILL)
    #m = mandrill.Mandrill(keys.MANDRILL_TEST) # test account
    msg = {"from_email": "digests@digestif.me",
           "from_name" : "Digestif",
           "to": [{"email" : to_address}],
           "subject": title,
           "text" : text,
           "html" : html}
    result = m.messages.send(msg)
    if result[0]["status"] == "sent":
        return True
    else:
        app.logger.info("Failed to send email: {}".format(result))
        return False

from datetime import datetime

from digestif import flickr_oauth as flickr
from digestif.models import Stream, FlickrPhoto
from digestif import db

FLICKR_DATE = "%Y-%m-%d %H:%M:%S"

def retrieve_photos(stream, since=None):
    # if since date not specified we'll default to last time we checked
    # the stream
    if not since:
        since = stream.last_checked
    now = datetime.utcnow()
    token = (stream.oauth_token, stream.oauth_token_secret)
    # build the query
    query = {"method" : "flickr.people.getPhotos",
             "user_id" : stream.foreign_key,
             "extras" : "date_upload, date_taken, description",
             "format" : "json",
             "nojsoncallback" : 1,
             "min_upload_date" :  (since - datetime(1970, 1, 1)).total_seconds()}
    # make the call and get the response
    resp = flickr.get('', data=query, token=token)
    
    successful = False
    page = None
    pages = None

    # on successful response get the paging data
    if resp.status == 200:
        page = int(resp.data["photos"]["page"])
        pages = int(resp.data["photos"]["pages"])

    # do the page dance!
    while resp.status == 200 and page <= pages:       
        for photo in resp.data["photos"]["photo"]:
            flickrphoto = create_flickr_photo(photo, stream)
        query["page"] = page + 1
        # dance dance dance
        resp = flickr.get('', data=query, token=token)
        if resp.status == 200:
            page = int(resp.data["photos"]["page"])
            pages = int(resp.data["photos"]["pages"])
        successful = True

    if resp.status != 200:
        successful = False
        # TODO log a problem
        print "Response code: %s\n data:%s" % (resp.status, resp.data)
    
    stream.last_checked = now
    db.session.add(stream)
    db.session.commit()
    return resp.status
    
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
        db.session.commit()
    else:
        # already present
        print flickrphoto, "already present"
    return flickrphoto
                              
               

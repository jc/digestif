from datetime import datetime

from digestif import flickr_oauth as flickr
from digestif.models import Publication, FlickrPhoto, ExternalProcess
from digestif import db

FLICKR_DATE = "%Y-%m-%d %H:%M:%S"

def retrieve_photos(pub, since=None):
    if not since:
        since = pub.last_updated
    now = datetime.utcnow()
    token = (pub.oauth_token, pub.oauth_token_secret)
    query = {"method" : "flickr.people.getPhotos",
             "user_id" : pub.remote_id,
             "extras" : "date_upload, date_taken, description",
             "format" : "json",
             "nojsoncallback" : 1,
             "min_upload_date" :  (since - datetime(1970, 1, 1)).total_seconds()}
        
    print query
    resp = flickr.get('', data=query, token=token)
    successful = False
    page = None
    pages = None
    if resp.status == 200:
        page = int(resp.data["photos"]["page"])
        pages = int(resp.data["photos"]["pages"])
        print page, pages
    while resp.status == 200 and page <= pages:       
        for photo in resp.data["photos"]["photo"]:
            flickrphoto = new_flickrphoto(photo, pub)
        query["page"] = page + 1
        resp = flickr.get('', data=query, token=token)
        if resp.status == 200:
            page = int(resp.data["photos"]["page"])
            pages = int(resp.data["photos"]["pages"])
            print page, pages
        successful = True
    if resp.status != 200:
        successful = False
        print "Response code: %s\n data:%s" % (resp.status, resp.data)
    pub.last_updated = now
    ext = ExternalProcess(pub_id=pub.id, date=now, successful=successful, msg=resp.status)
    pub.processes.append(ext)
    db.session.add(ext)
    db.session.add(pub)
    db.session.commit()
    return resp.status
    
def new_flickrphoto(photo, pub):
    id = photo["id"]
    farm = photo["farm"]
    server = photo["server"]
    secret = photo["secret"]
    date_uploaded = datetime.fromtimestamp(float(photo["dateupload"]))
    date_taken = datetime.strptime(photo["datetaken"], FLICKR_DATE)
    title = photo["title"]
    description = photo["description"]["_content"]
    flickrphoto = None
    flickrphoto = FlickrPhoto.query.filter_by(remote_id=id).first()
    video = False
    if "media" in photo and photo["media"] == "video":
        video = True
    if not flickrphoto:
        flickrphoto = FlickrPhoto(remote_id=id, publication_id=pub.id,
                                  farm=farm, server=server, secret=secret,
                                  title=title, description=description,
                                  date_uploaded=date_uploaded,
                                  date_taken=date_taken, video=video)
        db.session.add(flickrphoto)
        print "adding", flickrphoto
    else:
        print flickrphoto, "already present"
    db.session.commit()
    
    return flickrphoto
                              
               

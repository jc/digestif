from flask import session, request, g, redirect, url_for, abort, render_template, flash

from digestif import app
from digestif import database
from digestif import flickr_oauth
from digestif.models import Entry

@flickr_oauth.tokengetter
def get_flickr_token(token=None):
    #pass return (token, secret) or None
    return session.get('flickr_token')


@app.route('/login/flickr')
def login():
    return flickr_oauth.authorize(callback=url_for('oauth_flickr_authorized', \
      next=request.args.get('next') or request.referrer or None))

@app.route('/oauth-authorized')
@flickr_oauth.authorized_handler
def oauth_flickr_authorized(resp):
    next_url = request.args.get('next') or url_for('account')
    if resp is None:
        flash(u'You denied the request to sign in.')
        return redirect(next_url)

    session['flickr_token'] = (\
        resp['oauth_token'], \
        resp['oauth_token_secret']
    )
    session['flickr_user'] = resp['username']

    flash('You were signed in as %s' % resp['username'])
    return redirect(next_url)

@app.route("/account")
def account():
    print session
    return "Hello %s" % (session.get('flickr_user') or "stranger!")

@app.route("/logout")
def logout():
    if 'flickr_token' in session:
        del session['flickr_token']
        del session['flickr_user']
    return 'Logged out. <a href="/login/flickr?next=/account">Login</a> again.'

@app.route("/")
def show_entries():
    entries = [Entry({"main_src" : "http://michelleandjames.net/p/hjc1.jpg", "caption" : "Hello"})] * 3
    return render_template("show_entries.html", entries=entries)

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

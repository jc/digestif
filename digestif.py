from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, _app_ctx_stack
import json
from datetime import datetime, timedelta

DEBUG = True
SECRET_KEY = "DEVELOPMENT"

app = Flask(__name__)
app.config.from_object(__name__)
app.data = []


class Entry(object):
    def __init__(self, d):
        self.d = d
    def __getattr__(self, attr):
        return self.d[attr]


def load_json():
    data = json.load(open("data.json", "r"))
    for photo in data["photos"]["photo"]:
        app.data.append(Entry({"main_src" : photo["url_c"], \
                                   "caption" : photo["title"], \
                                   "date" : datetime.fromtimestamp(int(photo["dateupload"]))}))
    

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
    for entry in app.data:
        if entry.date >= previous_dt and entry.date <= today_dt:
            entries.append(entry)
    if today_dt - previous_dt < frequency_td:
        entries = []
    return render_template("show_entries.html", entries=entries)
    

if __name__ == "__main__":
    load_json()
    app.run()

from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, _app_ctx_stack

DEBUG = True
SECRET_KEY = "DEVELOPMENT"

app = Flask(__name__)
app.config.from_object(__name__)

class Entry(object):
    def __init__(self, d):
        self.d = d
    def __getattr__(self, attr):
        return self.d[attr]

@app.route("/")
def show_entries():
    entries = [Entry({"main_src" : "http://michelleandjames.net/p/hjc1.jpg", "caption" : "Hello"})] * 3
    return render_template("show_entries.html", entries=entries)


if __name__ == "__main__":
    app.run()

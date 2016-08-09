from flask.ext.wtf import Form
from wtforms import TextField, validators, HiddenField, SelectField

class SignUpStream(Form):
    email = TextField("Email address", [validators.Email("Please enter a valid email address.")])
    stream = HiddenField("stream", [validators.AnyOf(["flickr", "instagram"], message="You forgot to click the Flickr or Instagram icon.")], default="flickr")

class SubscribeForm(Form):
    email = TextField("Email", [validators.Email(message="Please enter a valid email address")])
    frequency = HiddenField("frequency", [validators.AnyOf(["0", "1", "2", "3", "7", "14"])])

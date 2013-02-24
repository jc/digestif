from digestif import app, load_json
load_json("data.json")
app.run(debug=True)

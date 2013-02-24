class Entry(object):
    def __init__(self, d):
        self.d = d
    def __getattr__(self, attr):
        return self.d[attr]


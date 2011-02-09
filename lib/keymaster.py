""" Keymaster stores encrypted keys in the datastore 

The purpose of this module is to provide an easy abstraction for initially 
setting and then getting at secret keys for other services. To use, just
include this line in your app.yaml under handlers:

- url: /_km/.*
  script: shared/keymaster.py
  login: admin

Now you can go to /_km/key as an admin user to create a key. You enter the
key name and the key, then submit. The key will be encrypted in the datastore
which is primarily to make it harder for people with admin access to easily
see keys. It's assumed admins are mostly trusted, the encryption is just a 
layer of obfuscation. If you can't hash a password, at least obfuscate it!

Using the API is just importing and then using the get function:

from shared import keymaster

descrypted_password = keymaster.get('some_service:api_key')

In the case where you might be getting a new access token periodically, say
with cron.yaml, you can also use keymaster.set(key, secret)

"""
import os
import urllib

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

try:
    from shared.utils import RedirectException
except ImportError:
    from utils import RedirectException

try:
    from Crypto.Cipher import ARC4
except ImportError:
    # Just pass through in dev mode
    class ARC4:
        new = classmethod(lambda k,x: ARC4)
        encrypt = classmethod(lambda k,x: x)
        decrypt = classmethod(lambda k,x: x)

class Keymaster(db.Model):
    secret  = db.BlobProperty(required=True)
    
    @classmethod
    def encrypt(cls, key_name, secret):
        secret  = ARC4.new(os.environ['APPLICATION_ID']).encrypt(secret)
        k = cls.get_by_key_name(key_name)
        if k:
            k.secret = str(secret)
        else:
            k = cls(key_name=str(key_name), secret=str(secret))
        return k.put()
    
    @classmethod
    def decrypt(cls, key_name):
        k = cls.get_by_key_name(str(key_name))
        if k is None:
            raise RedirectException('/_km/key/%s' % key_name, "Keymaster has no secret for %s" % key_name)
        return ARC4.new(os.environ['APPLICATION_ID']).encrypt(k.secret)

def get(key):
    return Keymaster.decrypt(key)

def set(key, secret):
    Keymaster.encrypt(key, secret)

class KeymasterHandler(webapp.RequestHandler):
    @util.login_required
    def get(self, key=None):
        if users.is_current_user_admin():
            if key:
                key = urllib.unquote(key)
                self.response.out.write("""<html><body><form method="post">
                    <input type="hidden" name="key" value="%(key)s" />
                    Need a key for <strong>%(key)s</strong>: <input type="text" name="secret" /> <input type="submit" value="Save" /></form></body></html>""" % locals())
            else:
                self.response.out.write("""<html><body><form method="post">
                    Key name: <input type="text" name="key" /><br />
                    Key secret: <input type="text" name="secret" /> <input type="submit" value="Save" /></form></body></html>""")
        else:
            self.redirect('/')
        
    def post(self, key=None):
        if users.is_current_user_admin():
            Keymaster.encrypt(self.request.get('key'), self.request.get('secret'))
            self.response.out.write("Saved: %s" % Keymaster.decrypt(self.request.get('key')))
        else:
            self.redirect('/')

def main():
    application = webapp.WSGIApplication([
        ('/_km/key', KeymasterHandler),
        ('/_km/key/(.+)', KeymasterHandler),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()


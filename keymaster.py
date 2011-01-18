""" Keymaster stores encrypted keys in the datastore 

The purpose of this module is to provide an easy abstraction for initially 
setting and then getting at secret keys for other services. To use, just
include this line in your app.yaml under handlers:

- url: /_km/.*
  script: keymaster.py
  login: admin

Now you can go to /_km/key as an admin user to create a key. You enter the
key name and the key, then submit. The key will be encrypted in the datastore
which is primarily to make it harder for people with admin access to easily
see keys. It's assumed admins are mostly trusted, the encryption is just a 
layer of obfuscation. If you can't hash a password, at least obfuscate it!

Using the API is just importing and then using the get function:

import keymaster

descrypted_password = keymaster.get('some_service:api_key')

In the case where you might be getting a new access token periodically, say
with cron.yaml, you can also use keymaster.set(key, secret)

"""
from google.appengine.api import urlfetch, memcache, users
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util
import os
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
        if not k:
            raise Exception("Keymaster has no secret for %s" % key_name)
        return ARC4.new(os.environ['APPLICATION_ID']).encrypt(k.secret)

def get(key):
    return Keymaster.decrypt(key)

def set(key, secret):
    Keymaster.encrypt(key, secret)

class KeymasterHandler(webapp.RequestHandler):
    @util.login_required
    def get(self):
        if users.is_current_user_admin():
            self.response.out.write("""<html><body><form method="post">
                <input type="text" name="key" /><input type="text" name="secret" /><input type="submit" /></form></body></html>""")
        else:
            self.redirect('/')
        
    def post(self):
        if users.is_current_user_admin():
            Keymaster.encrypt(self.request.get('key'), self.request.get('secret'))
            self.response.out.write("Saved: %s" % Keymaster.decrypt(self.request.get('key')))
        else:
            self.redirect('/')

def main():
    application = webapp.WSGIApplication([
        ('/_km/key', KeymasterHandler),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()


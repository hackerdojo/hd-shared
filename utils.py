import cgi
import Cookie
import datetime
import logging
import sys
import traceback

from google.appengine.ext import webapp

def set_cookie(response, key, value, expires=0):
    """ Convenience function for setting a cookie """
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=expires)
    cookie = Cookie.SimpleCookie()
    cookie[key] = value
    cookie[key]["path"] = "/"
    cookie[key]["expires"] = \
      expiration.strftime("%a, %d %b %Y %H:%M:%S")
    response.headers.add_header('Set-Cookie', cookie.output().split(': ', 1)[1])

def no_cache(response):
    """ Convenience function for making sure a page will not cache """
    response.headers.add_header('Expires', "0")
    response.headers.add_header('Cache-Control', "no-store, no-cache, must-revalidate")
    response.headers.add_header('Cache-Control', "post-check=0, pre-check=0")
    response.headers.add_header('Pragma', "no-cache")

def flatten(l):
    """ This takes a hierarchy of lists/tuples and flattens them into one """
    out = []
    for item in l:
        if isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

class RedirectException(Exception):
    def __init__(self, uri, message):
        self.uri = uri
        super(RedirectException, self).__init__(message)
    
    @staticmethod
    def handle_exception(self, exception, debug_mode):
        if isinstance(exception, RedirectException):
            self.redirect(exception.uri)
        else:
            self.error(500)
            logging.exception(exception)
            if debug_mode:
                lines = ''.join(traceback.format_exception(*sys.exc_info()))
                self.response.clear()
                self.response.out.write('<pre>%s</pre>' % (cgi.escape(lines, quote=True)))

# webapp framework monkey patch to support RedirectException
webapp.RequestHandler.handle_exception = RedirectException.handle_exception


def Redirect(path):
    """ Convenience RequestHandler that simply redirects to a path """
    class RedirectHandler(webapp.RequestHandler):
        def get(self):
            self.redirect(path)
    return RedirectHandler
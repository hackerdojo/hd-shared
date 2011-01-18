""" API access to other Dojo apps

Here we have wrappers for accessing data in other Hacker Dojo applications that
take care of local caching and failure scenarios. 

One common failure scenario is that App Engine instances can take a while to 
respond as they spin up after a period of inactivity, which commonly times out 
the App Engine API for making HTTP requests. The core request caching 
machanism here attempts to deal with this by keeping a failover copy of the
last good response that it will use when a request cache expires and the new 
request fails to respond in a timely fashion. It will keep using this while 
trying every time until it gets a good response. 

"""
from google.appengine.api import urlfetch
from django.utils import simplejson


def _request(url, cache_ttl=3600, force=False):
    request_cache_key = 'request:%s' % url
    failure_cache_key = 'failure:%s' % url
    resp = memcache.get(request_cache_key)
    if force or not resp:
        try:
            resp = simplejson.loads(urlfetch.fetch(url, deadline=5).content)
            memcache.set(request_cache_key, resp, cache_ttl)
            memcache.set(failure_cache_key, resp, cache_ttl*10)
        except (ValueError, urlfetch.DownloadError), e:
            # Not valid JSON or request timeout
            resp = memcache.get(failure_cache_key)
            if not resp:
                resp = []
    return resp
        

def domain(path, force=False):
    base_url = 'http://domain.hackerdojo.com'
    return _request(base_url + path, force=force)
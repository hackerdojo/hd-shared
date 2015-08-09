import time
import threading
from wsgiref import simple_server

import api

# Because request deadlines cause an IOError and the default
# WSGI stack catches and prints these exceptions, we will get 
# pointless exceptions after passing tests without this hack.
simple_server.ServerHandler.log_exception = lambda x,y: None

# Silences the default WSGI stack request logging output.
simple_server.WSGIRequestHandler.log_request = lambda x,y,z: None

# For testing purposes, set the request deadline to 1s
api.DEADLINE = 1

def serve_once(handler, port=4442):
    """ Single serving web server
    
    Creates a web server in another thread that will output the result of 
    handler for a single request. Returns a URL to hit the web server.
    """
    def app(e, start):
        start("200 OK", [])
        return [handler()]
    httpd = simple_server.make_server('', port, app)
    threading.Thread(target=httpd.handle_request).start()
    return "http://localhost:%s/" % port


def test_request():
    # Make sure it returns a fresh response
    url = serve_once(lambda: """["foobar"]""")
    resp = api._request(url)
    assert "foobar" in resp
    
    # Server is now gone, but response is cached
    resp = api._request(url)
    assert "foobar" in resp
    
    # Now we get something else, forcing actual request
    url = serve_once(lambda: "[42]")
    resp = api._request(url, force=True)
    assert 42 in resp
    
    # Force request of non-JSON will fallback to last good response
    url = serve_once(lambda: "Certainly not JSON.")
    resp = api._request(url, force=True)
    assert 42 in resp
    
    # Same when forcing request to non-existant server
    resp = api._request(url, force=True)
    assert 42 in resp
    
    # Or when it takes longer than deadline to serve
    def wait_past_deadline():
        time.sleep(api.DEADLINE+1)
        return "[666]"
    url = serve_once(wait_past_deadline)
    resp = api._request(url, force=True)
    assert 42 in resp
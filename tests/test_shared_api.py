import threading
import time
import socket
import unittest

from google.appengine.ext import testbed

from wsgiref import simple_server

from .. import api


""" Tests for api.py. """
class SharedApiTest(unittest.TestCase):
  def setUp(self):
    # Set up the testbed framework.
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_urlfetch_stub()
    self.testbed.init_memcache_stub()

    # Because request deadlines cause an IOError and the default
    # WSGI stack catches and prints these exceptions, we will get
    # pointless exceptions after passing tests without this hack.
    simple_server.ServerHandler.log_exception = lambda x,y: None

    # Silences the default WSGI stack request logging output.
    simple_server.WSGIRequestHandler.log_request = lambda x,y,z: None

    # For testing purposes, set the request deadline to 1s
    api.DEADLINE = 1

    self.threads = []

  def tearDown(self):
    self.testbed.deactivate()

  """ Single serving web server

  Creates a web server in another thread that will output the result of
  handler for a single request.
  handler: A function that we are serving the output of.
  port: The port for the server to listen on.
  Returns: URL to hit the web server. """
  def __serve_once(self, handler):
    def app(e, start):
      start("200 OK", [])
      return [handler()]

    port = 1337

    # Especially on Travis, we can't guarantee that a particular port will be
    # open, so just scan forward until we find one.
    while True:
      try:
        httpd = simple_server.make_server('', port, app)
      except socket.error:
        port += 1
        continue
      break

    thread = threading.Thread(target=httpd.handle_request)
    thread.start()
    self.threads.append(thread)
    return "http://localhost:%s/" % port

  """ Tests that it handles requests properly. """
  def test_request(self):
    # Make sure it returns a fresh response
    url = self.__serve_once(lambda: """["foobar"]""")
    resp = api._request(url)
    self.assertIn("foobar", resp)

    # Server is now gone, but response is cached
    resp = api._request(url)
    self.assertIn("foobar", resp)

    # Now we get something else, forcing actual request
    url = self.__serve_once(lambda: "[42]")
    resp = api._request(url, force=True)
    self.assertIn(42, resp)

    # Force request of non-JSON will fallback to last good response
    url = self.__serve_once(lambda: "Certainly not JSON.")
    resp = api._request(url, force=True)
    self.assertIn(42, resp)

    # Same when forcing request to non-existant server
    resp = api._request(url, force=True)
    self.assertIn(42, resp)

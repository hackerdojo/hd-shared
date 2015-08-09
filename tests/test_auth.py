""" Tests for auth.py. """


# We need our externals.
import appengine_config

import json
import os
import unittest
import urllib

from google.appengine.api import memcache
from google.appengine.ext import testbed

import webapp2

import webtest

# This has to go before we import the auth module so that the correct settings
# get loaded.
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from .. import auth


""" Class for creating simulated responses from the signup application for
testing purposes. """
class SignupSimulator(auth.ResponseFactory):
  """ Returns this instead of a true response object.
  content: The response content.
  status_code: The response status code. """
  class ResponseProxy:
    def __init__(self):
      self.content = None
      self.status_code = None

  def __init__(self):
    self.responses = []

  """ Sets a canned response that will be provided the next time someone calls
  get_response(). It stores responses in a sort of queue structure, so each new
  call to set_response() puts a new response on the queue, which will be
  returned in FIFO order by subsequent calls to get_response().
  content: The response content.
  status: The response HTTP status, defaults to 200. """
  def set_response(self, content, status=200):
    response = self.ResponseProxy()
    response.content = content
    response.status_code = status

    self.responses.append(response)

  """ Gets the set response.
  url: The URL to fetch. Will be ignored in this case.
  Returns: The response that was set by set_response(). """
  def get_response(self, url, *args, **kwargs):
    return self.responses.pop(0)


""" A handler subclass expressly for the purpose of testing the login_required
handler. """
class LoginRequiredTestHandler(auth.AuthHandler):
  @auth.AuthHandler.login_required
  def get(self):
    self.response.out.write("okay")


""" Same thing, but for the current_user method. """
class CurrentUserTestHandler(auth.AuthHandler):
  def get(self):
    current_user = self.current_user()
    if current_user:
      self.response.out.write(json.dumps(current_user))

""" Same thing for the admin_only handler. """
class AdminOnlyTestHandler(auth.AuthHandler):
  @auth.AuthHandler.admin_only
  def get(self):
    self.response.out.write("okay")

""" Tests for AuthHandler. """
class AuthHandlerTest(unittest.TestCase):
  def setUp(self):
    # Have the handler use SignupSimulator instead of actually fetching URLs.
    self.signup_app = SignupSimulator()
    auth.AuthHandler.URL_FETCHER = self.signup_app

    # Create an encapsulating app that will host the TestHandler.
    app = webapp2.WSGIApplication([
        ("/test_login_required", LoginRequiredTestHandler),
        ("/test_current_user", CurrentUserTestHandler),
        ("/test_admin_only", AdminOnlyTestHandler)], debug=True)
    self.test_app = webtest.TestApp(app)

    # Set up testbed.
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()

    # Some values that we will use for a fake auth cookie.
    self.auth_cookie_values = json.dumps({"user": 1,
                                          "token": "anunlikelytoken"})

  def tearDown(self):
    auth.AuthHandler.URL_FETCHER = auth.UrlFetch()

  """ Tests that it does nothing if a user is logged in already. """
  def test_logged_in_user(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    # Set the fake response we want the "signup app" to give.
    self.signup_app.set_response(json.dumps({"valid": True}))

    response = self.test_app.get("/test_login_required")
    self.assertEqual(200, response.status_int)
    self.assertEqual("okay", response.body)

  """ Tests that it redirects to the login page if there is no logged in user.
  """
  def test_no_cookie(self):
    response = self.test_app.get("/test_login_required")

    self.assertEqual(302, response.status_int)
    self.assertIn("/login", response.location)
    self.assertEqual("", response.body)


  """ Tests that it redirects to the login page if the cookie is invalid. """
  def test_invalid_auth(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    self.signup_app.set_response(json.dumps({"valid": False}))

    response = self.test_app.get("/test_login_required")

    self.assertEqual(302, response.status_int)
    self.assertIn("/login", response.location)
    self.assertEqual("", response.body)

  """ Tests that it correctly strips and saves user and token parameters. """
  def test_user_token_handling(self):
    query_str = urllib.urlencode({"user": 1, "token": "anunlikelytoken"})
    response = self.test_app.get("/test_login_required?" + query_str)
    self.assertEqual(302, response.status_int)

    self.assertIn("test_login_required", response.location)
    self.assertNotIn("user", response.location)
    self.assertNotIn("token", response.location)
    self.assertEqual("", response.body)

    # It should have saved the cookie.
    cookie_values = self.test_app.cookies["auth"]
    self.assertIn("user", cookie_values)
    self.assertIn("token", cookie_values)

  """ Tests that we can obtain basic information about the current logged-in
  user. """
  def test_current_user(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    self.signup_app.set_response(json.dumps({"valid": True}))
    user_info = {"first_name": "Testy", "last_name": "Testerson",
                 "is_admin": False, "email": "testy.testerson@gmail.com"}
    self.signup_app.set_response(json.dumps(user_info))

    response = self.test_app.get("/test_current_user")

    self.assertEqual(200, response.status_int)
    new_user_info = json.loads(response.body)
    self.assertEqual(user_info, new_user_info)

    # Check that it's cached.
    cookie_values = json.loads(self.auth_cookie_values)
    cached = memcache.get("user_data.%s" % cookie_values["user"])
    self.assertEqual(user_info, cached)

  """ Tests that current_user handles no user being logged in correctly. """
  def test_no_user(self):
    response = self.test_app.get("/test_current_user")
    self.assertEqual(200, response.status_int)
    self.assertEqual("", response.body)

  """ Tests that it can get user data from the cache. """
  def test_use_cache(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    self.signup_app.set_response(json.dumps({"valid": True}))

    # Cache the data.
    user_info = {"email": "testy.testerson@gmail.com"}
    cookie_values = json.loads(self.auth_cookie_values)
    key = "user_data.%s" % cookie_values["user"]
    memcache.set(key, user_info)

    response = self.test_app.get("/test_current_user")

    self.assertEqual(200, response.status_int)
    new_user_info = json.loads(response.body)
    self.assertEqual(user_info, new_user_info)

  """ Tests that the admin_only decorator allows admins to access something.
  """
  def test_admin_allowed(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    self.signup_app.set_response(json.dumps({"valid": True}))
    # Make the logged-in user an admin.
    self.signup_app.set_response(json.dumps({
        "email": "testy.testerson@gmail.com", "groups": ["admin"]}))

    response = self.test_app.get("/test_admin_only")
    self.assertEqual(200, response.status_int)
    self.assertEqual("okay", response.body)

  """ Tests that the admin_only decorator blocks normal users. """
  def test_non_admin_blocked(self):
    self.test_app.set_cookie("auth", self.auth_cookie_values)
    self.signup_app.set_response(json.dumps({"valid": True}))
    # Make the logged-in user an admin.
    self.signup_app.set_response(json.dumps({
        "email": "testy.testerson@gmail.com", "groups": []}))

    response = self.test_app.get("/test_admin_only", expect_errors=True)
    self.assertEqual(401, response.status_int)
    self.assertIn("must be an admin", response.body)

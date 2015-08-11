""" Manages the signup app user authentication system. """


import datetime
import json
import logging
import urllib
import urlparse

from google.appengine.api import app_identity, memcache, urlfetch

import webapp2

from config import Config


""" A class that on the production app, basically wraps urlfetch.fetch()
transparently. Its purpose is for testing, so we can implement versions that
feed canned responses to the auth machinery for testing purposes. """
class ResponseFactory:
  """ Gets the response for a particular query.
  url: The URL to fetch.
  Returns: The response. """
  def get_response(self, url, *args, **kwargs):
    raise NotImplementedError("Must be overriden in subclass.")


""" Wraps urlfetch.fetch(). """
class UrlFetch(ResponseFactory):
  """ A transparent wrapper around urlfetch.fetch(). Extra arguments are all
  forwarded to the undelying fetch function.
  url: The URL to fetch.
  Returns: The response from fetch(). """
  def get_response(self, url, *args, **kwargs):
    return urlfetch.fetch(url, *args, **kwargs)


""" A RequestHandler subclass for handling requests that require authentication.
"""
class AuthHandler(webapp2.RequestHandler):
  SIGNUP_URL_ = "http://5-dot-signup-dev.appspot.com"
  # Up here so we can change it for testing.
  URL_FETCHER = UrlFetch()
  # Properties to fetch when loading user data from the signup app.
  USER_PROPERTIES_ = ["first_name", "last_name", "email", "groups", "created"]
  # User attributes we are using to simulate login for testing purposes.
  SIMULATED_USER_ = None
  # How many days our sessions last for by default.
  SESSION_LENGTH = 30

  """ Function meant to be used as a decorator. It's purpose is to ensure that a
  valid user is logged in before running whatever it is decorating.
  function: The function we are decorating.
  Returns: A wrapped version of the function. """
  @classmethod
  def login_required(cls, function):
    """ The wrapper function that does that actual check. """
    def wrapper(self, *args, **kwargs):
      if not self.validate_user():
        # They need to log in.
        logging.debug("Redirecting to login page.")
        self.redirect(self.create_login_url(self.request.uri))
        return

      return function(self, *args, **kwargs)

    return wrapper

  """ Simulates a logged-in user for testing purposes.
  user: A dict containing user information, will be returned by current_user()
  in subsequent calls. An empty dict means that no user is logged in. """
  @classmethod
  def simulate_user(cls, user):
    cls.SIMULATED_USER_ = user

  def __init__(self, *args, **kwargs):
    super(AuthHandler, self).__init__(*args, **kwargs)

    self.user_valid = None

  """ Converts relative URLs relative to this app into absolute URLs. This is
  important when we send these URLs to the signup app.
  url: The relative URL to convert. """
  def __absolute_url(self, url):
    if not url.startswith("/"):
      # It's absolute to begin with.
      return url

    url_parts = urlparse.urlparse(self.request.uri)
    url_base = "%s://%s" % (url_parts.scheme, url_parts.netloc)
    return urlparse.urljoin(url_base, url)

  """ Creates a URL that a user can use to log in. Equivalent to the function of
  the same name from the GAE users module.
  return_url: The URL to redirect to once we are logged in.
  Returns: The login URL. """
  def create_login_url(self, return_url):
    return_url = self.__absolute_url(return_url)

    app_id = app_identity.get_application_id()
    query_str = urllib.urlencode({"url": return_url, "app_id": app_id})
    url = "%s/login?%s" % (self.SIGNUP_URL_, query_str)

    logging.debug("Login url: %s" % (url))
    return url

  """ Creates a URL that a user can use to log out. Equivalent to the function of
  the same name from the GAE users module.
  return_url: The URL to redirect to once we are logged in.
  Returns: The logout URL, or None, if no user is logged in. """
  def create_logout_url(self, return_url):
    return_url = self.__absolute_url(return_url)

    cookie_values = self.request.cookies.get("auth")
    if not cookie_values:
      return None
    cookie_values = json.loads(cookie_values)

    app_id = app_identity.get_application_id()
    query_str = urllib.urlencode({"url": return_url, "app_id": app_id,
                                  "user": cookie_values["user"],
                                  "token": cookie_values["token"]})
    url = "%s/logout?%s" % (self.SIGNUP_URL_, query_str)

    logging.debug("Logout URL: %s" % (url))
    return url

  """ Gets information about the current logged-in user from the signup app.
  Returns: A dict containing information about the user. The user properties to
  fetch are specified in the USER_PROPERTIES_ constant. If no user is logged in,
  or it cannot obtain information about the user, it returns None. """
  def current_user(self):
    # Use simulated user for testing.
    if self.SIMULATED_USER_ != None:
      if not Config().is_testing:
        error = "Cannot simulate user on non-unittest."
        logging.critical(error)
        raise RuntimeError(error)

      # {} means no logged-in user. None means that we are not using a simulated
      # user.
      if self.SIMULATED_USER_ == {}:
        return None
      return self.SIMULATED_USER_

    cookie_values = self.request.cookies.get("auth")
    if not cookie_values:
      return None
    cookie_values = json.loads(cookie_values)

    # First, check that the user is valid to begin with.
    if not self.validate_user():
      logging.debug("User is not valid.")
      return None

    # Check if we have any cached data for this.
    key = "user_data.%s" % cookie_values["user"]
    user_data = memcache.get(key)
    if user_data:
      return user_data

    logging.debug("Cache miss on data for user %s." % (cookie_values["user"]))

    # Fetch the URL.
    query_str = urllib.urlencode({"id": cookie_values["user"],
                                  "properties[]": self.USER_PROPERTIES_}, True)
    url = "%s/api/v1/user?%s" % (self.SIGNUP_URL_, query_str)
    logging.debug("Fetching URL: %s" % (url))
    response = self.URL_FETCHER.get_response(url, follow_redirects=False)
    if response.status_code != 200:
      logging.error("API call failed with status %d." % (response.status_code))
      return None

    user_data = json.loads(response.content)
    logging.debug("Got user data: %s" % (user_data))

    # Cache it.
    memcache.set(key, user_data)

    return user_data

  """ Checks if the current user is valid.
  Returns: True if the user is valid, False otherwise. """
  def validate_user(self):
    # Check if we should use the simulated user.
    if self.SIMULATED_USER_ != None:
      if not Config().is_testing:
        error = "Cannot simulate user on non-unittest."
        logging.critical(error)
        raise RuntimeError(error)

      if self.SIMULATED_USER_ == {}:
        return False
      return True

    # If we already validated the user for this request, we probably don't need
    # to do it again.
    if self.user_valid != None:
      return self.user_valid

    # Read the cookie to determine who's logged in.
    cookie_values = self.request.cookies.get("auth")
    if not cookie_values:
      self.user_valid = False
      return False

    cookie_values = json.loads(cookie_values)

    # Try validating the login.
    query_str = urllib.urlencode({"user": cookie_values["user"],
                                  "token": cookie_values["token"]})
    response = self.URL_FETCHER.get_response("%s/validate_token?%s" % \
                                              (self.SIGNUP_URL_, query_str),
                                              method="POST",
                                              follow_redirects=False)
    if response.status_code != 200:
      logging.error("Got bad response (%d), forcing login." % \
                    (response.status_code))
      self.user_valid = False
      return False
    else:
      # Check to see what it said.
      if not json.loads(str(response.content))["valid"]:
        self.user_valid = False
        return False

    self.user_valid = True
    return True

  """ Overriden dispatch method to deal with intercepting requests with user and
  token parameters and saving them in a cookie. """
  def dispatch(self, *args, **kwargs):
    # If we have the user and token parameters, that means we came from the
    # login page. Save them to a cookie and hide them.
    user = self.request.get("user")
    token = self.request.get("token")
    if (user and token):
      logging.debug("Got user %s and token." % (user))

      cookie_values = json.dumps({"user": user, "token": token})
      expires = datetime.datetime.now() + \
          datetime.timedelta(days=self.SESSION_LENGTH)
      self.response.set_cookie("auth", cookie_values, httponly=True,
                               expires=expires)

      # Redirect to a version of the page without them.
      redirect_url = self._remove_params(["user", "token"])
      logging.debug("Redirecting to %s." % (redirect_url))
      self.redirect(redirect_url)
      return

    super(AuthHandler, self).dispatch(*args, **kwargs)

  """ Removes specified parameters from a GET request.
  parameters: A list of parameters to remove.
  Returns: A new URL to redirect to, or None if no redirect is necessary. """
  def _remove_params(self, parameters):
    # Redirect to a version of the page without them.
    url_parts = urlparse.urlparse(self.request.uri)
    base_url = "%s://%s%s" % (url_parts.scheme, url_parts.netloc,
                              url_parts.path)

    query = urlparse.parse_qs(url_parts.query)
    changed = False
    for parameter in parameters:
      if parameter in query.keys():
        del query[parameter]
        changed = True

    if not changed:
      return None

    redirect_url = "%s?%s" % (base_url, urllib.urlencode(query))
    return redirect_url

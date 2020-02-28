import base64
import json
from kazoo import exceptions
import hashlib
import logging
import re
import requests
import urllib
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class HttpsAdapterHack(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=ssl.PROTOCOL_TLSv1)

class KazooRequest(object):
    http_methods = ["get", "post", "put", "delete", "patch"]

    def __init__(self, path, auth_required=True, method='get', get_params=None):
        """An object which takes a path and determines required
        parameters from it, these parameters must be passed to the execute
        method of the object
        """
        self.path = path
        self._required_param_names = self._get_params_from_path(self.path)
        self.auth_required = auth_required
        self.method = method
        self.get_params = get_params

    def _get_params_from_path(self, path):
        param_regex = re.compile("{([a-zA-Z0-9_]+)}")
        param_names = param_regex.findall(path)
        return param_names

    def _get_headers(self, token=None):
        headers = {"Content-Type": "application/json"}
        if self.auth_required:
            headers["X-Auth-Token"] = token
        return headers

    def _get_url(self, params, base_url):
        url = base_url + self._get_url_with_variables_replaced(params)
        if self.get_params:
            return url + "?" + urllib.parse.urlencode(self.get_params)
        return url

    def _get_url_with_variables_replaced(self, params):
        return self.path.format(**params)

    def execute(self, base_url, method=None, data=None, token=None, files=None, **kwargs):
        # if self.auth_required and token is None:
        #     error_message = ("This method requires an auth token, be sure to "
        #                      "call client.authenticate() before making API "
        #                      "calls")
        #     raise exceptions.AuthenticationRequiredError(error_message)
        if method is None:
            method = self.method
        if method.lower() not in self.http_methods:
            raise exceptions.InvalidHttpMethodError("method {0} is not a valid"
                                                    " http method".format(
                                                        method))
        for param_name in self._required_param_names:
            if param_name not in kwargs:
                raise ValueError("keyword argument {0} is required".format(
                    param_name))

        full_url = self._get_url(kwargs, base_url)
        logger.debug("Making {0} request to url {1}".
                     format(method, full_url.encode("utf-8")))

        headers = self._get_headers(token=token)
        req_func = getattr(requests, method)

        kwargs = {}
        if data:
            kwargs["data"] = json.dumps({"data": data})
        if files:
            kwargs["files"] = files
        raw_response = req_func(full_url, headers=headers, **kwargs)

        if base_url.startswith('https'):
            s = requests.Session()
            s.mount('https://', HttpsAdapterHack())

        if raw_response.status_code == 500:
            self._handle_500_error(raw_response)
        response = raw_response.json()
        if response["status"] == "error":
            logger.debug("There was an error, full error text is: {0}".format(
                raw_response.content))
            self._handle_error(response)
        return response

    def _handle_error(self, error_data):
        if error_data["error"] == "400" and ("data" in error_data):
            raise exceptions.KazooApiBadDataError(error_data["data"])

        if error_data['error'] == '401':
            raise exceptions.KazooApiAuthenticationError('Invalid credentials')

        raise exceptions.KazooApiError("There was an error calling the kazoo api, "
                                       "Request ID was {1}"
                                       " the error was {0}".format(
                                           error_data["message"],
                                           error_data["request_id"],
                                       ))

    def _handle_500_error(self, raw_response):
        request_id = raw_response.headers["X-Request-Id"]
        if raw_response.json():
            message = raw_response.json()["data"]
        else:
            message = "There was no error message"
        raise exceptions.KazooApiError("Internal Server Error, "
                                       "Request ID was {0}"
                                       " message was {1}".format(
                                           request_id, message))


class UsernamePasswordAuthRequest(KazooRequest):

    def __init__(self, username, password, account_name):
        super(UsernamePasswordAuthRequest, self).__init__("/user_auth",
                                                          auth_required=False)
        self.username = username
        self.password = password
        self.account_name = account_name

    def execute(self, base_url):
        data = {
            "credentials": self._get_hashed_credentials(),
            "account_name": self.account_name,
        }
        return super(UsernamePasswordAuthRequest, self).execute(base_url,
                                                                method="put",
                                                                data=data)

    def _get_hashed_credentials(self):
        m = hashlib.md5()
        m.update("{0}:{1}".format(self.username, self.password).encode())
        return m.hexdigest()


class ApiKeyAuthRequest(KazooRequest):

    def __init__(self, api_key):
        super(ApiKeyAuthRequest, self).__init__("/api_auth",
                                                auth_required=False)
        self.api_key = api_key

    def execute(self, base_url):
        data = {
            "api_key": self.api_key
        }
        return super(ApiKeyAuthRequest, self).execute(base_url, data=data,
                                                      method="put")

import json
import requests
import kazoo.exceptions as exceptions
import logging
from kazoo.request_objects import KazooRequest, UsernamePasswordAuthRequest, \
    ApiKeyAuthRequest
from kazoo.rest_resources import RestResource

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class RestClientMetaClass(type):

    def __init__(cls, name, bases, dct):
        super(RestClientMetaClass, cls).__init__(name, bases, dct)
        for key, value in dct.items():
            if hasattr(value, "plural_name"):
                cls._add_resource_methods(key, value, dct)

    def _add_resource_methods(cls, resource_field_name, rest_resource, dct):
        cls._generate_list_func(resource_field_name, rest_resource)
        cls._generate_get_object_func(resource_field_name, rest_resource)
        cls._generate_delete_object_func(resource_field_name, rest_resource)
        cls._generate_update_object_func(resource_field_name, rest_resource)
        cls._generate_create_object_func(resource_field_name, rest_resource)
        for view_desc in rest_resource.extra_views:
            cls._generate_extra_view_func(view_desc, resource_field_name,
                                          rest_resource)

    def _generate_create_object_func(cls, resource_field_name, rest_resource):
        if "create" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["create"]
        required_args = rest_resource.required_args
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_create_object_request',
            requires_data=True)
        setattr(cls, func_name, func)

    def _generate_list_func(cls, resource_field_name, rest_resource):
        if "list" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["list"]
        required_args = rest_resource.required_args
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_list_request')
        setattr(cls, func_name, func)

    def _generate_get_object_func(cls, resource_field_name, rest_resource):
        if "detail" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["object"]
        required_args = rest_resource.required_args + \
            [rest_resource.object_arg]
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_object_request')
        setattr(cls, func_name, func)

    def _generate_delete_object_func(cls, resource_field_name, rest_resource):
        if "delete" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["delete"]
        required_args = rest_resource.required_args + \
            [rest_resource.object_arg]
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_delete_object_request')
        setattr(cls, func_name, func)

    def _generate_update_object_func(cls, resource_field_name, rest_resource):
        if "update" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["update"]
        required_args = rest_resource.required_args + \
            [rest_resource.object_arg]
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_update_object_request',
            requires_data=True)
        setattr(cls, func_name, func)

    def _generate_extra_view_func(cls, extra_view_desc, resource_field_name,
                                  rest_resource):
        func_name = extra_view_desc["name"]
        if extra_view_desc["scope"] == "aggregate":
            required_args = rest_resource.required_args
        else:
            required_args = rest_resource.required_args + \
                [rest_resource.object_arg]
        if extra_view_desc["method"] in ["put", "post"]:
            requires_data=True
        else:
            requires_data = False
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            extra_view_name=extra_view_desc["path"],
            requires_data=requires_data)
        setattr(cls, func_name, func)

    def _generate_resource_func(cls, func_name, resource_field_name,
                                resource_required_args, request_type=None,
                                extra_view_name=None, requires_data=False):
        # This is quite nasty, the point of it is to generate a function which
        # has named required arguments so that it is nicely self documenting.
        # If you're having trouble following it stick a print statement in
        # around the func_definition variable and then import in a shell.
        required_args = list(resource_required_args)
        if requires_data:
            required_args.append("data")
        required_args_str = ",".join(required_args)
        if len(required_args) > 0:
            required_args_str += ","
        get_request_args = ",".join(["{0}={0}".format(argname)
                                     for argname in required_args])
        if request_type:
            get_request_string = "self.{0}.{1}({2})".format(
                resource_field_name, request_type, get_request_args)
        else:
            get_req_templ = "self.{0}.get_extra_view_request(\"{1}\",{2})"
            get_request_string = get_req_templ.format(
                resource_field_name, extra_view_name, get_request_args)
        if requires_data:
            func_definition = "def {0}(self, {1}): return self._execute_request({2}, data=data)".format(
                func_name, required_args_str, get_request_string)
        else:
            func_definition = "def {0}(self, {1}): return self._execute_request({2})".format(
                func_name, required_args_str, get_request_string)
        func = compile(func_definition, __file__, 'exec')
        d = {}
        exec func in d
        return d[func_name]


class Client(object):
    """The interface to the Kazoo API

    This class should be initialized either with a username, password and
    account name combination, or with an API key. Once you have initialized
    the client you will need to call :meth:`authenticate()` before you can
    begin making API calls. ::

        >>>import kazoo
        >>>client = kazoo.Client(api_key="sdfasdfas")
        >>>client.authenticate()

    You can also initialize with a username and password combination: ::

        >>>client = kazoo.Client(username="myusername", password="mypassword", account_name="my_account_name")
        >>>client.authenticate()

    The default api url is: 'http://api.2600hz.com:8000/v1'.  You can override this
    by supplying an extra argument, 'base_url' to kazoo.Client().

    Example of overriding 'base_url'::

        >>>client = kazoo.Client(base_url='http://api.example.com:8000/v1',
                                 api_key="sdfasdfas")

    API calls which require data take it in the form of a required argument
    called 'data' which is the last argument to the method. For example ::

        >>>client.update_account(acct_id, {"name": "somename", "realm":"superfunrealm"})

    Dictionaries and lists will automatically be converted to their appropriate
    representation so you can do things like: ::

        >>>client.update_callflow(acct_id, callflow_id, {"flow":{"module":"somemodule"}})

    Invalid data will result in an exception explaining the problem.

    The server response is returned from each method as a python dictionary of
    the returned JSON object, for example: ::

        >>>client.get_account(acct_id)
        {u'auth_token': u'abc437d000007d0454cc984f6f09daf3',
         u'data': {u'billing_mode': u'normal',
          u'caller_id': {},
          u'caller_id_options': {},
          u'id': u'c4f64412ad0057222c0009a3e7da011',
          u'media': {u'bypass_media': u'auto'},
          u'music_on_hold': {},
          u'name': u'test3',
          u'notifications': {},
          u'realm': u'4c8050.sip.2600hz.com',
          u'superduper_admin': False,
          u'timezone': u'America/Los_Angeles',
          u'wnm_allow_additions': False},
         u'request_id': u'ea6441422fb85000ad21db4f1e2326c1',
         u'revision': u'3-c16dd0a629fe1da0000e1e7b3e5fb35a',
         u'status': u'success'}

    For each resource exposed by the kazoo api there are corresponding methods
    on the client. For example, for the 'callflows' resource the
    correspondence is as follows. ::

        GET /accounts/{account_id}/callflows -> client.get_callflows(acct_id)
        GET /accounts/{account_id}/callflows/{callflow_id} -> client.get_callflow(acct_id, callflow_id)
        PUT /accounts/{account_id}/callflows/ -> client.create_callflow(acct_id, data)
        POST /account/{account_id}/callflows/{callflow_id} -> client.update_callflow(acct_id, data)
        DELETE /account/{account_id}/callflows/{callflow_id} -> client.delete_callflow(acct_id, callflow_id)

    Some resources do not have all methods available, in which case they are
    not present on the client.

    There are also some resources which don't quite fit this paradigm, they are: ::

        GET /accounts/{account_id}/media -> client.get_all_media(acct_id)
        GET /accounts/{account_id}/children -> client.get_account_children(acct_id)
        GET /accounts/{account_id}/descendants -> client.get_account_descendants(acct_id)
        GET /accounts/{account_id}/devices/status -> client.get_all_devices_status(acct_id)
        GET /accounts/{account_id}/servers/{server_id}/deployment -> client.get_deployment(acct_id, server_id)
        GET /accounts/{account_id}/users/hotdesk -> client.get_hotdesk(acct_id)

    """
    __metaclass__ = RestClientMetaClass
    base_url = "http://api.2600hz.com:8000/v1"

    _accounts_resource = RestResource("account",
                                      "/accounts/{account_id}",
                                      exclude_methods=[],
                                      extra_views=[
                                          {"name": "get_account_children",
                                           "path": "children",
                                           "scope": "object"},
                                          {"name": "get_account_descendants",
                                           "path": "descendants",
                                           "scope": "object"}])

    _callflow_resource = RestResource(
        "callflow",
        "/accounts/{account_id}/callflows/{callflow_id}")

    _conference_resource = RestResource(
        "conference",
        "/accounts/{account_id}/conferences/{conference_id}")

    _device_resource = RestResource(
        "device",
        "/accounts/{account_id}/devices/{device_id}",
        extra_views=[{"name": "get_all_devices_status", "path": "status"}])

    _directories_resource = RestResource(
        "directory",
        "/accounts/{account_id}/directories/{directory_id}",
        plural_name="directories")

    _global_resources = RestResource(
        "global_resource",
        "/accounts/{account_id}/global_resources/{resource_id}")

    _groups_resource = RestResource("group",
                                   "/accounts/{account_id}/groups/{group_id}")

    _limits_resource = RestResource("limit",
                                    "/accounts/{account_id}/limits/{ignored}",
                                    methods=["list"])

    _local_resources_resource = RestResource(
        "local_resource",
        "/accounts/{account_id}/local_resources/{resource_id}")


    _media_resource = RestResource("media",
                                   "/accounts/{account_id}/media/{media_id}",
                                   plural_name="media",
                                   method_names={
                                       "list": "get_all_media"
                                   })

    _menus_resource = RestResource("menu",
                                   "/accounts/{account_id}/menus/{menu_id}")

    _phone_number_resource = RestResource(
        "phone_number",
        "/accounts/{account_id}/phone_numbers/{phone_number}",
        methods=["list", "update", "delete"],
        extra_views=[
            {"name":"activate_phone_number",
             "path": "activate",
             "scope": "object",
             "method": "put"},
            {"name": "reserve_phone_number",
             "path": "reserve",
             "scope": "object",
             "method": "put"},
            {"name": "add_port_in_number",
             "path": "port",
             "scope": "object",
             "method": "put"}])

    _queues_resource = RestResource("queue",
                                    "/accounts/{account_id}/queues/{queue_id}")

    _rates_resource = RestResource("rates",
                                    "/accounts/{account_id}/rates/{rate_id}")

    _server_resource = RestResource(
        "server",
        "/accounts/{account_id}/servers/{server_id}",
        methods=["list"],
        extra_views=[
            {"name": "get_deployment",
             "path": "deployment",
             "scope": "object"},
            {"name": "create_deployment",
             "path": "deployment",
             "scope": "object",
             "method": "put"},
            {"name": "get_server_log", "path": "log"}
        ])

    _temporal_rules_resource = RestResource(
        "temporal_rule",
        "/accounts/{account_id}/temporal_rules/{rule_id}")

    _users_resource = RestResource(
        "user",
        "/accounts/{account_id}/users/{user_id}",
        extra_views=[{"name": "get_hotdesk", "path": "hotdesks"}])

    _vmbox_resource = RestResource(
        "voicemail_box",
        "/accounts/{account_id}/vmboxes/{vmbox_id}",
        plural_name="voicemail_boxes")

    _phone_number_docs_resource = RestResource(
        "phone_number_doc",
        "/accounts/{account_id}/phone_numbers/{phone_number}/docs/{filename}",
        methods=["delete"],
    )

    _webhook_resource = RestResource(
        "webhook",
        "/accounts/{account_id}/webhooks/{webhook_id}")

    def __init__(self, api_key=None, password=None, account_name=None,
                 username=None, base_url=None):
        if not api_key and not password:
            raise RuntimeError("You must pass either an api_key or an "
                               "account name/password pair")

        if base_url is not None:
            self.base_url = base_url

        if password or account_name or username:
            if not (password and account_name and username):
                raise RuntimeError("If using account name/password "
                                   "authentication then you must specify "
                                   "password, userame and account_name "
                                   "arguments")
            self.auth_request = UsernamePasswordAuthRequest(username,
                                                            password,
                                                            account_name)
        else:
            self.auth_request = ApiKeyAuthRequest(api_key)

        self.api_key = api_key
        self._authenticated = False
        self.auth_token = None

    def authenticate(self):
        """Call this before making other api calls to fetch an auth token
        which will be automatically used for all further requests
        """
        if not self._authenticated:
            self.auth_data = self.auth_request.execute(self.base_url)
            self.auth_token = self.auth_data["auth_token"]
            self._authenticated = True
        return self.auth_token

    def _execute_request(self, request, **kwargs):
        from exceptions import KazooApiAuthenticationError

        if request.auth_required:
            kwargs["token"] = self.auth_token

        try:
            return request.execute(self.base_url, **kwargs)
        except KazooApiAuthenticationError as e:
            logger.error('Kazoo authentication failed. Attempting to re-authentication and retry: {}'.format(e))
            self._authenticated = False
            self.auth_token = None
            self.authenticate()
            kwargs["token"] = self.auth_token
            return request.execute(self.base_url, **kwargs)

    def search_phone_numbers(self, prefix, quantity=10):
        request = KazooRequest("/phone_numbers", get_params={
            "prefix": prefix,
            "quantity": quantity
        })
        return self._execute_request(request)

    def create_phone_number(self, acct_id, phone_number):
        request = KazooRequest("/accounts/{account_id}/phone_numbers/{phone_number}",
                               method="put")
        return self._execute_request(request,
                                     account_id=acct_id, phone_number=phone_number)

    def get_phone_number(self, acct_id, phone_number):
        request = KazooRequest("/accounts/{account_id}/phone_numbers/{phone_number}",
                               method="get")
        return self._execute_request(request,
                                     account_id=acct_id, phone_number=phone_number)

    def upload_media_file(self, acct_id, media_id, filename, file_obj):
        """Uploads a media file like object as part of a media document"""
        request = KazooRequest("/accounts/{account_id}/media/{media_id}/raw",
                               method="post")
        return self._execute_request(request, 
                                     account_id=acct_id, 
                                     media_id=media_id,
                                     rawfiles=({filename: file_obj}))

    def upload_phone_number_file(self, acct_id, phone_number, filename, file_obj):
        """Uploads a file like object as part of a phone numbers documents"""
        request = KazooRequest("/accounts/{account_id}/phone_numbers/{phone_number}",
                               method="post")
        return self._execute_request(request, files={filename: file_obj})

    def list_devices_by_owner(self, accountId, ownerId):
        request = KazooRequest("/accounts/{account_id}/devices", get_params={"filter_owner_id": ownerId})
        request.auth_required = True

        return self._execute_request(request, account_id=accountId)

    def list_child_accounts(self, parentAccountId):
        request = KazooRequest("/accounts/{account_id}/children")
        request.auth_required = True

        return self._execute_request(request, account_id=parentAccountId)

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

        for key, value in list(dct.items()):
            if hasattr(value, "plural_name"):
                cls._add_resource_methods(key, value, dct)

    def _add_resource_methods(cls, resource_field_name, rest_resource, dct):
        cls._generate_list_func(resource_field_name, rest_resource)
        cls._generate_get_object_func(resource_field_name, rest_resource)
        cls._generate_delete_object_func(resource_field_name, rest_resource)
        cls._generate_update_object_func(resource_field_name, rest_resource)
        cls._generate_partial_update_object_func(resource_field_name, rest_resource)
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

    def _generate_partial_update_object_func(cls, resource_field_name, rest_resource):
        if "partial_update" not in rest_resource.methods:
            return
        func_name = rest_resource.method_names["partial_update"]
        required_args = rest_resource.required_args + \
            [rest_resource.object_arg]
        func = cls._generate_resource_func(
            func_name,
            resource_field_name,
            required_args,
            request_type='get_partial_update_object_request',
            requires_data=True)
        setattr(cls, func_name, func)

    def _generate_extra_view_func(cls, extra_view_desc, resource_field_name,
                                  rest_resource):
        func_name = extra_view_desc["name"]
        if extra_view_desc["scope"] in [ "aggregate", "system"]:
            required_args = rest_resource.required_args
        else:
            required_args = rest_resource.required_args + \
                [rest_resource.object_arg]
        if extra_view_desc["method"] in ["put", "post", "patch"]:
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

        if request_type == 'get_list_request' and get_request_args:
            get_request_string = "self.{0}.{1}({2}, request_optional_args=optional_args)".format(
            resource_field_name, request_type, get_request_args)

        elif request_type:
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
            if request_type == 'get_list_request' and get_request_args:
                func_definition = "def {0}(self, {1} optional_args=None): return self._execute_request({2} )".format(
                    func_name, required_args_str, get_request_string)
            else:
                func_definition = "def {0}(self, {1}): return self._execute_request({2})".format(
                    func_name, required_args_str, get_request_string)

        func = compile(func_definition, __file__, 'exec')
        d = {}
        exec(func, d)
        return d[func_name]


class Client(metaclass=RestClientMetaClass):
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
    base_url = "http://api.2600hz.com:8000/v1"
    account_id= ""
    """
    
    """
    _access_list_resource = RestResource(
        "access_list",
        "/accounts/{account_id}/access_lists/{access_list_id}",
        methods=["list"],
        extra_views=[{
            "name": "update_all",
            "method": "post",
            "path": ""
        },{
            "name": "delete_all",
            "method": "delete",
            "path": ""
        }
        ]
    )


    _accounts_resource = RestResource("account",
                                      "/accounts/{account_id}",
                                      exclude_methods=['list'],
                                      extra_views=[
                                          {"name": "get_account_children",
                                           "path": "children",
                                           "scope": "object"},
                                          {"name": "get_account_descendants",
                                           "path": "descendants",
                                           "scope": "object"},
                                          {"name": "get_account_siblings",
                                           "path": "siblings"},
                                          {"name": "get_account_tree",
                                           "path": "tree"},
                                          {"name": "get_account_parents",
                                           "path": "parents"},
                                          {"name": "get_account_apikey",
                                           "path": "api_key"},
                                          {"name": "demote_reseller",
                                           "path": "reseller",
                                           "method": "delete"},
                                          {"name": "promote_reseller",
                                           "path": "reseller",
                                           "method": "put"},
                                          {"name": "create_api_key",
                                           "path": "api_key",
                                           "method": "put"},
                                          {"name": "move_account",
                                           "method": "post",
                                           "path": "move"}])
    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/acdc_call_stats
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/acdc_call_stats?created_from={FROM_TIMESTAMP}&created_to={TO_TIMESTAMP}
    Support only GET method 
    Call:
        get_acdc_call_stats(account_id)
    """
    _acdc_call_stat_resource = RestResource(
        "acdc_call_stat",
        "/accounts/{account_id}/acdc_call_stats/{ignored}",
        methods=['list']
        )


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/acls
    Support only GET method
    Call:
        get_acls(account_id)
    """
    _acl_resource = RestResource(
        "acl",
        "/accounts/{account_id}/acls/{ignored}",
        methods=['list']
    )

    _agent_resource = RestResource(
        "agent",
        "/accounts/{account_id}/agents/{agent_id}",
        methods=['list', 'detail'],
        extra_views=[{
            "name": "get_stats",
            "path": "stats"
        },{
            "name": "get_statuses",
            "path": "statuses"
        },{
            "name": "get_queue_status",
            "path": "queue_status",
            "scope": "object"
        },{
            "name": "set_queue_status",
            "path": "queue_status",
            "scope": "object",
            "method": "post"
        },{
            "name": "set_agent_status",
            "path": "status",
            "method": "post",
            "scope": "object"
        },{
            "name": "get_agent_status",
            "path": "status",
            "scope": "object"
        },{
            "name": "set_status_agent",
            "path": "status/{agent_id}",
            "method": "post"
        },{
            "name": "get_status_agent",
            "path": "status/{agent_id}"
        }]
    )

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/alerts
    Support GET,PUT, DELETE methods
       Call:
           create_alert(account_id, data)
           list_alerts(account_id)
           get_alert(account_id, alert_id)
           delete_alert(account_id, alert_id)
    """
    _alert_resource = RestResource(
        "alert",
        "/accounts/{account_id}/alert/{alert_id}",
        exclude_methods=['update', 'partial_update'])


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/apps_link/authorize
    Support only GET method
       Call:
           list_apps_link(account_id)
           
    """
    _apps_link_resource = RestResource(
        "apps_link",
        "/accounts/{account_id}/apps_link/authorize/{ignored}",
        plural_name="apps_link",
        methods=['list'])


    _apps_store_resource = RestResource(
        "apps_store",
        "/accounts/{account_id}/apps_store/{app_id}",
        plural_name="apps_store",
        exclude_methods=['partial_update'],
        extra_views=[{
            "name": "install_app",
            "method": "put",
            "path": "",
            "scope": "object"
        }, {
            "name": "get_icon",
            "path": "icon",
            "scope": "object"
        },{
            "name": "get_screenshot",
            "path": "screenshot/{screenshot_index}",
            "scope": "object"
        },{
            "name": "get_blacklist",
            "path": "blacklist"
        },{
            "name": "update_blacklist",
            "path": "blacklist",
            "method": "post"
        }]
    )

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/blacklists
    Support GET,PUT, DELETE, POST, PATH methods
       Call:
           create_blacklist(account_id, data)
           list_blacklists(account_id)
           get_blacklist(account_id, blacklist_id)
           delete_blacklist(account_id, blacklist_id)
           update_blacklist(account_id, blacklist_id, data)
           partial_update_blacklist(account_id, blacklist_id, data)
    """
    _blacklist_resource = RestResource(
        "blacklist",
        "/accounts/{account_id}/blacklists/{blacklist_id}"
    )

    _braintree_resource = RestResource(
        "braintree",
        "/accounts/{account_id}/braintree/{ignored}",
        plural_name="braintree",
        methods=[],
        extra_views=[{
            "name": "get_client_token",
            "path": "client_token"
        },{
            "name": "list_transactions",
            "path": "transactions"
        },{
            "name": "list_addresses",
            "path": "addresses"
        },{
            "name": "list_credits",
            "path": "credits"
        },{
            "name": "list_cards",
            "path": "cards"
        },{
            "name": "add_credits",
            "path": "credits",
            "method": "put"
        },{
            "name": "get_transaction",
            "path": "transactions/{transaction_id}"
        },{
            "name": "add_cards",
            "path": "cards",
            "method": "put"
        },{
            "name": "get_address",
            "path": "addresses/{ADDRESS_ID}"
        },{
            "name": "delete_address",
            "path": "addresses/{ADDRESS_ID}",
            "method": "delete"
        },{
            "name": "update_address",
            "path": "addresses/{ADDRESS_ID}",
            "method": "post"
        },{
            "name": "get_card",
            "path": "cards/{CARD_ID}"
        },{
            "name": "delete_card",
            "path": "cards/{CARD_ID}",
            "method": "delete"
        },{
            "name": "update_card",
            "path": "cards/{CARD_ID}",
            "method": "post"
        }]
    )

    _bulk_resource = RestResource(
        "bulk",
        "/accounts/{account_id}/bulk/{ingored}",
        plural_name="bulk",
        methods=['list'])


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/call_inspector
    Support only GET methods
       Call:
           list_calls(account_id)
           get_call(account_id, call_id)
    """
    _call_inspector_resource = RestResource(
        "call_inspector",
        "/accounts/{account_id}/call_inspector/{call_id}",
        methods=['list', 'detail'],
        plural_name='call_inspector',
        method_names={
            "list": "list_calls",
            "detail": "get_call"
        }

    )

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/callflows
    Support GET,PUT, DELETE, POST, PATH methods
       Call:
           create_callflow(account_id, data)
           list_callflows(account_id)
           get_callflow(account_id, callflow_id)
           delete_callflow(account_id, callflow_id)
           update_callflow(account_id, callflow_id, data)
           partial_update_callflow(account_id, callflow_id, data)
    """
    _callflow_resource = RestResource(
        "callflow",
        "/accounts/{account_id}/callflows/{callflow_id}")

    """ 
        http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/cccps
        Support GET,PUT, DELETE, POST methods
           Call:
               create_cccp(account_id, data)
               list_cccps(account_id)
               get_cccp(account_id, blacklist_id)
               delete_cccp(account_id, blacklist_id)
               update_cccp(account_id, blacklist_id, data)
        """
    _cccp_resource = RestResource(
        "cccp",
        "/accounts/{account_id}/cccps/{cccp_id}",
        exclude_methods=['partial_update']
    )


    _channel_resource = RestResource(
        "channel",
        "/accounts/{account_id}/channels/{channel_id}",
        methods=['list','detail','update'],
        extra_views=[{
            "name": "execute_command_on_channel",
            "method": "put",
            "path": "",
            "scope": "object"
        }]
    )

    _clicktocall_resource = RestResource(
        "channel",
        "/accounts/{account_id}/clicktocall/{clicktocall_id}",
        plural_name="clicktocall",
        extra_views=[{
            "name": "get_clicktocall_history",
            "scope": "object",
            "path": "history"
        },{
            "name": "clicktocall_connect",
            "scope": "object",
            "path": "connect",
            "method": "post"
        },{
            "name": "list_clicktocall_connects",
            "scope": "object",
            "path": "connect"
        }]
        )

    _conference_resource = RestResource(
        "conference",
        "/accounts/{account_id}/conferences/{conference_id}",
        extra_views=[{
            "name": "conference_action",
            "path": "",
            "scope": "object",
            "method": "put"
        },{
            "name": "list_participants",
            "path": "participants",
            "scope": "object"
        },{
            "name": "action_participants",
            "path": "participants",
            "scope": "object",
            "method": "put"
        },{
            "name": "list_participant",
            "path": "participants/{participant_id}",
            "scope": "object"
        },{
            "name": "action_participant",
            "path": "participants/{participant_id}",
            "scope": "object",
            "method": "put"
        }]
    )

    _config_resource = RestResource(
        "config",
        "/accounts/{account_id}/configs/{config_id}",
        exclude_methods=['list','create'],
        extra_views=[{
            "name": "create_config",
            "method": "put",
            "path": "",
            "scope": "object"
        }]
    )

    _comment_resource = RestResource(
        "comment",
        "/accounts/{account_id}/comments/{comment_id}",
        exclude_methods=['partial_update'],
        extra_views=[{
            "name": "delete_all",
            "path": "",
            "method": "delete"
        }]
    )

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/connectivity
    Support GET,PUT, DELETE, POST, PATH methods
       Call:
           create_connectivity(account_id, data)
           list_connectivities(account_id)
           get_connectivity(account_id, connectivity_id)
           delete_connectivity(account_id, connectivity_id)
           update_connectivity(account_id, connectivity_id, data)
           partial_update_connectivity(account_id, connectivity_id, data)
    """
    _connectivity_resource = RestResource(
        "connectivity",
        "/accounts/{account_id}/connectivity/{connectivity_id}",
        plural_name="connectivities")


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/contact_list
    Support only GET methods
       Call:
           list_contact_list(account_id)
    """
    _contact_list_resource = RestResource(
        "contact_list",
        "/accounts/{account_id}/contact_list/{ignored}",
         plural_name="contact_list",
         methods=["list"])


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/cdrs
    Support only GET methods
       Call:
           list_cdrs(account_id)
           get_cdr(account_id, cdr_id)
    """
    _cdr_resource = RestResource(
        "cdr",
        "/accounts/{account_id}/cdrs/{cdr_id}",
         methods=["list", "detail"],
         extra_views=[{
             "name": "list_interactions",
             "path": "interaction"
         },{
             "name": "get_interaction",
             "path": "legs/{INTERACTION_ID}"
         }])

    _device_resource = RestResource(
        "device",
        "/accounts/{account_id}/devices/{device_id}",
        extra_views=[
            {
                "name": "get_all_devices_status",
                "path": "status"
            },{
                "name": "reboot_device",
                "scope": "object",
                "method": "post",
                "path": "sync"
            },{
                "name": "make_device_quickcall",
                "scope": "object",
                "path": "quickcall/{PHONE_NUMBER}"
            },{
                "name": "update_device_presence",
                "method": "post",
                "scope": "object",
                "path": "presence"
            },{
                "name": "get_device_channels",
                "scope": "object",
                "path": "channels"
            },{
                "name": "get_device_ratelimits",
                "scope": "object",
                "path": "rate_limits"
            },{
                "name": "update_device_ratelimits",
                "scope": "object",
                "path": "rate_limits",
                "method": "post"
            },{
                "name": "get_device_access_lists",
                "scope": "object",
                "path": "access_lists"
            },{
                "name": "delete_device_access_lists",
                "scope": "object",
                "path": "access_lists",
                "method": "delete"
            },{
                "name": "update_device_access_lists",
                "scope": "object",
                "path": "access_lists",
                "method": "post"

    }])


    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/directories
    Support GET,PUT, DELETE, POST, PATH methods
       Call:
           create_directory(account_id, data)
           list_directories(account_id)
           get_directory(account_id, directory_id)
           delete_directory(account_id, directory_id)
           update_directoryy(account_id, directory_id, data)
           partial_update_directory(account_id, directory_id, data)
    """
    _directories_resource = RestResource(
        "directory",
        "/accounts/{account_id}/directories/{directory_id}",
        plural_name="directories")

    _fax_resource = RestResource(
        "fax",
        "/accounts/{account_id}/faxes/{fax_id}",
        methods=['create'],
        plural_name="faxes",
        extra_views=[{
            "name": "create_outgoing_fax",
            "method": "put",
            "path": "outgoing"
        },{
            "name": "list_outgoing_faxes",
            "path": "outgoing"
        },{
            "name": "get_outgoing_fax",
            "path": "outgoing/{fax_job_id}"
        },{
            "name": "list_outbox_faxes",
            "path": "outbox"
        },{
            "name": "get_outbox_fax",
            "path": "outbox/{fax_id}"
        },{
            "name": "resubmit_outbox_fax",
            "method": "put",
            "path": "outbox/{FAX_ID}"
        },{
            "name": "get_fax_payload",
            "path": "outbox/{FAX_ID}/attachment"
        },{
            "name": "get_smtp_logs",
            "path": "smtplog"
        },{
            "name": "get_smtp_log",
            "path": "smtplog/{ATTEMPT_ID}"

        },{
            "name": "delete_outbox_fax",
            "method": "delete",
            "path": "outbox/{fax_id}"
        },{
            "name": "delete_outbox_payload",
            "method": "delete",
            "path": "outbox/{fax_id}/attachment"
        },{
            "name": "list_inbox_faxes",
            "path": "inbox"
        },{
            "name": "get_inbox_fax",
            "path": "inbox/{FAX_ID}"
        },{
            "name": "get_inbox_fax_payload",
            "path": "inbox/{FAX_ID}/attachment"
        },{
            "name": "delete_inbox_fax",
            "path": "inbox/{FAX_ID}",
            "method": "delete"
        },{
            "name": "delete_inbox_fax_payload",
            "path": "inbox/{FAX_ID}/attachment",
            "method": "delete"
        },{
            "name": "list_incoming_faxes",
            "path": "incoming"
        },{
            "name": "get_incoming_fax",
            "path": "incoming/{fax_id}"
        },{
            "name": "resubmit_inbox_faxes",
            "method": "put",
            "path": "inbox/{FAX_ID}"
        }]
    )

    _faxboxes_resource = RestResource(
        "faxbox",
        "/accounts/{account_id}/faxboxes/{faxbox_id}",
        plural_name="faxboxes")

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/freeswitch
    Support only GET methods
       Call:
           list_freeswitch(account_id)
    """
    _freeswitch_resource = RestResource(
        "freeswitch",
        "/accounts/{account_id}/freeswitch/{ignored}",
        plural_name="freeswitch",
        methods=["list"])

    _global_resources = RestResource(
        "global_resource",
        "/accounts/{account_id}/global_resources/{resource_id}")

    _groups_resource = RestResource("group",
                                   "/accounts/{account_id}/groups/{group_id}")

    """ 
        http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/directories
        Support GET,PUT, DELETE, POST, PATH methods
           Call:
               create_ip(account_id, data) superadmin only
               list_ips(account_id)
               get_ip(account_id, ip)
               delete_ip(account_id, directory_id)
               update_ip(account_id, directory_id, data)
               get_hosts(account_id)
               get_zones(account_id)
               get_assigned(account_id)
               assigned(account,data)
        """
    _ip_resource = RestResource("ip",
                                 "/accounts/{account_id}/ips/{ip}",
                                exclude_methods=['partial_update'],
                                extra_views=[
                                {
                                    "name":"get_hosts",
                                    "path":"hosts"
                                },
                                {
                                    "name":"get_zones",
                                    "path":"zones"
                                },
                                {
                                    "name": "get_assigned",
                                    "path": "assigned"
                                },
                                {
                                    "name": "assigned",
                                    "method": "post",
                                    "path": ""
                                }
                                ])


    _hotdesks_resource = RestResource("hotdesk",
                                    "/accounts/{account_id}/hotdesks/{ignored}",
                                    methods=["list"])

    """ 
    http://{SERVER}:8000/v2/accounts/{ACCOUNT_ID}/cdrs
    Support GET, POST methods
       Call:
           list_limits(account_id)
    """
    _limits_resource = RestResource("limit",
                                    "/accounts/{account_id}/limits/{ignored}",
                                    methods=["list"],
                                    extra_views=[{
                                        "name" :"update_list",
                                        "method": "post",
                                        "path": ""
                                    }])

    _list_resource = RestResource("list",
                                    "/accounts/{account_id}/lists/{lists_id}",
                                    extra_views=[{
                                        "name": "list_entries",
                                        "path": "entries",
                                        "scope": "object"
                                    },{
                                        "name": "add_entry",
                                        "path": "entries",
                                        "method": "put",
                                        "scope": "object"
                                    },{
                                        "name": "delete_entries",
                                        "path": "entries",
                                        "method": "delete",
                                        "scope": "object"
                                    },{
                                        "name": "get_entry",
                                        "path": "entries/{entry_id}",
                                        "scope": "object"
                                    },{
                                        "name": "delete_entry",
                                        "path": "entries/{entry_id}",
                                        "method": "delete",
                                        "scope": "object"
                                    },{
                                        "name": "replace_entry",
                                        "path": "entries/{entry_id}",
                                        "method": "post",
                                        "scope": "object"
                                    },{
                                        "name": "update_entry",
                                        "path": "entries/{entry_id}",
                                        "method": "patch",
                                        "scope": "object"
                                    },{
                                        "name": "get_vcard",
                                        "path": "entries/{entry_id}/vcard",
                                        "scope": "object"
                                    },{
                                        "name": "add_entry_photo",
                                        "path": "entries/{entry_id}/photo",
                                        "method": "post",
                                        "scope": "object"
                                    }])

    _local_resources_resource = RestResource(
        "local_resource",
        "/accounts/{account_id}/local_resources/{resource_id}")


    _media_resource = RestResource("media",
                                   "/accounts/{account_id}/media/{media_id}",
                                   plural_name="media",
                                   exclude_methods=['partial_update'],
                                   method_names={
                                       "list": "get_all_media"
                                   },
                                   extra_views=[{
                                       "name" : "get_prompts",
                                       "path": "prompts"
                                   },{
                                       "name": "list_languages",
                                       "path": "languages"
                                   },{
                                       "name": "get_prompt",
                                       "path": "prompts/{prompt_id}"
                                   },{
                                       "name": "get_media_file",
                                       "path": "/raw",
                                       "scope": "object"
                                   }])

    _menus_resource = RestResource("menu",
                                   "/accounts/{account_id}/menus/{menu_id}")

    _metaflow_resource = RestResource("metaflow",
                                   "/accounts/{account_id}/metaflows/{ignored}",
                                    methods=['list'],
                                    extra_views=[{
                                        "name": "update_metaflows",
                                        "method": "post",
                                        "path": ""
                                    },{
                                        "name": "delete_metaflows",
                                        "method": "delete",
                                        "path": ""
                                    }])

    _migration_resource = RestResource("migration",
                                      "/accounts/{account_id}/migrations/{migration_id}",
                                       methods=['list','detail','update'])

    _notification_resource = RestResource("notification",
                                   "/accounts/{account_id}/notifications/{notification_id}",
                                          exclude_methods="partial_update",
                                          extra_views=[{
                                              "name": "preview",
                                              "path": "preview",
                                              "scope": "object"
                                          },{
                                              "name": "delete_all",
                                              "path": "",
                                              "method": "delete"
                                          },{
                                              "name": "customer_update",
                                              "path": "customer_update/message",
                                              "method": "post"
                                          },{
                                              "name": "list_smtp_logs",
                                              "path": "smtp_log"
                                          },{
                                              "name": "get_smtp_log",
                                              "path": "smtplog/{smtp_log_id}"
                                          }
                                          ]
                                          )

    _phone_number_resource = RestResource(
        "phone_number",
        "/accounts/{account_id}/phone_numbers/{phone_number}",
        methods=["list", "update", "delete"],
        extra_views=[{
            "name":"activate_phone_number",
            "path": "activate",
            "scope": "object",
            "method": "put"
        },{
            "name": "reserve_phone_number",
            "path": "reserve",
            "scope": "object",
            "method": "put"
        },{
            "name": "add_port_in_number",
            "path": "port",
            "scope": "object",
            "method": "put"
        },{
            "name": "get_carriers_info",
            "path": "carriers_info"
        },{
            "name": "list_classifiers",
            "path": "classifiers"
        },{
            "name": "fix_issue",
            "method": "post",
            "path": "fix"
        },{
            "name": "get_locality_info",
            "method": "post",
            "path": "locality"
        },{
            "name": "check_phone_numbers_availability",
            "method": "post",
            "path": "check"
        },{
            "name": "update_numbers_collection",
            "method": "post",
            "path": "collection"
        },{
            "name": "partial_update_numbers_collection",
            "method": "patch",
            "path": "collection"
        },{
            "name": "add_numbers_collection",
            "method": "put",
            "path": "collection"
        },{
            "name": "list_numbers_collection",
            "path": "collection"
        }])

    _queues_resource = RestResource("queue",
                                    "/accounts/{account_id}/queues/{queue_id}",
                                    extra_views=[{
                                        "name": "get_stats",
                                        "path": "stats"
                                    },{
                                        "name": "get_queue_stats",
                                        "scope": "object",
                                        "path": "stats"
                                    },{
                                        "name": "get_queue_stats_realtime",
                                        "scope": "object",
                                        "path": "stats/realtime"
                                    },{
                                        "name": "get_roster",
                                        "scope": "object",
                                        "path": "roster"
                                    },{
                                        "name": "add_roster",
                                        "scope": "object",
                                        "path": "roster",
                                        "method": "post"
                                    },{
                                        "name": "delete_roster",
                                        "scope": "object",
                                        "path": "roster",
                                        "method": "delete"
                                    },{
                                        "name": "create_eavesdrop",
                                        "path": "eavesdrop",
                                        "method": "put"
                                    },{
                                        "name": "create_queue_eavesdrop",
                                        "path": "eavesdrop",
                                        "scope": "object",
                                        "method": "put"
                                    }]
                                    )

    _parked_call_resource = RestResource(
        "parked_call",
        "/accounts/{account_id}/parked_calls/{ignored}",
        methods=['list'])

    _pivot_resource = RestResource(
        "resource",
        "/accounts/{account_id}/pivot/debug/{call_id}",
        plural_name='pivot',
        methods=['list','detail'],
        method_names={
            "list": "get_pivots_debug",
            "detail": "get_pivot_call_debug"
        })

    _presence_resource = RestResource(
        "presence",
        "/accounts/{account_id}/presence/{ext_id}",
        plural_name='presence',
        methods=['list','update'],
        extra_views=[{
            "name": "get_presence_report",
            "path": "report"
        }])

    _rates_resource = RestResource("rates",
                                    "/accounts/{account_id}/rates/{rate_id}",
                                   extra_views=[{
                                       "name": "upload_rate",
                                       "path": "",
                                       "method": "post"
                                   },{
                                       "name": "number_rate",
                                       "path": "rates/number/{phone_number}"
                                   }]
                                   )

    _rate_limits_resource = RestResource("rate_limits",
                                   "/accounts/{account_id}/rate_limits/{ignored}",
                                   methods=['lists'],
                                   extra_views=[{
                                       "name": "update_rate_limits",
                                       "method": "post",
                                       "path": ""
                                   },{
                                       "name": "delete_rate_limits",
                                       "method": "delete",
                                       "path": ""
                                   }]
                                   )

    _recording_resource = RestResource("recording",
                                           "/accounts/{account_id}/recordings/{record_id}",
                                           methods=["list", "detail"])

    _registrations_resource = RestResource("registration",
                                   "/accounts/{account_id}/registrations/{ignored}",
                                   methods=["list"],
                                   extra_views=[{
                                       "name": "delete_registrations",
                                       "method": "delete",
                                       "path": ""
                                   }]
                                   )

    _resource_resource = RestResource(
        "resource",
        "/accounts/{account_id}/resources/{resource_id}",
        extra_views=[{
            "name": "list_jobs",
            "path": "jobs"
        },{
            "name": "create_job",
            "method": "put",
            "path": "jobs"
        },{
            "name": "get_job",
            "path": "jobs/{job_id}"
        },{
            "name": "create_collection",
            "path": "collection",
            "method": "put"
        },{
            "name": "update_collection",
            "path": "collection",
            "method": "post"
        }])


    _security_resource = RestResource(
        "security",
        "/accounts/{account_id}/security/{ignored}",
        plural_name="security",
        methods=["list"],
        extra_views=[
            {"name": "update_security",
             "path": "",
             "method": "post"},
            {"name": "delete_security",
             "path": "",
             "method": "delete"},
            {"name": "partial_update_security",
             "path": "",
             "method": "patch"},
            {"name": "list_attempts",
             "path": "attempts"},
            {"name": "get_attempt_id",
             "path": "attempts/{attempt_id}"},
            {"name": "list_auth_module",
             "scope": "system",
             "path": "security"}
        ])



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

    _services_resource = RestResource(
        "service",
        "/accounts/{account_id}/services/{service_id}",
        methods=["list"],
        extra_views=[{
            "name":"update_service",
            "path": "",
            "method": "post"
        },{
            "name": "get_audit_logs",
            "path": "audit"
        },{
            "name": "get_plan",
            "path": "plan"
        },{
            "name": "get_status",
            "path": "status"
        },{
            "name": "update_status",
            "path": "status",
            "method": "post"
        }])

    _service_plan_resource = RestResource(
        "service_plans",
        "/accounts/{account_id}/service_plans/{plan_id}",
        exclude_methods=['partial_update','create'],
        extra_views=[{
            "name": "create_plan",
            "method": "post",
            "path": ""
        },{
            "name": "override_plan",
            "method": "post",
            "path": ""
        },{
            "name": "get_current_plan",
            "path": "current"
        },{
            "name": "list_available_plans",
            "path": "available"
        },{
            "name": "get_available_plan",
            "path": "available/{plan_id}"
        },{
            "name": "sync_plan",
            "method": "post",
            "path": "synchronization"
        },{
            "name": "reconsilate_plan",
            "method": "post",
            "path": "reconciliation"
        }])

    _schema_resource = RestResource(
        "schema",
        "/accounts/{account_id}/schemas/{schema_id}",
         methods=['list','detail'],
         extra_views=[{
             "name": "validate_schema",
             "scope": "object",
             "method": "put",
             "path": "validate"
         }])

    _sms_resource = RestResource(
        "sms",
        "/accounts/{account_id}/sms/{sms_id}",
         exclude_methods=['update'],
         plural_name="sms")

    _skel_resource = RestResource(
        "skel",
        "/accounts/{account_id}/skels/{skel_id}")

    _storage_resource = RestResource(
        "storage",
        "/accounts/{account_id}/storage/{ignored}",
        methods=['list', 'create'],
        extra_views=[{
            "name": "create_storage_plan",
            "method": "put",
            "path": "plans"
        },{
            "name": "list_storage_plans",
            "path": "plans"
        },{
            "name": "get_storage_plan",
            "path": "plans/{plan_id}"
        },{
            "name": "update_storage_plan",
            "path": "plans/{plan_id}",
            "method": "post"
        },{
            "name": "partial_update_storage_plan",
            "path": "plans/{plan_id}",
            "method": "patch"
        },{
            "name": "delete_storage_plan",
            "path": "plans/{plan_id}",
            "method": "delete"
        },{
            "name": "delete_storage",
            "path": "",
            "method": "delete"
        },{
            "name": "update_storage",
            "path": "",
            "method": "post"
        },{
            "name": "partial_update_storage",
            "path": "",
            "method": "patch"
        }]
    )

    _temporal_rules_resource = RestResource(
        "temporal_rule",
        "/accounts/{account_id}/temporal_rules/{rule_id}")

    _temporal_rules_sets_resource = RestResource(
        "temporal_rules_set",
        "/accounts/{account_id}/temporal_rules_sets/{temporal_rule_set}")

    _transactions_resource = RestResource(
        "transaction",
        "/accounts/{account_id}/transactions/{ignored}",
        methods=['list'],
        extra_views=[{
            "name": "get_current_balance",
            "path": "current_balance"
        },{
            "name": "get_subscriptions",
            "path": "subscriptions"
        },{
            "name": "get_monthly",
            "path": "monthly_recurring"
        },{
            "name": "add_credit",
            "path": "credit",
            "method": "put"
        },{
            "name": "remove_credit",
            "path": "debit",
            "method": "delete"
        }]
    )

    _users_resource = RestResource(
        "user",
        "/accounts/{account_id}/users/{user_id}",
        extra_views=[
            {
                "name": "get_hotdesk",
                "path": "hotdesks"
            },{
                "name": "get_user_cdrs",
                "path": "cdrs"
            },{
                "name": "get_photo",
                "path": "photo",
                "scope": "object"
            },{
                "name": "update_photo",
                "path": "photo",
                "scope": "object",
                "method": "post"
            },{
                "name": "delete_photo",
                "path": "photo",
                "scope": "object",
                "method": "delete"
            },{
                "name": "get_vcard",
                "path": "vcard",
                "scope": "object"
            },{
                "name": "user_quickcall",
                "path": "quickcall/{PHONE_NUMBER}",
                "scope": "object"
            },{
                "name": "update_user_presence",
                "path": "presence",
                "method": "post",
                "scope": "object"
            },{
                "name": "list_user_channels",
                "path": "channels",
                "scope": "object"
            },{
                "name": "list_user_devices",
                "path": "devices",
                "scope": "object"
            },{
                "name": "list_user_recordings",
                "path": "recordings",
                "scope": "object"
            },{
                "name": "list_user_groups",
                "path": "groups",
                "scope": "object"
            }])

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
        "/accounts/{account_id}/webhooks/{webhook_id}",
        extra_views=[{
            "name": "get_attempts",
            "path": "attempts"
        }, {
            "name": "get_attempt",
            "scope": "object",
            "path": "attempts"
        },{
            "name": "enable_webhooks",
            "path": "",
            "method": "patch"
        },{
            "name": "enbale_webhooks",
            "path": "webhooks",
            "scope": "system"
        }]

    )

    _websockets_resource = RestResource(
        "websocket",
        "/accounts/{account_id}/websockets/{websocket_id}",
        methods=['list','detail'],
        extra_views=[{
            "name": "get_system_websockets",
            "path": "websockets",
            "scope": "system"
        }]
    )

    _whitelabel_resource = RestResource(
        "whitelabel",
        "/accounts/{account_id}/whitelabel/{whitelabel_id}",
        plural_name="whitelabel"
        )

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
            self.account_id = self.auth_data['data']["account_id"]
            self._authenticated = True
        return self.auth_token

    def _execute_request(self, request, **kwargs):
        from .exceptions import KazooApiAuthenticationError

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
        except ValueError:
            return ''

    def get_about(self):
        request = KazooRequest("/about", method="get")
        return self._execute_request(request)

    def create_ip_auth(self):
        request = KazooRequest("/ip_auth", method="put")
        return self._execute_request(request)

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

    def delete_numbers_collection(self, acct_id=None, del_data=None):
        if not acct_id:
            acct_id = self.account_id
        path= "/accounts/{account_id}/phone_numbers/collection"
        request = KazooRequest(path, method="delete")
        return self._execute_request(request, account_id=account_id, data=del_data )

    def list_numbers_by_prefix(self, acct_id=None, prefix_data=None):
        if not acct_id:
            acct_id = self.account_id

        path = self.dict_to_string(prefix_data)
        path = "/accounts/{account_id}/phone_numbers/prefix?" + path
        request = KazooRequest(path)
        return self._execute_request(request, account_id=acct_id)

    def run_sup_command(self, *args):
        path='/sup/'
        for i in args:
            path += i+'/'
        request = KazooRequest(path[:-1])
        return self._execute_request(request)

    def search(self, data, multi=None, acct_id=None):
        path = 'search'
        if acct_id:
            path = '/accounts/{account_id}/' + path
        if multi:
            path += '/multi'

        for i in data:
            path += i+'&'

        request = KazooRequest(path[:-1])
        return self._execute_request(request, account_id=acct_id)

    def dict_to_string(self, in_dict):
        res = ''
        for key, value in in_dict.items():
            res = res + key + '=' + value +'&'
        return res[:-1]
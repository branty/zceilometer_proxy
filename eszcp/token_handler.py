#    Copyright  2017 EasyStack, Inc
#    Authors: Claudio Marques,
#             David Palma,
#             Luis Cordeiro,
#             Branty <jun.wang@easystack.cn>
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Class for requesting authentication tokens to Keystone

This class provides means to requests for authentication

tokens to be used with OpenStack's Ceilometer, Nova and RabbitMQ
"""

import json
import urllib2
from urllib2 import HTTPError
from urllib2 import URLError

from eszcp.common import log


LOG = log.logger(__name__)


class Auth:
    def __init__(self, auth_host, public_port, admin_tenant,
                 admin_user, admin_password):

        self.auth_host = auth_host
        self.public_port = public_port
        self.admin_tenant = admin_tenant
        self.admin_user = admin_user
        self.admin_password = admin_password

    def getToken(self):
        """
        Requests and returns an authentication token to be used with

        OpenStack's Ceilometer, Nova and RabbitMQ
        :return: The Keystone token assigned to these credentials
        """
        auth_request = urllib2.Request("http://" + self.auth_host + ":" +
                                       self.public_port + "/v2.0/tokens")
        auth_request.add_header('Content-Type',
                                'application/json;charset=utf8')
        auth_request.add_header('Accept', 'application/json')
        auth_data = {"auth": {"tenantName": self.admin_tenant,
                              "passwordCredentials":
                              {"username": self.admin_user,
                               "password": self.admin_password}}}
        auth_request.add_data(json.dumps(auth_data))
        try:
            auth_response = urllib2.urlopen(auth_request)
            response_data = json.loads(auth_response.read())
            token = response_data['access']['token']['id']
        except HTTPError, ex:
            if ex.code == 401:
                LOG.error("Unauthorized,Please the username and password")
                raise
            LOG.error(ex.msg)
            raise
        except URLError, ex:
            msg = str(getattr(ex, 'reason'))if hasattr(ex, 'reason') \
                  else getattr(ex, 'msg', None) or getattr(ex, 'message')
            LOG.error(msg)
            raise
        except Exception, ex:
            LOG.error(msg)
            raise
        return token

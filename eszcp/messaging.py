#    Copyright  2017 EasyStack, Inc
#    Authors: Hanxi Liu<apolloliuhx@gmail.com>
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

import pika

from eszcp.common import conf
from eszcp.common import log


LOG = log.logger(__name__)
cfg = conf.Conf()

hosts = cfg.read_option('os_rabbitmq', 'rabbit_hosts')
user = cfg.read_option('os_rabbitmq', 'rabbit_user')
passwd = cfg.read_option('os_rabbitmq', 'rabbit_pass')
port = cfg.read_option('os_rabbitmq', 'rabbit_port')
vh = cfg.read_option('os_rabbitmq', 'rabbit_virtual_host')


def connection():
    connect = None
    connection_state = False
    for host in hosts.split(','):
        try:
            LOG.info("Conneting to Rabbitmq server %s..." % host)
            connect = pika.BlockingConnection(pika.ConnectionParameters(
                host=host,
                port=int(port),
                virtual_host=vh,
                credentials=pika.PlainCredentials(user,
                                                  passwd)))
        except Exception as e:
            LOG.warning("Fail to connect to Rabbitmq server %s : %s" % (host, e))
        else:
            connection_state = True
            break
    if connection_state:
        return connect
    else:
        LOG.error("Fail to connect to Rabbitmq nodes: %s. Please configure rabbitmq "
                  "with correct parameters!" % hosts.split(','))
        raise


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
Class for Handling KeystoneEvents in OpenStack's RabbitMQ

Uses the pika library for handling the AMQP protocol,

implementing the necessary callbacks for Keystone events
"""

from eszcp.common import log
import json
import pika

LOG = log.logger(__name__)


class ProjectEvents:

    def __init__(self, rabbit_host, rabbit_user, rabbit_pass, rabbit_port,
                 zabbix_handler):
        """
        :param rabbit_host: rabbit host
        :param rabbit_user: rabbit user
        :param rabbit_pass: rabbit user password
        :param zabbix_handler: zabbix api handler
        """
        self.rabbit_host = rabbit_host
        self.rabbit_user = rabbit_user
        self.rabbit_pass = rabbit_pass
        self.rabbit_port = rabbit_port
        self.zabbix_handler = zabbix_handler

    def keystone_amq(self):
        """
        Method used to listen to keystone events
        """

        connection = pika.BlockingConnection(pika.ConnectionParameters(
                                    host=self.rabbit_host,
                                    port=int(self.rabbit_port),
                                    credentials=pika.PlainCredentials(
                                        self.rabbit_user,
                                        self.rabbit_pass))
                     )
        channel = connection.channel()
        channel.exchange_declare(exchange='keystone', type='topic')
        channel.queue_declare(queue="zcp-keystone", exclusive=True)
        channel.queue_bind(exchange='keystone',
                           queue="zcp-keystone",
                           routing_key='notifications.#')
        channel.basic_consume(self.keystone_callback,
                              queue="zcp-keystone",
                              no_ack=True)
        channel.start_consuming()

    def keystone_callback(self, ch, method, properties, body):
        """
        Method used by method keystone_amq() to filter messages
        by type of message.

        :param ch: refers to the head of the protocol
        :param method: refers to the method used in callback
        :param properties: refers to the proprieties of the message
        :param body: refers to the message transmitted
        """
        payload = json.loads(body)
        try:
            if payload['event_type'] == 'identity.project.created':
                tenant_id = payload['payload']['resource_info']
                tenants = self.zabbix_handler.get_tenants()
                tenant_name = self.zabbix_handler.get_tenant_name(tenants,
                                                                  tenant_id)
                LOG.info("Creating a hostgroup: %s(%s) in Zabbix Server"
                         % (tenant_id, tenant_name))
                self.zabbix_handler.group_list.append([tenant_name, tenant_id])
                self.zabbix_handler.create_host_group(tenant_name)
            elif payload['event_type'] == 'identity.project.deleted':
                tenant_id = payload['payload']['resource_info']
                LOG.info("Deleting a hostgroup: %s in Zabbix Server"
                         % tenant_id)
                self.zabbix_handler.project_delete(tenant_id)
            else:
                # TO DO
                # Maybe more event types will be supported
                pass
        except Exception, ex:
            LOG.error(ex.message)
            raise ex

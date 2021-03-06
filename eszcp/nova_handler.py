"""
Class for Handling Nova events in OpenStack's RabbitMQ

Uses the pika library for handling the AMQP protocol, implementing the

necessary callbacks for Nova events
"""

from eszcp import log
import json
import pika

LOG = log.logger(__name__)

__authors__ = "Claudio Marques, David Palma, Luis Cordeiro, Branty"
__copyright__ = "Copyright (c) 2014 OneSource Consultoria Informatica, Lda"
__license__ = "Apache 2"
__contact__ = ["www.onesource.pt", "www.openstack.cn"]
__date__ = "03/01/2016"
__email__ = "jun.wang@easystack.cn"
__version__ = "1.0.0"


class NovaEvents:

    def __init__(self, rabbit_host, rabbit_user, rabbit_pass, rabbit_port,
                 zabbix_handler,
                 ceilometer_handler):

        """
        :param rabbit_host: rabbit host
        :param rabbit_user: rabbit user
        :param rabbit_pass: rabbit user password
        :param zabbix_handler: zabbix api handler
        :param ceilometer_handler: ceilometer api handler
        """
        self.rabbit_host = rabbit_host
        self.rabbit_user = rabbit_user
        self.rabbit_pass = rabbit_pass
        self.rabbit_port = rabbit_port
        self.zabbix_handler = zabbix_handler
        self.ceilometer_handler = ceilometer_handler

    def nova_amq(self):
        """
        Method used to listen to nova events

        """

        connection = pika.BlockingConnection(pika.ConnectionParameters(
                                    host=self.rabbit_host,
                                    port=int(self.rabbit_port),
                                    credentials=pika.PlainCredentials(
                                            self.rabbit_user,
                                            self.rabbit_pass)
                                    ))
        channel = connection.channel()
        channel.exchange_declare(exchange='nova', type='topic')
        channel.queue_declare(queue="zcp-nova", exclusive=True)
        channel.queue_bind(exchange='nova', queue="zcp-nova",
                           routing_key='notifications.#')
        channel.queue_bind(exchange='nova', queue="zcp-nova",
                           routing_key='compute.#')
        channel.basic_consume(self.nova_callback,
                              queue="zcp-nova",
                              no_ack=True)
        channel.start_consuming()

    def nova_callback(self, ch, method, properties, body):
        """
        Method used by method nova_amq() to filter messages by type of message.

        :param ch: refers to the head of the protocol
        :param method: refers to the method used in callback
        :param properties: refers to the proprieties of the message
        :param body: refers to the message transmitted
        """
        payload = json.loads(body)

        try:
            tenant_name = payload.get('_context_project_name')
            if not tenant_name:
                LOG.debug("Drop a notification message")
                return
            type_of_message = payload['event_type']

            if type_of_message == 'compute.instance.create.end':
                instance_id = payload['payload']['instance_id']
                instance_name = payload['payload']['hostname']
                self.zabbix_handler.create_host(instance_name,
                                                instance_id,
                                                tenant_name)
                LOG.info("Creating a host: %s(%s) in Zabbix Server"
                         % (instance_id, instance_name))
                self.ceilometer_handler.host_list = \
                    self.ceilometer_handler.get_hosts_ID()
            elif type_of_message == 'compute.instance.delete.end':
                host = payload['payload']['instance_id']
                host_id = self.zabbix_handler.find_host_id(host)
                self.zabbix_handler.delete_host(host_id)
                LOG.info("Deleting a host: %s in Zabbix Server"
                         % host_id)
                self.ceilometer_handler.host_list = \
                    self.ceilometer_handler.get_hosts_ID()
            else:
                # TO DO
                # Maybe more event types will be supported
                pass
        except Exception, ex:
            LOG.error(ex.message)
            raise ex

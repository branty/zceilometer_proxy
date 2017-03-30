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
Class for polling Ceilometer

This class provides means to requests for authentication
tokens to be used with OpenStack's Ceilometer, Nova and RabbitMQ
"""

import json
import socket
import struct
import time
import urllib2

from eszcp.common import log
from eszcp import utils
from eszcp.ceilometer_client import Client as CeiloV20

LOG = log.logger(__name__)

INSTANCE_METRICS = [
    'cpu_util',
    'cpu.delta',
    'memory.usage',
    'disk.read.bytes.rate',
    'disk.read.requests.rate',
    'disk.write.bytes.rate',
    'disk.write.requests.rate'
    ]

NETWORK_METRICS = [
    'network.incoming.bytes.rate',
    'network.incoming.packets.rate',
    'network.outgoing.bytes.rate',
    'network.outgoing.packets.rate'
    ]

"""
 Cache instance metrics, the date structure is the following:
 {"instance_id":{
     "instance_id": INSTANCE_METRICS,
     "instance-xxx-{instance_id}-{tap_id}": NETWORK_METRICS,
     "instance-{disk_id}": DISK_METRICS,
     ...
    },
  ...
 }
"""
METRIC_CACEHES = {}


class CeilometerHandler:

    def __init__(self, polling_interval, zabbix_host, zabbix_port,
                 ks_client, nv_client, zabbix_hdl):
        """Ceilometer polling handler

        :param ceilometer_api_port: ceilometer api port
        :param ceilometer_api_host: ceilometer host
        :param polling_interval:period(seconds) of polling ceilometer metric
        :param template_name:zabbix templete which binds nova instance
        :param zabbix_host: zabbix host
        :param zabbix_port: zabbix port
        :parms ks_client: Openstack identity service, keystone client
        :parms nv_client: Openstack compute service,nova client
        :parms zabbix_hdl:zabbix handler
        """
        self.polling_interval = int(polling_interval)
        self.zabbix_host = zabbix_host
        self.zabbix_port = zabbix_port
        self.ks_client = ks_client
        self.nv_client = nv_client
        self.zabbix_hdl = zabbix_hdl
        self.clt_client = CeiloV20()

    def interval_run(self, func=None):
        """
        :param func: loop execute function
        """
        LOG.info("********** Polling Ceilometer Metric Into Zabbix **********")
        while True:
            self.run()
            time.sleep(self.polling_interval)

    def run(self):
        hosts, hosts_map = self.zabbix_hdl.get_hosts(filter_no_proxy=True)
        # self.zabbix_hdl.check_host_groups()
        # self.zabbix_hdl.check_proxies()
        self.update_zabbix_values(hosts, hosts_map)

    def connect_zabbix(self, payload):
        """
        Method used to send information to Zabbix
        :param payload: refers to the json message prepared to send to Zabbix
        :rtype : returns the response received by the Zabbix API
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.zabbix_host, int(self.zabbix_port)))
        s.send(payload)
        # read its response, the first five bytes are the header again
        response_header = s.recv(5, socket.MSG_WAITALL)
        if not response_header == 'ZBXD\1':
            raise ValueError('Got invalid response')

        # read the data header to get the length of the response
        response_data_header = s.recv(8, socket.MSG_WAITALL)
        response_data_header = response_data_header[:4]
        response_len = struct.unpack('i', response_data_header)[0]

        # read the whole rest of the response now that we know the length
        response_raw = s.recv(response_len, socket.MSG_WAITALL)
        s.close()
        LOG.info(response_raw)
        response = json.loads(response_raw)

        return response

    def update_zabbix_values(self, hosts, hosts_map):
        """
        For ES metric collecor,
        We don't storage sample in a same collection meter(
        OpenStack community do it like this).

        Accroding to the sample period,slice the meter collection
        and collector metric
        :param hosts: a list ,record zabbix host information.
        :param hosts_cache:a dict ,record zabbix host information.
         hosts_cache, the date structure is the following:
         {"instance_id":["host_id","host_name","proxy_id"]
         }
        hosts: ['instance_id1','instance)id2',...]
        """
        def _all_instance_details():
            response = self.nv_client.instance_get_all()
            servers = [server.to_dict() for server in response]
            if not servers:
                LOG.warning("Servers list is empry,"
                            "skip to update zabbix values")
            return servers

        All_INSTANCES = _all_instance_details() or []
        for instance in All_INSTANCES:
            if instance['id'] in hosts and utils.is_active(instance):
                LOG.debug("Start Checking host : %s"
                          % hosts_map[instance['id']][1])
                # Get links for instance compute metrics
                query = [{'op': 'eq',
                          'value': instance['id'],
                          'field': 'metadata.instance_id'}]
                resources = self.clt_client.list_resources(q=query)
                # Add a new instance and its metrics
                if instance['id'] not in METRIC_CACEHES.keys():
                    rs_items = {}
                    for rs in resources:
                        if rs.resource_id.startswith('instance'):
                            rs_items[rs.resource_id] = NETWORK_METRICS
                        # NOTE:remove disk metrics
                        elif utils.endswith_words(rs.resource_id):
                            pass
                        else:
                            rs_items[rs.resource_id] = INSTANCE_METRICS
                    METRIC_CACEHES[instance['id']] = rs_items
                # Update metric_caches where instance_in exists.For the case:
                # instance add/remove a nic
                # instance add/remove a volume
                else:
                    rs_items = METRIC_CACEHES[instance['id']]
                    rs_item_keys = rs_items.keys()
                    for rs in resources:
                        if rs.resource_id not in rs_item_keys and \
                           rs.resource_id.startswith('instance'):
                            rs_items[rs.resource_id] = NETWORK_METRICS
                            METRIC_CACEHES[instance['id']] = rs_items
                        # NOTE:remove disk metrics
                        elif rs.resource_id not in rs_item_keys and \
                                utils.endswith_words(rs.resource_id):
                            pass
                        else:
                            continue
                LOG.debug("Starting to polling %s(%s) metric into zabbix"
                          % (instance.get('name'), instance.get('id')))
                pxy = self.zabbix_hdl.get_by_proxyid(
                                hosts_map[instance['id']][2])
                if pxy:
                    proxy_name = pxy['host']
                else:
                    LOG.warning("Can't find the prxoy:%s,Skip to polling "
                                "instance_id  %s metrics."
                                % (hosts_map[instance['id']][2],
                                   instance['id']))
                    continue
                # Polling Ceilometer the latest sample into zabbix
                # CLI:ceilometer statistics -m {...} -q resource_id={...} -p ..
                self.polling_metrics(instance['id'],
                                     proxy_name)
                LOG.debug("Finshed to polling %s(%s) metric into zabbix"
                          % (instance.get('name'), instance.get('id')))
            else:
                LOG.debug("Can't find the instance : %s(%s), "
                          "or the status of %s is not active"
                          % (instance.get('name'),
                             instance.get('id'),
                             instance.get('name'))
                          )

    def polling_metrics(self, instance_id, proxy_name):
        """
        :param instance_id: nova instance uuid
        :param proxy_name: zabbix proxy_name
        """
        def _polling(ids, METRICS):
            for metric in METRICS:
                counter_volume = 0.0
                for rsc_id in ids:
                    query = [{'op': 'eq',
                              'value': rsc_id,
                              'field': 'resource_id'}]
                    response = self.clt_client.statistics(
                                metric,
                                q=query,
                                limit=1)
                    if len(response) > 0:
                        counter_volume += response[0].avg
                    else:
                        LOG.info("The metric %s of resource_id %s statistics "
                                 "not found." % (metric, rsc_id))
                    LOG.info("Polling Ceilometer metri into zabbix proxy: %s,"
                             "resource_id: %s, metric: %s, counter_name: %s"
                             % (rsc_id, metric, counter_volume, proxy_name))
                    self.send_data_zabbix(counter_volume, instance_id,
                                          metric, proxy_name)
        # Get instance all taps
        network_nics_id = []
        # Get install all volumes
        for rsc_id in METRIC_CACEHES[instance_id].keys():
            if rsc_id.startswith('instance'):
                network_nics_id.append(rsc_id)

        # network metrics
        _polling(network_nics_id, NETWORK_METRICS)

        # instance metrics
        _polling([instance_id], INSTANCE_METRICS)

    def set_proxy_header(self, data):
        """Method used to simplify constructing the protocol to
        communicate with Zabbix

        :param data: refers to the json message
        :rtype : returns the message ready to send to Zabbix server
        with the right header
        """
        # data_length = len(data)
        # data_header = struct.pack('i', data_length) + '\0\0\0\0'
        # HEADER = '''ZBXD\1%s%s'''
        # data_to_send = HEADER % (data_header, data)
        payload = json.dumps(data)
        return payload

    def send_data_zabbix(self, counter_volume, resource_id,
                         item_key, proxy_name):
        """Method used to prepare the body with data from Ceilometer and send
        it to Zabbix using connect_zabbix method

        :param counter_volume: the actual measurement
        :param resource_id:  refers to the resource ID
        :param item_key:    refers to the item key
        """
        tmp = json.dumps(counter_volume)
        data = {"request": "history data", "host": proxy_name,
                "data": [{"host": resource_id,
                          "key": item_key,
                          "value": tmp}]}

        payload = self.set_proxy_header(data)
        self.connect_zabbix(payload)

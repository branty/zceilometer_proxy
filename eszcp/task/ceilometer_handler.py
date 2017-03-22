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

from eszcp.common import log
from eszcp import utils
import json
import socket
import struct
import time
import urllib2

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
# Disk device metric needed in the future
# DISK_METRICS = [
#    'disk.device.read.bytes.rate',
#    'disk.device.read.requests.rate',
#    'disk.device.write.bytes.rate',
#    'disk.device.write.requests.rate'
#    ]

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

    def __init__(self, ceilometer_api_port, polling_interval,
                 template_name, ceilometer_api_host, zabbix_host,
                 zabbix_port, zabbix_proxy_name, nova_host,
                 nova_port, admin_tenant_id, keystone_auth):
        """
        TODO
        :param ceilometer_api_port: ceilometer api port
        :param ceilometer_api_host: ceilometer host
        :param polling_interval:period(seconds) of polling ceilometer metric
        :param template_name:zabbix templete which binds nova instance
        :param zabbix_host: zabbix host
        :param zabbix_port: zabbix port
        :param zabbix_proxy_name: zabbix proxy name
        :param nova_host: Openstack compute service, nova-api host
        :param nova_port: Openstack compute service, nova-api port
        :param admin_tenant_id: The admin_tenant of of keystone Default domain
        :param keystone_auth: keystone token_id
        :no
        """
        self.ceilometer_api_port = ceilometer_api_port
        self.polling_interval = int(polling_interval)
        self.template_name = template_name
        self.ceilometer_api_host = ceilometer_api_host
        self.zabbix_host = zabbix_host
        self.zabbix_port = zabbix_port
        self.nova_host = nova_host
        self.nova_port = nova_port
        self.zabbix_proxy_name = zabbix_proxy_name
        self.admin_tenant_id = admin_tenant_id
        self.keystone_auth = keystone_auth

    def interval_run(self, func=None):
        """
        :param func: loop execute function
        """
        LOG.info("********** Polling Ceilometer Metric Into Zabbix **********")
        while True:
            self.run()
            time.sleep(self.polling_interval)

    def run(self):
        self.token = self.keystone_auth.getToken()
        # Timer(self.polling_interval, self.run, ()).start()
        host_list = self.get_hosts_ID()
        self.update_zabbix_values(host_list)

    def get_hosts_ID(self):
        """
        Method used do query Zabbix API in order to fill an Array of hosts
        :return: returns a array of servers and items to monitor by server
        """
        data = {"request": "proxy config", "host": self.zabbix_proxy_name}
        payload = self.set_proxy_header(data)
        response = self.connect_zabbix(payload)
        hosts_id = []
        items = []
        for line in response['hosts']['data']:
            for line2 in response['items']['data']:
                if line2[4] == line[0]:
                    items.append(line2[5])
            hosts_id.append([line[0], line[1], items, line[7]])
            items = []
        return hosts_id

    def update_values(self, hosts_id):
        """
        :param hosts_id: nova instance uuid
        For Upstream OpenStack community, use this function

        For EasyStack Ceilometer, this function is deprecated
        Use the function of update_zabbix_values
        """
        for host in hosts_id:
            links = []
            if not host[1] == self.template_name:

                LOG.debug("Checking host:" + host[3])
                # Get links for instance compute metrics
                request = urllib2.urlopen(urllib2.Request(
                    "http://" + self.ceilometer_api_host + ":" +
                    self.ceilometer_api_port +
                    "/v2/resources?q.field=resource_id&q.value=" + host[1],
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "X-Auth-Token": self.token})).read()
                # Filter the links to an array
                for line in json.loads(request):
                    for line2 in line['links']:
                        if line2['rel'] in ('cpu_util',
                                            'memory.usage',
                                            'disk.read.bytes',
                                            'disk.read.requests',
                                            'disk.write.bytes',
                                            'disk.write.requests',
                                            'disk.device.read.bytes',
                                            'disk.device.read.requests',
                                            'disk.device.write.bytes',
                                            'disk.device.write.requests',
                                            'volume.read.bytes',
                                            'volume.write.bytes'
                                            ):
                            links.append(line2)

                # Get the links regarding network metrics
                request = urllib2.urlopen(urllib2.Request(
                    "http://" + self.ceilometer_api_host +
                    ":" + self.ceilometer_api_port +
                    "/v2/resources?q.field=metadata.instance_id&q.value=" +
                    host[1],
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "X-Auth-Token": self.token})).read()

                # Add more links to the array
                for line in json.loads(request):
                    for line2 in line['links']:
                        if line2['rel'] in ('network.incoming.bytes',
                                            'network.incoming.packets',
                                            'network.outgoing.bytes',
                                            'network.outgoing.packets'):
                            links.append(line2)

                # Query ceilometer API using the array of links
                for line in links:
                    self.query_ceilometer(host[1], line['rel'], line['href'])
                    LOG.info("  - Item " + line['rel'])

    def query_ceilometer(self, resource_id, item_key, link):
        """
        :param resource_id: host_id
        :param item_key: zabbix metric
        :param link:
        """
        try:
            # global contents
            contents = urllib2.urlopen(urllib2.Request(
                    link + str("&limit=1"),
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "X-Auth-Token": self.token})).read()
            response = json.loads(contents)

            counter_volume = response[0]['counter_volume']
            LOG.debug("Start sending resource_id: %s, metric: %s"
                      % (resource_id, item_key))
            self.send_data_zabbix(counter_volume, resource_id, item_key)
        except urllib2.HTTPError, e:
            if e.code == 401:
                msg = "Error... \nToken refused! " \
                      "The request you have made requires authentication."
                LOG.error(msg)
                raise
            elif e.code == 404:
                msg = "Can't found for resource_id: %s, metric: %s " \
                      % (resource_id, item_key)
                LOG.error()
                raise
            elif e.code == 503:
                msg = "HTTP Error 503,The service of ceilometer is unavailable"
                LOG.error(msg)
                raise
            else:
                LOG.error("Unknown Error")
                raise
        except Exception, ex:
            LOG.error(ex.message)
            raise

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

    def update_zabbix_values(self, hosts_id):
        """
        For ES metric collecor,
        We don't storage sample in a same collection meter(
        OpenStack community do it like this).

        Accroding to the sample period,slice the meter collection
        and collector metric
        :param hosts_id: hosts in zabbix ,host_id is nova instance uuid
        """
        def _all_instance_details():
            try:
                request = urllib2.urlopen(urllib2.Request(
                    "http://" + self.nova_host + ":" + self.nova_port +
                    "/v2/" + self.admin_tenant_id +
                    "/servers/detail?all_tenants=1",
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "X-Auth-Token": self.token}
                )).read()
                return json.loads(request).get("servers")
            except urllib2.HTTPError, e:
                if e.code == 401:
                    msg = "Error... \nToken refused! " \
                          "The request you have made requires authentication."
                    LOG.error(msg)
                    raise
                elif e.code == 404:
                    msg = "Can't found for instances for tenant: %s " \
                           % self.admin_tenant_id
                    LOG.error(msg)
                    raise
                elif e.code == 503:
                    msg = "HTTP Error 503,The service of " \
                          "ceilometer is unavailable"
                    LOG.error(msg)
                    raise
                else:
                    LOG.error("Unknown Error")
                    raise
            except Exception, ex:
                LOG.error(ex.message)
                raise
        All_INSTANCES = _all_instance_details() or []
        # Get all instance in zabbix recored
        ZBX_HOSTS = [host[1] for host in hosts_id]
        for instance in All_INSTANCES:
            if instance['id'] in ZBX_HOSTS and utils.is_active(instance):
                LOG.debug("Start Checking host : " + host[3])
                # Get links for instance compute metrics
                request = urllib2.urlopen(urllib2.Request(
                    "http://" + self.ceilometer_api_host +
                    ":" + self.ceilometer_api_port +
                    "/v2/resources?q.field=metadata.instance_id&q.value=" +
                    host[1],
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "X-Auth-Token": self.token})).read()
                resources = json.loads(request)

                # Add a new instance and its metrics
                if instance['id'] not in METRIC_CACEHES.keys():
                    rs_items = {}
                    for rs in resources:
                        if rs['resource_id'].startswith('instance'):
                            rs_items[rs['resource_id']] = NETWORK_METRICS
                        # NOTE:remove disk metrics
                        elif utils.endswith_words(rs['resource_id']):
                            pass
                        else:
                            rs_items[rs['resource_id']] = INSTANCE_METRICS
                    METRIC_CACEHES[instance['id']] = rs_items
                # Update metric_caches where instance_in exists.For the case:
                # instance add/remove a nic
                # instance add/remove a volume
                else:
                    rs_items = METRIC_CACEHES[instance['id']]
                    rs_item_keys = rs_items.keys()
                    for rs in resources:
                        if rs['resource_id'] not in rs_item_keys and \
                           rs['resource_id'].startswith('instance'):
                            rs_items[rs['resource_id']] = NETWORK_METRICS
                            METRIC_CACEHES[instance['id']] = rs_items
                        # NOTE:remove disk metrics
                        elif rs['resource_id'] not in rs_item_keys and \
                                utils.endswith_words(rs['resource_id']):
                            pass
                        else:
                            continue
                LOG.debug("Starting to polling %s(%s) metric into zabbix"
                          % (instance.get('name'), instance.get('id')))
                # Polling Ceilometer the latest samplei into zabbix
                # CLI:ceilometer statistics -m {...} -q resource_id={...} -p ..
                self.polling_metrics(instance['id'])
                LOG.debug("Finshed to polling %s(%s) metric into zabbix"
                          % (instance.get('name'), instance.get('id')))
            else:
                LOG.debug("Can't find the instance : %s(%s), "
                          "or the status of %s is not active"
                          % (instance.get('name'),
                             instance.get('id'),
                             instance.get('name'))
                          )

    def polling_metrics(self, instance_id):
        """
        :param instance_id: nova instance uuid
        """
        def _polling(ids, METRICS):
            for metric in METRICS:
                counter_volume = 0.0
                try:
                    for rsc_id in ids:
                        contents = urllib2.urlopen(urllib2.Request(
                            "http://" + self.ceilometer_api_host +
                            ":" + self.ceilometer_api_port + "/v2/meters/" +
                            metric + "/statistics?q.field=resource_id&" +
                            "q.op=eq&q.type=&q.value=" + rsc_id + "&limit=1",
                            headers={
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                                "X-Auth-Token": self.token})).read()
                        response = json.loads(contents)
                        if len(response) > 0:
                            counter_volume += response[0]['avg']
                    LOG.info("Polling Ceilometer metric, resource_id: %s, "
                             "metric: %s, counter_name: %s"
                             % (rsc_id, metric, counter_volume))
                    self.send_data_zabbix(counter_volume, instance_id, metric)
                except urllib2.HTTPError, e:
                    if e.code == 401:
                        msg = "Error... \nToken refused! " \
                            "The request you have made requires authentication"
                        LOG.error(msg)
                        raise
                    elif e.code == 404:
                        msg = "Can't found for instances for tenant: %s" \
                              % self.instance_id
                        LOG.error(msg)
                        raise
                    elif e.code == 503:
                        msg = "HTTP Error 503,The service of " \
                              "ceilometer is unavailable"
                        LOG.error(msg)
                        raise
                    else:
                        LOG.error("Unknown Error")
                        raise
                except Exception, ex:
                    LOG.error(ex.message)
                    raise
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
        """
        Method used to simplify constructing the protocol to
        communicate with Zabbix
        :param data: refers to the json message
        :rtype : returns the message ready to send to Zabbix server
        with the right header
        """
        data_length = len(data)
        data_header = struct.pack('i', data_length) + '\0\0\0\0'
        HEADER = '''ZBXD\1%s%s'''
        data_to_send = HEADER % (data_header, data)
        payload = json.dumps(data)
        return payload

    def send_data_zabbix(self, counter_volume, resource_id, item_key):
        """
        Method used to prepare the body with data from Ceilometer and send
        it to Zabbix using connect_zabbix method

        :param counter_volume: the actual measurement
        :param resource_id:  refers to the resource ID
        :param item_key:    refers to the item key
        """
        tmp = json.dumps(counter_volume)
        data = {"request": "history data", "host": self.zabbix_proxy_name,
                "data": [{"host": resource_id,
                          "key": item_key,
                          "value": tmp}]}

        payload = self.set_proxy_header(data)
        self.connect_zabbix(payload)

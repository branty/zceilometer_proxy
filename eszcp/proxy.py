#!/usr/bin/env python
"""
Proxy for integration of resources between OpenStack's Ceilometer and Zabbix

This proxy periodically checks for changes in Ceilometer's resources reporting
them to Zabbix. It is also integrated

OpenStack's Nova and RabbitMQ for reflecting changes in
Projects/Tenants and Instances
"""

from eszcp import ceilometer_handler
from eszcp import log
from eszcp import nova_handler
from eszcp import project_handler
from eszcp import readFile
from eszcp import token_handler
from eszcp import zabbix_handler
import multiprocessing

__authors__ = "Claudio Marques, David Palma, Luis Cordeiro, Branty"
__copyright__ = "Copyright (c) 2014 OneSource Consultoria Informatica, Lda"
__license__ = "Apache 2"
__contact__ = ["www.onesource.pt", "www.openstack.cn"]
__date__ = "03/01/2016"
__email__ = "jun.wang@easystack.cn"
__version__ = "1.0.0"

log.initlog()
LOG = log.logger(__name__)
conf_file = readFile.ReadConfFile()


def init_zcp(processes):
    """
        Method used to initialize the Zabbix-Ceilometer Proxy
    """

    # Creation of the Auth keystone-dedicated authentication class
    # Responsible for managing AAA related requests
    keystone_auth = token_handler.Auth(conf_file.read_option(
                                        'keystone_authtoken',
                                        'keystone_host'),
                                       conf_file.read_option(
                                        'keystone_authtoken',
                                        'keystone_public_port'),
                                       conf_file.read_option(
                                        'keystone_authtoken',
                                        'admin_tenant'),
                                       conf_file.read_option(
                                        'keystone_authtoken',
                                        'admin_user'),
                                       conf_file.read_option(
                                        'keystone_authtoken',
                                        'admin_password'))

    # Creation of the Zabbix Handler class
    # Responsible for the communication with Zabbix
    zabbix_hdl = zabbix_handler.ZabbixHandler(conf_file.read_option(
                                                    'keystone_authtoken',
                                                    'keystone_admin_port'),
                                              conf_file.read_option(
                                                'nova_configs',
                                                'nova_port'),
                                              conf_file.read_option(
                                                    'zabbix_configs',
                                                    'zabbix_admin_user'),
                                              conf_file.read_option(
                                                    'zabbix_configs',
                                                    'zabbix_admin_pass'),
                                              conf_file.read_option(
                                                    'zabbix_configs',
                                                    'zabbix_host'),
                                              conf_file.read_option(
                                                    'keystone_authtoken',
                                                    'keystone_host'),
                                              conf_file.read_option(
                                                    'zcp_configs',
                                                    'template_name'),
                                              conf_file.read_option(
                                                    'zcp_configs',
                                                    'zabbix_proxy_name'),
                                              keystone_auth)

    # Creation of the Ceilometer Handler class
    # Responsible for the communication with OpenStack's Ceilometer,
    # polling for changes every N seconds
    ceilometer_hdl = ceilometer_handler.CeilometerHandler(
                        conf_file.read_option('ceilometer_configs',
                                              'ceilometer_api_port'),
                        conf_file.read_option('zcp_configs',
                                              'polling_interval'),
                        conf_file.read_option('zcp_configs',
                                              'template_name'),
                        conf_file.read_option('ceilometer_configs',
                                              'ceilometer_api_host'),
                        conf_file.read_option('zabbix_configs',
                                              'zabbix_host'),
                        conf_file.read_option('zabbix_configs',
                                              'zabbix_port'),
                        conf_file.read_option('zcp_configs',
                                              'zabbix_proxy_name'),
                        conf_file.read_option('nova_configs',
                                              'nova_host'),
                        conf_file.read_option('nova_configs',
                                              'nova_port'),
                        conf_file.read_option('keystone_authtoken',
                                              'admin_tenant_id'),
                        keystone_auth)

    # First run of the Zabbix handler for retrieving the necessary information
    zabbix_hdl.first_run()

    # Creation of the Nova Handler class
    # Responsible for detecting the creation of new instances in OpenStack,
    # translated then to Hosts in Zabbix
    nova_hdl = nova_handler.NovaEvents(
                conf_file.read_option('os_rabbitmq', 'rabbit_host'),
                conf_file.read_option('os_rabbitmq', 'rabbit_user'),
                conf_file.read_option('os_rabbitmq', 'rabbit_pass'),
                conf_file.read_option('os_rabbitmq', 'rabbit_port'),
                zabbix_hdl,
                ceilometer_hdl)

    # Creation of the Project Handler class
    # Responsible for detecting the creation of new tenants in OpenStack,
    # translated then to HostGroups in Zabbix
    project_hdl = project_handler.ProjectEvents(
                conf_file.read_option('os_rabbitmq', 'rabbit_host'),
                conf_file.read_option('os_rabbitmq', 'rabbit_user'),
                conf_file.read_option('os_rabbitmq', 'rabbit_pass'),
                conf_file.read_option('os_rabbitmq', 'rabbit_port'),
                zabbix_hdl)

    # Create and append processes to process list
    LOG.INFO('**************** Keystone listener started ****************')
    p1 = multiprocessing.Process(target=project_hdl.keystone_amq)
    p1.daemon = True
    processes.append(p1)

    LOG.INFO('**************** Nova listener started ****************')
    p2 = multiprocessing.Process(target=nova_hdl.nova_amq)
    p2.daemon = True
    processes.append(p2)

    p3 = multiprocessing.Process(target=ceilometer_hdl.interval_run)
    p3.daemon = True
    processes.append(p3)

    # start all the processes
    [ps.start() for ps in processes]


def main():
    processes = []
    LOG.info("-------------- Starting Zabbix Ceilometer Proxy --------------")
    init_zcp(processes)
    # wait for all processes to complete
    [ps.join() for ps in processes]
    LOG.info("************* Runnig Zabbix Ceilometer Proxy  ****************")
    print "ZCP terminated"
    LOG.info('************* Terninate Zabbix Ceilometer Proxy ***************')

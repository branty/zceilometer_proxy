#
#    Author : Branty(jun.wang@easystack.cn)
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Utilities and helper functions."""

import re


__authors__ = "Claudio Marques, David Palma, Luis Cordeiro, Branty"
__copyright__ = "Copyright (c) 2014 OneSource Consultoria Informatica, Lda"
__license__ = "Apache 2"
__contact__ = ["www.onesource.pt", "www.openstack.cn"]
__date__ = "03/01/2016"

__version__ = "1.0.0"

AVALIABLE_STATUS = [
    'SHUTOFF',
    'ACTIVE'
    ]


def isUseable_instance(status):
    """
    :param status: nova instance status
    """
    return status in AVALIABLE_STATUS


def is_active(instance):
    """
    :param instance: a nova instance,normally is a dict
    """
    if isinstance(instance, dict):
        return instance['server']['status'] == 'ACTIVE' \
               if "server" in instance.keys() \
               else instance['status'] == "ACTIVE"
    else:
        return False


def endswith_words(source):
    """
    Determine whether a string ends with the pattern of vd[a-z]
    example:
        string = 'aa0d0c92-31a8-44a2-vsfd' =>>> return False
        string = 'aa0d0a-4733-944bfe7-vda' =>>> return True
    :param source: str

    """
    match = False
    if isinstance(source, str):
        match = re.search(".*-vd[a-z]$", source)
    elif isinstance(source, unicode):
        match = re.search(".*-vd[a-z]$", str(source))
    else:
        return False
    return match

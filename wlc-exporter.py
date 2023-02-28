#!/usr/bin/env python3

import threading
import requests
import bottle
import traceback
import yaml

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(name)s %(message)s')
logger = logging.getLogger('wlc-exporter')

class Updater(threading.Thread):
    def __init__(self, config):
        super().__init__()

        self._config = config

        self._ssids = {}
        self._protocols = {}

        self._stopflag = threading.Event()
        self._next_run = 0

    def stop(self):
        logger.info('Stopping updater thread..')
        self._stopflag.set()
        self.join()

    def run(self):
        logger.info('Starting updater thread..')
        self.update()
        while not self._stopflag.wait(timeout=self._config['interval']):
            try:
                self.update()
            except:
                logger.error('Update failed!!')
                traceback.print_exc()

    def update(self):
        logger.debug('Updating statistics..')

        ap_url = '{}/api/hosts/{}@{}/tables/CISCO-LWAPP-AP-MIB::cLApTable'.format(config['snmpbot'], config['community'], config['wlc'])
        cl_url = '{}/api/hosts/{}@{}/tables/CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientTable'.format(config['snmpbot'], config['community'], config['wlc'])
        logger.debug('Using URL: {}'.format(ap_url))
        logger.debug('Using URL: {}'.format(cl_url))

        ap_payload = requests.get(ap_url).json()
        ap_entries = ap_payload['Entries']

        cl_payload = requests.get(cl_url).json()
        cl_entries = cl_payload['Entries']

        ssids = {}
        protocols = {}
        aps_mac = {}
        mac_mapping = {}

        for ap_entry in ap_entries:
            ap_mac = ap_entry['Index']['CISCO-LWAPP-AP-MIB::cLApSysMacAddress']
            ap_name = ap_entry['Objects']['CISCO-LWAPP-AP-MIB::cLApName']
            mac_mapping[ap_mac] = ap_name
            aps_mac[ap_mac] = 0

        for cl_entry in cl_entries:
            cl_objects = cl_entry['Objects']
            ssid = cl_objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientSSID']
            protocol = cl_objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientProtocol']
            ap_mac = cl_objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcApMacAddress']

            if ssid in ssids.keys():
                ssids[ssid] += 1
            else:
                ssids[ssid] = 1

            if protocol in protocols.keys():
                protocols[protocol] += 1
            else:
                protocols[protocol] = 1

            if not ap_mac in aps_mac.keys():
                logger.error('Unknown AP MAC: {}'.format(ap_mac))
                continue

            aps_mac[ap_mac] += 1

        self._ssids = ssids
        self._protocols = protocols
        self._aps_mac = aps_mac
        self._mac_mapping = mac_mapping

    def get_ssids(self):
        return self._ssids

    def get_protocols(self):
        return self._protocols

    def get_aps(self):
        ret = {}
        for mac, num in self._aps_mac.items():
            name = mac in self._mac_mapping.keys() and self._mac_mapping[mac] or 'N/A'
            ret[(mac, name)] = num
        return ret


@bottle.route('/metrics')
def bottle_metrics():
    output = []
    for k, v in updater.get_ssids().items():
        output.append('wlc_ssid_clients{{ssid="{}"}} {}'.format(k, v))

    for k, v in updater.get_protocols().items():
        output.append('wlc_types{{proto="{}"}} {}'.format(k, v))

    for k, v in updater.get_aps().items():
        output.append('wlc_ap_clients{{mac="{}", name="{}"}} {}'.format(k[0], k[1], v))

    text = '\n'.join(output)
    return bottle.HTTPResponse(text, headers={'Content-Type': 'text/plain'})


with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)
updater = Updater(config)
try:
    updater.start()
    bottle.run(host='0.0.0.0', port=9111)

finally:
    updater.stop()

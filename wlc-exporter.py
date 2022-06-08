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
        while not self._stopflag.wait(timeout=self._config['interval']):
            try:
                self.update()
            except:
                logger.error('Update failed!!')
                traceback.print_exc()

    def update(self):
        logger.debug('Updating statistics..')

        url = '{}/api/hosts/{}@{}/tables/CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientTable'.format(config['snmpbot'], config['community'], config['wlc'])
        logger.debug('Using URL: {}'.format(url))

        req = requests.get(url)
        payload = req.json()
        entries = payload['Entries']

        ssids = {}
        protocols = {}
        aps_mac = {}
        aps_name = {}
        for entry in entries:
            objects = entry['Objects']
            ssid = objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientSSID']
            protocol = objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientProtocol']
            apmac = objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcApMacAddress']

            if ssid in ssids.keys():
                ssids[ssid] += 1
            else:
                ssids[ssid] = 1

            if protocol in protocols.keys():
                protocols[protocol] += 1
            else:
                protocols[protocol] = 1

            if apmac in aps_mac.keys():
                aps_mac[apmac] += 1
            else:
                aps_mac[apmac] = 1

            for mac in aps_mac:
                if mac in config['mac_mapping'].keys():
                    apname = config['mac_mapping']['mac']
                    if apname in aps_name.keys():
                        aps_name[apname] += 1
                    else:
                        aps_name[apname] = 1



        self._ssids = ssids
        self._protocols = protocols
        self._aps_mac = aps_mac
        self._aps_name = aps_name

    def get_ssids(self):
        return self._ssids

    def get_protocols(self):
        return self._protocols

    def get_aps_mac(self):
        return self._aps_mac

    def get_aps_name(self):
        return self._aps_name


@bottle.route('/metrics')
def bottle_metrics():
    output = []
    for k, v in updater.get_ssids().items():
        output.append('wlc_ssid_clients{{ssid="{}"}} {}'.format(k, v))

    for k, v in updater.get_protocols().items():
        output.append('wlc_types{{proto="{}"}} {}'.format(k, v))

    for k, v in updater.get_aps_mac().items():
        output.append('wlc_ap_clients_mac{{mac="{}"}} {}'.format(k, v))

    for k, v in updater.get_aps_name().items():
        output.append('wlc_ap_clients_name{{name="{}"}} {}'.format(k,v))

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

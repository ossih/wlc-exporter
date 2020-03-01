#!/usr/bin/env python3

import threading
import requests
import time
import bottle
import traceback
import re
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

        self._is_running = True
        self._next_run = 0

    def stop(self):
        logger.info('Stopping updater thread..')
        self._is_running = False

    def run(self):
        logger.info('Starting updater thread..')
        while self._is_running:
            time_before = time.time()
            if time_before < self._next_run:
                time.sleep(1)
                continue

            try:
                self.update()
            except:
                logger.error('Update failed!!')
                traceback.print_exc()

            self._next_run = time_before + config['interval']

    def update(self):
        logger.debug('Updating statistics..')

        url = '{}/api/hosts/{}@{}/tables/CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientTable'.format(config['snmpbot'], config['community'], config['wlc'])
        logger.debug('Using URL: {}'.format(url))

        req = requests.get(url)
        payload = req.json()
        entries = payload['Entries']

        ssids = {}
        protocols = {}
        for entry in entries:
            objects = entry['Objects']
            ssid = objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientSSID']
            protocol = objects['CISCO-LWAPP-DOT11-CLIENT-MIB::cldcClientProtocol']

            if protocol.startswith('dot11'):
                protocol = re.sub('^dot11', '', protocol)

            if ssid in ssids.keys():
                ssids[ssid] += 1
            else:
                ssids[ssid] = 1

            if protocol in protocols.keys():
                protocols[protocol] += 1
            else:
                protocols[protocol] = 1

        self._ssids = ssids
        self._protocols = protocols

    def get_ssids(self):
        return self._ssids

    def get_protocols(self):
        return self._protocols


@bottle.route('/metrics')
def bottle_metrics():
    output = []
    for k, v in updater.get_ssids().items():
        output.append('wlc_ssid_clients{{ssid="{}"}} {}'.format(k, v))

    for k, v in updater.get_protocols().items():
        output.append('wlc_types{{proto="{}"}} {}'.format(k, v))

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

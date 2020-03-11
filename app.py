import sys, os
import requests
import json
import yaml
import argparse
import time
import math
import datetime
import schedule
import pytz
import hashlib
import uuid
import re

from expiringdict import ExpiringDict
from lxml import etree, html

cache = ExpiringDict(max_len=20, max_age_seconds=1000) 

def loadConfig(configFile='config.yml'):
    cfg = None
    with open(configFile, 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg

def getFlashLexToken(flashlexApiEndpoint, user, password):

    #print("get token", response_user, response_password)
    auth_response = requests.get('{flashlexApiEndpoint}/token'.format(flashlexApiEndpoint=flashlexApiEndpoint), 
        auth=(user, password))

    #print auth_response.json()
    if(auth_response.status_code == 200):        
        rmodel = auth_response.json()
        return rmodel['accessToken']
    else:
        raise ValueError("could not authenticate")

def sendFlashlexMessageToThing(thingId, messageModel, flashlexApiEndpoint, user, password):
    
    # encoding using encode() 
    # then sending to md5() 
    md5_hash = hashlib.md5(json.dumps(messageModel).encode()) 
    
    # add identifiers, we need to remove these and
    # recompute hash on client side
    messageModel['_id'] = str(uuid.uuid4())
    messageModel['_hash'] = md5_hash.hexdigest()

    # check if its in the cache, if missing then send
    if(cache.get(messageModel['_hash']) == None):
        cache[messageModel['_hash']] = messageModel
        accessToken = getFlashLexToken(flashlexApiEndpoint, user, password)
        headers = {'Authorization': "Bearer {0}".format(accessToken), 'Content-Type':"application/jsom"}
        publish_response = requests.post(
            '{flashlexApiEndpoint}/things/{thingId}/publish'.format(flashlexApiEndpoint=flashlexApiEndpoint, thingId=thingId), 
            data=json.dumps(messageModel), 
            headers=headers)
        #print("sending to thing:{0} message:{1} response from flashlex:{2}".format(thingId, json.dumps(messageModel), publish_response.status_code))
    else:
        #print("found message in cache", messageModel['_hash'])
        pass

def sendServiceMetrics(metrics, config):

    for metric in metrics:
        # print("metric", metric)
        messageModel = {
                'body':'{0}|{1}'.format(
                    metric['name'], metric['value']),
                'type':'metric',
                'behavior': 'number',
                'color': metric['color'],
                "font": "sm-1", 
                'elapsed': 20.0
        }

        sendFlashlexMessageToThing(
            config['flashlex']['thingId'], 
            messageModel, 
            config['flashlex']['apiEndpoint'],
            config['flashlex']['user'],
            config['flashlex']['password']) 


def replaceData(val):
   p = re.compile('\f*%')
   return p.sub('', '22.456%')

def getServicesMetrics(config):
    services = []
    for service in config['services']:
        if service['type'] == "table":        
            service['data'] = getServiceTableData(service)
        services.append(service)
    
    # print(json.dumps(services))
    return services

def getServiceTableData(service):
    #print(service)
    page = requests.get(service['url'])
    tree = html.fromstring(page.content)
    rows_data = []
    table_rows = tree.xpath(service['xpath'])
    for row in table_rows:
        #print(etree.tostring(row))
        tree_row = html.fromstring(etree.tostring(row))
        new_row = []

        ts_a = tree_row.xpath("//td/a/text()")
        for c1 in ts_a:
            if c1.strip() != '':
                new_row.append(c1.strip()) 

        ts_b = tree_row.xpath("//td/text()")
        for c2 in ts_b:
            if c2.strip() != '':
                new_row.append(c2.strip()) 

        if len(new_row)>0:
            rows_data.append(new_row)

    # now build metrics to be returned by id
    # by the metrics definitions 
    metrics_data = {}
    for metric in service['metrics']:
        metrics_data[metric['id']] = filterTableForMetric(rows_data, metric)
    
    return metrics_data

def filterTableForMetric(rows_data, metric):
    #print(rows_data)
    found_row = []
    if(metric['filterColumnTest'] == 'eq'):
        found_row = list(filter(lambda x: x[metric['filterColumnIndex']] == metric['filterColumnValue'], rows_data))

    print(found_row[0])

    if(len(found_row) > 0):
        val = replaceData(found_row[0][metric['valueColumnIndex']]) 
        val2 = found_row[0][metric['valueColumnIndex']]
        metric['value'] = int(val2)

    return metric

def serviceJob(service, config):
    print('=== running service job for world metrics')
    if service['type'] == "table":        
        service['data'] = getServiceTableData(service)

    if 'data' in service:
        sendServiceMetrics(service['metrics'], config)



# ======================================  
def main(argv):
    print("starting world info ticker with flashlex.")

    # Read in command-line parameters
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--config", action="store", required=True, dest="config", help="the YAML configuration file")
    
    args = parser.parse_args()
    configFile = args.config

    config = loadConfig(configFile)['worldometers']
    # services = getServicesMetrics(config)
    for service in config['services']:
        if(service['schedule']['rate'] == 'day'):
            schedule.every().day.at(service['schedule']['value']).do(serviceJob, service=service, config=config )
        if(service['schedule']['rate'] == 'hours'):
            schedule.every(service['schedule']['value']).hours.do(serviceJob, service=service, config=config )
        if(service['schedule']['rate'] == 'minutes'):
            schedule.every(service['schedule']['value']).minutes.do(serviceJob, service=service, config=config )

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main(sys.argv[1:])

#!/usr/bin/env python2.7

import requests
import json
import sys
import optparse
import ConfigParser
from urlparse import urlparse
from optparse import OptionGroup
import os
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class propertiesupdater(object):
    def __init__(self, definitions):
        self.ambari = ambariProps(protocol, host, port, username, password, clustername)
        self.definitions = definitions

    def service(self, service):
        for site, props in self.definitions[service].iteritems():
                for prop, value in props.iteritems():
                    finalvalue = self.replacefunc(value)
                    execute = self.ambari.set(site, prop, finalvalue)
                    print(execute)

    def replacefunc(self, value):
        for key, prop in changeprops.iteritems():
            value = value.replace(key, prop)
        return(value)


class ambariProps(object):
    def __init__(self, protocol, host, port, username, password, clustername):
        self.command = '/var/lib/ambari-server/resources/scripts/configs.py -p %s -t %s -l %s -u %s -s %s -n %s ' % (password, port, host, username, protocol, clustername)

    def get(self, config, property):
        command = '%s -c %s -a %s' % (self.command, config, 'get')
        data = os.popen(command + '| grep -v "###"').read()
        try:
            props = json.loads(data)
        except:
            final = 'http://localhost:8080'
        try:
            result = props["properties"][property]
        except:
            final = 'http://localhost:8080'
        try:
            final
        except:
            final = None
        if final is None:
            return(result)
        else:
            return(final)

    def set(self, config, property, value):
        command = "%s -c %s -a %s -k %s -v '%s'" % (self.command, config, 'set', property, value)
        result = os.popen(command).read()
        return(result)


def ambariREST(protocol, host, port, username, password, endpoint):
    url = protocol + "://" + host + ":" + str(port) + "/" + endpoint
    try:
        r = requests.get(url, auth=(username, password), verify=False)
    except:
        print("Cannot connect to Ambari")
        sys.exit(1)
    return(json.loads(r.text))


def ooziehost(protocol, host, port, username, password, clustername):
    try:
        info = ambariREST(protocol, host, port, username, password, "api/v1/clusters/%s/services/OOZIE/components/OOZIE_SERVER" % (clustername))
    except:
        return('localhost')
    host = info['host_components'][0]['HostRoles']['host_name']
    return(host)


def loaddefinitions():
    try:
        definitions = json.loads(open("./definitions.json").read())
    except:
        print("Cannot read defintions file")
        sys.exit(1)
    return(definitions)


def replaceurl(url, port):
    parsed = urlparse(url)
    newurl = 'https://' + parsed.hostname + ':' + str(port)
    return(newurl)


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-S", "--protocol", dest="protocol", default="http", help="default is http, set to https if required")
    parser.add_option("-P", "--port", dest="port", default="8080", help="Set Ambari Protocol")
    parser.add_option("-u", "--username", dest="username", default="admin", help="Ambari Username")
    parser.add_option("-p", "--password", dest="password", default="admin", help="Ambari Password")
    parser.add_option("-H", "--host", dest="host", default="localhost", help="Ambari Host")
    parser.add_option("-C", "--configfile", dest="configs", default="./configs", help="Config file containing key and truststore information")

    (options, args) = parser.parse_args()
    global username
    global password
    global port
    global protocol
    global host
    global clustername
    username = options.username
    password = options.password
    port = options.port
    protocol = options.protocol.lower()
    host = options.host
    if protocol not in ["http", "https"]:
        print("Protocol is not valid, use http or https")
        sys.exit(1)
    clustername = ambariREST(protocol, host, port, username, password, "api/v1/clusters")["items"][0]["Clusters"]["cluster_name"]
    installedservices = [line["ServiceInfo"]["service_name"] for line in ambariREST(protocol, host, port, username, password, "api/v1/clusters/" + clustername + "/services")["items"]]
    definitions = loaddefinitions()
    ambari = ambariProps(protocol, host, port, username, password, clustername)
    updater = propertiesupdater(definitions)
    Config = ConfigParser.ConfigParser()
    Config.read(options.configs)
    os.popen('PYTHONHTTPSVERIFY=0')
    global changeprops
    changeprops = {
        "KEYSTORELOC": Config.get("Configs", "KeyStoreLocation") + '/server.jks',
        "KEYSTORERANGER": Config.get("Configs", "KeyStoreLocation") + '/ranger-plugin.jks',
        "KEYPASS": Config.get("Configs", "KeyStorePassword"),
        "TRUSTSTORELOC": Config.get("Configs", "TrustStoreLocation") + '/truststore.jks',
        "TRUSTSTOREPASS": Config.get("Configs", "TrustStorePassword"),
        "RANGERCOMMONNAME": 'ranger.' + Config.get("Configs", "Domain"),
        "RANGERURL": replaceurl(ambari.get("admin-properties", "policymgr_external_url"), 6182),
        "TIMELINEURL": ambari.get("yarn-site", "yarn.timeline-service.webapp.address").split(':')[0] + ':8190',
        "HISTORYURL": ambari.get("mapred-site", "mapreduce.jobhistory.webapp.address").split(':')[0] + ':19889',
        "KMSURL": str(ambari.get("core-site", "hadoop.security.key.provider.path").replace(':9292', ':9393')).replace('//http@', '//https@'),
        "ATLASURL": replaceurl(ambari.get("application-properties", "atlas.rest.address"), 21443),
        "OOZIEURL": "https://%s:11443/oozie" % (ooziehost(protocol, host, port, username, password, clustername)),
    }
    if protocol is "https":
        changeprops.update({"TEZURL": replaceurl(ambari.get("tez-site", "tez.tez-ui.history-url.base"), port)})
    for service in installedservices:
        if service in definitions.keys():
            updater.service(service)
        else:
            continue


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nAborting ... Keyboard Interrupt.")
        sys.exit(1)

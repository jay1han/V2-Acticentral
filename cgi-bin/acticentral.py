#!/usr/bin/python

import os, urllib.parse, re, subprocess, sys, http.client, collections, json, pprint
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
from yattag import Doc

CENTRAL_HOST    = "localhost"
REPO_ROOT       = "/etc/actimetre/Repo"
DATA_ROOT       = "/etc/actimetre/Data"
UPLOAD_SIZE     = 1_000_000
UPLOAD_HR       = 1     
MAX_REPO_SIZE   = 10_000_000
MAX_REPO_HR     = 24
LOG_SIZE_MAX    = 1_000_000

TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"

REGISTRY        = "/etc/actimetre/Conf/registry.data"
ACTIMETRES      = "/etc/actimetre/Conf/actimetres.data"
ACTISERVERS     = "/etc/actimetre/Conf/actiservers.data"
LOG_FILE        = "/etc/actimetre/Log/central.log"
MQTT_TEXT       = "Acti"
MQTT_LOG        = "Acti/Log"

ACTIM_REPORT_SECS = 15
ACTIS_CHECK_SECS  = 15
ACTIS_FAIL_SECS   = 60

TIMEZERO = datetime(year=2020, month=1, day=1)

def printLog(text=''):
    try:
        if os.stat(LOG_FILE).st_size > LOG_SIZE_MAX:
            os.truncate(LOG_FILE, 0)
    except OSError: pass
    with open(LOG_FILE, 'a') as logfile:
        if text[-1:] == '\n':
            end = ''
        else:
            end = '\n'
        print('[' + str(datetime.utcnow()) + ' UTC]', text, file=logfile, end=end)

def prettyDate(dt):
    if dt == TIMEZERO:
        return '?'
    else:
        return dt.strftime(TIMEFORMAT_DISP)

### 

class SensorInfo:
    def __init__(self, actimId = 0, sensorId='', fileName='', fileSize = 0):
        self.actimId  = actimId
        self.sensorId = sensorId
        self.fileName = fileName
        self.fileSize = fileSize

    def toD(self):
        return {"actimId" : self.actimId,
                "sensorId": self.sensorId,
                "fileName": self.fileName,
                "fileSize": self.fileSize}

    def fromD(self, d):
        self.actimId  = int(d['actimId'])
        self.sensorId = d['sensorId']
        self.fileName = d['fileName']
        self.fileSize = int(d['fileSize'])
        return self

# Main class 

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='?', serverId=0, isDead=False, \
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,\
                 sensorList=None):
        self.actimId    = int(actimId)
        self.mac        = mac
        self.boardType  = boardType
        self.serverId   = int(serverId)
        self.isDead     = isDead
        self.bootTime   = bootTime
        self.lastSeen   = lastSeen
        self.lastReport = lastReport
        if sensorList is None:
            self.sensorList = {}
        else:
            self.sensorList = sensorList

    def toD(self):       
        return {'actimId'   : self.actimId,
                'mac'       : self.mac,
                'boardType' : self.boardType,
                'serverId'  : self.serverId,
                'isDead'    : self.isDead,
                'bootTime'  : self.bootTime.strftime(TIMEFORMAT_FN),
                'lastSeen'  : self.lastSeen.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'sensorList': {sensorInfo.sensorId:sensorInfo.toD() \
                               for sensorInfo in self.sensorList.values()}
                }

    def fromD(self, d):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.serverId   = int(d['serverId'])
        self.isDead     = bool(d['isDead']=="true" or d['isDead']=="True")
        self.bootTime   = datetime.strptime(d['bootTime'], TIMEFORMAT_FN)
        self.lastSeen   = datetime.strptime(d['lastSeen'], TIMEFORMAT_FN)
        self.lastReport = datetime.strptime(d['lastReport'], TIMEFORMAT_FN)
        if d.get('sensorList') is not None:
            self.sensorList = {sensorId:SensorInfo().fromD(sensorD)\
                               for sensorId, sensorD in d['sensorList'].items()}
        else:
            self.sensorList = {}
        return self

    def parsePort(self, portStr, port):
        if len(portStr) < 2: return 0
        if portStr[0] == port:
            if portStr[1] == 'A':
                self.sensorList[f'{port}A'] = SensorInfo(f'{port}A')
                if len(portStr) > 2 and portStr[2] == 'B':
                    self.sensorList[f'{port}B'] = SensorInfo(f'{port}B')
                    return 3
                else:
                    return 2
            else:
                self.sensorList[f'{port}B'] = SensorInfo(f'{port}B')
                return 2
        else:
            return 0

    def initSensorList(self, sensorStr):
        if sensorStr is None or sensorStr == '':
            self.sensorList = {}
            return
        cursor = self.parsePort(sensorStr, '1')
        self.parsePort(sensorStr[cursor:], '2')

    def actimName(self):
        return f"Actim{self.actimId:04d}"

    def serverName(self):
        return f"Actis{self.serverId:03d}"

    def sensorStr(self):
        accumulator = ''
        for port in range(2):
            portStr = '{:1d}'.format(port + 1)
            for address in range(2):
                if self.sensorList.get("{:1d}{:1c}".format(port + 1, ord('A') + address)) is not None:
                    portStr += '{:1c}'.format(ord('A') + address)
            if len(portStr) > 1:
                accumulator += portStr
        return accumulator

    def log(self, now, logString, data=None):
        longString = "{}: {}".format(prettyDate(now), logString)
        if args['l']:
            mqttClient.publish(MQTT_LOG, longString)
        if data is not None:
            logString += '\n' + str(data)
        if args['e']:
            print(logString)
        printLog(logString)

class Actiserver:
    def __init__(self, serverId=0, mac='.' * 12, ip='0.0.0.0', \
                 started=TIMEZERO, lastReport=TIMEZERO, \
                 actimetreList=None):
        self.serverId   = int(serverId)
        self.mac        = mac
        self.ip         = ip
        self.started    = started
        self.lastReport = lastReport
        if actimetreList is None:
            self.actimetreList = {}
        else:
            self.actimetreList = actimetreList

    def toD(self):
        return {'serverId'  : self.serverId,
                'mac'       : self.mac,
                'ip'        : self.ip,
                'started'   : self.started.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'actimetreList': {int(a.actimId):a.toD()
                                  for a in self.actimetreList.values()}
                }

    def fromD(self, d):
        self.serverId   = int(d['serverId'])
        self.mac        = d['mac']
        self.ip         = d['ip']
        self.started    = datetime.strptime(d['started'], TIMEFORMAT_FN)
        self.lastReport = datetime.strptime(d['lastReport'], TIMEFORMAT_FN)
        if d.get('actimetreList') is not None:
            self.actimetreList = {int(actimId):Actimetre().fromD(actimD)
                                  for actimId, actimD in d['actimetreList'].items()}
        else:
            self.actimetreList = {}
        return self

    def serverName(self):
        return f"Actis{self.serverId:03d}"

def loadData(filename):
    try:
        registry = open(filename, "r")
    except OSError:
        return {}
    data = json.loads(registry.read())
    printLog(f"Loaded from {filename}\n" + json.dumps(data))
    registry.close()
    return data

def dumpData(filename, data):
    try:
        os.truncate(filename, 0)
    except OSError:
        pass
    with open(filename, "r+") as registry:
        print(json.dumps(data), file=registry)
    printLog(f"Dumped to {filename}\n" + json.dumps(data))

pprinter = pprint.PrettyPrinter(indent=4, width=100, compact=True)

## The Registry: it's all in the shared library actilib.py

Registry = {}
Actiservers = {}
Actimetres  = {}

statinfo = os.stat(REGISTRY)
with open(REGISTRY, "r") as registry:
    try:
        Registry = json.load(registry)
    except JSONDecodeError:
        pass
    
def saveRegistry():
    os.truncate(REGISTRY, 0)
    with open(REGISTRY, "r+") as registry:
        json.dump(Registry, registry)
    printLog("Saved Registry " + str(Registry))

Actiservers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}
Actimetres  = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}

## Dump list of Actimetres in HTML

def printSize(size, unit='MB', precision=0):
    if unit == 'GB':
        inUnits = size / 1000000000
    else:
        inUnits = size / 1000000
    formatStr = '{:.' + str(precision) + 'f}'
    return formatStr.format(inUnits) + unit

def htmlActiservers():
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()
    doc.asis('<!DOCTYPE html>')

    with tag('html'):
        with tag('body'):
            with tag('table'):
                with tag('tr'):
                    line('th', 'Name')
                    line('th', 'MAC')
                    line('th', 'Actimetres')
                    line('th', 'Storage used')
                    line('th', 'Started')
                    line('th', 'Last update')

                for s in Actiservers.values():
                    with tag('tr'):
                        line('td', s.serverName())
                        with tag('td'):   # make thin spaces
                            doc.asis('&thinsp;'.join([s.mac[0:2], s.mac[2:4], s.mac[4:6], s.mac[6:8], s.mac[8:10], s.mac[10:12]]))
                        with tag('td', klass='center'):
                            for a in s.actimetreList.values():
                                line('div', a.actimName())
                        line('td', printSize(s.storage, 'MB', 1))
                        line('td', prettyDate(s.started))
                        line('td', prettyDate(s.lastReport))
    print(doc.getvalue())
    
def htmlActim(a):
    doc, tag, text, line = Doc().ttl()
    with tag('tr'):
        with tag('td'):
            doc.asis('Actim&shy;{:04d}'.format(a.actimId))
        with tag('td'):
            doc.asis('&thinsp;'.join([a.mac[0:2], a.mac[2:4], a.mac[4:6], a.mac[6:8], a.mac[8:10], a.mac[10:12]]))
        line('td', a.boardType, klass='center')
        line('td', a.sensorStr(), klass='center')
        line('td', a.serverName(), klass='center')
        line('td', prettyDate(a.bootTime))
        line('td', prettyDate(a.lastReport))
    return doc.getvalue()

def htmlActimetres():
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()
    doc.asis('<!DOCTYPE html>')

    actimList = {}
    for s in Actiservers.values():
        for a in s.actimetreList.values():
            actimList[a.actimId] = a

    with tag('html'):
        with tag('body'):
            with tag('table'):
                with tag('tr'):
                    line('th', 'Name')
                    line('th', 'MAC')
                    line('th', 'Type')
                    line('th', 'Sensors')
                    line('th', 'Server')
                    line('th', 'Booted')
                    line('th', 'Last update')
                    
                for actimId in sorted(actimList.keys()):
                    doc.asis(htmlActim(actimList[actimId]))
                for a in Actimetres.values():
                    doc.asis(htmlActim(a))
    print(doc.getvalue())
            
## Dump list of data files

def htmlDataActim(a):
    doc, tag, text, line = Doc().ttl()
    dataSize = 0
    totalRepo = 0
    pastRepoSize = 0
    pastRepoNums = 0
    
    with tag('tr'):
        with tag('td'):
            doc.asis('Actim&shy;{:04d}'.format(a.actimId))
        with tag('td'):
            for sensorInfo in a.sensorList.values():
                dataFile = sensorInfo.dataFile
                with tag('div', klass='list'):
                    text(sensorInfo.sensorId, ' : ', prettyDate(dataFile.fileDate))
                    with tag('div', klass='small'):
                        text(" {} ({:.1f}%)"\
                             .format(printSize(dataFile.fileSize, 'MB', 1),\
                                     100.0 * dataFile.fileSize / (UPLOAD_SIZE)))
                        dataSize += dataFile.fileSize
        with tag('td'):
            for sensorInfo in a.sensorList.values():
                repoFile = sensorInfo.repoFile
                totalRepo += repoFile.fileSize
                with tag('div', klass='list'):
                    text(sensorInfo.sensorId, ' : ', prettyDate(repoFile.fileDate))
                    with tag('div', klass='small'):
                        text(" {} ({:.2f}%)"\
                             .format(printSize(repoFile.fileSize, 'MB', 0),\
                                     100.0 * repoFile.fileSize / (MAX_REPO_SIZE)))
        with tag('td', klass='totals'):
            for sensorInfo in a.sensorList.values():
                repoFile = sensorInfo.repoFile
                pastRepoSize += repoFile.oldsSize
                pastRepoNums += repoFile.oldsNums
                with tag('div', klass='list'):
                    text(sensorInfo.sensorId, ' : ', repoFile.oldsNums, ' / ', printSize(repoFile.oldsSize, 'GB', 1))
    return (doc.getvalue(), dataSize, totalRepo, pastRepoSize, pastRepoNums)

def htmlDataRepo(otherRepoSize, otherRepoNums, freeRepo):
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()
    doc.asis('<!DOCTYPE html>')

    actimList = {}
    for s in Actiservers.values():
        for a in s.actimetreList.values():
            actimList[a.actimId] = a

    with tag('html'):
        with tag('body'):
            with tag('table'):
                with tag('tr'):
                    line('th', 'Name', rowspan=2)
                    line('th', 'Open Data files')
                    line('th', 'Open Repo files')
                    line('th', 'Past Repo files')

                with tag('tr'):
                    with tag('td', klass='sub'):
                        with tag('div', klass='code'):
                            text(DATA_ROOT)
                        with tag('div'):
                            text('each file max. ' + printSize(UPLOAD_SIZE, 'MB', 1))
                    with tag('td', klass='sub'):
                        with tag('div', klass='code'):
                            text(REPO_ROOT)
                        with tag('div'):
                            text('each file max. ' + printSize(MAX_REPO_SIZE, 'MB', 0))
                    line('td', '')

                dataSize = 0
                totalRepo = 0
                pastRepoSize = 0
                pastRepoNums = 0

                for actimId in sorted(actimList.keys()):
                    (html, data, total, pasts, pastn) = htmlDataActim(actimList[actimId])
                    doc.asis(html)
                    dataSize += data
                    totalRepo += total
                    pastRepoSize += pasts
                    pastRepoNums += pastn

                for a in Actimetres.values():
                    (html, data, total, pasts, pastn) = htmlDataActim(a)
                    doc.asis(html)
                    dataSize += data
                    totalRepo += total
                    pastRepoSize += pasts
                    pastRepoNums += pastn
                                    
                with tag('tr', klass='totals'):
                    with tag('td'):
                        text('Totals')
                    with tag('td'):
                        line('div', printSize(dataSize, 'MB', 1))
                    with tag('td'):
                        line('div', printSize(totalRepo, 'GB', 1))
                    with tag('td'):
                        line('div', str(pastRepoNums) + ' / ' + printSize(pastRepoSize, 'GB', 1))
                        with tag('div', klass='small'):
                            text('Unknown repo: ', otherRepoNums, ' / ', printSize(otherRepoSize, 'GB', 1))
                        with tag('div', klass='small'):
                            text('Available: ', printSize(freeRepo, 'GB', 1))
    print(doc.getvalue())

def actimStat(a, s=None):
    repoFiles = {}
    for sensorInfo in a.sensorList.values():
        repoFiles[f"Actim{a.actimId:04d}-{sensorInfo.sensorId}"] = sensorInfo.repoFile
        if s is not None:
            s.storage += sensorInfo.dataFile.fileSize
        sensorInfo.repoFile.oldsSize = 0
        sensorInfo.repoFile.oldsNums = 0
    return repoFiles

def dataStats():
    repoFiles = {}
    for s in Actiservers.values():
        s.storage = 0
        for a in Actimetres.values():
            repoFiles |= actimStat(a, s)
    for a in Actimetres.values():
        repoFiles |= actimStat(a)
            
    otherRepoSize = 0
    otherRepoNums = 0
    for repoFile in os.scandir(REPO_ROOT):
        fileName = repoFile.name
        fileSize = repoFile.stat().st_size
        sensorName = fileName[:12]
        actimId = int(fileName[5:9])
        sensorId = fileName[10:12]
        if repoFiles.get(sensorName) is None:
            otherRepoSize += fileSize
            otherRepoNums += 1
        elif repoFiles[sensorName].fileName != fileName:
            repoFiles[sensorName].oldsSize += fileSize
            repoFiles[sensorName].oldsNums += 1

    return (otherRepoSize, otherRepoNums)

## Main

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

now = datetime.utcnow()
for s in Actiservers.values():
    if now - s.lastReport > timedelta(seconds=ACTIS_FAIL_SECS):
        for a in s.actimetreList.values():
            Actimetres[a.actimId] = s.actimetreList[a.actimId]
        s.actimetreList = {}
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

qs = os.environ['QUERY_STRING']
printLog(qs)

args = urllib.parse.parse_qs(qs)
if 'action' in args.keys():
    action = args['action'][0]
else:
    action = ''

now = datetime.utcnow()
if action == 'actiserver':
    serverId = int(args['serverId'][0])
    ip = args['ip'][0]
    mac = args['mac'][0]

    printLog(f"Actis{serverId}={mac} at {ip}")
    thisServer = Actiserver().fromD(json.load(sys.stdin))

    if Actiservers.get(serverId) is not None:
        thisServer.started = Actiservers[serverId].started
        
    Actiservers[serverId] = thisServer
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

    plain(json.dumps(Registry))

elif action == 'actimetre-new':
    mac       = args['mac'][0]
    boardType = args['boardType'][0]
    serverId  = int(args['serverId'][0])
    bootTime  = datetime.strptime(args['bootTime'][0], TIMEFORMAT_FN)

    thisServer = Actiservers.get(serverId)
    if thisServer is None:
        thisServer = Actiserver(serverId, ip=ip, started=now, lastReport=now)
        Actiservers[serverId] = thisServer
    else:
        thisServer.lastReport = now

    if Registry.get(mac) is None:
        actimList = [r for r in Registry.values()]
        actimList.sort()
        actimId = len(actimList) + 1
        for newId in range(1, len(actimList) + 1):
            if not newId in actimList:
                actimId = newId
                break
        Registry[mac] = actimId
        printLog(f"Allocated new Actim{actimId:04d} for {mac}")
        saveRegistry()
    else:
        actimId = Registry[mac]
        printLog(f"Found known Actim{actimId:04d} for {mac}")
        
    a = Actimetre(actimId, mac, boardType, serverId, bootTime=now, lastSeen=now)
    printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")
    
    thisServer.actimetreList[actimId] = a
    if Actimetres.get(actimId) is not None:
        del Actimetres[actimId]
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain(actimId)

elif action == 'actimetre':
    actimId = int(args['actimId'][0])
    sensorStr = args['sensorStr'][0]
    serverId = int(args['serverId'][0])

    thisServer = Actiservers[serverId]

    newActim = Actimetre().fromD(json.load(sys.stdin))
    a = thisServer.actimetreList.get(actimId)
    if a is None:
        a = Actimetres.get(actimId)
    if a is None:
        a = newActim
    else:
        a.mac       = newActim.mac
        a.boardType = newActim.boardType
        a.bootTime  = newActim.bootTime
        
    thisServer.actimetreList[actimId] = a
    if Actimetres.get(actimId) is not None:
        del Actimetres[actimId]
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain("Ok")

elif action == 'actimetre-off':
    serverId = int(args['serverId'][0])
    actimId = int(args['actimId'][0])

    a = Actiservers[serverId].actimetreList.get(actimId)
    if a is not None:
        a.bootTime = TIMEZERO
        Actimetres[actimId] = a
        del Actiservers[serverId].actimetreList[actimId]
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain("Ok")

elif action == 'actimetre-html':
    htmlActimetres()

elif action == 'data':
    (otherRepoSize, otherRepoNums) = dataStats()

    freeRepo = 0
    with subprocess.Popen(['df', REPO_ROOT], text=True, stdout=subprocess.PIPE) as df:
        for line in df.stdout.readline():
            if re.match('^/', line):
                freeRepo = int(line.split()[3])

    htmlDataRepo(otherRepoSize, otherRepoNums, freeRepo)

# Fall-through, show index.html
else:
    print("Location:\\\n\n")

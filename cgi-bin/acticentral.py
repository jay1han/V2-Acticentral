#!/usr/bin/python3.9

import os, urllib.parse, re, subprocess, sys, http.client, collections, json, pprint, stat, time, fcntl
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
from yattag import Doc

LOG_SIZE_MAX    = 1_000_000

TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"

REPO_ROOT       = "/media/actimetre"
REGISTRY        = "/etc/actimetre/registry.data"
ACTIMETRES      = "/etc/actimetre/actimetres.data"
ACTISERVERS     = "/etc/actimetre/actiservers.data"
LOG_FILE        = "/etc/actimetre/central.log"
ACTI_META       = "/etc/actimetre/meta.data"

ACTIM_FAIL_SECS = 10
ACTIS_FAIL_SECS = 20

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
        print(text, file=logfile, end=end)

def prettyDate(dt):
    if dt == TIMEZERO:
        return '?'
    else:
        return dt.strftime(TIMEFORMAT_DISP)

# Main class 

class Actimetre:
    def __init__(self, actimId=9999, mac='.' * 12, boardType='?', version="", serverId=0, isDead=False, \
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,\
                 projectId = 0, sensorStr=""):
        self.actimId    = int(actimId)
        self.mac        = mac
        self.boardType  = boardType
        self.version    = version
        self.serverId   = int(serverId)
        self.isDead     = isDead
        self.bootTime   = bootTime
        self.lastSeen   = lastSeen
        self.lastReport = lastReport
        self.projectId  = projectId
        self.sensorStr  = sensorStr
        self.repoSize   = 0
        self.repoNums   = 0

    def toD(self):       
        return {'actimId'   : self.actimId,
                'mac'       : self.mac,
                'boardType' : self.boardType,
                'version'   : self.version,
                'serverId'  : self.serverId,
                'isDead'    : self.isDead,
                'bootTime'  : self.bootTime.strftime(TIMEFORMAT_FN),
                'lastSeen'  : self.lastSeen.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'projectId' : self.projectId,
                'sensorStr' : self.sensorStr,
                'repoSize'  : self.repoSize,
                'repoNums'  : self.repoNums
                }

    def fromD(self, d):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.version    = d['version']
        self.serverId   = int(d['serverId'])
        self.isDead     = bool(d['isDead']=="true" or d['isDead']=="True")
        self.bootTime   = datetime.strptime(d['bootTime'], TIMEFORMAT_FN)
        self.lastSeen   = datetime.strptime(d['lastSeen'], TIMEFORMAT_FN)
        self.lastReport = datetime.strptime(d['lastReport'], TIMEFORMAT_FN)
        self.sensorStr  = d['sensorStr']
        if d.get('projectId') is not None:
            self.projectId  = int(d['projectId'])
        else:
            self.projectId = 0
        if d.get('repoSize') is not None:
            self.repoSize = int(d['repoSize'])
        if d.get('repoNums') is not None:
            self.repoNums = int(d['repoNums'])
        return self

    def update(self, newActim, now):
        self.mac       = newActim.mac
        self.boardType = newActim.boardType
        self.version   = newActim.version
        self.serverId  = newActim.serverId
        self.isDead    = newActim.isDead
        self.bootTime  = newActim.bootTime
        self.lastSeen  = newActim.lastSeen
        self.sensorStr = newActim.sensorStr

    def actimName(self):
        return f"Actim{self.actimId:04d}"

    def serverName(self):
        return f"Actis{self.serverId:03d}"

class Actiserver:
    def __init__(self, serverId=0, mac='.' * 12, machine="Unknown", version="000", ip='0.0.0.0', channel=999,\
                 started=TIMEZERO, lastReport=TIMEZERO, \
                 actimetreList=set()):
        self.serverId   = int(serverId)
        self.mac        = mac
        self.machine    = machine
        self.version    = version
        self.ip         = ip
        self.channel    = int(channel)
        self.started    = started
        self.lastReport = lastReport
        self.actimetreList = actimetreList

    def toD(self):
        return {'serverId'  : self.serverId,
                'mac'       : self.mac,
                'machine'   : self.machine,
                'version'   : self.version,
                'ip'        : self.ip,
                'channel'   : self.channel,
                'started'   : self.started.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'actimetreList': list(self.actimetreList)
                }

    def fromD(self, d):
        self.serverId   = int(d['serverId'])
        self.mac        = d['mac']
        self.machine    = d['machine']
        self.version    = d['version']
        self.ip         = d['ip']
        self.channel    = int(d['channel'])
        self.started    = datetime.strptime(d['started'], TIMEFORMAT_FN)
        self.lastReport = datetime.strptime(d['lastReport'], TIMEFORMAT_FN)
        if d.get('actimetreList') is not None:
            self.actimetreList = set([int(a) for a in d['actimetreList']])
        else:
            self.actimetreList = set()
        return self

    def serverName(self):
        return f"Actis{self.serverId:03d}"

class Project:
    def __init__(self, projectId=0, title="", owner="", actimetreList=set()):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.actimetreList = actimetreList
        self.repoSize      = 0
        self.repoNums      = 0

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'repoSize'      : self.repoSize,
                'repoNums'      : self.repoNums,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId      = int(d['projectId'])
        self.title          = d['title']
        self.owner          = d['owner']
        self.repoSize       = int(d['repoSize'])
        self.repoNums       = int(d['repoNums'])
        if d.get('actimetreList') is not None:
            self.actimetreList = set([int(actimId) for actimId in d['actimetreList']])
        else:
            self.actimetreList = set()
        return self

    def addActim(self, a):
        self.actimetreList.add(a.actimId)

def loadData(filename):
    try:
        registry = open(filename, "r")
    except OSError:
        return {}
    data = json.load(registry)
    printLog(f"Loaded from {filename}\n" + json.dumps(data))
    registry.close()
    return data

def dumpData(filename, data):
    try:
        os.truncate(filename, 0)
    except OSError:
        pass
    with open(filename, "r+") as registry:
        json.dump(data, registry)
    printLog(f"Dumped to {filename}\n" + json.dumps(data))

pprinter = pprint.PrettyPrinter(indent=4, width=100, compact=True)

## Parse CGI query string -> action holds the verb

qs = os.environ['QUERY_STRING']
printLog(qs)

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
else:
    action = ''

## Mutex lock

lock = open("/etc/actimetre/acticentral.lock", "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)

## The Registry: it's all in the shared library actilib.py

Registry = {}
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
Projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(ACTI_META).items()}

garbageSize = 0
garbageNums = 0

def repoStats():
    global garbageSize, garbageNums
    garbageSize = 0
    garbageNums = 0

    for a in Actimetres.values():
        a.repoSize = 0
        a.repoNums = 0
            
    for repoFile in os.scandir(REPO_ROOT):
        fileName = repoFile.name
        fileSize = repoFile.stat().st_size
        sensorName = fileName[:12]
        actimId = int(fileName[5:9])
        sensorId = fileName[10:12]
        if Actimetres.get(actimId) is None:
            garbageSize += fileSize
            garbageNums += 1
        else:
            Actimetres[actimId].repoSize += fileSize
            Actimetres[actimId].repoNums += 1

    for p in Projects.values():
        p.repoSize = 0
        p.repoNums = 0
            
    for a in Actimetres.values():
        if Projects.get(a.projectId) is None:
            Projects[a.projectId] = Project(a.projectId, "Not assigned", "No owner")
        Projects[a.projectId].addActim(a)
        Projects[a.projectId].repoSize += a.repoSize
        Projects[a.projectId].repoNums += a.repoNums

    dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})
    return (garbageSize, garbageNums)

## Dump list of Actimetres in HTML

def printSize(size, unit='MB', precision=0):
    if unit == 'GB':
        inUnits = size / 1000000000
    else:
        inUnits = size / 1000000
    formatStr = '{:.' + str(precision) + 'f}'
    return formatStr.format(inUnits) + unit

def htmlActimetres():
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()

    for actimId in sorted(Actimetres.keys()):
        a = Actimetres[actimId]
        with tag('tr'):
            doc.asis('<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="actimId" value="{actimId}" />')
            with tag('td'):
                doc.asis('Actim&shy;{:04d}'.format(actimId))
            with tag('td'):
                doc.asis('&thinsp;'.join([a.mac[0:2], a.mac[2:4], a.mac[4:6], a.mac[6:8], a.mac[8:10], a.mac[10:12]]))
            line('td', a.boardType, klass='center')
            if datetime.utcnow() - a.lastReport < timedelta(seconds=ACTIM_FAIL_SECS):
                line('td', a.version, klass='center')
                line('td', a.sensorStr, klass='center')
                line('td', a.serverName(), klass='center')
                line('td', prettyDate(a.bootTime))
                line('td', prettyDate(a.lastReport))
            else:
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', prettyDate(a.lastReport), klass="red")
            with tag('td'):
                line('div', Projects[a.projectId].title)
                with tag('div', klass="right"):
                    line('button', "Change", type='submit', name='action', value='actim-change-project')
            line('td', str(a.repoNums) + " / " + printSize(a.repoSize, "GB", 1))
        doc.asis('</form>')
    print(doc.getvalue())
    
def htmlActiservers():
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()

    for s in Actiservers.values():
        with tag('tr'):
            line('td', s.serverName())
            line('td', s.machine)
            if datetime.utcnow() - s.lastReport < timedelta(seconds=ACTIS_FAIL_SECS):
                line('td', s.version, klass='center')
                line('td', s.ip)
                line('td', str(s.channel), klass='center')
                with tag('td'):
                    for a in s.actimetreList:
                        line('div', f"{Actimetres[a].actimName()} ({Actimetres[a].sensorStr})")
                line('td', prettyDate(s.started))
                line('td', prettyDate(s.lastReport))
            else:
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', '?', klass='center')
                line('td', '?', klass='center')
                line('td', '?', klass='center')
                line('td', prettyDate(s.lastReport), klass="red")
    print(doc.getvalue())
    
def htmlProjects():
    print("Content-type: text/html\n\n")
    doc, tag, text, line = Doc().ttl()

    for p in Projects.values():
        with tag('tr'):
            doc.asis('<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="projectId" value="{p.projectId}" />')
            line('td', p.title)
            line('td', p.owner)
            with tag('td'):
                for actimId in p.actimetreList:
                    line('div', f'{Actimetres[actimId].actimName()} ({Actimetres[actimId].sensorStr})')
            line('td', str(p.repoNums) + " / " + printSize(p.repoSize, "GB", 1))
            with tag('td', klass="no-borders"):
                if p.projectId != 0:
                    with tag('div'):
                        line('button', "Change info", type='submit', name='action', value='project-change-info')
                    with tag('div'):
                        line('button', "Remove", type='submit', name='action', value='remove-project')
            doc.asis('</form>')
    
    print(doc.getvalue())

def projectChangeInfo(projectId):
    print("Content-type: text/html\n\n")

    with open("/var/www/html/formProject.html") as form:
        print(form.read()\
              .replace("{projectTitle}", Projects[projectId].title)\
              .replace("{projectOwner}", Projects[projectId].owner)\
              .replace("{projectId}", str(projectId)))

def actimChangeProject(actimId):
    print("Content-type: text/html\n\n")

    htmlProjectList = ""
    for p in Projects.values():
        htmlProjectList += f'<input id="{p.projectId}" type="radio" name="projectId" value="{p.projectId}"'
        if p.projectId == Actimetres[actimId].projectId:
            htmlProjectList += ' checked="true"'
        htmlProjectList += f'><label for="{p.projectId}">{p.title} ({p.owner})</label><br>\n'

    with open("/var/www/html/formActim.html") as form:
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", Actimetres[actimId].actimName())\
              .replace("{htmlProjectList}", htmlProjectList))

def removeProject(projectId):
    printLog(f"Remove project with data: {Projects[projectId].title}, {Projects[projectId].owner}")

    if projectId != 0:
        for a in Projects[projectId].actimetreList:
            Actimetres[a].projectId = 0
        del Projects[projectId]
        dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    print("Location:\\index.html\n\n")

def processForm(formId):
    if formId == 'project-change-info':
        projectId = int(args['projectId'][0])
        title = args['title'][0]
        owner = args['owner'][0]
        printLog(f"Setting project {projectId} data: {title}, {owner}")
        
        if title != "" and owner != "":
            Projects[projectId].title = title
            Projects[projectId].owner = owner
            dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})
        print("Location:\\index.html\n\n")

    elif formId == 'actim-change-project':
        actimId = int(args['actimId'][0])
        projectId = int(args['projectId'][0])
        oldProject = Actimetres[actimId].projectId
        printLog(f"Changing {actimId} from {oldProject} to {projectId}")

        Projects[oldProject].actimetreList.remove(actimId)
        Projects[projectId].actimetreList.add(actimId)
        Actimetres[actimId].projectId = projectId
        dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        print("Location:\\index.html\n\n")

    elif formId == 'create-project':
        title = args['title'][0]
        owner = args['owner'][0]
        printLog(f"Create new project with data: {title}, {owner}")
        
        if title != "" and owner != "":
            projectId = 1
            while projectId in set(Projects.keys()):
                projectId += 1
            Projects[projectId] = Project(projectId, title, owner)
            dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})
        print("Location:\\index.html\n\n")

    else:
        print("Location:\\index.html\n\n")
    
## Main

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

now = datetime.utcnow()

if action == 'actiserver':
    serverId = int(args['serverId'][0])

    printLog(f"Actis{serverId} alive")
    thisServer = Actiserver().fromD(json.load(sys.stdin))

    if Actiservers.get(serverId) is not None:
        thisServer.started = Actiservers[serverId].started

    thisServer.lastReport = now
    
    Actiservers[serverId] = thisServer
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

    plain(json.dumps(Registry))

elif action == 'actimetre-new':
    mac       = args['mac'][0]
    boardType = args['boardType'][0]
    serverId  = int(args['serverId'][0])
    version   = args['version'][0]
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
        
    a = Actimetre(actimId, mac, boardType, version, serverId, bootTime=now, lastSeen=now, lastReport=now)
    printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")
    
    thisServer.actimetreList.add(actimId)
    Actimetres[actimId] = a
    dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain(actimId)

elif action == 'actimetre':
    actimId = int(args['actimId'][0])
    serverId = int(args['serverId'][0])

    thisServer = Actiservers[serverId]
    newActim = Actimetre().fromD(json.load(sys.stdin))
    a = Actimetres.get(actimId)
    if a is None:
        Actimetres[actimId] = newActim
    else:
        a.update(newActim, now)
    a.lastReport = now
    dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})

    if not actimId in thisServer.actimetreList:
        thisServer.actimetreList.add(actimId)
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

    plain("Ok")

elif action == 'actimetre-off':
    serverId = int(args['serverId'][0])
    actimId = int(args['actimId'][0])

    a = Actimetres.get(actimId)
    if a is not None:
        a.bootTime = TIMEZERO
        if a.actimId in Actiservers[serverId].actimetreList:
            Actiservers[serverId].actimetreList.remove(actimId)
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain("Ok")

elif action == 'prepare-stats':
    repoStats()
    plain("")

elif action == 'actimetre-html':
    htmlActimetres()

elif action == 'actiserver-html':
    htmlActiservers()

elif action == 'project-html':
    htmlProjects()

elif action == 'actim-change-project':
    actimId = int(args['actimId'][0])
    actimChangeProject(actimId)

elif action == 'project-change-info':
    projectId = int(args['projectId'][0])
    projectChangeInfo(projectId)

elif action == 'create-project':
    print("Location:\\formCreate.html\n\n")

elif action == 'remove-project':
    projectId = int(args['projectId'][0])
    removeProject(projectId)

elif action == 'submit':
    formId = args['formId'][0]
    printLog(f"Submitted form {formId}")
    processForm(formId)

# Fall-through, show index.html
else:
    print("Location:\\index.html\n\n")

#Release Mutex
lock.close()

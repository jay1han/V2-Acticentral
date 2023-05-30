#!/usr/bin/python3

import os, urllib.parse, sys, json, fcntl
from datetime import datetime, timedelta

LOG_SIZE_MAX    = 1_000_000

TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"

REGISTRY        = "/etc/actimetre/registry.data"
ACTIMETRES      = "/etc/actimetre/actimetres.data"
ACTISERVERS     = "/etc/actimetre/actiservers.data"
LOG_FILE        = "/etc/actimetre/central.log"
ACTI_META       = "/etc/actimetre/meta.data"
HISTORY_DIR     = "/etc/actimetre/history"
IMAGES_DIR      = "/var/www/html/images"

ACTIM_FAIL_SECS = 10
ACTIS_FAIL_SECS = 30

TIMEZERO     = datetime(year=2023, month=1, day=1)
REDRAW_TIME  = timedelta(minutes=5)
REFRESH_TIME = timedelta(seconds=15)
GRAPH_SPAN   = timedelta(days=7)
GRAPH_CULL   = timedelta(days=6)
FREQ_SCALE   = {0:0, 10:2, 30:5, 50:7, 100:10}

def scaleFreq(origFreq):
    for limit, scale in FREQ_SCALE.items():
        if origFreq <= limit:
            return scale

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

class Actimetre:
    def __init__(self, actimId=9999, mac='.' * 12, boardType='?', version="", serverId=0, isDead=True, \
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,\
                 projectId = 0, sensorStr="", frequency = 0, rating = 0.0,\
                 repoSize = 0):
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
        self.frequency  = frequency
        self.rating     = rating
        self.repoSize   = repoSize
        self.lastDrawn  = TIMEZERO
        self.graphSince = TIMEZERO

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
                'frequency' : self.frequency,
                'rating'    : self.rating,
                'repoSize'  : self.repoSize,
                'lastDrawn' : self.lastDrawn.strftime(TIMEFORMAT_FN),
                'graphSince': self.graphSince.strftime(TIMEFORMAT_FN),
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
        self.frequency  = int(d['frequency'])
        self.rating     = float(d['rating'])
        self.repoSize   = int(d['repoSize'])
        if d.get('projectId') is not None:
            self.projectId  = int(d['projectId'])
        else:
            self.projectId = 0
        if d.get('lastDrawn') is not None:
            self.lastDrawn = datetime.strptime(d['lastDrawn'], TIMEFORMAT_FN)
        if d.get('graphSince') is not None:
            self.graphSince = datetime.strptime(d['graphSince'], TIMEFORMAT_FN)
        return self

    def drawGraph(self, now):
        os.environ['MPLCONFIGDIR'] = "/etc/matplotlib"
        import matplotlib.pyplot as pyplot

        try:
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r") as history:
                self.graphSince = datetime.strptime(history.readline().partition(':')[0], TIMEFORMAT_FN)
        except (FileNotFoundError, ValueError):
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "w") as history:
                print(now.strftime(TIMEFORMAT_FN), ':', self.frequency, sep="", file=history)
                self.graphSince = now
                    
        with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r") as history:
            timeline = []
            frequencies = []
            for line in history:
                timeStr, part, freqStr = line.partition(':')
                timeline.append(datetime.strptime(timeStr.strip(), TIMEFORMAT_FN))
                freq = scaleFreq(int(freqStr))
                frequencies.append(freq)

        timeline.append(now)
        frequencies.append(scaleFreq(self.frequency))

        zero = [0 for i in range(len(timeline))]
        fig, ax = pyplot.subplots(figsize=(5.0,1.0), dpi=50.0)
        ax.set_axis_off()
        ax.set_ylim(bottom=-1, top=12)
        ax.text(now, 2, "  10", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 5, "  30", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 7, "  50", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 10, "100", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.plot(timeline, frequencies, drawstyle="steps-post", color="black", linewidth=1, solid_joinstyle="miter")
        ax.plot(timeline, zero, drawstyle="steps-post", color="red", linewidth=1, solid_joinstyle="miter")
        pyplot.savefig(f"{IMAGES_DIR}/Actim{self.actimId:04d}.svg", format='svg', bbox_inches="tight", pad_inches=0)
        pyplot.close()
        
        fig, ax = pyplot.subplots(figsize=(10.0,1.0), dpi=150.0)
        ax.set_frame_on(False)
        ax.set_ylim(bottom=-1, top=12)
        ax.get_yaxis().set_visible(False)
        ax.xaxis_date()
        pyplot.grid(True, 'both', 'x', linestyle='--', linewidth=0.5)
        ax.text(now, 2, "  10", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 5, "  30", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 7, "  50", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.text(now, 10, "100", family="sans-serif", stretch="condensed", ha="left", va="center")
        ax.plot(timeline, frequencies, drawstyle="steps-post", color="black", linewidth=1, solid_joinstyle="miter")
        ax.plot(timeline, zero, drawstyle="steps-post", color="red", linewidth=1, solid_joinstyle="miter")
        pyplot.savefig(f"{IMAGES_DIR}/Actim{self.actimId:04d}-large.svg", format='svg', bbox_inches="tight", pad_inches=0)
        pyplot.close()
        
        self.lastDrawn = now

        if now - self.graphSince >= GRAPH_SPAN:
            historyFile = f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist"
            freshLines = list()
            with open(historyFile, "r") as history:
                for line in history:
                    timeStr, part, freq = line.partition(':')
                    time = datetime.strptime(timeStr.strip(), TIMEFORMAT_FN)
                    if now - time < GRAPH_CULL:
                        time = now - GRAPH_CULL
                        self.graphSince = time
                        freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                        freshLines.extend(history.readlines())
            if len(freshLines) == 0:
                time = now - GRAPH_CULL
                self.graphSince = time
                freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                
            os.truncate(historyFile, 0)
            with open(historyFile, "r+") as history:
                for line in freshLines:
                    history.write(line)

    def drawGraphMaybe(self, now):
        if now - self.lastDrawn > REDRAW_TIME:
            self.drawGraph(now)
            return True
        else:
            return False

    def addFreqEvent(self, now, frequency):
        with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "a") as history:
            print(now.strftime(TIMEFORMAT_FN), ':', frequency, sep="", file=history)
        self.drawGraph(now)

    def update(self, newActim, now):
        if self.frequency != newActim.frequency:
            self.addFreqEvent(now, newActim.frequency)
        self.isDead    = False
        self.frequency = newActim.frequency
        self.boardType = newActim.boardType
        self.version   = newActim.version
        if self.serverId != newActim.serverId or self.bootTime != newActim.bootTime:
            self.addFreqEvent(newActim.bootTime, 0)
        self.serverId  = newActim.serverId
        self.bootTime  = newActim.bootTime
        self.lastSeen  = newActim.lastSeen
        self.sensorStr = newActim.sensorStr
        self.rating    = newActim.rating
        self.repoSize  = newActim.repoSize

    def updateSelf(self, now, frequency):
        if self.isDead:
            self.addFreqEvent(now, frequency)
            self.isDead    = False

    def actimName(self):
        return f"Actim{self.actimId:04d}"

    def serverName(self):
        return f"Actis{self.serverId:03d}"

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000", channel=0, ip = "0.0.0.0", \
                 lastReport=TIMEZERO, \
                 actimetreList=set()):
        self.serverId   = int(serverId)
        self.machine    = machine
        self.version    = version
        self.channel    = int(channel)
        self.ip         = ip
        self.lastReport = lastReport
        self.actimetreList = actimetreList

    def toD(self):
        return {'serverId'  : self.serverId,
                'machine'   : self.machine,
                'version'   : self.version,
                'channel'   : self.channel,
                'ip'        : self.ip,
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'actimetreList': list(self.actimetreList)
                }

    def fromD(self, d):
        self.serverId   = int(d['serverId'])
        self.machine    = d['machine']
        self.version    = d['version']
        self.channel    = int(d['channel'])
        self.ip         = d['ip']
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

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'repoSize'      : self.repoSize,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId      = int(d['projectId'])
        self.title          = d['title']
        self.owner          = d['owner']
        self.repoSize       = int(d['repoSize'])
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
    registry.close()
    return data

def dumpData(filename, data):
    printLog(json.dumps(data))
    try:
        os.truncate(filename, 0)
    except OSError:
        pass
    with open(filename, "r+") as registry:
        json.dump(data, registry)

qs = os.environ['QUERY_STRING']
printLog(qs)

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
else:
    action = ''

lock = open("/etc/actimetre/acticentral.lock", "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)

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

def repoStats(now):
    metaFile = os.stat(ACTI_META)
    if now - datetime.fromtimestamp(metaFile.st_mtime) > REFRESH_TIME:
        for p in Projects.values():
            p.repoSize = 0

        save = False
        for a in Actimetres.values():
            if a.drawGraphMaybe(now):
                save = True
            if Projects.get(a.projectId) is None:
                Projects[a.projectId] = Project(a.projectId, "Not assigned", "No owner")
            Projects[a.projectId].addActim(a)
            Projects[a.projectId].repoSize += a.repoSize

        if save:
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTI_META, {int(p.projectId):p.toD() for p in Projects.values()})

def printSize(size, unit='MB', precision=0):
    if unit == 'GB':
        inUnits = size / 1000000000
    else:
        inUnits = size / 1000000
    formatStr = '{:.' + str(precision) + 'f}'
    return formatStr.format(inUnits) + unit

def htmlActimetres(now):
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
            if now - a.lastReport < timedelta(seconds=ACTIM_FAIL_SECS):
                line('td', a.version, klass='center')
                line('td', a.sensorStr, klass='center')
                line('td', f"{a.frequency}Hz", klass='center')
                line('td', "{:.3f}%".format(100.0 * a.rating) , klass='center')
                line('td', a.serverName(), klass='center')
            else:
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', "?", klass='center')
                line('td', "?", klass='center')
            with tag('td', klass='health'):
                if a.graphSince == TIMEZERO:
                    text("Since ? ")
                else:
                    text("Since " + a.graphSince.strftime(TIMEFORMAT_DISP) + " ")
                doc.asis('<button type="submit" name="action" value="actim-reload-graph">&#x27f3;</button>')
                with tag('div'):
                    doc.asis(f'<a href="/images/Actim{actimId:04d}-large.svg"><img alt="Actim{actimId:04d} health" src="/images/Actim{actimId:04d}.svg" class="health"></a>\n')
            with tag('td'):
                line('div', Projects[a.projectId].title)
                with tag('div', klass='right'):
                    line('button', "Change", type='submit', name='action', value='actim-change-project')
            line('td', printSize(a.repoSize, 'GB', 1), klass='right')
        doc.asis('</form>')

    with open("/var/www/html/actimetres.html", "w") as html:
        print(doc.getvalue(), file=html)
    
def htmlActiservers(now):
    doc, tag, text, line = Doc().ttl()

    for s in Actiservers.values():
        with tag('tr'):
            line('td', s.serverName())
            line('td', s.machine)
            line('td', s.ip)
            if now - s.lastReport < timedelta(seconds=ACTIS_FAIL_SECS):
                line('td', s.version, klass='center')
                if s.channel != 0:
                    line('td', str(s.channel), klass='center')
                else:
                    line('td', "Unknown", klass='center')
                with tag('td'):
                    for a in s.actimetreList:
                        line('div', f"{Actimetres[a].actimName()} ({Actimetres[a].sensorStr})")
                line('td', prettyDate(s.lastReport))
            else:
                line('td', '?', klass='center')
                line('td', '?', klass='center')
                line('td', '?', klass='center')
                line('td', prettyDate(s.lastReport), klass='red')
    with open("/var/www/html/actiservers.html", "w") as html:
        print(doc.getvalue(), file=html)
    
def htmlProjects(now):
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
            line('td', printSize(p.repoSize, 'GB', 1), klass='right')
            with tag('td', klass="no-borders"):
                if p.projectId != 0:
                    with tag('div'):
                        line('button', "Change info", type='submit', name='action', value='project-change-info')
                    with tag('div'):
                        line('button', "Remove", type='submit', name='action', value='remove-project')
            doc.asis('</form>')
    
    with open("/var/www/html/projects.html", "w") as html:
        print(doc.getvalue(), file=html)

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
    
def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

now = datetime.utcnow()

if action == 'actiserver':
    serverId = int(args['serverId'][0])
    if serverId != 0:
        printLog(f"Actis{serverId} alive")
        thisServer = Actiserver().fromD(json.load(sys.stdin))
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
        thisServer = Actiserver(serverId, ip=ip, lastReport=now)
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

    if Actiservers.get(serverId) is None:
        Actiservers[serverId] = Actiserver()
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    thisServer = Actiservers[serverId]
    newActim = Actimetre().fromD(json.load(sys.stdin))
    a = Actimetres.get(actimId)
    if a is None:
        Actimetres[actimId] = newActim
        a = newActim
        a.updateSelf(now, newActim.frequency)
    else:
        a.update(newActim, now)
    Actimetres[actimId].lastReport = now
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
        a.isDead = True
        a.addFreqEvent(now, 0)
        a.frequency = 0
        if a.actimId in Actiservers[serverId].actimetreList:
            Actiservers[serverId].actimetreList.remove(actimId)
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    plain("Ok")

elif action == 'actim-change-project':
    actimId = int(args['actimId'][0])
    actimChangeProject(actimId)

elif action == 'actim-reload-graph':
    actimId = int(args['actimId'][0])
    if Actimetres.get(actimId) is not None:
        save = False
        if Actimetres[actimId].graphSince == TIMEZERO:
            save = True
        Actimetres[actimId].drawGraph(now)
        if save:
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    print("Location:\\index.html\n\n")

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

elif action == 'prepare-stats':
    from yattag import Doc
    repoStats(now)
    htmlActimetres(now)
    htmlActiservers(now)
    htmlProjects(now)
    plain("")

else:
    print("Location:\\index.html\n\n")

lock.close()

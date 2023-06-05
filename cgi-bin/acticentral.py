#!/usr/bin/python3

import os, sys, json, fcntl
from datetime import datetime, timedelta
from yattag import Doc, indent

LOG_SIZE_MAX    = 1_000_000

TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"

REGISTRY        = "/etc/actimetre/registry.data"
ACTIMETRES      = "/etc/actimetre/actimetres.data"
ACTISERVERS     = "/etc/actimetre/actiservers.data"
LOG_FILE        = "/etc/actimetre/central.log"
PROJECTS        = "/etc/actimetre/projects.data"
HISTORY_DIR     = "/etc/actimetre/history"
IMAGES_DIR      = "/var/www/html/images"
IMAGES_INDEX    = "/var/www/html/images/index.txt"
HTML_DIR        = "/var/www/html"

ACTIS_FAIL_TIME = timedelta(seconds=30)
ACTIS_RETIRE_P  = timedelta(days=7)
ACTIS_HIDE_P    = timedelta(days=1)
ACTIM_FAIL_TIME = ACTIS_FAIL_TIME
ACTIM_RETIRE_P  = timedelta(days=7)
ACTIM_HIDE_P    = timedelta(days=1)

TIMEZERO     = datetime(year=2023, month=1, day=1)

def printLog(text=''):
    try:
        if os.stat(LOG_FILE).st_size > LOG_SIZE_MAX:
            os.truncate(LOG_FILE, 0)
    except OSError: pass
    with open(LOG_FILE, 'a') as logfile:
        print(f'[{datetime.utcnow().strftime(TIMEFORMAT_DISP)}]', text, file=logfile)

def loadData(filename):
    try:
        registry = open(filename, "r")
    except OSError:
        return {}
    data = json.load(registry)
    registry.close()
    return data

def dumpData(filename, data):
    printLog(f"[DUMP {filename}] {json.dumps(data)}")
    try:
        os.truncate(filename, 0)
    except OSError:
        pass
    with open(filename, "r+") as registry:
        json.dump(data, registry)

def printSize(size, unit='', precision=0):
    if size == 0:
        return ""
    if unit == '':
        if size >= 1_000_000_000:
            unit = 'GB'
            if size >= 10_000_000_000:
                precision = 1
            else:
                precision = 2
        else:
            unit = 'MB'
            if size >= 100_000_000:
                precision = 0
            elif size >= 10_000_000:
                precision = 1
            else:
                precision = 2
    if unit == 'GB':
        inUnits = size / 1_000_000_000
    else:
        inUnits = size / 1_000_000
    formatStr = '{:.' + str(precision) + 'f}'
    return formatStr.format(inUnits) + unit

def sendEmail(now, recipient, subject, text):
    content = f"""\
    Event: {subject}
    At {now.strftime(TIMEFORMAT_DISP)}

    {text}

    For more information, please visit www.actimetre.fr
    """
    data = { \
        'Content': { 'Simple': { 'Body'   : { 'Text': { 'Data': content } }, \
                                 'Subject': { 'Data': subject } } }, \
        'Destination': { 'ToAddresses': [recipient] }, \
        'FromEmailAddress': 'acticentral@actimetre.fr', \
        'ReplyToAddresses': ['manager@actimetre.fr'] }
    pass

lock = open("/etc/actimetre/acticentral.lock", "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)

class Project:
    def __init__(self, projectId=0, title="", owner="", email="", actimetreList=set()):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.email         = email
        self.actimetreList = actimetreList
        self.repoSize      = 0

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'email'         : self.email,
                'repoSize'      : self.repoSize,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId      = int(d['projectId'])
        self.title          = d['title']
        self.owner          = d['owner']
        if d.get('email') is not None:
            self.email = d['email']
        self.repoSize       = int(d['repoSize'])
        if d.get('actimetreList') is not None:
            self.actimetreList = set([int(actimId) for actimId in d['actimetreList']])
        return self

    def addActim(self, a):
        self.actimetreList.add(a.actimId)
        
Projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}

REDRAW_TIME  = timedelta(minutes=5)
REDRAW_DEAD  = timedelta(minutes=30)
GRAPH_SPAN   = timedelta(days=7)
GRAPH_CULL   = timedelta(days=6)
FSCALE       = {10:2, 30:4, 50:7, 100:10}

def scaleFreq(origFreq):
    if origFreq == 0:
        return 0
    for limit, scale in FSCALE.items():
        if origFreq <= limit:
            return scale

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='?', version="", serverId=0, isDead=True, \
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,\
                 projectId = 0, sensorStr="", frequency = 0, rating = 0.0, repoSize = 0):
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
                'isDead'    : str(self.isDead),
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

    def fromD(self, d, actual=False):
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
            for p in Projects.values():
                if self.actimId in p.actimetreList and p.projectId != self.projectId:
                    p.actimetreList.remove(self.actimId)
            Projects[self.projectId].actimetreList.add(self.actimId)
        else:
            for p in Projects.values():
                if self.actimId in p.actimetreList:
                    self.projectId = p.projectId
            
        if d.get('lastDrawn') is not None:
            self.lastDrawn = datetime.strptime(d['lastDrawn'], TIMEFORMAT_FN)
        if d.get('graphSince') is not None:
            self.graphSince = datetime.strptime(d['graphSince'], TIMEFORMAT_FN)
        return self

    def cutHistory(self, cutLength=None, now=datetime.utcnow()):
        if cutLength == None:
            cutLength = now - self.bootTime
            
        historyFile = f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist"
        freshLines = list()
        with open(historyFile, "r") as history:
            for line in history:
                timeStr, part, freq = line.partition(':')
                time = datetime.strptime(timeStr.strip(), TIMEFORMAT_FN)
                if now - time < cutLength:
                    time = now - cutLength
                    self.graphSince = time
                    freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                    freshLines.extend(history.readlines())
        if len(freshLines) == 0:
            time = now - cutLength
            self.graphSince = time
            freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{self.frequency}")

        os.truncate(historyFile, 0)
        with open(historyFile, "r+") as history:
            for line in freshLines:
                history.write(line)

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
            try:
                os.chmod(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", 0o666)
            except OSError:
                pass
                    
        timeline = []
        frequencies = []
        with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r") as history:
            for line in history:
                timeStr, part, freqStr = line.partition(':')
                time = datetime.strptime(timeStr.strip(), TIMEFORMAT_FN)
                freq = scaleFreq(int(freqStr))
                timeline.append(time)
                frequencies.append(freq)

        timeline.append(now)
        frequencies.append(scaleFreq(self.frequency))
        freq = [scaleFreq(self.frequency) for i in range(len(timeline))]

        fig, ax = pyplot.subplots(figsize=(5.0,1.0), dpi=50.0)
        ax.set_axis_off()
        ax.set_ylim(bottom=-1, top=12)
        ax.axvline(timeline[0], 0, 0.95, lw=1.0, c="blue", marker="^", markevery=[1], ms=5.0, mfc="blue")
        for real, drawn in FSCALE.items():
            if self.frequency == real:
                c = 'green'
                w = 'bold'
            else:
                c = 'black'
                w = 'regular'
            ax.text(now, drawn, f"{real:4d}", family="sans-serif", stretch="condensed", ha="left", va="center", c=c, weight=w)
        ax.plot(timeline, frequencies, ds="steps-post", c="black", lw=1.0, solid_joinstyle="miter")
        if self.isDead:
            ax.plot(timeline[-2:], freq[-2:], ds="steps-post", c="red", lw=3.0)
        else:
            ax.plot(timeline[-2:], freq[-2:], ds="steps-post", c="green", lw=3.0)
        pyplot.savefig(f"{IMAGES_DIR}/Actim{self.actimId:04d}.svg", format='svg', bbox_inches="tight", pad_inches=0)
        pyplot.close()
        try:
            os.chmod(f"{IMAGES_DIR}/Actim{self.actimId:04d}.svg", 0o666)
        except OSError:
            pass

        updateMap = {}
        dataMap = {}
        with open(IMAGES_INDEX, "r") as index:
            for line in index:
                if line.strip() != "":
                    actimStr, updateStr, dataStr = line.split(':')
                    actimId = int(actimStr.strip())
                    updateMap[actimId] = updateStr.strip()
                    dataMap[actimId] = dataStr.strip()
        updateMap[self.actimId] = now.strftime(TIMEFORMAT_FN)
        dataMap[self.actimId] = f'{self.boardType},{self.serverId},{self.sensorStr},{self.frequency},{self.rating}'
        os.truncate(IMAGES_INDEX, 0)
        with open(IMAGES_INDEX, "r+") as index:
            for actimId in updateMap.keys():
                print(f'{actimId}:{updateMap[actimId]}:{dataMap[actimId]}', file=index)
        printLog(f'{self.actimName()}.drawGraph --> ' + ','.join(map(str, updateMap.keys())))
        
        self.lastDrawn = now
        if now - self.graphSince >= GRAPH_SPAN:
            self.cutHistory(GRAPH_CULL, now)

    def drawGraphMaybe(self, now):
        redraw = False
        if self.isDead:
            if now - self.lastDrawn > REDRAW_DEAD:
                redraw = True
        else:
            if now - self.lastDrawn > REDRAW_TIME and now - self.bootTime > ACTIM_FAIL_TIME:
                redraw = True
        if redraw:
            self.drawGraph(now)
        return redraw

    def addFreqEvent(self, now, frequency):
        with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r+") as history:
            for line in history:
                timeStr, part, freq = line.partition(':')
                time = datetime.strptime(timeStr.strip(), TIMEFORMAT_FN)
            if now < time and frequency != freq:
                now = time
            print(now.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)

    def update(self, newActim, now, actual=False):
        redraw = False
        if actual:
            if self.serverId != newActim.serverId or self.bootTime != newActim.bootTime:
                self.addFreqEvent(newActim.bootTime, 0)
                self.frequency = 0
                redraw = True
            if self.frequency != newActim.frequency:
                self.addFreqEvent(now, newActim.frequency)
                redraw = True
            self.frequency  = newActim.frequency
            self.isDead     = False
        self.boardType  = newActim.boardType
        self.version    = newActim.version
        self.serverId   = newActim.serverId
        self.bootTime   = newActim.bootTime
        self.lastSeen   = newActim.lastSeen
        self.lastReport = newActim.lastReport
        self.sensorStr  = newActim.sensorStr
        self.rating     = newActim.rating
        self.repoSize   = newActim.repoSize
        if redraw:
            self.drawGraph(now)
        return redraw

    def dies(self, now):
        printLog(f'{self.actimName()} dies {now.strftime(TIMEFORMAT_DISP)}')
        if Projects.get(self.projectId) is not None \
           and Projects[self.projectId].email != "":
            sendEmail(now, Projects[self.projectId].email,\
                      f'{self.actimName()} died',\
                      f'{self.actimName()}\nType {self.boardType}\nMAC {self.mac}\n' +\
                      f'Connected to Actis{self.serverId:03d}\nSensors {self.sensorStr}\nRunning at {self.frequency}Hz\n' +\
                      f'Latest uptime {self.uptime(now)}\nMissing rate {self.rating:.3f}%\n' +\
                      f'Total data size {printSize(self.repoSize)}\n')
        self.isDead    = True
        self.frequency = 0
        self.addFreqEvent(now, 0)
        self.serverId = 0
        self.drawGraph(now)

    def actimName(self):
        return f"Actim{self.actimId:04d}"

    def htmlInfo(self):
        if self.isDead or self.frequency == 0:
            return f'<span class="dead">(dead)</span>'
        else:
            return f'{self.sensorStr}@{self.frequency}Hz'
        
    def htmlCartouche(self):
        return f'{self.actimName()}&nbsp;<span class="small">{self.htmlInfo()}</span> '

    def uptime(self, now):
        up = now - self.bootTime
        days = up // timedelta(days=1)
        hours = (up % timedelta(days=1)) // timedelta(hours=1)
        minutes = (up % timedelta(hours=1)) // timedelta(minutes=1)
        if up > timedelta(days=1):
            return f'{days}d{hours}h'
        else:
            return f'{hours}h{minutes:02d}m'
Actimetres  = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000", channel=0, ip = "0.0.0.0", \
                 lastReport=TIMEZERO, actimetreList=set()):
        self.serverId   = int(serverId)
        self.machine    = machine
        self.version    = version
        self.channel    = int(channel)
        self.ip         = ip
        self.lastReport = lastReport
        self.actimetreList = actimetreList
        self.saveActim  = False

    def toD(self):
        return {'serverId'  : self.serverId,
                'machine'   : self.machine,
                'version'   : self.version,
                'channel'   : self.channel,
                'ip'        : self.ip,
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'actimetreList': '[' + ','.join([json.dumps(Actimetres[actimId].toD()) for actimId in self.actimetreList]) + ']'
                }

    def fromD(self, d, actual=False):
        self.serverId   = int(d['serverId'])
        self.machine    = d['machine']
        self.version    = d['version']
        self.channel    = int(d['channel'])
        self.ip         = d['ip']
        self.lastReport = datetime.strptime(d['lastReport'], TIMEFORMAT_FN)
        self.saveActim  = False
        self.actimetreList = set()
        if d['actimetreList'] != "[]":
            for actimData in json.loads(d['actimetreList']):
                a = Actimetre().fromD(actimData, actual)
                if Actimetres.get(a.actimId) is None:
                    Actimetres[a.actimId] = a
                    if actual:
                        self.saveActim = True
                else:
                    if Actimetres[a.actimId].update(a, self.lastReport, actual):
                        self.saveActim = True
                self.actimetreList.add(a.actimId)
        else:
            self.actimetreList = set()
        for a in Actimetres.values():
            if a.serverId == self.serverId and not a.actimId in self.actimetreList:
                a.dies(self.lastReport)
                self.saveActim = True
        return self

    def serverName(self):
        return f"Actis{self.serverId:03d}"
Actiservers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}

def saveRegistry():
    os.truncate(REGISTRY, 0)
    with open(REGISTRY, "r+") as registry:
        json.dump(Registry, registry)
    printLog("Saved Registry " + str(Registry))

Registry = {}
with open(REGISTRY, "r") as registry:
    try:
        Registry = json.load(registry)
    except JSONDecodeError:
        pass
    
if Projects.get(0) is None:
    Projects[0] = Project(0, "Not assigned", "No owner")
    dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

def htmlActimetres(now):
    doc, tag, text, line = Doc().ttl()

    for actimId in sorted(Actimetres.keys()):
        a = Actimetres[actimId]
        if now - a.lastReport > ACTIM_HIDE_P:
            continue
        with tag('tr'):
            doc.asis('<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="actimId" value="{actimId}"/>')
            alive = ''
            if now - a.lastReport > ACTIM_RETIRE_P:
                alive = 'retire'
            elif now - a.lastReport > ACTIM_FAIL_TIME or a.frequency == 0:
                alive = 'dead'

            with tag('td', klass=alive):
                doc.asis('Actim&shy;{:04d}<br>'.format(actimId))
                if alive == 'retire':
                    line('button', "Retire", type='submit', name='action', value='retire-actim')
            with tag('td'):
                text(a.boardType)
                doc.asis('<br>\n')
                if alive == '': text(f"v{a.version}")
            if alive == '':
                line('td', a.sensorStr)
                line('td', "{:.3f}%".format(100.0 * a.rating))
            else: 
                line('td', "?")
                line('td', "?")

            if alive == 'retire':
                line('td', 'No data', klass=f'health retire')
            else:
                with tag('td', klass=f'health left'):
                    if a.graphSince == TIMEZERO:
                        text('? ')
                    else:
                        text(a.graphSince.strftime(TIMEFORMAT_DISP) + "\n")
                    doc.asis('<button type="submit" name="action" value="actim-cut-graph">&#x2702;</button>\n')
                    if alive == 'dead':
                        line('span', 'down', klass='dead')
                    else:
                        line('span', f'up {a.uptime(now)}', klass='up')
                    with tag('div'):
                        doc.stag('img', src=f'/images/Actim{actimId:04d}.svg', klass='health')

            with tag('td'):
                line('div', Projects[a.projectId].title, klass='left')
                with tag('div', klass='right'):
                    line('button', "Change", type='submit', name='action', value='actim-change-project')
            with tag('td', klass='right'):
                text(printSize(a.repoSize))
                if alive != '': doc.asis('<br>(?)')
        doc.asis('</form>\n')

    with open(f"{HTML_DIR}/actimetres.html", "w") as html:
        print(indent(doc.getvalue()), file=html)

def htmlActiservers(now):
    doc, tag, text, line = Doc().ttl()

    for serverId in sorted(Actiservers.keys()):
        s = Actiservers[serverId]
        if now - s.lastReport > ACTIM_HIDE_P:
            continue
        with tag('tr'):
            doc.asis('<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="serverId" value="{s.serverId}" />')
            if now - s.lastReport < ACTIS_FAIL_TIME:
                alive = ''
            elif now - s.lastReport > ACTIS_RETIRE_P:
                alive = 'retire'
            else:
                alive = 'dead'

            with tag('td', klass=alive):
                text(s.serverName())
                if alive == 'retire':
                    line('button', "Retire", type='submit', name='action', value='retire-server')
            line('td', s.machine)
            with tag('td'):
                if alive == '':
                    text(f"v{s.version}")
                    doc.asis("<br>")
                    if s.channel != 0:
                        text(f"Ch. {s.channel}")
                else:
                    text("?")
            if alive != '':
                line('td', "None")
            else:
                with tag('td', klass='left'):
                    for a in s.actimetreList:
                        with tag ('div'):
                            doc.asis(Actimetres[a].htmlCartouche())
            if s.lastReport == TIMEZERO:
                line('td', "?", klass=alive)
            else:
                line('td', s.lastReport.strftime(TIMEFORMAT_DISP), klass=alive)
    with open(f"{HTML_DIR}/actiservers.html", "w") as html:
        print(indent(doc.getvalue()), file=html)

def htmlProjects(now):
    doc, tag, text, line = Doc().ttl()

    for projectId in sorted(Projects.keys()):
        p = Projects[projectId]
        with tag('tr'):
            doc.asis('<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="projectId" value="{p.projectId}" />')
            line('td', p.title, klass='left')
            line('td', p.owner)
            with tag('td', klass='left'):
                for actimId in p.actimetreList:
                    if Actimetres.get(actimId) is not None:
                        with tag('div'):
                            doc.asis(Actimetres[actimId].htmlCartouche())
            line('td', printSize(p.repoSize), klass='right')
            with tag('td', klass="no-borders"):
                if p.projectId != 0:
                    with tag('div', klass='left'):
                        line('button', "Edit", type='submit', name='action', value='project-change-info')
                    with tag('div', klass='left'):
                        line('button', "Remove", type='submit', name='action', value='remove-project')
            doc.asis('</form>')

    with open(f"{HTML_DIR}/projects.html", "w") as html:
        print(indent(doc.getvalue()), file=html)

def repoStats(now):
    for p in Projects.values():
        p.repoSize = 0

    save = False
    for a in Actimetres.values():
        if now - a.lastReport > ACTIM_HIDE_P:
            continue
        if a.drawGraphMaybe(now):
            save = True
        if Projects.get(a.projectId) is None:
            Projects[a.projectId] = Project(a.projectId, "Not assigned", "No owner")
        Projects[a.projectId].addActim(a)
        Projects[a.projectId].repoSize += a.repoSize

    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

    with open(f"{HTML_DIR}/updated.html", "w") as updated:
        print(now.strftime(TIMEFORMAT_DISP), file=updated)

    htmlActimetres(now)
    htmlActiservers(now)
    htmlProjects(now)
    
def projectChangeInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
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

    with open(f"{HTML_DIR}/formActim.html") as form:
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", Actimetres[actimId].actimName())\
              .replace("{actimInfo}", Actimetres[actimId].htmlInfo())\
              .replace("{htmlProjectList}", htmlProjectList))

def removeProject(projectId):
    print("Content-type: text/html\n\n")

    actimList = ""
    if len(Projects[projectId].actimetreList) == 0:
        actimList = "(no Actimetres assigned to this project)\n"
    else:
        actimList = ""
        for a in [Actimetres[actimId] for actimId in Projects[projectId].actimetreList]:
            actimList += f'<li>{a.htmlCartouche()}</li>\n'
            
    with open(f"{HTML_DIR}/formRemove.html") as form:
        print(form.read()\
              .replace("{projectId}", str(projectId))\
              .replace("{projectTitle}", Projects[projectId].title)\
              .replace("{actimetreList}", actimList))

def retireActim(actimId):
    print("Content-type: text/html\n\n")

    a = Actimetres[actimId]
    if a.projectId > 0:
        ownerStr = 'the name of the owner'
    else:
        ownerStr = '"CONFIRM"'
    with open(f"{HTML_DIR}/formRetire.html") as form:
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", a.actimName())\
              .replace("{mac}", a.mac)\
              .replace("{boardType}", a.boardType)\
              .replace("{repoSize}", printSize(a.repoSize))\
              .replace("{owner}", ownerStr)\
              .replace("{projectTitle}", Projects[a.projectId].title))

now = datetime.utcnow()

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

def processForm(formId):
    if formId == 'project-change-info':
        projectId = int(args['projectId'][0])
        title = args['title'][0]
        owner = args['owner'][0]
        email = args['email'][0]
        printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")
        
        if title != "" and owner != "":
            Projects[projectId].title = title
            Projects[projectId].owner = owner
            Projects[projectId].email = email
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            htmlProjects(now)
        print("Location:\\index.html\n\n")

    elif formId == 'actim-change-project':
        actimId = int(args['actimId'][0])
        projectId = int(args['projectId'][0])
        oldProject = Actimetres[actimId].projectId
        printLog(f"Changing {actimId} from {oldProject} to {projectId}")

        Projects[oldProject].actimetreList.remove(actimId)
        Projects[projectId].actimetreList.add(actimId)
        Actimetres[actimId].projectId = projectId
        dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        htmlActimetres(now)
        htmlProjects(now)
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
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            htmlProjects(now)
        print("Location:\\index.html\n\n")

    elif formId == 'retire-actim':
        actimId = int(args['actimId'][0])
        owner = args['owner'][0]

        a = Actimetres.get(actimId)
        if a is not None and \
           (a.projectId == 0 and owner == 'CONFIRM') or \
           (Projects.get(a.projectId) is not None and Projects[a.projectId].owner == owner):
            
            printLog(f"Retire Actimetre{actimId:04d} from {Projects[a.projectId].title}")
            save = False
            for s in Actiservers.values():
                if actimId in s.actimetreList:
                    s.actimetreList.remove(actimId)
                    save = True
            if save:
                dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

            save = False
            for p in Projects.values():
                if actimId in p.actimetreList:
                    p.actimetreList.remove(actimId)
                    save = True
            if save:
                dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
                
            del Registry[Actimetres[actimId].mac]
            saveRegistry()
            del Actimetres[actimId]
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            try:
                os.remove(f"{HISTORY_DIR}/Actim{actimId:04d}.hist")
            except FileNotFoundError: pass
            htmlActimetres(now)
        print("Location:\\index.html\n\n")

    elif formId == 'remove-project':
        projectId = int(args['projectId'][0])
        if projectId != 0:
            for a in Projects[projectId].actimetreList:
                Actimetres[a].projectId = 0
            del Projects[projectId]
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            repoStats(now)
        print("Location:\\index.html\n\n")

    else:
        print("Location:\\index.html\n\n")
    
import argparse
cmdparser = argparse.ArgumentParser()
cmdparser.add_argument('action', default='', nargs='?')
cmdargs = cmdparser.parse_args()
if cmdargs.action == 'prepare-stats':
    repoStats(now)
    lock.close()
    sys.exit(0)

import urllib.parse
qs = os.environ['QUERY_STRING']
printLog(qs)

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
else:
    action = ''

if action == 'actiserver':
    serverId = int(args['serverId'][0])
    if serverId != 0:
        printLog(f"Actis{serverId} alive")
        thisServer = Actiserver(serverId).fromD(json.load(sys.stdin), actual=True)
        Actiservers[serverId] = thisServer
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        if thisServer.saveActim:
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    plain(json.dumps(Registry))

elif action == 'actimetre-new':
    mac       = args['mac'][0]
    boardType = args['boardType'][0]
    serverId  = int(args['serverId'][0])
    version   = args['version'][0]
    bootTime  = datetime.strptime(args['bootTime'][0], TIMEFORMAT_FN)

    thisServer = Actiservers.get(serverId)
    if thisServer is None:
        thisServer = Actiserver(serverId, lastReport=now)
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
        responseStr = f"+{actimId}"
    else:
        actimId = Registry[mac]
        printLog(f"Found known Actim{actimId:04d} for {mac}")
        responseStr = str(actimId)
        
    a = Actimetre(actimId, mac, boardType, version, serverId, bootTime=now, lastSeen=now, lastReport=now)
    printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")
    
    thisServer.actimetreList.add(actimId)
    Actimetres[actimId] = a
    dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
    plain(responseStr)

elif action == 'actimetre-off':
    serverId = int(args['serverId'][0])
    actimId = int(args['actimId'][0])

    a = Actimetres.get(actimId)
    if a is not None:
        a.addFreqEvent(now, 0)
        a.drawGraph(now)
        a.isDead = True
        Actiservers[serverId].actimetreList.remove(actimId)
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        if Projects.get(a.projectId) is not None \
           and Projects[a.projectId].email != "":
            sendEmail(now, Projects[a.projectId].email,\
                      f'{a.actimName()} died',\
                      f'{a.actimName()}\nType {a.boardType}\nMAC {a.mac}\n' +\
                      f'Connected to Actis{a.serverId:03d}\nSensors {a.sensorStr}\nRunning at {a.frequency}Hz\n' +\
                      f'Latest uptime {a.uptime(now)}\nMissing rate {a.rating:.3f}%\n' +\
                      f'Total data size {printSize(a.repoSize)}\n')
    plain("Ok")

elif action == 'actim-change-project':
    actimId = int(args['actimId'][0])
    actimChangeProject(actimId)

elif action == 'actim-cut-graph':
    actimId = int(args['actimId'][0])
    if Actimetres.get(actimId) is not None:
        save = False
        if Actimetres[actimId].graphSince == TIMEZERO:
            save = True
        Actimetres[actimId].cutHistory(None, now)
        Actimetres[actimId].drawGraph(now)
        if save:
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    print("Location:\\index.html\n\n")

elif action == 'retire-actim':
    actimId = int(args['actimId'][0])
    retireActim(actimId)

elif action == 'retire-server':
    serverId = int(args['serverId'][0])
    del Actiservers[serverId]
    dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
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

else:
    print("Location:\\index.html\n\n")

lock.close()

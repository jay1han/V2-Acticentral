#!/usr/bin/python3

import os, sys, json, fcntl
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError

from yattag import Doc, indent

LOG_SIZE_MAX    = 10_000_000
VERSION_STR     = "v390"
ADMIN_EMAIL     = "actimetre@gmail.com"
ADMINISTRATORS  = "/etc/actimetre/administrators"

TIMEFORMAT_UTC  = "%Y%m%d%H%M%S%z"
TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"
TIMEFORMAT_ALERT= "%Y/%m/%d %H:%M (UTC)"

REGISTRY        = "/etc/actimetre/registry.data"
REGISTRY_BACKUP = "/etc/actimetre/registry/backup."
ACTIMETRES      = "/etc/actimetre/actimetres.data"
ACTISERVERS     = "/etc/actimetre/actiservers.data"
LOG_FILE        = "/etc/actimetre/central.log"
PROJECTS        = "/etc/actimetre/projects.data"
LOCK_FILE       = "/etc/actimetre/acticentral.lock"
SECRET_FILE     = "/etc/actimetre/.secret"
STAT_FILE       = "/etc/actimetre/acticentral.stat"
HISTORY_DIR     = "/etc/actimetre/history"
REMOTE_FILE     = "/etc/actimetre/remotes.data"
IMAGES_DIR      = "/var/www/html/images"
IMAGES_INDEX    = "/var/www/html/images/index.txt"

HTML_DIR        = "/var/www/html"
INDEX_HTML      = "/var/www/html/index.html"
SERVERS_HTML    = "/var/www/html/servers.html"
CGI_BIN         = "acticentral.py"

INDEX_TEMPLATE  = "/var/www/html/template.html"
PROJECT_TEMPLATE= "/var/www/html/templateProject.html"
SERVERS_TEMPLATE= "/var/www/html/templateServers.html"
SECRET_KEY      = "YouDontKnowThis"

HTML_ACTIMETRES = ""
HTML_ACTISERVERS= ""
HTML_PROJECTS   = ""
LAST_UPDATED    = ""

ACTIM_ALERT1    = timedelta(minutes=5)
ACTIM_ALERT2    = timedelta(minutes=30)
ACTIS_ALERT1    = timedelta(minutes=5)
ACTIS_ALERT2    = timedelta(minutes=30)
ACTIS_ALERT3    = timedelta(hours=8)

ACTIS_FAIL_TIME = timedelta(seconds=60)
ACTIS_RETIRE_P  = timedelta(days=7)
ACTIS_HIDE_P    = timedelta(days=1)
ACTIM_RETIRE_P  = timedelta(days=1)
ACTIM_HIDE_P    = timedelta(days=1)

TIMEZERO        = datetime(year=2023, month=1, day=1, tzinfo=timezone.utc)
NOW             = datetime.now(timezone.utc)

def printLog(text=''):
    try:
        if os.stat(LOG_FILE).st_size > LOG_SIZE_MAX:
            os.truncate(LOG_FILE, 0)
    except OSError: pass
    with open(LOG_FILE, 'a') as logfile:
        print(f'[{NOW.strftime(TIMEFORMAT_DISP)}]', text, file=logfile)

def loadData(filename):
    try:
        registry = open(filename, "r")
    except OSError:
        return {}
    try:
        data = json.load(registry)
    except JSONDecodeError:
        data = {}
    registry.close()
    return data

def dumpData(filename, data):
    printLog(f"[DUMP {filename}]")
    try:
        os.truncate(filename, 0)
    except OSError:
        pass
    with open(filename, "r+") as registry:
        json.dump(data, registry)

def printSize(size, unit='', precision=0):
    if size == 0:
        return "0B"
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

def utcStrptime(string):
    return datetime.strptime(string.strip() + "+0000", TIMEFORMAT_UTC)

import subprocess

def sendEmail(recipient, subject, text):
    content = f"""\
Subject:{subject}
This alert triggered at {NOW.strftime(TIMEFORMAT_ALERT)}

{text}

-----------------------------------------------
For more information, please visit actimetre.fr
.
"""
    if recipient != "":
        result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", recipient],\
                                input = content, text=True, stderr=subprocess.STDOUT)
        printLog(f'Email sent to "{recipient}", sendmail returns {result.returncode}: {result.stdout}')
    else:
        try:
            admins = open(ADMINISTRATORS, "r")
        except OSError:
            result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", ADMIN_EMAIL],\
                                    input = content, text=True, stderr=subprocess.STDOUT)
            printLog(f'Email sent to "{ADMIN_EMAIL}", sendmail returns {result.returncode}: {result.stdout}')
        else:
            for email in admins:
                result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", email],\
                                        input = content, text=True, stderr=subprocess.STDOUT)
                printLog(f'Email sent to "{email}", sendmail returns {result.returncode}: {result.stdout}')
            admins.close()
                
lock = open(LOCK_FILE, "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)

with open(SECRET_FILE, "r") as secret:
    SECRET_KEY = secret.read().strip()

class Project:
    def __init__(self, projectId=0, title="", owner="", email="", actimetreList=set()):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.email         = email
        self.actimetreList = actimetreList
        self.repoNums      = 0
        self.repoSize      = 0

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'email'         : self.email,
                'repoNums'      : self.repoNums,
                'repoSize'      : self.repoSize,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId      = int(d['projectId'])
        self.title          = d['title']
        self.owner          = d['owner']
        if d.get('email'):
            self.email      = d['email']
        if d.get('repoNums'):
            self.repoNums   = int(d['repoNums'])
        self.repoSize       = int(d['repoSize'])
        if d.get('actimetreList') is not None:
            self.actimetreList = set([int(actimId) for actimId in d['actimetreList']])
        return self

    def addActim(self, actimId):
        if actimId not in self.actimetreList:
            self.actimetreList.add(actimId)
            return True
        else:
            return False

    def name(self):
        return f"{self.title} (#{self.projectId:02d})"
        
Projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
ProjectsTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)

def listProjects():
    for (projectId, p) in Projects.items():
        if len(p.actimetreList) > 0:
            print(f'{projectId}:', ','.join([str(a) for a in list(p.actimetreList)]))

REDRAW_TIME  = timedelta(minutes=5)
REDRAW_DEAD  = timedelta(minutes=30)
GRAPH_SPAN   = timedelta(days=7)
GRAPH_CULL   = timedelta(days=6)
FSCALETAG    = {50:5, 100:10}
FSCALEV3     = {100:3, 1000:5, 4000:8, 8000:10}
FSCALEV3TAG  = {100:3, 1000:5, 4000:8}

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='?', version="", serverId=0, isDead=0, isStopped=False,\
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,\
                 projectId = 0, sensorStr="", frequency = 0, rating = 0.0, rssi = 0,  repoNums = 0, repoSize = 0):
        self.actimId    = int(actimId)
        self.mac        = mac
        self.boardType  = boardType
        self.version    = version
        self.serverId   = int(serverId)
        self.isDead     = isDead
        self.isStopped  = isStopped
        self.bootTime   = bootTime
        self.lastSeen   = lastSeen
        self.lastReport = lastReport
        self.projectId  = projectId
        self.sensorStr  = sensorStr
        self.frequency  = frequency
        self.rating     = rating
        self.rssi       = rssi
        self.repoNums   = repoNums
        self.repoSize   = repoSize
        self.lastDrawn  = TIMEZERO
        self.graphSince = TIMEZERO
        self.reportStr  = ""

    def toD(self):       
        return {'actimId'   : self.actimId,
                'mac'       : self.mac,
                'boardType' : self.boardType,
                'version'   : self.version,
                'serverId'  : self.serverId,
                'isDead'    : int(self.isDead),
                'isStopped' : str(self.isStopped).upper(),
                'bootTime'  : self.bootTime.strftime(TIMEFORMAT_FN),
                'lastSeen'  : self.lastSeen.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'projectId' : self.projectId,
                'sensorStr' : self.sensorStr,
                'frequency' : self.frequency,
                'rating'    : self.rating,
                'rssi'      : str(self.rssi),
                'repoNums'  : self.repoNums,
                'repoSize'  : self.repoSize,
                'lastDrawn' : self.lastDrawn.strftime(TIMEFORMAT_FN),
                'graphSince': self.graphSince.strftime(TIMEFORMAT_FN),
                'reportStr' : self.reportStr,
                }

    def fromD(self, d):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.version    = d['version']
        self.serverId   = int(d['serverId'])
        if str(d['isDead']).isdecimal():
            self.isDead = int(d['isDead'])
        else:
            self.isDead = int(str(d['isDead']).strip().upper() == "TRUE")
        if d.get('isStopped') is not None:
            self.isStopped = (str(d['isStopped']).strip().upper() == "TRUE")
        else:
            self.isStopped = False
        self.bootTime   = utcStrptime(d['bootTime'])
        self.lastSeen   = utcStrptime(d['lastSeen'])
        self.lastReport = utcStrptime(d['lastReport'])
        self.sensorStr  = d['sensorStr']
        self.frequency  = int(d['frequency'])
        self.rating     = float(d['rating'])
        if d.get('rssi') is not None:
            self.rssi   = int(d['rssi'])
        if d.get('repoNums'):
            self.repoNums   = int(d['repoNums'])
        self.repoSize   = int(d['repoSize'])
        
        if d.get('projectId') is not None:
            self.projectId  = int(d['projectId'])
            for p in Projects.values():
                if self.actimId in p.actimetreList and p.projectId != self.projectId:
                    p.actimetreList.remove(self.actimId)
            if Projects.get(self.projectId) is None:
                self.projectId = 0
            else:
                Projects[self.projectId].actimetreList.add(self.actimId)
        else:
            for p in Projects.values():
                if self.actimId in p.actimetreList:
                    self.projectId = p.projectId
            
        if d.get('lastDrawn') is not None:
            self.lastDrawn = utcStrptime(d['lastDrawn'])
        if d.get('graphSince') is not None:
            self.graphSince = utcStrptime(d['graphSince'])
        if d.get('reportStr') is not None:
            self.reportStr = d['reportStr']
        else:
            self.reportStr = ""
        return self

    def cutHistory(self, cutLength=None):
        if cutLength is None:
            cutLength = NOW - self.bootTime
            
        historyFile = f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist"
        freshLines = list()
        try:
            with open(historyFile, "r") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                    if NOW - time <= cutLength:
                        time = NOW - cutLength
                        self.graphSince = time
                        freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                        freshLines.extend(history.readlines())
        except FileNotFoundError:
            pass
        else:
            if len(freshLines) == 0:
                time = NOW - cutLength
                self.graphSince = time
                freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{self.frequency}")

            os.truncate(historyFile, 0)
            with open(historyFile, "r+") as history:
                for line in freshLines:
                    print(line.strip(), file=history)

    def forgetData(self):
        self.isDead = 3
        self.repoNums = 0
        self.repoSize = 0
        s = Actiservers.get(self.serverId)
        if s is not None and self.actimId in s.actimetreList:
            s.actimetreList.remove(self.actimId)
        self.serverId = 0
        printLog(f"{self.actimName()} data forgotten")

    def scaleFreq(self, origFreq):
        if origFreq == 0:
            return 0
        if self.version >= "300":
            for limit, scale in FSCALEV3.items():
                if origFreq <= limit:
                    return scale
        else:
            return origFreq // 10

    def drawGraph(self):
        os.environ['MPLCONFIGDIR'] = "/etc/matplotlib"
        import matplotlib.pyplot as pyplot

        if NOW - self.graphSince >= GRAPH_SPAN:
            self.cutHistory(GRAPH_CULL)
            
        try:
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r") as history:
                self.graphSince = utcStrptime(history.readline().partition(':')[0])
        except (FileNotFoundError, ValueError):
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "w") as history:
                print(NOW.strftime(TIMEFORMAT_FN), ':', self.frequency, sep="", file=history)
            self.graphSince = NOW
            try:
                os.chmod(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", 0o666)
            except OSError:
                pass
                    
        timeline = []
        frequencies = []
        with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r") as history:
            for line in history:
                timeStr, part, freqStr = line.partition(':')
                time = utcStrptime(timeStr.strip())
                freq = self.scaleFreq(int(freqStr))
                if len(timeline) == 0 or freq != frequencies[-1]:
                    timeline.append(time)
                    frequencies.append(freq)

        timeline.append(NOW)
        frequencies.append(self.scaleFreq(self.frequency))
        freq = [self.scaleFreq(self.frequency) for i in range(len(timeline))]

        fig, ax = pyplot.subplots(figsize=(5.0,1.0), dpi=50.0)
        ax.set_axis_off()
        ax.set_ylim(bottom=-1, top=12)
        ax.axvline(timeline[0], 0, 0.95, lw=1.0, c="blue", marker="^", markevery=[1], ms=5.0, mfc="blue")
        if self.version >= "300":
            fscale = FSCALEV3TAG
        else:
            fscale = FSCALETAG
        for real, drawn in fscale.items():
            if self.frequency == real:
                c = 'green'
                w = 'bold'
            else:
                c = 'black'
                w = 'regular'
            if real >= 1000:
                real = f" {real // 1000 :2d}k"
            else:
                real = f" {real:3d}"
            ax.text(NOW, drawn, real, family="sans-serif", stretch="condensed", ha="left", va="center", c=c, weight=w)
            
        ax.plot(timeline, frequencies, ds="steps-post", c="black", lw=1.0, solid_joinstyle="miter")
        if self.isDead > 0 or self.frequency == 0:
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
        updateMap[self.actimId] = NOW.strftime(TIMEFORMAT_FN)
        dataMap[self.actimId] = f'{self.boardType},{self.serverId},{self.sensorStr},{self.frequency},{self.rating}'
        os.truncate(IMAGES_INDEX, 0)
        with open(IMAGES_INDEX, "r+") as index:
            for actimId in updateMap.keys():
                print(f'{actimId}:{updateMap[actimId]}:{dataMap[actimId]}', file=index)
        printLog(f'{self.actimName()}.drawGraph --> ' + ','.join(map(str, updateMap.keys())))
        
        self.lastDrawn = NOW

    def drawGraphMaybe(self):
        redraw = False
        if self.isDead > 0:
            if NOW - self.lastDrawn > REDRAW_DEAD:
                redraw = True
        else:
            if NOW - self.lastDrawn > REDRAW_TIME:
                redraw = True
        if redraw:
            self.drawGraph()
        return redraw

    def addFreqEvent(self, now, frequency):
        try:
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "r+") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                if now < time: now = time
                if frequency != freq:
                    print(now.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)
        except FileNotFoundError:
            with open(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", "w") as history:
                print(now.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)                
            self.graphSince = now
            try:
                os.chmod(f"{HISTORY_DIR}/Actim{self.actimId:04d}.hist", 0o666)
            except OSError:
                pass
            
    def update(self, newActim, actual=False):
        redraw = False
        if actual:
            s = Actiservers.get(self.serverId)
            if self.serverId != newActim.serverId:
                if s is not None and self.actimId in s.actimetreList:
                    s.actimetreList.remove(self.actimId)
                if self.frequency > 0:
                    if s is not None:
                        self.addFreqEvent(s.lastUpdate, 0)
                    else:
                        self.addFreqEvent(newActim.bootTime, 0)
                    self.frequency = 0
                redraw = True
            if self.bootTime != newActim.bootTime:
                self.addFreqEvent(newActim.bootTime, 0)
                self.frequency = 0
                redraw = True
            if self.frequency != newActim.frequency:
                self.addFreqEvent(NOW, newActim.frequency)
                self.frequency  = newActim.frequency
                redraw = True
            if newActim.isDead == 0:
                self.isDead = 0
            self.isStopped = newActim.isStopped

        if newActim.boardType != "":
            self.boardType  = newActim.boardType
        if newActim.version != "":
            self.version    = newActim.version
        self.sensorStr  = newActim.sensorStr
        self.serverId   = newActim.serverId
        self.bootTime   = newActim.bootTime
        self.lastSeen   = newActim.lastSeen
        self.lastReport = newActim.lastReport
        self.rating     = newActim.rating
        self.rssi       = newActim.rssi
        self.repoNums   = newActim.repoNums
        self.repoSize   = newActim.repoSize
        
        if redraw:
            self.drawGraph()
        return redraw

    def alert(self):
        printLog(f'Alert {self.actimName()}')
        subject = f'{self.actimName()} unreachable since {self.lastSeen.strftime(TIMEFORMAT_ALERT)}'
        content = f'{self.actimName()}\n'
        if Projects.get(self.projectId) is not None:
            content += f'Project "{Projects[self.projectId].name()}"\n'
        content += f'Type {self.boardType}\nMAC {self.mac}\n' +\
            f'Sensors {self.sensorStr}\n' +\
            f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' +\
            f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'
        
        if Projects.get(self.projectId) is not None \
           and Projects[self.projectId].email != "":
            sendEmail(Projects[self.projectId].email, subject, content)
        sendEmail("", subject, content)

    def alertDisk(self):
        printLog(f"{self.actimName()}'s server disk low")
        subject = f"{self.actimName()}'s server disk low"
        content = f'{self.actimName()}\n'
        if Projects.get(self.projectId) is not None:
            content += f'Project "{Projects[self.projectId].name()}"\n'
        content += f'Type {self.boardType}\nMAC {self.mac}\n' +\
            f'Sensors {self.sensorStr}\n' +\
            f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' +\
            f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'
        if Actiservers.get(self.serverId) is not None:
            s = Actiservers[self.serverId]
            content += f'{s.serverName()}\n' +\
            f'Hardware {s.machine}\nVersion {s.version}\n' +\
            f'IP {s.ip}\nChannel {s.channel}\n' +\
            f'Disk size {printSize(s.diskSize)}, free {printSize(s.diskFree)} ' +\
            f'({100.0 * s.diskFree / s.diskSize :.1f}%)\n' +\
            f'Last seen {s.lastUpdate.strftime(TIMEFORMAT_DISP)}\n'
        content += '\n'
        
        if Projects.get(self.projectId) is not None \
           and Projects[self.projectId].email != "":
            sendEmail(Projects[self.projectId].email, subject, content)
        else:
            sendEmail("", subject, content)
        
    def dies(self):
        if self.isDead == 0:
            printLog(f'{self.actimName()} dies {NOW.strftime(TIMEFORMAT_DISP)}')
            self.frequency = 0
            self.isDead = 1
            self.addFreqEvent(NOW, 0)
            self.drawGraph()

    def actimName(self):
        return f"Actim{self.actimId:04d}"

    def htmlInfo(self):
        if self.isDead > 0 or self.frequency == 0:
            return f'<span class="down">(dead)</span>'
        elif self.isStopped:
            return f'({self.sensorStr})'
        else:
            return f'{self.sensorStr}@{self.frequencyText()}'
        
    def htmlCartouche(self):
        return f'{self.actimName()}&nbsp;<span class="small">{self.htmlInfo()}</span> '

    def frequencyText(self, sensorStr = None):
        if self.isDead > 0 or self.frequency == 0:
            if sensorStr is not None:
                return f"({sensorStr})<br>dead"
            else:
                return "(dead)"
        else:
            if self.frequency >= 1000:
                text = f"{self.frequency // 1000}kHz"
            else:
                text = f"{self.frequency}Hz"
            if sensorStr is not None:
                return f"{sensorStr}<br>{text}"
            else:
                return text
    
    def uptime(self):
        if self.isDead > 0 or self.frequency == 0:
            up = NOW - self.lastReport
        else:
            up = NOW - self.bootTime
        days = up // timedelta(days=1)
        hours = (up % timedelta(days=1)) // timedelta(hours=1)
        minutes = (up % timedelta(hours=1)) // timedelta(minutes=1)
        if up > timedelta(days=1):
            return f'{days}d{hours}h'
        else:
            return f'{hours}h{minutes:02d}m'

    def hasData(self):
        return self.repoNums > 0 or self.repoSize > 0
        
Actimetres  = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000", channel=0, ip = "0.0.0.0", isLocal = False,\
                 isDown = 0, lastUpdate=TIMEZERO, dbTime=TIMEZERO, actimetreList=set()):
        self.serverId   = int(serverId)
        self.machine    = machine
        self.version    = version
        self.channel    = int(channel)
        self.ip         = ip
        self.isLocal    = isLocal
        self.diskSize   = 0
        self.diskFree   = 0
        self.lastUpdate = lastUpdate
        self.dbTime     = dbTime
        self.isDown     = isDown
        self.actimetreList = actimetreList
        self.diskLow    = 0
        self.cpuIdle    = 0.0
        self.memAvail   = 0.0
        self.diskTput   = 0.0
        self.diskUtil   = 0.0

    def toD(self):
        return {'serverId'  : self.serverId,
                'machine'   : self.machine,
                'version'   : self.version,
                'channel'   : self.channel,
                'ip'        : self.ip,
                'isLocal'   : self.isLocal,
                'diskSize'  : self.diskSize,
                'diskFree'  : self.diskFree,
                'diskLow'   : self.diskLow,
                'lastUpdate': self.lastUpdate.strftime(TIMEFORMAT_FN),
                'dbTime'    : self.dbTime.strftime(TIMEFORMAT_FN),
                'isDown'    : self.isDown,
                'actimetreList': '[' + ','.join([json.dumps(Actimetres[actimId].toD()) for actimId in self.actimetreList]) + ']',
                'cpuIdle'   : self.cpuIdle,
                'memAvail'  : self.memAvail,
                'diskTput'  : self.diskTput,
                'diskUtil'  : self.diskUtil,
                }

    def fromD(self, d, actual=False):
        self.serverId   = int(d['serverId'])
        self.machine    = d['machine']
        self.version    = d['version']
        self.channel    = int(d['channel'])
        self.ip         = d['ip']
        if d.get('isLocal'):
            self.isLocal = (str(d['isLocal']).strip().upper() == "TRUE")
        if d.get('diskSize'):
            self.diskSize = int(d['diskSize'])
            self.diskFree = int(d['diskFree'])
        self.actimetreList = set()
        if d['actimetreList'] != "[]":
            for actimData in json.loads(d['actimetreList']):
                a = Actimetre().fromD(actimData)
                if Actimetres.get(a.actimId) is None:
                    Actimetres[a.actimId] = a
                else:
                    Actimetres[a.actimId].update(a, actual)
                self.actimetreList.add(a.actimId)
        else:
            self.actimetreList = set()
        for a in Actimetres.values():
            if a.serverId == self.serverId and not a.actimId in self.actimetreList:
                a.dies()
        if d.get('lastUpdate'):
            self.lastUpdate = utcStrptime(d['lastUpdate'])
        else:
            self.lastUpdate = utcStrptime(d['lastReport'])
        if d.get('dbTime'):
            self.dbTime = utcStrptime(d['dbTime'])
        if d.get('isDown'):
            self.isDown = int(d['isDown'])
        else:
            if NOW - self.lastUpdate < ACTIS_ALERT3:
                self.isDown = 0
            else:
                self.isDown = 3
        if d.get('diskLow') is None:
            self.diskLow = 0
        elif d['diskLow'] == False:
            self.diskLow = 0
        elif d['diskLow'] == True:
            self.diskLow = 1
        else:
            self.diskLow = d['diskLow']
            
        if d.get('cpuIdle')  is not None: self.cpuIdle  = float(d['cpuIdle'])
        if d.get('memAvail') is not None: self.memAvail = float(d['memAvail'])
        if d.get('diskTput') is not None: self.diskTput = float(d['diskTput'])
        if d.get('diskUtil') is not None: self.diskUtil = float(d['diskUtil'])
            
        return self

    def serverName(self):
        return f"Actis{self.serverId:03d}"

    def removeActimetres(self):
        removed = False
        for actimId in self.actimetreList.copy():
            a = Actimetres.get(actimId)
            if a is not None:
                if a.serverId == self.serverId and a.isDead == 0:
                    a.dies()
                self.actimetreList.remove(actimId)
                removed = True
        return removed

    def alert(self):
        printLog(f'Alert {self.serverName()}')
        subject = f'{self.serverName()} unreachable since {self.lastUpdate.strftime(TIMEFORMAT_ALERT)}'
        content = f'{self.serverName()}\n' +\
            f'Hardware {self.machine}\nVersion {self.version}\n' +\
            f'IP {self.ip}\nChannel {self.channel}\n' +\
            f'Disk size {printSize(self.diskSize)}, free {printSize(self.diskFree)} ' +\
            f'Last seen {self.lastUpdate.strftime(TIMEFORMAT_DISP)}\n' +\
            f'Last known Actimetres:\n    '
        for actimId in self.actimetreList:
            content += f'Actim{actimId:04d} '
        content += '\n'
        
        sendEmail("", subject, content)

    def alertDisk(self):
        printLog(f'{self.serverName()} disk low')
        subject = f'{self.serverName()} storage low'
        content = f'{self.serverName()}\n' +\
            f'Hardware {self.machine}\nVersion {self.version}\n' +\
            f'IP {self.ip}\nChannel {self.channel}\n' +\
            f'Disk size {printSize(self.diskSize)}, free {printSize(self.diskFree)} ' +\
            f'Last seen {self.lastUpdate.strftime(TIMEFORMAT_DISP)}\n' +\
            f'Last known Actimetres:\n    '
        for actimId in self.actimetreList:
            content += f'Actim{actimId:04d} '
            if Actimetres.get(actimId) is not None:
                Actimetres[actimId].alertDisk()
        content += '\n'
        
        sendEmail("", subject, content)
    
Actiservers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}

import shutil
def saveRegistry():
    registryBackup = REGISTRY_BACKUP + datetime.now().strftime(TIMEFORMAT_FN)
    try:
        shutil.copyfile(REGISTRY, registryBackup)
    except OSError:
        pass
    
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
RegistryTime = datetime.fromtimestamp(os.stat(REGISTRY).st_mtime, tz=timezone.utc)
    
if Projects.get(0) is None:
    Projects[0] = Project(0, "Not assigned", "No owner")
    dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

def htmlRssi(rssi):
    doc, tag, text, line = Doc().ttl()
    
    widthFull = 100.0 * rssi / 7
    widthEmpty = 100.0 - widthFull
    with tag('table', klass='rssi'):
        with tag('tr'):
            if rssi == 0:
                line('td', '?', klass='small')
            else:
                if   rssi < 3: color = 'weak'
                elif rssi > 5: color = 'best'
                else         : color = 'good'
                line('td', ' ', width=f'{widthFull}%', klass=color)
                line('td', ' ', width=f'{widthEmpty}%')
    return doc.getvalue()

def htmlActimetre1(actimId):
    if Actimetres.get(actimId) is None:
        return ""
    
    a = Actimetres[actimId]
    if a.serverId != 0:
        s = Actiservers.get(a.serverId)
    doc, tag, text, line = Doc().ttl()
    with tag('tr'):
        doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
        doc.asis(f'<input type="hidden" name="actimId" value="{a.actimId}"/>')
        alive = 'up'
        if NOW - a.lastReport > ACTIM_RETIRE_P:
            alive = 'retire'
        elif a.frequency == 0 or a.isDead > 0:
            alive = 'down'

        with tag('td', klass=alive):
            doc.asis('Actim&shy;{:04d}'.format(actimId))
            if a.version >= '301' and alive == 'up' and \
               (Actiservers.get(a.serverId) is not None and Actiservers[a.serverId].version >= '301') :
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='remote-restart'):
                    text('Reboot')
        with tag('td'):
            text(a.boardType)
            doc.asis('<br>')
            text(f"v{a.version}")
        if a.serverId != 0:
            if s is not None and s.isDown == 0:
                line('td', f"Actis{a.serverId:03d}")
            else:
                line('td', f"Actis{a.serverId:03d}", klass="down")
        else:
            line('td', "")
        with tag('td'):
            doc.asis(a.frequencyText(a.sensorStr))
            if a.version >= '301' and alive == 'up' and \
               (Actiservers.get(a.serverId) is not None and Actiservers[a.serverId].version >= '301') :
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='remote-button'):
                    text('Button')
        if alive == 'up':
            with tag('td'):
                doc.asis(htmlRssi(a.rssi))
                doc.stag('br')
                if a.isStopped:
                    text('stopped')
                else:
                    text("{:.3f}%".format(100.0 * a.rating))
        else: 
            line('td', "")

        if alive == 'retire':
            line('td', 'No data', klass=f'health retire')
        else:
            with tag('td', klass=f'health left'):
                if a.graphSince == TIMEZERO:
                    text('? ')
                else:
                    text(a.graphSince.strftime(TIMEFORMAT_DISP) + "\n")
                doc.asis('<button type="submit" name="action" value="actim-cut-graph">&#x2702;</button>\n')
                line('span', f' {a.uptime()}', klass=alive)
                with tag('div'):
                    doc.stag('img', src=f'/images/Actim{actimId:04d}.svg', klass='health')

        with tag('td', klass='right'):
            if not a.hasData():
                text('No data')
            else:
                text(f'{a.repoNums} files')
                doc.stag('br')
                text(printSize(a.repoSize))
            if a.serverId == 0 or not a.hasData():
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='actim-change-project'):
                    doc.asis('Move')
            elif alive == 'up' and a.hasData() and \
               (Actiservers.get(a.serverId) is not None and Actiservers[a.serverId].version >= '380'):
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='actim-stop'):
                    doc.asis('Stop')
            elif alive != 'up' and a.hasData() and s is not None and s.isDown == 0:
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='actim-sync'):
                    text('Sync')
            elif alive == 'retire' and a.hasData():
                doc.asis('<br>')
                with tag('button', type='submit', name='action', value='actim-forget'):
                    doc.asis('Forget')
        if a.reportStr != "":
            with tag('td', klass="report"):
                text(a.reportStr)
                doc.asis('<br><button type="submit" name="action" value="clear-report">Clear</button>\n')
        doc.asis('</form>\n')
    return indent(doc.getvalue())

def htmlActimetres():
    doc, tag, text, line = Doc().ttl()

    for actimId in sorted(Actimetres.keys()):
        a = Actimetres[actimId]
        if NOW - a.lastReport > ACTIM_HIDE_P:
            continue
        with tag('tr'):
            doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
            doc.asis(f'<input type="hidden" name="actimId" value="{actimId}"/>')
            alive = 'up'
            if a.frequency == 0 or a.isDead > 0:
                alive = 'down'
            elif Actiservers.get(a.serverId) is None or NOW - Actiservers[a.serverId].lastUpdate > ACTIS_FAIL_TIME:
                alive = 'unknown'

            with tag('td', ('data-comparator', f'{actimId :04d}'), klass=alive):
                doc.asis('Actim&shy;{:04d}<br>'.format(actimId))
            with tag('td'):
                text(a.boardType)
                doc.asis('<br>\n')
                text(f"v{a.version}")
            if a.serverId != 0:
                line('td', f"Actis{a.serverId:03d}")
            else:
                line('td', "")
            with tag('td'):
                doc.asis(a.frequencyText(a.sensorStr))
            if alive == 'up':
                with tag('td'):
                    doc.asis(htmlRssi(a.rssi))
                    doc.stag('br')
                    if a.isStopped:
                        text('stopped')
                    else:
                        text("{:.3f}%".format(100.0 * a.rating))
            else: 
                line('td', "")

            with tag('td', klass=f'health left'):
                if a.graphSince == TIMEZERO:
                    text('? ')
                else:
                    text(a.graphSince.strftime(TIMEFORMAT_DISP) + "\n")
                doc.asis('<button type="submit" name="action" value="actim-cut-graph">&#x2702;</button>\n')
                line('span', f' {a.uptime()}', klass=alive)
                with tag('div'):
                    doc.stag('img', src=f'/images/Actim{actimId:04d}.svg', klass='health')

            with tag('td', ('data-comparator', Projects[a.projectId].projectId), klass='left'):
                with tag('a', href=f'/project{a.projectId:02d}.html'):
                    text(Projects[a.projectId].name())
            with tag('td', ('data-comparator', f'{a.repoSize // 1000000 :06d}'), klass='right'):
                if a.repoNums == 0:
                    text('No data')
                else:
                    text(f'{a.repoNums} files')
                    doc.stag('br')
                    text(printSize(a.repoSize))
            if a.reportStr != "":
                with tag('td', klass="report"):
                    text(a.reportStr)
                    doc.asis('<br><button type="submit" name="action" value="clear-report">Clear</button>\n')
            doc.asis('</form>\n')

    global HTML_ACTIMETRES
    HTML_ACTIMETRES = indent(doc.getvalue())

def htmlActiservers():
    doc, tag, text, line = Doc().ttl()

    modServers = False
    for serverId in sorted(Actiservers.keys()):
        s = Actiservers[serverId]
        if NOW - s.lastUpdate > ACTIM_HIDE_P:
            continue
        with tag('tr'):
            doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
            doc.asis(f'<input type="hidden" name="serverId" value="{s.serverId}" />')
            if NOW - s.lastUpdate < ACTIS_FAIL_TIME:
                alive = 'up'
            elif NOW - s.lastUpdate > ACTIS_RETIRE_P:
                alive = 'retire'
            else:
                alive = 'down'

            with tag('td', klass=alive):
                text(s.serverName())
                doc.asis('<br>')
                line('span', s.ip, klass='small')
#                if alive == 'retire':
#                    line('button', 'Retire', type='submit', name='action', value='retire-server')
            line('td', s.machine)
            with tag('td'):
                if alive == 'up':
                    text(f"v{s.version}")
                    doc.asis("<br>")
                    if s.channel != 0:
                        text(f"Ch. {s.channel}")
                else:
                    text("?")
            if s.lastUpdate == TIMEZERO:
                line('td', "?", klass=alive)
            else:
                line('td', s.lastUpdate.strftime(TIMEFORMAT_DISP), klass=alive)
            if alive != 'up':
                line('td', '')
                line('td', "None")
                line('td', '')
                line('td', '')
            else:
                with tag('td', klass='no-padding'):
                    if s.version >= "370":
                        with tag('table'):
                            with tag('tr'):
                                with tag('td', klass='left-tight'):
                                    text('CPU')
                                    doc.asis('<br>')
                                    text('RAM')
                                    doc.asis('<br>')
                                    text('Disk')
                                with tag('td', klass='left-tight'):
                                    text(f'{s.cpuIdle:.1f}% idle')
                                    doc.asis('<br>')
                                    text(f'{s.memAvail:.1f}% free')
                                    doc.asis('<br>')
                                    text(f'{s.diskTput:.0f}kB/s({s.diskUtil:.1f}%)')
                    else: text('')
                with tag('td', klass='left'):
                    for actimId in s.actimetreList:
                        with tag('div'):
                            doc.asis(Actimetres[actimId].htmlCartouche())
                if s.isLocal:
                    with tag('td', klass='right'):
                        for actimId in s.actimetreList:
                            a = Actimetres[actimId]
                            with tag('div'):
                                if a.repoNums == 0:
                                    text('(No data)')
                                else:
                                    if s.version >= "345":
                                        link = f'http://{s.ip}/Project{a.projectId:02d}/index{a.actimId:04d}.html'
                                    else:
                                        link = f'http://{s.ip}/index{a.actimId:04d}.html'
                                    with tag('a', href=link):
                                        doc.asis(f'{a.repoNums}&nbsp;/&nbsp;{printSize(a.repoSize)}')
                    if s.diskSize > 0:
                        diskState = ''
                        if s.diskFree < s.diskSize // 10:
                            diskState = 'disk-low'
                        line('td', f'{printSize(s.diskFree)} ({100.0*s.diskFree/s.diskSize:.1f}%)', klass=diskState)
                    else:
                        line('td', '')
                else:
                    line('td', '')
                    line('td', '')
                
    global HTML_ACTISERVERS
    HTML_ACTISERVERS = indent(doc.getvalue())
    
    if modServers:
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

def htmlAllServers():
    doc, tag, text, line = Doc().ttl()

    modServers = False
    for serverId in sorted(Actiservers.keys()):
        s = Actiservers[serverId]
        with tag('tr'):
            doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
            doc.asis(f'<input type="hidden" name="serverId" value="{s.serverId}" />')
            if NOW - s.lastUpdate < ACTIS_FAIL_TIME:
                alive = 'up'
            elif NOW - s.lastUpdate > ACTIS_RETIRE_P:
                alive = 'retire'
            elif NOW - s.lastUpdate > ACTIM_HIDE_P:
                alive = 'hidden'
            else:
                alive = 'down'

            with tag('td', klass=alive):
                text(s.serverName())
                doc.asis('<br>')
                line('span', s.ip, klass='small')
#                if alive == 'retire':
#                    line('button', 'Retire', type='submit', name='action', value='retire-server')
            line('td', s.machine)
            with tag('td'):
                if alive == 'up':
                    text(f"v{s.version}")
                    doc.asis("<br>")
                    if s.channel != 0:
                        text(f"Ch. {s.channel}")
                else:
                    text("?")
            if s.lastUpdate == TIMEZERO:
                line('td', "?", klass=alive)
            else:
                line('td', s.lastUpdate.strftime(TIMEFORMAT_DISP), klass=alive)
            with tag('td', klass='no-padding'):
                if s.version >= "370":
                    with tag('table'):
                        with tag('tr'):
                            with tag('td', klass='left-tight'):
                                text('CPU')
                                doc.asis('<br>')
                                text('RAM')
                                doc.asis('<br>')
                                text('Disk')
                            with tag('td', klass='left-tight'):
                                text(f'{s.cpuIdle:.1f}% idle')
                                doc.asis('<br>')
                                text(f'{s.memAvail:.1f}% free')
                                doc.asis('<br>')
                                text(f'{s.diskTput:.0f}kB/s({s.diskUtil:.1f}%)')
                else: text('')
            with tag('td', klass='left'):
                for actimId in s.actimetreList:
                    with tag('div'):
                        doc.asis(Actimetres[actimId].htmlCartouche())
            if s.isLocal:
                with tag('td', klass='right'):
                    for actimId in s.actimetreList:
                        a = Actimetres[actimId]
                        with tag('div'):
                            if not a.hasData():
                                doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
                                doc.asis(f'<input type="hidden" name="actimId" value="{a.actimId}"/>')
                                doc.asis(f'<input type="hidden" name="serverId" value="{s.serverId}"/>')
                                with tag('button', type='submit', name='action', value='actim-decouple'):
                                    doc.asis('Remove')
                                doc.asis('</form>')
                            else:
                                if s.version >= "345":
                                    link = f'http://{s.ip}/Project{a.projectId:02d}/index{a.actimId:04d}.html'
                                else:
                                    link = f'http://{s.ip}/index{a.actimId:04d}.html'
                                with tag('a', href=link):
                                    doc.asis(f'{a.repoNums}&nbsp;/&nbsp;{printSize(a.repoSize)}')
                if s.diskSize > 0:
                    diskState = ''
                    if s.diskFree < s.diskSize // 10:
                        diskState = 'disk-low'
                    line('td', f'{printSize(s.diskFree)} ({100.0*s.diskFree/s.diskSize:.1f}%)', klass=diskState)
                else:
                    line('td', '')
            else:
                line('td', '')
                line('td', '')

    if modServers:
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

    with open(SERVERS_HTML, "w") as html:
        with open(SERVERS_TEMPLATE, "r") as template:
            print(template.read() \
                  .replace("{Actiservers}", indent(doc.getvalue())) \
                  .replace("{Updated}", LAST_UPDATED)\
                  , file=html)
    
def htmlProjects():
    for projectId in Projects.keys():
        p = Projects[projectId]
        projectActimHTML = ""
        for actimId in p.actimetreList:
            projectActimHTML += htmlActimetre1(actimId)
        if projectId == 0:
            buttons = ""
        else:
            buttons = '''\
                      <button type="submit" name="action" value="project-edit-info">Edit info</button>
                      <button type="submit" name="action" value="remove-project">Remove project</button>
                      '''

        if projectId == 0:
            projectOwner = ""
            projectEmail = ""
        else:
            projectOwner = f"<h3>Project Owner: {p.owner}</h3>"
            projectEmail = f"<h3>Email: {p.email}</h3>"
            
        with open(f"{HTML_DIR}/project{projectId:02d}.html", "w") as html:
            with open(PROJECT_TEMPLATE, "r") as template:
                print(template.read()\
                      .replace("{buttons}", buttons)\
                      .replace("{projectTitle}", p.name())\
                      .replace("{projectOwner}", projectOwner)\
                      .replace("{projectEmail}", projectEmail)\
                      .replace("{projectActimHTML}", projectActimHTML)\
                      .replace("{projectId}", str(projectId)) \
                      .replace("{Updated}", LAST_UPDATED)\
                      , file=html)
        try:
            os.chmod(f"{HTML_DIR}/project{projectId:02d}.html", 0o777)
        except OSError:
            pass

    doc, tag, text, line = Doc().ttl()
    for projectId in sorted(Projects.keys()):
        p = Projects[projectId]
        with tag('tr'):
            with tag('td', klass='left'):
                with tag('a', href=f'/project{projectId:02d}.html'):
                    text(p.name())
            if projectId == 0:
                line('td', '')
                with tag('td'):
                    with tag('a', href=f'/project{projectId:02d}.html'):
                        text('List')
            else:
                line('td', p.owner)
                with tag('td', klass='left'):
                    for actimId in p.actimetreList:
                        if Actimetres.get(actimId) is not None:
                            with tag('div'):
                                doc.asis(Actimetres[actimId].htmlCartouche())

    global HTML_PROJECTS
    HTML_PROJECTS = indent(doc.getvalue())

def htmlUpdate():
    global LAST_UPDATED
    LAST_UPDATED = NOW.strftime(TIMEFORMAT_DISP)
    
    htmlActimetres()
    htmlActiservers()
    htmlProjects()
    htmlAllServers()
    
    htmlTemplate = open(INDEX_TEMPLATE, "r").read()
    htmlOutput = htmlTemplate\
        .replace("{Actimetres}", HTML_ACTIMETRES)\
        .replace("{Actiservers}", HTML_ACTISERVERS)\
        .replace("{Projects}", HTML_PROJECTS)\
        .replace("{Updated}", LAST_UPDATED)\
        .replace("{Version}", VERSION_STR)\
        .replace("{cgi-bin}", CGI_BIN)
    
    os.truncate(INDEX_HTML, 0)
    with open(INDEX_HTML, "r+") as html:
        print(htmlOutput, file=html)

def checkAlerts():
    save = False
    for a in Actimetres.values():
        if a.isDead == 1 and (NOW - a.lastSeen) > ACTIM_ALERT1:
            a.alert()
            a.isDead = 2
            save = True
        elif a.isDead == 2 and (NOW - a.lastSeen) > ACTIM_ALERT2:
            a.alert()
            a.isDead = 3
            save = True
    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})

    save = False
    for s in Actiservers.values():
        if s.isDown == 0 and (NOW - s.lastUpdate) > ACTIS_ALERT1:
            s.alert()
            s.isDown = 1
            save = True
        elif s.isDown == 1 and (NOW - s.lastUpdate) > ACTIS_ALERT2:
            s.alert()
            s.isDown = 2
            save = True
        elif s.isDown == 2 and (NOW - s.lastUpdate) > ACTIS_ALERT3:
            s.alert()
            s.isDown = 3
            save = True
    if save:
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

def repoStats():
    for p in Projects.values():
        p.repoSize = 0
        p.repoNums = 0

    save = False
    saveP = False
    for a in Actimetres.values():
        if NOW - a.lastReport > ACTIM_HIDE_P:
            continue
        if a.drawGraphMaybe():
            save = True
        if Projects.get(a.projectId) is None:
            Projects[a.projectId] = Project(a.projectId, "Not assigned", "No owner")
            saveP = True
        saveP = Projects[a.projectId].addActim(a.actimId)
        Projects[a.projectId].repoNums += a.repoNums
        Projects[a.projectId].repoSize += a.repoSize

    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    if saveP:
        dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

    with open(STAT_FILE, "w") as stat:
        stat.write(NOW.strftime(TIMEFORMAT_DISP))

    htmlUpdate()
    
def projectChangeInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-change-info")\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{projectOwner}", Projects[projectId].owner)\
              .replace("{projectId}", str(projectId)))

def projectEditInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-edit-info")\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{projectOwner}", Projects[projectId].owner)\
              .replace("{projectId}", str(projectId)))

def actimChangeProject(actimId):
    print("Content-type: text/html\n\n")

    htmlProjectList = ""
    for p in Projects.values():
        htmlProjectList += f'<input id="{p.projectId}" type="radio" name="projectId" value="{p.projectId}"'
        if p.projectId == Actimetres[actimId].projectId:
            htmlProjectList += ' checked="true"'
        htmlProjectList += f'><label for="{p.projectId}">{p.name()} ({p.owner})</label><br>\n'

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
        for actimId in Projects[projectId].actimetreList:
            if Actimetres.get(actimId) is not None:
                actimList += f'<li>{Actimetres[actimId].htmlCartouche()}</li>\n'
            
    with open(f"{HTML_DIR}/formRemove.html") as form:
        print(form.read()\
              .replace("{projectId}", str(projectId))\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{actimetreList}", actimList))

def retireActim(actimId):
    print("Content-type: text/html\n\n")

    a = Actimetres[actimId]
    if a.projectId > 0:
        ownerStr = 'the name of the owner'
    else:
        ownerStr = '"CONFIRM"'
    with open(f"{HTML_DIR}/formRetire.html") as form:
        repoNumsStr = ''
        if a.repoNums > 0:
            repoNumsStr = f'{a.repoNums} files, '
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", a.actimName())\
              .replace("{mac}", a.mac)\
              .replace("{boardType}", a.boardType)\
              .replace("{repoNums}", repoNumsStr)\
              .replace("{repoSize}", printSize(a.repoSize))\
              .replace("{owner}", ownerStr)\
              .replace("{projectTitle}", Projects[a.projectId].name()))

def loadRemotes():
    try:
        remoteFile = open(REMOTE_FILE, "r")
    except OSError:
        return {}
    try:
        remoteJson = json.load(remoteFile)
    except json.JSONDecodeError:
        return {}
    remote = {}
    for (key, value) in remoteJson.items():
        remote[int(key)] = int(value)
    return remote

def saveRemotes(remote):
    try:
        os.truncate(REMOTE_FILE, 0)
    except OSError:
        return
    with open(REMOTE_FILE, "r+") as remoteFile:
        json.dump(remote, remoteFile)
        
def remoteAction(actimId, command):
    remotes = loadRemotes()
    remotes[actimId] = command
    saveRemotes(remotes)

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

def processForm(formId):
    password = args['password'][0]
    if password != SECRET_KEY:
        print("Location:\\password.html\n\n")
        return
    
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
            htmlUpdate()
        print(f'Location:\\index.html\n\n')

    elif formId == 'project-edit-info':
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
            htmlUpdate()
        print(f"Location:\\project{projectId:02d}.html\n\n")

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
        htmlUpdate()
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
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif formId == 'retire-actim':
        actimId = int(args['actimId'][0])
        owner = args['owner'][0]

        a = Actimetres.get(actimId)
        if a is not None and \
           (a.projectId == 0 and owner == 'CONFIRM') or \
           (Projects.get(a.projectId) is not None and Projects[a.projectId].owner == owner):

            printLog(f"Retire Actimetre{actimId:04d} from {Projects[a.projectId].name()}")
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
            htmlUpdate()
                
        print("Location:\\index.html\n\n")

    elif formId == 'remove-project':
        projectId = int(args['projectId'][0])
        if projectId != 0:
            for a in Projects[projectId].actimetreList:
                if Actimetres.get(a) is not None:
                    Actimetres[a].projectId = 0
            del Projects[projectId]
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            repoStats()
        print(f"Location:\\index.html\n\n")

    else:
        print("Location:\\index.html\n\n")

def checkSecret():
    if secret != SECRET_KEY:
        printLog(f"Wrong secret {secret}")
        print(f"Wrong secret {secret}", file=sys.stdout)
        plain("Wrong secret")
        return

def processAction():
    if action == 'actiserver' or action == 'actiserver3':
        checkSecret()
        serverId = int(args['serverId'][0])
            
        if serverId != 0:
            printLog(f"Actis{serverId} alive")
            thisServer = Actiserver(serverId).fromD(json.load(sys.stdin), actual=True)
            if Actiservers.get(serverId) is not None:
                s = Actiservers[serverId]
                thisServer.diskLow = s.diskLow
                if thisServer.diskLow == 0:
                    if thisServer.diskSize > 0 and thisServer.diskFree < thisServer.diskSize // 10:
                        thisServer.diskLow = 1
                        thisServer.alertDisk()
                elif thisServer.diskLow == 1:
                    if thisServer.diskSize > 0 and thisServer.diskFree < thisServer.diskSize // 20:
                        thisServer.diskLow = 2
                        thisServer.alertDisk()
                else:
                    if thisServer.diskSize > 0 and thisServer.diskFree > thisServer.diskSize // 10:
                        thisServer.diskLow = 0
            Actiservers[serverId] = thisServer
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()

        remotes = loadRemotes()
        for actimId in remotes.keys():
            if actimId in thisServer.actimetreList:
                plain(f'+{actimId}:{remotes[actimId]}')
                del remotes[actimId]
                saveRemotes(remotes)
                return

        if action == 'actiserver':
            plain(json.dumps(Registry))
        else:
            if RegistryTime > thisServer.dbTime.replace(tzinfo=timezone.utc) \
               or ProjectsTime > thisServer.dbTime.replace(tzinfo=timezone.utc):
                printLog(f'{thisServer.dbTime} < {ProjectsTime}, needs update')
                plain('!')
            else:
                plain('OK')

    elif action == 'registry':
        checkSecret()
#        serverId = int(args['serverId'][0])
        plain(json.dumps(Registry))

    elif action == 'projects':
        checkSecret()
#        serverId = int(args['serverId'][0])
        plain()
        listProjects()

    elif action == 'report':
        checkSecret()
        serverId  = int(args['serverId'][0])
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            message = sys.stdin.read()
            printLog(f'Actim{actimId:04d} {message}')
            Actimetres[actimId].reportStr = message
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        plain('OK')
        
    elif action == 'clear-report':
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            printLog(f'Actim{actimId:04d} CLEAR {Actimetres[actimId].reportStr}')
            Actimetres[actimId].reportStr = ""
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'actimetre-new':
        checkSecret()
        mac       = args['mac'][0]
        boardType = args['boardType'][0]
        serverId  = int(args['serverId'][0])
        version   = args['version'][0]
        bootTime  = utcStrptime(args['bootTime'][0])

        thisServer = Actiservers.get(serverId)
        if thisServer is None:
            thisServer = Actiserver(serverId, lastUpdate=NOW)
            Actiservers[serverId] = thisServer
        else:
            thisServer.lastUpdate = NOW

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

        a = Actimetre(actimId, mac, boardType, version, serverId, bootTime=NOW, lastSeen=NOW, lastReport=NOW, isDead=0)
        printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")

        thisServer.actimetreList.add(actimId)
        Actimetres[actimId] = a
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        htmlUpdate()
        plain(responseStr)

    elif action == 'actimetre-off':
        checkSecret()
        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = Actimetres.get(actimId)
        if a is not None:
            a.dies()
#            Actiservers[serverId].actimetreList.remove(actimId)
#            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
        plain("Ok")

    elif action == 'actimetre-query':
        checkSecret()
        ### TODO
        try:
            actisList = json.load(sys.stdin)
        except JSONDecodeError:
            plain("101 Parse error")

        plain("0")

    elif action == 'actimetre-removed':
        checkSecret()
        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = Actimetres.get(actimId)
        if a is not None:
            a.serverId = 0
            a.repoNums = 0
            a.repoSize = 0
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})

        s = Actiservers.get(serverId)
        if s is not None:
            s.actimetreList.remove(actimId)
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            
        htmlUpdate()
        plain("Ok")

    elif action == 'actim-change-project':
        actimId = int(args['actimId'][0])
        actimChangeProject(actimId)

    elif action == 'actim-cut-graph':
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].cutHistory()
            Actimetres[actimId].drawGraph()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
        if args.get('projectId') is not None:
            print("Location:\\project{int(args['projectId'][0]):03d}.html\n\n")
        else:
            print("Location:\\index.html\n\n")

    elif action == 'remote-button':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x10)
        print("Location:\\index.html\n\n")

    elif action == 'actim-sync':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x20)
        print("Location:\\index.html\n\n")

    elif action == 'actim-forget':
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].forgetData()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        print("Location:\\index.html\n\n")

    elif action == 'actim-decouple':
        actimId = int(args['actimId'][0])
        serverId = int(args['serverId'][0])
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].forgetData()
        if Actiservers.get(serverId) is not None and actimId in Actiservers[serverId].actimetreList:
            Actiservers[serverId].actimetreList.remove(actimId)
            printLog(f"Removed Actim{actimId:04d} from Actis{serverId:04d}")
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'remote-restart':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0xF0)
        print("Location:\\index.html\n\n")

    elif action == 'actim-stop':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x30)
        print("Location:\\index.html\n\n")

    elif action == 'retire-actim':
        actimId = int(args['actimId'][0])
        retireActim(actimId)

    elif action == 'retire-server':
        serverId = int(args['serverId'][0])
        del Actiservers[serverId]
        htmlUpdate()
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        print("Location:\\index.html\n\n")

    elif action == 'project-change-info':
        projectId = int(args['projectId'][0])
        projectChangeInfo(projectId)

    elif action == 'project-edit-info':
        projectId = int(args['projectId'][0])
        projectEditInfo(projectId)

    elif action == 'create-project':
        print("Location:\\formCreate.html\n\n")

    elif action == 'remove-project':
        projectId = int(args['projectId'][0])
        removeProject(projectId)

    elif action == 'submit':
        formId = args['formId'][0]
        printLog(f"Submitted form {formId}")
        processForm(formId)

    elif action == 'cancel':
        print("Location:\\index.html\n\n")
        
import argparse
cmdparser = argparse.ArgumentParser()
cmdparser.add_argument('action', default='', nargs='?')
cmdargs = cmdparser.parse_args()
if cmdargs.action == 'prepare-stats':
    printLog("Timer prepare-stats")
    checkAlerts()
    repoStats()
    lock.close()
    sys.exit(0)

import urllib.parse
qs = os.environ['QUERY_STRING']
remote = os.environ['REMOTE_ADDR']
printLog(f"From {remote}: {qs}")

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
    if 'secret' in args.keys():
        secret = args['secret'][0]
    else:
        secret = "YouDontKnowThis"
    processAction()

lock.close()

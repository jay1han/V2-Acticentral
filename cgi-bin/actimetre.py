import os.path
import sys

from const import *
from registry import Registry
from project import Projects
from actiserver import Actiservers

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='???', version='000',
                 serverId=0, isDead=0, isStopped=False,
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,
                 projectId = 0, sensorStr="", frequency = 0, rating = 0.0, rssi = 0,
                 repoNums = 0, repoSize = 0):
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
        self.dirty      = True

    def __str__(self):
        string = f'Actim{self.actimId:04d}'
        if self.isDead > 0: string += '(dead)'
        string += f' {self.sensorStr}@{self.frequency}'
        string += f' Project{self.projectId:02d}'
        string += f' {self.repoNums}/{printSize(self.repoSize)}'
        return string

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

    def fromD(self, d, actual=False):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.version    = d['version']
        self.serverId   = int(d['serverId'])
        self.isDead     = int(d['isDead'])
        self.isStopped  = (str(d['isStopped']).strip().upper() == "TRUE")
        self.bootTime   = utcStrptime(d['bootTime'])
        self.lastSeen   = utcStrptime(d['lastSeen'])
        self.lastReport = utcStrptime(d['lastReport'])
        self.sensorStr  = d['sensorStr']
        self.frequency  = int(d['frequency'])
        self.rating     = float(d['rating'])
        self.rssi       = int(d['rssi'])
        self.repoNums   = int(d['repoNums'])
        self.repoSize   = int(d['repoSize'])

        if not actual:
            self.projectId  = int(d['projectId'])
            self.lastDrawn  = utcStrptime(d['lastDrawn'])
            self.graphSince = utcStrptime(d['graphSince'])
            self.reportStr  = d['reportStr']
        self.dirty = actual
        return self

    def update(self, newActim, actual=True):
        redraw = False
        if actual:
            if self.serverId != newActim.serverId:
                Actiservers.removeActim(self.actimId)
                if self.frequency > 0:
                    if Actiservers[self.serverId]:
                        self.addFreqEvent(Actiservers.getLastUpdate(self.serverId), 0)
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
            self.dirty = True

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

        if redraw: self.drawGraph()
        return redraw

    def name(self):
        return f"Actim{self.actimId:04d}"

    def htmlInfo(self):
        if self.isDead > 0 or self.frequency == 0:
            return f'<span class="down">(dead)</span>'
        elif self.isStopped:
            return f'({self.sensorStr})'
        else:
            return f'{self.sensorStr}@{self.frequencyText()}'

    def htmlCartouche(self):
        return f'{self.name()}&nbsp;<span class="small">{self.htmlInfo()}</span> '

    def htmlActimType(self):
        return f'{self.boardType}/v{self.version}'

    def addFreqEvent(self, now, frequency):
        from history import ActimHistory
        ActimHistory(self).addFreqEvent(now, frequency)

    def cutHistory(self, cutLength=None):
        from history import ActimHistory
        ActimHistory(self).cutHistory(cutLength)
        self.dirty = True

    def drawGraph(self):
        from history import ActimHistory
        ActimHistory(self).drawGraph()

    def drawGraphMaybe(self):
        from history import ActimHistory
        return ActimHistory(self).drawGraphMaybe()

    def alert(self, subject=None, info=""):
        printLog(f'Alert {self.name()}')
        if subject is None:
            subject = f'{self.name()} unreachable since {self.lastSeen.strftime(TIMEFORMAT_ALERT)}'
        content = f'{self.name()}\n'
        content += Projects.getName(self.projectId, 'Project "%s"\n')
        content += f'Type {self.boardType}\nMAC {self.mac}\n' + \
                   f'Sensors {self.sensorStr}\n' + \
                   f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' + \
                   f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'
        content += Actiservers.emailInfo(self.serverId)

        sendEmail(Projects.getEmail(self.projectId), subject, content + info)

    def forgetData(self):
        self.isDead = 3
        self.repoNums = 0
        self.repoSize = 0
        Actiservers.removeActim(self.actimId)
        self.serverId = 0
        printLog(f"{self.name()} data forgotten")
        self.dirty = True

    def dies(self):
        if self.isDead == 0:
            printLog(f'{self.name()} dies {NOW.strftime(TIMEFORMAT_DISP)}')
            self.frequency = 0
            self.isDead = 1
            self.addFreqEvent(NOW, 0)
            self.drawGraph()
        printLog(f"Actim{self.actimId:04d} removed from Actis{self.serverId:03d}")
        Actiservers.removeActim(self.actimId)
        self.serverId = 0
        self.repoSize = 0
        self.repoNums = 0
        Projects.dirtyProject(self.projectId)
        self.dirty = True

    def frequencyText(self, sensorStr = None):
        if self.isDead > 0 or self.frequency == 0:
            if sensorStr is None or sensorStr == "":
                return "(dead)"
            else:
                return f"({sensorStr})<br>dead"
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
        return printTimeSpan(up)

    def hasData(self):
        return self.repoNums > 0 or self.repoSize > 0

    def html(self):
        doc, tag, text, line = Doc().ttl()
        with tag('tr'):
            doc.asis(f'<form action="/bin/acticentral.py" method="get">')
            doc.asis(f'<input type="hidden" name="actimId" value="{self.actimId}"/>')
            alive = 'up'
            if NOW - self.lastReport > ACTIM_RETIRE_P:
                alive = 'retire'
            elif self.frequency == 0 or self.isDead > 0:
                alive = 'down'

            with tag('td', klass=alive):
                doc.asis('Actim&shy;{:04d}'.format(self.actimId))
                if alive == 'up':
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-restart'):
                        text('Restart')
                elif alive == 'retire':
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-retire'):
                        text('Retire')
            with tag('td', name='actimproject'):
                if self.projectId == 0:
                    with tag('a', href="/actims-free.html"):
                        text('Available')
                else:
                    with tag('a', href=f'/project{self.projectId:02d}.html'):
                        text(Projects.getName(self.projectId))
            with tag('td'):
                text(self.boardType)
                doc.asis('<br>')
                text(f"v{self.version}")
            if self.serverId != 0:
                line('td', f"Actis{self.serverId:03d}", name="actimfree",
                     klass="" if (Actiservers.isDown(self.serverId) == 0) else "down")
            else:
                line('td', "", name="actimfree")
            with tag('td', name="actimfree"):
                doc.asis(self.frequencyText(self.sensorStr))
                if alive == 'up':
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-switch'):
                        text('Switch')
            if alive == 'up':
                with tag('td', name="actimfree"):
                    doc.asis(htmlRssi(self.rssi))
                    doc.stag('br')
                    if self.isStopped: text('stopped')
                    else:              text("{:.3f}%".format(100.0 * self.rating))
            else:
                line('td', "", name="actimfree")

            if alive == 'retire':
                with tag('td', klass=f'health retire'):
                    doc.asis(f'Last seen: {self.lastSeen.strftime(TIMEFORMAT_DISP)}' +
                             f'<br>({printTimeSpan(NOW - self.lastSeen)} ago)'),
            else:
                with tag('td', klass=f'health left'):
                    if self.graphSince == TIMEZERO:
                        text('? ')
                    else:
                        text(self.graphSince.strftime(TIMEFORMAT_DISP) + "\n")
                    doc.asis('<button type="submit" name="action" value="actim-cut-graph">&#x2702;</button>\n')
                    line('span', f' {self.uptime()}', klass=alive)
                    if not os.path.isfile(f'{IMAGES_DIR}/Actim{self.actimId:04d}.svg'):
                        self.cutHistory()
                        self.drawGraph()
                    with tag('div'):
                        doc.stag('img', src=f'/images/Actim{self.actimId:04d}.svg', klass='health')

            with tag('td', klass='right'):
                if not self.hasData(): line('span', 'No data', name="actimfree")
                else:
                    text(f'{self.repoNums} files')
                    doc.stag('br')
                    text(printSize(self.repoSize))
                if self.serverId == 0 or not self.hasData():
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-move'):
                        doc.asis('Move')
                    if self.projectId != 0:
                        doc.asis('<br>')
                        with tag('button', type='submit', name='action', value='actim-remove'):
                            doc.asis('Remove')
                elif alive == 'up' and self.hasData() and Actiservers.getVersion(self.serverId) >= '380':
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-stop'):
                        doc.asis('Stop')
                elif alive != 'up' and self.hasData() and Actiservers.isDown(self.serverId) == 0:
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-sync'):
                        text('Sync')
                elif alive == 'retire' and self.hasData():
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-forget'):
                        doc.asis('Forget')
            if self.reportStr != "":
                with tag('td', klass="report"):
                    text(self.reportStr)
                    doc.asis('<br><button type="submit" name="action" value="actim-clear">Clear</button>\n')
            doc.asis('</form>\n')
        return doc.getvalue()

    def save(self):
        if self.dirty:
            printLog(f'Actim{self.actimId:04d}[{self.projectId}] is dirty')
            Projects.dirtyProject(self.projectId)
            with open(f'{ACTIM_HTML_DIR}/actim{self.actimId:04d}.html', "w") as html:
                print(self.html(), file=html)
            try: os.chmod(f'{ACTIM_HTML_DIR}/actim{self.actimId:04d}.html', 0o666)
            except OSError: pass
            return True
        else: return False

class ActimetresClass:
    def __init__(self):
        self.actims: dict[int, Actimetre] = {}
        self.dirty = False

    def __getitem__(self, item: int):
        return item in self.actims

    def init(self):
        self.actims = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}
        for mac, actimId in Registry.macToId.items():
            if actimId not in self.actims.keys():
                self.actims[actimId] = Actimetre(actimId, mac=mac, projectId=0)
        for actim in self.actims.values():
            if fileOlderThan(f'{ACTIM_HTML_DIR}/actim{actim.actimId:04d}.html', 3600):
                actim.dirty = True

    def fromProject(self, projectId):
        return [actimId for actimId in self.actims.keys() if self.actims[actimId].projectId == projectId]

    def str(self, actimId: int):
        if not actimId in self.actims.keys(): return ""
        return str(self.actims[actimId])

    def fromD(self, data, actual=True):
        a = Actimetre().fromD(data, actual)
        if a.actimId in self.actims:
            self.actims[a.actimId].update(a, actual)
        else:
            self.actims[a.actimId] = a
        return a.actimId

    def isAlive(self, actimId: int):
        return actimId in self.actims.keys() and self.actims[actimId].isDead == 0

    def removeProject(self, actimId: int):
        if actimId in self.actims:
            self.actims[actimId].projectId = 0
            self.actims[actimId].dirty = True

    def checkOrphan(self, serverId: int, actimetreList):
        for a in self.actims.values():
            if a.serverId == serverId and not a.actimId in actimetreList:
                printLog(f"Actim{a.actimId:04d} orphaned by Actis{serverId}")
                a.forgetData()

    def dump(self, actimId: int):
        return json.dumps(self.actims[actimId].toD())

    def html(self, actimId: int):
        if not actimId in self.actims.keys(): return ""
        return self.actims[actimId].html()

    def htmlCartouche(self, actimId: int):
        if not actimId in self.actims.keys(): return ""
        return self.actims[actimId].htmlCartouche()

    def htmlActimType(self, actimId: int):
        if not actimId in self.actims.keys(): return ""
        return self.actims[actimId].htmlActimType()

    def htmlRepo(self, actimId: int, ip: str) -> str:
        if not actimId in self.actims.keys(): return ""
        a = self.actims[actimId]
        doc, tag, text, line = Doc().ttl()

        if a.repoNums == 0:
            text('(No data)')
        else:
            with tag('a', href=f'http://{ip}/Project{a.projectId:02d}/index{a.actimId:04d}.html'):
                doc.asis(f'{a.repoNums}&nbsp;/&nbsp;{printSize(a.repoSize)}')
        return doc.getvalue()

    def new(self, mac, boardType, version, serverId, bootTime=NOW):
        actimId = Registry.getId(mac)
        printLog(f"Actim{actimId:04d} for {mac} is type {boardType} booted at {bootTime}")
        self.actims[actimId] = Actimetre(actimId, mac, boardType, version, serverId, 0, bootTime, lastSeen=NOW, lastReport=NOW)

    def delete(self, actimId: int):
        if actimId in self.actims.keys():
            del self.actims[actimId]
            self.dirty = True
        try:
            os.remove(f"{HISTORY_DIR}/Actim{actimId:04d}.hist")
        except FileNotFoundError: pass

    def forget(self, actimId: int):
        if actimId in self.actims.keys():
            self.actims[actimId].forgetData()

    def setProjectId(self, actimId: int, projectId: int):
        if self.actims[actimId].projectId != projectId:
            self.actims[actimId].projectId = projectId
            self.actims[actimId].dirty = True
            return True
        return False

    def getServerId(self, actimId: int):
        if not actimId in self.actims.keys(): return 0
        return self.actims[actimId].serverId

    def getLastSeen(self, actimId: int):
        if not actimId in self.actims.keys(): return TIMEZERO
        return self.actims[actimId].lastSeen

    def dies(self, actimId: int):
        if actimId in self.actims.keys():
            self.actims[actimId].dies()

    def checkAlerts(self):
        for a in self.actims.values():
            if a.isDead == 1 and (NOW - a.lastSeen) > ACTIM_ALERT1:
                a.alert()
                a.isDead = 2
                a.dirty = True
            elif a.isDead == 2 and (NOW - a.lastSeen) > ACTIM_ALERT2:
                a.alert()
                a.isDead = 3
                a.dirty = True

    def alertAll(self, actimetreList, subject, content):
        for actimId in actimetreList:
            if actimId in self.actims.keys():
                self.actims[actimId].alert(subject, content)

    def getName(self, actimId: int):
        if not actimId in self.actims: return ""
        return self.actims[actimId].name()

    def processAction(self, action, args):
        actim = self.actims[int(args['actimId'][0])]

        if action == 'actim-cut-graph':
            actim.cutHistory()
            actim.drawGraph()
            print("Status: 205\n\n")

        elif action == 'actim-report':
            # check secret
            message = sys.stdin.read()
            actim.reportStr = message
            actim.dirty = True
            plain('OK')

        elif action == 'actim-clear':
            actim.reportStr = ""
            actim.dirty = True
            print("Status: 205\n\n")

        elif action == 'actim-forget':
            actim.forgetData()
            print("Status: 205\n\n")

        elif action == 'actim-move':
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formMove.html", {
                "{actimId}": str(actim.actimId),
                "{actimName}": actim.name(),
                "{actimInfo}": actim.htmlInfo(),
                "{projectName}": Projects.getName(actim.projectId),
                "{projectList}": Projects.htmlChoice(actim.projectId),
                "{attached}" : 'hidden' if (actim.projectId == 0) else '',
                "{notAttached}": 'hidden' if (actim.projectId > 0) else ''
            })

        elif action == 'actim-remove':
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formRemove.html", {
                "{actimId}": str(actim.actimId),
                "{actimName}": actim.name(),
                "{actimInfo}": actim.htmlInfo(),
                "{projectName}": Projects.getName(actim.projectId),
            })

        elif action == 'actim-retire':
            # TODO
            print("Status: 204\n\n")

        else:
            print("Status: 205\n\n")

    def processForm(self, formId, args):
        actim = self.actims[int(args['actimId'][0])]

        if formId == 'actim-move':
            projectId = int(args['projectId'][0])
            oldProject = actim.projectId
            if oldProject == 0 or args['owner'][0] == Projects.getOwner(oldProject):
                printLog(f"Changing {actim.name()} from Project{oldProject:02d} to Project{projectId:02d}")
                Projects.moveActim(actim.actimId, projectId)
                actim.projectId = projectId
                actim.dirty = True
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'actim-remove':
            projectId = actim.projectId
            if args['owner'][0] == Projects.getOwner(actim.projectId):
                Projects.removeActim(actim.actimId)
                actim.projectId = 0
                actim.dirty = True
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'actim-retire':
            pass

        else:
            print("Status: 205\n\n")

    def save(self):
        for actim in self.actims.values():
            if actim.save():
                self.dirty = True
        if self.dirty:
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in self.actims.values()})
            htmlStr = ''
            for actimId in sorted(self.actims.keys()):
                htmlStr += self.actims[actimId].html()
            writeTemplateSub(open(f'{HTML_ROOT}/actims.html', "w"), ACTIMS_TEMPLATE, {
                "{Actimetres}": htmlStr,
            })

Actimetres = ActimetresClass()
def initActimetres() -> ActimetresClass:
    Actimetres.init()
    return Actimetres

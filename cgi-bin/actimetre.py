import sys

from const import *
from registry import Registry
from project import Projects
from actiserver import Actiservers

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='???', version='000',
                 isDead=5, isStopped=False,
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO,
                 sensorStr="", frequency = 0, rating = 0.0, rssi = 0,
                 repoNums = 0, repoSize = 0):
        self.actimId    = int(actimId)
        self.mac        = mac
        self.boardType  = boardType
        self.version    = version
        self.isDead     = isDead
        self.isStopped  = isStopped
        self.bootTime   = bootTime
        self.lastSeen   = lastSeen
        self.lastReport = lastReport
        self.sensorStr  = sensorStr
        self.frequency  = frequency
        self.rating     = rating
        self.rssi       = rssi
        self.repoNums   = repoNums
        self.repoSize   = repoSize
        self.reportStr  = ""
        self.remote     = 0
        self.dirty      = False

    def __str__(self):
        string = f'Actim{self.actimId:04d}'
        if self.isDead > 0: string += '(dead)'
        string += f' {self.sensorStr}@{self.frequency}'
        string += f' Project{Projects.getProjectId(self.actimId):02d}'
        string += f' {self.repoNums}/{printSize(self.repoSize)}'
        return string

    def toD(self):
        return {'actimId'   : self.actimId,
                'mac'       : self.mac,
                'boardType' : self.boardType,
                'version'   : self.version,
                'isDead'    : int(self.isDead),
                'isStopped' : str(self.isStopped).upper(),
                'bootTime'  : self.bootTime.strftime(TIMEFORMAT_FN),
                'lastSeen'  : self.lastSeen.strftime(TIMEFORMAT_FN),
                'lastReport': self.lastReport.strftime(TIMEFORMAT_FN),
                'sensorStr' : self.sensorStr,
                'frequency' : self.frequency,
                'rating'    : self.rating,
                'rssi'      : str(self.rssi),
                'repoNums'  : self.repoNums,
                'repoSize'  : self.repoSize,
                'reportStr' : self.reportStr,
                'remote'    : self.remote,
                }

    def fromD(self, d:dict, actual=False):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.version    = d['version']
        self.isStopped  = (str(d['isStopped']).strip().upper() == "TRUE")
        self.bootTime   = utcStrptime(d['bootTime'])
        self.lastSeen   = utcStrptime(d['lastSeen'])
        self.lastReport = utcStrptime(d['lastReport'])
        self.sensorStr  = d['sensorStr']
        self.rating     = float(d['rating'])
        self.rssi       = int(d['rssi'])
        self.repoNums   = int(d['repoNums'])
        self.repoSize   = int(d['repoSize'])
        self.isDead     = int(d['isDead'])
        if self.isDead == 0: self.frequency  = int(d['frequency'])
        else:                self.frequency = 0

        if not actual:
            self.reportStr  = d['reportStr']
            if 'remote' in d.keys():
                self.remote = int(d['remote'])
        else:
            self.dirty = True
        return self

    def update(self, newActim):
        from history import ActimHistory
        history = ActimHistory(self)
        if newActim.isDead == 0:
            self.isDead = 0
            if self.bootTime < newActim.bootTime:
                history \
                    .addFreqEvent(newActim.bootTime, 0) \
                    .addFreqEvent(newActim.bootTime, newActim.frequency)
                self.bootTime = newActim.bootTime
                self.frequency  = newActim.frequency
            if self.frequency != newActim.frequency:
                history.addFreqEvent(NOW, newActim.frequency)
                self.frequency  = newActim.frequency

        self.isStopped  = newActim.isStopped
        self.boardType  = newActim.boardType
        self.version    = newActim.version
        self.sensorStr  = newActim.sensorStr
        self.lastSeen   = newActim.lastSeen
        self.lastReport = newActim.lastReport
        self.rating     = newActim.rating
        self.rssi       = newActim.rssi
        self.repoNums   = newActim.repoNums
        self.repoSize   = newActim.repoSize
        self.dirty = True
        history.drawGraphMaybe()

    def name(self):
        return f"Actim{self.actimId:04d}"

    def htmlInfo(self):
        subtext = f'{self.sensorStr}@{self.frequencyText()}'
        if self.isDead > 0 or self.frequency == 0:
            subtext = f'<span class="down">(dead)</span>'
        elif self.isStopped:
            subtext = f'({self.sensorStr})'
        if self.boardType != "":
            return f'{self.boardType}:' + subtext
        else:
            return subtext

    def htmlCartouche(self):
        return (f'{self.name()}&nbsp;<span class="small">{self.htmlInfo()}' +
                ('*' if self.reportStr != "" else '') +
                '</span>\n')

    def htmlActimType(self):
        return f'{self.boardType}/v{self.version}'

    def cutHistory(self):
        from history import ActimHistory
        ActimHistory(self).cutHistory()

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
        content += Projects.getName(Projects.getProjectId(self.actimId), 'Project "%s"\n')
        content += f'Type {self.boardType}\nMAC {self.mac}\n' + \
                   f'Sensors {self.sensorStr}\n' + \
                   f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' + \
                   f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'
        content += Actiservers.serverInfo(self.actimId)

        sendEmail(Projects.getEmail(Projects.getProjectId(self.actimId)), subject, content + info)

    def forgetData(self):
        self.isDead = 3
        self.repoNums = 0
        self.repoSize = 0
        Actiservers.removeActim(self.actimId)
        Projects.actimIsStale(self.actimId)
        printLog(f"{self.name()} data forgotten")
        self.dirty = True

    def dies(self):
        printLog(f'{self.name()} dies {NOW.strftime(TIMEFORMAT_DISP)}')
        self.frequency = 0
        self.isDead = 1
        from history import ActimHistory
        ActimHistory(self).addFreqEvent(NOW, 0).drawGraph()
        # serverId = Actiservers.removeActim(self.actimId)
        # printLog(f"Actim{self.actimId:04d} removed from Actis{serverId:03d}")
        # self.repoSize = 0
        # self.repoNums = 0
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
            up = self.lastReport
        else:
            up = self.bootTime
        return printTimeAgo(up)

    def hasData(self):
        return self.repoNums > 0 or self.repoSize > 0

    def htmlButton(self, action, text, *, hide=False, name=None) -> str:
        if not hide:
            return ('<form action="/bin/acticentral.py" method="get" style="padding:0;margin:0"' +
                    (f' name="{name}"' if name is not None else '') +
                    f'><input type="hidden" name="actimId" value="{self.actimId}"/>' +
                    f'<button type="submit" name="action" value="{action}">' +
                    f'{text}</button></form>\n')
        else: return ''

    def html(self):
        doc, tag, text, line = Doc().ttl()
        serverId = Actiservers.getServerId(self.actimId)
        projectId = Projects.getProjectId(self.actimId)

        alive = 'up'
        if NOW - self.lastReport > ACTIM_RETIRE_P:
            alive = 'retire'
        elif self.frequency == 0 or self.isDead > 0:
            alive = 'down'

        with tag('td', klass=alive):
            doc.asis('Actim&shy;{:04d}'.format(self.actimId))
            if alive == 'up':
                doc.asis(self.htmlButton("actim-remote-restart", "Restart", hide = (self.remote != 0)))
            elif alive == 'retire':
                doc.asis(self.htmlButton("actim-retire", "Retire"))
        with tag('td', name='actimproject'):
            if projectId == 0:
                with tag('a', href="/actims-free.html"):
                    text('Available')
            else:
                with tag('a', href=f'/project{projectId:02d}.html'):
                    text(Projects.getName(projectId))
        with tag('td'):
            text(self.boardType)
            doc.asis('<br>')
            text(f"v{self.version}")
        if serverId != 0:
            line('td', f"Actis{serverId:03d}", name="actimfree",
                 klass="" if (Actiservers.isDown(serverId) == 0) else "down")
        else:
            line('td', "", name="actimfree")
        with tag('td', name="actimfree"):
            doc.asis(self.frequencyText(self.sensorStr))
            if alive == 'up':
                doc.asis(self.htmlButton("actim-remote-switch", "Switch",
                                         hide = (self.remote != 0 or self.isStopped)))
        if alive == 'up':
            with tag('td', name="actimfree"):
                doc.asis(htmlRssi(self.rssi))
                doc.stag('br')
                if self.isStopped: line('span', 'Stopped', klass='down')
                else:              text("{:.3f}%".format(100.0 * self.rating))
        else:
            line('td', "", name="actimfree")

        if alive == 'retire':
            line('td', '', klass='health retire')
        else:
            with tag('td', klass=f'health left'):
                from history import ActimHistory
                history = ActimHistory(self)
                if history.graphSince != TIMEZERO:
                    doc.asis(self.htmlButton("actim-cut-graph",
                                             history.graphSince.strftime(TIMEFORMAT_DISP) +
                                             '&#x2702;' +
                                             f'<span class="{alive}">{self.uptime()}</span>\n'))
                    history.drawGraphMaybe()
                    with tag('div'):
                        doc.stag('img',
                                 src=f'/images/actim{self.actimId:04d}.svg',
                                 klass='health',
                                 id=f'Image{self.actimId:04d}')

        with tag('td', klass='right'):
            if self.hasData():
                text(f'{self.repoNums} / {printSize(self.repoSize)}')
                doc.asis(self.htmlButton("actim-remote-stop", "Stop",
                                         hide = (self.remote != 0 or self.isStopped)))
                # doc.asis(self.htmlButton("actim-remote-sync", "Sync",
                #                          hide = (self.remote != 0)))
            else:
                line('span', 'No data', name='actimfree')
                doc.asis(self.htmlButton("actim-move", "Move"))
                if projectId != 0:
                    doc.asis(self.htmlButton("actim-remove", "Remove", name='actimfree'))
        if self.reportStr != "":
            with tag('td', klass="report"):
                text(self.reportStr)
                doc.asis(self.htmlButton("actim-clear", "Clear"))
        return doc.getvalue()

    def save(self):
        if self.dirty:
            printLog(f'Actim{self.actimId:04d}[{Projects.getProjectId(self.actimId)}]({self.isDead}) is dirty')
            with open(f'{ACTIM_HTML_DIR}/actim{self.actimId:04d}.html', "w") as html:
                print(self.html(), file=html)
            self.drawGraphMaybe()
            return True
        else:
            return False

class ActimetresClass:
    def __init__(self):
        self.actims: dict[int, Actimetre] = {}
        self.dirty = False  # save data
        self.stale = False  # write HTML

    def __getitem__(self, item: int):
        return item in self.actims

    def init(self):
        self.actims = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}
        for mac, actimId in Registry.macToId.items():
            if actimId not in self.actims.keys():
                self.actims[actimId] = Actimetre(actimId, mac=mac)
        for actim in self.actims.values():
            if fileNeedsUpdate(f'{ACTIM_HTML_DIR}/actim{actim.actimId:04d}.html', actim.lastReport):
                actim.dirty = True
        if fileOlderThan(ACTIMS_HTML, 3600):
            self.stale = True

    def str(self, actimId: int):
        if not actimId in self.actims.keys(): return ""
        return str(self.actims[actimId])

    def fromDactual(self, data):
        a = Actimetre().fromD(data, True)
        if a.actimId in self.actims:
            self.actims[a.actimId].update(a)
        else:
            self.actims[a.actimId] = a
        self.dirty = True
        return a.actimId

    def dump(self, actimId: int):
        return json.dumps(self.actims[actimId].toD())

    def allActimList(self):
        return set(self.actims.keys())

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
            with tag('a', href=f'http://{ip}/Project{Projects.getProjectId(a.actimId):02d}/index{a.actimId:04d}.html'):
                doc.asis(f'{a.repoNums}&nbsp;/&nbsp;{printSize(a.repoSize)}')
        return doc.getvalue()

    def new(self, mac, boardType, version, bootTime=NOW):
        actimId = Registry.getId(mac)
        printLog(f"Actim{actimId:04d} for {mac} is type {boardType} booted at {bootTime}")
        self.actims[actimId] = Actimetre(actimId, mac, boardType, version, 0, bootTime, lastSeen=NOW, lastReport=NOW)
        self.stale = True
        return actimId

    def forget(self, actimId: int):
        if actimId in self.actims.keys():
            self.actims[actimId].forgetData()

    def getLastSeen(self, actimId: int):
        if not actimId in self.actims.keys(): return TIMEZERO
        return self.actims[actimId].lastSeen

    def hasGraph(self, actimId: int):
        if not actimId in self.actims.keys(): return False
        return NOW - self.actims[actimId].lastSeen < ACTIM_RETIRE_P

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

    def isAlive(self, actimId: int):
        if not actimId in self.actims: return False
        return self.actims[actimId].isDead == 0

    def getRemote(self, actimId):
        if actimId in self.actims.keys():
            command = self.actims[actimId].remote
            if command != 0:
                self.actims[actimId].remote = 0
                self.actims[actimId].dirty = True
                return command
        return 0

    def processAction(self, action, args):
        actim = self.actims[int(args['actimId'][0])]

        if action == 'actim-cut-graph':
            actim.cutHistory()
            actim.drawGraph()
            print("Status: 205\n\n")

        elif action == 'actim-report':
            from acticentral import checkSecret
            if not checkSecret():
                print("Status: 205\n\n")
            else:
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
                "{projectName}": Projects.getName(Projects.getProjectId(actim.actimId)),
                "{projectList}": Projects.htmlChoice(Projects.getProjectId(actim.actimId)),
                "{inputOwner}": '' \
                    if (Projects.getProjectId(actim.actimId) == 0) \
                    else '<p><input type="text" name="owner" value="" required></p>',
                "{attached}" : 'hidden' if (Projects.getProjectId(actim.actimId) == 0) else '',
                "{notAttached}": 'hidden' if (Projects.getProjectId(actim.actimId) > 0) else ''
            })

        elif action == 'actim-remove':
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formRemove.html", {
                "{actimId}": str(actim.actimId),
                "{actimName}": actim.name(),
                "{actimInfo}": actim.htmlInfo(),
                "{projectName}": Projects.getName(Projects.getProjectId(actim.actimId)),
            })

        elif action.startswith('actim-remote-'):
            actimId = int(args['actimId'][0])
            if actimId in self.actims.keys():
                command = 0
                if action   == 'actim-remote-switch' : command = REMOTE_SWITCH
                elif action == 'actim-remote-sync'   : command = REMOTE_SYNC
                elif action == 'actim-remote-stop'   : command = REMOTE_STOP
                elif action == 'actim-remote-restart': command = REMOTE_RESTART
                printLog(f'addRemote: Actim{actimId:04d} command 0x{command:02X}')
                self.actims[actimId].remote = command
                self.actims[actimId].dirty = True
                print("Status: 205\n\n")
            else:
                print("Status: 204\n\n")

        elif action == 'actim-retire':
            # TODO
            print("Status: 204\n\n")

        else:
            print("Status: 205\n\n")

    def processForm(self, formId, args):
        actim = self.actims[int(args['actimId'][0])]

        if formId == 'actim-move':
            if actim.isDead == 0 and not actim.isStopped:
                printLog(f"Can't move {actim.name()} because it's alive and not stopped")
                actim.reportStr = "Alive; can't move"
                actim.dirty = True
                projectId = Projects.getProjectId(actim.actimId)
            else:
                projectId = int(args['projectId'][0])
                oldProjectId = Projects.getProjectId(actim.actimId)
                if oldProjectId == 0 or args['owner'][0] == Projects.getOwner(oldProjectId):
                    printLog(f"Changing {actim.name()} from Project{oldProjectId:02d} to Project{projectId:02d}")
                    Projects.moveActim(actim.actimId, projectId)
                    actim.dirty = True
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'actim-remove':
            projectId = Projects.getProjectId(actim.actimId)
            if actim.isDead == 0 and not actim.isStopped:
                printLog(f"Can't remove {actim.name()} because it's alive and not stopped")
                actim.reportStr = "Alive; can't remove"
            else:
                if args['owner'][0] == Projects.getOwner(Projects.getProjectId(actim.actimId)):
                    Projects.moveActim(actim.actimId, 0)
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
        if self.stale:
            allPages = []
            htmlAll = ""
            for actimId in sorted(self.actims.keys()):
                htmlAll += f'<tr id="Actim{actimId:04d}"></tr>\n'
                allPages.append('{' +
                                f'id: "Actim{actimId:04d}", ' +
                                f'ref: "/actimetre/actim{actimId:04d}.html", ' +
                                f'date: "{JS_TIMEZERO}", ' +
                                'html: ""}')
            writeTemplateSub(open(ACTIMS_HTML, "w"), ACTIMS_TEMPLATE, {
                "{Actimetres}": htmlAll,
                "{allpages}"  : ',\n'.join(allPages),
                "{date}"      : jsDateString(now()),
            })

Actimetres: ActimetresClass = ActimetresClass()
def initActimetres() -> ActimetresClass:
    Actimetres.init()
    return Actimetres

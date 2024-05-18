from const import *
import actimetre
import project

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000",
                 channel=0, ip = "0.0.0.0", isDown = 0, lastUpdate=TIMEZERO, dbTime=TIMEZERO,
                 actimetreList=None):
        self.serverId   = int(serverId)
        self.machine    = machine
        self.version    = version
        self.channel    = int(channel)
        self.ip         = ip
        self.diskSize   = 0
        self.diskFree   = 0
        self.lastUpdate = lastUpdate
        self.dbTime     = dbTime
        self.isDown     = isDown
        if actimetreList is None:
            self.actimetreList = set()
        else:
            self.actimetreList = actimetreList
        self.diskLow    = 0
        self.cpuIdle    = 0.0
        self.memAvail   = 0.0
        self.diskTput   = 0.0
        self.diskUtil   = 0.0
        self.dirty      = False

    def __str__(self):
        Actimetres = actimetre.Actimetres
        string = f'Actis{self.serverId:03d} '
        string += self.lastUpdate.strftime(TIMEFORMAT_DISP)
        for actimId in self.actimetreList:
            string += f' - {Actimetres.str(actimId)}'
        return string

    def toD(self):
        return {'serverId'  : self.serverId,
                'machine'   : self.machine,
                'version'   : self.version,
                'channel'   : self.channel,
                'ip'        : self.ip,
                'diskSize'  : self.diskSize,
                'diskFree'  : self.diskFree,
                'diskLow'   : self.diskLow,
                'lastUpdate': self.lastUpdate.strftime(TIMEFORMAT_FN),
                'dbTime'    : self.dbTime.strftime(TIMEFORMAT_FN),
                'isDown'    : self.isDown,
                'actimetreList': '[' + ','.join([str(actimId) for actimId in self.actimetreList]) + ']',
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
        self.diskSize = int(d['diskSize'])
        self.diskFree = int(d['diskFree'])
        self.actimetreList = set()
        self.dbTime = utcStrptime(d['dbTime'])
        self.cpuIdle  = float(d['cpuIdle'])
        self.memAvail = float(d['memAvail'])
        self.diskTput = float(d['diskTput'])
        self.diskUtil = float(d['diskUtil'])

        Actimetres = actimetre.Actimetres
        if d['actimetreList'] != "[]":
            if actual:
                for actimData in json.loads(d['actimetreList']):
                    actimId = Actimetres.fromDactual(actimData)
                    self.actimetreList.add(actimId)
            else:
                for actimData in json.loads(d['actimetreList']):
                    if isinstance(actimData, int):
                        self.actimetreList.add(actimData)
                    else: self.actimetreList.add(int(actimData['actimId']))

        if actual:
            self.lastUpdate = NOW
        else:
            self.isDown = int(d['isDown'])
            self.lastUpdate = utcStrptime(d['lastUpdate'])
            self.diskLow = int(d['diskLow'])
        self.dirty = actual
        return self

    def name(self):
        return f"Actis{self.serverId:03d}"

    def addActim(self, actimId):
        if not actimId in self.actimetreList:
            self.actimetreList.add(actimId)
            self.lastUpdate = NOW
            self.dirty = True

    def removeActim(self, actimId):
        if actimId in self.actimetreList:
            self.actimetreList.remove(actimId)
            self.dirty = True
            return True
        else: return False

    def alertContent(self):
        content = f'{self.name()}\n' + \
                  f'Hardware {self.machine}\nVersion {self.version}\n' + \
                  f'IP {self.ip}\nChannel {self.channel}\n' + \
                  f'Disk size {printSize(self.diskSize)}, free {printSize(self.diskFree)} ' + \
                  f'Last seen {self.lastUpdate.strftime(TIMEFORMAT_DISP)}\n' + \
                  f'Last known Actimetres:\n'
        for actimId in self.actimetreList:
            content += f'Actim{actimId:04d} '
        content += '\n'
        return content

    def alert(self):
        Actimetres = actimetre.Actimetres
        printLog(f'Alert {self.name()}')
        subject = f'{self.name()} unreachable since {self.lastUpdate.strftime(TIMEFORMAT_ALERT)}'
#        sendEmail("", subject, self.alertContent())
        Actimetres.alertAll(self.actimetreList, subject, self.alertContent())

    def alertDisk(self):
        Actimetres = actimetre.Actimetres
        printLog(f'{self.name()} disk low')
        subject = f'{self.name()} storage low'
        sendEmail("", subject, self.alertContent())
        Actimetres.alertAll(self.actimetreList, subject, self.alertContent())

    def html(self):
        from actimetre import Actimetres
        doc, tag, text, line = Doc().ttl()

        with tag('tr', id=f'Actis{self.serverId:03d}'):
            if NOW - self.lastUpdate < ACTIS_FAIL_TIME:
                alive = 'up'
            elif NOW - self.lastUpdate > ACTIS_RETIRE_P:
                alive = 'retire'
            else:
                alive = 'down'

            with tag('td', klass=alive):
                text(self.name())
                if alive == 'retire':
                    doc.asis('<br>')
                    doc.asis(f'<form action="/bin/acticentral.py" method="get">')
                    doc.asis(f'<input type="hidden" name="serverId" value="{self.serverId}" />')
                    line('button', 'Retire', type='submit', name='action', value='server-retire')
                    doc.asis('</form>')
                else:
                    doc.asis('<br>')
                    line('span', self.ip, klass='small')
            line('td', self.machine)
            with tag('td'):
                if alive == 'up':
                    text(f"v{self.version}")
                    doc.asis("<br>")
                    if self.channel != 0:
                        text(f"Ch. {self.channel}")
            line('td', self.lastUpdate.strftime(TIMEFORMAT_DISP), klass=alive)
            if alive != 'up':
                with tag('td', klass=alive):
                    text(f'Missing {printTimeAgo(self.lastUpdate)}')
                line('td', '')
                line('td', '')
                line('td', '')
            else:
                with tag('td', klass='no-padding'):
                    if self.version >= "370":
                        with tag('table'):
                            with tag('tr'):
                                with tag('td', klass='left-tight'):
                                    doc.asis('CPU<br>RAM<br>Disk')
                                with tag('td', klass='left-tight'):
                                    text(f'{self.cpuIdle:.1f}% idle')
                                    doc.asis('<br>')
                                    text(f'{self.memAvail:.1f}% avail.')
                                    doc.asis('<br>')
                                    text(f'{self.diskTput:.0f}kB/s({self.diskUtil:.1f}%)')
                    else: text('')
                with tag('td', klass='left'):
                    for actimId in self.actimetreList:
                        with tag('div'):
                            doc.asis(Actimetres.htmlCartouche(actimId))
                with tag('td', klass='right'):
                    for actimId in self.actimetreList:
                        with tag('div'):
                            doc.asis(Actimetres.htmlRepo(actimId, self.ip))
                if self.diskSize > 0:
                    diskState = ''
                    if self.diskFree < self.diskSize // 10:
                        diskState = 'disk-low'
                    line('td', f'{printSize(self.diskFree)} ({100.0*self.diskFree/self.diskSize:.1f}%)', klass=diskState)
                else:
                    line('td', '')
        return doc.getvalue()

    def save(self):
        if self.dirty:
            printLog(f'Actis{self.serverId:03d} is dirty')
            with open(f'{SERVER_HTML_DIR}/server{self.serverId:03d}.html', "w") as html:
                print(self.html(), file=html)
            return True
        else: return False

class ActiserversClass:
    def __init__(self):
        self.servers: dict[int, Actiserver] = {}
        self.dirty = False

    def init(self):
        self.servers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}
        if fileOlderThan(SERVERS_HTML, 3600):
            self.dirty = True
        for server in self.servers.values():
            if fileNeedsUpdate(f'{SERVER_HTML_DIR}/server{server.serverId:03d}.html', server.lastUpdate):
                server.dirty = True

    def __getitem__(self, item: int):
        return item in self.servers

    def htmlWrite(self, *, picker=None):
        allPages = []
        allServers = ""
        for serverId in sorted(self.servers.keys()):
            if picker is None or picker(self.servers[serverId]):
                allPages.append('{' +
                                f'id: "Actis{serverId:03d}", ' +
                                f'ref: "/actiserver/server{serverId:03d}.html", ' +
                                f'date: "{JS_TIMEZERO}"' + '}')
                allServers += f'<tr id="Actis{serverId:03d}"></tr>\n'
        writeTemplateSub(open(SERVERS_HTML, "w"), SERVERS_TEMPLATE, {
                         '{Actiservers}': allServers,
                         '{allpages}': ',\n'.join(allPages),
                         '{date}': jsDateString(now() + PROCESSING_TIME),
        })

    def listIds(self):
        return sorted(self.servers.keys())

    def getLastUpdate(self, serverId):
        return self.servers[serverId].lastUpdate

    def getVersion(self, serverId):
        return self.servers[serverId].version

    def getCpuIdle(self, serverId):
        return self.servers[serverId].cpuIdle

    def isDown(self, serverId):
        if serverId in self.servers:
            return self.servers[serverId].isDown
        else: return True

    def addActim(self, serverId, actimId):
        self.servers[serverId].addActim(actimId)

    def removeActim(self, actimId):
        serverId = 0
        for s in self.servers.values():
            if s.removeActim(actimId): serverId = s.serverId
        return serverId

    def getServerId(self, actimId):
        for s in self.servers.values():
            if actimId in s.actimetreList:
                return s.serverId
        else: return 0

    def serverInfo(self, actimId):
        for s in self.servers.values():
            if actimId in s.actimetreList: return \
                f'{s.name()}\n' + \
                f'Hardware {s.machine}\nVersion {s.version}\n' + \
                f'IP {s.ip}\nChannel {s.channel}\n' + \
                f'Disk size {printSize(s.diskSize)}, free {printSize(s.diskFree)} ' + \
                f'({100.0 * s.diskFree / s.diskSize :.1f}%)\n' + \
                f'Last seen {s.lastUpdate.strftime(TIMEFORMAT_DISP)}\n'
        return ''

    def getRemotes(self, serverId):
        remotes = []
        if serverId in self.servers.keys():
            Actimetres = actimetre.Actimetres
            for actimId in self.servers[serverId].actimetreList:
                command = Actimetres.getRemote(actimId)
                if command != 0:
                    printLog(f'getRemote Actim{actimId:04d}:{command:02X}')
                    remotes.append((actimId, command))
        return remotes

    def checkAlerts(self):
        for s in self.servers.values():
            if s.isDown == 0 and (NOW - s.lastUpdate) > ACTIS_ALERT1:
                s.alert()
                s.isDown = 1
                s.dirty = True
            elif s.isDown == 1 and (NOW - s.lastUpdate) > ACTIS_ALERT2:
                s.alert()
                s.isDown = 2
                s.dirty = True
            elif s.isDown == 2 and (NOW - s.lastUpdate) > ACTIS_ALERT3:
                s.alert()
                s.isDown = 3
                s.dirty = True

    def processUpdate(self, serverId, data):
        thisServer = Actiserver(serverId).fromD(json.load(data), True)
        if serverId in self.servers.keys():
            thisServer.diskLow = self.servers[serverId].diskLow
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
        if not serverId in self.servers.keys():
            self.dirty = True
        self.servers[serverId] = thisServer

        Projects = project.Projects
        for actimId in thisServer.actimetreList:
            Projects.makeDirty(actimId)
        Projects.makeStaleMaybe(serverId)

        printLog(thisServer)
        return thisServer

    def processAction(self, action, args):
        if action == 'server-retire':
            # TODO
            print("Status: 204\n\n")
        else:
            print("Status: 205\n\n")

    def processForm(self, formId, args):
        print("Status: 205\n\n")

    def save(self):
        stale = False
        for server in self.servers.values():
            if server.save(): stale = True
        if self.dirty:
            self.htmlWrite()
            stale = True
        if stale:
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in self.servers.values()})

Actiservers = ActiserversClass()
def initActiservers() -> ActiserversClass:
    Actiservers.init()
    return Actiservers

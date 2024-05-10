from const import *
import actimetre

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000",
                 channel=0, ip = "0.0.0.0", isLocal = False,
                 isDown = 0, lastUpdate=TIMEZERO, dbTime=TIMEZERO,
                 actimetreList=None):
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
            string += f'\n- {Actimetres.str(actimId)}'
        return string

    def toD(self):
        Actimetres = actimetre.Actimetres
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
                'actimetreList': '[' + ','.join([Actimetres.dump(actimId) for actimId in self.actimetreList]) + ']',
                'cpuIdle'   : self.cpuIdle,
                'memAvail'  : self.memAvail,
                'diskTput'  : self.diskTput,
                'diskUtil'  : self.diskUtil,
                }

    def fromD(self, d, actual=False):
        Actimetres = actimetre.Actimetres
        self.serverId   = int(d['serverId'])
        self.machine    = d['machine']
        self.version    = d['version']
        self.channel    = int(d['channel'])
        self.ip         = d['ip']
        self.isLocal = (str(d['isLocal']).strip().upper() == "TRUE")
        self.diskSize = int(d['diskSize'])
        self.diskFree = int(d['diskFree'])
        self.actimetreList = set()
        self.dbTime = utcStrptime(d['dbTime'])
        self.isDown = int(d['isDown'])
        self.cpuIdle  = float(d['cpuIdle'])
        self.memAvail = float(d['memAvail'])
        self.diskTput = float(d['diskTput'])
        self.diskUtil = float(d['diskUtil'])

        if d['actimetreList'] != "[]":
            for actimData in json.loads(d['actimetreList']):
                actimId = Actimetres.fromD(actimData, actual)
                self.actimetreList.add(actimId)
        Actimetres.checkOrphan(self.serverId, self.actimetreList)

        if actual:
            self.lastUpdate = NOW
        else:
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

        with tag('tr'):
            doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
            doc.asis(f'<input type="hidden" name="serverId" value="{self.serverId}" />')
            if NOW - self.lastUpdate < ACTIS_FAIL_TIME:
                alive = 'up'
            elif NOW - self.lastUpdate > ACTIS_RETIRE_P:
                alive = 'retire'
            else:
                alive = 'down'

            with tag('td', klass=alive):
                text(self.name())
                doc.asis('<br>')
                line('span', self.ip, klass='small')
            #                if alive == 'retire':
            #                    line('button', 'Retire', type='submit', name='action', value='retire-server')
            line('td', self.machine)
            with tag('td'):
                if alive == 'up':
                    text(f"v{self.version}")
                    doc.asis("<br>")
                    if self.channel != 0:
                        text(f"Ch. {self.channel}")
                else:
                    text("?")
            if self.lastUpdate == TIMEZERO:
                line('td', "?", klass=alive)
            else:
                line('td', self.lastUpdate.strftime(TIMEFORMAT_DISP), klass=alive)
            if alive != 'up':
                line('td', '')
                line('td', "None")
                line('td', '')
                line('td', '')
            else:
                with tag('td', klass='no-padding'):
                    if self.version >= "370":
                        with tag('table'):
                            with tag('tr'):
                                with tag('td', klass='left-tight'):
                                    text('CPU')
                                    doc.asis('<br>')
                                    text('RAM')
                                    doc.asis('<br>')
                                    text('Disk')
                                with tag('td', klass='left-tight'):
                                    text(f'{self.cpuIdle:.1f}% idle')
                                    doc.asis('<br>')
                                    text(f'{self.memAvail:.1f}% free')
                                    doc.asis('<br>')
                                    text(f'{self.diskTput:.0f}kB/s({self.diskUtil:.1f}%)')
                    else: text('')
                with tag('td', klass='left'):
                    for actimId in self.actimetreList:
                        with tag('div'):
                            doc.asis(Actimetres.htmlCartouche(actimId))
                if self.isLocal:
                    with tag('td', klass='right'):
                        for actimId in self.actimetreList:
                            with tag('div'):
                                doc.asis(Actimetres.htmlRepo(actimId, self.version, self.ip))
                    if self.diskSize > 0:
                        diskState = ''
                        if self.diskFree < self.diskSize // 10:
                            diskState = 'disk-low'
                        line('td', f'{printSize(self.diskFree)} ({100.0*self.diskFree/self.diskSize:.1f}%)', klass=diskState)
                    else:
                        line('td', '')
                else:
                    line('td', '')
                    line('td', '')

        return doc.getvalue()

class ActiserversClass:
    def __init__(self):
        self.servers: dict[int, Actiserver] = {}

    def init(self):
        self.servers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}

    def __getitem__(self, item: int):
        return item in self.servers

    def htmlServers(self, *, picker=None):
        htmlString = ""
        for serverId in sorted(self.servers.keys()):
            if picker is None or picker(self.servers[serverId]):
                htmlString += self.servers[serverId].html()
        return htmlString

    def htmlWriteServers(self):
        with open(SERVERS_HTML, "w") as html:
            with open(SERVERS_TEMPLATE, "r") as template:
                print(template.read() \
                      .replace('{Actiservers}', self.htmlServers()) \
                      .replace('{Updated}', LAST_UPDATED),
                      file=html)

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

    def delete(self, serverId):
        if serverId in self.servers.keys():
            del self.servers[serverId]
            return True
        else:return False

    def addActim(self, serverId, actimId):
        self.servers[serverId].addActim(actimId)

    def removeActim(self, actimId):
        for s in self.servers.values():
            s.removeActim(actimId)

    def emailInfo(self, serverId):
        s = self.servers[serverId]
        return \
            f'{s.name()}\n' + \
            f'Hardware {s.machine}\nVersion {s.version}\n' + \
            f'IP {s.ip}\nChannel {s.channel}\n' + \
            f'Disk size {printSize(s.diskSize)}, free {printSize(s.diskFree)} ' + \
            f'({100.0 * s.diskFree / s.diskSize :.1f}%)\n' + \
            f'Last seen {s.lastUpdate.strftime(TIMEFORMAT_DISP)}\n'

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

    def processAction(self, serverId, data):
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
        self.servers[serverId] = thisServer
        printLog(thisServer)
        return thisServer

    def save(self):
        for server in self.servers.values():
            if server.dirty:
                dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in self.servers.values()})
                self.htmlWriteServers()
                return

Actiservers = ActiserversClass()
def initActiservers() -> ActiserversClass:
    Actiservers.init()
    return Actiservers

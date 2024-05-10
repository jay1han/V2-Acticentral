from const import *
import globals as x
from actimetre import Actimetre
from project import Projects

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000", channel=0, ip = "0.0.0.0", isLocal = False,
                 isDown = 0, lastUpdate=TIMEZERO, dbTime=TIMEZERO, actimetreList=None):
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
                'actimetreList': '[' + ','.join([json.dumps(x.Actimetres[actimId].toD()) for actimId in self.actimetreList]) + ']',
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
                a = Actimetre().fromD(actimData, fromFile=False)
                if a.actimId in x.Actimetres.keys():
                    x.Actimetres[a.actimId].update(a, actual)
                else:
                    x.Actimetres[a.actimId] = a
                self.actimetreList.add(a.actimId)
                Projects.htmlUpdate(x.Actimetres[a.actimId].projectId)

        for a in x.Actimetres.values():
            if a.serverId == self.serverId and not a.actimId in self.actimetreList:
                printLog(f"Actim{a.actimId:04d} orphaned by Actis{self.serverId}")
                a.dies()

        if not actual:
            self.lastUpdate = utcStrptime(d['lastUpdate'])
            self.diskLow = int(d['diskLow'])
        else:
            self.lastUpdate = NOW

        return self

    def serverName(self):
        return f"Actis{self.serverId:03d}"

    def alert(self):
        printLog(f'Alert {self.serverName()}')
        subject = f'{self.serverName()} unreachable since {self.lastUpdate.strftime(TIMEFORMAT_ALERT)}'
        content = f'{self.serverName()}\n' + \
                  f'Hardware {self.machine}\nVersion {self.version}\n' + \
                  f'IP {self.ip}\nChannel {self.channel}\n' + \
                  f'Disk size {printSize(self.diskSize)}, free {printSize(self.diskFree)} ' + \
                  f'Last seen {self.lastUpdate.strftime(TIMEFORMAT_DISP)}\n' + \
                  f'Last known Actimetres:\n    '
        for actimId in self.actimetreList:
            content += f'Actim{actimId:04d} '
        content += '\n'

        sendEmail("", subject, content)

    def alertDisk(self):
        printLog(f'{self.serverName()} disk low')
        subject = f'{self.serverName()} storage low'
        content = f'{self.serverName()}\n' + \
                  f'Hardware {self.machine}\nVersion {self.version}\n' + \
                  f'IP {self.ip}\nChannel {self.channel}\n' + \
                  f'Disk size {printSize(self.diskSize)}, free {printSize(self.diskFree)} ' + \
                  f'Last seen {self.lastUpdate.strftime(TIMEFORMAT_DISP)}\n' + \
                  f'Last known Actimetres:\n    '
        for actimId in self.actimetreList:
            content += f'Actim{actimId:04d} '
            if x.Actimetres.get(actimId) is not None:
                x.Actimetres[actimId].alertDisk()
        content += '\n'

        sendEmail("", subject, content)

    def html(self):
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
                text(self.serverName())
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
                            doc.asis(x.Actimetres[actimId].htmlCartouche())
                if self.isLocal:
                    with tag('td', klass='right'):
                        for actimId in self.actimetreList:
                            a = x.Actimetres[actimId]
                            with tag('div'):
                                if a.repoNums == 0:
                                    text('(No data)')
                                else:
                                    if self.version >= "345":
                                        link = f'http://{self.ip}/Project{a.projectId:02d}/index{a.actimId:04d}.html'
                                    else:
                                        link = f'http://{self.ip}/index{a.actimId:04d}.html'
                                    with tag('a', href=link):
                                        doc.asis(f'{a.repoNums}&nbsp;/&nbsp;{printSize(a.repoSize)}')
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
        self.servers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}
        self.dirty = False

    def save(self, save=True):
        if save:
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in self.servers.values()})

    def html(self, *, picker=None):
        htmlString = ""
        for serverId in sorted(self.servers.keys()):
            if picker is None or picker(self.servers[serverId]):
                htmlString += self.servers[serverId].html()
        return htmlString

    def htmlUpdate(self):
        with open(SERVERS_HTML, "w") as html:
            with open(SERVERS_TEMPLATE, "r") as template:
                print(template.read() \
                      .replace('{Actiservers}', self.html()) \
                      .replace('{Updated}', LAST_UPDATED),
                      file=html)


    def exists(self, serverId):
        return serverId in self.servers.keys()

    def getLastUpdate(self, serverId):
        if serverId in self.servers.keys():
            return self.servers[serverId].lastUpdate
        else: return TIMEZERO

    def get(self, serverId, update=False):
        if not serverId in self.servers.keys():
            self.servers[serverId] = Actiserver(serverId)
            if update:
                self.servers[serverId].lastUpdate = NOW
        return self.servers[serverId]

    def getVersion(self, serverId):
        if serverId in self.servers.keys():
            return self.servers[serverId].version
        else: return "000"

    def getCpuIdle(self, serverId):
        if serverId in self.servers.keys():
            return self.servers[serverId].cpuIdle
        else: return 0.0

    def isDown(self, serverId):
        if serverId in self.servers.keys():
            return self.servers[serverId].isDown
        else: return 1

    def delete(self, serverId):
        if serverId in self.servers.keys():
            del self.servers[serverId]
            self.save()
            return True
        return False

    def removeActim(self, actimId, serverId=None):
        save = False
        if serverId is not None:
            s = self.servers.get(serverId)
            if actimId in s.actimetreList:
                s.actimetreList.remove(actimId)
                save = True
        else:
            for s in self.servers.values():
                if actimId in s.actimetreList:
                    s.actimetreList.remove(actimId)
                    save = True
        self.save(save)
        return save

    def emailInfo(self, serverId):
        if serverId in self.servers.keys():
            s = self.servers[serverId]
            return \
                f'{s.serverName()}\n' + \
                f'Hardware {s.machine}\nVersion {s.version}\n' + \
                f'IP {s.ip}\nChannel {s.channel}\n' + \
                f'Disk size {printSize(s.diskSize)}, free {printSize(s.diskFree)} ' + \
                f'({100.0 * s.diskFree / s.diskSize :.1f}%)\n' + \
                f'Last seen {s.lastUpdate.strftime(TIMEFORMAT_DISP)}\n'
        else: return ""

    def checkAlerts(self):
        save = False
        for s in self.servers.values():
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
        self.save(save)

    def processAction(self, serverId, data):
        thisServer = Actiserver(serverId).fromD(json.load(data), actual=True)
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
        self.save()
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})

Actiservers = ActiserversClass()

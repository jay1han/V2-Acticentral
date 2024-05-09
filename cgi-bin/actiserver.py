from globals import *
if not 'Actimetre' in dir():
    from actimetre import *

class Actiserver:
    def __init__(self, serverId=0, machine="Unknown", version="000", channel=0, ip = "0.0.0.0", isLocal = False, \
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
            if Actimetres.get(actimId) is not None:
                Actimetres[actimId].alertDisk()
        content += '\n'

        sendEmail("", subject, content)

    def html(self, force=False):
        doc, tag, text, line = Doc().ttl()

        if NOW - self.lastUpdate > ACTIM_HIDE_P and not force:
            return ""
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
                            doc.asis(Actimetres[actimId].htmlCartouche())
                if self.isLocal:
                    with tag('td', klass='right'):
                        for actimId in self.actimetreList:
                            a = Actimetres[actimId]
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

        return indent(doc.getvalue())

def htmlAllServers():
    htmlString = ""
    for serverId in sorted(Actiservers.keys()):
        htmlString += Actiservers[serverId].html(True)

    with open(SERVERS_HTML, "w") as html:
        with open(SERVERS_TEMPLATE, "r") as template:
            print(template.read() \
                  .replace('{Actiservers}', htmlString) \
                  .replace('{Updated}', LAST_UPDATED) \
                  , file=html)

def initActiservers():
    global Actiservers
    if len(Actiservers) == 0:
        Actiservers = {int(serverId):Actiserver().fromD(d) for serverId, d in loadData(ACTISERVERS).items()}

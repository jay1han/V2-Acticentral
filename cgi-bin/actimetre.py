from yattag import Doc, indent

from const import *
import globals as x

REDRAW_TIME  = timedelta(minutes=5)
REDRAW_DEAD  = timedelta(minutes=30)
GRAPH_SPAN   = timedelta(days=7)
GRAPH_CULL   = timedelta(days=6)
FSCALETAG    = {50:5, 100:10}
FSCALEV3     = {100:3, 1000:5, 4000:8, 8000:10}
FSCALEV3TAG  = {100:3, 1000:5, 4000:8}

class Actimetre:
    def __init__(self, actimId=0, mac='.' * 12, boardType='?', version="", serverId=0, isDead=0, isStopped=False, \
                 bootTime=TIMEZERO, lastSeen=TIMEZERO, lastReport=TIMEZERO, \
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

    def fromD(self, d, fromFile=True):
        self.actimId    = int(d['actimId'])
        self.mac        = d['mac']
        self.boardType  = d['boardType']
        self.version    = d['version']
        self.serverId   = int(d['serverId'])
        self.isDead     = int(d['isDead'])
        self.isStopped = (str(d['isStopped']).strip().upper() == "TRUE")
        self.bootTime   = utcStrptime(d['bootTime'])
        self.lastSeen   = utcStrptime(d['lastSeen'])
        self.lastReport = utcStrptime(d['lastReport'])
        self.sensorStr  = d['sensorStr']
        self.frequency  = int(d['frequency'])
        self.rating     = float(d['rating'])
        self.rssi   = int(d['rssi'])
        self.repoNums   = int(d['repoNums'])
        self.repoSize   = int(d['repoSize'])

        if fromFile:
            self.projectId  = int(d['projectId'])
            for p in x.Projects.values():
                if self.actimId in p.actimetreList and p.projectId != self.projectId:
                    p.actimetreList.remove(self.actimId)
            if x.Projects.get(self.projectId) is None:
                self.projectId = 0
            else:
                x.Projects[self.projectId].actimetreList.add(self.actimId)
            self.lastDrawn = utcStrptime(d['lastDrawn'])
            self.graphSince = utcStrptime(d['graphSince'])
            self.reportStr = d['reportStr']

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
        s = x.Actiservers.get(self.serverId)
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
            s = x.Actiservers.get(self.serverId)
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
        if x.Projects.get(self.projectId) is not None:
            content += f'Project "{x.Projects[self.projectId].name()}"\n'
        content += f'Type {self.boardType}\nMAC {self.mac}\n' + \
                   f'Sensors {self.sensorStr}\n' + \
                   f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' + \
                   f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'

        if x.Projects.get(self.projectId) is not None \
                and x.Projects[self.projectId].email != "":
            sendEmail(x.Projects[self.projectId].email, subject, content)
        sendEmail("", subject, content)

    def alertDisk(self):
        printLog(f"{self.actimName()}'s server disk low")
        subject = f"{self.actimName()}'s server disk low"
        content = f'{self.actimName()}\n'
        if x.Projects.get(self.projectId) is not None:
            content += f'Project "{x.Projects[self.projectId].name()}"\n'
        content += f'Type {self.boardType}\nMAC {self.mac}\n' + \
                   f'Sensors {self.sensorStr}\n' + \
                   f'Last seen {self.lastSeen.strftime(TIMEFORMAT_DISP)}\n' + \
                   f'Total data {self.repoNums} files, size {printSize(self.repoSize)}\n'
        if x.Actiservers.get(self.serverId) is not None:
            s = x.Actiservers[self.serverId]
            content += f'{s.serverName()}\n' + \
                       f'Hardware {s.machine}\nVersion {s.version}\n' + \
                       f'IP {s.ip}\nChannel {s.channel}\n' + \
                       f'Disk size {printSize(s.diskSize)}, free {printSize(s.diskFree)} ' + \
                       f'({100.0 * s.diskFree / s.diskSize :.1f}%)\n' + \
                       f'Last seen {s.lastUpdate.strftime(TIMEFORMAT_DISP)}\n'
        content += '\n'

        if x.Projects.get(self.projectId) is not None \
                and x.Projects[self.projectId].email != "":
            sendEmail(x.Projects[self.projectId].email, subject, content)
        else:
            sendEmail("", subject, content)

    def dies(self):
        if self.isDead == 0:
            printLog(f'{self.actimName()} dies {NOW.strftime(TIMEFORMAT_DISP)}')
            self.frequency = 0
            self.isDead = 1
            self.addFreqEvent(NOW, 0)
            self.drawGraph()
        if self.serverId != 0 and x.Actiservers.get(self.serverId) is not None:
            if self.actimId in x.Actiservers[self.serverId].actimetreList:
                printLog(f"Actim{self.actimId:04d} removed from Actis{self.serverId:03d}")
                x.Actiservers[self.serverId].actimetreList.remove(self.actimId)
            self.serverId = 0
            self.repoSize = 0
            self.repoNums = 0
            if x.Projects.get(self.projectId) is not None:
                printLog(f"Actim{self.actimId:04d} dies, update Project{self.projectId:02d}")
                x.Projects[self.projectId].htmlUpdate()

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

    def html(self):
        s = x.Actiservers.get(self.serverId)
        doc, tag, text, line = Doc().ttl()
        with tag('tr'):
            doc.asis(f'<form action="/bin/{CGI_BIN}" method="get">')
            doc.asis(f'<input type="hidden" name="actimId" value="{self.actimId}"/>')
            alive = 'up'
            if NOW - self.lastReport > ACTIM_RETIRE_P:
                alive = 'retire'
            elif self.frequency == 0 or self.isDead > 0:
                alive = 'down'

            with tag('td', klass=alive):
                doc.asis('Actim&shy;{:04d}'.format(self.actimId))
                if self.version >= '301' and alive == 'up' and \
                        (s is not None and s.version >= '301') :
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-restart'):
                        text('Reboot')
            with tag('td'):
                text(self.boardType)
                doc.asis('<br>')
                text(f"v{self.version}")
            if self.serverId != 0:
                if s is not None and s.isDown == 0:
                    line('td', f"Actis{self.serverId:03d}")
                else:
                    line('td', f"Actis{self.serverId:03d}", klass="down")
            else:
                line('td', "")
            with tag('td'):
                doc.asis(self.frequencyText(self.sensorStr))
                if self.version >= '301' and alive == 'up' and \
                        (x.Actiservers.get(self.serverId) is not None and x.Actiservers[self.serverId].version >= '301') :
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='remote-button'):
                        text('Button')
            if alive == 'up':
                with tag('td'):
                    doc.asis(htmlRssi(self.rssi))
                    doc.stag('br')
                    if self.isStopped:
                        text('stopped')
                    else:
                        text("{:.3f}%".format(100.0 * self.rating))
            else:
                line('td', "")

            if alive == 'retire':
                line('td', 'No data', klass=f'health retire')
            else:
                with tag('td', klass=f'health left'):
                    if self.graphSince == TIMEZERO:
                        text('? ')
                    else:
                        text(self.graphSince.strftime(TIMEFORMAT_DISP) + "\n")
                    doc.asis('<button type="submit" name="action" value="actim-cut-graph">&#x2702;</button>\n')
                    line('span', f' {self.uptime()}', klass=alive)
                    with tag('div'):
                        doc.stag('img', src=f'/images/Actim{self.actimId:04d}.svg', klass='health')

            with tag('td', klass='right'):
                if not self.hasData():
                    text('No data')
                else:
                    text(f'{self.repoNums} files')
                    doc.stag('br')
                    text(printSize(self.repoSize))
                if self.serverId == 0 or not self.hasData():
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-change-project'):
                        doc.asis('Move')
                elif alive == 'up' and self.hasData() and \
                        (x.Actiservers.get(self.serverId) is not None and x.Actiservers[self.serverId].version >= '380'):
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-stop'):
                        doc.asis('Stop')
                elif alive != 'up' and self.hasData() and s is not None and s.isDown == 0:
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-sync'):
                        text('Sync')
                elif alive == 'retire' and self.hasData():
                    doc.asis('<br>')
                    with tag('button', type='submit', name='action', value='actim-forget'):
                        doc.asis('Forget')
            if self.reportStr != "":
                with tag('td', klass="report"):
                    text(self.reportStr)
                    doc.asis('<br><button type="submit" name="action" value="clear-report">Clear</button>\n')
            doc.asis('</form>\n')
        return indent(doc.getvalue())

def loadActimetres():
    x.Actimetres = {int(actimId):Actimetre().fromD(d) for actimId, d in loadData(ACTIMETRES).items()}
from const import *

from actimetre import Actimetre

FSCALE       = {100:2, 1000:5, 4000:10}
FSCALETAG    = {100:2, 1000:5, 4000:10}

def scaleFreq(origFreq):
    if origFreq == 0:
        return 0
    for limit, scale in FSCALE.items():
        if origFreq <= limit:
            return scale
    return origFreq // 40

class ActimHistory:
    def __init__(self, actim):
        self.a: Actimetre = actim
        self.dirty = False
        self.histFile  = f'{HISTORY_DIR}/actim{self.a.actimId:04d}.hist'
        self.imageFile = f'{IMAGES_DIR}/actim{self.a.actimId:04d}.svg'
        if not os.path.isfile(self.histFile):
            self.lastDrawn = TIMEZERO
            self.graphSince = TIMEZERO
        else:
            self.lastDrawn = datetime.fromtimestamp(os.stat(self.histFile).st_mtime, timezone.utc)
        try:
            with open(self.histFile, "r") as history:
                self.graphSince = utcStrptime(history.readline().partition(':')[0])
        except FileNotFoundError:
            self.graphSince = TIMEZERO

    def cutHistory(self):
        printLog(f'Actim{self.a.actimId:04d} cut history to {self.a.bootTime.strftime(TIMEFORMAT_DISP)}')
        freshLines = list()
        try:
            with open(self.histFile, "r") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                    if time >= self.a.bootTime:
                        freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                        freshLines.extend(history.readlines())
        except FileNotFoundError:
            pass

        if len(freshLines) == 0:
            printLog(f'Actm{self.a.actimId:04d} has no history')
            os.remove(self.histFile)
        else:
            with open(self.histFile, "w") as history:
                for line in freshLines:
                    print(line.strip(), file=history)
        self.dirty = True

    def drawGraph(self):
        os.environ['MPLCONFIGDIR'] = "/etc/matplotlib"
        import matplotlib.pyplot as pyplot

        printLog(f'Actim{self.a.actimId:04d}.lastDrawn = {self.lastDrawn.strftime(TIMEFORMAT_DISP)}')

        timeline = []
        frequencies = []
        scaledFreqNow = 0
        try:
            with open(f"{HISTORY_DIR}/actim{self.a.actimId:04d}.hist", "r") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    scaledFreqNow = scaleFreq(int(freqStr))
                    if len(timeline) == 0 or scaledFreqNow != frequencies[-1]:
                        timeline.append(time)
                        frequencies.append(scaledFreqNow)
        except FileNotFoundError:
            timeline.append(TIMEZERO)
            frequencies.append(scaleFreq(self.a.frequency))

        timeline.append(NOW)
        frequencies.append(scaledFreqNow)
        rowFreqNow = [scaledFreqNow for _ in range(len(timeline))]

        fig, ax = pyplot.subplots(figsize=(5.0,1.0), dpi=50.0)
        ax.set_axis_off()
        ax.set_ylim(bottom=-1, top=12)
        ax.axvline(timeline[0], 0, 0.95, lw=1.0, c="blue", marker="^", markevery=[1], ms=5.0, mfc="blue")
        fscale = FSCALETAG
        for real, drawn in fscale.items():
            if self.a.frequency == real:
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
        if self.a.isDead > 0 or self.a.frequency == 0:
            ax.plot(timeline[-2:], rowFreqNow[-2:], ds="steps-post", c="red", lw=3.0)
        else:
            ax.plot(timeline[-2:], rowFreqNow[-2:], ds="steps-post", c="green", lw=3.0)
        pyplot.savefig(f"{IMAGES_DIR}/actim{self.a.actimId:04d}.svg", format='svg', bbox_inches="tight", pad_inches=0)
        pyplot.close()
        try:
            os.chmod(f"{IMAGES_DIR}/actim{self.a.actimId:04d}.svg", 0o666)
        except OSError:
            pass
        self.lastDrawn = now()
        self.a.dirty = True

    def drawGraphMaybe(self):
        if NOW - self.a.lastSeen < ACTIM_RETIRE_P:
            if (self.dirty or
                fileNeedsUpdate(self.imageFile, self.a.bootTime, timedelta(minutes=5))):
                printLog(f'Actim{self.a.actimId:04d}.lastDrawn = {self.lastDrawn.strftime(TIMEFORMAT_DISP)} vs. {NOW.strftime(TIMEFORMAT_DISP)}')
                self.drawGraph()

    def addFreqEvent(self, x, frequency):
        try:
            with open(f"{HISTORY_DIR}/actim{self.a.actimId:04d}.hist", "r+") as history:
                time = TIMEZERO
                freq = 0
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                if x < time: x = time
                if frequency != freq:
                    print(x.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)
                    self.dirty = True
        except FileNotFoundError:
            with open(f"{HISTORY_DIR}/actim{self.a.actimId:04d}.hist", "w") as history:
                print(x.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)
                self.dirty = True
        return self

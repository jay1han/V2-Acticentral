from const import *

from actimetre import Actimetre

REDRAW_TIME  = timedelta(minutes=5)
REDRAW_DEAD  = timedelta(minutes=30)
GRAPH_SPAN   = timedelta(days=7)
GRAPH_CULL   = timedelta(days=6)
FSCALE       = {100:2, 1000:5, 4000:10}
FSCALETAG    = {100:2, 1000:5, 4000:10}

def scaleFreq(origFreq):
    if origFreq == 0:
        return 0
    for limit, scale in FSCALE.items():
        if origFreq <= limit:
            return scale
    else:
        return origFreq // 10

class ActimHistory:
    def __init__(self, actim):
        self.a: Actimetre = actim

    def cutHistory(self, cutLength):
        if cutLength is None:
            cutLength = NOW - self.a.bootTime

        printLog(f'Actim{self.a.actimId:04d} cut history to {self.a.bootTime.strftime(TIMEFORMAT_DISP)}')
        historyFile = f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist"
        freshLines = list()
        try:
            with open(historyFile, "r") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                    if NOW - time <= cutLength:
                        time = NOW - cutLength
                        self.a.graphSince = time
                        freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{freq}")
                        freshLines.extend(history.readlines())
        except FileNotFoundError:
            pass
        else:
            if len(freshLines) == 0:
                time = NOW - cutLength
                self.a.graphSince = time
                freshLines.append(f"{time.strftime(TIMEFORMAT_FN)}:{self.a.frequency}")

            os.truncate(historyFile, 0)
            with open(historyFile, "r+") as history:
                for line in freshLines:
                    print(line.strip(), file=history)

    def drawGraph(self):
        os.environ['MPLCONFIGDIR'] = "/etc/matplotlib"
        import matplotlib.pyplot as pyplot

        if NOW - self.a.graphSince >= GRAPH_SPAN:
            self.cutHistory(GRAPH_CULL)

        try:
            with open(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", "r") as history:
                self.a.graphSince = utcStrptime(history.readline().partition(':')[0])
        except (FileNotFoundError, ValueError):
            with open(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", "w") as history:
                print(NOW.strftime(TIMEFORMAT_FN), ':', self.a.frequency, sep="", file=history)
            self.a.graphSince = NOW

        timeline = []
        frequencies = []
        with open(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", "r") as history:
            for line in history:
                timeStr, part, freqStr = line.partition(':')
                time = utcStrptime(timeStr.strip())
                freq = scaleFreq(int(freqStr))
                if len(timeline) == 0 or freq != frequencies[-1]:
                    timeline.append(time)
                    frequencies.append(freq)

        timeline.append(NOW)
        frequencies.append(scaleFreq(self.a.frequency))
        freq = [scaleFreq(self.a.frequency) for _ in range(len(timeline))]

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
            ax.plot(timeline[-2:], freq[-2:], ds="steps-post", c="red", lw=3.0)
        else:
            ax.plot(timeline[-2:], freq[-2:], ds="steps-post", c="green", lw=3.0)
        pyplot.savefig(f"{IMAGES_DIR}/actim{self.a.actimId:04d}.svg", format='svg', bbox_inches="tight", pad_inches=0)
        pyplot.close()
        try:
            os.chmod(f"{IMAGES_DIR}/actim{self.a.actimId:04d}.svg", 0o666)
        except OSError:
            pass
        self.a.lastDrawn = NOW

    def drawGraphMaybe(self):
        redraw = False
        if self.a.isDead > 0:
            if NOW - self.a.lastSeen > ACTIM_RETIRE_P:
                redraw = False
            elif NOW - self.a.lastDrawn > REDRAW_DEAD:
                redraw = True
        else:
            if NOW - self.a.lastDrawn > REDRAW_TIME:
                redraw = True
        if redraw: self.drawGraph()
        return redraw

    def addFreqEvent(self, now, frequency):
        try:
            with open(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", "r+") as history:
                for line in history:
                    timeStr, part, freqStr = line.partition(':')
                    time = utcStrptime(timeStr.strip())
                    freq = int(freqStr)
                if now < time: now = time
                if frequency != freq:
                    print(now.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)
        except FileNotFoundError:
            with open(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", "w") as history:
                print(now.strftime(TIMEFORMAT_FN), frequency, sep=":", file=history)
            self.a.graphSince = now
            try:
                os.chmod(f"{HISTORY_DIR}/Actim{self.a.actimId:04d}.hist", 0o666)
            except OSError:
                pass

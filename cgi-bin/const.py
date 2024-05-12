### Constants and context-free functions

import os, json, subprocess
from datetime import datetime, timedelta, timezone
from yattag import Doc

VERSION_STR     = "v420"
FILE_ROOT       = "/etc/actimetre"
HTML_ROOT       = "/var/www/html"

ADMIN_EMAIL     = "actimetre@gmail.com"
ADMINISTRATORS  = f"{FILE_ROOT}/administrators"
LOG_SIZE_MAX    = 10_000_000

TIMEFORMAT_UTC  = "%Y%m%d%H%M%S%z"
TIMEFORMAT_FN   = "%Y%m%d%H%M%S"
TIMEFORMAT_DISP = "%Y/%m/%d %H:%M:%S"
TIMEFORMAT_ALERT= "%Y/%m/%d %H:%M (UTC)"

REGISTRY        = f"{FILE_ROOT}/registry.data"
REGISTRY_BACKUP = f"{FILE_ROOT}/registry/backup."
ACTIMETRES      = f"{FILE_ROOT}/actimetres.data"
ACTISERVERS     = f"{FILE_ROOT}/actiservers.data"
LOG_FILE        = f"{FILE_ROOT}/central.log"
PROJECTS        = f"{FILE_ROOT}/projects.data"
LOCK_FILE       = f"{FILE_ROOT}/acticentral.lock"
SECRET_FILE     = f"{FILE_ROOT}/.secret"
HISTORY_DIR     = f"{FILE_ROOT}/history"
REMOTE_FILE     = f"{FILE_ROOT}/remotes.data"
IMAGES_DIR      = f"{HTML_ROOT}/images"
INDEX_NAME      = "acticentral.html"
ACTIM_HTML_DIR  = f"{HTML_ROOT}/actimetre"
SERVER_HTML_DIR = f"{HTML_ROOT}/actiserver"
INDEX_HTML      = f"{HTML_ROOT}/{INDEX_NAME}"
SERVERS_HTML    = f"{HTML_ROOT}/servers.html"
ACTIMS_HTML     = f"{HTML_ROOT}/actims.html"
ACTIMS0_HTML    = f"{HTML_ROOT}/actims-free.html"
INDEX_TEMPLATE  = f"{HTML_ROOT}/template.html"
PROJECT_TEMPLATE= f"{HTML_ROOT}/templateProject.html"
SERVERS_TEMPLATE= f"{HTML_ROOT}/templateServers.html"
ACTIMS_TEMPLATE = f"{HTML_ROOT}/templateActims.html"
ACTIMS0_TEMPLATE= f"{HTML_ROOT}/templateActimsFree.html"

try:
    SECRET_KEY = open(SECRET_FILE, "r").read().strip()
except (OSError, FileNotFoundError):
    pass

ACTIM_ALERT1    = timedelta(minutes=5)
ACTIM_ALERT2    = timedelta(minutes=30)
ACTIS_ALERT1    = timedelta(minutes=5)
ACTIS_ALERT2    = timedelta(minutes=30)
ACTIS_ALERT3    = timedelta(hours=8)

ACTIS_FAIL_TIME = timedelta(seconds=60)
ACTIS_RETIRE_P  = timedelta(days=30)
ACTIM_RETIRE_P  = timedelta(days=30)

TIMEZERO        = datetime(year=2023, month=1, day=1, tzinfo=timezone.utc)
NOW             = datetime.now(timezone.utc)
LAST_UPDATED    = NOW.strftime(TIMEFORMAT_DISP)

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
        printLog(f"Can't open {filename}")
        return {}
    try:
        data = json.load(registry)
    except json.JSONDecodeError:
        printLog(f"Decode error in {filename}")
        data = {}
    registry.close()
    printLog(f"Loaded from {filename}: {len(data)} items")
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

def printTimeSpan(span: timedelta):
    months = span // timedelta(days=30)
    days = span // timedelta(days=1)
    hours = (span % timedelta(days=1)) // timedelta(hours=1)
    minutes = (span % timedelta(hours=1)) // timedelta(minutes=1)
    if span > timedelta(days=60):
        return f'{months} months'
    if span > timedelta(days=7):
        return f'{days} days'
    elif span > timedelta(days=1):
        return f'{days}d{hours}h'
    else:
        return f'{hours}h{minutes:02d}m'

def utcStrptime(string):
    return datetime.strptime(string.strip() + "+0000", TIMEFORMAT_UTC)

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
        result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", recipient],
                                input = content, text=True, stderr=subprocess.STDOUT)
        printLog(f'Email sent to "{recipient}", sendmail returns {result.returncode}: {result.stdout}')
    else:
        try:
            admins = open(ADMINISTRATORS, "r")
        except OSError:
            result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", ADMIN_EMAIL],
                                    input = content, text=True, stderr=subprocess.STDOUT)
            printLog(f'Email sent to "{ADMIN_EMAIL}", sendmail returns {result.returncode}: {result.stdout}')
        else:
            for email in admins:
                result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", email.strip()],
                                        input = content, text=True, stderr=subprocess.STDOUT)
                printLog(f'Email sent to "{email.strip()}", sendmail returns {result.returncode}: {result.stdout}')
            admins.close()

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

CONSTANT = {
    "{Updated}"    : LAST_UPDATED,
    "{Version}"    : VERSION_STR,
    "{Index}"      : INDEX_NAME,
}

def writeTemplateSub(output, template: str, substitutions: dict[str,str]):
    content = open(template, "r").read()
    for before, after in substitutions.items():
        content = content.replace(before, after)
    for before, after in CONSTANT.items():
        content = content.replace(before, after)
    print(content, file=output)
    return content

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

def fileOlderThan(filename: str, seconds: int) -> bool:
    return not os.path.isfile(filename) or \
        NOW - datetime.fromtimestamp(os.stat(filename).st_mtime, timezone.utc) > timedelta(seconds=seconds)

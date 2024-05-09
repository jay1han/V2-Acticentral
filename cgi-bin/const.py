### Constants and context-free functions

import os, json, subprocess
from datetime import datetime, timedelta, timezone
from yattag import Doc

VERSION_STR     = "v400"
FILE_ROOT       = "/etc/actimetre"
WWW_ROOT        = "/var/www"

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
STAT_FILE       = f"{FILE_ROOT}/acticentral.stat"
HISTORY_DIR     = f"{FILE_ROOT}/history"
REMOTE_FILE     = f"{FILE_ROOT}/remotes.data"
IMAGES_DIR      = f"{WWW_ROOT}/html/images"
IMAGES_INDEX    = f"{WWW_ROOT}/html/images/index.txt"
HTML_DIR        = f"{WWW_ROOT}/html"
INDEX_HTML      = f"{WWW_ROOT}/html/index.html"
SERVERS_HTML    = f"{WWW_ROOT}/html/servers.html"
CGI_BIN         = "acticentral.py"
INDEX_TEMPLATE  = f"{WWW_ROOT}/html/template.html"
PROJECT_TEMPLATE= f"{WWW_ROOT}/html/templateProject.html"
SERVERS_TEMPLATE= f"{WWW_ROOT}/html/templateServers.html"

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
ACTIS_RETIRE_P  = timedelta(days=7)
ACTIS_HIDE_P    = timedelta(days=1)
ACTIM_RETIRE_P  = timedelta(days=1)
ACTIM_HIDE_P    = timedelta(days=1)

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
        return {}
    try:
        data = json.load(registry)
    except json.JSONDecodeError:
        data = {}
    registry.close()
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
        result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", recipient], \
                                input = content, text=True, stderr=subprocess.STDOUT)
        printLog(f'Email sent to "{recipient}", sendmail returns {result.returncode}: {result.stdout}')
    else:
        try:
            admins = open(ADMINISTRATORS, "r")
        except OSError:
            result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", ADMIN_EMAIL], \
                                    input = content, text=True, stderr=subprocess.STDOUT)
            printLog(f'Email sent to "{ADMIN_EMAIL}", sendmail returns {result.returncode}: {result.stdout}')
        else:
            for email in admins:
                result = subprocess.run(["/usr/sbin/sendmail", "-F", "Acticentral", email.strip()], \
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

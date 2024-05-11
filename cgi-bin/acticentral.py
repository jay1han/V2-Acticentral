#!/usr/bin/python3

import sys, fcntl
from json import JSONDecodeError

from const import *

lock = open(LOCK_FILE, "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)
printLog("===================================================")

from registry import Registry
import actimetre
import actiserver
import project

Projects = project.initProjects()
Actiservers = actiserver.initActiservers()
Actimetres = actimetre.initActimetres()

def htmlIndex():
    os.truncate(INDEX_HTML, 0)
    writeTemplateSub(open(INDEX_HTML, "r+"), INDEX_TEMPLATE, {
        "{Actiservers}": Actiservers.htmlServers(picker=lambda s: NOW - s.lastUpdate < ACTIS_HIDE_P),
        "{Projects}"   : Projects.htmlProjects(),
        "{cgi-bin}"    : CGI_BIN,
    })

def checkAlerts():
    Actimetres.checkAlerts()
    Actiservers.checkAlerts()

def repoStats():
    Actimetres.repoStat()
    with open(STAT_FILE, "w") as stat:
        stat.write(NOW.strftime(TIMEFORMAT_DISP))

def loadRemotes():
    try:
        remoteFile = open(REMOTE_FILE, "r")
    except OSError:
        return {}
    try:
        remoteJson = json.load(remoteFile)
    except json.JSONDecodeError:
        return {}
    remote = {}
    for (key, value) in remoteJson.items():
        remote[int(key)] = int(value)
    return remote

def saveRemotes(remote):
    try:
        os.truncate(REMOTE_FILE, 0)
    except OSError:
        return
    with open(REMOTE_FILE, "r+") as remoteFile:
        json.dump(remote, remoteFile)
        
def remoteAction(actimId, command):
    remotes = loadRemotes()
    remotes[actimId] = command
    saveRemotes(remotes)

class ActisInfo:
    def __init__(self, index, serverId, rssi):
        self.index = index
        self.serverId = serverId
        self.rssi = rssi
        self.cpuIdle = Actiservers.getCpuIdle(serverId)

def assignActim(data):
    try:
        parseList = json.loads(data)
    except JSONDecodeError:
        return 101

    actisList = []
    index = 0
    for actisInfo in parseList:
        serverId = int(actisInfo['serverId'])
        rssi = int(actisInfo['rssi'])
        printLog(f'[{index:2d}] Actis{serverId:03d}: -{rssi}dB')
        actisList.append(ActisInfo(index, serverId, rssi))
        index += 1

    airNotRain = [actisInfo for actisInfo in actisList if actisInfo.rssi <= 37 and actisInfo.cpuIdle >= 0.5]
    if len(airNotRain) > 0:
        airNotRain.sort(key=lambda actis: actis.cpuIdle, reverse=True)
        return airNotRain[0].index
    sunNotMud = [actisInfo for actisInfo in actisList if actisInfo.rssi <= 64 and actisInfo.cpuIdle >= 0.8]
    if len(sunNotMud) > 0:
        sunNotMud.sort(key=lambda actis: actis.rssi)
        return sunNotMud[0].index
    waterAndCloud = [actisInfo for actisInfo in actisList if actisInfo.rssi <= 64 and actisInfo.cpuIdle >= 0.5]
    if len(waterAndCloud) > 0:
        waterAndCloud.sort(key=lambda actis: actis.cpuIdle, reverse=True)
        return waterAndCloud[0].index
    ### TODO: send alert
    actisList.sort(key=lambda actis: actis.rssi)
    return actisList[0].index

def plain(text=''):
    print("Content-type: text/plain\n\n")
    print(text)

def processForm(formId):
    if formId.startswith('project-'):
        Projects.processForm(formId, args)
    elif formId.startswith('actim-'):
        Actimetres.processForm(formId, args)
    else:
        print(f"Location:\\{INDEX_NAME}\n\n")

def checkSecret():
    if secret != SECRET_KEY:
        printLog(f"Wrong secret {secret} vs. {SECRET_KEY}")
        print(f"Wrong secret {secret}", file=sys.stdout)
        plain("Wrong secret")
        return False
    return True

def processAction():
    if action == 'actiserver' or action == 'actiserver3':
        if not checkSecret(): return
        serverId = int(args['serverId'][0])
        s = Actiservers.processUpdate(serverId, sys.stdin)

        if action == 'actiserver':
            plain(Registry.dump())
        else:
            if Registry.needUpdate(s.dbTime) or Projects.needUpdate(s.dbTime):
                printLog(f'{s.dbTime} needs update')
                plain('!')
            else:
                remotes = loadRemotes()
                for actimId in remotes.keys():
                    if actimId in s.actimetreList:
                        plain(f'+{actimId}:{remotes[actimId]}')
                        del remotes[actimId]
                        saveRemotes(remotes)
                        return
                plain('OK')

    elif action == 'registry':
        if not checkSecret(): return
#        serverId = int(args['serverId'][0])
        plain(Registry.dump())

    elif action == 'projects':
        if not checkSecret(): return
#        serverId = int(args['serverId'][0])
        plain(Projects.dump())

    elif action == 'report':
        if not checkSecret(): return
#        serverId  = int(args['serverId'][0])
        actimId = int(args['actimId'][0])
        message = sys.stdin.read()
        printLog(f'Actim{actimId:04d} {message}')
        Actimetres.setReportStr(actimId, message)
        plain('OK')
        
    elif action == 'clear-report':
        actimId = int(args['actimId'][0])
        printLog(f'Actim{actimId:04d} CLEAR {Actimetres.getReportStr(actimId)}')
        Actimetres.setReportStr(actimId, "")
        print(f"Location:\\{INDEX_NAME}\n\n")

    elif action == 'actimetre-new':
        if not checkSecret(): return
        mac       = args['mac'][0]
        boardType = args['boardType'][0]
        serverId  = int(args['serverId'][0])
        version   = args['version'][0]
        bootTime  = utcStrptime(args['bootTime'][0])

        actimId = Actimetres.new(mac, boardType, version, serverId, bootTime)
        Actiservers.addActim(serverId, actimId)
        plain(str(actimId))

    elif action == 'actimetre-off':
        if not checkSecret(): return
        actimId = int(args['actimId'][0])
        Actimetres.dies(actimId)
        plain("Ok")

    elif action == 'actimetre-query':
        if not checkSecret(): return
        assigned = assignActim(sys.stdin.read())
        printLog(f'Assigned {assigned}')
        plain(str(assigned))

    elif action == 'actimetre-removed':
        if not checkSecret(): return
        actimId = int(args['actimId'][0])
        Actimetres.forget(actimId)
        Actiservers.removeActim(actimId)
        plain("Ok")

    elif action.startswith('server-'):
        Actiservers.processAction(action, args)

    elif action.startswith('actim-'):
        Actimetres.processAction(action, args)

    elif action.startswith('remote-'):
        command = 0
        if action   == 'remote-button' : command = 0x10
        elif action == 'remote-sync'   : command = 0x20
        elif action == 'remote-stop'   : command = 0x30
        elif action == 'remote-restart': command = 0xF0
        remoteAction(int(args['actimId'][0]), command)
        print(f"Location:\\{INDEX_NAME}\n\n")

    elif action.startswith('project-'):
        Projects.processAction(action, args)

    elif action == 'submit':
        formId = args['formId'][0]
        printLog(f"Submitted form {formId}")
        processForm(formId)

    elif action == 'cancel':
        print(f"Location:\\{INDEX_NAME}\n\n")


def saveAll():
    Registry.save()
    Actimetres.save()
    Actiservers.save()
    Projects.save()
    htmlIndex()

import argparse
cmdparser = argparse.ArgumentParser()
cmdparser.add_argument('action', default='', nargs='?')
cmdargs = cmdparser.parse_args()
if cmdargs.action == 'prepare-stats':
    printLog("Timer prepare-stats")
    checkAlerts()
    repoStats()
    saveAll()
    lock.close()
    sys.exit(0)

import urllib.parse
qs = os.environ['QUERY_STRING']
client = os.environ['REMOTE_ADDR']
printLog(f"From {client}: {qs}")

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
    if 'secret' in args.keys():
        secret = args['secret'][0]
    else:
        secret = "YouDontKnowThis"
    processAction()
    saveAll()

lock.close()

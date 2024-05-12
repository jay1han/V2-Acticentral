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

Actimetres = actimetre.initActimetres()
Actiservers = actiserver.initActiservers()
Projects = project.initProjects()

def htmlIndex():
    writeTemplateSub(open(INDEX_HTML, "w"), INDEX_TEMPLATE, {
        "{Projects}"   : Projects.htmlProjects(picker=lambda p: p.projectId != 0),
        "{Actiservers}": Actiservers.html(picker=lambda s: len(s.actimetreList) > 0),
    })

def checkAlerts():
    Actimetres.checkAlerts()
    Actiservers.checkAlerts()

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
    with open(REMOTE_FILE, "w") as remoteFile:
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

    alertText = ""
    actisList = []
    index = 0
    for actisInfo in parseList:
        serverId = int(actisInfo['serverId'])
        rssi = int(actisInfo['rssi'])
        actisData = ActisInfo(index, serverId, rssi)
        printLog(f'[{index:2d}] Actis{serverId:03d} ({actisData.cpuIdle:.1f}%): -{rssi}dB')
        actisList.append(actisData)
        alertText += f"Actis{serverId:03d} ({actisData.cpuIdle:.1f}% idle) at -{rssi}dB\n"
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

    actisList.sort(key=lambda actis: actis.rssi)
    sendEmail("", "Rainy and Muddy",
              "An Actimetre is trying to connect, only sees these Servers:\n" +
              alertText +
              f"\nAssigned Actis{actisList[0].serverId:03d}")

    return actisList[0].index

def processForm(formId):
    if formId.startswith('project-'):
        Projects.processForm(formId, args)
    elif formId.startswith('actim-'):
        Actimetres.processForm(formId, args)
    elif formId.startswith('server-'):
        Actiservers.processForm(formId, args)
    else:
        print(f"Location:\\{INDEX_NAME}\n\n")

def checkSecret():
    if secret != SECRET_KEY:
        printLog(f"Wrong secret {secret} vs. {SECRET_KEY}")
        print(f"Wrong secret {secret}", file=sys.stdout)
        print("Status: 401\n\n")
        return False
    return True

def processAction():
    printLog(f"Process action {action}")
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
        actimId = int(args['actimId'][0])
        if action   == 'remote-switch' : command = 0x10
        elif action == 'remote-sync'   : command = 0x20
        elif action == 'remote-stop'   :
            command = 0x30
            Actimetres.stop(actimId)
        elif action == 'remote-restart': command = 0xF0
        remoteAction(actimId, command)
        print("Status: 205\n\n")

    elif action.startswith('project-'):
        Projects.processAction(action, args)

    elif action == 'submit':
        formId = args['formId'][0]
        printLog(f"Submitted form {formId}")
        processForm(formId)

    else: print("Status: 205\n\n")

def saveAll():
    Registry.save()
    Actimetres.save()
    Actiservers.save()
    Projects.save()
    #TODO refine dirtiness
    if Projects.dirty or Actiservers.dirty: htmlIndex()

import argparse
cmdparser = argparse.ArgumentParser()
cmdparser.add_argument('action', default='', nargs='?')
cmdargs = cmdparser.parse_args()
if cmdargs.action == 'prepare-stats':
    printLog("Timer prepare-stats")
    checkAlerts()
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

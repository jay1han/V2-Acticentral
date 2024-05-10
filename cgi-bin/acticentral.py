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

def htmlUpdate():
    Actiservers.htmlWriteServers()

    os.truncate(INDEX_HTML, 0)
    writeTemplateSub(open(INDEX_HTML, "r+"), INDEX_TEMPLATE, {
        "{Actiservers}": Actiservers.htmlServers(picker=lambda s: NOW - s.lastUpdate < ACTIS_HIDE_P),
        "{Projects}": Projects.htmlProjects(),
        "{Updated}": LAST_UPDATED,
        "{Version}": VERSION_STR,
        "{cgi-bin}": CGI_BIN,
    })

def checkAlerts():
    Actimetres.checkAlerts()
    Actiservers.checkAlerts()

def repoStats():
    Actimetres.repoStat()

    with open(STAT_FILE, "w") as stat:
        stat.write(NOW.strftime(TIMEFORMAT_DISP))
    htmlUpdate()
    
def actimChangeProject(actimId):
    print("Content-type: text/html\n\n")
    writeTemplateSub(sys.stdout, f"{HTML_DIR}/formActim.html", {
        "{actimId}": str(actimId),
        "{actimName}": Actimetres.getName(actimId),
        "{actimInfo}": Actimetres.htmlInfo(actimId),
        "{htmlProjectList}": Projects.htmlChoice(Actimetres.getProjectId(actimId)),
    })

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
    password = args['password'][0]
    if password != SECRET_KEY:
        print("Location:\\password.html\n\n")
        return
    
    if formId.startswith('project-'):
        Projects.processForm(formId, args)

    elif formId.startswith('actim-'):
        Actimetres.processForm(formId, args)

    elif formId == 'project-remove':
        Projects.deleteProject(int(args['projectId'][0]))
        print(f"Location:\\index.html\n\n")

    else:
        print("Location:\\index.html\n\n")

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
            
        printLog(f"Actis{serverId} alive")
        s = Actiservers.processAction(serverId, sys.stdin)

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
        htmlUpdate()
        plain('OK')
        
    elif action == 'clear-report':
        actimId = int(args['actimId'][0])
        printLog(f'Actim{actimId:04d} CLEAR {Actimetres.getReportStr(actimId)}')
        Actimetres.setReportStr(actimId, "")
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'actimetre-new':
        if not checkSecret(): return
        mac       = args['mac'][0]
        boardType = args['boardType'][0]
        serverId  = int(args['serverId'][0])
        version   = args['version'][0]
        bootTime  = utcStrptime(args['bootTime'][0])

        actimId = Actimetres.new(mac, boardType, version, serverId, bootTime)
        Actiservers.addActim(serverId, actimId)
        htmlUpdate()
        plain(str(actimId))

    elif action == 'actimetre-off':
        if not checkSecret(): return
#        serverId = int(args['serverId'][0])
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
#        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        Actimetres.forget(actimId)
        Actiservers.removeActim(actimId)

        htmlUpdate()
        plain("Ok")

    elif action == 'actim-change-project':
        actimId = int(args['actimId'][0])
        actimChangeProject(actimId)

    elif action == 'actim-cut-graph':
        actimId = int(args['actimId'][0])
        Actimetres.cutGraph(actimId)
        if args.get('projectId') is not None:
            print("Location:\\project{int(args['projectId'][0]):03d}.html\n\n")
        else:
            print("Location:\\index.html\n\n")

    elif action == 'remote-button':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x10)
        print("Location:\\index.html\n\n")

    elif action == 'actim-sync':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x20)
        print("Location:\\index.html\n\n")

    elif action == 'actim-forget':
        actimId = int(args['actimId'][0])
        Actimetres.forget(actimId)
        print("Location:\\index.html\n\n")

    elif action == 'actim-decouple':
        actimId = int(args['actimId'][0])
#        serverId = int(args['serverId'][0])
        Actimetres.forget(actimId)
        print("Location:\\index.html\n\n")

    elif action == 'remote-restart':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0xF0)
        print("Location:\\index.html\n\n")

    elif action == 'actim-stop':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x30)
        print("Location:\\index.html\n\n")

    elif action == 'actim-retire':
        Actimetres.formRetire(int(args['actimId'][0]))

    elif action == 'server-retire':
        serverId = int(args['serverId'][0])
        Actiservers.delete(serverId)
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'project-change-info':
        Projects.formChangeInfo(int(args['projectId'][0]))

    elif action == 'project-edit-info':
        Projects.formEditInfo(int(args['projectId'][0]))

    elif action == 'project-create':
        print("Location:\\formCreate.html\n\n")

    elif action == 'project-remove':
        Projects.formRemove(int(args['projectId'][0]))

    elif action == 'submit':
        formId = args['formId'][0]
        printLog(f"Submitted form {formId}")
        processForm(formId)

    elif action == 'cancel':
        print("Location:\\index.html\n\n")
        
import argparse
cmdparser = argparse.ArgumentParser()
cmdparser.add_argument('action', default='', nargs='?')
cmdargs = cmdparser.parse_args()
if cmdargs.action == 'prepare-stats':
    printLog("Timer prepare-stats")
    checkAlerts()
    repoStats()
    htmlUpdate()
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

lock.close()

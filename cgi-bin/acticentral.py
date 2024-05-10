#!/usr/bin/python3

import sys, fcntl
from json import JSONDecodeError

from const import *

lock = open(LOCK_FILE, "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)
printLog("===================================================")

import globals as x
from project import Projects
from actimetre import Actimetre, loadActimetres
from actiserver import Actiservers

x.loadRegistry()
loadActimetres()

def htmlUpdate():
    Actiservers.htmlUpdate()

    htmlTemplate = open(INDEX_TEMPLATE, "r").read()
    htmlOutput = htmlTemplate\
        .replace("{Actiservers}", Actiservers.html(picker=lambda s: NOW - s.lastUpdate < ACTIS_HIDE_P))\
        .replace("{Projects}", Projects.html())\
        .replace("{Updated}", LAST_UPDATED)\
        .replace("{Version}", VERSION_STR)\
        .replace("{cgi-bin}", CGI_BIN)
    
    os.truncate(INDEX_HTML, 0)
    with open(INDEX_HTML, "r+") as html:
        print(htmlOutput, file=html)

def checkAlerts():
    save = False
    for a in x.Actimetres.values():
        if a.isDead == 1 and (NOW - a.lastSeen) > ACTIM_ALERT1:
            a.alert()
            a.isDead = 2
            save = True
        elif a.isDead == 2 and (NOW - a.lastSeen) > ACTIM_ALERT2:
            a.alert()
            a.isDead = 3
            save = True
    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})

    Actiservers.checkAlerts()

def repoStats():
    Projects.clearRepos()

    save = False
    saveP = False
    for a in x.Actimetres.values():
        if NOW - a.lastReport > ACTIM_HIDE_P:
            continue
        if a.drawGraphMaybe():
            save = True
        saveP = Projects.addActim(a)

    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
    if saveP:
        Projects.save()

    with open(STAT_FILE, "w") as stat:
        stat.write(NOW.strftime(TIMEFORMAT_DISP))

    htmlUpdate()
    
def projectChangeInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-change-info")\
              .replace("{projectTitle}", Projects.get(projectId).name())\
              .replace("{projectOwner}", Projects.get(projectId).owner)\
              .replace("{projectId}", str(projectId)))

def projectEditInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-edit-info")\
              .replace("{projectTitle}", Projects.get(projectId).name())\
              .replace("{projectOwner}", Projects.get(projectId).owner)\
              .replace("{projectId}", str(projectId)))

def actimChangeProject(actimId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formActim.html") as form:
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", x.Actimetres[actimId].actimName())\
              .replace("{actimInfo}", x.Actimetres[actimId].htmlInfo())\
              .replace("{htmlProjectList}", Projects.htmlList(x.Actimetres[actimId].projectId)))

def removeProject(projectId):
    print("Content-type: text/html\n\n")

    if len(Projects.get(projectId).actimetreList) == 0:
        actimList = "(no Actimetres assigned to this project)\n"
    else:
        actimList = ""
        for actimId in Projects.get(projectId).actimetreList:
            if x.Actimetres.get(actimId) is not None:
                actimList += f'<li>{x.Actimetres[actimId].htmlCartouche()}</li>\n'
            
    with open(f"{HTML_DIR}/formRemove.html") as form:
        print(form.read()\
              .replace("{projectId}", str(projectId))\
              .replace("{projectTitle}", Projects.get(projectId).name())\
              .replace("{actimetreList}", actimList))

def retireActim(actimId):
    print("Content-type: text/html\n\n")

    a = x.Actimetres[actimId]
    if a.projectId > 0:
        ownerStr = 'the name of the owner'
    else:
        ownerStr = '"CONFIRM"'
    with open(f"{HTML_DIR}/formRetire.html") as form:
        repoNumsStr = ''
        if a.repoNums > 0:
            repoNumsStr = f'{a.repoNums} files, '
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", a.actimName())\
              .replace("{mac}", a.mac)\
              .replace("{boardType}", a.boardType)\
              .replace("{repoNums}", repoNumsStr)\
              .replace("{repoSize}", printSize(a.repoSize))\
              .replace("{owner}", ownerStr)\
              .replace("{projectTitle}", Projects.get(a.projectId).name()))

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
    
    if formId == 'project-change-info':
        projectId = int(args['projectId'][0])
        title = args['title'][0]
        owner = args['owner'][0]
        email = args['email'][0]
        printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")

        if title != "" and owner != "":
            Projects.set(projectId, title, owner, email)
            Projects.save()
            htmlUpdate()
        print(f'Location:\\index.html\n\n')

    elif formId == 'project-edit-info':
        projectId = int(args['projectId'][0])
        title = args['title'][0]
        owner = args['owner'][0]
        email = args['email'][0]
        printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")

        if title != "" and owner != "":
            Projects.set(projectId, title, owner, email)
            Projects.save()
            htmlUpdate()
        print(f"Location:\\project{projectId:02d}.html\n\n")

    elif formId == 'actim-change-project':
        actimId = int(args['actimId'][0])
        projectId = int(args['projectId'][0])
        oldProject = x.Actimetres[actimId].projectId
        printLog(f"Changing {actimId} from {oldProject} to {projectId}")

        Projects.removeActim(oldProject, actimId)
        Projects.get(projectId).actimetreList.add(actimId)
        x.Actimetres[actimId].projectId = projectId
        Projects.save()
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif formId == 'create-project':
        title = args['title'][0]
        owner = args['owner'][0]
        printLog(f"Create new project with data: {title}, {owner}")

        if title != "" and owner != "":
            Projects.new(title, owner)
            Projects.save()
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif formId == 'retire-actim':
        actimId = int(args['actimId'][0])
        owner = args['owner'][0]

        a = x.Actimetres.get(actimId)
        if a is not None and \
           (a.projectId == 0 and owner == 'CONFIRM') or \
           Projects.get(a.projectId).owner == owner:
            printLog(f"Retire Actimetre{actimId:04d} from {Projects.get(a.projectId).name()}")
            Actiservers.removeActim(actimId)
            Projects.removeActim(actimId)

            del x.Registry[x.Actimetres[actimId].mac]
            x.saveRegistry()
            del x.Actimetres[actimId]
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            try:
                os.remove(f"{HISTORY_DIR}/Actim{actimId:04d}.hist")
            except FileNotFoundError: pass
            htmlUpdate()
                
        print("Location:\\index.html\n\n")

    elif formId == 'remove-project':
        projectId = int(args['projectId'][0])
        if projectId != 0:
            for a in Projects.get(projectId).actimetreList:
                if x.Actimetres.get(a) is not None:
                    x.Actimetres[a].projectId = 0
            Projects.delete(projectId)
            Projects.save()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            repoStats()
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
        htmlUpdate()

        if action == 'actiserver':
            plain(json.dumps(x.Registry))
        else:
            if x.RegistryTime > s.dbTime.replace(tzinfo=timezone.utc) \
               or Projects.fileTime > s.dbTime.replace(tzinfo=timezone.utc):
                printLog(f'{s.dbTime} < {Projects.fileTime}, needs update')
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
        plain(json.dumps(x.Registry))

    elif action == 'projects':
        if not checkSecret(): return
#        serverId = int(args['serverId'][0])
        plain()
        Projects.list()

    elif action == 'report':
        if not checkSecret(): return
#        serverId  = int(args['serverId'][0])
        actimId = int(args['actimId'][0])
        if x.Actimetres.get(actimId) is not None:
            message = sys.stdin.read()
            printLog(f'Actim{actimId:04d} {message}')
            x.Actimetres[actimId].reportStr = message
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
        plain('OK')
        
    elif action == 'clear-report':
        actimId = int(args['actimId'][0])
        if x.Actimetres.get(actimId) is not None:
            printLog(f'Actim{actimId:04d} CLEAR {x.Actimetres[actimId].reportStr}')
            x.Actimetres[actimId].reportStr = ""
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'actimetre-new':
        if not checkSecret(): return
        mac       = args['mac'][0]
        boardType = args['boardType'][0]
        serverId  = int(args['serverId'][0])
        version   = args['version'][0]
        bootTime  = utcStrptime(args['bootTime'][0])

        s = Actiservers.get(serverId, update=True)
        if x.Registry.get(mac) is None:
            actimList = [r for r in x.Registry.values()]
            actimList.sort()
            actimId = len(actimList) + 1
            for newId in range(1, len(actimList) + 1):
                if not newId in actimList:
                    actimId = newId
                    break
            x.Registry[mac] = actimId
            printLog(f"Allocated new Actim{actimId:04d} for {mac}")
            x.saveRegistry()
            responseStr = f"+{actimId}"
        else:
            actimId = x.Registry[mac]
            printLog(f"Found known Actim{actimId:04d} for {mac}")
            responseStr = str(actimId)

        a = Actimetre(actimId, mac, boardType, version, serverId, bootTime=NOW, lastSeen=NOW, lastReport=NOW, isDead=0)
        printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")

        s.actimetreList.add(actimId)
        x.Actimetres[actimId] = a
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
        Actiservers.save()
        htmlUpdate()
        plain(responseStr)

    elif action == 'actimetre-off':
        if not checkSecret(): return
#        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = x.Actimetres.get(actimId)
        if a is not None:
            a.dies()
#            x.Actiservers[serverId].actimetreList.remove(actimId)
#            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in x.Actiservers.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            htmlUpdate()
        plain("Ok")

    elif action == 'actimetre-query':
        if not checkSecret(): return
        assigned = assignActim(sys.stdin.read())
        printLog(f'Assigned {assigned}')
        plain(str(assigned))

    elif action == 'actimetre-removed':
        if not checkSecret(): return
        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = x.Actimetres.get(actimId)
        if a is not None:
            a.serverId = 0
            a.repoNums = 0
            a.repoSize = 0
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})

        Actiservers.removeActim(actimId, serverId)

        htmlUpdate()
        plain("Ok")

    elif action == 'actim-change-project':
        actimId = int(args['actimId'][0])
        actimChangeProject(actimId)

    elif action == 'actim-cut-graph':
        actimId = int(args['actimId'][0])
        if x.Actimetres.get(actimId) is not None:
            x.Actimetres[actimId].cutHistory()
            x.Actimetres[actimId].drawGraph()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            htmlUpdate()
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
        if x.Actimetres.get(actimId) is not None:
            x.Actimetres[actimId].forgetData()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'actim-decouple':
        actimId = int(args['actimId'][0])
        serverId = int(args['serverId'][0])
        if x.Actimetres.get(actimId) is not None:
            x.Actimetres[actimId].forgetData()
            printLog(f"Removed Actim{actimId:04d} from Actis{serverId:04d}")
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in x.Actimetres.values()})
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'remote-restart':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0xF0)
        print("Location:\\index.html\n\n")

    elif action == 'actim-stop':
        actimId = int(args['actimId'][0])
        remoteAction(actimId, 0x30)
        print("Location:\\index.html\n\n")

    elif action == 'retire-actim':
        actimId = int(args['actimId'][0])
        retireActim(actimId)

    elif action == 'retire-server':
        serverId = int(args['serverId'][0])
        Actiservers.delete(serverId)
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'project-change-info':
        projectId = int(args['projectId'][0])
        projectChangeInfo(projectId)

    elif action == 'project-edit-info':
        projectId = int(args['projectId'][0])
        projectEditInfo(projectId)

    elif action == 'create-project':
        print("Location:\\formCreate.html\n\n")

    elif action == 'remove-project':
        projectId = int(args['projectId'][0])
        removeProject(projectId)

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

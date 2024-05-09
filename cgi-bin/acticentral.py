#!/usr/bin/python3

import sys
import fcntl
from globals import *

lock = open(LOCK_FILE, "w+")
fcntl.lockf(lock, fcntl.LOCK_EX)

if 'Projects' not in dir():
    from project import *
if 'Actiservers' not in dir():
    from actiserver import *
if 'Actimetres' not in dir():
    from actimetre import *

SECRET_KEY = initRegistry()
initActimetres()
initActiservers()
initProjects()

def htmlUpdate():
    global LAST_UPDATED
    LAST_UPDATED = NOW.strftime(TIMEFORMAT_DISP)
    
#    htmlActiservers()
#    htmlProjects()
    htmlAllServers()
    
    htmlTemplate = open(INDEX_TEMPLATE, "r").read()
    htmlOutput = htmlTemplate\
        .replace("{Actiservers}", HTML_ACTISERVERS)\
        .replace("{Projects}", HTML_PROJECTS)\
        .replace("{Updated}", LAST_UPDATED)\
        .replace("{Version}", VERSION_STR)\
        .replace("{cgi-bin}", CGI_BIN)
    
    os.truncate(INDEX_HTML, 0)
    with open(INDEX_HTML, "r+") as html:
        print(htmlOutput, file=html)

def checkAlerts():
    save = False
    for a in Actimetres.values():
        if a.isDead == 1 and (NOW - a.lastSeen) > ACTIM_ALERT1:
            a.alert()
            a.isDead = 2
            save = True
        elif a.isDead == 2 and (NOW - a.lastSeen) > ACTIM_ALERT2:
            a.alert()
            a.isDead = 3
            save = True
    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})

    save = False
    for s in Actiservers.values():
        if s.isDown == 0 and (NOW - s.lastUpdate) > ACTIS_ALERT1:
            s.alert()
            s.isDown = 1
            save = True
        elif s.isDown == 1 and (NOW - s.lastUpdate) > ACTIS_ALERT2:
            s.alert()
            s.isDown = 2
            save = True
        elif s.isDown == 2 and (NOW - s.lastUpdate) > ACTIS_ALERT3:
            s.alert()
            s.isDown = 3
            save = True
    if save:
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

def repoStats():
    for p in Projects.values():
        p.repoSize = 0
        p.repoNums = 0

    save = False
    saveP = False
    for a in Actimetres.values():
        if NOW - a.lastReport > ACTIM_HIDE_P:
            continue
        if a.drawGraphMaybe():
            save = True
        if Projects.get(a.projectId) is None:
            Projects[a.projectId] = Project(a.projectId, "Not assigned", "No owner")
            saveP = True
        saveP = Projects[a.projectId].addActim(a.actimId)
        Projects[a.projectId].repoNums += a.repoNums
        Projects[a.projectId].repoSize += a.repoSize

    if save:
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
    if saveP:
        dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

    with open(STAT_FILE, "w") as stat:
        stat.write(NOW.strftime(TIMEFORMAT_DISP))

    htmlUpdate()
    
def projectChangeInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-change-info")\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{projectOwner}", Projects[projectId].owner)\
              .replace("{projectId}", str(projectId)))

def projectEditInfo(projectId):
    print("Content-type: text/html\n\n")

    with open(f"{HTML_DIR}/formProject.html") as form:
        print(form.read()\
              .replace("{project-change-info}", "project-edit-info")\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{projectOwner}", Projects[projectId].owner)\
              .replace("{projectId}", str(projectId)))

def actimChangeProject(actimId):
    print("Content-type: text/html\n\n")

    htmlProjectList = ""
    for p in Projects.values():
        htmlProjectList += f'<input id="{p.projectId}" type="radio" name="projectId" value="{p.projectId}"'
        if p.projectId == Actimetres[actimId].projectId:
            htmlProjectList += ' checked="true"'
        htmlProjectList += f'><label for="{p.projectId}">{p.name()} ({p.owner})</label><br>\n'

    with open(f"{HTML_DIR}/formActim.html") as form:
        print(form.read()\
              .replace("{actimId}", str(actimId))\
              .replace("{actimName}", Actimetres[actimId].actimName())\
              .replace("{actimInfo}", Actimetres[actimId].htmlInfo())\
              .replace("{htmlProjectList}", htmlProjectList))

def removeProject(projectId):
    print("Content-type: text/html\n\n")

    actimList = ""
    if len(Projects[projectId].actimetreList) == 0:
        actimList = "(no Actimetres assigned to this project)\n"
    else:
        actimList = ""
        for actimId in Projects[projectId].actimetreList:
            if Actimetres.get(actimId) is not None:
                actimList += f'<li>{Actimetres[actimId].htmlCartouche()}</li>\n'
            
    with open(f"{HTML_DIR}/formRemove.html") as form:
        print(form.read()\
              .replace("{projectId}", str(projectId))\
              .replace("{projectTitle}", Projects[projectId].name())\
              .replace("{actimetreList}", actimList))

def retireActim(actimId):
    print("Content-type: text/html\n\n")

    a = Actimetres[actimId]
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
              .replace("{projectTitle}", Projects[a.projectId].name()))

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
        self.cpuIdle = 0.0
        if Actiservers.get(serverId) is not None:
            self.cpuIdle = Actiservers[serverId].cpuIdle

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
        airNotRain.sort(key=lambda actisInfo: actisInfo.cpuIdle, reverse=True)
        return airNotRain[0].index
    sunNotMud = [actisInfo for actisInfo in actisList if actisInfo.rssi <= 64 and actisInfo.cpuIdle >= 0.8]
    if len(sunNotMud) > 0:
        sunNotMud.sort(key=lambda actisInfo: actisInfo.rssi)
        return sunNotMud[0].index
    waterAndCloud = [actisInfo for actisInfo in actisList if actisInfo.rssi <= 64 and actisInfo.cpuIdle >= 0.5]
    if len(waterAndCloud) > 0:
        waterAndCloud.sort(key=lambda actisInfo: actisInfo.cpuIdle, reverse=True)
        return waterAndCloud[0].index
    ### TODO: send alert
    actisList.sort(key=lambda actisInfo: actisInfo.rssi)
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
            Projects[projectId].title = title
            Projects[projectId].owner = owner
            Projects[projectId].email = email
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            htmlUpdate()
        print(f'Location:\\index.html\n\n')

    elif formId == 'project-edit-info':
        projectId = int(args['projectId'][0])
        title = args['title'][0]
        owner = args['owner'][0]
        email = args['email'][0]
        printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")

        if title != "" and owner != "":
            Projects[projectId].title = title
            Projects[projectId].owner = owner
            Projects[projectId].email = email
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            htmlUpdate()
        print(f"Location:\\project{projectId:02d}.html\n\n")

    elif formId == 'actim-change-project':
        actimId = int(args['actimId'][0])
        projectId = int(args['projectId'][0])
        oldProject = Actimetres[actimId].projectId
        printLog(f"Changing {actimId} from {oldProject} to {projectId}")

        Projects[oldProject].actimetreList.remove(actimId)
        Projects[projectId].actimetreList.add(actimId)
        Actimetres[actimId].projectId = projectId
        dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        htmlUpdate()
        print("Location:\\index.html\n\n")

    elif formId == 'create-project':
        title = args['title'][0]
        owner = args['owner'][0]
        printLog(f"Create new project with data: {title}, {owner}")

        if title != "" and owner != "":
            projectId = 1
            while projectId in set(Projects.keys()):
                projectId += 1
            Projects[projectId] = Project(projectId, title, owner)
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif formId == 'retire-actim':
        actimId = int(args['actimId'][0])
        owner = args['owner'][0]

        a = Actimetres.get(actimId)
        if a is not None and \
           (a.projectId == 0 and owner == 'CONFIRM') or \
           (Projects.get(a.projectId) is not None and Projects[a.projectId].owner == owner):

            printLog(f"Retire Actimetre{actimId:04d} from {Projects[a.projectId].name()}")
            save = False
            for s in Actiservers.values():
                if actimId in s.actimetreList:
                    s.actimetreList.remove(actimId)
                    save = True
            if save:
                dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})

            save = False
            for p in Projects.values():
                if actimId in p.actimetreList:
                    p.actimetreList.remove(actimId)
                    save = True
            if save:
                dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})

            del Registry[Actimetres[actimId].mac]
            saveRegistry()
            del Actimetres[actimId]
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            try:
                os.remove(f"{HISTORY_DIR}/Actim{actimId:04d}.hist")
            except FileNotFoundError: pass
            htmlUpdate()
                
        print("Location:\\index.html\n\n")

    elif formId == 'remove-project':
        projectId = int(args['projectId'][0])
        if projectId != 0:
            for a in Projects[projectId].actimetreList:
                if Actimetres.get(a) is not None:
                    Actimetres[a].projectId = 0
            del Projects[projectId]
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            repoStats()
        print(f"Location:\\index.html\n\n")

    else:
        print("Location:\\index.html\n\n")

def checkSecret():
    if secret != SECRET_KEY:
        printLog(f"Wrong secret {secret} vs. {SECRET_KEY}")
        print(f"Wrong secret {secret}", file=sys.stdout)
        plain("Wrong secret")
        return

def processAction():
    if action == 'actiserver' or action == 'actiserver3':
        checkSecret()
        serverId = int(args['serverId'][0])
            
        if serverId != 0:
            printLog(f"Actis{serverId} alive")
            thisServer = Actiserver(serverId).fromD(json.load(sys.stdin), actual=True)
            if Actiservers.get(serverId) is not None:
                s = Actiservers[serverId]
                thisServer.diskLow = s.diskLow
                if thisServer.diskLow == 0:
                    if thisServer.diskSize > 0 and thisServer.diskFree < thisServer.diskSize // 10:
                        thisServer.diskLow = 1
                        thisServer.alertDisk()
                elif thisServer.diskLow == 1:
                    if thisServer.diskSize > 0 and thisServer.diskFree < thisServer.diskSize // 20:
                        thisServer.diskLow = 2
                        thisServer.alertDisk()
                else:
                    if thisServer.diskSize > 0 and thisServer.diskFree > thisServer.diskSize // 10:
                        thisServer.diskLow = 0
            Actiservers[serverId] = thisServer
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()

        remotes = loadRemotes()
        for actimId in remotes.keys():
            if actimId in thisServer.actimetreList:
                plain(f'+{actimId}:{remotes[actimId]}')
                del remotes[actimId]
                saveRemotes(remotes)
                return

        if action == 'actiserver':
            plain(json.dumps(Registry))
        else:
            if RegistryTime > thisServer.dbTime.replace(tzinfo=timezone.utc) \
               or ProjectsTime > thisServer.dbTime.replace(tzinfo=timezone.utc):
                printLog(f'{thisServer.dbTime} < {ProjectsTime}, needs update')
                plain('!')
            else:
                plain('OK')

    elif action == 'registry':
        checkSecret()
#        serverId = int(args['serverId'][0])
        plain(json.dumps(Registry))

    elif action == 'projects':
        checkSecret()
#        serverId = int(args['serverId'][0])
        plain()
        listProjects()

    elif action == 'report':
        checkSecret()
        serverId  = int(args['serverId'][0])
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            message = sys.stdin.read()
            printLog(f'Actim{actimId:04d} {message}')
            Actimetres[actimId].reportStr = message
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        plain('OK')
        
    elif action == 'clear-report':
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            printLog(f'Actim{actimId:04d} CLEAR {Actimetres[actimId].reportStr}')
            Actimetres[actimId].reportStr = ""
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
        print("Location:\\index.html\n\n")

    elif action == 'actimetre-new':
        checkSecret()
        mac       = args['mac'][0]
        boardType = args['boardType'][0]
        serverId  = int(args['serverId'][0])
        version   = args['version'][0]
        bootTime  = utcStrptime(args['bootTime'][0])

        thisServer = Actiservers.get(serverId)
        if thisServer is None:
            thisServer = Actiserver(serverId, lastUpdate=NOW)
            Actiservers[serverId] = thisServer
        else:
            thisServer.lastUpdate = NOW

        if Registry.get(mac) is None:
            actimList = [r for r in Registry.values()]
            actimList.sort()
            actimId = len(actimList) + 1
            for newId in range(1, len(actimList) + 1):
                if not newId in actimList:
                    actimId = newId
                    break
            Registry[mac] = actimId
            printLog(f"Allocated new Actim{actimId:04d} for {mac}")
            saveRegistry()
            responseStr = f"+{actimId}"
        else:
            actimId = Registry[mac]
            printLog(f"Found known Actim{actimId:04d} for {mac}")
            responseStr = str(actimId)

        a = Actimetre(actimId, mac, boardType, version, serverId, bootTime=NOW, lastSeen=NOW, lastReport=NOW, isDead=0)
        printLog(f"Actim{a.actimId:04d} for {mac} is type {boardType} booted at {bootTime}")

        thisServer.actimetreList.add(actimId)
        Actimetres[actimId] = a
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        htmlUpdate()
        plain(responseStr)

    elif action == 'actimetre-off':
        checkSecret()
        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = Actimetres.get(actimId)
        if a is not None:
            a.dies()
#            Actiservers[serverId].actimetreList.remove(actimId)
#            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
        plain("Ok")

    elif action == 'actimetre-query':
        checkSecret()
        assigned = assignActim(sys.stdin.read())
        printLog(f'Assigned {assigned}')
        plain(str(assigned))

    elif action == 'actimetre-removed':
        checkSecret()
        serverId = int(args['serverId'][0])
        actimId = int(args['actimId'][0])

        a = Actimetres.get(actimId)
        if a is not None:
            a.serverId = 0
            a.repoNums = 0
            a.repoSize = 0
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})

        s = Actiservers.get(serverId)
        if s is not None:
            s.actimetreList.remove(actimId)
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
            
        htmlUpdate()
        plain("Ok")

    elif action == 'actim-change-project':
        actimId = int(args['actimId'][0])
        actimChangeProject(actimId)

    elif action == 'actim-cut-graph':
        actimId = int(args['actimId'][0])
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].cutHistory()
            Actimetres[actimId].drawGraph()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
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
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].forgetData()
            dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
            htmlUpdate()
            dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
        print("Location:\\index.html\n\n")

    elif action == 'actim-decouple':
        actimId = int(args['actimId'][0])
        serverId = int(args['serverId'][0])
        if Actimetres.get(actimId) is not None:
            Actimetres[actimId].forgetData()
        if Actiservers.get(serverId) is not None and actimId in Actiservers[serverId].actimetreList:
            Actiservers[serverId].actimetreList.remove(actimId)
            printLog(f"Removed Actim{actimId:04d} from Actis{serverId:04d}")
        dumpData(ACTIMETRES, {int(a.actimId):a.toD() for a in Actimetres.values()})
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
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
        del Actiservers[serverId]
        htmlUpdate()
        dumpData(ACTISERVERS, {int(s.serverId):s.toD() for s in Actiservers.values()})
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
remote = os.environ['REMOTE_ADDR']
printLog(f"From {remote}: {qs}")

args = urllib.parse.parse_qs(qs, keep_blank_values=True)
if 'action' in args.keys():
    action = args['action'][0]
    if 'secret' in args.keys():
        secret = args['secret'][0]
    else:
        secret = "YouDontKnowThis"
    processAction()

lock.close()

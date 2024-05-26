import sys
from const import *
import actimetre, actiserver

class Project:
    def __init__(self,
                 projectId=999,
                 title="Error",
                 owner="Nobody",
                 email="actimetre@gmail.com",
                 actimetreList=None):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.email         = email
        if actimetreList is None:
            self.actimetreList = set()
        else:
            self.actimetreList = actimetreList
        self.serverList   = set()
        self.dirty        = True        # refresh inner HTML (actim changed)
        self.stale        = True        # refresh outer HTML (actim or server changed)

    def __str__(self):
        Actimetres = actimetre.Actimetres
        string = f'Project{self.projectId:02d}({self.title})'
        for actimId in self.actimetreList:
            string += f' - {Actimetres.str(actimId)}'
        return string

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'email'         : self.email,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId     = int(d['projectId'])
        self.title         = d['title']
        self.owner         = d['owner']
        self.email         = d['email']
        self.actimetreList = set([int(actimId) for actimId in d['actimetreList']])
        self.dirty         = False
        self.stale         = False
        return self

    def addActim(self, actimId: int):
        if actimId not in self.actimetreList:
            self.actimetreList.add(actimId)
            self.stale = True
            printLog(f'Added Actim{actimId:04d} to Project{self.projectId:02d}')
            return True
        else: return False

    def removeActim(self, actimId: int):
        if actimId in self.actimetreList:
            self.actimetreList.remove(actimId)
            self.dirty = True
            return True
        else: return False

    def name(self):
        return f"{self.title} (#{self.projectId:02d})"

    def htmlWrite(self):
        Actimetres = actimetre.Actimetres
        projectActims = ""
        allPages = []
        allImages = []
        for actimId in sorted(self.actimetreList):
            projectActims += f'<tr id="Actim{actimId:04d}"></tr>\n'
            allPages.append('{' +
                           f'id: "Actim{actimId:04d}", ' +
                            f'ref: "/actimetre/actim{actimId:04d}.html", ' +
                            f'date: "{JS_TIMEZERO}", ' +
                            'html: ""}')
            if Actimetres.hasGraph(actimId):
                allImages.append('{' +
                            f'id: "Image{actimId:04d}", ' +
                            f'ref: "/images/actim{actimId:04d}.svg", ' +
                            f'date: "{JS_TIMEZERO}", ' +
                            'up: false}')

        projectServers = ""
        for serverId in sorted(self.serverList):
            projectServers += f'<tr id="Actis{serverId:03d}"></tr>\n'
            allPages.append('{' +
                            f'id: "Actis{serverId:03d}", ' +
                            f'ref: "/actiserver/server{serverId:03d}.html", ' +
                            f'date: "{JS_TIMEZERO}", ' +
                            'html: ""}')

        printLog(f'Write HTML Project{self.projectId:02d} = ' +
                 ' '.join(map(lambda a: f'Actim{a:04d}', self.actimetreList)) + ', ' +
                 ' '.join(map(lambda s: f'Actis{s:03d}', self.serverList)))

        projectOwner = f"<h3>Project Owner: {self.owner}</h3>"
        projectEmail = f"<h3>Email: {self.email}</h3>"

        writeTemplateSub(open(f"{HTML_ROOT}/project{self.projectId:02d}.html", "w"),
                         PROJECT_TEMPLATE, {
                         "{projectTitle}"  : self.name(),
                         "{projectOwner}"  : projectOwner,
                         "{projectEmail}"  : projectEmail,
                         "{projectActims}" : projectActims,
                         "{projectServers}": projectServers,
                         "{projectId}"     : str(self.projectId),
                         "{ifempty}"       : 'hidden' if len(self.actimetreList) > 0 else '',
                         "{allpages}"      : ',\n'.join(allPages),
                         "{allimages}"     : ',\n'.join(allImages),
                         "{date}"          : jsDateString(now()),
                         "{document}"      : f'/project{self.projectId:02d}.html',
                         })

    def htmlWriteFree(self):
        from actimetre import Actimetres
        free = ""
        alive = ""
        freePages = []
        livePages = []
        for actimId in sorted(self.actimetreList):
            inline = f'<tr id="Actim{actimId:04d}"></tr>\n'
            index = ('{' + f'id: "Actim{actimId:04d}", ' +
                     f'ref: "/actimetre/actim{actimId:04d}.html", ' +
                     f'date: "{JS_TIMEZERO}", ' + 'html: ""}')
            if Actimetres.isAlive(actimId):
                alive += inline
                livePages.append(index)
            else:
                free += inline
                freePages.append(index)

        writeTemplateSub(open(ACTIMS0_HTML, "w"),
                         ACTIMS0_TEMPLATE,
                         {
                             "{title}"      : 'available',
                             "{Actimetres}" : free,
                             "{allpages}"   : ',\n'.join(freePages),
                             "{date}"       : jsDateString(now()),
                         })

        writeTemplateSub(open(ACTIMS_UN_HTML, "w"),
                         ACTIMS0_TEMPLATE,
                         {
                             "{title}"      : 'to assign',
                             "{Actimetres}" : alive,
                             "{allpages}"   : ',\n'.join(livePages),
                             "{date}"       : jsDateString(now()),
                         })

    def html(self):
        Actimetres = actimetre.Actimetres
        doc, tag, text, line = Doc().ttl()
#        with tag('tr', id=f'Project{self.projectId:02d}'):
        with tag('td', klass='left'):
            with tag('a', href=f'/project{self.projectId:02d}.html'):
                text(self.name())
        if self.projectId == 0:
            line('td', '')
            with tag('td'):
                with tag('a', href=f'/project{self.projectId:02d}.html'):
                    text('List')
        else:
            line('td', self.owner)
            with tag('td', klass='left'):
                for actimId in sorted(self.actimetreList):
                    doc.asis('<div>' + Actimetres.htmlCartouche(actimId) + '</div>')
        return doc.getvalue()

    def save(self):
        if self.stale:
            printLog(f'Project{self.projectId:02d} is stale')
            self.htmlWrite()
            self.dirty = True
        if self.dirty:
            printLog(f'Project{self.projectId:02d} is dirty')
            if self.projectId == 0:
                printLog('Write free Actimetres list')
                self.htmlWriteFree()
            else:
                with open(f'{PROJECT_DIR}/project{self.projectId:02d}.html', 'w') as html:
                    print(self.html(), file=html)
        return self.dirty

class ProjectsClass:
    def __init__(self):
        self.projects: dict[int, Project] = {}
        self.fileTime = TIMEZERO
        self.dirty = False

    def __str__(self):
        string = ""
        for (projectId, p) in self.projects.items():
            string += f"Project{projectId:02d}:"
            for actimId in p.actimetreList:
                string += f" Actim{actimId:04d}"
            string += "\n"
        return string

    def __getitem__(self, item: int):
        return item in self.projects

    def init(self):
        self.projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
        if self.projects.get(0) is None:
            printLog(f'Missing Project00, created')
            self.projects[0] = Project(0, "Not assigned", "No owner")
            self.dirty = True
        self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
        if fileOlderThan(ACTIMS0_HTML, 3600) or fileOlderThan(ACTIMS_UN_HTML, 3600):
            self.projects[0].dirty = True
        Actimetres = actimetre.Actimetres
        Actiservers = actiserver.Actiservers

        allProjectsActimSet = set()
        for project in self.projects.values():
            actimetreSet = project.actimetreList.copy()
            for actimId in actimetreSet:
                if actimId in allProjectsActimSet:
                    printLog(f'Actim{actimId:04d}[{project.projectId}] in duplicate, removed')
                    project.actimetreList.remove(actimId)
                    project.dirty = True
                    self.dirty = True
                else:
                    allProjectsActimSet.add(actimId)
        allActimSet = Actimetres.allActimList()
        diff = allActimSet - allProjectsActimSet
        project0 = self.projects[0]
        for actimId in diff:
            printLog(f'Orphaned Actim{actimId:04d} taken as free')
            project0.actimetreList.add(actimId)
            project0.stale = True
            self.dirty = True

        for project in self.projects.values():
            if project.projectId != 0:
                if fileOlderThan(f'{HTML_ROOT}/project{project.projectId:02d}.html', 3600) :
                    project.stale = True
                if fileOlderThan(f'{PROJECT_DIR}/project{project.projectId:02d}.html', 3600) :
                    project.dirty = True
        for project in self.projects.values():
            for actimId in project.actimetreList:
                serverId = Actiservers.getServerId(actimId)
                if serverId != 0: project.serverList.add(serverId)

    def dump(self):
        string = ""
        for (projectId, p) in self.projects.items():
            if len(p.actimetreList) > 0:
                string += f'{projectId}:' + ','.join([str(a) for a in list(p.actimetreList)]) + '\n'
        return string

    def listIds(self):
        return sorted(self.projects.keys())

    def getName(self, projectId, withFormat=None):
        if projectId in self.projects:
            if withFormat is None:
                return self.projects[projectId].name()
            else:
                return withFormat.format(self.projects[projectId].name())
        else: return ""

    def getOwner(self, projectId):
        return self.projects[projectId].owner

    def getEmail(self, projectId):
        return self.projects[projectId].email

    def getProjectId(self, actimId):
        for project in self.projects.values():
            if actimId in project.actimetreList: return project.projectId
        return 0

    def new(self, title, owner, email) -> int:
        projectId = 1
        while projectId in set(self.projects.keys()):
            projectId += 1
        self.projects[projectId] = Project(projectId, title, owner, email)
        self.dirty = True
        return projectId

    def setInfo(self, projectId, title="Not assigned", owner="", email=""):
        if projectId not in self.projects:
            self.projects[projectId] = Project(projectId, title, owner, email)
        else:
            self.projects[projectId].title = title
            self.projects[projectId].owner = owner
            self.projects[projectId].dirty = True
        self.dirty = True
        return self[projectId]

    def moveActim(self, actimId, projectId):
        for p in self.projects.values():
            if actimId in p.actimetreList:
                printLog(f'Removed Actim{actimId:04d} from Project{p.projectId:02d}')
                p.actimetreList.remove(actimId)
                p.stale = True
        if projectId in self.projects.keys():
            p = self.projects[projectId]
        else:
            p = Project(projectId)
        if p.addActim(actimId):
            self.dirty = True

    def makeDirty(self, actimId):
        for project in self.projects.values():
            if actimId in project.actimetreList:
                project.dirty = True

    def makeStaleMaybe(self):
        Actiservers = actiserver.Actiservers
        for project in self.projects.values():
            for actimId in project.actimetreList:
                s = Actiservers.getServerId(actimId)
                if s != 0 and not s in project.serverList:
                    project.serverList.add(s)
                    project.stale = True

    def htmlChoice(self, projectId=0):
        htmlString = ""
        for p in self.projects.values():
            if p.projectId != 0:
                htmlString += f'<input id="{p.projectId}" type="radio" name="projectId" value="{p.projectId}"'
                if p.projectId == projectId:
                    htmlString += ' checked="true"'
                htmlString += f'><label for="{p.projectId}">{p.name()} ({p.owner})</label><br>\n'
        return htmlString

    def processAction(self, action, args):
        if action == 'project-edit':
            project = self.projects[int(args['projectId'][0])]
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formProject.html", {
                "{projectTitle}": project.title,
                "{projectName}": project.name(),
                "{projectOwner}": project.owner,
                "{projectEmail}": project.email,
                "{projectId}": str(project.projectId),
            })

        elif action == 'project-create':
            print("Location:\\formCreate.html\n\n")

        elif action == 'project-delete':
            project = self.projects[int(args['projectId'][0])]
            actimetreList = ""
            if len(project.actimetreList) == 0:
                actimetreList = "(no Actimetres assigned to this project)\n"
            else:
                Actimetres = actimetre.Actimetres
                for actimId in project.actimetreList:
                    actimetreList += '<li>' + Actimetres.htmlCartouche(actimId) + '</li>'
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formDelete.html", {
                "{projectId}": str(project.projectId),
                "{projectTitle}": project.name(),
                "{actimetreList}": actimetreList,
            })

        elif action == 'project-add':
            Actimetres = actimetre.Actimetres
            project = self.projects[int(args['projectId'][0])]
            actimetreList = ""
            for actimId in sorted(self.projects[0].actimetreList,
                                  key=lambda a: Actimetres.getLastSeen(a),
                                  reverse=True):
                actimetreList += (
                        f'<div><input type="checkbox" name="actimId" value="{actimId}"> <b>' +
                        Actimetres.getName(actimId) + '</b> [' +
                        Actimetres.htmlActimType(actimId) + '] Last seen ' +
                        Actimetres.getLastSeen(actimId).strftime(TIMEFORMAT_DISP) +
                        f' <i>{printTimeAgo(Actimetres.getLastSeen(actimId))}</i></input></div>'
                )
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formAdd.html", {
                "{projectId}": str(project.projectId),
                "{projectTitle}": project.name(),
                "{actimetreList}": actimetreList,
            })

        else:
            print("Status: 205\n\n")

    def processForm(self, formId, args):
        if formId == 'project-edit':
            projectId = int(args['projectId'][0])
            title = args['title'][0]
            owner = args['owner'][0]
            email = args['email'][0]
            printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")
            if title != "" and owner != "" and email != "":
                self.setInfo(projectId, title, owner, email)
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'project-create':
            title = args['title'][0]
            owner = args['owner'][0]
            email = args['email'][0]
            printLog(f"Create new project with data: {title}, {owner}, {email}")
            if title != "" and owner != "" and email != "":
                projectId = self.new(title, owner, email)
                print(f"Location:\\project{projectId:02d}.html\n\n")
            else:
                print(f"Location:\\{INDEX_NAME}\n\n")

        elif formId == 'project-add':
            projectId = int(args['projectId'][0])
            actimetreList = args['actimId']
            for actimId in map(int, actimetreList):
                self.moveActim(actimId, projectId)
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'project-delete':
            projectId = int(args['projectId'][0])
            if projectId in self.projects:
                if len(self.projects[projectId].actimetreList) == 0:
                    del self.projects[projectId]
                    self.dirty = True
                    print(f"Location:\\{INDEX_NAME}\n\n")
                else:
                    print(f"Location:\\project{projectId:02d}.html\n\n")
            else:
                print(f"Location:\\{INDEX_NAME}\n\n")

        else:
            print("Status: 205\n\n")

    def actimIsStale(self, actimId):
        for p in self.projects.values():
            if actimId in p.actimetreList:
                p.stale = True

    def needUpdate(self, serverTime):
        return self.fileTime > serverTime

    def save(self):
        for p in self.projects.values():
            p.save()
        if self.dirty:
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})
            self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
            self.projects[0].htmlWriteFree()

Projects = ProjectsClass()
def initProjects() -> ProjectsClass:
    Projects.init()
    return Projects

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
        self.dirty        = True

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
        return self

    def addActim(self, actimId: int):
        if actimId not in self.actimetreList:
            self.actimetreList.add(actimId)
            self.dirty = True
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
        for actimId in sorted(self.actimetreList):
            if Actimetres.isAlive(actimId):
                projectActims += Actimetres.html(actimId)
        for actimId in sorted(self.actimetreList, key=lambda a: Actimetres.getLastSeen(a), reverse=True):
            if not Actimetres.isAlive(actimId):
                projectActims += Actimetres.html(actimId)

        Actiservers = actiserver.Actiservers
        serverList = set()
        for serverId in sorted(map(Actimetres.getServerId, self.actimetreList)):
            if serverId != 0:
                serverList.add(serverId)

        projectOwner = f"<h3>Project Owner: {self.owner}</h3>"
        projectEmail = f"<h3>Email: {self.email}</h3>"

        writeTemplateSub(open(f"{HTML_ROOT}/project{self.projectId:02d}.html", "w"),
                         PROJECT_TEMPLATE, {
                         "{projectTitle}"  : self.name(),
                         "{projectOwner}"  : projectOwner,
                         "{projectEmail}"  : projectEmail,
                         "{projectActims}" : projectActims,
                         "{projectServers}": Actiservers.html(picker=lambda s: s.serverId in serverList),
                         "{projectId}"     : str(self.projectId),
                         })

    def htmlWriteFree(self):
        Actimetres = actimetre.Actimetres
        freeActims = ""
        for actimId in self.actimetreList:
            freeActims += Actimetres.html(actimId)

        writeTemplateSub(open(ACTIMS0_HTML, "w"), ACTIMS0_TEMPLATE, {
                             "{Actimetres}" : freeActims,
                         })

    def html(self):
        Actimetres = actimetre.Actimetres
        doc, tag, text, line = Doc().ttl()
        with tag('tr'):
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
                    for actimId in self.actimetreList:
                        doc.asis('<div>' + Actimetres.htmlCartouche(actimId) + '</div>')
        return doc.getvalue()

    def save(self):
        if self.dirty:
            if self.projectId == 0:
                self.htmlWriteFree()
                return True
            else:
                self.htmlWrite()
        return False

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
            self.projects[0] = Project(0, "Not assigned", "No owner")
            self.dirty = True
        self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
        for project in self.projects.values():
            htmlFile = f'{HTML_ROOT}/project{project.projectId:02d}.html'
            if not os.path.isfile(htmlFile) or olderThanSeconds(os.stat(htmlFile).st_mtime, 3600) :
                project.dirty = True

    def dump(self):
        string = ""
        for (projectId, p) in self.projects.items():
            if len(p.actimetreList) > 0:
                string += f'{projectId}:' + ','.join([str(a) for a in list(p.actimetreList)]) + '\n'
        return string

    def htmlProjects(self, *, picker=None):
        htmlString = ""
        for projectId in sorted(self.projects.keys()):
            if picker is None or picker(self.projects[projectId]):
                htmlString += self.projects[projectId].html()
        return htmlString

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

    def setInfo(self, projectId, title="Not assigned", owner="", email=""):
        if projectId not in self.projects:
            self.projects[projectId] = Project(projectId, title, owner, email)
        else:
            self.projects[projectId].title = title
            self.projects[projectId].owner = owner
            self.projects[projectId].dirty = True
        self.dirty = True
        return self[projectId]

    def setActimetre(self, projectId: int, actimId: int) -> int:
        for p in self.projects.values():
            if actimId in p.actimetreList and p.projectId != projectId:
                p.removeActim(actimId)
                self.dirty = True
        if projectId in self.projects:
            if self.projects[projectId].addActim(actimId):
                self.dirty = True
            return projectId
        else:
            return 0

    def removeActim(self, actimId):
        for p in self.projects.values():
            if actimId in p.actimetreList:
                p.actimetreList.remove(actimId)
                p.dirty = True
                self.dirty = True

    def moveActim(self, actimId, projectId):
        if self.removeActim(actimId): self.dirty = True
        if self.addActim(projectId, actimId): self.dirty = True

    def new(self, title, owner, email) -> int:
        projectId = 1
        while projectId in set(self.projects.keys()):
            projectId += 1
        self.projects[projectId] = Project(projectId, title, owner, email)
        self.dirty = True
        return projectId

    def addActim(self, projectId, actimId):
        if projectId in self.projects.keys():
            p = self.projects[projectId]
        else:
            p = Project(projectId)
        if p.addActim(actimId): self.dirty = True

    def htmlChoice(self, projectId=0):
        htmlString = ""
        for p in self.projects.values():
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
                        f'<li> <input type="checkbox" name="actimId" value="{actimId}"> ' +
                        Actimetres.getName(actimId) + ' - ' +
                        Actimetres.getLastSeen(actimId).strftime(TIMEFORMAT_DISP) +
                        '</input></li>'
                )
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_ROOT}/formAdd.html", {
                "{projectId}": str(project.projectId),
                "{projectTitle}": project.name(),
                "{actimetreList}": actimetreList,
            })

        else:
            print("Status: 4205n\n")

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
                print("Location:\\index.html\n\n")

        elif formId == 'project-add':
            Actimetres = actimetre.Actimetres
            projectId = int(args['projectId'][0])
            actimetreList = args['actimId']
            for actimId in map(int, actimetreList):
                self.projects[projectId].addActim(actimId)
                Actimetres.setProjectId(actimId, projectId)
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'project-delete':
            projectId = int(args['projectId'][0])
            if projectId in self.projects:
                Actimetres = actimetre.Actimetres
                for actimId in self.projects[projectId].actimetreList:
                    Actimetres.removeProject(actimId)
                    self.projects[projectId].removeActim(actimId)
                del self.projects[projectId]
                self.dirty = True
            print("Location:\\index.html\n\n")

        else:
            print("Status: 205\n\n")

    def dirtyProject(self, projectId):
        self.projects[projectId].dirty = True

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

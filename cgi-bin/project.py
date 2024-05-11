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
        printLog(f'HTML: {self}')
        Actimetres = actimetre.Actimetres
        projectActims = ""
        for actimId in self.actimetreList:
            projectActims += Actimetres.html(actimId)

        Actiservers = actiserver.Actiservers
        serverList = set()
        for actimId in self.actimetreList:
            serverList.add(Actimetres.getServerId(actimId))

        if self.projectId == 0:
            buttons = ""
        else:
            buttons = '''\
                  <button type="submit" name="action" value="project-edit">Edit info</button>
                  <button type="submit" name="action" value="project-delete">Delete project</button>
                  '''

        if self.projectId == 0:
            projectOwner = ""
            projectEmail = ""
        else:
            projectOwner = f"<h3>Project Owner: {self.owner}</h3>"
            projectEmail = f"<h3>Email: {self.email}</h3>"

        writeTemplateSub(open(f"{HTML_DIR}/project{self.projectId:02d}.html", "w"),
                         PROJECT_TEMPLATE, {
                         "{buttons}"       : buttons,
                         "{projectTitle}"  : self.name(),
                         "{projectOwner}"  : projectOwner,
                         "{projectEmail}"  : projectEmail,
                         "{projectActims}" : projectActims,
                         "{projectServers}": Actiservers.html(picker=lambda s: s.serverId in serverList),
                         "{projectId}"     : str(self.projectId),
                         })
        try:
            os.chmod(f"{HTML_DIR}/project{self.projectId:02d}.html", 0o666)
        except OSError:
            pass

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
                        doc.asis(Actimetres.htmlCartouche(actimId, withTag='div'))
        return doc.getvalue()

    def save(self):
        if self.dirty: self.htmlWrite()

class ProjectsClass:
    def __init__(self):
        self.projects: dict[int, Project] = {}
        self.fileTime = TIMEZERO
        self.dirty = False

    def __getitem__(self, item: int):
        return item in self.projects

    def init(self):
        self.projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
        if self.projects.get(0) is None:
            self.projects[0] = Project(0, "Not assigned", "No owner")
            self.dirty = True
        self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)

    def dump(self):
        for (projectId, p) in self.projects.items():
            if len(p.actimetreList) > 0:
                print(f'{projectId}:', ','.join([str(a) for a in list(p.actimetreList)]))

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
            writeTemplateSub(sys.stdout, f"{HTML_DIR}/formProject.html", {
                "{projectTitle}": project.title,
                "{projectName}": project.name(),
                "{projectOwner}": project.owner,
                "{projectId}": str(project.projectId),
            })

        elif action == 'project-create':
            print("Location:\\formCreate.html\n\n")

        elif action == 'project-delete':
            project = self.projects[int(args['projectId'][0])]
            actimetreStr = ""
            if len(project.actimetreList) == 0:
                actimetreStr = "(no Actimetres assigned to this project)\n"
            else:
                Actimetres = actimetre.Actimetres
                for actimId in project.actimetreList:
                    actimetreStr += Actimetres.htmlCartouche(actimId, withTag='li')
            print("Content-type: text/html\n\n")
            writeTemplateSub(sys.stdout, f"{HTML_DIR}/formDelete.html", {
                "{projectId}": str(project.projectId),
                "{projectTitle}": project.name(),
                "{actimetreList}": actimetreStr,
            })

        else:
            print("Status: 400\n\n")

    def processForm(self, formId, args):
        title = args['title'][0]
        owner = args['owner'][0]
        email = args['email'][0]

        if formId == 'project-edit':
            projectId = int(args['projectId'][0])
            printLog(f"Setting project {projectId} data: {title}, {owner}, {email}")
            if title != "" and owner != "" and email != "":
                self.setInfo(projectId, title, owner, email)
            print(f"Location:\\project{projectId:02d}.html\n\n")

        elif formId == 'project-create':
            printLog(f"Create new project with data: {title}, {owner}, {email}")
            if title != "" and owner != "" and email != "":
                projectId = self.new(title, owner, email)
                print(f"Location:\\project{projectId:02d}.html\n\n")
            else:
                print("Location:\\index.html\n\n")

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
            print("Status: 400\n\n")

    def dirtyProject(self, projectId):
        self.projects[projectId].dirty = True

    def needUpdate(self, serverTime):
        return self.fileTime > serverTime

    def save(self):
        if self.dirty:
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})
            self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
        for p in self.projects.values():
            p.save()

Projects = ProjectsClass()
def initProjects() -> ProjectsClass:
    Projects.init()
    return Projects

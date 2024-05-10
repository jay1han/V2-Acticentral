from const import *
import actimetre

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
        self.dirty        = False

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
        return self

    def addActim(self, actimId: int):
        if actimId not in self.actimetreList:
            self.actimetreList.add(actimId)
            self.dirty = True
            return True
        else:
            return False

    def name(self):
        return f"{self.title} (#{self.projectId:02d})"

    def htmlWrite(self):
        Actimetres = actimetre.Actimetres
        projectActimHTML = ""
        for actimId in self.actimetreList:
            projectActimHTML += Actimetres.html(actimId)
        if self.projectId == 0:
            buttons = ""
        else:
            buttons = '''\
                  <button type="submit" name="action" value="project-edit-info">Edit info</button>
                  <button type="submit" name="action" value="remove-project">Remove project</button>
                  '''

        if self.projectId == 0:
            projectOwner = ""
            projectEmail = ""
        else:
            projectOwner = f"<h3>Project Owner: {self.owner}</h3>"
            projectEmail = f"<h3>Email: {self.email}</h3>"

        with open(f"{HTML_DIR}/project{self.projectId:02d}.html", "w") as html:
            with open(PROJECT_TEMPLATE, "r") as template:
                print(template.read() \
                      .replace("{buttons}", buttons) \
                      .replace("{projectTitle}", self.name()) \
                      .replace("{projectOwner}", projectOwner) \
                      .replace("{projectEmail}", projectEmail) \
                      .replace("{projectActimHTML}", projectActimHTML) \
                      .replace("{projectId}", str(self.projectId)) \
                      .replace("{Updated}", LAST_UPDATED),
                      file=html)
        try:
            os.chmod(f"{HTML_DIR}/project{self.projectId:02d}.html", 0o777)
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

    def saveProject(self):
        if self.dirty: self.htmlWrite()

class ProjectsClass:
    def __init__(self):
        self.projects: dict[int, Project] = {}
        self.fileTime = TIMEZERO
        self.dirty = False
        self.dummy = Project()

    def __getitem__(self, item: int):
        return item in self.projects

    def init(self):
        self.projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
        if self.projects.get(0) is None:
            self.projects[0] = Project(0, "Not assigned", "No owner")
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})
        self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
        self.dirty = False

    def list(self):
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
                p.actimetreList.remove(actimId)
        if projectId in self.projects:
            self.projects[projectId].addActim(actimId)
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
        self.removeActim(actimId)
        self.addActim(projectId, actimId)

    def new(self, title, owner):
        projectId = 1
        while projectId in set(self.projects.keys()):
            projectId += 1
        self.projects[projectId] = Project(projectId, title, owner)
        self.projects[projectId].dirty = True
        self.dirty = True

    def deleteProject(self, projectId):
        Actimetres = actimetre.Actimetres
        if projectId in self.projects:
            for a in self.projects[projectId].actimetreList:
                Actimetres.removeProject(a)
            del self.projects[projectId]
            self.dirty = True

    def htmlWrite(self, projectId):
        self.projects[projectId].htmlWrite()

    def addActim(self, projectId, actimId):
        if projectId in self.projects.keys():
            p = self.projects[projectId]
        else:
            p = Project(projectId)
        p.addActim(actimId)
        self.dirty = True

    def htmlChoice(self, projectId=None):
        htmlString = ""
        for p in self.projects.values():
            htmlString += f'<input id="{p.projectId}" type="radio" name="projectId" value="{p.projectId}"'
            if p.projectId == projectId:
                htmlString += ' checked="true"'
            htmlString += f'><label for="{p.projectId}">{p.name()} ({p.owner})</label><br>\n'
        return htmlString

    def htmlActimetreList(self, projectId):
        if len(self.projects[projectId].actimetreList) == 0:
            return "(no Actimetres assigned to this project)\n"
        else:
            Actimetres = actimetre.Actimetres
            actimList = ""
            for actimId in self.projects[projectId].actimetreList:
                actimList += Actimetres.htmlCartouche(actimId, 'li')
            return actimList

    def needUpdate(self, serverTime):
        return self.fileTime > serverTime

    def dirtyProject(self, projectId):
        self.projects[projectId].dirty = True

    def save(self):
        if self.dirty:
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})
            self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)
            for p in self.projects.values():
                p.saveProject()

Projects = ProjectsClass()
def initProjects() -> ProjectsClass:
    Projects.init()
    return Projects

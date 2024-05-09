from yattag import Doc, indent

from const import *
import globals as x

class Project:
    def __init__(self, projectId=0, title="", owner="", email="", actimetreList=None):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.email         = email
        if actimetreList is None:
            self.actimetreList = set()
        else:
            self.actimetreList = actimetreList
        self.repoNums      = 0
        self.repoSize      = 0

    def toD(self):
        return {'projectId'     : self.projectId,
                'title'         : self.title,
                'owner'         : self.owner,
                'email'         : self.email,
                'repoNums'      : self.repoNums,
                'repoSize'      : self.repoSize,
                'actimetreList' : list(self.actimetreList),
                }

    def fromD(self, d):
        self.projectId      = int(d['projectId'])
        self.title          = d['title']
        self.owner          = d['owner']
        self.email      = d['email']
        self.repoNums   = int(d['repoNums'])
        self.repoSize       = int(d['repoSize'])
        self.actimetreList = set([int(actimId) for actimId in d['actimetreList']])
        return self

    def addActim(self, actimId):
        if actimId not in self.actimetreList:
            self.actimetreList.add(actimId)
            return True
        else:
            return False

    def name(self):
        return f"{self.title} (#{self.projectId:02d})"

    def htmlUpdate(self):
        projectActimHTML = ""
        for actimId in self.actimetreList:
            if x.Actimetres.get(actimId) is not None:
                projectActimHTML += x.Actimetres[actimId].html()
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
                      .replace("{Updated}", LAST_UPDATED) \
                      , file=html)
        try:
            os.chmod(f"{HTML_DIR}/project{self.projectId:02d}.html", 0o777)
        except OSError:
            pass

    def html(self):
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
                        if x.Actimetres.get(actimId) is not None:
                            with tag('div'):
                                doc.asis(x.Actimetres[actimId].htmlCartouche())

        return indent(doc.getvalue())

class ProjectsClass:
    def __init__(self):
        self.projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
        if self.projects.get(0) is None:
            self.projects[0] = Project(0, "Not assigned", "No owner")
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})
        self.fileTime = datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)

    def list(self):
        for (projectId, p) in self.projects.items():
            if len(p.actimetreList) > 0:
                print(f'{projectId}:', ','.join([str(a) for a in list(p.actimetreList)]))

    def html(self, *, picker=None):
        htmlString = ""
        for projectId in sorted(self.projects.keys()):
            if picker is None or picker(self.projects[projectId]):
                htmlString += self.projects[projectId].html()
        return htmlString

    def get(self, projectId):
        if projectId not in self.projects.keys():
            self.projects[projectId] = Project(projectId, "", "")
        return self.projects[projectId]

    def clearRepos(self):
        for p in self.projects.values():
            p.repoNums = 0
            p.repoSize = 0

    def set(self, projectId, title="Not assigned", owner="", email=""):
        if projectId not in self.projects.keys():
            self.projects[projectId] = Project(projectId, title, owner, email)
        else:
            self.projects[projectId].title = title
            self.projects[projectId].owner = owner
        return self.projects[projectId]

    def save(self, save=True):
        if save:
            dumpData(PROJECTS, {int(p.projectId):p.toD() for p in self.projects.values()})

    def values(self):
        return self.projects.values()

    def removeActim(self, actimId, projectId=None):
        if projectId is not None:
            if projectId in self.projects.keys():
                if actimId in self.projects[projectId].actimetreList:
                    self.projects[projectId].actimetreList.remove(actimId)
        else:
            save = False
            for p in self.projects.values():
                if actimId in p.actimetreList:
                    p.actimetreList.remove(actimId)
                    save = True
            self.save(save)

    def new(self, title, owner):
        projectId = 1
        while projectId in set(self.projects.keys()):
            projectId += 1
        self.projects[projectId] = Project(projectId, title, owner)

    def delete(self, projectId):
        if projectId in self.projects.keys():
            del self.projects[projectId]

    def exists(self, projectId):
        return projectId in self.projects.keys()

    def htmlUpdate(self, projectId):
        if projectId in self.projects.keys():
            self.projects[projectId].htmlUpdate()

Projects = ProjectsClass()

from globals import *

class Project:
    def __init__(self, projectId=0, title="", owner="", email="", actimetreList=set()):
        self.projectId     = projectId
        self.title         = title
        self.owner         = owner
        self.email         = email
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
        if d.get('email'):
            self.email      = d['email']
        if d.get('repoNums'):
            self.repoNums   = int(d['repoNums'])
        self.repoSize       = int(d['repoSize'])
        if d.get('actimetreList') is not None:
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

    def html(self):
        projectActimHTML = ""
        for actimId in self.actimetreList:
            if Actimetres.get(actimId) is not None:
                projectActimHTML += Actimetres[actimId].html()
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

        doc, tag, text, line = Doc().ttl()
        for projectId in sorted(Projects.keys()):
            p = Projects[projectId]
            with tag('tr'):
                with tag('td', klass='left'):
                    with tag('a', href=f'/project{projectId:02d}.html'):
                        text(self.name())
                if projectId == 0:
                    line('td', '')
                    with tag('td'):
                        with tag('a', href=f'/project{projectId:02d}.html'):
                            text('List')
                else:
                    line('td', self.owner)
                    with tag('td', klass='left'):
                        for actimId in self.actimetreList:
                            if Actimetres.get(actimId) is not None:
                                with tag('div'):
                                    doc.asis(Actimetres[actimId].htmlCartouche())

        return indent(doc.getvalue())

def listProjects():
    for (projectId, p) in Projects.items():
        if len(p.actimetreList) > 0:
            print(f'{projectId}:', ','.join([str(a) for a in list(p.actimetreList)]))

def initProjects():
    projects = {int(projectId):Project().fromD(d) for projectId, d in loadData(PROJECTS).items()}
    if projects.get(0) is None:
        projects[0] = Project(0, "Not assigned", "No owner")
        dumpData(PROJECTS, {int(p.projectId):p.toD() for p in Projects.values()})
    return projects

def initProjectsTime():
    return datetime.fromtimestamp(os.stat(PROJECTS).st_mtime, tz=timezone.utc)

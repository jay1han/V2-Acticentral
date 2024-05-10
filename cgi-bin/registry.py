import shutil
from const import *

class RegistryClass:
    def __init__(self):
        self.macToId: dict[str, int] = {}
        with open(REGISTRY, "r") as registry:
            try:
                self.macToId = json.load(registry)
            except json.JSONDecodeError:
                pass
        self.fileTime = datetime.fromtimestamp(os.stat(REGISTRY).st_mtime, tz=timezone.utc)
        self.dirty = False

    def getId(self, mac):
        if mac in self.macToId:
            actimId = self.macToId[mac]
            printLog(f"Found known Actim{actimId:04d} for {mac}")
            return actimId
        else:
            actimList = self.macToId.values()
            actimList.sort()
            actimId = len(actimList) + 1
            for newId in range(1, len(actimList) + 1):
                if not newId in actimList:
                    actimId = newId
                    break
            self.macToId[mac] = actimId
            printLog(f"Allocated new Actim{actimId:04d} for {mac}")
            self.dirty = True
            return actimId

    def deleteId(self, actimId):
        for mac, macId in self.macToId.items():
            if macId == actimId:
                del self.macToId[mac]
                self.dirty = True

    def save(self, save=True):
        if not save: return
        registryBackup = REGISTRY_BACKUP + datetime.now().strftime(TIMEFORMAT_FN)
        try:
            shutil.copyfile(REGISTRY, registryBackup)
        except OSError:
            pass

        os.truncate(REGISTRY, 0)
        with open(REGISTRY, "r+") as registry:
            json.dump(self.macToId, registry)
        printLog("Saved Registry " + str(self.macToId))
        self.fileTime = datetime.fromtimestamp(os.stat(REGISTRY).st_mtime, tz=timezone.utc)

    def dump(self):
        return json.dumps(self.macToId)

    def needUpdate(self, serverTime):
        return self.fileTime > serverTime

Registry = RegistryClass()

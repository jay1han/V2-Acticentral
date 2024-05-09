### Global variables

import shutil

from const import *

Registry     = {}
RegistryTime = TIMEZERO
Actiservers  = {}
Actimetres   = {}

def saveRegistry():
    registryBackup = REGISTRY_BACKUP + datetime.now().strftime(TIMEFORMAT_FN)
    try:
        shutil.copyfile(REGISTRY, registryBackup)
    except OSError:
        pass

    os.truncate(REGISTRY, 0)
    with open(REGISTRY, "r+") as registry:
        json.dump(Registry, registry)
    printLog("Saved Registry " + str(Registry))

def loadRegistry():
    global Registry, RegistryTime
    with open(REGISTRY, "r") as registry:
        try:
            Registry = json.load(registry)
        except json.JSONDecodeError:
            pass
    RegistryTime = datetime.fromtimestamp(os.stat(REGISTRY).st_mtime, tz=timezone.utc)
    return

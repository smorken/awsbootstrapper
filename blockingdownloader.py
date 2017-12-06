import logging
from instancemanager import InstanceManager
class BlockingDownloader(object):

    def __init__(self, manifest, instance_manager):
        self._manifest = manifest
        self._instance_manager = instance_manager
        self._allJobIds = [x["Id"] for x in self._manifest.GetJobs()]
        self._activeJobs = set(self._allJobIds)

    def block(self, sleep, sleepInterval):
        while len(self._activeJobs) > 0:
            self.run()
            sleep(sleepInterval)

    def run(self, downloads):
        instanceMetaCollection = {}
        for x in self._allJobIds:
            if not x in self._activeJobs:
                continue
            instanceMeta = self._instance_manager.downloadMetaData(x)
            instanceMetaCollection[x] = instanceMeta
            #check if all tasks are finished in the current instance
            if instanceMeta.AllTasksFinished():
                docs = self._manifest.GetInstanceS3Documents(x) 
                for doc in docs:
                    if doc["Direction"] == "AWSToLocal":
                        downloads.append(doc["Name"])
                self._activeJobs.remove(x)
        return instanceMetaCollection






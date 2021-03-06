import os, subprocess, logging


class AWSInstanceBootStrapper(object):
    """ this class is to be executed on an aws instance
    it consumes the manifest and downloads files from 
    s3 accordingly, and then runs specified commands depending on the instance
    id
    """
    def __init__(self, instanceId, manifest, s3interface, instancemanager, metadata):
        """Initialize AWSInstanceBootStrapper.

        Args:
            instanceId: the id of this instance as defined in the manifest
            manifest: a Manifest object - describes the tasks and data for this instance
            s3interface: a S3Interface object - used to upload and download data from the AWS S3 service
            instancemanager: an InstanceManager object - used to upload logs and status data to S3
        """
        self.instanceId = instanceId
        self.manifest = manifest
        self.s3interface = s3interface
        self.instancemanager = instancemanager
        self.metadata = metadata
        self.job = self.manifest.GetJob(self.instanceId)
        self.requiredS3Docs = self.job["RequiredS3Data"]

    def UploadStatus(self):
        """Uploads the log file to S3"""
        self.instancemanager.uploadInstanceLog(self.instanceId)
        self.instancemanager.uploadMetaData(self.metadata)

    def DownloadS3Documents(self):
        """ Downloads documents specified as required for this instance in the
        manifest
        """
        for documentName in self.requiredS3Docs:
            documentData = self.manifest.GetS3Documents(
                filter={ "Name": documentName })[0]
            # [0] because only one document will match because 
            # Name is constrained as a unique identifier

            #AWSInstance path is the local path on an instance
            localPath = documentData["AWSInstancePath"]
            keyPrefix = self.manifest.GetS3KeyPrefix()

            direction = documentData["Direction"]
            if direction in ["LocalToAWS", "Static"]:
                self.metadata.UpdateMessage("Downloading '{0}'"
                                            .format(documentName))
                self.UploadStatus()
                self.s3interface.downloadCompressed(
                    keyPrefix, documentName, localPath)
                self.metadata.IncrementDownloadFinished()
                self.UploadStatus()

    def RunCommands(self):
        """Run the commands specified for this instance in the manifest.

        Returns:
            True, if all commands executed sucessfully, otherwise an exception will be thrown
        """
        
        for c in self.job["Commands"]:
            command = [c["Command"]]
            args = c["Args"]
            command.extend(args)

            try:
                # http://stackoverflow.com/questions/16198546/get-exit-code-and-stderr-from-subprocess-call
                logging.info("issuing command: {0}".format(command))
                self.metadata.UpdateMessage("Running command '{0}'".format(command))
                self.UploadStatus()
                cmnd_output = subprocess.check_output(command, 
                                                      stderr=subprocess.STDOUT,
                                                      shell=False, 
                                                      universal_newlines=True);
                logging.info("command executed successfully")
                self.metadata.IncrementCommandFinished()
                self.UploadStatus()
            except subprocess.CalledProcessError as cp_ex:
                logging.exception("error occurred running command")
                logging.error(cp_ex.output)
                raise cp_ex
            except Exception as ex:
                logging.exception("error occurred running command")
                raise ex
            finally:
                self.UploadStatus()

        return True

    def UploadS3Documents(self):
        """Upload the documents from this instance to S3 that are specified in
        the manifest as required for this instance
        """
        for documentName in self.requiredS3Docs:
            documentData = self.manifest.GetS3Documents(
                filter={ "Name": documentName })[0]
            # [0] because exactly one document should match because 
            # Name is constrained as a unique identifier

            #AWSInstance path is the local path on an instance
            localPath = documentData["AWSInstancePath"]
            keyPrefix = self.manifest.GetS3KeyPrefix()

            direction = documentData["Direction"]
            if direction in ["AWSToLocal"]:
                self.metadata.UpdateMessage("Uploading '{0}'"
                    .format(documentName))
                self.UploadStatus()
                self.s3interface.uploadCompressed(keyPrefix, documentName, localPath)
                self.metadata.IncrementUploadsFinished()
                self.UploadStatus()

def main():
    """to be run on by each instance as a startup command"""
    import argparse, sys
    import boto3
    #from powershell_s3 import powershell_s3
    from s3interface import S3Interface
    from manifest import Manifest
    from instancemanager import InstanceManager
    from instancemetadatafactory import InstanceMetadataFactory
    from loghelper import LogHelper
    parser = argparse.ArgumentParser(
        description="AWS Instance bootstrapper" +
                    "Loads manifest which contains data and commands to run on this instance,"+
                    "downloads data from S3, runs commands, and uploads results to S3")

    parser.add_argument("--bucketName", help = "the name of the S3 bucket to work with", required=True)
    parser.add_argument("--manifestKey", help = "the key pointing to the manifest file in the s3 bucket", required=True)
    parser.add_argument("--instanceId", help = "the id of this instance as defined in the manifest file", required=True)
    parser.add_argument("--localWorkingDir", help = "a directory to store working files, it will be created if it does not exist on the instance", required=True)

    try:
        #boto3.set_stream_logger(name='botocore')
        args = vars(parser.parse_args())
        bootstrapper = None

        bucketName = args["bucketName"]
        manifestKey = args["manifestKey"]
        instanceId = int(args["instanceId"])
        localWorkingDir = args["localWorkingDir"]

        if not os.path.exists(localWorkingDir):
            os.makedirs(localWorkingDir)
        logPath = LogHelper.instanceLogPath(localWorkingDir, instanceId)
        LogHelper.start_logging(logPath)
        logging.info("startup")
        logging.info("creating boto3 s3 resource")
        s3 = boto3.resource('s3')

        logging.info("creating S3Interface")
        s3interface = S3Interface(s3, bucketName, localWorkingDir)

        localManifestPath = os.path.join(localWorkingDir, "manifest.json")
        logging.info("downloading manifest from S3")
        s3interface.downloadFile(manifestKey, localManifestPath)
        manifest = Manifest(localManifestPath)
        metafac = InstanceMetadataFactory(manifest)
        instancemanager = InstanceManager(s3interface, manifest, metafac)
        metadata = instancemanager.downloadMetaData(instanceId)
        bootstrapper = AWSInstanceBootStrapper(instanceId,
                                               manifest, 
                                               s3interface, 
                                               instancemanager,
                                               metadata)
        bootstrapper.DownloadS3Documents()
        bootstrapper.RunCommands()
        bootstrapper.UploadS3Documents()
    except Exception as ex:
        logging.exception("error in bootstrapper")
        if bootstrapper is not None:
            bootstrapper.UploadStatus()
        sys.exit(1)

if __name__ == "__main__":
    main()
import os, shutil, zipfile, logging

class S3Interface(object):

    def __init__(self, s3Resource, bucketName, localTempDir):
        self.bucketName = bucketName
        self.bucket = s3Resource.Bucket(bucketName)
        self.localTempDir = localTempDir
        self.__format = "zip"
        self.__singleFileFlag = "__is__single__file_archive__"

    def downloadFile(self, keyName, localPath, logged=True):
        if logged:
            logging.info("downloading file from S3 '{0}' to '{1}'".format(keyName, localPath))
        self.bucket.download_file(keyName, localPath)

    def uploadFile(self, localPath, keyName, logged=True):
        if logged:
            logging.info("uploading file '{0}' to S3 '{1}'".format(localPath, keyName))
        self.bucket.upload_file(localPath, keyName)

    def make_zipfile(self, output_filename, source_dir):
        """
        mostly borrowed from an answer on Stack overflow
        https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory
        """
        relroot = os.path.abspath(source_dir)
        with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zip:
            for root, dirs, files in os.walk(source_dir):
                # add directory (needed for empty dirs)
                zip.write(root, os.path.relpath(root, relroot))
                for file in files:
                    filename = os.path.join(root, file)
                    if os.path.isfile(filename): # regular files only
                        arcname = os.path.join(os.path.relpath(root, relroot), file)
                        zip.write(filename, arcname)

    def archiveFileOrDirectory(self, pathToArchive, archiveName):
        if os.path.isdir(pathToArchive):
            archivePath = os.path.join(self.localTempDir, archiveName)
            logging.info("archiving documents at '{0}' to '{1}'".format(pathToArchive, archivePath))
            outputPath = archivePath + '.zip'
            self.make_zipfile(outputPath, pathToArchive)
            return outputPath;
        elif os.path.isfile(pathToArchive):
            outputPath =  os.path.join(self.localTempDir, archiveName) + "." + self.__format
            logging.info("archiving file '{0}' to '{1}'".format(pathToArchive, outputPath))
            with zipfile.ZipFile(outputPath, 'w', zipfile.ZIP_DEFLATED, True) as z:
                z.write(pathToArchive, os.path.basename(pathToArchive))
                singleFilePath = os.path.join(self.localTempDir, self.__singleFileFlag)
                with open(singleFilePath, mode='w') as tmp:
                    z.write(singleFilePath, self.__singleFileFlag)
                os.remove(singleFilePath)
            return outputPath
        else:
            raise ValueError(
                "specified pathToArchive '{0}' is neither a dir or a file path"
                .format(pathToArchive))

    def unpackFileOrDirectory(self, archiveName, destinationPath):
        logging.info("upacking files in '{0}' to '{1}'".format(archiveName, destinationPath))
        with zipfile.ZipFile(archiveName, 'r', allowZip64=True) as z:
            files = z.namelist()
            if self.__singleFileFlag in files:
                if len(files) != 2:
                    raise ValueError("single file archive expected to have a single file")
                # it's a single file archive, so the destination path is
                # assumed to be the full path to the filename
                destinationDir = os.path.dirname(destinationPath)
                destinationFileName = os.path.basename(destinationPath)
                compressedFileName = [x for x in files if x != self.__singleFileFlag][0]
                z.extractall(destinationDir)
                os.rename(os.path.join(destinationDir, compressedFileName), os.path.join(destinationDir, destinationFileName))
                os.remove(os.path.join(destinationDir, self.__singleFileFlag))
            else:
                z.extractall(destinationPath)


    def uploadCompressed(self, keyNamePrefix, documentName, localPath):

        fn = self.archiveFileOrDirectory(localPath, documentName)
        #archive directory may add a file extension
        ext = os.path.splitext(fn)[1]
        documentName = documentName + ext
        self.uploadFile(fn, "/".join([keyNamePrefix, documentName]))
        os.remove(fn)

    def downloadCompressed(self, keyNamePrefix, documentName, localPath):
        documentName = "{0}.{1}".format(documentName, self.__format)
        archiveName =  os.path.join(self.localTempDir, documentName.replace('/', '_'))
        #for the above replace: if the documentname itself represents a nested S3 key, 
        #convert it to something that can be written to file systems for the local temp file
        self.downloadFile("/".join([keyNamePrefix, documentName]), archiveName)
        self.unpackFileOrDirectory(archiveName, localPath)
        os.remove(archiveName)

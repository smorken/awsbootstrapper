import logging, os
class LogHelper(object):

    @staticmethod
    def start_logging(fn=".\\script.log",fmode='w', use_console=True):
        #set up logging to print to console window and to log file
        #
        # From http://docs.python.org/2/howto/logging-cookbook.html#logging-cookbook
        #
        rootLogger = logging.getLogger()

        logFormatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M')

        fileHandler = logging.FileHandler(fn, fmode)
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)
        if use_console:
            consoleHandler = logging.StreamHandler()
            consoleHandler.setFormatter(logFormatter)
            rootLogger.addHandler(consoleHandler)

        rootLogger.setLevel(logging.INFO)

    @staticmethod
    def instanceLogFileName(instanceId):
        return "log_instance{0}.txt".format(instanceId)

    @staticmethod
    def instanceLogPath(workingdir, instanceId):
        return os.path.join(workingdir, LogHelper.instanceLogFileName(instanceId))
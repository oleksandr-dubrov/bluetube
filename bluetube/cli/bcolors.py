class Bcolors:
    '''CLI color codes and wrappers.'''

    BOLD = '\033[1m'
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    @staticmethod
    def disable():
        Bcolors.BOLD = ''
        Bcolors.HEADER = ''
        Bcolors.OKBLUE = ''
        Bcolors.OKGREEN = ''
        Bcolors.WARNING = ''
        Bcolors.FAIL = ''
        Bcolors.ENDC = ''

    @staticmethod
    def warn(txt):
        print('{}{}{}'.format(Bcolors.WARNING, txt, Bcolors.ENDC))

    @staticmethod
    def error(txt):
        print('{}{}{}'.format(Bcolors.FAIL, txt, Bcolors.ENDC))

    @staticmethod
    def intense(txt):
        print('{}{}{}'.format(Bcolors.BOLD, txt, Bcolors.ENDC))

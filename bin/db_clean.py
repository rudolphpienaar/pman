#!/usr/bin/env python3
#
# (c) 2020 Fetal-Neonatal Neuroimaging & Developmental Science Center
#                   Boston Children's Hospital
#
#              http://childrenshospital.org/FNNDSC/
#                        dev@babyMRI.org
#

import  sys
import  os
from    distutils.sysconfig     import get_python_lib

from    argparse                import RawTextHelpFormatter
from    argparse                import ArgumentParser
import  shutil

import  pfmisc
from    pfmisc._colors          import Colors
from    pfmisc.C_snode          import  *


str_version = "1.0.0.2"
str_name    = 'db_clean'
str_desc    = Colors.CYAN + """
     _ _          _
    | | |        | |
  __| | |__   ___| | ___  __ _ _ __    _ __  _   _
 / _` | '_ \ / __| |/ _ \/ _` | '_ \  | '_ \| | | |
| (_| | |_) | (__| |  __/ (_| | | | |_| |_) | |_| |
 \__,_|_.__/ \___|_|\___|\__,_|_| |_(_) .__/ \__, |
         ______                       | |     __/ |
        |______|                      |_|    |___/


    font generated by:
    http://patorjk.com/software/taag/#p=display&f=Doom&t=db_clean


                             DataBase cleaner

           A simple stand alone script that merely cleans the
           pman database.

                              -- version """ + \
           Colors.YELLOW + str_version + Colors.CYAN + """ --

    'db_clean.py' is very simple app that performs the same set
    of operations that `pman` doesn in cleaning its internal
    file-system based state DB.

    The need for the script was simply to address a quick and
    simple mechanism for effecting a `pman` data base clean after
    CUBE integration tests.


""" + Colors.NO_COLOUR

class db_clean:
    def __init__(self, **kwargs):
        """
        Simple constructor
        """
        self.str_DBpath         = "/tmp/pman"
        self.__name__           = "db_clean"

        # Debug parameters
        self.str_debugFile      = '/dev/null'
        self.b_debugToFile      = True
        self.verbosity          = 1

        for key,val in kwargs.items():
            if key == 'DBpath':         self.str_DBpath     = val
            if key == 'verbosity':      self.verbosity      = int(val)


        self.dp                 = pfmisc.debug(
                                            verbosity   = self.verbosity,
                                            within      = self.__name__,
                                            syslog      = False
                                )
        self.dp.methodcol       = 20

    def do(self):
        """
        Main method to clear the DB.

        Essentially, this simply overwrites the file-based
        state information that `pman` maintains.

        """

        def saveToDiskAsJSON(tree_DB):
            tree_DB.tree_save(
                startPath       = '/',
                pathDiskRoot    = self.str_DBpath,
                failOnDirExist  = False,
                saveJSON        = True,
                savePickle      = False)

        self.dp.qprint('%50s%8s' % ('Clearing internal memory DB...', 
                                    '[ done ]'))
        tree_DB = C_stree()
        self.dp.qprint('%50s%8s' % ('Removing DB from persistent storage...', 
                                    '[ done ]'))
        if os.path.isdir(self.str_DBpath):
            shutil.rmtree(self.str_DBpath, ignore_errors=True)
        self.dp.qprint('%50s%8s' % ('Saving empty DB to peristent storage...',
                                    '[ done ]'))
        saveToDiskAsJSON(tree_DB)

def synopsis(ab_shortOnly = False):
    scriptName = os.path.basename(sys.argv[0])
    shortSynopsis =  '''
    NAME

	    db_clean.py

        - clean a `pman` database

    SYNOPSIS

            db_clean.py                                             \\
                [--DBpath <str_location>]                           \\
                [--synopsis]                                        \\
                [--desc]                                            \\
                [--version]                                         \\
                [--verbosity <level>]

    BRIEF EXAMPLE

            db_clean.py

    '''

    description =  '''
    DESCRIPTION

        `db_clean.py` simply cleans a `pman` filesystem state "tree".

    ARGS

        [--DBpath <str_location>]
        The location on persistent storage of the state "data base".
        Typically this is `/tmp/pman`.

        [-x|--desc]
        Provide an overview help page.

        [-y|--synopsis]
        Provide a synopsis help summary.

        [--version]
        Print internal version number and exit.

        [-v|--verbosity <level>]
        Set the verbosity level. "0" typically means no/minimal output. 


    EXAMPLES

            db_clean.py --DBpath /tmp/pman

    '''
    if ab_shortOnly:
        return shortSynopsis
    else:
        return shortSynopsis + description

parser  = ArgumentParser(description = str_desc, formatter_class = RawTextHelpFormatter)


parser.add_argument(
    "-p", "--DBpath",
    help    = "location of the DB path",
    dest    = 'DBpath',
    default = "/tmp/pman"
)
parser.add_argument(
    '--version',
    help    = 'if specified, print version number',
    dest    = 'b_version',
    action  = 'store_true',
    default = False
)
parser.add_argument(
    "-v", "--verbosity",
    help    = "verbosity level for app",
    dest    = 'verbosity',
    default = "1")
parser.add_argument(
    "-x", "--desc",
    help    = "long synopsis",
    dest    = 'desc',
    action  = 'store_true',
    default = False
)
parser.add_argument(
    "-y", "--synopsis",
    help    = "short synopsis",
    dest    = 'synopsis',
    action  = 'store_true',
    default = False
)

args = parser.parse_args()


if args.desc or args.synopsis:
    print(str_desc)
    if args.desc:
        str_help     = synopsis(False)
    if args.synopsis:
        str_help     = synopsis(True)
    print(str_help)
    sys.exit(1)

if args.b_version:
    print("Version: %s" % str_version)
    sys.exit(1)

clean   = db_clean(
            DBpath      = args.DBpath,
            verbosity   = args.verbosity
        )
clean.do()
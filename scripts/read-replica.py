#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import pprint
import sys

from lib import ReplicaServer

def main(argv=None):

    if not argv:
        argv = sys.argv
    if len(argv) != 2:
        print "Bad params " + str(argv)
    else:
        server = argv[1].upper()
        pprint.pprint(ReplicaServer(server).read())

if __name__ == "__main__":
    main()

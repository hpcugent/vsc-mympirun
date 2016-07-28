"""Tests for the jenkins version problems"""
import os
import unittest
import pkgutil
import sys


print("syspath0 %s" % sorted([(k,getattr(v,'__file__', getattr(v, '__path__', None))) for k,v in sys.modules.items() if k.startswith('vsc.mympirun') ]))


from vsc.mympirun.factory import getinstance

print("syspath1 %s" % sorted([(k,getattr(v,'__file__', getattr(v, '__path__', None))) for k,v in sys.modules.items() if k.startswith('vsc.mympirun') ]))

import vsc.mympirun.mpi as m
import vsc.mympirun.mpi.mpi as mpim

print("syspath2 %s" % sorted([(k,getattr(v,'__file__', getattr(v, '__path__', None))) for k,v in sys.modules.items() if k.startswith('vsc.mympirun') ]))

print("mpi_path %s mpim_file %s , listdir_map%s" % (m.__path__, mpim.__file__, map(os.listdir,m.__path__)))


os.environ["PATH"] = os.path.dirname(os.path.realpath(__file__)) + os.pathsep + os.environ["PATH"]


class TestMPI(unittest.TestCase):

    def test_version(self):
        print("mpim_file %s" % mpim.__file__)
        print("list dir %s" % os.listdir("/var/lib/jenkins/.vsc/lib/python/"))

        for loader, modulename, _ in pkgutil.walk_packages([mpim.__file__]):
            loader.find_module(modulename).load_module(modulename)

        print("mpi_path %s mpim_file %s" % (m.__path__, mpim.__file__))

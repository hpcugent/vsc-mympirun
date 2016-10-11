#!/usr/bin/env python
# -*- coding: latin-1 -*-
#
# Copyright 2009-2012 Ghent University
# Copyright 2009-2012 Stijn De Weirdt
# Copyright 2012 Andy Georges
#
# This file is part of VSC-tools,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/VSC-tools
#
# VSC-tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# VSC-tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VSC-tools. If not, see <http://www.gnu.org/licenses/>.
#
"""
Setup for mympirun
"""
import os
import pkgutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

import vsc.install.shared_setup as shared_setup
from vsc.install.shared_setup import vsc_setup, log, sdw
import vsc.mympirun.mpi.mpi as mpim
from vsc.utils.missing import get_subclasses

PACKAGE = {
    'install_requires': [
        'vsc-base >= 2.5.0',
        'vsc-install >= 0.10.9', # for modified subclassing
        'IPy',
    ],
    'version': '3.4.4',
    'author': [sdw],
    'maintainer': [sdw],
    'zip_safe': False,
}


class mympirun_vsc_install_scripts(vsc_setup.vsc_install_scripts):


    def run(self):
        """
        make a fake mpirun, that replaces the symlinks of all the mpirun aliases.
        This way any mpirun call will be passed to the fake mpirun.

        Next, symlink the fake mpirun to the mympirun executable.
        This way any mpirun call will be passed to the mympirun executable, but we can see that it passed through
        the fake mpirun
        """

        # import all modules in this dir: http://stackoverflow.com/a/16853487
        for loader, modulename, _ in pkgutil.walk_packages([os.path.dirname(mpim.__file__)]):
            loader.find_module(modulename).load_module(modulename)

        mympirun_aliases = []

        for mpiclass in get_subclasses(mpim.MPI):
            mympirun_aliases += mpiclass._mpiscriptname_for

        mympirun_aliases += ['myscoop']


        log.info("mympirun_vsc_install_scripts %s", mpim)
        # old-style class
        vsc_setup.vsc_install_scripts.run(self)

        for script in self.original_outfiles:
            if script.endswith(".py") or script.endswith(".sh"):
                script = script[:-3]

            if script.endswith('/mympirun'):

                # store current working dir so we can get back to it
                previous_pwd = os.getcwd()

                # get script basename and dirname
                rel_script = os.path.basename(script)
                rel_script_dir = os.path.dirname(script)
                os.chdir(rel_script_dir)

                # create symlinks that point to mympirun for all mpirun aliases
                for sym_name in mympirun_aliases:
                    if os.path.exists(sym_name):
                        os.remove(sym_name)
                    os.symlink(rel_script, sym_name)
                    newoutfile = os.path.join(rel_script_dir, sym_name)
                    self.outfiles.append(newoutfile)
                    log.info("symlink %s to %s newoutfile %s", rel_script, sym_name, newoutfile)

                # create a directory for faking mpirun
                os.chdir(previous_pwd)
                abs_fakepath = os.path.join(self.install_dir, mpim.FAKE_SUBDIRECTORY_NAME)
                if not os.path.isdir(abs_fakepath):
                    log.info("creating abs_fakepath %s", abs_fakepath)
                    os.mkdir(abs_fakepath)
                else:
                    log.info("not creating abs_fakepath %s (already exists)", abs_fakepath)

                # create a fake mpirin and symlink the real mpirun to it
                os.chdir(abs_fakepath)
                fake_mpirun = os.path.join(abs_fakepath, 'mpirun')
                if os.path.exists(fake_mpirun):
                    os.remove(fake_mpirun)

                # create another symlink that links mpirun to mympirun
                mympirun_src = '../%s' % rel_script
                os.symlink(mympirun_src, 'mpirun')
                self.outfiles.append(fake_mpirun)
                log.info("symlink %s to %s newoutfile %s", mympirun_src, 'mpirun', fake_mpirun)

                os.chdir(previous_pwd)

class mympirun_vsc_setup(vsc_setup):
    vsc_install_scripts = mympirun_vsc_install_scripts

# Monkeypatch setuptools.easy_install.install_egg_scripts.metadata_listdir
# because easy_install ignores the easy_install cmdclass
#
# The metadata_listdir assumes no subdirectories in scripts dir.
# We replace it with a function that calls the original metadata_listdir, searches through it results for the fake
# mympirun directory, appends '/mpirun' to it and returns the final result.
# The function is used through a whole bunch of Egg classes, no way we can easily intercept this
try:
    from setuptools.command.easy_install import easy_install

    _orig_install_egg_scripts = sys.modules['setuptools.command.easy_install'].easy_install.install_egg_scripts

    def _new_install_egg_scripts(self, dist):
        orig_func = dist.metadata_listdir
        def new_func(txt):
            res = orig_func(txt)
            if txt == 'scripts':
                log.debug('mympirun easy_install.install_egg_scripts scripts res %s', res)
                if mpim.FAKE_SUBDIRECTORY_NAME in res:
                    idx = res.index(mpim.FAKE_SUBDIRECTORY_NAME)
                    if idx >= 0:
                        res[idx] = '%s/mpirun' % mpim.FAKE_SUBDIRECTORY_NAME
            return res
        dist.metadata_listdir = new_func
        _orig_install_egg_scripts(self, dist)

    sys.modules['setuptools.command.easy_install'].easy_install.install_egg_scripts = _new_install_egg_scripts
except Exception as e:
    raise Exception("mympirun requires setuptools: %s" % e)


if __name__ == '__main__':
    shared_setup.action_target(PACKAGE)

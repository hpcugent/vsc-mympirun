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
import sys
import vsc.install.shared_setup as shared_setup
from vsc.install.shared_setup import action_target, vsc_setup, log, sdw

# issue #51: should taken from the code where it is used
FAKE_SUBDIRECTORY_NAME = 'fake'

# issue #50: generate these somehow from lib/vsc/mympirun/mpi/mpi.py
MYMPIRUN_ALIASES = ['%smpirun' % x for x in ['i', 'ih', 'o', 'm', 'mh', 'mm', 'q', 'm2', 'm2h']] + ['myscoop']

PACKAGE = {
    'install_requires': [
        'vsc-base >= 2.5.0',
        'IPy',
    ],
    'version': '3.4.4',
    'author': [sdw],
    'maintainer': [sdw],
}

# Monkeypatch shared_setup.vsc_setup
# because subclassing vsc_setup and it's the classes is tricky
# (lots of vsc_setup() self-referencing in shared_setup?)
class mympirun_vsc_install_scripts(vsc_setup.vsc_install_scripts):
    def run(self):
        # old-style class
        vsc_setup.vsc_install_scripts.run(self)

        for script in self.original_outfiles:
            if script.endswith(".py") or script.endswith(".sh"):
                script = script[:-3]

            if script.endswith('/mympirun'):
                # make the fake dir, create all symlinks

                # make all links
                # they are created with relative paths !

                rel_script = os.path.basename(script)
                rel_script_dir = os.path.dirname(script)

                # abspath: all_syms = [os.path.join(self.install_dir, x) for x in MYMPIRUN_ALIASES]
                # abspath: all_syms.append(os.path.join(abs_fakepath, 'mpirun'))
                # with relative paths, we also need to chdir for the fake/mpirun and ref to ../mympirun
                previous_pwd = os.getcwd()

                os.chdir(rel_script_dir)
                for sym_name in MYMPIRUN_ALIASES:
                    if os.path.exists(sym_name):
                        os.remove(sym_name)
                    os.symlink(rel_script, sym_name)
                    newoutfile = os.path.join(rel_script_dir, sym_name)
                    self.outfiles.append(newoutfile)
                    log.info("symlink %s to %s newoutfile %s" % (rel_script, sym_name, newoutfile))

                # fake mpirun
                os.chdir(previous_pwd)
                abs_fakepath = os.path.join(self.install_dir, FAKE_SUBDIRECTORY_NAME)
                if not os.path.isdir(abs_fakepath):
                    log.info("creating abs_fakepath %s" % abs_fakepath)
                    os.mkdir(abs_fakepath)
                else:
                    log.info("not creating abs_fakepath %s (already exists)" % abs_fakepath)

                os.chdir(abs_fakepath)  # abs_fakepath si not always absolute
                fake_mpirun = os.path.join(abs_fakepath, 'mpirun')
                if os.path.exists(fake_mpirun):
                    os.remove(fake_mpirun)

                mympirun_src = '../%s' % rel_script
                os.symlink(mympirun_src, 'mpirun')
                self.outfiles.append(fake_mpirun)
                log.info("symlink %s to %s newoutfile %s" % (mympirun_src, 'mpirun', fake_mpirun))

                os.chdir(previous_pwd)

vsc_setup.vsc_install_scripts = mympirun_vsc_install_scripts

# Monkeypatch setuptools.easy_install
# because easy_install ignores the easy_install cmdclass
try:
    from setuptools.command.easy_install import easy_install

    _orig_install_egg_scripts = sys.modules['setuptools.command.easy_install'].easy_install.install_egg_scripts

    def _new_install_egg_scripts(self, dist):
        orig_func = dist.metadata_listdir
        def new_func(txt):
            """
            The original metadata_listdir assumes no subdirectories in scripts dir.
            fake/mpirun is the exception (mpirun itself is not listed !)
            The function is used through a whole bunch of Egg classes, no way we can easily intercept this
            """
            res = orig_func(txt)
            if txt == 'scripts':
                if FAKE_SUBDIRECTORY_NAME in res:
                    idx = res.index(FAKE_SUBDIRECTORY_NAME)
                    if idx >= 0:
                        res[idx] = '%s/mpirun' % FAKE_SUBDIRECTORY_NAME
            return res
        dist.metadata_listdir = new_func
        _orig_install_egg_scripts(self, dist)

    sys.modules['setuptools.command.easy_install'].easy_install.install_egg_scripts = _new_install_egg_scripts
except Exception as e:
    raise Exception("mympirun requires setuptools: %s" % e)


if __name__ == '__main__':
    shared_setup.action_target(PACKAGE)

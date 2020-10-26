#!/usr/bin/env python
# -*- coding: latin-1 -*-
#
# Copyright 2009-2020 Ghent University
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
import sys
import vsc.install.shared_setup as shared_setup
from vsc.install.shared_setup import vsc_setup, log, sdw, kh

FAKE_SUBDIRECTORY_NAME = 'fake'

# hardcoded list, to avoid ugly hacks in order to be able to import from vsc.mympirun in setup.py...
# this list is checked to be synced via a dedicated unit test
MYMPIRUN_ALIASES = ['ihmpirun', 'impirun', 'm2hmpirun', 'm2mpirun', 'mhmpirun', 'mmpirun', 'myscoop', 'ompirun']

PACKAGE = {
    'install_requires': [
        'vsc-base >= 3.0.1',
        'vsc-install >= 0.15.1',
        'IPy',
    ],
    'tests_require': [
        'mock',
    ],
    'version': '5.2.2',
    'author': [sdw, kh],
    'maintainer': [sdw, kh],
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
                for sym_name in MYMPIRUN_ALIASES:
                    if os.path.exists(sym_name):
                        os.remove(sym_name)
                    os.symlink(rel_script, sym_name)
                    newoutfile = os.path.join(rel_script_dir, sym_name)
                    self.outfiles.append(newoutfile)
                    log.info("symlink %s to %s newoutfile %s", rel_script, sym_name, newoutfile)

                # create a directory for faking mpirun
                os.chdir(previous_pwd)
                abs_fakepath = os.path.join(self.install_dir, FAKE_SUBDIRECTORY_NAME)
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
    from setuptools.command.easy_install import easy_install  # NOQA
    _orig_install_egg_scripts = sys.modules['setuptools.command.easy_install'].easy_install.install_egg_scripts

    def _new_install_egg_scripts(self, dist):
        orig_func = dist.metadata_listdir

        def new_func(txt):
            res = orig_func(txt)
            if txt == 'scripts':
                log.debug('mympirun easy_install.install_egg_scripts scripts res %s', res)
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

# next monstrocity: inject header in script to filter out PYTHONPATH in mixed EB py3/py2 envs
# mympirun modules rely on the system python and dependencies, so this is fine
#   however, system python might pick up loaded Python-2.X modules, and then nothing should be done
# this can be removed as soon as mympirun is py3 safe
EB_SAFE_HEADER = """
import os
import sys
ebp = os.environ.get('EBROOTPYTHON', None)
if ebp and not os.__file__.startswith(ebp):
    # ebroots excpet mympirun
    ignore = [v for k,v in os.environ.items() if k.startswith('EBROOT') and not k.endswith('VSCMINMYMPIRUN')]
    # add realpaths to (sys.path normally ojnly has realpaths)
    ignore += [os.path.realpath(x) for x in ignore if os.path.exists(x)]
    # remove sys.path entries that start with eb path
    sys.path = [x for x in sys.path if not [y for y in ignore if x.startswith(y)]]
"""
# this is a bit tricky, since setuptools some version has moved the function as classmethod to the ScriptWriter class
#   there is also a legacy/deprecated get_script_header classmethod
# this will also trigger the magic for all dependencies pulled in
try:
    orig_header = sys.modules['setuptools.command.easy_install'].ScriptWriter.get_header
    def new_header(cls, *args, **kwargs):  #pylint: disable=unused-argument
        return orig_header(*args, **kwargs) + EB_SAFE_HEADER
    sys.modules['setuptools.command.easy_install'].ScriptWriter.get_header = classmethod(new_header)
except Exception as e:
    orig_header = sys.modules['setuptools.command.easy_install'].get_script_header
    def new_header(*args, **kwargs):
        return orig_header(*args, **kwargs) + EB_SAFE_HEADER
    sys.modules['setuptools.command.easy_install'].get_script_header = new_header


if __name__ == '__main__':
    shared_setup.action_target(PACKAGE)

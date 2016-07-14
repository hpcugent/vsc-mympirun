#
# Copyright 2009-2016 Ghent University
#
# This file is part of vsc-mympirun,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# the Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/hpcugent/vsc-mympirun
#
# vsc-mympirun is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# vsc-mympirun is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vsc-mympirun.  If not, see <http://www.gnu.org/licenses/>.
#
"""
QLogicMPI specific class

Documentation can be found at filedownloads.qlogic.com/files/manual/68842/IB6054601-00G.pdf
"""

from vsc.mympirun.mpi.mpi import MPI
import os


class QLogicMPI(MPI):

    _mpiscriptname_for = ['qmpirun']
    _mpirun_for = ['QLogicMPI']

    RUNTIMEOPTION = {'options': {'quiescencecheck': (("Set level of quiescence checking (default 1) [0=No ; "
                                                      "1=Some checking; 2: All supported checking]"), "int", "store", 1)
                                 },
                     'prefix': 'qlogicmpi',
                     'description': ('QLogicMPI options', 'Advanced options specific for QLogicMPI'),
                     }

    MPIEXEC_QUIESCENCECHECK_MAP = {0: '-q 0',
                                   1: '-disable-mpi-progress-check',
                                   2: ''}

    MPIEXEC_TEMPLATE_GLOBAL_OPTION = "export %(name)s='%(value)s'"
    MPIEXEC_TEMPLATE_LOCAL_OPTION = "export %(name)s='%(value)s'"
    MPIEXEC_TEMPLATE_PASS_VARIABLE_OPTION = "export %(name)s='%(value)s'"

    def _pin_flavour(self, mp=None):
        if self.options.hybrid is not None and self.options.hybrid > 0:
            if self.pinning_override_type is not None:
                self.pinning_override_type = 'spread'
                self.log.debug("pin_flavour: hybrid mode: overwritepin not set, setting to default %s" %
                               self.pinning_override_type)
        return mp

    def get_pinning_override_variable(self):
        """
        QLogic MPI has no real fine control
          - affinity is packed, no MP opts
          - one has to calculate the map oneself and then calculate the affinity
            - variables: PSC_MPI_NODE_RANK, PSC_MPI_PPN, PSC_MPI_NP, PSC_MPI_RANK
            - then start the real exe with numactl or taskset
        """
        return 'PSC_MPI_NODE_RANK'

    def mpiexec_get_global_options(self):
        """Using rcfile with all options
            Use it to set quiescence options
        """
        quiescence_opts = self.MPIEXEC_QUIESCENCECHECK_MAP[self.options.qlogicmpi_quiescencecheck]
        self.log.debug("mpiexec_get_global_options: only setting quiescence options here: %s." % quiescence_opts)

        return [quiescence_opts]

    def mpiexec_get_local_options(self):
        """Using rcfile with all options"""
        return []

    def mpiexec_get_local_pass_variable_options(self):
        """There is a rcfile style option"""
        opts = ['']
        opts += ["## global variables", ''] + super(QLogicMPI, self).mpiexec_get_local_options() + ['']
        opts += ["## local variables", ''] + super(QLogicMPI, self).mpiexec_get_global_options() + ['']
        opts += ["## passvariables", ''] + super(QLogicMPI, self).mpiexec_get_local_pass_variable_options() + ['']

        txt = "\n".join(opts)
        try:
            fn = os.path.join(self.mympirundir, 'qlcrcfile')
            file(fn, 'w').write(txt)
            self.log.debug("mpiexec_get_local_pass_variable_options: wrote rcfile %s:\n%s" % (fn, txt))
        except IOError:
            self.log.raiseException('mpiexec_get_local_pass_variable_options: failed to write rcfile %s' % (fn))

        variables = "-rcfile %s" % fn
        self.log.debug("mpiexec_get_local_pass_variable_options returns %s" % variables)
        return [variables]

    def _make_final_mpirun_cmd(self):
        """Create the acual mpirun command and add it to self.mpirun_cmd"""
        # mpirun opts
        if self.options.debuglvl > 0:
            self.mpirun_cmd.append('-V')

        if self.options.stats > 0:
            stats_map = ['mpi']
            if self.options.stats > 2:
                stats_map.append('ipath')
            if self.options.stats > 4:
                stats_map.append('p2p')
            if self.options.stats > 10:
                stats_map.append('all')
            self.mpirun_cmd.append("-print-stats=%s" % ','.join(stats_map))

        self.mpirun_cmd += self.mpiexec_options

    def qlogic_ipath(self):
        """Override some settings to deal with broken ipath load balancing"""
        super(QLogicMPI, self).qlogic_ipath()

        # pin all resources on single adapter, allow shared contexts
        # can be externally disabled by setting PSM_SHAREDCONTEXTS=0 and IPATH_UNIT=-1
        self.mpiexec_global_options['PSM_SHAREDCONTEXTS'] = '1'
        self.mpiexec_global_options['IPATH_UNIT'] = '0'

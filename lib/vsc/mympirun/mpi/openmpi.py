#
# Copyright 2009-2020 Ghent University
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
OpenMPI specific classes
Documentation can be found at https://www.open-mpi.org/doc/
"""
import os
import re
import sys
from vsc.utils.missing import nub
from vsc.utils.run import CmdList, run

from vsc.mympirun.common import version_in_range
from vsc.mympirun.mpi.mpi import MPI


SLURM_EXPORT_ENV = 'SLURM_EXPORT_ENV'


class OpenMPI(MPI):

    """An implementation of the MPI class for OpenMPI"""

    _mpiscriptname_for = ['ompirun']
    _mpirun_for = 'OpenMPI'
    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, None, '1.7.0'))

    DEVICE_MPIDEVICE_MAP = {
        'det': 'sm,tcp,self',
        'ib': 'sm,openib,self',
        'shm': 'sm,self',
        'socket': 'sm,tcp,self',
    }

    MPIEXEC_TEMPLATE_GLOBAL_OPTION = ['--mca', '%(name)s', "%(value)s"]

    REMOTE_OPTION_TEMPLATE = ['--mca', 'pls_rsh_agent', '%(rsh)s']

    def use_ucx_pml(self):
        """Determine whether or not to use the UCX Point-to-Point Messaging Layer (PML)."""
        # don't use UCX by default (mostly because of backwards-compatibility)
        return False

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""

        if self.use_ucx_pml():
            self.mpiexec_global_options['pml'] = 'ucx'
            # disable uct btl, see http://openucx.github.io/ucx/running.html
            self.mpiexec_global_options['btl'] = '^uct'
        else:
            # default PML (ob1) uses Byte Transport Layer (BTL)
            self.mpiexec_global_options['btl'] = self.device

        # make sure Open Run-Time Environment (ORTE) uses FQDN hostnames
        # using short hostnames may cause problems (e.g. if SLURM is configured to use FQDN hostnames)
        self.mpiexec_global_options['orte_keep_fqdn_hostnames'] = '1'

        super(OpenMPI, self).set_mpiexec_global_options()

    def set_mpiexec_options(self):
        """Set mpiexec options"""
        super(OpenMPI, self).set_mpiexec_options()

        # specify number of processes to start per node if --hybrid is used
        if self.options.hybrid:
            procs_per_node = self.multiplier * self.options.hybrid
            self.mpiexec_options.add(['--map-by', 'ppr:%s:node' % procs_per_node])

    def _make_final_mpirun_cmd(self):
        """
        Create the acual mpirun command
        OpenMPI doesn't need mpdboot options
        """
        self.mpirun_cmd.add(self.mpiexec_options)

    def determine_sockets_per_node(self):
        """
        Try to determine the number of sockets per node; either specified by --sockets-per-node or using /proc/cupinfo
        """
        sockets_per_node = self.options.sockets_per_node
        if sockets_per_node == 0:
            try:
                proc_cpuinfo = open('/proc/cpuinfo').read()
            except IOError as err:
                error_msg = "Failed to read /proc/cpuinfo to determine number of sockets per node: %s" % err
                error_msg += "; use --sockets-per-node to override"
                self.log.error(error_msg)
                sys.exit(1)

            if proc_cpuinfo:
                res = re.findall('^physical id.*', proc_cpuinfo, re.M)
                sockets_per_node = len(nub(res))
                self.log.debug("Sockets per node found in cpuinfo: set to %s" % sockets_per_node)

            if sockets_per_node == 0:
                self.log.warning("Could not derive number of sockets per node from /proc/cpuinfo. "
                                 "Assuming a single socket, use --sockets-per-node to override.")
                sockets_per_node = 1

        return sockets_per_node

    def pinning_override(self):
        """ pinning """

        override_type = self.pinning_override_type

        self.log.debug("pinning_override: type %s ", override_type)

        ranktxt = ""
        sockets_per_node = self.determine_sockets_per_node()
        universe = self.options.universe or self.nodes_tot_cnt

        try:
            rankfn = os.path.join(self.mympirundir, 'rankfile')

            if override_type in ('packed', 'compact', 'bunch'):
                # pack ranks, filling every consecutive slot on every consecutive node
                for rank in range(universe):
                    node = rank / self.ppn
                    socket = rank / (self.ppn / sockets_per_node)
                    slot = rank % (self.ppn / sockets_per_node)
                    ranktxt += "rank %i=+n%i slot=%i:%i\n" % (rank, node, socket, slot)

            elif override_type in ('spread', 'scatter'):
                # spread ranks evenly across nodes, but also spread them across sockets
                for rank in range(universe):
                    node = rank % self.nodes_tot_cnt
                    socket = (rank % self.ppn) % sockets_per_node
                    slot = (rank % self.ppn) / sockets_per_node
                    ranktxt += "rank %i=+n%i slot=%i:%i\n" % (rank, node, socket, slot)

            else:
                self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                        self.pinning_override_type)

            with open(rankfn, 'w') as fp:
                fp.write(ranktxt)
            self.log.debug("pinning_override: wrote rankfile %s:\n%s", rankfn, ranktxt)
            cmd = CmdList('-rf', rankfn)

        except IOError as err:
            self.log.raiseException('pinning_override: failed to write rankfile %s: %s' % (rankfn, err))

        return cmd

    def make_machine_file(self, nodetxt=None, universe=None):
        """
        Make the machinefile.
        Parses the list of nodes that run an MPI process and writes this information to a machinefile.
        """
        if self.mpinodes is None:
            self.set_mpinodes()

        if nodetxt is None:
            nodetxt = ''
            # if --universe is specified, we control how many processes per node are run via 'slots='
            if universe is not None and universe > 0:
                universe_ppn = self.get_universe_ncpus()
                for node in nub(self.mpinodes):
                    nodetxt += "%s slots=%s\n" % (node, universe_ppn[node])

            # in case of oversubscription or multinode, also use 'slots='
            elif self.multiplier > 1 or self.ppn < len(self.mpinodes):
                for node in nub(self.mpinodes):
                    nodetxt += '%s slots=%s\n' % (node, self.ppn)
            else:
                nodetxt = '\n'.join(self.mpinodes)

        super(OpenMPI, self).make_machine_file(nodetxt=nodetxt, universe=universe)

    def prepare(self):
        """Prepare environment"""
        # undefine $SLURM_EXPORT_ENV if it is set;
        # $SLURM_EXPORT_ENV is defined as 'NONE' by qsub wrappers for SLURM,
        # and then gets passed down to srun via mpirun, which may cause problems with 'orted' being found
        # because $PATH and $LD_LIBRARY_PATH are no longer set
        # (unless OpenMPI installation was configured with --enable-orterun-prefix-by-default)
        # cfr. https://www.mail-archive.com/devel@lists.open-mpi.org/msg17305.html
        if SLURM_EXPORT_ENV in os.environ:
            self.log.info("Undefining $%s (was '%s')", SLURM_EXPORT_ENV, os.getenv(SLURM_EXPORT_ENV))
            del os.environ[SLURM_EXPORT_ENV]

        super(OpenMPI, self).prepare()


class OpenMpiOversubscribe(OpenMPI):

    """
    An implementation of the MPI class for OpenMPI. Starting from version 1.7, --oversubscribe has to be used
    when requesting more processes than available processors.
    """

    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '1.7.0', '3'))

    def set_mpiexec_options(self):

        super(OpenMpiOversubscribe, self).set_mpiexec_options()

        if self.multiplier > 1 or len(self.mpinodes) > self.ppn:
            self.mpiexec_options.add("--oversubscribe")


class OpenMpi3(OpenMpiOversubscribe):

    """
    An implementation of the MPI class for OpenMPI 3.x & more recent.
    """

    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '3', '4'))

    # 'sm' BTL (Byte Transfer Layer) was replaced by the 'vader' BTL
    # cfr. https://www.open-mpi.org/faq/?category=sm
    DEVICE_MPIDEVICE_MAP = {
        'det': 'vader,tcp,self',
        'ib': 'vader,openib,self',
        'shm': 'vader,self',
        'socket': 'vader,tcp,self',
    }


class OpenMpi4(OpenMpi3):

    """
    An implementation of the MPI class for OpenMPI 4.x & more recent.
    """

    _mpirun_version = staticmethod(lambda ver: version_in_range(ver, '4', None))

    def use_ucx_pml(self):
        """Determine whether or not to use the UCX Point-to-Point Messaging Layer (PML)."""

        # use UCX if 'ompi_info' reports that it is a supported PML;
        # only for OpenMPI 4.x and newer, as recommended by UCX:
        # "OpenMPI supports UCX starting from version 3.0, but it's recommended to use
        # "version 4.0 or higher due to stability and performance improvements."
        # (see https://openucx.github.io/ucx/running.html#openmpi-with-ucx)
        cmd = "ompi_info"
        ec, out = run(cmd)
        if ec:
            self.log.raiseException("use_ucx_pml: failed to run cmd '%s', ec: %s, out: %s" % (cmd, ec, out))

        pml_ucx_pattern = ' pml: ucx '
        return bool(re.search(pml_ucx_pattern, out))

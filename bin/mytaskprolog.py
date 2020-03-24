#!/usr/bin/env python
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
Generate preferred CUDA_VISIBLE_DEVICES as part of srun task prolog

Work around some slurm issues
"""

from __future__ import print_function

from vsc.utils.affinity import sched_getaffinity


def export(key, value):
    """print export key=value, which is picked up by the task prolog"""
    print("export %s=%s" % (key, value))


def get_preferred_gpu_map():
    # issue #158: make generic or wait for schedmd fix, eg python nvml bindings
    #   this is the joltik map: 32 cores, even cores for gpu 0-1, odd for gpus 2-3
    #   so we prefer first 8 even cores for gpu 0, first 8 odd cores for gpu 1 etc etc
    GPU_MAP = [0, 2] * 8 + [1, 3] * 8
    return GPU_MAP


def preferred_cvd():
    """Generate the CUDA_VISIBLE_DEVICES value"""
    gpu_map = get_preferred_gpu_map()
    current_idx = [idx for idx, bit in enumerate(sched_getaffinity().get_cpus()) if bit and idx < len(gpu_map)]
    gpus = set([gpu_map[idx] for idx in current_idx])
    export('CUDA_VISIBLE_DEVICES', ','.join([str(x) for x in sorted(gpus)]))


def main():
    preferred_cvd()


if __name__ == '__main__':
    main()

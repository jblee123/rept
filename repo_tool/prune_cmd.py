################################################################################
# prune cmd funcs
#
# The "prune" command removes all remote branches from all repos on which the
# currently checked out revision of the current repo depend.
# i.e. 'git remote prune <remote>' is called for all dependent repos.
################################################################################

import subprocess
import sys

from repo_tool import rept_utils

def print_prune_usage():
    rept_utils.printerr('usage: rept prune')

def cmd_prune(dependencies, local_config, args):
    parsed_args = rept_utils.parse_args(
        args, '', usage_fn=print_prune_usage)

    if len(parsed_args[1]):
        rept_utils.print_unknown_arg(parsed_args[1][0])
        print_prune_usage()
        sys.exit(1)

    errs = []

    print('pruning {0} for this repo...'.format(local_config.remote))
    ret = subprocess.call(['git', 'remote', 'prune', local_config.remote])
    if (ret):
        errs.append(
            "error: cannot prune '{0}' for this repo".format(local_config.remote))

    for dep in dependencies:
        print('pruning {0}...'.format(dep.name))
        with rept_utils.DoInExistingDir(dep.path) as ctx:
            if ctx:
                ret = subprocess.call(['git', 'remote', 'prune', dep.remote])
                if (ret):
                    errs.append(
                        "error: cannot prune repo '{0}': ".format(dep.name))
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

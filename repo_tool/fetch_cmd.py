################################################################################
# fetch cmd funcs
#
# The "fetch" command fetches all repos on which the currently checked out
# revision of the current repo depend. i.e. 'git fetch <remote>' is called for
# all dependent repos.
################################################################################

import subprocess
import sys

from repo_tool import rept_utils

def print_fetch_usage():
    rept_utils.printerr('usage: rept fetch')

def cmd_fetch(dependencies, local_config, args):
    parsed_args = rept_utils.parse_args(
        args, '', usage_fn=print_fetch_usage)

    if len(parsed_args[1]):
        rept_utils.print_unknown_arg(parsed_args[1][0])
        print_fetch_usage()
        sys.exit(1)

    errs = []

    print('fetching {0} for this repo...'.format(local_config.remote))
    ret = subprocess.call(['git', 'fetch', local_config.remote])
    if (ret):
        errs.append(
            "error: cannot fetch '{0}' for this repo".format(local_config.remote))

    for dep in dependencies:
        print('fetching {0}...'.format(dep.name))
        with rept_utils.DoInExistingDir(dep.path) as ctx:
            if ctx:
                ret = subprocess.call(['git', 'fetch', dep.remote])
                if (ret):
                    errs.append(
                        "error: cannot fetch repo '{0}'".format(dep.name))
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

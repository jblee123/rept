################################################################################
# sync cmd funcs
#
# The "sync" command is used to get all code that the currently checked out
# revision of a repo needs to build. All repos on which the main repo depends
# are pulled fetched or cloned as needed, and the specific revisions of those
# repos are checked out.
################################################################################

import errno # python 2 hack
import os
import sys

from repo_tool import check_deps_cmd
from repo_tool import rept_utils

def print_sync_usage():
    rept_utils.printerr('usage: rept sync')

def cmd_sync(dependencies, args):
    parsed_args = rept_utils.parse_args(
        args, '', usage_fn=print_sync_usage)

    if len(parsed_args[1]):
        rept_utils.print_unknown_arg(parsed_args[1][0])
        print_sync_usage()
        sys.exit(1)

    errs = []

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)

        # If the dir doesn't exist, it needs to. If it does, this is a no-op.
        # start python 2 hack
        #os.makedirs(repo_path, exist_ok=True)
        try:
            os.makedirs(repo_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise  # raises the error again
        # end python 2 hack

        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                # Empty dir? If so, do a clone.
                if not os.listdir('.'): # python 2 requires param
                    print('cloning repo {0}...'.format(dep.name))
                    full_remote_repo_name = dep.remote_server + dep.name
                    ret = rept_utils.exec_proc(
                        ['git', 'clone', '-o', dep.remote,
                         full_remote_repo_name, '.'], False)
                    if (ret):
                        errs.append(
                            'cannot sync "{0}": '
                            'fetch clone'.format(dep.path))
                # Already a .git dir? If so, do a fetch.
                elif (os.path.isdir('.git')):
                    print('fetching repo {0}...'.format(dep.name))
                    ret = rept_utils.exec_proc(
                        ['git', 'fetch', dep.remote], False)
                    if (ret):
                        errs.append(
                            'cannot sync "{0}": '
                            'fetch failed'.format(dep.path))
                else:
                    errs.append(
                        'cannot sync {0}: {1} is not empty '
                        'and is not a git repo'.format(
                            dep.name, dep.path))
                # No .git dir. Do a clone.
            else:
                errs.append(
                    'cannot sync {0}: cannot enter directory {1}'.format(
                        dep.name, dep.path))

    if errs:
        rept_utils.printerr('\n{0} errors:'.format(len(errs)))
        for err in errs:
            rept_utils.printerr('- ' + err)
        sys.exit(1)

    if not check_deps_cmd.do_check_dep_consistency(dependencies):
        sys.exit(
            'error: inconsistent dependencies. cannot proceed with checkout')

    for dep in dependencies:
        print('checking out {0} on {1}...'.format(dep.revision, dep.name))
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                ret = rept_utils.exec_proc(
                    ['git', 'checkout', '-q', dep.revision], False)
                if ret:
                    errs.append(
                        'cannot check out rev {0} for repo: {1}'.
                            format(dep.revision, dep.path))
            else:
                errs.append(
                    'cannot enter repo at {0} for checkout'.format(dep.path))

    if errs:
        rept_utils.printerr('\n{0} errors:'.format(len(errs)))
        for err in errs:
            rept_utils.printerr('- ' + err)
        sys.exit(1)
    else:
        print('\nSuccess')

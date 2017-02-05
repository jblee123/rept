################################################################################
# git util funcs
################################################################################

import os

from repo_tool import rept_utils

def get_rev_hash(rev):
    ret, out, err = rept_utils.exec_proc(['git', 'rev-parse', rev])
    return out if not ret else None

def get_rev_hash_from_repo(rev, repo_dir):
    rev_hash = None
    err = ''
    with rept_utils.DoInExistingDir(repo_dir) as ctx:
        if ctx:
            rev_hash = get_rev_hash(rev)
            if not rev_hash:
                err = 'could not get revision from the repo'
        else:
            err = 'could not enter the repo'
    return (rev_hash, err)

def get_branch_exists(branch_name):
    ret, out, err = rept_utils.exec_proc(
        ['git', 'rev-parse', '--verify', branch_name])
    return ret == 0

def is_current_branch(branch_name):
    ret, out, err = rept_utils.exec_proc(['git', 'branch'])
    if ret:
        return False

    branches = [branch.strip() for branch in out.split(os.linesep)]
    branch = [branch[2:] for branch in branches if branch.startswith('* ')]
    return branch[0] == branch_name if branch else False

def get_any_remote_branch_exists(branch_name):
    ret, out, err = rept_utils.exec_proc(['git', 'branch', '-a'])
    if ret:
        return []

    branches = out.split()
    return [branch for branch in branches if
        branch.startswith('remotes/') and branch.endswith('/' + branch_name)]

def is_branch_merged(branch_name):
    ret, out, err = rept_utils.exec_proc(['git', 'branch', '--merged'])
    if ret:
        return False

    branches = out.split()
    return branch_name in branches

def get_remotes():
    ret, out, err = rept_utils.exec_proc(['git', 'remote'])
    if ret:
        return []

    return [remote.strip() for remote in out.split(os.linesep)]

def is_clean_working_directory(count_untracked):
    cmd = ['git', 'status', '--porcelain']
    if not count_untracked:
        cmd.append('-uno')
    ret, out, err = rept_utils.exec_proc(cmd)

    return (ret == 0) and (out == '')

def get_file_contents_for_revision(rev, filename):
    spec = '{0}:{1}'.format(rev, filename)
    ret, out, err = rept_utils.exec_proc(['git', 'show', spec])
    return out if not ret else None

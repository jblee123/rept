################################################################################
# feature cmd funcs
#
# The "feature" command creates or deletes branches of the specified name across
# all dependency repos. In the main repo, the branch will point to the currently
# checked out commit, and the dependencies in the main repo's current working
# space are used to determine the commits to which the new branches in the
# dependency repos will refer.
#
# By default, deleting will delete all branches with the specified name in the
# main and dependency repos. The -d and -D options cause equivalent deletion
# behavior as git's "branch" command. That is, -d will fail if the branch is
# unmerged with the currently checked out branch, and -D will force deletion.
# If deleting, --push will additionally cause the deletions to be pushed to the
# remote, and --push-only will only push the deletion to the remote but will
# not delete the local branches.
################################################################################

import collections
import os
import sys

from repo_tool import git_utils
from repo_tool import rept_utils

FeatureArgs = collections.namedtuple('FeatureArgs',
    'name delete force push push_only')

FeatureBranchState = collections.namedtuple('FeatureBranchState',
    'exists is_current has_remote is_merged')

def can_create_feature_branch(branch_name, remote_name, dep_name, errs):
    if dep_name:
        err_prefix = 'dependency {0}'.format(dep_name)
    else:
        err_prefix = 'this repo'

    remote_branch_name = remote_name + '/' + branch_name
    if git_utils.get_branch_exists(branch_name):
        errs.append(
            '{0} already contains a local branch: {1}'.
            format(err_prefix, branch_name))
        return

    if dep_name:
        if git_utils.get_branch_exists(remote_branch_name):
            errs.append(
                '{0} already contains a remote branch: {1}'.
                format(err_prefix, remote_branch_name))
    else:
        remotes = git_utils.get_any_remote_branch_exists(branch_name)
        if remotes:
            len_remotes_prefix = len('remotes/')
            remotes = [remote[len_remotes_prefix:] for remote in remotes]
            if len(remotes) == 1:
                errs.append(
                    '{0} already contains a remote branch: {1}'.
                    format(err_prefix, remotes[0]))
            else:
                errs2 = [
                    '{0} already contains remote branches:'.
                    format(err_prefix)]
                errs2 += remotes
                errs.append(errs2)

def create_feature(dependencies, feat_args):
    errs = []

    can_create_feature_branch(feat_args.name, '', '', errs)

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                can_create_feature_branch(
                    feat_args.name, dep.remote, dep.name, errs)
            else:
                errs.append('Missing repo: {0}'.format(repo_name))
        dep_hash, hash_err = git_utils.get_rev_hash_from_repo(
            dep.revision, repo_path)
        if not dep_hash:
            errs.append(rept_utils.gen_bad_revision_err_str(
                dep.name, dep.revision, hash_err))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

    created_branches = 0

    ret = rept_utils.exec_proc(['git', 'branch', '-q', feat_args.name], False)
    if (not ret):
        created_branches += 1
    else:
        errs.append(
            'cannot create branch "{0}" in this repo'.format(feat_args.name))

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                ret = rept_utils.exec_proc(
                    ['git', 'branch', '-q', feat_args.name, dep.revision], False)
                if (not ret):
                    created_branches += 1
                else:
                    errs.append(
                        'cannot create branch "{0}": '
                        'in repo {1}'.format(feat_args.name, dep.name))
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    print('created {0}/{1} branches'.
        format(created_branches, len(dependencies) + 1))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

def get_feature_branch_state(branch_name, remote_name):

    remote_branch_name = remote_name + '/' + branch_name

    exists = git_utils.get_branch_exists(branch_name)
    is_current = git_utils.is_current_branch(branch_name)
    has_remote = git_utils.get_branch_exists(remote_branch_name)
    is_merged = git_utils.is_branch_merged(branch_name)

    return FeatureBranchState(
        exists, is_current, has_remote, is_merged)

def delete_feature_branch(dep, del_cmd, fail_list, errs):
    success = False
    if not dep:
        ret = rept_utils.exec_proc(del_cmd, False)
        if (not ret):
            success = True
        else:
            fail_list.append('this repo')
    else:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                ret = rept_utils.exec_proc(del_cmd, False)
                if (not ret):
                    success = True
                else:
                    fail_list.append('repo {0}'.format(dep.name))
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    return success

def delete_feature(dependencies, local_config, feat_args):
    errs = []
    branch_states = []

    state = get_feature_branch_state(feat_args.name, local_config.remote)
    branch_states.append((None, state))

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                state = get_feature_branch_state(feat_args.name, dep.remote)
                branch_states.append((dep, state))
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

    exists = [state for state in branch_states if state[1].exists]
    are_current = [state for state in branch_states
        if state[1].exists and state[1].is_current]
    has_remote = [state for state in branch_states if state[1].has_remote]
    unmerged = [state for state in branch_states
        if state[1].exists and not state[1].is_merged]

    def print_bad_repos(branch_states):
        for dep, state in branch_states:
            rept_utils.printerr(
                '  - {0}'.format(dep.name if dep else 'this repo'))

    if are_current and not feat_args.push_only:
        rept_utils.printerr(
            'error: cannot delete branches checked out in repos:')
        print_bad_repos(are_current)
        sys.exit(1)

    if unmerged and not feat_args.force and not feat_args.push_only:
        rept_utils.printerr(
            'error: cannot delete unmerged branches (use -D to force) in repos:')
        print_bad_repos(unmerged)
        sys.exit(1)

    deleted_branches_local = 0
    deleted_branches_remote = 0

    del_opt = '-D' if feat_args.force else '-d'
    del_local_cmd = ['git', 'branch', del_opt, '-q', feat_args.name]

    delete_locals = not feat_args.push_only
    delete_remotes = feat_args.push or feat_args.push_only

    local_del_fail = []
    remote_del_fail = []

    if delete_locals:
        for dep, state in exists:
            repo_name = dep.name if dep else 'this repo'
            print('deleting local branch in {0}'.format(repo_name))

            if delete_feature_branch(dep, del_local_cmd, local_del_fail, errs):
                deleted_branches_local += 1

    if delete_remotes:
        for dep, state in has_remote:
            repo_name = dep.name if dep else 'this repo'
            print('deleting remote branch in {0}'.format(repo_name))

            remote = dep.remote if dep else local_config.remote
            push_target = ':{0}'.format(feat_args.name)
            del_remote_cmd = ['git', 'push', '-q', remote, push_target]

            if delete_feature_branch(dep, del_remote_cmd, remote_del_fail, errs):
                deleted_branches_remote += 1

    def print_deletion_summary(
        failures, branch_type, del_count, del_attempt_count):
        print('deleted {0}/{1} {2} branches'.
            format(del_count, del_attempt_count, branch_type))
        if failures:
            rept_utils.printerr("error: couldn't delete branches from:")
        for failure in failures:
            print('  {0}'.format(failure))

    if delete_locals:
        print_deletion_summary(
            local_del_fail, 'local', deleted_branches_local, len(exists))

    if delete_remotes:
        print_deletion_summary(
            remote_del_fail, 'remote', deleted_branches_remote, len(has_remote))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

def parse_feature_args(args):
    parsed_args = rept_utils.parse_args(
        args, 'dD', ['push', 'push-only'], usage_fn=print_feature_usage)

    if len(parsed_args[1]) == 0:
        rept_utils.printerr('error: missing feature name')
        print_feature_usage()
        sys.exit(1)

    if len(parsed_args[1]) > 1:
        rept_utils.print_unknown_arg(parsed_args[1][1])
        print_feature_usage()
        sys.exit(1)

    delete = False
    force = False
    push = False
    push_only = False
    for opt, optarg in parsed_args[0]:
        if opt == '-d': delete = True
        if opt == '-D':
            delete = True
            force = True
        if opt == '--push': push = True
        if opt == '--push-only': push_only = True

    feature_name = parsed_args[1][0]

    if push and not delete:
        rept_utils.printerr("error: '--push' can only be used with delete")
        print_feature_usage()
        sys.exit(1)

    if push_only and not delete:
        rept_utils.printerr("error: '--push-only' can only be used with delete")
        print_feature_usage()
        sys.exit(1)

    if push and push_only:
        rept_utils.printerr("error: '--push' and '--push-only' cannot be used together")
        print_feature_usage()
        sys.exit(1)

    return FeatureArgs(feature_name, delete, force, push, push_only)


def print_feature_usage():
    rept_utils.printerr('usage: rept feature <feature-name>')
    rept_utils.printerr('   or: rept feature (-d | -D) [--push | --push-only] <feature-name>')

def cmd_feature(dependencies, local_config, args):
    feat_args = parse_feature_args(args)

    if feat_args.delete:
        delete_feature(dependencies, local_config, feat_args)
    else:
        create_feature(dependencies, feat_args)

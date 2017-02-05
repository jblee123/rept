################################################################################
# switch cmd funcs
#
# The "switch" command is used to check out all branches of a feature. In the
# main repo, the feature branch is required to exist either locally or remotely.
# (The local branch is used first.) In the dependencies, if a feature branch
# exists locally, that is used first, followed by the remote feature branch. If
# the feature branch exists neither locally or remotely, the dependency commit
# is checked out.
#
# The switch command may also be used to detach any repos that have the
# specified local feature branch checked out. If a repo contains a local feature
# branch and has it checked out, rept will not check out a different commit, but
# will put that repo into a detached head state.
################################################################################

import collections
import os
import sys

from repo_tool import git_utils
from repo_tool import rept_utils

SwitchArgs = collections.namedtuple('SwitchArgs',
    'feature_name create_branches detach')

SwitchPoint = collections.namedtuple('SwitchPoint',
    'dep target_rev no_action_msg')

def get_remote(dep, local_config):
    remote = dep.remote if dep else local_config.remote
    if not remote:
        remote = "origin"
    return remote

def get_dependencies_or_die(local_config, switch_args):
    remote = get_remote(None, local_config)
    remote_branch = remote + '/' + switch_args.feature_name
    target_rev = None

    # The branch exists, so use that commit's deps.
    if git_utils.get_branch_exists(switch_args.feature_name):
        target_rev = switch_args.feature_name
    # The branch doesn't exist locally. How about remotely?
    elif git_utils.get_branch_exists(remote_branch):
        target_rev = remote_branch

    if not target_rev:
        sys.exit('error: could not load .rept_deps file: target feature does '
                 'not exist locally or remotely')

    dep_file_contents = git_utils.get_file_contents_for_revision(
        target_rev, '.rept_deps')
    if not dep_file_contents:
        sys.exit('error: could not retrieve .rept_deps file from repo at '
                 'revision {0}'.format(target_rev))

    dependencies, err = rept_utils.parse_dependency_data(dep_file_contents)
    if err:
        sys.exit('error: could not load .rept_deps file: {0}'.format(err))

    # If the target branch is currently checked out, check to see if the
    # .rept_deps file has been changed. If so, warn the user that the repo
    # version is being used.
    if ((git_utils.get_rev_hash(target_rev) ==
         git_utils.get_rev_hash('HEAD'))):

        ret, out, err = rept_utils.exec_proc(['git', 'status', '--porcelain', '-uno'])
        mods = [mod for mod in out.split(os.linesep) if mod.strip() == 'M .rept_deps']
        if len(mods) > 0:
            rept_utils.printerr(
                'warning: .rept_deps file has been modified ion the current branch. '
                'The repository version is being used.')

    return dependencies

def get_switch_point(dep, local_config, switch_args):

    target_rev = None
    remote_target_rev = None
    no_action_msg = None
    remote = get_remote(dep, local_config)
    remote_branch = remote + '/' + switch_args.feature_name

    # Nothing to do if we're already on the correct branch.
    if git_utils.is_current_branch(switch_args.feature_name):
        no_action_msg = 'already on feature branch'
    # The branch exists and we're not on it, so that's where we need to go.
    elif git_utils.get_branch_exists(switch_args.feature_name):
        target_rev = switch_args.feature_name
    # The branch doesn't exist locally. How about remotely?
    elif git_utils.get_branch_exists(remote_branch):
        if switch_args.create_branches:
            # Just set the target_rev to the not-yet-existing local branch, and
            # git's default behavior will create the local branch to track the
            # remote branch that we know exists.
            target_rev = switch_args.feature_name
            remote_target_rev = remote_branch
        else:
            target_rev = remote_branch
    # The branch doesn't exist. If we're in a dependency, we need to go to its
    # specified revision.
    elif dep:
        if git_utils.get_rev_hash(dep.revision):
            target_rev = dep.revision
        else:
            return (
                None,
                'repo {0} missing both feature branch and dependent revision'.
                    format(dep.name))
    # The branch doesn't exist locally or remotely, and we're not in a
    # dependency, so we must be in the base repo, where we require the feature
    # branch to be present.
    else:
        no_action_msg = 'feature branch not present'

    # If we're creating branches, then target_rev may be a local branch that
    # doesn't exist yet. In this case, the remote branch from which we'll create
    # the new branch is stored in remote_target_rev, so that's the one we'll
    # need to test against in the next step to see if we're really changing
    # commits when we do the checkout.
    existing_target_rev = remote_target_rev or target_rev

    # We know where we need to go. If we're actually changing commits, then the
    # working directory had better be clean so we don't accidentally try to
    # do a checkout that might be destructive.
    if (target_rev and
        (git_utils.get_rev_hash(existing_target_rev) !=
         git_utils.get_rev_hash('HEAD')) and
        not git_utils.is_clean_working_directory(False)):
        return (None, 'working directory is not clean for repo {0}'.format(dep.name))

    switch_point = SwitchPoint(dep, target_rev, no_action_msg)

    return (switch_point, None)

def do_switch(dependencies, local_config, switch_args):
    errs = []

    switch_points = []
    ret = get_switch_point(None, local_config, switch_args)
    switch_points.append(ret[0])
    if ret[1]:
        print_std_err(ret[1])
        sys.exit(1)

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                ret = get_switch_point(dep, local_config, switch_args)
                switch_points.append(ret[0])
                if (ret[1]):
                    errs.append(ret[1])
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

    def do_switch_checkout(rev, dep_path):
        ret = rept_utils.exec_proc(['git', 'checkout', '-q', rev], False)
        if ret:
            repo_part = 'repo: {0}'.format(dep_path) if dep_path else 'this repo'
            errs.append(
                'cannot check out rev {0} for {1}'.format(rev, repo_part))

    for sp in switch_points:
        repo_name = sp.dep.name if sp.dep else 'this repo'
        if sp.target_rev:
            print('checking out {0} on {1}...'.format(sp.target_rev, repo_name))
            if sp.dep:
                repo_path = os.path.abspath(sp.dep.path)
                with rept_utils.DoInExistingDir(repo_path) as ctx:
                    if ctx:
                        do_switch_checkout(sp.target_rev, sp.dep.path)
                    else:
                        errs.append(
                            'cannot enter repo at {0} for checkout'.format(sp.dep.path))
            else:
                do_switch_checkout(sp.target_rev, None)
        else:
            print('skipping checkout in {0}: {1}'.format(repo_name, sp.no_action_msg))

    return errs

def do_detach(dependencies, switch_args):
    def detach_repo(feature_name):
        if git_utils.is_current_branch(switch_args.feature_name):
            rept_utils.exec_proc(['git', 'checkout', '-q', '--detach', 'HEAD'])

    errs = []

    detach_repo(switch_args.feature_name)

    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        with rept_utils.DoInExistingDir(repo_path) as ctx:
            if ctx:
                detach_repo(switch_args.feature_name)
            else:
                errs.append('Missing repo: {0}'.format(dep.path))

    return errs

def print_switch_usage():
    rept_utils.printerr('usage: rept switch [-b] <feature-name>')
    rept_utils.printerr('   or: rept switch -d <feature-name>')

def cmd_switch(local_config, args):
    parsed_args = rept_utils.parse_args(
        args, 'bd', usage_fn=print_switch_usage)

    if len(parsed_args[1]) != 1:
        print_switch_usage()
        sys.exit(1)

    create_branches = False
    detach = False
    for opt, optarg in parsed_args[0]:
        if opt == '-b': create_branches = True
        elif opt == '-d': detach = True

    if create_branches and detach:
        rept_utils.printerr("error: '-b' and '-d' cannot be used together")
        print_switch_usage()
        sys.exit(1)

    feature_name = parsed_args[1][0]

    switch_args = SwitchArgs(feature_name, create_branches, detach)

    dependencies = get_dependencies_or_die(local_config, switch_args)

    if not detach:
        errs = do_switch(dependencies, local_config, switch_args)
    else:
        errs = do_detach(dependencies, switch_args)

    if errs:
        rept_utils.print_std_err_list(errs)
        sys.exit(1)

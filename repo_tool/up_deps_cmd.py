################################################################################
# up-deps cmd funcs
#
# The "up-deps" command is used to udpate all dependencies in dependent repos to
# reflect changes made in the current feature branch. The repos in the
# dependency graph will be inspected in a depth-first manner, and the rules for
# updating each repo's dependencies are as follows:
#
# - If the repo is not clean, error.
# - Else, if the repo has no updated dependencies:
#   - If this is the main repo, there is nothing to do.
#   - Else, if there is no feature branch:
#     - If there are no changes, ignore the repo.
#     - Otherwise error.
#   - Else, if the feature branch isn't current, error.
#   - Else, if there are no changes, ignore the repo.
#   - Else, this repo doesn't need to be updated, but all repos depending on
#     this repo will need to depend on this repo's current revision.
# - Else, if the feature branch doesn't exist or isn't the current branch,
#   error.
# - Else, if [this is the main repo and the commit type was "new"] OR [this repo
#   has not changed], the repo's dependencies will be updated with a new commit.
# - Else, [this is the main repo and the commit type was "amend"] OR [this repo
#   has changed], in which case the repo's dependencies will be updated by
#   amending the commit pointed to by the feature branch.
#
# The --dr option will perform a dry run and only display a report of needed
# udpates, but no actual changes will be made.
################################################################################

import collections
import enum
import os
import sys

from repo_tool import git_utils
from repo_tool import rept_utils

RootCommitType = enum.Enum('RootCommitType', 'NEW AMEND')
RepoAction = enum.Enum('RepoAction', 'ERR NONE UPDATE_NEW UPDATE_AMEND')

UpdateResult = collections.namedtuple('UpdateResult',
    'repo_path action new_rev msg')

def get_result_if_no_changed_deps(feature_name, repo_path, targets):
    feature_branch_exists = git_utils.get_branch_exists(feature_name)
    dep_rev = git_utils.get_rev_hash(targets[os.getcwd()].revision)
    current_rev = git_utils.get_rev_hash('HEAD')

    if not feature_branch_exists:
        if dep_rev == current_rev:
            result = UpdateResult(repo_path, RepoAction.NONE, None,
                'no feature branch; no changes; no dependency changes')
        else:
            result = UpdateResult(repo_path, RepoAction.ERR, None,
                'current HEAD is not on the expected dependecy revision')
    elif not git_utils.is_current_branch(feature_name):
        result = UpdateResult(repo_path, RepoAction.ERR, None,
            'feature branch exists but is not the current branch')
    elif dep_rev == current_rev:
        result = UpdateResult(repo_path, RepoAction.NONE, None,
            'no changes; no dependency changes')
    else:
        result = UpdateResult(repo_path, RepoAction.NONE, current_rev,
            'the feature branch was updated; no dependency changes')

    return result

def check_for_changed_dependencies(dependencies, visited):
    update_actions = [RepoAction.UPDATE_NEW, RepoAction.UPDATE_AMEND]
    for dep in dependencies:
        dep_abs_path = os.path.abspath(dep.path)
        visited_dep = visited.get(dep_abs_path)
        if (visited_dep and
            (visited_dep.new_rev or
             (visited_dep.action in update_actions))):
            return True
    return False

def should_update_with_new(root_commit_type, repo_path, current_rev, targets):
    # If we're in the root repo, the commit type is determined soley by the
    # root commit type parameter.
    if (repo_path == ''):
        return root_commit_type == RootCommitType.NEW

    # Otherwise, we need to do a new commit if the current branch points toward
    # the expected revision.
    else:
        dep_rev = git_utils.get_rev_hash(targets[os.getcwd()].revision)
        return current_rev == dep_rev

def get_result_for_current_node(
    dependencies, feature_name, root_commit_type, repo_path, targets, visited):

    deps_updated = check_for_changed_dependencies(dependencies, visited)

    if not deps_updated:
        if (repo_path != ''):
            result = get_result_if_no_changed_deps(feature_name, repo_path, targets)
        else:
            result = UpdateResult(repo_path, RepoAction.NONE, None,
                'no changed dependencies')

    elif not git_utils.get_branch_exists(feature_name):
        result = UpdateResult(repo_path, RepoAction.ERR, None,
            'updatee required, but feature branch is missing')

    elif not git_utils.is_current_branch(feature_name):
        result = UpdateResult(repo_path, RepoAction.ERR, None,
            'feature branch exists but is not the current branch')

    else:
        current_rev = git_utils.get_rev_hash('HEAD')

        if should_update_with_new(root_commit_type, repo_path, current_rev, targets):
            msg = ('updating root with new commit' if (repo_path == '')
                else 'no feature branch changes; udpated dependencies; '
                     'update with new commit')
            new_rev = None
            action = RepoAction.UPDATE_NEW

        else:
            msg = ('updating root by amending commit' if (repo_path == '')
                else 'feature branch changes; udpated dependencies; '
                     'update by amending')
            new_rev = current_rev
            action = RepoAction.UPDATE_AMEND

        result = UpdateResult(repo_path, action, new_rev, msg)

    return result

def update_deps_for_repo(
    dependencies, feature_name, root_commit_type, repo_path, targets, visited):

    results = []

    # The working directory must be clean.
    if not git_utils.is_clean_working_directory(False):
        results.append(UpdateResult(
            repo_path, RepoAction.ERR, None, 'working directory is not clean'))
        return results

    for dep in dependencies:
        dep_abs_path = os.path.abspath(dep.path)
        if (dep_abs_path not in visited):
            target_dep = targets.get(dep_abs_path)

            dep_results = update_deps_for_dependency_repo(
                feature_name, dep_abs_path, targets, visited)

            results.extend(dep_results)

    result = get_result_for_current_node(
        dependencies, feature_name, root_commit_type, repo_path, targets, visited)

    visited[repo_path] = result
    results.append(result)

    return results

def update_deps_for_dependency_repo(
    feature_name, repo_path, targets, visited):

    with rept_utils.DoInExistingDir(repo_path) as ctx:
        if ctx:
            # This is guaranteed to succeed because we verified it in
            # check_subdeps().
            target_dep = targets.get(repo_path)

            # Look for the contents of a .rept_deps file at the specified
            # revision so see if we need to keep doing consistency checks.
            rept_deps_contents = git_utils.get_file_contents_for_revision(
                target_dep.revision, '.rept_deps')

            dependencies = []
            if rept_deps_contents:
                dependencies, err = rept_utils.parse_dependency_data(
                    rept_deps_contents)

                # If the dependencies couldn't be parsed, we can't continue down
                # this chain, so err out.
                if dependencies == None: # test for None since [] is allowed
                    result = UpdateResult(repo_path, RepoAction.ERR, None, err)
                    return [result]

            # Now we can check all of the sub-dependencies of this dependency.
            return update_deps_for_repo(
                dependencies, feature_name, None, repo_path, targets, visited)

        else:
            result = UpdateResult(
                repo_path, RepoAction.ERR, None, 'The repo is missing')
            return [result]

def action_to_display_str(action):
    if action == RepoAction.ERR:
        return 'Error'
    elif action == RepoAction.NONE:
        return 'No action required'
    elif action == RepoAction.UPDATE_NEW:
        return 'Updating dependencies with a new commit'
    elif action == RepoAction.UPDATE_AMEND:
        return 'Amending commit with new dependencies'
    else:
        assert False

def do_update_deps(dependencies, root_commit_type, feature_name):
    target_deps = {}
    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        target_deps[repo_path] = dep

    results = update_deps_for_repo(
        dependencies, feature_name, root_commit_type, '', target_deps, {})

    first_time = True
    for result in results:
        dep = target_deps[result.repo_path] if result.repo_path else None
        repo_name = dep.name if dep else 'root repo'
        path = dep.path if dep else ''

        new_dep_rev = (result.repo_path and result.new_rev) or '--'

        if not first_time: print()
        print('Result for {0}:'.format(repo_name))
        #print('  path: {0}'.format(path))
        print('  action: {0}'.format(action_to_display_str(result.action)))
        print('  new dependency rev: {0}'.format(new_dep_rev))
        print('  msg: {0}'.format(result.msg))

        first_time = False

    return True

def print_up_deps_usage():
    rept_utils.printerr('usage: rept up-deps -t root_commit_type [-n] <feature-name>')

def cmd_up_deps(dependencies, local_config, args):
    parsed_args = rept_utils.parse_args(
        args, 'nt:', usage_fn=print_up_deps_usage)

    if len(parsed_args[1]) != 1:
        print_up_deps_usage()
        sys.exit(1)

    root_commit_type = None

    dry_run = False
    for opt, optarg in parsed_args[0]:
        if opt == '-t':
            if optarg == 'new':
                root_commit_type = RootCommitType.NEW
            elif optarg == 'amend':
                root_commit_type = RootCommitType.AMEND
            else:
                rept_utils.printerr("error: '-t' argument must be 'new' or 'amend'")
                print_up_deps_usage()
                sys.exit(1)
        elif opt == '-n':
            dry_run = True

    if root_commit_type == None:
        rept_utils.printerr("error: missing required parameter: '-t'")
        print_up_deps_usage()
        sys.exit(1)

    feature_name = parsed_args[1][0]

    if not do_update_deps(dependencies, root_commit_type, feature_name):
        sys.exit(1)

################################################################################
# check-deps cmd funcs
#
# The "check-deps" command inspects the dependencies for consistency. While the
# .rept_deps files lists all dpendencies directly (there are no implicitly
# inherited dependencies), conflicts are still possible. For instance, two
# dependencies may each depend on different versions of a third dependency.
################################################################################

import os
import sys

from repo_tool import git_utils
from repo_tool import rept_utils

# Check each dependency for inconsistencies against the target dependencies.
def check_subdeps(dep_chain, dependencies, targets):
    errs = []
    for dep in dependencies:
        dep_abs_path = os.path.abspath(dep.path)
        target_dep = targets.get(dep_abs_path)

        # Because dependencies are flat, the main repo's .rept_deps file must
        # list *all* needed repos all the way down through the dependency tree.
        # So if this dep repo is NOT in the targets, then it's missing from the
        # main .rept_deps file, which is bad.
        if not target_dep:
            err = "Unlisted dependency '{0}' found".format(repo_name)
            errs.append((err, dep_chain))

        # We're requiring that revision names, not just commits have to match.
        # Technically commits are all that are required for consistency, but
        # that's just asking for trouble if we start mixing representations.
        elif dep.revision != target_dep.revision:
            errs.append(
                (['Inconsistent dependency for {0}:'.format(dep.name),
                  'required: {0}'.format(target_dep.revision),
                  'found: {0}'.format(dep.revision)],
                 dep_chain))

        else:
            dep_hash, hash_err = git_utils.get_rev_hash_from_repo(
                dep.revision, dep_abs_path)
            if not dep_hash:
                err_msg = rept_utils.gen_bad_revision_err_str(
                    dep.name, dep.revision, hash_err)
                errs.append((errs, dep_chain))

            else:
                # If we got here, this dependency's revision is ok. Now gotta
                # check its sub-deps.
                subdep_errs = check_subdeps_for_repo(
                    dep_chain, dep.name, dep_abs_path, targets)
                errs.extend(subdep_errs)

    return errs

# Check the subdependencies for the specified repo against the targets.
def check_subdeps_for_repo(dep_chain, repo_name, repo_abs_path, targets):
    new_dep_chain = dep_chain + [repo_abs_path]

    # If the current repo path is already in the dependency chain, that means
    # we must have a circular dependency, which is bad.
    if repo_abs_path in dep_chain:
        return [('Circular reference detected', new_dep_chain)]

    with rept_utils.DoInExistingDir(repo_abs_path) as ctx:
        if ctx:
            # This is guaranteed to succeed because we verified it in
            # check_subdeps().
            target_dep = targets.get(repo_abs_path)

            # Look for the contents of a .rept_deps file at the specified
            # revision so see if we need to keep doing consistency checks.
            rept_deps_contents = git_utils.get_file_contents_for_revision(
                target_dep.revision, '.rept_deps')

            # No .rept_deps file? No prob. Just means no conflicts.
            # Treat an empty file and no file as the same thing.
            if not rept_deps_contents:
                return []

            dependencies, err = rept_utils.parse_dependency_data(
                rept_deps_contents)

            # If the dependencies couldn't be parsed, we can't continue down
            # this chain, so err out.
            if dependencies == None: # test for None since [] is allowed
                return [(err, new_dep_chain)]

            # Now we can check all of the sub-dependencies of this dependency.
            return check_subdeps(new_dep_chain, dependencies, targets)

        else:
            return [('Missing repo: {0}'.format(repo_name), new_dep_chain)]

def do_check_dep_consistency(dependencies):
    target_deps = {}
    for dep in dependencies:
        repo_path = os.path.abspath(dep.path)
        target_deps[repo_path] = dep

    # Check each dependency for consistency with the targets.
    errs = check_subdeps([os.getcwd()], dependencies, target_deps)

    for err in errs:
        dep_chain = [os.path.basename(dirname) for dirname in err[1]]
        rept_utils.print_std_err(err[0])
        rept_utils.printerr('  Detected in: ' + dep_chain[-1])
        for dep in reversed(dep_chain[:-1]):
            rept_utils.printerr('    included by: ' + dep)

    return not errs

def print_check_dep_usage():
    rept_utils.printerr('usage: rept chk-deps')

def cmd_check_deps(dependencies, args):
    parsed_args = rept_utils.parse_args(
        args, '', usage_fn=print_check_dep_usage)

    if len(parsed_args[1]):
        rept_utils.print_unknown_arg(parsed_args[1][0])
        print_check_dep_usage()
        sys.exit(1)

    if not do_check_dep_consistency(dependencies):
        sys.exit(1)

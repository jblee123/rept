import os
import shutil
import unittest

import test_utils

# Consistent deps.
# app -> dep1:b2, dep2:b1, dep3
# dep1:b2 -> dep2:b1
def make_app_branch2_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch2'),
        test_utils.make_dependency('test_repo_dep2', 'origin/branch1'),
        test_utils.make_dependency('test_repo_dep3', ''),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

def make_dep1_branch2_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep2', 'origin/branch1'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

# Inconsistent deps. Update the app dependencies, but keep dep1 dependencies
# as-is.
# app -> dep1:b2, dep2:b2, dep3
# dep1:b2 -> dep2:b1
def make_app_branch3_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch2'),
        test_utils.make_dependency('test_repo_dep2', 'origin/branch2'),
        test_utils.make_dependency('test_repo_dep3', ''),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

# Unlisted deps. Update the app dependencies, but keep dep1 dependencies
# as-is.
# app -> dep1:b2
# dep1:b2 -> dep2:b1
def make_app_branch4_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch2'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

# Circular reference in deps.
# app -> dep1:b5, dep2:b5
# dep1:b5 -> dep2:b5
# dep2:b5 -> dep1:b5
def make_app_branch5_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch5'),
        test_utils.make_dependency('test_repo_dep2', 'origin/branch5'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

def make_dep1_branch5_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep2', 'origin/branch5'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

def make_dep2_branch5_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch5'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

# Unparsable deps.
# app -> dep1:b6
# dep1:b6 -> bad deps
def make_app_branch6_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch6'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

def make_dep1_branch6_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep2', 'origin/branch5'),
        'This is not valid python',
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

rept_deps_build_data = [
    # branch1
    # No deps are set. The app is given a .rept_deps file, but its dependencies
    # are empty.
    {
        'test_repo_app': test_utils.make_no_deps,
    },
    # branch2
    # Update the app to be dependent on dep1/branch2, dep2/branch1, and dep3.
    # dep1 is also updated to be dependent on dep2/branch1, so we have both the
    # app and dep1 dependent on the same version of dep2.
    {
        'test_repo_app': make_app_branch2_deps,
        'test_repo_dep1': make_dep1_branch2_deps,
    },
    # branch3
    # Update the app to be dependent on dep2/branch2. The dep1 dependencies
    # remain unchanged, so the app still depends on dep1/branch2, which still
    # depends on dep2/branch1. The app and dep1 are now dependent on different
    # versions of dep2, so we have our failure condition to test for.
    {
        'test_repo_app': make_app_branch3_deps,
    },
    # branch4
    # Update the app to be dependent only on dep1/branch2. The dep1 dependencies
    # remain unchanged, so dep1 depends on dep2, but the app does not.
    {
        'test_repo_app': make_app_branch4_deps,
    },
    # branch5
    # Update the app to be dependent on dep1/branch5 and dep2/branch5. Update
    # dep1 to be dependent on dep2/branch5 as well. Then update dep2 to be
    # dependent back on dep1, which will create a circular dependency.
    {
        'test_repo_app': make_app_branch5_deps,
        'test_repo_dep1': make_dep1_branch5_deps,
        'test_repo_dep2': make_dep2_branch5_deps,
    },
    # branch6
    # Update the app to be dependent on dep1/branch6. Update dep1 to have an
    # invalid dependencies file.
    {
        'test_repo_app': make_app_branch6_deps,
        'test_repo_dep1': make_dep1_branch6_deps,
    },
]

app_local_refs_dir = test_utils.get_local_repo_local_refs_dir('test_repo_app')
dep1_local_refs_dir = test_utils.get_local_repo_local_refs_dir('test_repo_dep1')
dep2_local_refs_dir = test_utils.get_local_repo_local_refs_dir('test_repo_dep2')
dep3_local_refs_dir = test_utils.get_local_repo_local_refs_dir('test_repo_dep3')

app_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_app')
dep1_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep1')
dep2_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep2')
dep3_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep3')

repo_info_list = [
    ('test_repo_app', app_local_refs_dir, app_remote_refs_dir),
    ('test_repo_dep1', dep1_local_refs_dir, dep1_remote_refs_dir),
    ('test_repo_dep2', dep2_local_refs_dir, dep2_remote_refs_dir),
    ('test_repo_dep3', dep3_local_refs_dir, dep3_remote_refs_dir),
]

app1_dir = os.path.join(test_utils.locals_home_dir, 'test_repo_app')

class CheckDepsTestCase(unittest.TestCase):
    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos', ignore_errors=True)

        # Create 4 local repos.
        for repo_name, local_refs_dir, remote_refs_dir in repo_info_list:
            local_dir = os.path.join(test_utils.locals_home_dir, repo_name)
            repo_name = os.path.basename(local_dir)
            test_utils.init_repo(local_dir)

            test_utils.add_remote(repo_name)

            os.makedirs(remote_refs_dir)

            branches = ['master']
            for i in range(0, len(rept_deps_build_data)):
                test_utils.commit_common_files(repo_name, i, rept_deps_build_data)

                branch_name = 'branch{0}'.format(i + 1)
                test_utils.exec_proc(['git', 'branch', '-q', branch_name])
                branches.append(branch_name)

                local_branch_file = os.path.join(local_refs_dir, branch_name)
                remote_branch_file = os.path.join(remote_refs_dir, branch_name)
                shutil.copyfile(local_branch_file, remote_branch_file)

            local_branch_file = os.path.join(local_refs_dir, 'master')
            remote_branch_file = os.path.join(remote_refs_dir, 'master')
            shutil.copyfile(local_branch_file, remote_branch_file)

        os.chdir(app1_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def checkout_branch(self, branch_name):
        try:
            out, err, ret = test_utils.exec_proc(['git', 'checkout', branch_name])
            self.assertEqual(ret, 0)
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_1_no_deps(self):
        self.checkout_branch('branch1')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 0)
            self.assertEqual(out, '')
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_2_consistent_deps(self):
        self.checkout_branch('branch2')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 0)
            self.assertEqual(out, '')
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_3_inconsistent_deps(self):
        self.checkout_branch('branch3')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 1)
            self.assertEqual(out, '')
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                "Inconsistent dependency for test_repo_dep2:",
                "  required: origin/branch2",
                "  found: origin/branch1",
                "  Detected in: test_repo_dep1",
                "    included by: test_repo_app",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_4_unlisted_dep(self):
        self.checkout_branch('branch4')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 1)
            self.assertEqual(out, '')
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                "Unlisted dependency 'test_repo_dep2' found",
                "  Detected in: test_repo_dep1",
                "    included by: test_repo_app",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_5_circular_reference(self):
        self.checkout_branch('branch5')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 1)
            self.assertEqual(out, '')
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                "Circular reference detected",
                "  Detected in: test_repo_dep1",
                "    included by: test_repo_dep2",
                "    included by: test_repo_dep1",
                "    included by: test_repo_app",
                "Circular reference detected",
                "  Detected in: test_repo_dep2",
                "    included by: test_repo_dep1",
                "    included by: test_repo_dep2",
                "    included by: test_repo_app",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_check_deps_6_circular_reference(self):
        self.checkout_branch('branch6')

        try:
            out, err, ret = test_utils.exec_proc(['rept', 'check-deps'])
            self.assertEqual(ret, 1)
            self.assertEqual(out, '')
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                    "syntax error at line 14, offset 24: 'This is not valid python'",
                    "  Detected in: test_repo_dep1",
                    "    included by: test_repo_app",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

if __name__ == '__main__':
    unittest.main()

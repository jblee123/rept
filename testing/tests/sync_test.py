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
]

class SyncTestCase(unittest.TestCase):
    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos', ignore_errors=True)

        rept_deps_filename = '.rept_deps'

        base_remote_dir = os.path.join(test_utils.test_repos_home_dir, 'remotes')
        base_local1_dir = os.path.join(test_utils.test_repos_home_dir, 'locals1')
        repo_dirs = [
            'test_repo_app',
            'test_repo_dep1',
            'test_repo_dep2',
            'test_repo_dep3',
        ]

        # Create 4 bare repos to act as remotes.
        remote_dirs = [os.path.join(base_remote_dir, repo_dir) for repo_dir in repo_dirs]
        for remote_dir in remote_dirs:
            os.makedirs(remote_dir)
            os.chdir(remote_dir)
            test_utils.exec_proc(['git', 'init', '-q', '--bare'])
            os.chdir(test_utils.top_testing_dir)

        # Create 4 local repos and push them up to the remotes.
        local1_dirs = [os.path.join(base_local1_dir, repo_dir) for repo_dir in repo_dirs]
        for local1_dir in local1_dirs:
            os.makedirs(local1_dir)
            os.chdir(local1_dir)
            repo_name = os.path.basename(local1_dir)
            prefix = repo_name
            test_utils.exec_proc(['git', 'init', '-q'])

            remote_name = os.path.join(test_utils.remotes_home_dir, repo_name)
            test_utils.exec_proc(['git', 'remote', 'add', 'origin', remote_name])

            branches = ['master']
            for i in range(0, 3):
                files_to_add = [prefix]
                f = open(prefix, 'w')
                f.write('{0} v{1}'.format(prefix, i + 1))
                f.close()

                build_rept_deps = rept_deps_build_data[i].get(repo_name)
                if build_rept_deps:
                    f = open(rept_deps_filename, 'w')
                    rept_file_contents = build_rept_deps()
                    f.write(rept_file_contents)
                    f.close()
                    files_to_add.append(rept_deps_filename)

                test_utils.exec_proc(['git', 'add'] + files_to_add)

                msg = 'v{0}'.format(i + 1)
                test_utils.exec_proc(['git', 'commit', '-q', '-m', msg])
                branch_name = 'branch{0}'.format(i + 1)
                test_utils.exec_proc(['git', 'branch', '-q', branch_name])
                branches.append(branch_name)

            test_utils.exec_proc(['git', 'push', '-q', 'origin'] + branches)

            os.chdir(test_utils.top_testing_dir)

        base_local2_dir = os.path.join(test_utils.test_repos_home_dir, 'locals2')
        os.makedirs(base_local2_dir)
        os.chdir(base_local2_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def test_sync1(self):

        test_repo_app_dir = os.path.join(test_utils.remotes_home_dir, 'test_repo_app')

        app1_dir = os.path.abspath('test_repo_app')
        dep1_dir = os.path.abspath('test_repo_dep1')
        dep2_dir = os.path.abspath('test_repo_dep2')
        dep3_dir = os.path.abspath('test_repo_dep3')

        out, err, ret = test_utils.exec_proc(['git', 'clone', test_repo_app_dir])
        self.assertEqual(ret, 0)

        def reset_for_next_test():
            os.chdir(app1_dir)
            shutil.rmtree(dep1_dir, ignore_errors=True)
            shutil.rmtree(dep2_dir, ignore_errors=True)
            shutil.rmtree(dep3_dir, ignore_errors=True)

        with self.subTest('sync no deps test'):
            try:
                out, err = '', ''
                os.chdir(app1_dir)
                out, err, ret= test_utils.exec_proc(['git', 'checkout', 'branch1'])
                self.assertEqual(ret, 0)

                out, err, ret = test_utils.exec_proc(['rept', 'sync'])
                self.assertEqual(ret, 0)
                self.assertEqual(out, 'Success')

                self.assertFalse(os.path.exists(dep1_dir))
                self.assertFalse(os.path.exists(dep2_dir))
                self.assertFalse(os.path.exists(dep3_dir))
            except:
                test_utils.print_out_err(out, err)
                raise

        reset_for_next_test()

        # Make sure that, when we have consistent dependencies, we can:
        # 1) clone deps
        # 2) fetch deps if the repos already exist
        # 3) can fail when a repo directory:
        #    a) is non-empty, which disallows a clone, and
        #    b) has no .git directory, which disallows a fetch
        # These tests all build on each other, hence nesting them under the same
        # sub-test.
        with self.subTest('sync consistent deps test (cloning)'):
            try:
                out, err = '', ''
                os.chdir(app1_dir)
                out, err, ret= test_utils.exec_proc(['git', 'checkout', 'branch2'])
                self.assertEqual(ret, 0)

                out, err, ret = test_utils.exec_proc(['rept', 'sync'])
                # print('out: \n' + out)
                # print('err: \n' + err)
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'cloning repo test_repo_dep1...',
                    'cloning repo test_repo_dep2...',
                    'cloning repo test_repo_dep3...',
                    'checking out origin/branch2 on test_repo_dep1...',
                    'checking out origin/branch1 on test_repo_dep2...',
                    'checking out origin/master on test_repo_dep3...',
                    '',
                    'Success',
                    ])

                self.assertTrue(os.path.exists(dep1_dir))
                self.assertTrue(os.path.exists(dep2_dir))
                self.assertTrue(os.path.exists(dep3_dir))
            except:
                test_utils.print_out_err(out, err)
                raise

            with self.subTest('sync consistent deps test (fetching)'):
                try:
                    out, err = '', ''
                    out, err, ret = test_utils.exec_proc(['rept', 'sync'])
                    # print('out: \n' + out)
                    # print('err: \n' + err)
                    self.assertEqual(ret, 0)
                    self.assertEqual(
                        test_utils.convert_to_lines(out),
                        [
                        'fetching repo test_repo_dep1...',
                        'fetching repo test_repo_dep2...',
                        'fetching repo test_repo_dep3...',
                        'checking out origin/branch2 on test_repo_dep1...',
                        'checking out origin/branch1 on test_repo_dep2...',
                        'checking out origin/master on test_repo_dep3...',
                        '',
                        'Success',
                        ])
                except:
                    test_utils.print_out_err(out, err)
                    raise

            with self.subTest('sync consistent deps test (no dep1 .git folder)'):
                try:
                    out, err = '', ''
                    shutil.rmtree(os.path.join(dep1_dir, '.git'))
                    out, err, ret = test_utils.exec_proc(['rept', 'sync'])
                    # print('out: \n' + out)
                    # print('err: \n' + err)
                    self.assertEqual(ret, 1)
                    self.assertEqual(
                        test_utils.convert_to_lines(out),
                        [
                        'fetching repo test_repo_dep2...',
                        'fetching repo test_repo_dep3...',
                        ])
                    self.assertEqual(
                        test_utils.convert_to_lines(err),
                        [
                        '1 errors:',
                        '- cannot sync test_repo_dep1: ../test_repo_dep1 is '
                            'not empty and is not a git repo',
                        ])
                except:
                    test_utils.print_out_err(out, err)
                    raise

        reset_for_next_test()

        # Make sure we fail checking out on inconsistent dependencies.
        with self.subTest('sync inconsistent deps test'):
            try:
                out, err = '', ''
                os.chdir(app1_dir)
                out, err, ret= test_utils.exec_proc(['git', 'checkout', 'branch3'])
                self.assertEqual(ret, 0)

                out, err, ret = test_utils.exec_proc(['rept', 'sync'])
                # print('out: \n' + out)
                # print('err: \n' + err)
                self.assertEqual(ret, 1)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'cloning repo test_repo_dep1...',
                    'cloning repo test_repo_dep2...',
                    'cloning repo test_repo_dep3...',
                    ])
                self.assertEqual(
                    test_utils.convert_to_lines(err),
                    [
                    "Cloning into '.'...",
                    "done.",
                    "Cloning into '.'...",
                    "done.",
                    "Cloning into '.'...",
                    "done.",
                    "Inconsistent dependency for test_repo_dep2:",
                    "  required: origin/branch2",
                    "  found: origin/branch1",
                    "  Detected in: test_repo_dep1",
                    "    included by: test_repo_app",
                    "error: inconsistent dependencies. cannot proceed with checkout",
                    ])

                self.assertTrue(os.path.exists(dep1_dir))
                self.assertTrue(os.path.exists(dep2_dir))
                self.assertTrue(os.path.exists(dep3_dir))
            except:
                test_utils.print_out_err(out, err)
                raise

if __name__ == '__main__':
    unittest.main()

import os
import shutil
import sys
import unittest

sys.path.append('../..');
from repo_tool import git_utils

import test_utils

# app -> dep1:b1, dep2:b1, dep3
# dep1:b2 -> dep2:b1
def make_app_branch1_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch1'),
        test_utils.make_dependency('test_repo_dep2', 'origin/branch1'),
        test_utils.make_dependency('test_repo_dep3', ''),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

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

rept_deps_build_data = [
    # branch1
    # app is dependent on b1 of dep1 and dep2, and the latest branch of dep3.
    {
        'test_repo_app': make_app_branch1_deps,
    },
    # branch2
    # Update the app to be dependent on dep1/branch2, dep2/branch1, and dep3.
    # dep1 is also updated to be dependent on dep2/branch1, so we have both the
    # app and dep1 dependent on the same version of dep2.
    {
        'test_repo_app': make_app_branch2_deps,
        'test_repo_dep1': make_dep1_branch2_deps,
    },
]

class FeatureTestCase(unittest.TestCase):
    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos', ignore_errors=True)

        base_local_dir = os.path.join(test_utils.test_repos_home_dir, 'locals')
        repo_names = [
            'test_repo_app',
            'test_repo_dep1',
            'test_repo_dep2',
            'test_repo_dep3',
        ]

        # Create 4 bare repos to act as remotes.
        test_utils.init_remotes(repo_names)

        # Create 4 local repos and push them up to the remotes.
        for repo_name in repo_names:
            local_dir = os.path.join(base_local_dir, repo_name)
            test_utils.init_repo(local_dir)

            test_utils.add_remote(repo_name)

            branches = ['master']
            for i in range(0, len(rept_deps_build_data)):
                test_utils.commit_common_files(repo_name, i, rept_deps_build_data)

                branch_name = 'branch{0}'.format(i + 1)
                test_utils.exec_proc(['git', 'branch', '-q', branch_name])
                branches.append(branch_name)

            test_utils.push_branches_to_origin(branches)

            os.chdir(test_utils.top_testing_dir)

        os.chdir(test_utils.locals_home_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def test_feature_1_success(self):

        app1_dir = os.path.abspath('test_repo_app')

        try:
            out, err = '', ''
            os.chdir(app1_dir)

            out, err, ret = test_utils.exec_proc(['rept', 'feat', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'created 4/4 branches',
                ])

            def compare_commits(repo_dir, repo1_branch, repo2_branch):
                hash1, err1 = git_utils.get_rev_hash_from_repo(
                    repo1_branch, repo_dir)
                hash2, err2 = git_utils.get_rev_hash_from_repo(
                    repo2_branch, repo_dir)
                self.assertFalse(err1)
                self.assertFalse(err2)
                self.assertEqual(hash1, hash2)

            compare_commits('.', 'master', 'feat1')
            compare_commits('../test_repo_dep1', 'branch2', 'feat1')
            compare_commits('../test_repo_dep2', 'branch1', 'feat1')
            compare_commits('../test_repo_dep3', 'master', 'feat1')

        except:
            test_utils.print_out_err(out, err)
            raise

    def test_feature_2_fail_on_existing(self):

        app1_dir = os.path.abspath('test_repo_app')
        dep1_local_refs_dir = test_utils.get_local_repo_local_refs_dir('test_repo_dep1')
        dep1_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep1')

        def make_fake_branch(refs_dir, branch_name):
            os.chdir(refs_dir)
            shutil.copyfile('master', branch_name)
        make_fake_branch(dep1_local_refs_dir, 'feat1')
        make_fake_branch(dep1_remote_refs_dir, 'feat2')

        os.chdir(app1_dir)

        with self.subTest('feature existing local branch'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(['rept', 'feat', 'feat1'])
                self.assertEqual(ret, 1)
                self.assertEqual(out, '')
                self.assertEqual(
                    test_utils.convert_to_lines(err),
                    [
                    '1 errors:',
                    'dependency test_repo_dep1 already contains a local branch: feat1',
                    ])

            except:
                test_utils.print_out_err(out, err)
                raise

        with self.subTest('feature existing remote branch'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(['rept', 'feat', 'feat2'])
                self.assertEqual(ret, 1)
                self.assertEqual(out, '')
                self.assertEqual(
                    test_utils.convert_to_lines(err),
                    [
                    '1 errors:',
                    'dependency test_repo_dep1 already contains a remote branch: origin/feat2',
                    ])

            except:
                test_utils.print_out_err(out, err)
                raise

    def test_feature_3_delete(self):

        repo_names = [
            'test_repo_app',
            'test_repo_dep1',
            'test_repo_dep2',
            'test_repo_dep3',
        ]

        try:
            for repo_name in repo_names:
                os.chdir(repo_name)
                out, err, ret = test_utils.exec_proc(
                    ['git', 'checkout', '-b', 'test1', 'branch1'])
                self.assertEqual(ret, 0)
                os.chdir('..')
        except:
            test_utils.print_out_err(out, err)
            raise

        app1_dir = os.path.abspath('test_repo_app')

        os.chdir(app1_dir)

        with self.subTest('fail delete unmerged'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(['rept', 'feat', '-d', 'branch2'])
                self.assertEqual(ret, 1)
                self.assertEqual(out, '')
                self.assertEqual(
                    test_utils.convert_to_lines(err),
                    [
                    'error: cannot delete unmerged branches (use -D to force) in repos:',
                    '  - this repo',
                    '  - test_repo_dep1',
                    '  - test_repo_dep2',
                    '  - test_repo_dep3',
                    ])

            except:
                test_utils.print_out_err(out, err)
                raise

        with self.subTest('succeed delete unmerged'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-D', 'branch2'])
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'deleting local branch in this repo',
                    'deleting local branch in test_repo_dep1',
                    'deleting local branch in test_repo_dep2',
                    'deleting local branch in test_repo_dep3',
                    'deleted 4/4 local branches',
                    ])
                self.assertEqual(err, '')


                os.chdir(test_utils.locals_home_dir)
                for repo_name in repo_names:
                    os.chdir(repo_name)
                    self.assertFalse(git_utils.get_branch_exists('branch2'))
                    os.chdir('..')
                os.chdir(app1_dir)

            except:
                test_utils.print_out_err(out, err)
                raise

        with self.subTest('fail delete checked out'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-d', 'test1'])
                self.assertEqual(ret, 1)
                self.assertEqual(out, '')
                self.assertEqual(
                    test_utils.convert_to_lines(err),
                    [
                    'error: cannot delete branches checked out in repos:',
                    '  - this repo',
                    '  - test_repo_dep1',
                    '  - test_repo_dep2',
                    '  - test_repo_dep3',
                    ])

            except:
                test_utils.print_out_err(out, err)
                raise

        with self.subTest('succeed delete non-existent'):
            try:
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-d', 'nonexistent'])
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'deleted 0/0 local branches',
                    ])
                self.assertEqual(err, '')

            except:
                test_utils.print_out_err(out, err)
                raise

        try:
            os.chdir(test_utils.locals_home_dir)
            out, err = '', ''
            for repo_name in repo_names:
                os.chdir(repo_name)
                out, err, ret = test_utils.exec_proc(
                    ['git', 'checkout', 'master'])
                self.assertEqual(ret, 0)
                os.chdir('..')
            os.chdir(app1_dir)
        except:
            test_utils.print_out_err(out, err)
            raise

        with self.subTest('succeed delete local only'):
            try:
                os.chdir(app1_dir)
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-d', 'branch1'])
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'deleting local branch in this repo',
                    'deleting local branch in test_repo_dep1',
                    'deleting local branch in test_repo_dep2',
                    'deleting local branch in test_repo_dep3',
                    'deleted 4/4 local branches',
                    ])
                self.assertEqual(err, '')

                os.chdir(test_utils.locals_home_dir)
                for repo_name in repo_names:
                    os.chdir(repo_name)
                    self.assertFalse(git_utils.get_branch_exists('branch1'))
                    self.assertTrue(git_utils.get_branch_exists('origin/branch1'))
                    os.chdir('..')
                os.chdir(app1_dir)

            except:
                test_utils.print_out_err(out, err)
                raise

        # recreate 'branch2' to ensure that only the remote is being deleted
        try:
            out, err = '', ''
            os.chdir(test_utils.locals_home_dir)
            for repo_name in repo_names:
                os.chdir(repo_name)
                out, err, ret = test_utils.exec_proc(
                    ['git', 'branch', 'branch2', 'origin/branch2'])
                self.assertEqual(ret, 0)
                os.chdir('..')
        except:
            test_utils.print_out_err(out, err)
            raise

        with self.subTest('succeed delete remote only'):
            try:
                os.chdir(app1_dir)
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-d', '--push-only', 'branch2'])
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'deleting remote branch in this repo',
                    'deleting remote branch in test_repo_dep1',
                    'deleting remote branch in test_repo_dep2',
                    'deleting remote branch in test_repo_dep3',
                    'deleted 4/4 remote branches',
                    ])
                self.assertEqual(err, '')

                os.chdir(test_utils.locals_home_dir)
                out, err = '', ''
                for repo_name in repo_names:
                    os.chdir(repo_name)
                    self.assertTrue(git_utils.get_branch_exists('branch2'))
                    self.assertFalse(git_utils.get_branch_exists('origin/branch2'))
                    os.chdir('..')
                os.chdir(app1_dir)

            except:
                test_utils.print_out_err(out, err)
                raise

        # recreate 'branch1' so we can delete both local and remote
        try:
            out, err = '', ''
            os.chdir(test_utils.locals_home_dir)
            for repo_name in repo_names:
                os.chdir(repo_name)
                out, err, ret = test_utils.exec_proc(
                    ['git', 'branch', 'branch1', 'origin/branch1'])
                self.assertEqual(ret, 0)
                os.chdir('..')
        except:
            test_utils.print_out_err(out, err)
            raise

        with self.subTest('succeed delete local and remote only'):
            try:
                os.chdir(app1_dir)
                out, err = '', ''
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'feat', '-d', '--push', 'branch1'])
                self.assertEqual(ret, 0)
                self.assertEqual(
                    test_utils.convert_to_lines(out),
                    [
                    'deleting local branch in this repo',
                    'deleting local branch in test_repo_dep1',
                    'deleting local branch in test_repo_dep2',
                    'deleting local branch in test_repo_dep3',
                    'deleting remote branch in this repo',
                    'deleting remote branch in test_repo_dep1',
                    'deleting remote branch in test_repo_dep2',
                    'deleting remote branch in test_repo_dep3',
                    'deleted 4/4 local branches',
                    'deleted 4/4 remote branches',
                    ])
                self.assertEqual(err, '')

                os.chdir(test_utils.locals_home_dir)
                out, err = '', ''
                for repo_name in repo_names:
                    os.chdir(repo_name)
                    self.assertFalse(git_utils.get_branch_exists('branch1'))
                    self.assertFalse(git_utils.get_branch_exists('origin/branch1'))
                    os.chdir('..')
                os.chdir(app1_dir)

            except:
                test_utils.print_out_err(out, err)
                raise

if __name__ == '__main__':
    unittest.main()

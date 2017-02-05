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

    def is_detached_at(self, rev):
        out, err, ret = test_utils.exec_proc(['git', 'branch'])
        if ret:
            return False

        branches = [branch.strip() for branch in out.split(os.linesep)]
        branch = [branch[2:] for branch in branches if branch.startswith('* ')]
        is_detached = branch[0].startswith('(HEAD detached at ') if branch else False
        if not is_detached:
            return False

        head_hash = git_utils.get_rev_hash('HEAD')
        rev_hash = git_utils.get_rev_hash(rev)

        return head_hash == rev_hash

    def test_switch_1_all_branches_exist_success(self):
        app1_dir = os.path.abspath('test_repo_app')
        dep1_dir = os.path.abspath('test_repo_dep1')
        dep2_dir = os.path.abspath('test_repo_dep2')
        dep3_dir = os.path.abspath('test_repo_dep3')
        all_dirs = [app1_dir, dep1_dir, dep2_dir, dep3_dir]

        for repo_dir in all_dirs:
            os.chdir(repo_dir)
            test_utils.exec_proc(['git', 'checkout', 'branch1'])
            test_utils.exec_proc(['git', 'branch', 'feat1', 'branch2'])

        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'checking out feat1 on this repo...',
                'checking out feat1 on test_repo_dep1...',
                'checking out feat1 on test_repo_dep2...',
                'checking out feat1 on test_repo_dep3...',
                ])

            for repo_dir in all_dirs:
                os.chdir(repo_dir)
                self.assertTrue(git_utils.is_current_branch('feat1'))

        except:
            test_utils.print_out_err(out, err)
            raise

    def test_switch_2_sparse_branches(self):
        app1_dir = os.path.abspath('test_repo_app')
        dep1_dir = os.path.abspath('test_repo_dep1')
        dep2_dir = os.path.abspath('test_repo_dep2')
        dep3_dir = os.path.abspath('test_repo_dep3')
        all_dirs = [app1_dir, dep1_dir, dep2_dir, dep3_dir]

        for repo_dir in all_dirs:
            os.chdir(repo_dir)
            test_utils.exec_proc(['git', 'checkout', 'branch1'])

        os.chdir(app1_dir)
        test_utils.exec_proc(['git', 'branch', 'feat1', 'branch2'])

        os.chdir(dep2_dir)
        test_utils.exec_proc(['git', 'branch', 'feat1', 'branch2'])

        # test successfully checking out with all depos starting off-feature
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'checking out feat1 on this repo...',
                'checking out origin/branch2 on test_repo_dep1...',
                'checking out feat1 on test_repo_dep2...',
                'checking out origin/master on test_repo_dep3...',
                ])

            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep1_dir)
            self.is_detached_at('origin/branch2')

            os.chdir(dep2_dir)
            self.is_detached_at('feat1')

            os.chdir(dep3_dir)
            self.is_detached_at('origin/master')

        except:
            test_utils.print_out_err(out, err)
            raise

        os.chdir(dep1_dir)
        test_utils.exec_proc(['git', 'checkout', 'branch1'])

        # test successfully checking out with some depos starting on-feature and
        # some starting off-feature
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'skipping checkout in this repo: already on feature branch',
                'checking out origin/branch2 on test_repo_dep1...',
                'skipping checkout in test_repo_dep2: already on feature branch',
                'checking out origin/master on test_repo_dep3...',
                ])

            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep1_dir)
            self.assertTrue(self.is_detached_at('origin/branch2'))

            os.chdir(dep2_dir)
            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep3_dir)
            self.assertTrue(self.is_detached_at('origin/master'))

        except:
            test_utils.print_out_err(out, err)
            raise

        for repo_dir in all_dirs:
            os.chdir(repo_dir)
            test_utils.exec_proc(['git', 'checkout', 'branch1'])

        dep1_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep1')
        os.chdir(dep1_remote_refs_dir)
        shutil.copyfile('branch2', 'feat1')

        # test successfully checking out with all depos starting off-feature
        # and using the -b option
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', '-b', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'checking out feat1 on this repo...',
                'checking out feat1 on test_repo_dep1...',
                'checking out feat1 on test_repo_dep2...',
                'checking out origin/master on test_repo_dep3...',
                ])

            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep1_dir)
            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep2_dir)
            self.assertTrue(git_utils.is_current_branch('feat1'))

            os.chdir(dep3_dir)
            self.assertTrue(self.is_detached_at('origin/master'))

        except:
            test_utils.print_out_err(out, err)
            raise

        # detach from feat1
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', '-d', 'feat1'])
            self.assertEqual(ret, 0)
            self.assertEqual(out, '')

            self.assertTrue(self.is_detached_at('feat1'))

            os.chdir(dep1_dir)
            self.assertTrue(self.is_detached_at('feat1'))

            os.chdir(dep2_dir)
            self.assertTrue(self.is_detached_at('feat1'))

            os.chdir(dep3_dir)
            self.assertTrue(self.is_detached_at('origin/master'))

        except:
            test_utils.print_out_err(out, err)
            raise

        for repo_dir in all_dirs:
            os.chdir(repo_dir)
            test_utils.exec_proc(['git', 'checkout', 'branch1'])

        os.chdir(dep1_dir)
        with open('test_repo_dep1', 'r+') as f:
            f.seek(0, 2)
            f.write('\nsome more text')

        # test failing on dirty workspace
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', 'feat1'])
            self.assertEqual(ret, 1)
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                '1 errors:',
                'working directory is not clean for repo test_repo_dep1',
                ])

            for repo_dir in all_dirs:
                os.chdir(repo_dir)
                self.assertTrue(git_utils.is_current_branch('branch1'))

        except:
            test_utils.print_out_err(out, err)
            raise

        os.chdir(dep1_dir)
        test_utils.exec_proc(['git', 'checkout', 'test_repo_dep1'])
        test_utils.exec_proc(['git', 'branch', '-D', 'feat1'])
        test_utils.exec_proc(['git', 'branch', '-rD', 'origin/feat1'])
        test_utils.exec_proc(['git', 'branch', '-rD', 'origin/branch2'])

        # test failing on no branch or remote branch or dependency found
        try:
            os.chdir(app1_dir)
            out, err, ret = test_utils.exec_proc(['rept', 'switch', 'feat1'])
            self.assertEqual(ret, 1)
            self.assertEqual(
                test_utils.convert_to_lines(err),
                [
                '1 errors:',
                'repo test_repo_dep1 missing both feature branch and dependent revision',
                ])

            for repo_dir in all_dirs:
                os.chdir(repo_dir)
                self.assertTrue(git_utils.is_current_branch('branch1'))

        except:
            test_utils.print_out_err(out, err)
            raise

if __name__ == '__main__':
    unittest.main()

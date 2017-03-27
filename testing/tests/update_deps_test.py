import os
import shutil
import sys
import unittest

sys.path.append('../..');
from repo_tool import git_utils

import test_utils

# app -> dep1:b1, dep2:b1, dep3:b1
# dep2:b1 -> dep3:b1
def make_app_branch1_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', 'origin/branch1'),
        test_utils.make_dependency('test_repo_dep2', 'origin/branch1'),
        test_utils.make_dependency('test_repo_dep3', 'origin/branch1'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

def make_dep2_branch1_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep3', 'origin/branch1'),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

rept_deps_build_data = [
    # branch1
    # app is dependent on b1 of dep1 and dep2, and the latest branch of dep3.
    {
        'test_repo_app': make_app_branch1_deps,
        'test_repo_dep2': make_dep2_branch1_deps,
    },
]

repo_result_template = \
'''Result for {0}:
  action: {1}
  new dependency rev: {2}
  msg: {3}
'''

def build_result_string(results):
    str_list = [
        repo_result_template.format(result[0], result[1], result[2], result[3])
        for result in results]
    return os.linesep.join(str_list)

class UpdateDepsTestCase(unittest.TestCase):
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
        app1_dir = os.path.abspath('test_repo_app')

        os.chdir(app1_dir)
        test_utils.exec_proc(['rept', 'feat', 'feat1'])
        test_utils.exec_proc(['rept', 'switch', '-b', 'feat1'])

        os.chdir(test_utils.locals_home_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def udpate_branch(self, repo_name, branch_name, version):
        test_utils.exec_proc(['git', 'checkout', branch_name])

        f = open(repo_name, 'w')
        f.write('{0} v{1}'.format(repo_name, version))
        f.close()

        test_utils.exec_proc(['git', 'add', repo_name])

        msg = 'v{0}'.format(version)
        test_utils.exec_proc(['git', 'commit', '-q', '-m', msg])

    def test_up_deps_01_dry_run_no_changes_success(self):

        app1_dir = os.path.abspath('test_repo_app')
        os.chdir(app1_dir)

        out, err, ret = test_utils.exec_proc(
            ['rept', 'up-deps', '-t', 'new', '-n', 'feat1'])
        self.assertEqual(ret, 0)

        target_str = build_result_string([
            [
                'test_repo_dep1',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep3',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep2',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'root repo',
                'No action required',
                '--',
                'no changed dependencies',
            ],
        ]).strip()
        self.assertEqual(out, target_str)

    def test_up_deps_02_dry_run_changes_1_success(self):

        app1_dir = os.path.abspath('test_repo_app')
        dep3_dir = os.path.abspath('test_repo_dep3')

        os.chdir(dep3_dir)
        self.udpate_branch('test_repo_dep3', 'feat1', 2)
        dep3_feat1_rev = git_utils.get_rev_hash('feat1')

        os.chdir(app1_dir)

        base_target_str_params = [
            [
                'test_repo_dep1',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep3',
                'No action required',
                dep3_feat1_rev,
                'the feature branch was updated; no dependency changes',
            ],
            [
                'test_repo_dep2',
                'Updating dependencies with a new commit',
                '--',
                'no feature branch changes; udpated dependencies; update with new commit',
            ],
        ]

        for commit_type in ['new', 'amend']:
            with self.subTest(commit_type=commit_type):
                out, err, ret = test_utils.exec_proc(
                    ['rept', 'up-deps', '-t', commit_type, '-n', 'feat1'])
                self.assertEqual(ret, 0)

                if commit_type == 'new':
                    target_str_params = base_target_str_params + [
                        [
                            'root repo',
                            'Updating dependencies with a new commit',
                            '--',
                            'updating root with new commit',
                        ]
                    ]
                else:
                    target_str_params = base_target_str_params + [
                        [
                            'root repo',
                            'Amending commit with new dependencies',
                            '--',
                            'updating root by amending commit',
                        ]
                    ]

                target_str = build_result_string(target_str_params).strip()
                self.assertEqual(out, target_str)

    def test_up_deps_03_dry_run_changes_2_success(self):

        app1_dir = os.path.abspath('test_repo_app')
        dep2_dir = os.path.abspath('test_repo_dep2')
        dep3_dir = os.path.abspath('test_repo_dep3')

        os.chdir(dep2_dir)
        self.udpate_branch('test_repo_dep2', 'feat1', 2)
        dep2_feat1_rev = git_utils.get_rev_hash('feat1')

        os.chdir(dep3_dir)
        self.udpate_branch('test_repo_dep3', 'feat1', 2)
        dep3_feat1_rev = git_utils.get_rev_hash('feat1')

        os.chdir(app1_dir)

        out, err, ret = test_utils.exec_proc(
            ['rept', 'up-deps', '-t', 'new', '-n', 'feat1'])
        self.assertEqual(ret, 0)

        target_str = build_result_string([
            [
                'test_repo_dep1',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep3',
                'No action required',
                dep3_feat1_rev,
                'the feature branch was updated; no dependency changes',
            ],
            [
                'test_repo_dep2',
                'Amending commit with new dependencies',
                dep2_feat1_rev,
                'feature branch changes; udpated dependencies; update by amending',
            ],
            [
                'root repo',
                'Updating dependencies with a new commit',
                '--',
                'updating root with new commit',
            ],
        ]).strip()
        self.assertEqual(out, target_str)

    def test_up_deps_04_dry_run_changes_3_success(self):

        app1_dir = os.path.abspath('test_repo_app')
        dep2_dir = os.path.abspath('test_repo_dep2')

        os.chdir(dep2_dir)
        self.udpate_branch('test_repo_dep2', 'feat1', 2)
        dep2_feat1_rev = git_utils.get_rev_hash('feat1')

        os.chdir(app1_dir)

        out, err, ret = test_utils.exec_proc(
            ['rept', 'up-deps', '-t', 'new', '-n', 'feat1'])
        self.assertEqual(ret, 0)

        target_str = build_result_string([
            [
                'test_repo_dep1',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep3',
                'No action required',
                '--',
                'no changes; no dependency changes',
            ],
            [
                'test_repo_dep2',
                'No action required',
                dep2_feat1_rev,
                'the feature branch was updated; no dependency changes',
            ],
            [
                'root repo',
                'Updating dependencies with a new commit',
                '--',
                'updating root with new commit',
            ],
        ]).strip()
        self.assertEqual(out, target_str)

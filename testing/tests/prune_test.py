import os
import shutil
import unittest

import test_utils

def make_app_deps():
    deps = [
        test_utils.make_dependency('test_repo_dep1', ''),
        test_utils.make_dependency('test_repo_dep2', ''),
        test_utils.make_dependency('test_repo_dep3', ''),
    ]
    deps = ''.join(deps)
    return test_utils.deps_template.format(deps)

rept_deps_build_data = [
    {
        'test_repo_app': make_app_deps,
    },
]

dep1_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep1')
dep2_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep2')
dep3_remote_refs_dir = test_utils.get_local_repo_remote_refs_dir('test_repo_dep3')

class PruneTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos', ignore_errors=True)

        rept_deps_filename = '.rept_deps'

        base_remote_dir = os.path.join(test_utils.test_repos_home_dir, 'remotes')
        base_local_dir = os.path.join(test_utils.test_repos_home_dir, 'locals')
        repo_dirs = [
            'test_repo_app',
            'test_repo_dep1',
            'test_repo_dep2',
            'test_repo_dep3',
        ]

        # Create 4 bare repos to act as remotes.
        remote_dirs = [os.path.join(base_remote_dir, repo_dir) for repo_dir in repo_dirs]
        test_utils.make_bare_repos(remote_dirs)

        # Create 4 local repos and push them up to the remotes.
        local_dirs = [os.path.join(base_local_dir, repo_dir) for repo_dir in repo_dirs]
        for local_dir in local_dirs:
            os.makedirs(local_dir)
            os.chdir(local_dir)
            repo_name = os.path.basename(local_dir)
            prefix = repo_name
            test_utils.exec_proc(['git', 'init', '-q'])

            remote_name = os.path.join(test_utils.remotes_home_dir, repo_name)
            test_utils.exec_proc(['git', 'remote', 'add', 'origin', remote_name])

            branches = ['master']
            for i in range(0, 1):
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

            test_utils.exec_proc(['git', 'push', '-q', 'origin'] + branches)

            os.chdir(test_utils.top_testing_dir)

        # Manually alter the repos to add a remote branches that don't exist in
        # the actual remote repos so there's something to prune.
        def make_fake_remote_branch(refs_dir):
            os.chdir(refs_dir)
            shutil.copyfile('master', 'branch_to_prune')
        make_fake_remote_branch(dep1_remote_refs_dir)
        make_fake_remote_branch(dep2_remote_refs_dir)
        make_fake_remote_branch(dep3_remote_refs_dir)

        os.chdir(base_local_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def check_branches(self, refs_dir, branches):
        os.chdir(refs_dir)
        refs = sorted(os.listdir())
        self.assertEqual(refs, branches)

    def check_pre_prune_branches(self, refs_dir):
        self.check_branches(refs_dir, ['branch_to_prune', 'master'])

    def check_post_prune_branches(self, refs_dir):
        self.check_branches(refs_dir, ['master'])

    def test_prune_1_success(self):
        app1_dir = os.path.abspath('test_repo_app')

        # Make sure the branches to prune exists.
        self.check_pre_prune_branches(dep1_remote_refs_dir)
        self.check_pre_prune_branches(dep2_remote_refs_dir)
        self.check_pre_prune_branches(dep3_remote_refs_dir)

        try:
            out, err = '', ''
            os.chdir(app1_dir)

            out, err, ret = test_utils.exec_proc(['rept', 'prune'])

            # Make sure the branch to prune has been deleted.
            self.check_post_prune_branches(dep1_remote_refs_dir)
            self.check_post_prune_branches(dep2_remote_refs_dir)
            self.check_post_prune_branches(dep3_remote_refs_dir)

            self.assertEqual(ret, 0)

            outlines = test_utils.convert_to_lines(out)
            self.assertEqual(len(outlines), 13)
            self.assertEqual(outlines[0],  'pruning origin for this repo...')
            self.assertEqual(outlines[1],  'pruning test_repo_dep1...')
            self.assertEqual(outlines[2],  'Pruning origin')
            self.assertRegex(outlines[3],  '^URL: .*/testing/test_repos/remotes/test_repo_dep1$')
            self.assertEqual(outlines[4],  ' * [pruned] origin/branch_to_prune')
            self.assertEqual(outlines[5],  'pruning test_repo_dep2...')
            self.assertEqual(outlines[6],  'Pruning origin')
            self.assertRegex(outlines[7],  '^URL: .*/testing/test_repos/remotes/test_repo_dep2$')
            self.assertEqual(outlines[8],  ' * [pruned] origin/branch_to_prune')
            self.assertEqual(outlines[9],  'pruning test_repo_dep3...')
            self.assertEqual(outlines[10], 'Pruning origin')
            self.assertRegex(outlines[11], '^URL: .*/testing/test_repos/remotes/test_repo_dep3$')
            self.assertEqual(outlines[12], ' * [pruned] origin/branch_to_prune')
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_prune_2_missing_origin_and_deps(self):
        app1_dir = os.path.abspath('test_repo_app')
        dep1_dir = os.path.abspath('test_repo_dep1')
        dep2_dir = os.path.abspath('test_repo_dep2')

        # Sabatage the remote so the prune will fail.
        base_remote_dir = os.path.join(test_utils.test_repos_home_dir, 'remotes')
        remote_app_dir = os.path.join(base_remote_dir, 'test_repo_app')
        os.rename(remote_app_dir, remote_app_dir + '2')

        # Sabatage dep1 by killing the whole repo.
        shutil.rmtree(dep1_dir)

        # Sabatage dep2 by killing the .git directory so it's not a repo.
        shutil.rmtree(os.path.join(dep2_dir, '.git'))

        # Make sure the branches to prune exists.
        self.check_pre_prune_branches(dep3_remote_refs_dir)

        try:
            out, err = '', ''
            os.chdir(app1_dir)

            out, err, ret = test_utils.exec_proc(['rept', 'prune'])

            # Make sure the branch to prune has been deleted.
            self.check_post_prune_branches(dep3_remote_refs_dir)

            self.assertEqual(ret, 1)

            outlines = test_utils.convert_to_lines(out)
            self.assertEqual(len(outlines), 7)
            self.assertEqual(outlines[0], 'pruning origin for this repo...')
            self.assertEqual(outlines[1], 'pruning test_repo_dep1...')
            self.assertEqual(outlines[2], 'pruning test_repo_dep2...')
            self.assertEqual(outlines[3], 'pruning test_repo_dep3...')
            self.assertEqual(outlines[4], 'Pruning origin')
            self.assertRegex(outlines[5], '^URL: .*/testing/test_repos/remotes/test_repo_dep3$')
            self.assertEqual(outlines[6], ' * [pruned] origin/branch_to_prune')

            self.assertEqual(
                test_utils.convert_to_lines(err)[-5:],
                [
                "",
                "3 errors:",
                "error: cannot prune 'origin' for this repo",
                "Missing repo: ../test_repo_dep1",
                "error: cannot prune repo 'test_repo_dep2'",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

if __name__ == '__main__':
    unittest.main()

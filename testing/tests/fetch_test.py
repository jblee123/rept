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

class FetchTestCase(unittest.TestCase):

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
        for remote_dir in remote_dirs:
            os.makedirs(remote_dir)
            os.chdir(remote_dir)
            test_utils.exec_proc(['git', 'init', '-q', '--bare'])
            os.chdir(test_utils.top_testing_dir)

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

        os.chdir(base_local_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def test_fetch_1_success(self):
        try:
            out, err = '', ''
            app1_dir = os.path.abspath('test_repo_app')
            os.chdir(app1_dir)

            out, err, ret = test_utils.exec_proc(['rept', 'fetch'])
            self.assertEqual(ret, 0)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'fetching origin for this repo...',
                'fetching test_repo_dep1...',
                'fetching test_repo_dep2...',
                'fetching test_repo_dep3...',
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

    def test_fetch_2_missing_origin_and_deps(self):
        app1_dir = os.path.abspath('test_repo_app')
        dep1_dir = os.path.abspath('test_repo_dep1')
        dep2_dir = os.path.abspath('test_repo_dep2')

        # Sabatage the remote so the fetch will fail.
        base_remote_dir = os.path.join(test_utils.test_repos_home_dir, 'remotes')
        remote_app_dir = os.path.join(base_remote_dir, 'test_repo_app')
        os.rename(remote_app_dir, remote_app_dir + '2')

        # Sabatage dep1 by killing the whole repo.
        shutil.rmtree(dep1_dir)

        # Sabatage dep2 by killing the .git directory so it's not a repo.
        shutil.rmtree(os.path.join(dep2_dir, '.git'))

        try:
            out, err = '', ''
            os.chdir(app1_dir)

            out, err, ret = test_utils.exec_proc(['rept', 'fetch'])
            self.assertEqual(ret, 1)
            self.assertEqual(
                test_utils.convert_to_lines(out),
                [
                'fetching origin for this repo...',
                'fetching test_repo_dep1...',
                'fetching test_repo_dep2...',
                'fetching test_repo_dep3...',
                ])
            self.assertEqual(
                test_utils.convert_to_lines(err)[-3:],
                [
                "error: cannot fetch 'origin' for this repo",
                "Missing repo: ../test_repo_dep1",
                "error: cannot fetch repo 'test_repo_dep2'",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

if __name__ == '__main__':
    unittest.main()

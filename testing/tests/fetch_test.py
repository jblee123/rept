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
    {
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

class FetchTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos', ignore_errors=True)

        rept_deps_filename = '.rept_deps'

        # Create 4 bare repos to act as remotes.
        remote_dirs = [os.path.join(test_utils.remotes_home_dir, repo_info[0])
            for repo_info in repo_info_list]
        test_utils.make_bare_repos(remote_dirs)

        self.commits = {}

        # Create 4 local repos and push them up to the remotes.
        for repo_name, local_refs_dir, remote_refs_dir in repo_info_list:
            local_dir = os.path.join(test_utils.locals_home_dir, repo_name)
            os.makedirs(local_dir)
            os.chdir(local_dir)
            prefix = repo_name
            test_utils.exec_proc(['git', 'init', '-q'])

            remote_name = os.path.join(test_utils.remotes_home_dir, repo_name)
            test_utils.exec_proc(['git', 'remote', 'add', 'origin', remote_name])

            self.commits[repo_name] = []

            branches = ['master']
            for i in range(0, 2):
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

                d = os.getcwd()
                os.chdir(local_refs_dir)
                ref_file = open('master')
                self.commits[repo_name].append(ref_file.read())
                ref_file.close()
                os.chdir(d)

            test_utils.exec_proc(['git', 'push', '-q', 'origin'] + branches)

            os.chdir(local_refs_dir)
            ref_file = open('master', 'w')
            ref_file.write(self.commits[repo_name][0])
            ref_file.close()

            os.chdir(remote_refs_dir)
            ref_file = open('master', 'w')
            ref_file.write(self.commits[repo_name][0])
            ref_file.close()

            os.chdir(local_dir)
            out, err, ret = test_utils.exec_proc(
                ['git', 'reset', '--hard', 'HEAD'])
            if ret:
                print(out)
                print(err)

            os.chdir(test_utils.top_testing_dir)

        os.chdir(test_utils.locals_home_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree('test_repos')

    def test_fetch_1_success(self):
        app1_dir = os.path.abspath('test_repo_app')

        try:
            out, err = '', ''
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

            # Make sure the branches are where they're supposed to be.
            for repo_name, local_refs_dir, remote_refs_dir in repo_info_list:
                os.chdir(local_refs_dir)
                ref_file = open('master')
                commit = ref_file.read()
                ref_file.close()
                self.assertEqual(commit, self.commits[repo_name][0])

                os.chdir(remote_refs_dir)
                ref_file = open('master')
                commit = ref_file.read()
                ref_file.close()
                self.assertEqual(commit, self.commits[repo_name][1])

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
                test_utils.convert_to_lines(err)[-5:],
                [
                "",
                "3 errors:",
                "error: cannot fetch 'origin' for this repo",
                "Missing repo: ../test_repo_dep1",
                "error: cannot fetch repo 'test_repo_dep2'",
                ])
        except:
            test_utils.print_out_err(out, err)
            raise

if __name__ == '__main__':
    unittest.main()

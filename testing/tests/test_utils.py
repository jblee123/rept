import os
import subprocess
import sys

################################################################################
# Folder utils
################################################################################

rept_deps_filename = '.rept_deps'

top_testing_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

test_repos_home_dir = os.path.abspath(os.path.join(top_testing_dir, 'test_repos'))
remotes_home_dir = os.path.join(test_repos_home_dir, 'remotes')
locals_home_dir = os.path.join(test_repos_home_dir, 'locals')

def get_local_repo_local_refs_dir(repo):
    return os.path.join(
        test_repos_home_dir, 'locals', repo, '.git', 'refs', 'heads')

def get_local_repo_remote_refs_dir(repo):
    return os.path.join(
        test_repos_home_dir, 'locals', repo, '.git', 'refs', 'remotes', 'origin')

################################################################################
# Dependency utils
################################################################################

deps_template = """
{{{{
    "defaults": {{{{
        "remote": "origin",
        "remote_server": "{0}{1}",
        "revision": "origin/master"
    }}}},
    "dependencies": [
{{0}}
    ]
}}}}
""".format(remotes_home_dir, os.path.sep)

dependency_template = """
        {{
            "name": "{0}",
            "path": "../{0}",
{1}
        }},
"""

def make_dependency(repo_name, rev):
    if rev:
        rev = '            "revision": "{0}"'.format(rev)

    return dependency_template.format(repo_name, rev)

# No deps
def make_no_deps():
    return deps_template.format('')

################################################################################
# Misc utils
################################################################################

def exec_proc(cmd):
    sys.stdout.flush()
    sys.stderr.flush()
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out, err = p.communicate()
    out = str(out,'utf-8').strip()
    err = str(err,'utf-8').strip()
    return out, err, p.returncode

def convert_to_lines(s):
    return [line for line in s.split(os.linesep)]

def print_out_err(out, err):
    print()
    if out:
        print('out:')
        print(out)
    else:
        print('-- NOTHING SENT TO STDOUT --')

    print()
    if err:
        print('err:')
        print(err)
    else:
        print('-- NOTHING SENT TO STDERR --')

def init_repo(dirname):
    os.makedirs(dirname)
    os.chdir(dirname)
    exec_proc(['git', 'init', '-q'])

def make_bare_repo(remote_dir):
    orig_dir = os.getcwd()
    os.makedirs(remote_dir)
    os.chdir(remote_dir)
    exec_proc(['git', 'init', '-q', '--bare'])
    os.chdir(orig_dir)

def init_remotes(repo_names):
    base_remote_dir = os.path.join(test_repos_home_dir, 'remotes')
    for repo_name in repo_names:
        remote_dir = os.path.join(base_remote_dir, repo_name)
        make_bare_repo(remote_dir)

def add_remote(repo_name):
    remote_name = os.path.join(remotes_home_dir, repo_name)
    exec_proc(['git', 'remote', 'add', 'origin', remote_name])

def push_branches_to_origin(branches):
    exec_proc(['git', 'push', '-q', 'origin'] + branches)

def maybe_write_rept_deps(build_rept_deps_fn, added_files):
    if build_rept_deps_fn:
        f = open(rept_deps_filename, 'w')
        rept_file_contents = build_rept_deps_fn()
        f.write(rept_file_contents)
        f.close()
        added_files.append(rept_deps_filename)

def commit_common_files(repo_name, commit_set_num, rept_deps_build_data):
    files_to_add = [repo_name]
    f = open(repo_name, 'w')
    f.write('{0} v{1}'.format(repo_name, commit_set_num + 1))
    f.close()

    build_rept_deps_fn = rept_deps_build_data[commit_set_num].get(repo_name)
    maybe_write_rept_deps(build_rept_deps_fn, files_to_add)

    exec_proc(['git', 'add'] + files_to_add)

    msg = 'v{0}'.format(commit_set_num + 1)
    exec_proc(['git', 'commit', '-q', '-m', msg])

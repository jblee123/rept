import os
import subprocess
import sys

################################################################################
# Folder utils
################################################################################

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
    if out:
        print()
        print('out:')
        print(out)

    if err:
        print()
        print('err:')
        print(err)

import ast
import collections
import getopt
import os
import subprocess
import sys

Dependency = collections.namedtuple('Dependency',
    'name path remote remote_server revision')
LocalConfig = collections.namedtuple('LocalConfig',
    'remote')

class DoInExistingDir(object):
    def __init__(self, dir):
        self.old_dir = os.getcwd()
        self.new_dir = dir

    def __enter__(self):
        try:
            os.chdir(self.new_dir)
            return self
        except:
            return None

    def __exit__(self, type, value, traceback):
        os.chdir(self.old_dir)
        return isinstance(value, OSError)

################################################################################
# General util funcs
################################################################################

def printerr(s):
    print(s, file=sys.stderr)

def print_unknown_arg(param):
    printerr('error: unknown argument \'{0}\''.format(param))

def print_std_err(err):
    if (type(err) == str):
        printerr(err)
    else:
        printerr(err[0])
        for msg in err[1:]:
            printerr('  ' + msg)

def print_std_err_list(errs):
    for err in errs:
        print_std_err(err)

def parse_args(args, short_opts, long_opts=[], usage_fn=None):
    try:
        return getopt.getopt(args, short_opts, long_opts)
    except getopt.GetoptError as e:
        printerr('error: ' + e.msg)
        if usage_fn:
            usage_fn()
        sys.exit(1)

def gen_bad_revision_err_str(dep_name, dep_revision, rev_hash_err):
    return ['Bad revision specified: {0}'.format(dep_revision),
            'for repo: {0}'.format(dep_name),
            rev_hash_err]

def exec_proc(cmd):
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out, err = p.communicate()
    out = str(out,'utf-8').strip()
    err = str(err,'utf-8').strip()
    return p.returncode, out, err

################################################################################
# dependency and config funcs
################################################################################

def move_to_repo_dir_or_die():
    while True:
        if os.path.isdir('.git'):
            break
        else:
            cur_dir = os.getcwd()
            parent_dir = os.path.dirname(cur_dir)
            if cur_dir == parent_dir:
                sys.exit('error: no git repo found')
            os.chdir(parent_dir)

def open_rept_dep_file():
    try:
        return open('.rept_deps')
    except:
        return None

def open_rept_local_file():
    try:
        return open('.rept_local')
    except:
        return None

def parse_local_data(rept_local_str):
    err = None
    contents = None

    try:
        # Use literal_eval() for safety since we're eval'ing untrusted code.
        contents = ast.literal_eval(rept_local_str)
    except SyntaxError as e:
        err = 'syntax error at line {0}, offset {1}'.format(e.lineno, e.offset)
        return (None, err)
    except ValueError:
        err = 'illegal value used. (Do you have a function call in the file?)'
        return (None, err)
    except:
        err = 'unknown parse error'
        return (None, err)

    if type(contents) != dict:
        err = 'must contain a single dictionary'
        return (None, err)

    remote = contents.get('remote', None)
    if remote != None and type(remote) != str:
        err = '"remote" must be a string'
        return (None, err)

    local_config = LocalConfig(remote)

    return (local_config, err)

def get_local_config_from_file(rept_local_file):
    contents = None

    if rept_local_file:
        try:
            contents = rept_local_file.read()
        except:
            return (None, 'could not read the .rept_local file')

        return parse_local_data(contents)
    else:
        local_config = LocalConfig(None)
        return (local_config, None)

def parse_dependency_data(rept_deps_str):
    err = None
    contents = None

    try:
        # Use literal_eval() for safety since we're eval'ing untrusted code.
        contents = ast.literal_eval(rept_deps_str)
    except SyntaxError as e:
        err = 'syntax error at line {0}, offset {1}'.format(e.lineno, e.offset)
        return (None, err)
    except ValueError:
        err = 'illegal value used. (Do you have a function call in the file?)'
        return (None, err)
    except:
        return (None, str(sys.exc_info()[1]))

    if type(contents) != dict:
        err = 'must contain a single dictionary'
        return (None, err)

    def_remote = ''
    def_remote_server = ''
    def_revision = ''

    defaults = contents.get('defaults')
    if defaults:
        def_remote = defaults.get('remote', def_remote);
        def_remote_server = defaults.get('remote_server', def_remote_server)
        def_revision = defaults.get('revision', def_revision)

    if 'dependencies' not in contents.keys():
        err = '"dependencies" list not found'
        return (None, err)

    dep_list = contents['dependencies']
    if (type(dep_list) != list):
        err = '"dependencies" is not a list'
        return (None, err)

    dependencies = []

    idx = 0
    for dep in dep_list:
        if (type(dep) != dict):
            err = 'dependency {0} is not a dictionary'.format(idx)
            return (None, err)

        name = dep.get('name')
        path = dep.get('path')

        if not name:
            err = 'dependency {0} requires a name'.format(idx)
            return (None, err)

        if not path:
            err = 'dependency {0} requires a path'.format(idx)
            return (None, err)

        remote = dep.get('remote', def_remote)
        remote_server = dep.get('remote_server', def_remote_server)
        revision = dep.get('revision', def_revision)

        if not remote:
            err = 'dependency {0} requires a remote'.format(idx)
            return (None, err)

        if not remote_server:
            err = 'dependency {0} requires a remote server'.format(idx)
            return (None, err)

        if not revision:
            err = 'dependency {0} requires a revision'.format(idx)
            return (None, err)

        dependencies.append(
            Dependency(name, path, remote, remote_server, revision))

        idx += 1

    return (dependencies, err)

def get_dependency_data_from_file(rept_deps_file):
    contents = None

    try:
        contents = rept_deps_file.read()
    except:
        return (None, 'could not read the .rept_deps file')

    return parse_dependency_data(contents)

def get_dependency_data_or_die(rept_deps_file):
    dependencies, err = get_dependency_data_from_file(rept_deps_file)
    if err:
        sys.exit('error: could not load .rept_deps file: ' + err)
    return dependencies

def get_local_config_or_die(rept_local_file, remotes):
    local_config, err = get_local_config_from_file(rept_local_file)
    if not local_config:
        sys.exit('error: could not load .rept_local file: ' + err)

    if not remotes:
        sys.exit('error: no remotes detected in this repo')

    remote = local_config.remote
    if remote and (remote not in remotes):
        sys.exit('error: specified remote is not in this repo')

    if not remote:
        if len(remotes) == 1:
            remote = remotes[0]
        else:
            sys.exit('error: multiple remotes detected. specify in .rept_local file')

    local_config = LocalConfig(remote)

    return local_config

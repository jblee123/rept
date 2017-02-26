import ast
import itertools
import parser
import re
import token

BADLY_FORMATTED_LINE_ERR_TXT = 'badly formatted line for automatic update'

def detect_line_ending(contents_lines):
    cr_cnt = 0
    for line in contents_lines:
        if len(line) > 1 and line[-2] == '\r':
            cr_cnt += 1
    over_half_cr = cr_cnt > (len(contents_lines) / 2)
    return '\r\n' if over_half_cr else '\n'

def replace_rev_value(contents_lines, tokens, target_ast_str, new_rev):

    token_to_replace = [tok for tok in tokens if
        tok[0] == token.STRING and
        tok[2] == target_ast_str.lineno and
        tok[3] == target_ast_str.col_offset][0]

    # make sure the string value we're replacing is in a single token
    if eval(token_to_replace[1]) != target_ast_str.s:
        return (None, BADLY_FORMATTED_LINE_ERR_TXT)

    new_token = re.sub(target_ast_str.s, new_rev, token_to_replace[1])

    the_line = contents_lines[target_ast_str.lineno - 1]

    start_idx = target_ast_str.col_offset
    end_idx = start_idx + len(token_to_replace[1])

    first_part = ''.join(contents_lines[:target_ast_str.lineno - 1])
    target_line = ''.join([the_line[:start_idx], new_token, the_line[end_idx:]])
    end_part = ''.join(contents_lines[target_ast_str.lineno:])
    new_contents = ''.join([first_part, target_line, end_part])

    return (new_contents, None)

def add_rev_value(contents_lines, tokens, last_ast_key, last_ast_val, new_rev):
    rbrace_idx = 0
    for tok in tokens:
        if (tokens[rbrace_idx][0] == token.STRING and
            tokens[rbrace_idx][2] == last_ast_val.lineno and
            tokens[rbrace_idx][3] == last_ast_val.col_offset):
            break;
        rbrace_idx += 1

    while tokens[rbrace_idx][0] != token.RBRACE:
        rbrace_idx += 1

    rbrace_token = tokens[rbrace_idx]
    prev_token = tokens[rbrace_idx - 1]

    add_comma = tokens[rbrace_idx - 1][0] != token.COMMA
    on_same_line = rbrace_token[2] == prev_token[2]

    prev_tok_line_idx = prev_token[2] - 1
    first_part = ''.join(contents_lines[:prev_tok_line_idx])

    through_prev_tok_idx = prev_token[3] + len(prev_token[1])
    prev_tok_line = contents_lines[prev_tok_line_idx]
    second_part = prev_tok_line[:through_prev_tok_idx]
    if add_comma:
        second_part += ','

    text_to_insert = '"revision": "{0}",'.format(new_rev)

    if on_same_line:
        maybe_space = '' if prev_tok_line[through_prev_tok_idx].isspace() else ' '
        second_part = ''.join([
            second_part, ' ', text_to_insert, maybe_space,
            prev_tok_line[through_prev_tok_idx:]])
    else:
        second_part = ''.join([
            second_part, prev_tok_line[through_prev_tok_idx:],
            ' ' * last_ast_key.col_offset, text_to_insert,
            detect_line_ending(contents_lines)])

    third_part = ''.join(contents_lines[prev_token[2]:])

    new_contents = ''.join([first_part, second_part, third_part])

    return (new_contents, None)

def get_index_of_string_key(ast_dict, target_key):
    key_idx = 0
    for key in ast_dict.keys:
        if type(key) == ast.Str and key.s == target_key:
            return key_idx
        key_idx += 1
    return -1

def do_get_tokens(st):
    if type(st[1]) == str:
        return [st]

    sublists = map(do_get_tokens, st[1:])
    return itertools.chain.from_iterable(sublists)

def get_tokens(contents_whole):
    st = parser.expr(contents_whole)
    return list(do_get_tokens(st.totuple(True, True)))

def update_dep_rev(rept_deps_filename, dep_name, new_rev):
    try:
        rept_deps_file = open(rept_deps_filename, 'r')
        contents_lines = rept_deps_file.readlines()
    except:
        return 'could not read the .rept_deps file'
    finally:
        rept_deps_file.close()

    contents_whole = ''.join(contents_lines)
    deps_ast = ast.parse(contents_whole, '<deps_file>', 'eval')

    if type(deps_ast.body) != ast.Dict:
        return 'expression was not a dictionary'

    tokens = get_tokens(contents_whole)

    dependencies_idx = get_index_of_string_key(deps_ast.body, 'dependencies')

    if dependencies_idx == -1:
        return 'could not find dependencies list'

    target_dep_dict = None
    deps_list = deps_ast.body.values[dependencies_idx].elts
    for dep_dict in deps_list:
        name_idx = get_index_of_string_key(dep_dict, 'name')
        if (name_idx > -1 and
            type(dep_dict.values[name_idx]) == ast.Str and
            dep_dict.values[name_idx].s == dep_name):
            target_dep_dict = dep_dict

    if not target_dep_dict:
        return 'could not find target dependency'

    rev_idx = get_index_of_string_key(target_dep_dict, 'revision')

    add_info = None
    if rev_idx > -1:
        target_ast_str = target_dep_dict.values[rev_idx]
        if type(target_ast_str) != ast.Str:
            return 'target revision was not a string'
        (new_contents, err) = replace_rev_value(
            contents_lines, tokens, target_ast_str, new_rev)
    else:
        last_key_idx = len(target_dep_dict.keys) - 1
        last_key = target_dep_dict.keys[last_key_idx]
        last_val = target_dep_dict.values[last_key_idx]
        if type(last_val) != ast.Str or type(last_val) != ast.Str:
            return BADLY_FORMATTED_LINE_ERR_TXT
        (new_contents, err) = add_rev_value(
            contents_lines, tokens, last_key, last_val, new_rev)

    if err:
        return err

    try:
        rept_deps_file = open(rept_deps_filename, 'w')
        rept_deps_file.write(new_contents)
    except:
        return 'could not write the .rept_deps file'
    finally:
        rept_deps_file.close()

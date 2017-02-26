import os
import re
import shutil
import sys
import unittest

sys.path.append('../..');
sys.path.append('../../repo_tool');
from repo_tool import deps_manip

import test_utils

deps_testing_dir = 'deps_testing'

sample_deps_1 = \
'''
# This is the rept deps file.

{
    "defaults": {
        "remote": "origin",
        "remote_server": "git@github.com:",
        "revision": "origin/master"
    },
    "dependencies": [
        {
            "name": "repo1_name",
            "path": "repo1_dir",
            "revision": "1234567890abcdef1234567890abcdef11111111"
        },
        {
            "name": "repo2_name",
            "path": "repo2_dir",
            "revision": "1234567890abcdef1234567890abcdef22222222"
        },
        {
            "name": "repo3_name",
            "path": "repo3_dir"#REPO3_TEST_MARKER1
#REPO3_TEST_MARKER2
        },
        {
            "name": "repo4_name",
            "path": "repo4_dir"},#REPO4_TEST_MARKER1
        {
            "name": "repo5_name",
            "path": "repo5_dir",
            "revision": "1234567890abcdef123"  "4567890abcdef55555555"
        },
    ]
}
'''

BADLY_FORMATTED_LINE_ERR_TXT = 'badly formatted line for automatic update'

class DepsTestCase(unittest.TestCase):
    def setUp(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree(deps_testing_dir, ignore_errors=True)
        os.mkdir(deps_testing_dir)

    def tearDown(self):
        os.chdir(test_utils.top_testing_dir)
        shutil.rmtree(deps_testing_dir)

    def test_1_replace_existing(self):

        os.chdir(os.path.join(test_utils.top_testing_dir, deps_testing_dir))
        test_filename = 'test_deps'

        string_enclosures = [
            ["'", "'"],
            ['"', '"'],
            ["'''", "'''"],
            ['"""', '"""'],
            ["r'", "'"],
            ['r"', '"'],
            ["r'''", "'''"],
            ['r"""', '"""'],
        ]

        old_rev = '1234567890abcdef1234567890abcdef22222222'
        new_rev = old_rev[::-1] # reverse the string
        rev_text_base = '"' + old_rev + '"'
        for enc in string_enclosures:
            with self.subTest(enc=enc):
                rev_text_pre = enc[0] + old_rev + enc[1]
                rev_text_post = enc[0] + new_rev + enc[1]

                deps_text_pre = re.sub(
                    rev_text_base, rev_text_pre, sample_deps_1)
                deps_text_post = re.sub(
                    rev_text_base, rev_text_post, sample_deps_1)

                try:
                    f = open(test_filename, 'w')
                    f.write(deps_text_pre)
                finally:
                    f.close()

                result = deps_manip.update_dep_rev(
                    test_filename, 'repo2_name', new_rev)

                self.assertIsNone(result)

                try:
                    f = open(test_filename, 'r')
                    new_contents = f.read()
                finally:
                    f.close()

                self.assertEqual(new_contents, deps_text_post)

    def test_2_add_new(self):
        os.chdir(os.path.join(test_utils.top_testing_dir, deps_testing_dir))

        test_filename = 'test_deps'

        new_rev = '1234567890abcdef1234567890abcdef33333333';
        new_rev_base_text = '"revision": "{0}",'.format(new_rev)

        def do_test(repo_name, pre_data, post_data):
            try:
                f = open(test_filename, 'w')
                f.write(pre_data)
            finally:
                f.close()

            result = deps_manip.update_dep_rev(
                test_filename, repo_name, new_rev)

            self.assertIsNone(result)

            try:
                f = open(test_filename, 'r')
                new_contents = f.read()
            finally:
                f.close()

            self.assertEqual(new_contents, post_data)

        line_endings = [
            ['', ',' ],
            [',', None ],
            ['   ,   ', None ],
            ['   ,   # some random comment', None ]
        ]
        new_rev_newline_text = '            {0}\n'.format(new_rev_base_text)

        for line_ending in line_endings:
            with self.subTest(line_ending=line_ending):

                pre_data_line_ending = line_ending[0]
                post_data_line_ending = (
                    line_ending[1] if (line_ending[1] != None) else line_ending[0])

                pre_data = re.sub(
                    '#REPO3_TEST_MARKER1', pre_data_line_ending, sample_deps_1)
                pre_data = re.sub(
                    '#REPO3_TEST_MARKER2\n', '', pre_data)

                post_data = re.sub(
                    '#REPO3_TEST_MARKER1', post_data_line_ending, sample_deps_1)
                post_data = re.sub(
                    '#REPO3_TEST_MARKER2\n', new_rev_newline_text, post_data)

                do_test('repo3_name', pre_data, post_data)

        same_line_repls = [
            ['},', ', {0} }},'.format(new_rev_base_text)],
            [',},', ', {0} }},'.format(new_rev_base_text)],
            ['   ,   },', '   , {0}   }},'.format(new_rev_base_text)],
        ]

        for repl in same_line_repls:
            with self.subTest(repl=same_line_repls):

                pre_data = re.sub(
                    '},#REPO4_TEST_MARKER1', repl[0], sample_deps_1)

                post_data = re.sub(
                    '},#REPO4_TEST_MARKER1', repl[1], sample_deps_1)

                do_test('repo4_name', pre_data, post_data)

    def test_3_bad_format(self):

        os.chdir(os.path.join(test_utils.top_testing_dir, deps_testing_dir))
        test_filename = 'test_deps'

        try:
            f = open(test_filename, 'w')
            f.write(sample_deps_1)
        finally:
            f.close()

        result = deps_manip.update_dep_rev(
            test_filename, 'repo5_name', '12345')

        self.assertEqual(result, BADLY_FORMATTED_LINE_ERR_TXT)

        try:
            f = open(test_filename, 'r')
            new_contents = f.read()
        finally:
            f.close()

        # File should be unchanged.
        self.assertEqual(new_contents, sample_deps_1)

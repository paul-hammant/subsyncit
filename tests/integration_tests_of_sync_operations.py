# Subsyncit - File sync backed by Subversion
#
#   Copyright (c) 2016 - 2017, Paul Hammant
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 3.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

#
#  TODO - if not a subversion site, should abort.
#

import argparse
import copy
import json
import os
import re
import shutil
import sys
import time
import unittest

import docker
import glob2
import requests
import sh
from decorator import decorator
from docker.errors import NotFound
from os.path import dirname
from tinydb import TinyDB


class IntegrationTestsOfSyncOperations(unittest.TestCase):

    test_num = 0
    test_name = ""
    test_sync_dir_one = ""
    test_sync_dir_two = ""
    process_one = None
    process_two = None
    container = None
    kill_container_at_end = False

    def __init__(self, testname, size, kill_container_at_end):
        super(IntegrationTestsOfSyncOperations, self).__init__(testname)
        self.size = size
        IntegrationTestsOfSyncOperations.kill_container_at_end = kill_container_at_end
        self.output = ""
        self.user = "davsvn"
        self.passwd = "davsvn"
        self.svn_repo = "http://127.0.0.1:8099/svn/testrepo/"
        self.line = ""

    @decorator
    def timedtest(f, *args, **kwargs):

        IntegrationTestsOfSyncOperations.test_name = getattr(f, "__name__", "<unnamed>")
        t1 = time.time()
        out = f(*args, **kwargs)
        t2 = time.time()
        dt = str((t2 - t1) * 1.00)
        dtout = dt[:(dt.find(".") + 4)]
        print('\nTest {0} finished in {1}s'.format(IntegrationTestsOfSyncOperations.test_name, dtout))
        print("==================================================================================================================================")


    @classmethod
    def setUpClass(cls):
        sh.rm("-rf", str(sh.pwd()).strip('\n') + os.sep + "/integrationTests/")

        cls.client = docker.from_env()

        print("Kill Docker container (if necessary) from last test suite invocation...")
        cls.kill_docker_container(True)
        cls.kill_docker_container(True)
        print("... done")

        print("Start Docker container for this test suite invocation...")
        cls.client.containers.run("subsyncit/alpine-svn-dav:latest", name="subsyncitTests", detach=True, ports={'80/tcp': 8099}, auto_remove=True)
        content = ""
        while "It works!" not in content:
            try:
                get = requests.get("http://127.0.0.1:8099")
                content = get.content.decode("utf-8")
            except requests.exceptions.ConnectionError:
                pass

        requests.request('MKCOL', "http://127.0.0.1:8099/svn/testrepo/integrationTests", auth=("davsvn", "davsvn"), verify=False)
        print("... done")

    @classmethod
    def tearDownClass(cls):
        if cls.kill_container_at_end:
            cls.kill_docker_container(False)


    def setUp(self):

        self.maxDiff = None

        from io import StringIO
        self.process_output_one = StringIO()
        self.process_output_two = StringIO()

        if os.name != 'nt':
            self.home_dir = os.path.expanduser('~' + (os.getenv("SUDO_USER") or os.getenv("USER")))
        else:
            self.home_dir = os.path.expanduser(str(os.getenv('USERPROFILE')))

        IntegrationTestsOfSyncOperations.test_num += 1
        testNum = str(IntegrationTestsOfSyncOperations.test_num)

        self.rel_dir_one = "integrationTests/test_" + testNum + "/one/"
        pwd = str(sh.pwd()).strip('\n')
        self.test_sync_dir_one = pwd + os.sep + self.rel_dir_one
        self.rel_dir_two = "integrationTests/test_" + testNum + "/two/"
        self.test_sync_dir_two = pwd + os.sep + self.rel_dir_two

        self.db_dir_one = self.home_dir + os.sep + ".subsyncit" + os.sep + self.test_sync_dir_one[:-1].replace("/", "%47").replace(":", "%58").replace("\\", "%92")
        self.db_dir_two = self.home_dir + os.sep + ".subsyncit" + os.sep + self.test_sync_dir_two[:-1].replace("/", "%47").replace(":", "%58").replace("\\", "%92")

        self.reset_test_dir(self.test_sync_dir_one)
        self.reset_test_dir(self.db_dir_one)
        self.reset_test_dir(self.test_sync_dir_two)
        self.reset_test_dir(self.db_dir_two)

        self.svn_url = self.svn_repo + "integrationTests/test_" + testNum + "/"
        self.expect201(requests.request('MKCOL', self.svn_url, auth=(self.user, self.passwd), verify=False))


    def tearDown(self):

        self.end(self.process_one, self.test_sync_dir_one)
        self.end(self.process_two, self.test_sync_dir_two)

        def list2reason(exc_list):
            if exc_list and exc_list[-1][0] is self:
                return exc_list[-1][1]

        # Listener to status from https://stackoverflow.com/questions/4414234/getting-pythons-unittest-results-in-a-teardown-method
        result = self.defaultTestResult()
        self._feedErrorsToResult(result, self._outcome.errors)
        errs = str(list2reason(result.errors))
        failed = "File \"subsyncit.py\", line" in errs or "AssertionError:" in str(list2reason(result.failures))
        a = self.process_output_one.getvalue()
        if failed and len(a) > 0:
            print(">>>>> A OUTPUT and ERR >>>>>")
            print(a)
        b = self.process_output_two.getvalue()
        if failed and len(b) > 0:
            print(">>>>> B OUTPUT and ERR >>>>>")
            print(b)

        with open(dirname(self.test_sync_dir_one[:-1]) + os.sep + ".testname", "w", encoding="utf-8") as text_file:
            text_file.write(IntegrationTestsOfSyncOperations.test_name)

    @timedtest
    def test_a_single_file_syncs(self):

        test_start = time.time()

        self.start_one_and_two_subsyncits()
        try:
            test_file_a = self.test_sync_dir_one + "testfile.txt"
            with open(test_file_a, "w", encoding="utf-8") as text_file:
                text_file.write("Hello")
            test_file_two = self.test_sync_dir_two + "testfile.txt"
            self.wait_for_file_to_appear(test_file_two)
            self.wait_for_file_contents_to_contain(test_file_two, "Hello")
        finally:
            self.end_process_one_and_two()

        rows = self.get_db_rows()
        self.should_start_with(rows, 0, "01, /testfile.txt, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0")


    @timedtest
    def test_a_changed_file_syncs_back(self):

        self.start_one_and_two_subsyncits()

        test_start = time.time()

        time.sleep(2)

        try:
            test_file_in_a = self.test_sync_dir_one + "testfile.txt"
            with open(test_file_in_a, "w", encoding="utf-8") as text_file:
                text_file.write("Hello") # f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0

            test_file_in_two = self.test_sync_dir_two + "testfile.txt"
            self.wait_for_file_to_appear(test_file_in_two)

            time.sleep(1)
            with open(test_file_in_two, "w", encoding="utf-8") as text_file:
                text_file.write("Hello to you too") # 3f19e1ea9c19f0c6967723b453a423340cbd6e36

            self.wait_for_file_contents_to_contain(test_file_in_a, "Hello to you too")

        finally:
            self.end_process_one_and_two()

        rows = self.get_db_rows()
        self.should_start_with(rows, 0, "01, /testfile.txt, 3f19e1ea9c19f0c6967723b453a423340cbd6e36, 3f19e1ea9c19f0c6967723b453a423340cbd6e36")



    @timedtest
    def test_files_with_special_characters_make_it_to_svn_and_back(self):

        # It is alleged that some characters are not allowed in right-of-the-port-number paths.
        # Between them Apache2 and Subversion munge a few for display purposes. That's either on the way into Subversion,
        # or on the way back over HTTP into the file system. No matter - the most important representation of file name
        # is in the local file system, and we only require consistency GET/PUT from/to that.

#        test_start = time.time()

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:
            files = ["a&a", "b{b", "c?c", "d$d", "e;e", "f=f", "g+g", "h,h",
                     "i(i", "j)j", "k[k", "l]l", "m:m", "n\'n", "o\"o", "p`p", "q*q", "r~r"]
            for f in files:
                with open(self.test_sync_dir_one + f, "w", encoding="utf-8") as text_file:
                    text_file.write("Hello")

            self.expect201(
                requests.put(self.svn_url + "CONTROL",
                             auth=(self.user, self.passwd), data="Hello",
                             verify=False))

            start = time.time()
            elapsed = 0

            files_not_found_in_subversion = copy.deepcopy(files)

            while len(files_not_found_in_subversion) > 1 and elapsed < 90:
                files2 = copy.deepcopy(files_not_found_in_subversion)
                for f in files2:
                    if requests.get(self.svn_url + f, auth=(self.user, self.passwd), verify=False).status_code == 200:
                        files_not_found_in_subversion.remove(f)
                elapsed = time.time() - start

            self.assertEquals(len(files_not_found_in_subversion), 1, "These not found in svn: " + str(files_not_found_in_subversion))

            # `?` isn't handled seamlessly by the requests library
            if requests.get(self.svn_url + "c?c".replace("?", "%3f"),
                            auth=(self.user, self.passwd),
                            verify=False).status_code == 200:
                files_not_found_in_subversion.remove("c?c")

            self.assertEquals(len(files_not_found_in_subversion), 0, "Some not found in Subversion: " + str(files_not_found_in_subversion))

            self.wait_for_file_to_appear(self.test_sync_dir_one + "CONTROL")

            # As Subsncit pulled down files it didn't already have, the only one to add was the `CONTROL` file.
            self.maxDiff = None
            self.assertEquals(str(sorted(
                os.listdir(self.test_sync_dir_one))),
                "['CONTROL', 'a&a', 'b{b', 'c?c', 'd$d', 'e;e', 'f=f', 'g+g', 'h,h', 'i(i', 'j)j', 'k[k', 'l]l', 'm:m', \"n\'n\", 'o\"o', 'p`p', 'q*q', 'r~r']")

        finally:
            self.end_process_one()

        rows = self.get_db_rows()

        self.should_start_with(rows, 0, '01, /CONTROL, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 1, '02, /i(i, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 2, '03, /g+g, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 3, '04, /l]l, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 4, '05, /r~r, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 5, '06, /c?c, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 6, '07, /j)j, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 7, '08, /d$d, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 8, '09, /q*q, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 9, '10, /o"o, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 10, '11, /p`p, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 11, '12, /b{b, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 12, '13, /f=f, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 13, '14, /h,h, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 14, '15, /m:m, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 15, '16, /e;e, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 16, "17, /n'n, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None")
        self.should_start_with(rows, 17, '18, /k[k, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')
        self.should_start_with(rows, 18, '19, /a&a, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, f7ff9e8b7bb2e09b70935a5d785e0cc5d9d0abf0, None')


    @timedtest
    def test_a_files_in_a_directory_gets_pushed_up(self):

        # It is alleged that some characters are not allowed in right-of-the-port-number paths.
        # Between them Apache2 and Subversion munge a few for display purposes. That's either on the way into Subversion,
        # or on the way back over HTTP into the file system. No matter - the most important representation of file name
        # is in the file system, and we only require consistent GET/PUT from/to that.

        dir = self.test_sync_dir_one

        os.mkdir(dir + "aaa")
        with open(dir + "aaa/test.txt", "w") as text_file:
            text_file.write("testttt")

        self.process_one = self.start_subsyncit(self.svn_url, dir, self.process_output_one)

        try:
            start = time.time()
            while True:
                if self.path_exists_on_svn_server("aaa") and self.path_exists_on_svn_server("aaa/test.txt"):
                    break
                if time.time() - start > 15:
                    self.fail("dir aaa and file aaa/test.txt should be up on " + self.svn_url + " within 90 seconds")
                time.sleep(1.5)

        finally:
            self.end_process_one()


    @timedtest
    def test_a_deleted_file_syncs_down(self):

        test_start = time.time()

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
        try:
            self.wait_for_file_to_appear(self.test_sync_dir_one + "output.txt")

            self.expect204(requests.delete(self.svn_url + "output.txt", auth=(self.user, self.passwd), verify=False))

            self.wait_for_file_to_disappear(self.test_sync_dir_one + "output.txt")

        finally:
            self.end_process_one()

            rows = self.get_db_rows()
            if len(rows) > 0:
                print("row 0 " + str(rows[0]))


    @timedtest
    def test_a_deleted_file_syncs_up(self):

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="Hello",
                                    verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:
            self.wait_for_file_to_appear(self.test_sync_dir_one + "output.txt")

        finally:
            self.end_process_one()


    @timedtest
    def test_a_deleted_file_syncs_back(self):

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one,
                                                extra_opt='--do-not-scan-file-system-periodically')
        self.process_two = self.start_subsyncit(self.svn_url, self.test_sync_dir_two, self.process_output_two,
                                                extra_opt='--do-not-scan-file-system-periodically')
        time.sleep(2)

        try:
            a_path = self.test_sync_dir_one + "testfile"
            with open(a_path, "w", encoding="utf-8") as text_file:
                text_file.write("Hello")
            b_path = self.test_sync_dir_two + "testfile"
            self.wait_for_file_to_appear(b_path)
            time.sleep(2) # Needed because of the 2 seconds grace on FS actions for recently downloaded (GET) files
            self.journal_to_one_and_two("-- orig sync'd from one to two --")
            print(b_path)
            os.remove(b_path)
            self.wait_for_file_to_disappear(a_path)
            time.sleep(2)
        finally:
            self.end_process_one_and_two()

        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Batch 1 of: PUT(s) to Svn took M ms, 1 PUT files, taking M ms each. stack: main:loop:PUTs
                -- orig sync'd from one to two --
                [SECTION] Instructions created: GETs 1 local deletes (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Performing 1 local deletes took M ms. stack: main:loop:local_deletes             
            """), self.simplify_output(self.process_output_one))

        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Instructions created: 1 file GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 1 files (/testfile), at F files/sec. stack: main:loop:GETs
                -- orig sync'd from one to two --
                [SECTION] DELETEs on Subversion server took M ms, 0 directories and 1 files, S secs per DELETE.
            """), self.simplify_output(self.process_output_two))



    @timedtest
    def test_a_file_changed_while_sync_agent_offline_still_sync_syncs_later(self):

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="As First PUT Up To Svn", verify=False))

        self.start_subsyncit_one()
        self.start_subsyncit_two()

        try:
            file_in_subsyncit_one = self.test_sync_dir_one + "output.txt"
            file_in_subsyncit_two = self.test_sync_dir_two + "output.txt"
            self.wait_for_file_to_appear(file_in_subsyncit_one)
            self.wait_for_file_to_appear(file_in_subsyncit_two)
            self.signal_stop_of_subsyncit(self.test_sync_dir_two)
            self.process_two.wait()
            with open(file_in_subsyncit_two, "w") as text_file:
                text_file.write("Overrite locally in client 2")
            self.start_subsyncit_two()
            self.wait_for_file_contents_to_contain(file_in_subsyncit_one, "Overrite locally in client 2")
        finally:
            self.end_process_one_and_two()


    @timedtest
    def test_a_file_changed_while_sync_agent_offline_still_sync_syncs_later_when_no_fs_listener(self):

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="As First PUT Up To Svn", verify=False))

        self.start_subsyncit_one(extra_opt="--do-not-listen-for-file-system-events")
        self.start_subsyncit_two(extra_opt="--do-not-listen-for-file-system-events")

        try:
            file_in_subsyncit_one = self.test_sync_dir_one + "output.txt"
            file_in_subsyncit_two = self.test_sync_dir_two + "output.txt"
            self.wait_for_file_to_appear(file_in_subsyncit_one)
            self.wait_for_file_to_appear(file_in_subsyncit_two)
            self.signal_stop_of_subsyncit(self.test_sync_dir_two)
            self.process_two.wait()
            # time.sleep(10)
            with open(file_in_subsyncit_two, "w") as text_file:
                text_file.write("Overrite locally in client 2")
            self.start_subsyncit_two()
            self.wait_for_file_contents_to_contain(file_in_subsyncit_one, "Overrite locally in client 2")
        finally:
            self.end_process_one_and_two()


    @timedtest
    def test_that_a_restarted_client_picks_up_where_it_left_off(self):

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="hello", verify=False))

        self.start_subsyncit_one(extra_opt="--do-not-listen-for-file-system-events")

        try:
            self.wait_for_file_to_appear(self.test_sync_dir_one + "output.txt")
            self.signal_stop_of_subsyncit(self.test_sync_dir_one)
            self.process_one.wait()
            self.start_subsyncit_one()
            time.sleep(2)
        finally:
            self.end_process_one()

        output = self.simplify_output(self.process_output_one)
        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Instructions created: 1 file GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 1 files (/output.txt), at F files/sec. stack: main:loop:GETs
                [STARTING] last_root_revision=XX
            """), output)


    @timedtest
    def test_both_change_detectors_turned_off_means_that_files_are_not_pushed(self):

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="As First PUT Up To Svn", verify=False))

        self.start_subsyncit_one(extra_opt="--do-not-scan-file-system-periodically", extra_opt2="--do-not-listen-for-file-system-events")
        self.start_subsyncit_two(extra_opt="--do-not-scan-file-system-periodically", extra_opt2="--do-not-listen-for-file-system-events")

        try:
            file_in_subsyncit_one = self.test_sync_dir_one + "output.txt"
            file_in_subsyncit_two = self.test_sync_dir_two + "output.txt"
            self.wait_for_file_to_appear(file_in_subsyncit_one)
            self.wait_for_file_to_appear(file_in_subsyncit_two)
            self.signal_stop_of_subsyncit(self.test_sync_dir_two)
            self.process_two.wait()
            with open(file_in_subsyncit_two, "w") as text_file:
                text_file.write("Overrite locally in client 2")
            self.start_subsyncit_two(extra_opt="--do-not-scan-file-system-periodically", extra_opt2="--do-not-listen-for-file-system-events")
            ae = None
            try:
                self.wait_for_file_contents_to_contain(file_in_subsyncit_one, "Overrite locally in client 2")
            except AssertionError as e:
                ae = e
            self.assertIsNotNone(ae)
        finally:
            self.end_process_one_and_two()


    @timedtest
    def test_a_file_in_dir_added_to_repo_while_sync_agent_offline_still_sync_syncs_later(self):

        self.expect201(requests.request('MKCOL',
                                        self.svn_url + "fred/",
                                        auth=(self.user, self.passwd),
                                        verify=False))
        self.expect201(requests.put(self.svn_url + "fred/output.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:
            testfile_in_a = self.test_sync_dir_one + "fred/output.txt"
            self.wait_for_file_to_appear(testfile_in_a)
        finally:
            self.end_process_one()


    @timedtest
    def test_that_excluded_patterns_work(self):


        self.expect201(requests.put(self.svn_url + ".subsyncit-excluded-filename-patterns", auth=(self.user, self.passwd), data=".*\.foo\n.*\.txt\n.*\.bar", verify=False))

        self.expect201(requests.put(self.svn_url + "output.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.expect201(requests.put(self.svn_url + "output.zzz", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:

            test_file_in_a = self.test_sync_dir_one + "output.zzz"
            self.wait_for_file_to_appear(test_file_in_a)

            test_file_in_a = self.test_sync_dir_one + "output.txt"
            time.sleep(2) # the two files should arrive pretty much at the same time, but why not wait 2 secs, heh?
            if os.path.exists(test_file_in_a):
                self.fail("File " + test_file_in_a + " should not have appeared but did.")
        finally:
            self.end_process_one()


    @timedtest
    def test_a_file_in_dir_with_spaces_in_names_are_added_to_repo_while_sync_agent_offline_still_sync_syncs_later(self):

        self.expect201(requests.request('MKCOL',
                                        self.svn_url + "f r e d/",
                                        auth=(self.user, self.passwd),
                                        verify=False))
        self.expect201(requests.put(self.svn_url + "f r e d/o u t & p u t.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:
            testfile_in_a = self.test_sync_dir_one + "f r e d/o u t & p u t.txt"
            self.wait_for_file_to_appear(testfile_in_a)
        finally:
            self.end_process_one()

        # with open(self.testSyncDir1 + "paul was here.txt", "w") as text_file:
        #     text_file.write("Hello to you too")


    @timedtest
    def test_a_file_changed_while_sync_agent_offline_does_not_sync_sync_later_if_it_changed_on_the_server_too(self):

        self.expect201(requests.put(self.svn_url + "something.txt", auth=(self.user, self.passwd), data="Hello", verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "aaa/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.put(self.svn_url + "aaa/another.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
        try:
            self.wait_for_file_contents_to_contain(self.test_sync_dir_one + "something.txt", "Hello")
            self.signal_stop_of_subsyncit(self.test_sync_dir_one)
            self.process_one.wait()

            self.expect204(requests.put(self.svn_url + "something.txt", auth=(self.user, self.passwd), data="Hello changed on server", verify=False))

            with open(self.test_sync_dir_one + "something.txt", "w") as text_file:
                text_file.write("Hello changed locally too")

            with open(self.test_sync_dir_one + "aaa/something_else.txt", "w") as text_file:
                text_file.write("Hello changed locally too")

            os.mkdir(self.test_sync_dir_one + "aaa/bbb")
            with open(self.test_sync_dir_one + "aaa/bbb/something_else.txt", "w") as text_file:
                text_file.write("Hello changed locally too")

            self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

            time.sleep(2)

            self.wait_for_file_contents_to_contain(self.test_sync_dir_one + "something.txt", "Hello changed on server")
            clash_file = glob2.glob(self.test_sync_dir_one + "*.clash_*")[0]
            self.wait_for_file_contents_to_contain(clash_file, "Hello changed locally too")

            self.wait_for_URL_to_appear(self.svn_url + "aaa/something_else.txt")
            self.wait_for_URL_to_appear(self.svn_url + "aaa/bbb/something_else.txt")
            self.wait_for_file_to_appear(self.test_sync_dir_one + "aaa/another.txt")

        finally:
            self.end_process_one()


    @timedtest
    def test_cant_start_on_a_non_svn_dav_server(self):

        self.process_one = self.start_subsyncit_without_user_and_password("http://localhost:8099/", self.test_sync_dir_one)
        try:
            self.wait_for_file_contents_to_contain(self.db_dir_one + os.sep + "subsyncit.err", "http://localhost:8099 does not have Subversion mounted on that URL")
        finally:
            self.end_process_one()


    @timedtest
    def test_cant_start_on_a_svn_dav_server_with_incorrect_password(self):

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one, passwd="sdfsdfget3qgwegsdgsdgsf")
        try:
            self.wait_for_file_contents_to_contain(self.db_dir_one + os.sep + "subsyncit.err", "http://127.0.0.1:8099/svn/testrepo/integrationTests/") # start
            self.wait_for_file_contents_to_contain(self.db_dir_one + os.sep + "subsyncit.err", " is saying that the user is not authorized") # end
        finally:
            self.end_process_one()


    @timedtest
    def test_cant_start_on_a_server_that_is_down(self):

        self.process_one = self.start_subsyncit("https://localhost:34456/", self.test_sync_dir_one, self.process_output_one)
        try:
            time.sleep(2)
            self.wait_for_file_contents_to_contain(self.db_dir_one + os.sep + "subsyncit.err", " Failed to establish a new connection")
        finally:
            self.end_process_one()

        self.process_one.wait()

        self.assertEquals(self.get_status_dict()['online'], False)

    @timedtest
    def test_an_excluded_filename_patterns_is_not_pushed_up(self):

        self.expect201(requests.put(self.svn_url + ".subsyncit-excluded-filename-patterns", auth=(self.user, self.passwd), data=".*\.txt\n\~\$.*\n", verify=False))

        testfile_in_a = self.test_sync_dir_one + "output.txt"
        with open(testfile_in_a, "w") as text_file:
            text_file.write("I should not be PUT up to the server")

        testfile_in_a = self.test_sync_dir_one + "~$output"
        with open(testfile_in_a, "w") as text_file:
            text_file.write("I also should not be PUT up to the server")

        testfile_in_a = self.test_sync_dir_one + "output.zzz"
        with open(testfile_in_a, "w") as text_file:
            text_file.write("Only I can go to the server")

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:

            self.wait_for_URL_to_appear(self.svn_url + "output.zzz")

            time.sleep(2) # the all files should arrive pretty much at the same time, but why not wait 5 secs, heh?

            self.assertEqual(
                requests.get(self.svn_url + "output.txt",
                             auth=(self.user, self.passwd), verify=False)
                    .status_code, 404, "URL " + self.svn_url + "output.txt" + " should NOT have appeared, but it did")

            self.assertEqual(
                requests.get(self.svn_url + "~$output",
                             auth=(self.user, self.passwd), verify=False)
                    .status_code, 404, "URL " + self.svn_url + "~$output" + " should NOT have appeared, but it did")


        finally:
            self.end_process_one()


    @timedtest
    def test_a_partially_downloaded_big_file_recovers(self):

        filename1 = str(sh.pwd()).strip('\n') + "/testBigRandomFile1"
        filename2 = str(sh.pwd()).strip('\n') + "/testBigRandomFile2"
        start = time.time()

        if not os.path.exists(filename1):
            self.make_a_big_random_file(filename1, self.size)
        if not os.path.exists(filename2):
            self.make_a_big_random_file(filename2, self.size)

        sz = os.stat(filename1).st_size
        self.upload_file(filename1, self.svn_url + "testBigRandomFile")

        start = time.time()
        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
        try:
            print("Started Subsyncit, and waiting for " + str(self.size) + "MB random file to be downloaded from Svn and be at least " + str(sz) + " MB ... ")
            self.wait_for_file_contents_to_be_sized_above_or_eq_too(self.test_sync_dir_one + "testBigRandomFile", sz)
            print(" ... took secs: " + str(round(time.time() - start, 1)))

            self.signal_stop_of_subsyncit(self.test_sync_dir_one)
            self.journal_to_one("--controlled shutdown signalled--")
            self.process_one.wait()

            self.upload_file(filename2, self.svn_url + "testBigRandomFile")
            self.journal_to_one("--Uploaded a alternate version of testBigRandomFile--")
            start = time.time()
            self.journal_to_one("--Restart Subsyncit--")
            self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
            self.wait_for_file_contents_to_be_sized_below(self.test_sync_dir_one + "testBigRandomFile", (sz * 99 / 100))
            self.wait_for_file_contents_to_be_sized_above_or_eq_too(self.test_sync_dir_one + "testBigRandomFile", (sz / 10))
            self.journal_to_one("--kill Subsyncit--")
            self.process_one.kill()
            self.journal_to_one("--killed after secs: " + str(round(time.time() - start, 1)))

            aborted_get_size = os.stat(self.test_sync_dir_one + "testBigRandomFile").st_size
            print("\\  / YES, that 30 lines of a process being killed and the resulting stack trace is intentional at this stage in the integration test suite\n \\/")
            self.assertNotEquals(aborted_get_size, sz, "Aborted file size: " + str(aborted_get_size) + " should have been less that the ultimate size of the test file: " + str(sz))

            self.journal_to_one("-- DB ROWS START --")
            self.journal_to_one(self.get_db_rows_as_text())
            self.journal_to_one("-- DB ROWS END --")

            self.journal_to_one("--Restart Subsyncit--")
            self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
            self.wait_for_file_contents_to_be_sized_above_or_eq_too(self.test_sync_dir_one + "testBigRandomFile", sz)
        finally:
            self.end_process_one()


        clash_file = glob2.glob(self.test_sync_dir_one + "*.clash_*")[0]
        self.assertEqual(os.stat(clash_file).st_size, aborted_get_size)


    @timedtest
    def test_that_we_understand_how_revisions_can_be_a_surrogate_for_a_proper_merkle_tree(self):

        test_start = time.time()

        self.expect201(requests.request('MKCOL', self.svn_url + "fred/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "wilma/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "barney/", auth=(self.user, self.passwd), verify=False))

        self.assertEquals(self.no_leading_spaces(
            """<root> : 03
               fred/ : 01
               wilma/ : 02
               barney/ : 03
               """),
            self.get_rev_summary_for_root_barney_wilma_fred_and_bambam_if_there())

        self.expect201(requests.request('MKCOL', self.svn_url + "wilma/bambam", auth=(self.user, self.passwd), verify=False))

        # Only 'wilma' gets a actual directory version (to #4) bump, but the repo is bumped to latest everywhere.
        self.assertEquals(self.no_leading_spaces(
            """<root> : 03
               fred/ : 01
               wilma/ : 03
               wilma/bambam : 03
               barney/ : 02
               """),
            self.get_rev_summary_for_root_barney_wilma_fred_and_bambam_if_there())


    @timedtest
    def test_that_subsynct_can_collect_the_merkel_esque_revisions_from_subversion(self):

        test_start = time.time()

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        self.expect201(requests.request('MKCOL', self.svn_url + "fred/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "wilma/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "barney/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('PUT', self.svn_url + "wilma/bambam", data="hi", auth=(self.user, self.passwd), verify=False))

        try:
            self.wait_for_file_to_appear(self.test_sync_dir_one + "fred")
            self.wait_for_file_to_appear(self.test_sync_dir_one + "wilma/bambam")
            self.wait_for_file_to_appear(self.test_sync_dir_one + "barney")

            time.sleep(1)

        finally:
            self.end_process_one()

        self.process_one.wait()

        # Only 'wilma' gets a actual directory version (to #4) bump, but the repo is bumped to latest everywhere.
        self.assertEquals(self.no_leading_spaces(
            """<root> : 03
               fred/ : 01
               wilma/ : 03
               wilma/bambam : 03
               barney/ : 02
               """),
            self.get_rev_summary_for_root_barney_wilma_fred_and_bambam_if_there())


        rows = self.get_db_rows()

        self.should_start_with(rows, 0, "01, /fred/, None, None, None")
        self.should_start_with(rows, 1, "02, /barney/, None, None, None")
        self.should_start_with(rows, 2, "03, /wilma/, None, None, None")
        self.should_start_with(rows, 3, "03, /wilma/bambam, c22b5f9178342609428d6f51b2c5af4c0bde6a42, c22b5f9178342609428d6f51b2c5af4c0bde6a42, None")

        output = self.simplify_output(self.process_output_one)
        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Instructions created: 3 dir GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 3 dirs, at F files/sec. stack: main:loop:GETs
                [SECTION] Instructions created: 1 file GETs (children of '/wilma/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 1 files (/wilma/bambam), at F files/sec. stack: main:loop:GETs
            """), output)


    @timedtest
    def test_that_subsynct_can_participate_in_the_merkel_esque_revisions_with_subversion(self):

        # This test is much like the one above and wants to allow an eyeball confirmation that Subsyncit is adequately tracking revision numbers

        test_start = time.time()

        self.expect201(requests.request('MKCOL', self.svn_url + "fred/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "wilma/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "barney/", auth=(self.user, self.passwd), verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one, extra_opt="--do-not-scan-file-system-periodically")

        try:

            self.wait_for_file_to_appear(self.test_sync_dir_one + "wilma")
            with open(self.test_sync_dir_one + "wilma/bambam", "w") as text_file:
                text_file.write("hi")

            self.wait_for_file_to_appear(self.test_sync_dir_one + "fred")
            self.wait_for_file_to_appear(self.test_sync_dir_one + "barney")
            self.wait_for_URL_to_appear(self.svn_url + "wilma/bambam")

            # Only 'wilma' gets a actual directory version (to #4) bump, but the repo is bumped to latest everywhere.
            self.assertEquals(self.no_leading_spaces(
                """<root> : 03
                   fred/ : 01
                   wilma/ : 03
                   wilma/bambam : 03
                   barney/ : 02
                   """),
                self.get_rev_summary_for_root_barney_wilma_fred_and_bambam_if_there())

            time.sleep(5)


        finally:
            self.end_process_one()


        rows = self.get_db_rows()

        self.assertEquals(self.no_leading_spaces(
             """01, /fred/, None, None, None
                02, /barney/, None, None, None
                03, /wilma/, None, None, None
                03, /wilma/bambam, c22b5f9178342609428d6f51b2c5af4c0bde6a42, c22b5f9178342609428d6f51b2c5af4c0bde6a42, None"""),
            "\n".join(rows))

        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Instructions created: 3 dir GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 3 dirs, at F files/sec. stack: main:loop:GETs
                [SECTION] Batch 1 of: PUT(s) to Svn took M ms, 1 PUT files, taking M ms each. stack: main:loop:PUTs
                [SECTION] Instructions created: 3 dir GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
            """), self.simplify_output(self.process_output_one))


    @timedtest
    def test_that_subsynct_can_participate_in_a_deeper_merkle_traversal(self):

        # This test is much like the one above and wants to allow an eyeball confirmation that Subsyncit is adequately tracking revision numbers

        test_start = time.time()

        self.expect201(requests.request('MKCOL', self.svn_url + "a/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/a/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/a/b", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('PUT', self.svn_url + "a/a/b/txt", data="hi", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/b", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/b/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "a/b/b", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/a/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/a/b", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/b", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/b/a", auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.request('MKCOL', self.svn_url + "b/b/b", auth=(self.user, self.passwd), verify=False))

        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)

        try:
            self.wait_for_file_to_appear(self.test_sync_dir_one + "a/a/b/txt")
            self.wait_for_file_to_appear(self.test_sync_dir_one + "b/b/b")
            time.sleep(1)

        finally:
            self.end_process_one()

        self.process_one.wait()

        self.assertEquals(self.no_leading_spaces(
            """01, /a/a/a/, None, None, None
               02, /a/a/, None, None, None
               02, /a/a/b/, None, None, None
               02, /a/a/b/txt, c22b5f9178342609428d6f51b2c5af4c0bde6a42, c22b5f9178342609428d6f51b2c5af4c0bde6a42, None
               03, /a/b/a/, None, None, None
               04, /a/, None, None, None
               04, /a/b/, None, None, None
               04, /a/b/b/, None, None, None
               05, /b/a/a/, None, None, None
               06, /b/a/, None, None, None
               06, /b/a/b/, None, None, None
               07, /b/b/a/, None, None, None
               08, /b/, None, None, None
               08, /b/b/, None, None, None
               08, /b/b/b/, None, None, None"""), "\n".join(self.get_db_rows()))

        self.assertEquals(self.no_leading_spaces(
             """[SECTION] Instructions created: 2 dir GETs (children of '/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 2 dirs, at F files/sec. stack: main:loop:GETs
                [SECTION] Instructions created: 4 dir GETs (children of '/a/, /b/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 4 dirs, at F files/sec. stack: main:loop:GETs
                [SECTION] Instructions created: 8 dir GETs (children of '/a/a/, /a/b/, /b/a/, /b/b/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 8 dirs, at F files/sec. stack: main:loop:GETs
                [SECTION] Instructions created: 1 file GETs (children of '/a/a/b/') took M ms. stack: main:loop:svn_changesʔ
                [SECTION] Batch 1 of: GET(s) from Svn took M ms: 1 files (/a/a/b/txt), at F files/sec. stack: main:loop:GETs
            """), self.simplify_output(self.process_output_one))


    # ======================================================================================================

    def path_exists_on_svn_server(self, path):
        return 200 == requests.get(self.svn_url + path, auth=(self.user, self.passwd), verify=False).status_code


    def journal_to_one_and_two(self, s):
        self.journal_to_one(s)
        self.journal_to_two(s)


    def journal_to_one(self, s):
        self.process_output_one.writelines(s + "\n")


    def journal_to_two(self, s):
        self.process_output_two.writelines(s + "\n")


    def get_status_dict(self):
        return json.loads(self.file_contents(self.db_dir_one + os.sep + "status.json"))


    def get_rev_summary_for_root_barney_wilma_fred_and_bambam_if_there(self):

        bambam = -1
        try:
            bambam = self.directory_revision_for("wilma/bambam")
        except AssertionError:
            pass

        root = self.directory_revision_for("")
        fred = self.directory_revision_for("fred/")
        wilma = self.directory_revision_for("wilma/")
        barney = self.directory_revision_for("barney/")

        # Revisions are normalized down to 1,2,3,4 when they actually might be 12,13,14 in the repo
        revisions = {root: 0, fred: 0, wilma: 0, barney: 0}
        revision_map = {}
        for ix, key in enumerate(sorted(revisions.keys())):
            revision_map[key] = str(ix + 1).zfill(2)

        return "<root> : " + revision_map[root] + "\n" \
               + "fred/ : " + revision_map[fred] + "\n" \
               + "wilma/ : " + revision_map[wilma] + "\n" \
               + ("wilma/bambam : " + revision_map[bambam] + "\n" if bambam > 0 else "") \
               + "barney/ : " + revision_map[barney] + "\n"


    def no_leading_spaces(self, string):
        c = [item.strip() for item in string.splitlines()]
        return '\n'.join(c)

    def directory_revision_for(self, dir):
        options = requests.request("OPTIONS", self.svn_url + dir, auth=("davsvn", "davsvn"),
                                   data='<?xml version="1.0" encoding="utf-8"?><D:options xmlns:D="DAV:"><D:activity-collection-set></D:activity-collection-set></D:options>')

        self.assertEquals(options.status_code, 200)

        content = options.content.decode("utf-8")
        youngest_rev = options.headers["SVN-Youngest-Rev"].strip()

        rev_dir = self.svn_url.replace('testrepo/', 'testrepo/!svn/rvr/' + youngest_rev + "/") + dir
        propfind = requests.request('PROPFIND', rev_dir, auth=("davsvn", "davsvn"), headers = {'Depth': '1'},
                                    data='<?xml version="1.0" encoding="utf-8"?>'
                                         '<propfind xmlns="DAV:">'
                                         '<prop>'
                                         '<version-name/>'
                                         '</prop>'
                                         '</propfind>')

        self.assertEquals(propfind.status_code, 207)

        content = propfind.content.decode("utf-8")
        return int(str([line for line in content.splitlines() if ':version-name>' in line]).split(">")[1].split("<")[0])

    def repo_rev_for(self, dir, offset):
        # from HTML
        get = requests.get(self.svn_url + dir, auth=(self.user, self.passwd), verify=False)
        self.assertEqual(get.status_code, 200)
        try:
            return int(str([line for line in get.text.splitlines() if 'testrepo - Revision' in line]).split(" ")[3][:-1]) - offset
        except IndexError:
            return "?"


    def make_a_big_random_file(self, filename, size):
        start = time.time()
        print("Making " + size + " MB random file " + filename + " (potentially time consuming, but once off) ... ")
        sh.bash("tests/make_a_so_big_file.sh", filename, size)
        print(" ... secs: " + str(round(time.time() - start, 1)))


    def list_files(self, root):
        glob = glob2.glob(root + "**")
        print("List of files in " + root + "folder:")
        if len(glob) == 0:
            print("  no files")
        for s in glob:
            print("  " + (str(s)) + " " + str(os.stat(str(s)).st_size))


    def expect201(self, commandOutput):
        self.assertEqual("<Response [201]>", str(commandOutput))


    def expect204(self, commandOutput):
        self.assertEqual("<Response [204]>", str(commandOutput))


    def should_start_with(self, rows, row, start_with_this):
        self.assertTrue(rows[row].startswith(start_with_this), msg="Was actually: " + rows[row])


    def get_db_rows_as_text(self):
        return "\n".join(self.get_db_rows())


    def get_db_rows(self):
        db_ = self.db_dir_one + os.sep + "subsyncit.db"

        time.sleep(2.5)
        db = TinyDB(db_)
        files_table = db.table('files')

        revisions = {}
        for row in files_table.all():
            revisions[row['RV']] = 0

        # Revisions are normalized down to 1,2,3,4 when they actually might be 12,13,18 in the repo
        revision_map = {}
        for ix, (key, value) in enumerate(sorted(revisions.items())):
            revision_map[key] = ix + 1

        rv = ""
        for row in files_table.all():
            rv += str(revision_map[row['RV']]).zfill(2) + ", " + row['FN'] + ", " + str(row['RS'])+ ", " + str(row['LS']) + ", " + str(row['I'])  + "\n"

        return sorted(rv.splitlines())

    @classmethod
    def kill_docker_container(cls, wait):
        try:
            ctr = cls.client.containers.get("subsyncitTests")
            ctr.stop()
            if wait:
                status = 200
                while status == 200:
                    status = -1
                    try:
                        get = requests.get("http://127.0.0.1:8099")
                        status = get.status_code
                    except:
                        pass
                while cls.client.containers.get("subsyncitTests"):
                    time.sleep(0.2)
                    pass  # keep looping until there's an exception
        except NotFound:
            pass


    def end(self, p, dir):
        if p is not None:
            self.signal_stop_of_subsyncit(dir)


    def reset_test_dir(self, dirname):
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
        os.makedirs(dirname)


    def signal_stop_of_subsyncit(self, dir):
        if not os.path.exists(dir):
            os.makedirs(dir)

        stop_ = dir + "subsyncit.stop"
        with open(stop_, "w") as text_file:
            text_file.write("anything")

    def wait_for_file_to_appear(self, file_should_appear):
        start = time.time()
        while not os.path.exists(file_should_appear):
            if time.time() - start > 15:
                self.fail(file_should_appear + " should have appeared but did not")
            time.sleep(.01)


    def wait_for_URL_to_appear(self, url):

        start = time.time()
        status = requests.get(url, auth=(self.user, self.passwd), verify=False).status_code
        while status == 404:
            if time.time() - start > 15:
                break
            time.sleep(.1)
            status = requests.get(url, auth=(self.user, self.passwd), verify=False).status_code

        if status != 200:
            self.fail("URL " + url + " should have appeared, but it did not (status code: " + str(status) + ")")


    def process_output(self, line):
        print(line)
        self.line += ("\n" + line)


    def start_one_and_two_subsyncits(self):
        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one)
        self.process_two = self.start_subsyncit(self.svn_url, self.test_sync_dir_two, self.process_output_two)
 

    def start_subsyncit_one(self, passwd=None, extra_opt=None, extra_opt2=None):
        self.process_one = self.start_subsyncit(self.svn_url, self.test_sync_dir_one, self.process_output_one, passwd=passwd, extra_opt=extra_opt, extra_opt2=extra_opt2)


    def start_subsyncit_two(self, passwd=None, extra_opt=None, extra_opt2=None):
        self.process_two = self.start_subsyncit(self.svn_url, self.test_sync_dir_two, self.process_output_two, passwd=passwd, extra_opt=extra_opt, extra_opt2=extra_opt2)


    def start_subsyncit(self, svn_repo, dir, process_output, passwd=None, extra_opt=None, extra_opt2=None):
        if passwd is None:
            passwd = self.passwd
        print("Subsyncit start. URL: " + svn_repo + ", sync dir: " + dir)
        cwd = os.getcwd()
        args = ["run", "--branch", cwd + os.sep + 'subsyncit.py', svn_repo, dir, self.user, '--no-verify-ssl-cert', "--sleep-secs-between-polling", "1", '--passwd', passwd]
        if extra_opt:
            args.append(extra_opt)
        if extra_opt2:
            args.append(extra_opt2)
        python = sh.coverage(args, _out=process_output, _err_to_out=True, _bg=True, _cwd=dir)
        return python


    def start_subsyncit_without_user_and_password(self, svn_repo, dir):
        print("Subsyncit start. URL: " + svn_repo + ", dir: " + dir)
        python = sh.python3("subsyncit.py", svn_repo, dir, None, '--no-verify-ssl-cert',
                           "--sleep-secs-between-polling", "1",
                           '--passwd', "*NONE", _out=self.process_output,
                           _err_to_out=True, _bg=True)
        return python


    def wait_for_file_contents_to_be_sized_above_or_eq_too(self, f, sz):
        self.wait_for_file_to_appear(f)
        start = time.time()
        while os.stat(f).st_size < sz:
            time.sleep(.01)
            if time.time() - start > 20:
                self.fail("should have made it above " + str(sz) + " by now, but is " + str(os.stat(f).st_size))


    def wait_for_file_contents_to_be_sized_below(self, f, sz):
        self.wait_for_file_to_appear(f)
        start = time.time()
        while os.stat(f).st_size >= sz:
            time.sleep(.01)
            if time.time() - start > 15:
                self.fail("should have made it below that size by now")


    def wait_for_file_contents_to_contain(self, f, val):

        self.wait_for_file_to_appear(f)
        contents = self.file_contents(f)
        start = time.time()

        while val not in contents:
            if time.time() - start > 15:
                self.assertIn(val, contents, "file " + f + " should have contained '" + val + "' but was '" + contents + "' instead.")
            time.sleep(1)
            contents = self.file_contents(f)

    def file_contents(self, f):
        open1 = open(f, encoding="utf-8")
        contents = open1.read()
        open1.close()
        return contents


    def wait_for_file_to_disappear(self, f):
        start = time.time()
        while os.path.exists(f):
            if time.time() - start > 45:
                self.fail("file " + f + " didn't disappear in 45 secs")
            time.sleep(1)


    def upload_file(self, filename, remote_path):
        f = open(filename, 'rb')
        requests.put(remote_path, auth=(self.user, self.passwd), data=f, verify=False)
        f.close()

    def simplify_output(self, process_output):
        op = process_output.getvalue()
        rv = ""
        regex = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}): ")
        regex2 = re.compile(r"[0-9]\d*(\.\d*)? ms")
        regex3 = re.compile(r"[0-9]\d*(\.\d*)? ns")
        regex4 = re.compile(r"[0-9]\d*(\.\d*)? files/sec")
        regex5 = re.compile(r"[0-9]\d*(\.\d*)? secs per")
        regex6 = re.compile(r"root_revision=\d+")
        for line in op.splitlines():
            rv += regex6.sub("root_revision=XX", regex5.sub("S secs per", regex4.sub("F files/sec", regex3.sub("N ns", regex2.sub("M ms", regex.sub("", line)))))) + "\n"
        return rv.replace("N ns", "M ms")

        pass

    def end_process_one(self):
        self.end(self.process_one, self.test_sync_dir_one)

    def end_process_two(self):
        self.end(self.process_two, self.test_sync_dir_two)

    def end_process_one_and_two(self):
        self.end_process_one()
        self.end_process_two()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Subsyncit Integration Tests')
    parser.add_argument('--test', dest='test_name', default="all", help="Test name if just one test")
    parser.add_argument('--big', dest='size_of_big_test_file', default="512", help="MB for big file")
    parser.add_argument('--killc', dest='kill_container_at_end', action='store_true', help="Kill container at end?")
    parser.set_defaults(kill_container_at_end=False)

    args = parser.parse_args(sys.argv[1:])

    test_loader = unittest.TestLoader()
    test_names = test_loader.getTestCaseNames(IntegrationTestsOfSyncOperations)
    suite = unittest.TestSuite()
    if args.test_name == "all":
        for tname in test_names:
            suite.addTest(IntegrationTestsOfSyncOperations(tname, args.size_of_big_test_file, args.kill_container_at_end))
    else:
        suite.addTest(IntegrationTestsOfSyncOperations(args.test_name, args.size_of_big_test_file, args.kill_container_at_end))

    result = unittest.TextTestRunner().run(suite)
    sys.exit(not result.wasSuccessful())
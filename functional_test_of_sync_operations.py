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

import fileinput
import getpass
import threading
import time
import unittest
from decorator import decorator
import os

import glob2
import requests
import sh
import pprint
from tinydb import TinyDB, Query

import subsyncit
from base_sync_test import BaseSyncTest
from recreate_svn_repo import make_or_wipe_server_side_subversion_repo


class FunctionalTestOfSyncOperations(BaseSyncTest):

    i = 0
    testSyncDir1 = ""
    testSyncDir2 = ""
    p1 = None
    p2 = None

    def __init__(self, testname, svnrepo, user, svnrepo_root, size, pword):
        super(FunctionalTestOfSyncOperations, self).__init__(testname)
        BaseSyncTest.svn_repo = svnrepo
        BaseSyncTest.user = user
        BaseSyncTest.passwd = pword
        BaseSyncTest.size = size
        BaseSyncTest.output = ""
        BaseSyncTest.svnrepo_root = svnrepo_root


    @classmethod
    def setUpClass(cls):
        sh.rm("-rf", str(sh.pwd()).strip('\n') + "/functionalTests/")

    def setUp(self):

        FunctionalTestOfSyncOperations.i += 1

        FunctionalTestOfSyncOperations.rel_dir_1 = "functionalTests/1_" + str(FunctionalTestOfSyncOperations.i) + "/"
        FunctionalTestOfSyncOperations.testSyncDir1 = str(sh.pwd()).strip('\n') + FunctionalTestOfSyncOperations.rel_dir_1
        self.reset_test_dir(FunctionalTestOfSyncOperations.testSyncDir1)
        FunctionalTestOfSyncOperations.rel_dir_2 = "functionalTests/2_" + str(FunctionalTestOfSyncOperations.i) + "/"
        FunctionalTestOfSyncOperations.testSyncDir2 = str(sh.pwd()).strip('\n') + FunctionalTestOfSyncOperations.rel_dir_2
        self.reset_test_dir(FunctionalTestOfSyncOperations.testSyncDir2)

        make_or_wipe_server_side_subversion_repo(svnrepo_root, "functionalTests", True, True, True)

    def teardown(self):
        self.end(FunctionalTestOfSyncOperations.p1, FunctionalTestOfSyncOperations.testSyncDir1)
        self.end(FunctionalTestOfSyncOperations.p2, FunctionalTestOfSyncOperations.testSyncDir2)

    def end(self, p, dir):
        if p is not None:
            self.signal_stop_of_subsyncIt(dir)

    @decorator
    def timedtest(f, *args, **kwargs):

        t1 = time.time()
        out = f(*args, **kwargs)
        t2 = time.time()
        dt = str((t2 - t1) * 1.00)
        dtout = dt[:(dt.find(".") + 4)]
        print "----------------------------------------------------------"
        print 'Test {0} finished in {1}s using {2}'.format(getattr(f, "__name__", "<unnamed>"), dtout, FunctionalTestOfSyncOperations.testSyncDir1)
        print "=========================================================="

    @timedtest
    def test_a_single_file_syncs(self):

        p1, p2 = self.start_two_subsyncits("functionalTests/")
        try:
            op1 = FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt"
            with open(op1, "w") as text_file:
                text_file.write("Hello")
            op2 = FunctionalTestOfSyncOperations.testSyncDir2 + "output.txt"
            self.wait_for_file_to_appear(op2)
            contents = open(op2).read()
            self.assertEqual(contents, "Hello")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)
            self.end(p2, FunctionalTestOfSyncOperations.testSyncDir2)


    # def dtest_a_changed_file_syncs_back2(self):
    #     self.test_a_changed_file_syncs_back()
    #
    # def dtest_a_changed_file_syncs_back3(self):
    #     self.test_a_changed_file_syncs_back()

    @timedtest
    def test_a_changed_file_syncs_back(self):

        p1, p2 = self.start_two_subsyncits("functionalTests/")
        try:
            with open(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "w") as text_file:
                text_file.write("Hello")
            op2 = FunctionalTestOfSyncOperations.testSyncDir2 + "output.txt"
            self.wait_for_file_to_appear(op2)
            with open(op2, "w") as text_file:
                text_file.write("Hello to you too")
            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "Hello to you too")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)
            self.end(p2, FunctionalTestOfSyncOperations.testSyncDir2)

    @timedtest
    def test_a_deleted_file_syncs_down(self):

        self.expect201(requests.request('MKCOL', self.svn_repo + self.rel_dir_1[:-1], auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.put(self.svn_repo + self.rel_dir_1 + "output.txt", auth=(self.user, self.passwd), data="Hello",
                     verify=False))

        p1 = self.start_subsyncit(self.svn_repo + self.rel_dir_1, FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            self.wait_for_file_to_appear(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")

            requests.delete(self.svn_repo + self.rel_dir_1 + "output.txt", auth=(self.user, self.passwd), verify=False)
            self.wait_for_file_to_disappear(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)

    @timedtest
    def test_a_deleted_file_can_have_its_parent_dir_deleted_too(self):

        self.expect201(requests.request('MKCOL', self.svn_repo + self.rel_dir_1,
                                        auth=(self.user, self.passwd),
                                        verify=False))

        self.expect201(requests.request('MKCOL',
                                        self.svn_repo + self.rel_dir_1 + "fred/",
                                        auth=(self.user, self.passwd),
                                        verify=False))

        self.expect201(requests.put(self.svn_repo + self.rel_dir_1 + "fred/output.txt",
                     auth=(self.user, self.passwd), data="Hello",
                     verify=False))

        p1 = self.start_subsyncit(self.svn_repo + self.rel_dir_1, FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            output_txt_ = FunctionalTestOfSyncOperations.testSyncDir1 + "fred/output.txt"
            self.wait_for_file_to_appear(output_txt_)
            requests.delete(self.svn_repo + self.rel_dir_1 + "fred/output.txt",
                            auth=(self.user, self.passwd), verify=False)
            self.wait_for_file_to_disappear(output_txt_)
            self.wait_for_file_to_disappear(FunctionalTestOfSyncOperations.testSyncDir1 + "fred")

        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_a_deleted_file_syncs_up(self):

        self.expect201(requests.request('MKCOL', self.svn_repo + self.rel_dir_1[:-1], auth=(self.user, self.passwd), verify=False))
        self.expect201(requests.put(self.svn_repo + self.rel_dir_1 + "output.txt", auth=(self.user, self.passwd), data="Hello",
                     verify=False))

        p1 = self.start_subsyncit(self.svn_repo + self.rel_dir_1, FunctionalTestOfSyncOperations.testSyncDir1)

        try:
            self.wait_for_file_to_appear(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")

            time.sleep(5)
            # print "rmv"
            # os.remove(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")
            # time.sleep(5)
            # print "wait"
            #
            # self.wait_for_file_to_disappear(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")
            #
            # self.assertEquals(
            #     requests.get(self.svn_repo + self.rel_dir_1 + "output.txt", auth=(self.user, self.passwd), verify=False).status_code, 404)
            #
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_a_deleted_file_syncs_back(self):

        p1, p2 = self.start_two_subsyncits("functionalTests/")
        try:
            with open(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "w") as text_file:
                text_file.write("Hello")
            op2 = FunctionalTestOfSyncOperations.testSyncDir2 + "output.txt"
            self.wait_for_file_to_appear(op2)
            os.remove(op2)
            self.wait_for_file_to_disappear(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt")
            print  FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt has disappeared as expected"
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)
            self.end(p2, FunctionalTestOfSyncOperations.testSyncDir2)

    @timedtest
    def test_a_file_changed_while_sync_agent_offline_still_sync_syncs_later(self):

        #TODO
        self.expect201(requests.put(self.svn_repo + "functionalTests/output.txt", auth=(self.user, self.passwd), data="Hello", verify=False))
        p1, p2 = self.start_two_subsyncits("functionalTests/")

        try:
            op1 = FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt"
            op2 = FunctionalTestOfSyncOperations.testSyncDir2 + "output.txt"
            self.wait_for_file_to_appear(op1)
            self.wait_for_file_to_appear(op2)
            self.signal_stop_of_subsyncIt(FunctionalTestOfSyncOperations.testSyncDir2)
            p2.wait()
            with open(op2, "w") as text_file:
                text_file.write("Hello to you too")
            p2 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir2)
            self.wait_for_file_contents_to_contain(op1, "Hello to you too")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)
            self.end(p2, FunctionalTestOfSyncOperations.testSyncDir2)


    @timedtest
    def test_a_file_changed_while_sync_agent_offline_does_not_sync_sync_later_if_it_changed_on_the_server_too(self):

        self.expect201(requests.put(self.svn_repo + "functionalTests/output.txt", auth=(self.user, self.passwd), data="Hello", verify=False))

        p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "Hello")
            self.signal_stop_of_subsyncIt(FunctionalTestOfSyncOperations.testSyncDir1)
            p1.wait()

            self.expect204(requests.put(self.svn_repo + "functionalTests/output.txt", auth=(self.user, self.passwd), data="Hello changed on server", verify=False))

            with open(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "w") as text_file:
                text_file.write("Hello changed locally too")

            p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
            time.sleep(1)

            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "Hello changed on server")
            clash_file = glob2.glob(FunctionalTestOfSyncOperations.testSyncDir1 + "*.clash_*")[0]
            self.wait_for_file_contents_to_contain(clash_file, "Hello changed locally too")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)

    @timedtest
    def test_cant_sync_against_non_svn_dav_site(self):

        p1 = self.start_subsyncit("https://example.com/", FunctionalTestOfSyncOperations.testSyncDir1, passwd="dontLeakRealPasswordToExampleDotCom")
        try:
            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + ".subsyncit.err", "PROPFIND status: 405 for: https://example.com/ user: paul")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_cant_access_svn_dav_site_with_incorrect_password(self):

        p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1, passwd="sdfsdfget3qgwegsdgsdgsf")
        try:
            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + ".subsyncit.err", "PROPFIND status: 401 for: " + self.svn_repo + "functionalTests/" + " user: " + self.user)
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_cant_sync_against_down_site(self):

        p1 = self.start_subsyncit("https://localhost:34456/", FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            time.sleep(2)
            self.wait_for_file_contents_to_contain(FunctionalTestOfSyncOperations.testSyncDir1 + ".subsyncit.err", " Failed to establish a new connection")
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_an_excluded_suffix_is_not_pushed_up(self):

        self.expect201(requests.put(self.svn_repo + "functionalTests/.subsyncit-excluded-suffixes", auth=(self.user, self.passwd), data=".bak\n", verify=False))
        p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            time.sleep(2)
            with open(FunctionalTestOfSyncOperations.testSyncDir1 + "output.bak", "w") as text_file:
                text_file.write("Hello")
            with open(FunctionalTestOfSyncOperations.testSyncDir1 + "output.txt", "w") as text_file:
                text_file.write("Hello")
            time.sleep(10)
            self.assertEquals(
                requests.get(self.svn_repo + "functionalTests/output.bak", auth=(self.user, self.passwd), verify=False).status_code, 404)
            self.assertEquals(
                requests.get(self.svn_repo + "functionalTests/output.txt", auth=(self.user, self.passwd), verify=False).status_code, 200)
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


    @timedtest
    def test_a_partially_downloaded_big_file_recovers(self):

        filename = str(sh.pwd()).strip('\n') + "/testBigRandomFile"
        start = time.time()
        self.make_a_1gig_random_file(filename, start, self.size)

        sz = os.stat(filename).st_size
        self.upload_file(filename, self.svn_repo + "functionalTests/testBigRandomFile")

        self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

        start = time.time()
        p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
        try:
            print "Started Subsyncit, and waiting for " + str(self.size) + "MB random file to be ... "
            self.wait_for_file_contents_to_be_sized_above(FunctionalTestOfSyncOperations.testSyncDir1 + "testBigRandomFile", sz)
            print " ... secs: " + str(round(time.time() - start, 1))

            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            self.signal_stop_of_subsyncIt(FunctionalTestOfSyncOperations.testSyncDir1)
            p1.wait()

            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            self.make_a_1gig_random_file(filename, start, self.size)

            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            self.upload_file(filename, self.svn_repo + "functionalTests/testBigRandomFile")

            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            start = time.time()

            print "start p1 again"
            p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
            self.wait_for_file_contents_to_be_sized_below(FunctionalTestOfSyncOperations.testSyncDir1 + "testBigRandomFile", (sz/2))
            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)
            self.wait_for_file_contents_to_be_sized_above(FunctionalTestOfSyncOperations.testSyncDir1 + "testBigRandomFile", (sz/2))
            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)
            p1.kill()
            print "Killed after secs: " + str(round(time.time() - start, 1))
            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            time.sleep(5)
            aborted_get_size = os.stat(FunctionalTestOfSyncOperations.testSyncDir1 + "testBigRandomFile").st_size

            print "Aborted size: " + str(aborted_get_size)

            self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

            p1 = self.start_subsyncit(self.svn_repo + "functionalTests/", FunctionalTestOfSyncOperations.testSyncDir1)
            self.wait_for_file_contents_to_be_sized_above(FunctionalTestOfSyncOperations.testSyncDir1 + "testBigRandomFile", sz)
        finally:
            self.end(p1, FunctionalTestOfSyncOperations.testSyncDir1)


        self.list_files(FunctionalTestOfSyncOperations.testSyncDir1)

        clash_file = glob2.glob(FunctionalTestOfSyncOperations.testSyncDir1 + "*.clash_*")[0]
        self.assertEquals(os.stat(clash_file).st_size, aborted_get_size)

    def make_a_1gig_random_file(self, filename, start, size):
        print "Making " + size + "MB random file ... "
        sh.bash("./make_a_so_big_file.sh", filename, size)
        print " ... secs: " + str(round(time.time() - start, 1))

    def list_files(self, root):
        glob = glob2.glob(root + "**")
        print "List of files in " + root + "folder:"
        if len(glob) == 0:
            print "  no files"
        for s in glob:
            print "  " + (str(s))

    def expect201(self, commandOutput):
        self.assertEquals("<Response [201]>", str(commandOutput))

    def expect204(self, commandOutput):
        self.assertEquals("<Response [204]>", str(commandOutput))


if __name__ == '__main__':
    import sys

    test_name = sys.argv[1]

    svnrepo = sys.argv[2]
    user = sys.argv[3]
    pword = getpass.getpass(prompt="Subverison password for " + user + ": ")

    svnrepo_root = sys.argv[4]
    size = sys.argv[5]

    test_loader = unittest.TestLoader()
    test_names = test_loader.getTestCaseNames(FunctionalTestOfSyncOperations)

    suite = unittest.TestSuite()
    if test_name == "ALL":
        for tname in test_names:
            suite.addTest(FunctionalTestOfSyncOperations(tname, svnrepo, user, svnrepo_root, size, pword))
    else:
        suite.addTest(FunctionalTestOfSyncOperations(test_name, svnrepo, user, svnrepo_root, size, pword))

    result = unittest.TextTestRunner().run(suite)
    sys.exit(not result.wasSuccessful())
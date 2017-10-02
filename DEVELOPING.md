Python2 is required, as well as some `pip2` installed modules:

```
pip2 install requests watchdog tinydb
```

Note:

1. Requests is Apache 2.0 licensed and maintained at http://python-requests.org
2. Watchdog is Apache 2.0 licensed and maintained at https://github.com/gorakhargosh/watchdog
2. TinyDB is MIT licensed and maintained at https://github.com/msiemens/tinydb

# Running the functional tests

Functional tests can only run these on the same server as the Subversion and Apache installs as it runs subversion admin operations, too.

You wll already have setup the Subversion+Apache server (as [described here](SERVER-SETUP)).

Python modules that are needed:

```
pip install sh glob2 requests
```

In the checkout directory, run:

```
sudo python functional_test_of_sync_operations.py all <URL> <user> <root-of-repo-in-filesystem> <size-of-big-file>

```

The URL is to the `svnParent` directory that the test will make a `unitTests` folder in. The user will be an account that can read
and write to that repo. You'll be prompted to enter the password for the subversion account. The sudo and subversion password pay be
different of course.

The tests, when running, delete and recreate the `functionalTests` folder on the subversion server, and implement the subversion `fsfs.conf` settings
changes, as detailed above. That is why they need to be run as `sudo`.

You can change `all` to the name of a single test method to run, if you want to focus on one test.
ourApp.config(['$translateProvider', function ($translateProvider) {
    $translateProvider.useSanitizeValueStrategy(null);
    $translateProvider.translations('en', {
        'TAGLINE': 'A multi-user <strong>file sync client</strong> for office use that is backed by Subversion, has permissioned access, keeps revision history, and pleases auditors.',
        'FOOTER': '&copy; 2016, 2017 <b>Paul Hammant</b>. All Rights Reserved. Subversion is an open source product from the <a href="https://apache.org">Apache Software Foundation</a>',
        'KNOW_MORE': 'MORE INFO?',
        'FEATURES': 'Features',
        'LIST': 'Basic file-sync features',
        'FILE_TYPES': 'Large and small file types',
        'ALL_SORTS': 'Excel Spreadsheets, Word documents, Powerpoint presentation, etc. Movies, music, pictures too',
        'DIRECT': 'Users can setup file sync for a subdirectory of a larger tree',
        'RW_PERMS': 'Multi-user with fine-grained read and write permissions',
        'RW_PERMS2': 'Permissions can be set at any place in the directory tree for users and groups',
        'SVN': 'Using Subversion means some features come by default, and some are now possible',
        'HIST': 'Terabytes of revision history is permanently and cheaply retained',
        'HIST2': 'Subversion does not have an upper limit of what can be stored in it',
        'POWER_USERS': 'Power users can still use traditional Svn workflows',
        'CLI_TOOLS': 'Like &apos;checkout&apos; and &apos;commit&apos;, as well as batch operations',
        'X_PLAT': 'Works on Windows, Mac and Linux',
        'EXCEPT': 'iOS and Android coming later',
        'PYTHON': 'Installation is a single Python script (and dependent packages)',
        'WORKFLOWS': '"Assign to co-worker" workflows',
        'WORKFLOWS2': '(coming soon)',
        'PI_CLOUD': 'Server on a Rasberry Pi or in the cloud',
        'PI_CLOUD2': 'Or many other types of deployment, including the Subversion server you already have in the org',
        'TRAY': 'Icon in the Tray (Mac: Menu bar)',
        'TRAY2': '(work in progress)',
        'NO_SVN': 'No client-side installation of Subversion at all means there is no &apos;working copy&apos; or .svn folders (or duplicated files)',
        'EXCLUDES': 'Files can be globally excluded from sync operations via their suffix',
        'EXCLUDES2': 'Some applications make a temp backup file while editing, like &apos;.bak&apos;',
        'TESTIMONIALS': 'Testimonials from those using it',
        'TESTIMONIAL_1': 'I have been using this for a year and love it. It is just what I have always wanted',
        'PH': 'Paul Hammant',
        'TESTIMONIAL_2': 'I hope he is going to stop talking about it soon',
        'PH_FRIEND': 'Paul&apos;s friend',
        'GH': 'is open source <a href="https://github.com/paul-hammant/subsyncit">on GitHub</a>, of course. ',
        'GH2': 'The installation instructions are <a href="https://github.com/paul-hammant/subsyncit/blob/master/CLIENT-SETUP.md">here</a>,<br> but installation is really only for IT' +
        ' people<br>right now while this is in BETA (sorry). Click on the octocat:'
    });

    $translateProvider.translations('es', {
        'TAGLINE': 'A multi-user <strong>file sync client</strong> for office use that is backed by Subversion, has permissioned access, keeps revision history, and pleases auditors.',
        'FOOTER': '&copy; 2016, 2017 <b>Paul Hammant</b>. All Rights Reserved. Subversion is an open source product from the <a href="https://apache.org">Apache Software Foundation</a>',
        'KNOW_MORE': 'MORE INFO?',
        'FEATURES': 'Features',
        'LIST': 'Basic file-sync features',
        'FILE_TYPES': 'Large and small file types',
        'ALL_SORTS': 'Excel Spreadsheets, Word documents, Powerpoint presentation, etc. Movies, music, pictures too',
        'DIRECT': 'Users can setup file sync for a subdirectory of a larger tree',
        'RW_PERMS': 'Multi-user with fine-grained read and write permissions',
        'RW_PERMS2': 'Permissions can be set at any place in the directory tree for users and groups',
        'SVN': 'Using Subversion means many features come by default',
        'HIST': 'Terabytes of revision history is permanently retained',
        'HIST2': 'Subversion does not have an upper limit of what can be stored in it',
        'POWER_USERS': 'Power users can still use traditional Svn workflows',
        'CLI_TOOLS': 'Like &apos;checkout&apos; and &apos;commit&apos;, as well as batch operations',
        'X_PLAT': 'Works on Windows, Mac and Linux',
        'EXCEPT': 'iOS and Android coming later',
        'PYTHON': 'Installation is a single Python script (and dependent packages)',
        'WORKFLOWS': '"Assign to co-worker" workflows',
        'WORKFLOWS2': '(coming soon)',
        'PI_CLOUD': 'Server on a Rasberry Pi or in the cloud',
        'PI_CLOUD2': 'Or many other types of deployment, including the Subversion server you already have in the org',
        'TRAY': 'Icon in the Tray (Mac: Menu bar)',
        'TRAY2': '(work in progress)',
        'NO_SVN': 'No client-side installation of Subversion at all means there is no &apos;working copy&apos; or .svn folders (or duplicated files)',
        'EXCLUDES': 'Files can be globally excluded from sync operations via their suffix',
        'EXCLUDES2': 'Some applications make a temp backup file while editing, like &apos;.bak&apos;',
        'TESTIMONIALS': 'Testimonials from those using it',
        'TESTIMONIAL_1': 'I have been using this for a year and love it. It is just what I have always wanted',
        'PH': 'Paul Hammant',
        'TESTIMONIAL_2': 'I hope he is going to stop talking about it soon',
        'PH_FRIEND': 'Paul&apos;s friend',
        'GH': 'is open source <a href="https://github.com/paul-hammant/subsyncit">on GitHub</a>, of course. ',
        'GH2': 'The installation instructions are <a href="https://github.com/paul-hammant/subsyncit/blob/master/CLIENT-SETUP.md">here</a>,<br> but installation is really only for IT' +
        ' people<br>right now while this is in BETA (sorry). Click on the octocat:'
    });

    var userLang = navigator.language || navigator.userLanguage;
    var defaultLanguage = userLang.split('-')[0];
    $translateProvider.preferredLanguage(defaultLanguage);
}]);

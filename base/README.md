This directory is a mount point for the installed Omarchy host during isolated tests.
The public snapshot does not redistribute the captured reference host. `dev/run`
binds `/usr/share/omarchy` (or `GOOEY_TEST_HOST`) here read-only inside Bubblewrap.

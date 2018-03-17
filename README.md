incron-recursive
================

What this script does:
  - Recursive monitoring with incron, for newly created subdirectories in a parent folder.
  - Adds new watches to incrontab for newly created folders.
  - Updates incrontab when files/folders are arbitrarily renamed/removed (including files/folders with spaces, parentheses, and brackets).
  - On IN_CREATE events (files are added), allows you to process these files with any arbitrary set of commands that you define.
  - Performs sanity checks and cleanup tasks to ensure that incrontab is maintained up-to-date and recovers from race conditions.

To use: make an intial update your incrontab entry to look like this: 

/path/to/monitored/dir IN_CREATE,IN_DELETE,IN_CLOSE_WRITE,IN_MOVED_TO /path/to/update.py $# $@ $%

Also ensure that you: 
  - Change the variables: scriptPath, curUser, updatePy
  - Update the processFile() commands to your liking. You can add addition logic here if you so desire.
  - chmod +x the script
  - Write access the watched folder.

Note: This script has been designed and will only work to monitor a +single+ root directory. It can be updated to handle more. Please share a new fork if you implement this!

Lastly, shouts out to Thang for the original version of this script! (https://github.com/nguyent/incron-recursive)
Brilliant work!

Cheers,
Joseph

#!/usr/bin/env python

# '''
# Any time a folder is added to the monitored parent directory, that folder needs
# to be monitored as well [recursive monitoring is not fully supported]. This
# script will add to incrontab when a new folder is added and process files that
# are added to these directories with any arbitrary set of commands that you define.
#
# This script will also handle arbitrary file/folder deletions & renaming, at any 
# depth.
# '''

import os,sys,pwd,subprocess, time
from datetime import datetime

# CFG Variables
curTime = datetime.time(datetime.now()).isoformat()
curUser = 'root' # ensure this runs under the correct incrontab user
scriptPath = '/path/to/update.py' # the path to THIS script.
updatePy = '/path/to/monitored/dir IN_CREATE,IN_DELETE,IN_CLOSE_WRITE,IN_MOVED_TO %s $# $@ $%%' % scriptPath
logDir = '/var/log/incrond'
incrontemp = '/tmp/incrontemp'
os.setuid(pwd.getpwnam(curUser)[2])
event = sys.argv[-1]
changed = sys.argv[1].strip().replace(' ','\\ ').replace('(','\(').replace(')','\)').replace('[','\\[').replace(']','\\]')
if len(sys.argv) > 4:
    workingDir = '\\ '.join(sys.argv[2:-1]).replace('(','\(').replace(')','\)').replace('[','\\[').replace(']','\\]')  # spaces
else:
    workingDir = sys.argv[2].replace(' ','\\ ').replace('(','\(').replace(')','\)').replace('[','\\[').replace(']','\\]')  # no spaces
if not os.path.exists(logDir):
    os.makedirs(logDir)

def makeTemp():
    if not os.path.isfile(incrontemp):
        cmdList = ['/usr/bin/incrontab -l > %s' % incrontemp]
        runCmd(cmdList)

# Log to a timestamped log file
def log(out, err, cmd):
    f = open(logDir + '/error.%s.log' % curTime , 'w')
    f.write('Could not update incrontab for %s' % changed + '\n')
    f.write('Failed output: \n')
    f.write('Attempted: %s \n' % cmd)
    f.write(out + '\n')
    f.write(err + '\n')
    f.write('Parameters: %s, %s, %s' % (changed,logDir,event) + '\n')
    f.close()

# Execute a list of shell commands, return the output as a list.
def runCmd(cmdList):
    outList = []
    for cmd in cmdList:
        o = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, err = o.communicate()
        outList += [out]
        if o.returncode != 0:
            log(out,err,cmd)
            sys.exit('Process failed..' )
    return outList

# Update Incrontab after modifying the current incrontab.
def updateIncron(cmdList):
    # Copy the current incrontab, & modify the copy accordingly.
    cmdList = ['/usr/bin/incrontab -l > %s' % incrontemp] + cmdList
    # Replace with the changed incrontemp.
    cmdList += ['/usr/bin/incrontab %s' % incrontemp]
    runCmd(cmdList)

def cleanIncron():
    cmds = ['/usr/bin/incrontab -l']
    incrontab = runCmd(cmds)[0]
    for x in incrontab.split('\n')[:-1]:
	tempDir = x.split(' IN_CREATE,')[0]
        if not os.path.exists(tempDir.replace('\\ ', ' ')): 
	    deletions = tempDir.replace('\\','\\\\').replace('/','\\/')
	    cmds = ["sed -i '/%s\//d' %s" % (deletions, incrontemp)]
            cmds += ["sed -i '/%s\\ /d' %s" % (deletions, incrontemp)]
    updateIncron(cmds)
	
# Process an uploaded file.
def processFile():
    # full path to the file..
    in_file = workingDir + '/' + changed
    # Pop off the extension.
    out_file = '.'.join(changed.split('.')[:-1])
    # Fix ACL
    cmds = ["setfacl -Rm m:rwx %s*" % (in_file.split('.')[0])]
    # Do anything else you want
    #cmds += ["HandBrakeCLI -i %s -o %s --preset=\"iPad\"" % ( in_file, out_file + '_ipad.mov' )]
    runCmd(cmds)

# Fix duplicate and missing incrontab entries
def removeDupsMissing():
    seen = set()
    cmds = ['/usr/bin/incrontab -l']
    incrontab = runCmd(cmds)[0]
    values = incrontab.split('\n')
    f = open(incrontemp, "w")
    for value in values:
	watchedDir = value.split(' IN_CREATE,')[0].replace('\\','')
        if os.path.exists(watchedDir) and value not in seen:
            f.write(value+'\n')
            seen.add(value)
    f.close()
    cmdList = ['/usr/bin/incrontab %s' % incrontemp]
    runCmd(cmdList)

# Fix race conditions
def sanityCheck():
    cmds = ['/usr/bin/incrontab -l']
    incrontab = runCmd(cmds)[0]
    trigger = incrontab.split('\n')[0]
    # Replace trigger statement (update.py command) if this goes missing
    if trigger != updatePy:
	cmds = ["echo >> %s" % (incrontemp)]
	cmds += ["sed -i '1s/^/%s\\n/' %s" % (updatePy.replace('\\','\\\\').replace('/','\\/'), incrontemp)]
	cmds += ["sed -i '$ d' %s" % (incrontemp)]
        cmds += ['/usr/bin/incrontab %s' % incrontemp]
        runCmd(cmds)

def main():

    # A Sub-Directory is added.
    if 'IN_CREATE,IN_ISDIR' in event:
        cmds = ["echo '%s IN_CREATE,IN_DELETE,IN_CLOSE_WRITE,IN_MOVED_TO %s $# $@ $%%' >> %s" % (workingDir+'/'+changed, scriptPath, incrontemp)]
        # update incrontab to add/remove watches on the changed Directory
        updateIncron(cmds)

    # A Sub-Directory is deleted.
    elif 'IN_DELETE,IN_ISDIR' in event:
        deletions = (workingDir+'/'+changed).replace('\\','\\\\').replace('/','\\/')
        # First we remove the exact entry. Then we remove instances of foo/test/ to remove any subdirs.
        cmds = ["sed -i '/%s\//d' %s" % (deletions, incrontemp)]
        cmds += ["sed -i '/%s\\ /d' %s" % (deletions, incrontemp)]
        updateIncron(cmds)
        sanityCheck()

    # A File is added.
    elif 'IN_CREATE' in event and incrontemp not in changed:
        ext = changed.split('.')[-1]
        processFile()

    # A directory was renamed.
    elif 'IN_MOVED_TO,IN_ISDIR' in event:
        # Find the original name of the directory.
        # Compare with the directories in incrontab
        cmds = ['/usr/bin/incrontab -l']
        incrontab = runCmd(cmds)[0]
        oldName = ''
        
        for x in incrontab.split('\n')[:-1]:
            tempDir = x.split(' IN_CREATE,')[0]
            # Ensure the basepath matches, and then check if it exists.
            # If it doesn't, we can assume that it was the renamed directory.
            # This does introduce a race condition, if a folder is deleted
            # while this script is running for a MOVED_TO event.
            # This race condition should be very rare.
            # I am not a doctor. Use at your own risk.

            if workingDir in tempDir and not os.path.exists(tempDir.replace('\\ ', ' ')):
                oldName = tempDir
                break

        # Now we need to pass this to sed, and {forward|back}slashes need to be
        # escaped.
        # Python needs backslashes escaped, and sed is weird about backslashes.
        # So I'm pretty sure this is the right amount of backslashes.

        oldName = oldName.replace('\\','\\\\').replace('/','\\/')
        newName = (workingDir+'/'+changed).replace('\\','\\\\').replace('/','\\/')
	if oldName:
	    cmds = ["sed -i 's/%s /%s /g' %s" % (oldName,newName,incrontemp)]
            updateIncron(cmds)
	else:
	    log("Attempting to update directory.", "Failed: no oldName match!", newName)
	    cmds = ["echo '%s IN_CREATE,IN_DELETE,IN_CLOSE_WRITE,IN_MOVED_TO %s $# $@ $%%' >> %s" % (workingDir+'/'+changed, scriptPath, incrontemp)]
	    updateIncron(cmds)
	    cleanIncron()
	sanityCheck()

if __name__ == "__main__":
    try:
	makeTemp()
    	main()
        removeDupsMissing()
    except Exception as e:
	log("Main block","Main block general exception: ", e)

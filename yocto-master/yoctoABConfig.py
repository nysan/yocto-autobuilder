################################################################################
# Yocto Build Server Developer Configuration
################################################################################
# Elizabeth Flanagan <elizabeth.flanagan@intel.com>
# TODO
# - make bspworkdir modify bblayers
# - CI flag
# - release flag
# - meta-bsp target
################################################################################
# Copyright (C) 2011 Intel Corp.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import copy, random, os, datetime 
from time import strftime
from email.Utils import formatdate
from twisted.python import log
from buildbot.changes.pb import PBChangeSource
from buildbot.process import factory
from buildbot.process.properties import WithProperties
from buildbot.process.buildstep import BuildStep, LoggingBuildStep, LoggedRemoteCommand, RemoteShellCommand
from buildbot.scheduler import Triggerable
from buildbot.scheduler import Scheduler
from buildbot.scheduler import Periodic
from buildbot.scheduler import Nightly
from buildbot.schedulers import triggerable
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.steps.trigger import Trigger
from buildbot.steps import shell
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source import Git

yocto_projname = "Yocto"
yocto_projurl = "http://yoctoproject.org/"
yocto_sources = []

yocto_sources.append(PBChangeSource())
yocto_sched = []
yocto_builders = []
defaultenv = {}
layerid = 0
SOURCE_DL_DIR = os.environ.get("SOURCE_DL_DIR")
defaultenv['DL_DIR'] = SOURCE_DL_DIR
SOURCE_SSTATE_DIR = os.environ.get("SOURCE_SSTATE_DIR")
defaultenv['SSTATE_DIR'] = SOURCE_SSTATE_DIR
CLEAN_SOURCE_DIR = os.environ.get("CLEAN_SOURCE_DIR")
PUBLISH_BUILDS = os.environ.get("PUBLISH_BUILDS")
PUBLISH_SOURCE_MIRROR = os.environ.get("PUBLISH_SOURCE_MIRROR")
PUBLISH_SSTATE = os.environ.get("PUBLISH_SSTATE")
BUILD_PUBLISH_DIR = os.environ.get("BUILD_PUBLISH_DIR")
SSTATE_PUBLISH_DIR = os.environ.get("SSTATE_PUBLISH_DIR")
SOURCE_PUBLISH_DIR = os.environ.get("SOURCE_PUBLISH_DIR")
defaultenv['BUILDSTRING'] = ""
defaultenv['DEST'] = ""

class createBBLayersConf(LoggingBuildStep):
    renderables = [ 'workdir', 'btarget', 'bsplayer' ]
    
    def __init__(self, workdir=None, btarget=None, bsplayer=False, **kwargs):
        LoggingBuildStep.__init__(self, **kwargs)
        self.workdir = workdir
        self.btarget = btarget
        self.bsplayer = bsplayer
        self.description = ["Setting", "bblayers.conf"]
        self.addFactoryArguments(workdir=workdir, btarget=btarget, bsplayer=bsplayer)

    def describe(self, done=False):
        return self.description

    def setStepStatus(self, step_status):
        LoggingBuildStep.setStepStatus(self, step_status)

    def setDefaultWorkdir(self, workdir):
        self.workdir = self.workdir or workdir

    def start(self):
        BBLAYER = self.workdir + "/build/build/conf/bblayers.conf"
        try:
            os.remove(BBLAYER)        
        except:
            pass
        fout = open(BBLAYER, "wb")            
        fout.write('LCONF_VERSION = "4" \n')
        fout.write('BBFILES ?="" \n')
        fout.write('BBLAYERS = " \ \n')
        fout.write(self.workdir + '/build/meta \ \n')
        fout.write(self.workdir + '/build/meta-yocto \ \n')
        if self.bsplayer is True:
            fout.write(self.workdir + '/build/yocto/meta-intel/meta-' + self.btarget + ' \ \n')
        fout.write(self.workdir + '/build/meta-qt3 " \n')
        fout.close()            
        return self.finished(SUCCESS)

class createAutoConf(LoggingBuildStep):
    renderables = [ 'workdir', 'btarget' ]
    
    def __init__(self, workdir=None, btarget=None, **kwargs):
        LoggingBuildStep.__init__(self, **kwargs)
        self.workdir = workdir
        self.btarget = btarget
        self.description = ["Setting", "auto.conf"]
        self.addFactoryArguments(workdir=workdir, btarget=btarget)

    def describe(self, done=False):
        return self.description

    def setStepStatus(self, step_status):
        LoggingBuildStep.setStepStatus(self, step_status)

    def setDefaultWorkdir(self, workdir):
        self.workdir = self.workdir or workdir

    def start(self):
        AUTOCONF = self.workdir + "/build/build/conf/auto.conf"
        log.msg(self.workdir)
        try:
            os.remove(AUTOCONF)        
        except:
            pass
        fout = open(AUTOCONF, "wb")        
        fout.write('PACKAGE_CLASSES = "package_rpm package_deb package_ipk"\n') 
        fout.write('BB_NUMBER_THREADS = "10"\n')
        fout.write('PARALLEL_MAKE = "-j 16"\n')
        fout.write('SDKMACHINE ?= "i586"\n')
        fout.write('DL_DIR = ' + defaultenv['DL_DIR']+"\n")
        fout.write('SSTATE_DIR ?= ' + defaultenv['SSTATE_DIR']+"\n")
        #fout.write('INHERIT += "rm_work"\n')
        fout.write('MACHINE = ' + self.btarget + "\n")
        #fout.write('MIRRORS = ""\n')
        fout.write('PREMIRRORS = ""\n')
        if defaultenv['ENABLE_SWABBER'] == 'true':
            fout.write('USER_CLASSES += "image-prelink image-swab"\n')
        if PUBLISH_BUILDS == "True":
            fout.write('BB_GENERATE_MIRROR_TARBALLS = "1"\n')           
        fout.close()
        return self.finished(SUCCESS)

def runBSPLayerPreamble(factory):
    makeCheckout(factory)
    factory.addStep(shell.SetProperty(workdir="build", 
                    command="git rev-parse HEAD", 
                    property="POKYHASH"))
    factory.addStep(ShellCommand, 
                    command="echo 'Checking out git://git.pokylinux.org/meta-intel.git'",
                    timeout=10)
    factory.addStep(Git(repourl="git://git.pokylinux.org/meta-intel.git", 
                    mode="clobber", workdir="build/yocto/meta-intel",
                    branch=WithProperties("BRANCHNAME"),
                    timeout=10000, retry=(5, 3)))
    factory.addStep(ShellCommand(doStepIf=doEMGDTest, 
                    description="Copying EMGD", 
                    workdir="build", 
                    command="cp -R ~/EMGD_1.6/* yocto/meta-intel/meta-crownbay/recipes-graphics/xorg-xserver/",
                    timeout=60))

def runImage(factory, machine, image, bsplayer):
    factory.addStep(ShellCommand, description=["Setting up build"],
                    command=["yocto-autobuild-preamble"],
                    env=copy.copy(defaultenv),
                    timeout=14400)                            
    factory.addStep(createAutoConf(workdir=WithProperties("%s", "workdir"), btarget=machine))
    factory.addStep(createBBLayersConf(workdir=WithProperties("%s", "workdir"), btarget=machine, bsplayer=bsplayer))
    defaultenv['MACHINE'] = machine
    factory.addStep(ShellCommand, description=["Building", machine, image],
                    command=["yocto-autobuild", image, "-k"],
                    env=copy.copy(defaultenv),
                    timeout=14400)


def runSanityTest(factory, machine, image):
    defaultenv['MACHINE'] = machine
    factory.addStep(ShellCommand, description=["Running sanity test for", 
                    machine, image], 
                    command=["yocto-autobuild-sanitytest", image], 
                    env=copy.copy(defaultenv), 
                    timeout=2400)

def runPreamble(factory):
    factory.addStep(ShellCommand, description=["Setting up build"],
                    command=["yocto-autobuild-preamble"],
                    env=copy.copy(defaultenv),
                    timeout=14400)      
    defaultenv['DEST'] = os.path.join(BUILD_PUBLISH_DIR.strip('"').strip("'"), str(defaultenv['ABTARGET']))
    REV = 1
    DEST_DATE=datetime.datetime.now().strftime("%Y%m%d")
    while os.path.exists(os.path.join(defaultenv['DEST'], DEST_DATE + "-" + str(REV))):
        REV = REV + 1
    factory.addStep(ShellCommand, description="Setting deploy dir", 
                    command="echo " + 
                    DEST_DATE + "-" + str(REV) + 
                    " deploy-dir",
                    workdir="build", 
                    timeout=600)
    defaultenv['DEST']=os.path.join(os.path.join(defaultenv['DEST'], DEST_DATE + "-" + str(REV)))
    factory.addStep(ShellCommand, description="Creating output dir", 
                    command=["mkdir", "-p", defaultenv['DEST']], 
                    timeout=60)
    factory.addStep(ShellCommand, description="Marking deploy-dir", 
                    command=["echo", DEST_DATE + "-" + str(REV), ">>", "deploy-dir"], 
                    timeout=60)

def getRepo(step):
    gittype = step.getProperty("repository")
    if gittype == "git://git.yoctoproject.org/poky-contrib":
        step.setProperty("branch", "stage/master_under_test")
    elif gittype == "git://git.yoctoproject.org/poky":
         try:
             branch = step.getProperty("branch")
         except: 
             step.setProperty("branch", "master")
             pass
    else:
        return False
    return True

def getTag(step):
    try:
        tag = step.getProperty("pokytag")
    except:
        step.setProperty("pokytag", "HEAD")
        pass
    return True


def makeCheckout(factory):
    factory.addStep(ShellCommand(doStepIf=getRepo,
                    description="Getting the requested git repo",
                    command='echo "Getting the requested git repo"'))
    factory.addStep(ShellCommand(
                    description=["Building", WithProperties("%s", "branch"),  WithProperties("%s", "repository")],
                    command=["echo", WithProperties("%s", "branch"),  WithProperties("%s", "repository")]))
    factory.addStep(Git(
                    mode="clobber", 
                    branch=WithProperties("%s", "branch"),
                    timeout=10000, retry=(5, 3)))
    factory.addStep(ShellCommand(doStepIf=getTag, command=["git", "checkout",  WithProperties("%s", "pokytag")], timeout=1000))
    factory.addStep(ShellCommand(workdir="build", command=["git", "clone",  "git://git.pokylinux.org/meta-qt3.git"], timeout=1000))
    factory.addStep(shell.SetProperty(workdir="build/meta-qt3",
                    command="git rev-parse HEAD",
                    property="QTHASH"))
                    
def makeTarball(factory):
    factory.addStep(ShellCommand, description="Generating release tarball", 
                    command=["yocto-autobuild-generate-sources-tarball", "nightly", "1.0pre", 
                    WithProperties("%s", "branch")], timeout=120)
    if PUBLISH_BUILDS == "True":
        factory.addStep(ShellCommand, description="Copying release tarball", 
                        command=["yocto-autobuild-copy-images", "yocto-sources", 
                        "nightly",    BUILD_PUBLISH_DIR], 
                        timeout=60)

def makeLayerTarball(factory):
    factory.addStep(ShellCommand, description="Generating release tarball",
                    command=["yocto-autobuild-generate-sources-tarball", "nightly", "1.0pre",
                    WithProperties("%s", "layer0branch")], timeout=120)
    if PUBLISH_BUILDS == "True":
        factory.addStep(ShellCommand, description="Copying release tarball",
                        command=["yocto-autobuild-copy-images", "yocto-sources", "nightly", 
                        BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])], timeout=60)

def doEMGDTest(step):
    buildername = step.getProperty("buildername")
    if buildername == "crownbay":
        return True
    elif buildername == "crownbay-lsb":
        return True
    else:
        return False 

def setRandom(step):
    step.setProperty("FuzzArch", random.choice( ['qemux86', 
                                                 'qemux86-64', 
                                                 'qemuarm', 
                                                 'qemuppc', 
                                                 'qemumips'] ))
    step.setProperty("FuzzImage", random.choice( ['core-image-sato', 
                                                  'core-image-sato-dev', 
                                                  'core-image-sato-sdk', 
                                                  'core-image-minimal', 
                                                  'core-image-minimal-dev',
                                                  'core-image-lsb', 
                                                  'core-image-lsb-dev', 
                                                  'core-image-lsb-sdk', 
                                                  'core-image-lsb-qt3']))
    step.setProperty("FuzzSDK", random.choice( ['i686', 'x86-64'] ))
    defaultenv['MACHINE'] = step.getProperty("FuzzArch")
    imageType = step.getProperty("FuzzImage")
    defaultenv['SDKMACHINE'] = step.getProperty("FuzzSDK")
    if "lsb" in imageType:
        defaultenv['DISTRO'] = "poky-lsb"
    else:
        defaultenv['DISTRO'] = "poky"
    return True

def fuzzyBuild(factory):
    factory.addStep(ShellCommand(doStepIf=setRandom,
                    description="Setting to random build parameters",
                    command='echo "Setting to random build parameters"'))
    runPreamble(factory)
    factory.addStep(ShellCommand(doStepIf=setRandom,
                    description=["Building", WithProperties("%s", "FuzzImage"),  
                                 WithProperties("%s", "FuzzArch"), 
                                 WithProperties("%s", "FuzzSDK")],
                    command=["echo", WithProperties("%s", "FuzzImage"),  
                             WithProperties("%s", "FuzzArch"), 
                             WithProperties("%s", "FuzzSDK")]))                                    
    factory.addStep(createAutoConf(workdir=WithProperties("%s", "workdir"), btarget=WithProperties("%s", "FuzzArch")))
    factory.addStep(createBBLayersConf(workdir=WithProperties("%s", "workdir"), btarget=WithProperties("%s", "FuzzArch"), bsplayer=False))
    factory.addStep(ShellCommand, 
                    description=["Building", WithProperties("%s", "FuzzImage")],
                    command=["yocto-autobuild", 
                             WithProperties("%s", "FuzzImage"), "-k"],
                    env=copy.copy(defaultenv),
                    timeout=14400)

def getMetaParams(step):
    defaultenv['MACHINE'] = step.getProperty("machine")
    defaultenv['SDKMACHINE'] = step.getProperty("sdk")
    step.setProperty("MetaImage", step.getProperty("imagetype").replace("and", " "))
    return True

def metaBuild(factory):
    defaultenv['IMAGETYPES'] = ""
    defaultenv['SDKMACHINE'] = ""
    factory.addStep(ShellCommand(doStepIf=getMetaParams,
                    description="Getting to meta build parameters",
                    command='echo "Getting to meta build parameters"'))
    runPreamble(factory)
    factory.addStep(ShellCommand, description=["Setting up build"],
                    command=["yocto-autobuild-preamble"],
                    env=copy.copy(defaultenv),
                    timeout=14400)                                                 
    factory.addStep(createAutoConf(workdir=WithProperties("%s", "workdir"), btarget=WithProperties("%s", "machine")))
    factory.addStep(createBBLayersConf(workdir=WithProperties("%s", "workdir"), btarget=WithProperties("%s", "machine"), bsplayer=False))
    factory.addStep(ShellCommand, description=["Building", WithProperties("%s", "MetaImage")],
                    command=["yocto-autobuild", WithProperties("%s", "MetaImage"), "-k"],
                    env=copy.copy(defaultenv),
                    timeout=14400)

def nightlyQEMU(factory, machine, distrotype):
    if distrotype == "poky":
       defaultenv['DISTRO'] = "poky"
       runImage(factory, machine, 'core-image-sato core-image-sato-dev core-image-sato-sdk core-image-minimal core-image-minimal-dev', False)
       runSanityTest(factory, machine, 'core-image-sato')
       runSanityTest(factory, machine, 'core-image-minimal')
    elif distrotype == "poky-lsb":
       defaultenv['DISTRO'] = "poky-lsb"
       runImage(factory, machine, 'core-image-lsb core-image-lsb-dev core-image-lsb-sdk', False)
    defaultenv['DISTRO'] = 'poky'
    factory.addStep(ShellCommand, description="Copying " + machine + " build output", 
                    command="yocto-autobuild-copy-images " + 
                    machine + " nightly " +    BUILD_PUBLISH_DIR, 
                    timeout=600)

def nightlyBSP(factory, machine, distrotype):
    if distrotype == "poky":
        defaultenv['DISTRO'] = 'poky'
        runImage(factory, machine, 'core-image-sato core-image-sato-sdk core-image-minimal', False)
    elif distrotype == "poky-lsb":
        defaultenv['DISTRO'] = 'poky-lsb'
        runImage(factory, machine,  'core-image-lsb-sdk', False)
    defaultenv['DISTRO'] = 'poky'
    factory.addStep(ShellCommand, description="Copying " + machine + " build output", 
                    command="yocto-autobuild-copy-images " + 
                    machine + " nightly " +    BUILD_PUBLISH_DIR, 
                    timeout=600)
                    
def setBSPLayerRepo(step):
####################
# WIP web selectable layer support
####################
    defaultenv['BSP_REPO'] = step.getProperty("layer0repo")
    defaultenv['BSP_BRANCH'] = step.getProperty("layer0branch")
    defaultenv['BSP_WORKDIR'] = "build/" + step.getProperty("layer0workdir")
    defaultenv['BSP_REV'] = step.getProperty("layer0revision")
    return True

def runBSPLayerPostamble(factory):
    if PUBLISH_BUILDS == "True":
        factory.addStep(ShellCommand, description="Creating CURRENT link", 
                        command=["yocto-autobuild-generate-current-link", "nightly", 
                        BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET']), "current"], 
                        timeout=20)

def buildBSPLayer(factory, distrotype, btarget):
    if distrotype == "poky":
        defaultenv['DISTRO'] = 'poky'
        runImage(factory, btarget, 'core-image-sato-live core-image-sato-sdk-live core-image-minimal-live', True)
        if PUBLISH_BUILDS == "True":
            factory.addStep(ShellCommand, description="Copying " + 
                            str(defaultenv['ABTARGET']) + " build output", 
                            command=["yocto-autobuild-copy-images", 
                            defaultenv['BTARGET'], "nightly", 
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 
            makeLayerTarball(factory)
            factory.addStep(ShellCommand, description="Copying RPM feed output", 
                            command=["yocto-autobuild-copy-images", "rpm", "nightly", 
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 
            factory.addStep(ShellCommand, description="Copying IPK feed output",
                            command=["yocto-autobuild-copy-images", "ipk", "nightly",
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 
    elif distrotype == "poky-lsb":
        defaultenv['DISTRO'] = 'poky-lsb'
        runImage(factory, btarget, 'core-image-lsb-live core-image-lsb-sdk-live', True)
        if PUBLISH_BUILDS == "True":
            factory.addStep(ShellCommand, description="Copying " + str(defaultenv['ABTARGET']) + " build output", 
                            command=["yocto-autobuild-copy-images", defaultenv['BTARGET'], "nightly", 
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 
            factory.addStep(ShellCommand, description="Copying RPM feed output", 
                            command=["yocto-autobuild-copy-images", "rpm-lsb", "nightly", 
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 
            factory.addStep(ShellCommand, description="Copying IPK feed output",
                            command=["yocto-autobuild-copy-images", "ipk-lsb", "nightly",
                            BUILD_PUBLISH_DIR + str(defaultenv['ABTARGET'])]) 

################################################################################
#
# BuildSets Section
# These are predefined buildsets used on the yocto-project production autobuilder
#
################################################################################
################################################################################
# Yocto Master Fuzzy Target
################################################################################
f2 = factory.BuildFactory()
fuzzsched = Triggerable(name="fuzzy-master",
        builderNames=["b2"])
defaultenv['REVISION'] = "HEAD"
defaultenv['ABTARGET'] = 'fuzzy-master'
makeCheckout(f2)
fuzzyBuild(f2)
f2.addStep(Trigger(schedulerNames=['fuzzymastersched'],
                           waitForFinish=False))
b2 = {'name': "fuzzy-master",
      'slavenames': ["builder1"],
      'builddir': "fuzzy-master",
      'factory': f2
     }
yocto_builders.append(b2)
yocto_sched.append(triggerable.Triggerable(name="fuzzymastersched", builderNames=["fuzzy-master"]))

################################################################################
# Yocto poky-contrib master-under-test Fuzzy Target
################################################################################
f3 = factory.BuildFactory()
fuzzsched = Triggerable(name="fuzzy-mut",
        builderNames=["b3"])
defaultenv['REVISION'] = "HEAD"
defaultenv['ABTARGET'] = 'fuzzy-mut'
makeCheckout(f3)
fuzzyBuild(f3)
f3.addStep(Trigger(schedulerNames=['fuzzymutsched'],
                           waitForFinish=False))
b3 = {'name': "fuzzy-mut",
      'slavenames': ["builder1"],
      'builddir': "fuzzy-mut",
      'factory': f3
     }
yocto_builders.append(b3)
yocto_sched.append(triggerable.Triggerable(name="fuzzymutsched", builderNames=["fuzzy-mut"]))

################################################################################
# Selectable Targets, for when a nightly fails one or two images
################################################################################
f4 = factory.BuildFactory()
defaultenv['REVISION'] = "HEAD"
defaultenv['ABTARGET'] = 'meta-target'
makeCheckout(f4)
metaBuild(f4)
b4 = {'name': "meta-target",
      'slavenames': ["builder1", "builder1", "builder1"],
      'builddir': "meta-target",
      'factory': f4
     }
yocto_builders.append(b4)

################################################################################
#
# Poky Toolchain Swabber Builder Example Target
#
# Build the toolchain and sdk and profile it with swabber.
# I've set this inactive, but it exists as an example
################################################################################

f22 = factory.BuildFactory()
makeCheckout(f22)
defaultenv['REVISION'] = "HEAD"
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'core-swabber-test'
f22.addStep(ShellCommand, description=["Setting", "SDKMACHINE=i686"], 
            command="echo 'Setting SDKMACHINE=i686'", timeout=10)
defaultenv['SDKMACHINE'] = 'i686'
f22.addStep(ShellCommand, description=["Setting", "ENABLE_SWABBER"], 
            command="echo 'Setting ENABLE_SWABBER'", timeout=10)
defaultenv['ENABLE_SWABBER'] = 'true'
runPreamble(f22)
defaultenv['SDKMACHINE'] = 'i686'
runImage(f22, 'qemux86-64', 'meta-toolchain-gmae', False)
f22.addStep(ShellCommand, description="Setting SDKMACHINE=x86_64", 
            command="echo 'Setting SDKMACHINE=x86_64'", timeout=10)
defaultenv['SDKMACHINE'] = 'x86_64'
runImage(f22, 'qemux86-64', 'meta-toolchain-gmae', False)
if PUBLISH_BUILDS == "True":
    swabberTimeStamp = strftime("%Y%m%d%H%M%S")
    swabberTarPath = BUILD_PUBLISH_DIR + "/swabber-logs/" + swabberTimeStamp + ".tar.bz2"
    f22.addStep(ShellCommand, description=["Compressing", "Swabber Logs"], 
                command="tar cjf " + swabberTarPath + " build/tmp/log", 
                timeout=10000)
b22 = {'name': "core-swabber-test",
      'slavename': "builder1",
      'builddir': "core-swabber-test",
      'factory': f22
     }

yocto_builders.append(b22)

#yocto_sched.append(Nightly(name="Poky Swabber Test", branch=None,
#                                 hour=05, minute=00,
#                                 builderNames=["core-swabber-test"])) 	


################################################################################
#
# Eclipse Plugin Builder
#
# This builds the eclipse plugin. This is a temporary area until this
# gets merged into the nightly & milestone builds
#
################################################################################

f61 = factory.BuildFactory()
f61.addStep(Git(repourl="git://git.pokylinux.org/eclipse-poky.git", mode="copy", 
            timeout=10000, retry=(5, 3)))
f61.addStep(ShellCommand, description=["Copying", "eclipse", "build", "tools"], 
            command="yocto-eclipse-plugin-copy-buildtools standalone", timeout=120)
f61.addStep(ShellCommand, description=["Building", "eclipse", "plugin"], 
            command="yocto-eclipse-plugin-build standalone", timeout=120)
if PUBLISH_BUILDS == "True":
    f61.addStep(ShellCommand, description="Copying eclipse plugin output", 
                command="yocto-autobuild-copy-images eclipse-plugin nightly " +    BUILD_PUBLISH_DIR, 
                timeout=60)
b61 = {'name': "eclipse-plugin",
      'slavename': "builder1",
      'builddir': "eclipse-plugin",
      'factory': f61,
      }
yocto_builders.append(b61)

################################################################################
#
# Nightly External Release Builder
#
################################################################################
f65 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-external'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
makeCheckout(f65)
runPreamble(f65)
nightlyQEMU(f65, 'qemux86', 'poky')
nightlyQEMU(f65, 'qemuarm', 'poky')
nightlyQEMU(f65, 'qemumips', 'poky')
nightlyQEMU(f65, 'qemuppc', 'poky')
nightlyBSP(f65, 'beagleboard', 'poky')
nightlyBSP(f65, 'mpc8315e-rdb', 'poky')
nightlyBSP(f65, 'routerstationpro', 'poky')
f65.addStep(ShellCommand, description="Moving non-lsb TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
nightlyQEMU(f65, 'qemux86', "poky-lsb")
nightlyQEMU(f65, 'qemuarm', "poky-lsb")
nightlyQEMU(f65, 'qemumips', "poky-lsb")
nightlyQEMU(f65, 'qemuppc', "poky-lsb")
nightlyBSP(f65, 'beagleboard', "poky-lsb")
nightlyBSP(f65, 'mpc8315e-rdb', "poky-lsb")
nightlyBSP(f65, 'routerstationpro', "poky-lsb")
runImage(f65, 'qemux86', 'package-index', False)
makeTarball(f65)

if PUBLISH_BUILDS == "True":
    f65.addStep(ShellCommand, description="Copying IPK feed output", 
                command="yocto-autobuild-copy-images ipk nightly " +    BUILD_PUBLISH_DIR, 
                timeout=1800)
    f65.addStep(ShellCommand, description="Copying RPM feed output", 
                command="yocto-autobuild-copy-images rpm nightly " +    BUILD_PUBLISH_DIR, 
                timeout=1800)
f65.addStep(ShellCommand, description="Cloning eclipse-poky git repo", 
            command="yocto-eclipse-plugin-clone-repo", timeout=300)
f65.addStep(ShellCommand, description="Copying eclipse build tools", 
            command="yocto-eclipse-plugin-copy-buildtools combo", timeout=120)
f65.addStep(ShellCommand, description="Building eclipse plugin", 
            command="yocto-eclipse-plugin-build combo master", timeout=120)

#if PUBLISH_BUILDS == "True":
#    f65.addStep(ShellCommand, description="Copying eclipse plugin output", 
#                command="yocto-autobuild-copy-images eclipse-plugin nightly " +    BUILD_PUBLISH_DIR, 
#                timeout=60)
#    f65.addStep(ShellCommand, description="Copying buildstatistics output", 
#                command="yocto-autobuild-copy-images buildstats nightly " +    BUILD_PUBLISH_DIR, 
#                timeout=600)
#    f65.addStep(ShellCommand, description="Creating CURRENT link", 
#                command="yocto-autobuild-generate-current-link nightly " +    BUILD_PUBLISH_DIR +"/ current", 
#               timeout=20)
                
if PUBLISH_SSTATE == "True":
    f65.addStep(ShellCommand, description="Syncing shared state cache to mirror", 
                command="yocto-update-shared-state-prebuilds", timeout=2400)
    f65.addStep(ShellCommand, description="Copying shared state cache", 
                command="yocto-autobuild-copy-images sstate nightly " +    BUILD_PUBLISH_DIR, 
                timeout=8400)

b65 = {'name': "nightly-external",
      'slavename': "builder1",
      'builddir': "nightly-external",
      'factory': f65,
      }
yocto_builders.append(b65)

#######################################################
#
# External toolcahin buildset
#
######################################################
f66 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-external-toolchain'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['REVISION'] = "HEAD"
makeCheckout(f66)
runPreamble(f66)                   
f66.addStep(createAutoConf(workdir=WithProperties("%s", "workdir"), btarget="qemux86"))
f66.addStep(createBBLayersConf(workdir=WithProperties("%s", "workdir"), btarget="qemux86", bsplayer=False))
f66.addStep(ShellCommand, description="Setting SDKMACHINE=i686", 
            command="echo 'Setting SDKMACHINE=i686'", timeout=10)
defaultenv['SDKMACHINE'] = 'i686'
runImage(f66, 'qemux86', 'meta-toolchain-gmae', False)
runImage(f66, 'qemuarm', 'meta-toolchain-gmae', False)
runImage(f66, 'qemumips', 'meta-toolchain-gmae', False)
runImage(f66, 'qemuppc', 'meta-toolchain-gmae', False)
defaultenv['SDKMACHINE'] = 'x86_64'
runImage(f66, 'qemux86', 'meta-toolchain-gmae', False)
runImage(f66, 'qemuarm', 'meta-toolchain-gmae', False)
runImage(f66, 'qemumips', 'meta-toolchain-gmae', False)
runImage(f66, 'qemuppc', 'meta-toolchain-gmae', False)
runImage(f66, 'qemux86', 'package-index', False)
if PUBLISH_BUILDS == "True":
    f66.addStep(ShellCommand, description="Copying toolchain-x86-64 build output", 
                command="yocto-autobuild-copy-images toolchain nightly " +    BUILD_PUBLISH_DIR , 
                timeout=600)
    f66.addStep(ShellCommand, description="Copying buildstatistics output", 
                command="yocto-autobuild-copy-images buildstats nightly " +    BUILD_PUBLISH_DIR , 
                timeout=600)
    f66.addStep(ShellCommand, description="Creating CURRENT link", 
                command="yocto-autobuild-generate-current-link nightly " +    BUILD_PUBLISH_DIR + "/ current", 
                timeout=20)
b66 = {'name': "nightly-external-toolchain",
      'slavename': "builder1",
      'builddir': "nightly-external-toolchain",
      'factory': f66,
      }
yocto_builders.append(b66)

################################################################################
#
#  Internal Release Builder
#
# This build performs some of the poky builds needed for a milestone release
# suitable for submission to QA. It is split up to allow the remaining builds
# to run in parallel on the other buildslave.
#
################################################################################
f70 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-internal'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['REVISION'] = "HEAD"
makeCheckout(f70)
runPreamble(f70)
nightlyQEMU(f70, 'qemux86', 'poky')
nightlyQEMU(f70, 'qemux86-64', 'poky')
nightlyBSP(f70, 'atom-pc', 'poky')
f70.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
nightlyQEMU(f70, 'qemux86', 'poky-lsb')
nightlyQEMU(f70, 'qemux86-64', 'poky-lsb')
nightlyBSP(f70, 'atom-pc', 'poky-lsb')
runImage(f70, 'qemux86', 'package-index', False)
makeTarball(f70)
if PUBLISH_BUILDS == "True":
    f70.addStep(ShellCommand, description="Copying toolchain-x86-64 build output", 
                command="yocto-autobuild-copy-images toolchain nightly " +    BUILD_PUBLISH_DIR , 
                timeout=600)
    f70.addStep(ShellCommand, description="Copying IPK feed output", 
                command="yocto-autobuild-copy-images ipk nightly " +    BUILD_PUBLISH_DIR , 
                timeout=1800)
    f70.addStep(ShellCommand, description="Copying RPM feed output", 
                command="yocto-autobuild-copy-images rpm nightly " +    BUILD_PUBLISH_DIR , 
                timeout=1800)
    f70.addStep(ShellCommand, description="Copying buildstatistics output", 
                command="yocto-autobuild-copy-images buildstats nightly " +    BUILD_PUBLISH_DIR , 
                timeout=1800)
if PUBLISH_SSTATE == "True":
    f70.addStep(ShellCommand, description="Syncing shared state cache to mirror", 
                command="yocto-update-shared-state-prebuilds", timeout=2400)
    f70.addStep(ShellCommand, description="Copying shared state cache", 
                command="yocto-autobuild-copy-images sstate nightly " +    BUILD_PUBLISH_DIR , 
                timeout=8400)
if PUBLISH_BUILDS == "True":
    f70.addStep(ShellCommand, description="Creating CURRENT link", 
                command="yocto-autobuild-generate-current-link nightly " +    BUILD_PUBLISH_DIR + "/ current", 
                timeout=20)
b70 = {'name': "nightly-internal",
      'slavename': "builder1",
      'builddir': "nightly-internal",
      'factory': f70,
      }
yocto_builders.append(b70)

#####################################################################
#
# Tunnel Creek Buildout
#
#####################################################################
f170 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'crownbay'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'crownbay'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f170)
runBSPLayerPreamble(f170)
buildBSPLayer(f170, "poky", defaultenv['BTARGET'])
f170.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f170, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f170)
b170 = {'name': "crownbay",
       'slavename': "builder1",
       'builddir': "crownbay",
       'factory': f170}
yocto_builders.append(b170)

#####################################################################
#
# Tunnel Creek Buildout
#
#####################################################################

f175 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'crownbay-noemgd'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'crownbay'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f175)
runBSPLayerPreamble(f175)
buildBSPLayer(f175, "poky", defaultenv['BTARGET'])
f175.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f175, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f175)
b175 = {'name': "crownbay-noemgd",
       'slavename': "builder1",
       'builddir': "crownbay-noemgd",
       'factory': f175}
yocto_builders.append(b175)

#####################################################################
#
# Emenlow Buildout
#
#####################################################################


f180 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'emenlow'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'emenlow'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f180)
runBSPLayerPreamble(f180)
buildBSPLayer(f180, "poky", defaultenv['BTARGET'])
f180.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f180, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f180)
b180 = {'name': "emenlow",
       'slavename': "builder1",
       'builddir': "emenlow",
       'factory': f180}
yocto_builders.append(b180)

#####################################################################
#
# n450 Buildout
#
#####################################################################


f190 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'n450'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'n450'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f190)
runBSPLayerPreamble(f190)
buildBSPLayer(f190, "poky", defaultenv['BTARGET'])
f190.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f190, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f190)
b190 = {'name': "n450",
       'slavename': "builder1",
       'builddir': "n450",
       'factory': f190}
yocto_builders.append(b190)

#####################################################################
#
# jasperforest Buildout
#
#####################################################################

f200 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'jasperforest'
defaultenv['ENABLE_SWABBER'] = 'false'

defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'jasperforest'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f200)
runBSPLayerPreamble(f200)
buildBSPLayer(f200, "poky", defaultenv['BTARGET'])
f200.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f200, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f200)
b200 = {'name': "jasperforest",
       'slavename': "builder1",
       'builddir': "jasperforest",
       'factory': f200}
yocto_builders.append(b200)

#####################################################################
# Sugarbay Buildout
#####################################################################

f210 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'sugarbay'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['REVISION'] = "HEAD"
defaultenv['BTARGET'] = 'sugarbay'
defaultenv['BSP_REPO'] = "git://git.pokylinux.org/meta-intel.git"
defaultenv['BSP_BRANCH'] = "master"
defaultenv['BSP_WORKDIR'] = "build/yocto/meta-intel"
defaultenv['BSP_REV'] = "HEAD"
runPreamble(f210)
runBSPLayerPreamble(f210)
buildBSPLayer(f210, "poky", defaultenv['BTARGET'])
f210.addStep(ShellCommand, description="Moving old TMPDIR", workdir="build/build", command="mv tmp non-lsbtmp; mkdir tmp")
buildBSPLayer(f210, "poky-lsb", defaultenv['BTARGET'])
runBSPLayerPostamble(f210)
b210 = {'name': "sugarbay",
       'slavename': "builder1",
       'builddir': "sugarbay",
       'factory': f210}
yocto_builders.append(b210)

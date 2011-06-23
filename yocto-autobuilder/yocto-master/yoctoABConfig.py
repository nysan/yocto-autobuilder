################################################################################
#                             Project Identity
################################################################################

# the 'projectName' string will be used to describe the project that this
# buildbot is working on. For example, it is used as the title of the
# waterfall HTML page. The 'projectURL' string will be used to provide a link
# from buildbot HTML pages to your project's home page.

yocto_projname = "Yocto"
yocto_projurl = "http://yoctoproject.org/"

################################################################################
#                              Change Sources
################################################################################

yocto_sources = []

# For example, if you had CVSToys installed on your repository, and your
# CVSROOT/freshcfg file had an entry like this:
#pb = ConfigurationSet([
#    (None, None, None, PBService(userpass=('foo', 'bar'), port=4519)),
#    ])

# then you could use the following buildmaster Change Source to subscribe to
# the FreshCVS daemon and be notified on every commit:
#
#from buildbot.changes.freshcvs import FreshCVSSource688
#fc_source = FreshCVSSource("cvs.example.com", 4519, "foo", "bar")
#c['change_source'] = fc_source

# or, use a PBChangeSource, and then have your repository's commit script run
# 'buildbot sendchange', or use contrib/svn_buildbot.py, or
# contrib/arch_buildbot.py :
#
from buildbot.changes.pb import PBChangeSource
yocto_sources.append(PBChangeSource())

################################################################################
#                               Schedulers
################################################################################
from buildbot.scheduler import Triggerable
from buildbot.scheduler import Scheduler
from buildbot.scheduler import Periodic
from buildbot.scheduler import Nightly
yocto_sched = []

# Schedulers themselves are attached to builders below

################################################################################
#                                Builders
################################################################################

# the 'builders' list defines the Builders. Each one is configured with a
# dictionary, using the following keys:
#  name (required): the name used to describe this builder
#  slavename (required): which slave to use (must appear in c['slaves'])
#  builddir (required): which subdirectory to run the builder in
#  factory (required): a BuildFactory to define how the build is run
#  periodicBuildTime (optional): if set, force a build every N seconds

# buildbot/process/factory.py provides several BuildFactory classes you can
# start with, which implement build processes for common targets (GNU
# autoconf projects, CPAN perl modules, etc). The factory.BuildFactory is the
# base class, and is configured with a series of BuildSteps. When the build
# is run, the appropriate buildslave is told to execute each Step in turn.

# the first BuildStep is typically responsible for obtaining a copy of the
# sources. There are source-obtaining Steps in buildbot/steps/source.py for
# CVS, SVN, and others.

import copy
import random
import os
from buildbot.process import factory
from buildbot.steps.trigger import Trigger
from buildbot.schedulers import triggerable
from buildbot.steps.source import Git
from buildbot.process.properties import WithProperties
from buildbot.steps import shell
from buildbot.steps.shell import ShellCommand
from time import strftime

yocto_builders = []

# Setup default environment
defaultenv = {}
BUILD_OUTPUT_DIR = os.environ.get("BUILD_OUTPUT_DIR")
BUILD_OUTPUT_SERVER = os.environ.get("BUILD_OUTPUT_SERVER")
BUILD_OUTPUT_COMMAND = os.environ.get("BUILD_OUTPUT_COMMAND")

# Common command 'macros'
def runImage(factory, machine, image):
    defaultenv['MACHINE'] = machine
    factory.addStep(ShellCommand, description=["Building", machine, image], 
                    command=["yocto-autobuild", image, "-k"], 
                    env=copy.copy(defaultenv), 
                    timeout=14400)

def runImageLayers(factory, machine, image):
    defaultenv['MACHINE'] = machine
    factory.addStep(ShellCommand, description=["Building", machine, image], 
                    command=["yocto-autobuild-layers", image, "-k"], 
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
    factory.addStep(ShellCommand, description="Run preamble",  
                    command="yocto-autobuild-preamble", 
                    env=copy.copy(defaultenv), 
                    timeout=60)

def backupWorkDir(factory):
    factory.addStep(ShellCommand, description="Backup work dir", 
                    command="yocto-preserve-work-dir backup", 
                    timeout=60)

def restoreWorkDir(factory):
    factory.addStep(ShellCommand, description="Restore work dir", 
                    command="yocto-preserve-work-dir restore", 
                    timeout=60)

def getRepo(step):
    gittype = step.getProperty("repository")
    if gittype == "git://git.yoctoproject.org/poky-contrib":
        step.setProperty("branch", "stage/master_under_test")
    elif gittype == "git://git.yoctoproject.org/poky":
        step.setProperty("branch", "master")
    else:
        return False
    return True

def makeCheckout(factory):
    factory.addStep(ShellCommand(doStepIf=getRepo,
                    description="Getting the requested git repo",
                    command='echo "Getting the requested git repo"'))
    factory.addStep(ShellCommand(
                    description=["Building", WithProperties("%s", "branch"),  
                                 WithProperties("%s", "repository")],
                    command=["echo", WithProperties("%s", "branch"),  
                             WithProperties("%s", "repository")]))
    factory.addStep(Git(timeout=10000, retry=(5, 3)))
    factory.addStep(ShellCommand, command=["git", "checkout",  
                    WithProperties("%s", "pokytag")], timeout=1000)

def cleanImages(factory):
    factory.addStep(ShellCommand, description="Cleaning previous images",  
                    command="yocto-autobuild-cleanoutput", 
                    timeout=600)

def cleanImagesIncremental(factory):
    factory.addStep(ShellCommand, description="Cleaning previous images",  
                    command="yocto-autobuild-cleanoutput-exclude-kernels", 
                    timeout=600)

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
                                                  'core-image-minimal-dev']))
    step.setProperty("FuzzSDK", random.choice( ['i686', 'x86-64'] ))
    defaultenv['MACHINE'] = step.getProperty("FuzzArch")
    imageType = step.getProperty("FuzzImage")
    defaultenv['SDKMACHINE'] = step.getProperty("FuzzSDK")
    if imageType.endswith('lsb'):
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
    factory.addStep(ShellCommand, 
                    description=["Building", WithProperties("%s", "MetaImage")],
                    command=["yocto-autobuild", 
                             WithProperties("%s", "MetaImage"), "-k"],
                    env=copy.copy(defaultenv),
                    timeout=14400)

def nightlyQEMU(factory, machine, distrotype):
    if distrotype == "poky":
       defaultenv['DISTRO'] = "poky"
       #runImage(factory, machine, 'core-image-minimal') 
       runImage(factory, machine, 'core-image-sato core-image-sato-dev core-image-sato-sdk core-image-minimal core-image-minimal-dev')
       runSanityTest(factory, machine, 'core-image-sato')
       runSanityTest(factory, machine, 'core-image-minimal')
    elif distrotype == "poky-lsb":
       defaultenv['DISTRO'] = "poky-lsb"
       #runImage(factory, machine, 'core-image-lsb')
       runImage(factory, machine, 'core-image-lsb core-image-lsb-dev core-image-lsb-sdk')
    defaultenv['DISTRO'] = 'poky'
    factory.addStep(ShellCommand, description="Copying " + machine + " build output", 
                    command="yocto-autobuild-copy-images-2.0 " + 
                    machine + " nightly " + BUILD_OUTPUT_DIR, 
                    timeout=600)

def nightlyBSP(factory, machine, distrotype):
    if distrotype == "poky":
        defaultenv['DISTRO'] = 'poky'
        #runImage(factory, machine, 'core-image-minimal')
        runImage(factory, machine, 'core-image-sato core-image-sato-sdk core-image-minimal')
    elif distrotype == "poky-lsb":
        defaultenv['DISTRO'] = 'poky-lsb'
        runImage(factory, machine,  'core-image-lsb-sdk')
    defaultenv['DISTRO'] = 'poky'
    factory.addStep(ShellCommand, description="Copying " + machine + " build output", 
                    command="yocto-autobuild-copy-images-2.0 " + 
                    machine + " nightly " + BUILD_OUTPUT_DIR, 
                    timeout=600)

def setBranchName(step):
    branch = step.getProperty("branch")
    if branch == None:
        step.setProperty("BRANCHNAME", "stage/master_under_test")  
        step.setProperty("BRANCHDEST", "")
        step.setProperty("REALBRANCH", "stage/master_under_test")
    else:
        step.setProperty("BRANCHNAME", str(branch))
        step.setProperty("BRANCHDEST", '-' + str(branch))
        step.setProperty("REALBRANCH", str(branch))
    return True

def doEMGDTest(step):
    buildername = step.getProperty("buildername")
    if buildername == "crownbay":
        return True
    elif buildername == "crownbay-lsb":
        return True
    else:
        return False

def checkBranchName(step):
    branch = step.getProperty("branch")
    if branch == "None":
        return False
    else:
        return True
 
def makeTarball(factory):
    factory.addStep(ShellCommand, description="Generating release tarball", 
                    command=["yocto-autobuild-generate-sources-tarball", "nightly", "1.0pre", 
                    WithProperties("%s", "BRANCHNAME")], timeout=120)
    factory.addStep(ShellCommand, description="Copying release tarball", 
                    command=["yocto-autobuild-copy-images-2.0", "yocto-sources", 
                    "nightly", BUILD_OUTPUT_DIR], 
                    timeout=60)

def makeLayerTarball(factory):
    factory.addStep(ShellCommand, description="Generating release tarball",
                    command=["yocto-autobuild-generate-sources-tarball", "nightly", "1.0pre",
                    WithProperties("%s", "BRANCHNAME")], timeout=120)
    factory.addStep(ShellCommand, description="Copying release tarball",
                    command=["yocto-autobuild-copy-images-2.0", "yocto-sources", "nightly", 
                    WithProperties(BUILD_OUTPUT_DIR + 
                    str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")], timeout=60)


def runBSPLayerPreamble(factory):
    factory.addStep(ShellCommand(doStepIf=setBranchName, 
                    description="Setting Branch Name", 
                    command='echo "Setting Branch Name"'))
    makeCheckout(factory)
    factory.addStep(shell.SetProperty(workdir="build", 
                    command="git rev-parse HEAD", 
                    property="POKYHASH"))
    factory.addStep(ShellCommand, 
                    command="echo 'Checking out git://git.pokylinux.org/meta-intel.git'",
                    timeout=10)
    factory.addStep(Git(repourl="git://git.pokylinux.org/meta-intel.git", 
                    mode="clobber", workdir="build/yocto/meta-intel",
                    branch="master",
                    timeout=10000, retry=(5, 3)))
    factory.addStep(shell.SetProperty(workdir="build/yocto/meta-intel", 
                    command="git rev-parse HEAD", 
                    property="METAHASH"))
    factory.addStep(ShellCommand(doStepIf=doEMGDTest, 
                    description="Copying EMGD", 
                    workdir="build", 
                    command="cp -R ~/EMGD_1.6/* yocto/meta-intel/meta-crownbay/recipes-graphics/xorg-xserver/",
                    timeout=60))
    factory.addStep(ShellCommand, description="Making output directory", 
                    command=["/bin/mkdir", "-p", 
                    WithProperties(BUILD_OUTPUT_DIR + 
                    str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s/nightly")], 
                    timeout=60)
    factory.addStep(ShellCommand, description="Run preamble", 
                    command=["yocto-autobuild-preamble", 
                    WithProperties(BUILD_OUTPUT_DIR + 
                    str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s/nightly")], timeout=60)

def runBSPLayerPostamble(factory):
    factory.addStep(ShellCommand, description="Creating CURRENT link", 
                    command=["yocto-autobuild-generate-current-link", "nightly", 
                    WithProperties(BUILD_OUTPUT_DIR + 
                    str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s"), "current"], 
                    timeout=20)

def buildBSPLayer(factory, distrotype):
    if distrotype == "poky":
        defaultenv['DISTRO'] = 'poky'
        runImageLayers(factory, str(defaultenv['BTARGET']), 
                       'core-image-sato-live core-image-sato-sdk-live core-image-minimal-live')
        factory.addStep(ShellCommand, description="Copying " + 
                        str(defaultenv['ABTARGET']) + " build output", 
                        command=["yocto-autobuild-copy-images-2.0", 
                        defaultenv['BTARGET'], "nightly", 
                        WithProperties(BUILD_OUTPUT_DIR + 
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")]) 
        makeLayerTarball(factory)
        factory.addStep(ShellCommand, description="Copying RPM feed output", 
                        command=["yocto-autobuild-copy-images-2.0", "rpm", "nightly", 
                        WithProperties(BUILD_OUTPUT_DIR + 
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")])
        factory.addStep(ShellCommand, description="Copying IPK feed output",
                        command=["yocto-autobuild-copy-images-2.0", "ipk", "nightly",
                        WithProperties(BUILD_OUTPUT_DIR +
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")])
    elif distrotype == "poky-lsb":
        defaultenv['DISTRO'] = 'poky-lsb'
        runImageLayers(factory, str(defaultenv['BTARGET']), 'core-image-lsb-live core-image-lsb-sdk-live')
        factory.addStep(ShellCommand, description="Copying " + str(defaultenv['ABTARGET']) + " build output", 
                        command=["yocto-autobuild-copy-images-2.0", defaultenv['BTARGET'], "nightly", 
                        WithProperties(BUILD_OUTPUT_DIR + 
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")]) 
        factory.addStep(ShellCommand, description="Copying RPM feed output", 
                        command=["yocto-autobuild-copy-images-2.0", "rpm-lsb", "nightly", 
                        WithProperties(BUILD_OUTPUT_DIR + 
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")], timeout=1800)
        factory.addStep(ShellCommand, description="Copying IPK feed output",
                        command=["yocto-autobuild-copy-images-2.0", "ipk-lsb", "nightly",
                        WithProperties(BUILD_OUTPUT_DIR +
                        str(defaultenv['ABTARGET']) + "%(BRANCHDEST)s")], timeout=1800)


################################################################################
#
# Poky Toolchain Fuzzy Target
#
#
################################################################################
f2 = factory.BuildFactory()
fuzzsched = Triggerable(name="fuzzy-master",
        builderNames=["b2"])

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
#
# Poky Toolchain Fuzzy Target
#
#
################################################################################
f3 = factory.BuildFactory()
fuzzsched = Triggerable(name="fuzzy-mut",
        builderNames=["b3"])

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
#
# Poky Toolchain Fuzzy Target
#
#
################################################################################
f4 = factory.BuildFactory()
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
#
################################################################################

f22 = factory.BuildFactory()
makeCheckout(f22)
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
runImage(f22, 'qemux86-64', 'meta-toolchain-gmae')
f22.addStep(ShellCommand, description="Setting SDKMACHINE=x86_64", 
            command="echo 'Setting SDKMACHINE=x86_64'", timeout=10)
defaultenv['SDKMACHINE'] = 'x86_64'
runImage(f22, 'qemux86-64', 'meta-toolchain-gmae')
swabberTimeStamp = strftime("%Y%m%d%H%M%S")
swabberTarPath = BUILD_OUTPUT_DIR + "/swabber-logs/" + swabberTimeStamp + ".tar.bz2"
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
f61.addStep(ShellCommand, description=["Copying", "eclipse", "plugin", "output"], 
            command="yocto-eclipse-plugin-copy-output", timeout=120)

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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
f65.addStep(ShellCommand(doStepIf=setBranchName, description="Setting Branch Names", 
            command='echo "Setting Branch Name"'))
makeCheckout(f65)
f65.addStep(ShellCommand, description="Run preamble", 
            command="yocto-autobuild-preamble " + BUILD_OUTPUT_DIR + "/nightly", 
            timeout=60)
nightlyQEMU(f65, 'qemux86', 'poky')
nightlyQEMU(f65, 'qemuarm', 'poky')
nightlyQEMU(f65, 'qemumips', 'poky')
nightlyQEMU(f65, 'qemuppc', 'poky')
nightlyBSP(f65, 'beagleboard', 'poky')
nightlyBSP(f65, 'mpc8315e-rdb', 'poky')
nightlyBSP(f65, 'routerstationpro', 'poky')
nightlyQEMU(f65, 'qemux86', "poky-lsb")
nightlyQEMU(f65, 'qemuarm', "poky-lsb")
nightlyQEMU(f65, 'qemumips', "poky-lsb")
nightlyQEMU(f65, 'qemuppc', "poky-lsb")
nightlyBSP(f65, 'beagleboard', "poky-lsb")
nightlyBSP(f65, 'mpc8315e-rdb', "poky-lsb")
nightlyBSP(f65, 'routerstationpro', "poky-lsb")
runImage(f65, 'qemux86', 'package-index')
makeTarball(f65)
f65.addStep(ShellCommand, description="Copying IPK feed output", 
            command="yocto-autobuild-copy-images-2.0 ipk nightly " + BUILD_OUTPUT_DIR, 
            timeout=1800)
f65.addStep(ShellCommand, description="Copying RPM feed output", 
            command="yocto-autobuild-copy-images-2.0 rpm nightly " + BUILD_OUTPUT_DIR, 
            timeout=1800)
f65.addStep(ShellCommand, description="Cloning eclipse-poky git repo", 
            command="yocto-eclipse-plugin-clone-repo", timeout=300)
f65.addStep(ShellCommand, description="Copying eclipse build tools", 
            command="yocto-eclipse-plugin-copy-buildtools combo", timeout=120)
f65.addStep(ShellCommand, description="Building eclipse plugin", 
            command="yocto-eclipse-plugin-build combo master", timeout=120)
f65.addStep(ShellCommand, description="Copying eclipse plugin output", 
            command="yocto-autobuild-copy-images-2.0 eclipse-plugin nightly " + BUILD_OUTPUT_DIR, 
            timeout=60)
f65.addStep(ShellCommand, description="Syncing shared state cache to mirror", 
            command="yocto-update-shared-state-prebuilds-2.0", timeout=2400)
f65.addStep(ShellCommand, description="Copying shared state cache", 
            command="yocto-autobuild-copy-images-2.0 sstate nightly " + BUILD_OUTPUT_DIR, 
            timeout=8400)
f65.addStep(ShellCommand, description="Copying buildstatistics output", 
            command="yocto-autobuild-copy-images-2.0 buildstats nightly " + BUILD_OUTPUT_DIR, 
            timeout=600)
f65.addStep(ShellCommand, description="Creating CURRENT link", 
            command="yocto-autobuild-generate-current-link nightly " + BUILD_OUTPUT_DIR +"/ current", 
            timeout=20)

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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
f66.addStep(ShellCommand(doStepIf=setBranchName, description="Setting Branch Names",
            command='echo "Setting Branch Name"'))
makeCheckout(f66)
f66.addStep(ShellCommand, description="Run preamble",
            command="yocto-autobuild-preamble " + BUILD_OUTPUT_DIR + "nightly",
            timeout=60)
f66.addStep(ShellCommand, description="Setting SDKMACHINE=i686", 
            command="echo 'Setting SDKMACHINE=i686'", timeout=10)
defaultenv['SDKMACHINE'] = 'i686'
runImage(f66, 'qemux86', 'meta-toolchain-gmae')
runImage(f66, 'qemuarm', 'meta-toolchain-gmae')
runImage(f66, 'qemumips', 'meta-toolchain-gmae')
runImage(f66, 'qemuppc', 'meta-toolchain-gmae')
defaultenv['SDKMACHINE'] = 'x86_64'
runImage(f66, 'qemux86', 'meta-toolchain-gmae')
runImage(f66, 'qemuarm', 'meta-toolchain-gmae')
runImage(f66, 'qemumips', 'meta-toolchain-gmae')
runImage(f66, 'qemuppc', 'meta-toolchain-gmae')
runImage(f66, 'qemux86', 'package-index')
f66.addStep(ShellCommand, description="Copying toolchain-x86-64 build output", 
            command="yocto-autobuild-copy-images-2.0 toolchain nightly " + BUILD_OUTPUT_DIR , 
            timeout=600)
f66.addStep(ShellCommand, description="Copying buildstatistics output", 
            command="yocto-autobuild-copy-images-2.0 buildstats nightly " + BUILD_OUTPUT_DIR , 
            timeout=600)
f66.addStep(ShellCommand, description="Creating CURRENT link", 
            command="yocto-autobuild-generate-current-link nightly " + BUILD_OUTPUT_DIR + "/ current", 
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
f70.addStep(ShellCommand(doStepIf=setBranchName, description="Setting Branch Names", 
            command='echo "Setting Branch Name"'))
makeCheckout(f70)
f70.addStep(ShellCommand, description="Run preamble", 
            command="yocto-autobuild-preamble " + BUILD_OUTPUT_DIR + "/nightly", timeout=60)
nightlyQEMU(f70, 'qemux86', 'poky')
nightlyQEMU(f70, 'qemux86-64', 'poky')
nightlyBSP(f70, 'atom-pc', 'poky')
nightlyQEMU(f70, 'qemux86', 'poky-lsb')
nightlyQEMU(f70, 'qemux86-64', 'poky-lsb')
nightlyBSP(f70, 'atom-pc', 'poky-lsb')
runImage(f70, 'qemux86', 'package-index')
f70.addStep(ShellCommand, description="Copying toolchain-x86-64 build output", 
            command="yocto-autobuild-copy-images-2.0 toolchain nightly " + BUILD_OUTPUT_DIR , 
            timeout=600)
makeTarball(f70)
f70.addStep(ShellCommand, description="Copying IPK feed output", 
            command="yocto-autobuild-copy-images-2.0 ipk nightly " + BUILD_OUTPUT_DIR , 
            timeout=1800)
f70.addStep(ShellCommand, description="Copying RPM feed output", 
            command="yocto-autobuild-copy-images-2.0 rpm nightly " + BUILD_OUTPUT_DIR , 
            timeout=1800)
f70.addStep(ShellCommand, description="Copying buildstatistics output", 
            command="yocto-autobuild-copy-images-2.0 buildstats nightly " + BUILD_OUTPUT_DIR , 
            timeout=1800)
f70.addStep(ShellCommand, description="Syncing shared state cache to mirror", 
            command="yocto-update-shared-state-prebuilds-2.0", timeout=2400)
f70.addStep(ShellCommand, description="Copying shared state cache", 
            command="yocto-autobuild-copy-images-2.0 sstate nightly " + BUILD_OUTPUT_DIR , 
            timeout=8400)
f70.addStep(ShellCommand, description="Creating CURRENT link", 
            command="yocto-autobuild-generate-current-link nightly " + BUILD_OUTPUT_DIR + "/ current", 
            timeout=20)
b70 = {'name': "nightly-internal",
      'slavename': "builder1",
      'builddir': "nightly-internal",
      'factory': f70,
      }
yocto_builders.append(b70)

################################################################################
# external incremental
################################################################################

f100 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-external-incremental'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
backupWorkDir(f100)
makeCheckout(f100)
restoreWorkDir(f100)
f100.addStep(ShellCommand, description="Run preamble", 
             command="yocto-autobuild-preamble " + BUILD_OUTPUT_DIR + "/nightly", 
             timeout=60)
cleanImagesIncremental(f100)
runImage(f100, 'qemux86', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemux86', 'poky')
runImage(f100, 'qemuarm', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemuarm', 'poky')
runImage(f100, 'qemumips', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemumips', 'poky')
runImage(f100, 'qemuppc', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemuppc', 'poky')
nightlyBSP(f100, 'beagleboard', 'poky')
nightlyBSP(f100, 'mpc8315e-rdb', 'poky')
nightlyBSP(f100, 'routerstationpro', 'poky')
runImage(f100, 'qemux86', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemux86', 'poky-lsb')
runImage(f100, 'qemuarm', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemuarm', 'poky-lsb')
runImage(f100, 'qemumips', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemumips', 'poky-lsb')
runImage(f100, 'qemuppc', 'virtual/kernel -c deploy')
nightlyQEMU(f100, 'qemuppc', 'poky-lsb')
nightlyBSP(f100, 'beagleboard', 'poky-lsb')
nightlyBSP(f100, 'mpc8315e-rdb', 'poky-lsb')
nightlyBSP(f100, 'routerstationpro', 'poky-lsb')
runImage(f100, 'qemux86', 'package-image')
f100.addStep(ShellCommand, description="Cloning eclipse-poky git repo", 
             command="yocto-eclipse-plugin-clone-repo", timeout=300)
f100.addStep(ShellCommand, description="Copying eclipse build tools", 
             command="yocto-eclipse-plugin-copy-buildtools combo", timeout=120)
f100.addStep(ShellCommand, description="Building eclipse plugin", 
             command="yocto-eclipse-plugin-build combo", timeout=120)
b100 = {'name': "nightly-external-incremental",
      'slavename': "builder1",
      'builddir': "nightly-external-incremental",
      'factory': f100,
      }
yocto_builders.append(b100)


################################################################################
# internal incremental
################################################################################
f110 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-internal-incremental'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
backupWorkDir(f110)
makeCheckout(f110)
restoreWorkDir(f110)
f110.addStep(ShellCommand, description="Run preamble", 
             command="yocto-autobuild-preamble " + BUILD_OUTPUT_DIR + "/nightly", 
             timeout=60)
cleanImagesIncremental(f110)
runImage(f110, 'qemux86', 'virtual/kernel -c deploy')
nightlyQEMU(f110, 'qemux86', 'poky')
runImage(f110, 'qemux86-64', 'virtual/kernel -c deploy')
nightlyQEMU(f110, 'qemux86-64', 'poky')
nightlyBSP(f110, 'atom-pc', 'poky')
runImage(f110, 'qemux86', 'virtual/kernel -c deploy')
nightlyQEMU(f110, 'qemux86', 'poky-lsb')
runImage(f110, 'qemux86-64', 'virtual/kernel -c deploy')
nightlyQEMU(f110, 'qemux86-64', 'poky-lsb')
nightlyBSP(f110, 'atom-pc', 'poky-lsb')
defaultenv['SDKMACHINE'] = 'i686'
runImage(f110, 'qemux86', 'meta-toolchain-gmae')
runImage(f110, 'qemux86-64', 'meta-toolchain-gmae')
runImage(f110, 'qemux86', 'package-index')
f110.addStep(ShellCommand, description="Setting SDKMACHINE=x86_64", 
             command="echo 'Setting SDKMACHINE=x86_64'", 
             timeout=10)
defaultenv['SDKMACHINE'] = 'x86_64'
runImage(f110, 'qemux86', 'meta-toolchain-gmae')
runImage(f110, 'qemux86-64', 'meta-toolchain-gmae')
runImage(f110, 'qemux86', 'package-index')
b110 = {'name': "nightly-internal-incremental",
      'slavename': "builder1",
      'builddir': "nightly-internal-incremental",
      'factory': f110,
      }
yocto_builders.append(b110)


################################################################################
# External Sanity
################################################################################
f80 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-external-sanity'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
runSanityTest(f80, 'qemuarm', 'core-image-sato')
runSanityTest(f80, 'qemuarm', 'core-image-lsb')
runSanityTest(f80, 'qemuarm', 'core-image-minimal')
runSanityTest(f80, 'qemumips', 'core-image-sato')
runSanityTest(f80, 'qemumips', 'core-image-lsb')
runSanityTest(f80, 'qemumips', 'core-image-minimal')
runSanityTest(f80, 'qemuppc', 'core-image-sato')
runSanityTest(f80, 'qemuppc', 'core-image-lsb')
runSanityTest(f80, 'qemuppc', 'core-image-minimal')
b80 = {'name': "nightly-external-sanity",
      'slavename': "builder1",
      'builddir': "nightly-external-sanity",
      'factory': f80,
      }
yocto_builders.append(b80)

################################################################################
# Internal Sanity
################################################################################

f90 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'nightly-internal-sanity'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
runSanityTest(f90, 'qemux86', 'core-image-sato')
runSanityTest(f90, 'qemux86', 'core-image-minimal')
runSanityTest(f90, 'qemux86-64', 'core-image-sato')
runSanityTest(f90, 'qemux86-64', 'core-image-lsb')
runSanityTest(f90, 'qemux86-64', 'core-image-minimal')
b90 = {'name': "nightly-internal-sanity",
      'slavename': "builder1",
      'builddir': "nightly-internal-sanity",
      'factory': f90,
      }
yocto_builders.append(b90)

#####################################################################
#
# Tunnel Creek Buildout
#
#####################################################################


f170 = factory.BuildFactory()
defaultenv['DISTRO'] = 'poky'
defaultenv['ABTARGET'] = 'crownbay'
defaultenv['ENABLE_SWABBER'] = 'false'
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'crownbay'
f170.addStep(ShellCommand, description="Removing old sstate-cache", command='rm -rf ' +  BUILD_OUTPUT_DIR + '/sstate-cache/*')
runBSPLayerPreamble(f170)
buildBSPLayer(f170, "poky")
buildBSPLayer(f170, "poky-lsb")
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'crownbay'
f175.addStep(ShellCommand, description="Removing old sstate-cache", command='rm -rf ' +  BUILD_OUTPUT_DIR + '/sstate-cache/*')
runBSPLayerPreamble(f175)
buildBSPLayer(f175, "poky")
buildBSPLayer(f175, "poky-lsb")
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'emenlow'
f180.addStep(ShellCommand, description="Removing old sstate-cache", command='rm -rf ' +  BUILD_OUTPUT_DIR + '/sstate-cache/*')
runBSPLayerPreamble(f180)
buildBSPLayer(f180, "poky")
buildBSPLayer(f180, "poky-lsb")
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'n450'
f190.addStep(ShellCommand, description="Removing old sstate-cache", command='rm -rf ' +  BUILD_OUTPUT_DIR + '/sstate-cache/*')
runBSPLayerPreamble(f190)
buildBSPLayer(f190, "poky")
buildBSPLayer(f190, "poky-lsb")
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'jasperforest'
f200.addStep(ShellCommand, description="Removing old sstate-cache", command='rm -rf ' +  BUILD_OUTPUT_DIR + '/sstate-cache/*')
runBSPLayerPreamble(f200)
buildBSPLayer(f200, "poky")
buildBSPLayer(f200, "poky-lsb")
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
defaultenv['SSTATE_DIR'] = BUILD_OUTPUT_DIR + '/sstate-cache'
defaultenv['BTARGET'] = 'sugarbay'
runBSPLayerPreamble(f210)
buildBSPLayer(f210, "poky")
buildBSPLayer(f210, "poky-lsb")
runBSPLayerPostamble(f210)
b210 = {'name': "sugarbay",
       'slavename': "builder1",
       'builddir': "sugarbay",
       'factory': f210}
yocto_builders.append(b210)



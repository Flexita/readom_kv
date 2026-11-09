# Contributing

This file is for people changing the code. To put the system on a Kindle, read
`docs/install.en.md`. Anything about security -- signing keys, the guarantee
that no partition is written, private data -- is in `SECURITY.en.md`.
Talking and contributing here means following `CODE_OF_CONDUCT.en.md`.

## The hard rules of this project

Said first, because they explain most of what follows:

1. **No partition is written and no bootloader is changed.** The whole system
   is two image files on the Kindle's user area (FAT), reached through a
   handover module inside the stock kernel. Holding the power button down gets
   you back to the stock system. Anything that needs a partition written is not
   accepted.
2. **Per-device data goes neither into the repository nor into a release.** The
   panel waveform, the Wi-Fi calibration and firmware, the MAC, the serial
   number, the ATAGs, the stock private kernel modules -- these are taken off
   the owner's own device at install time and nowhere else.
3. **A conclusion is backed by a measurement.** The documents here are full of
   "this was measured at N". A change that moves a number somebody wrote down
   either measures it again or says why it need not be measured again. Say
   which parts are inference and which are measurement.
4. **No stopgaps.** Make the premise of the problem a compile-time or test-time
   refusal rather than adding a special case to the code.

## Build environment

Today: macOS on Apple Silicon with a Lima VM -- ARM64 Ubuntu holding an x86
chroot, which is where AOSP 8.1's host tools run. None of it touches a device.

```bash
python3 tools/fetch-prebuilts.py      # third-party files (EinkBro, WebView, the monochrome emoji font), SHA-256 checked
bash tools/vm.sh start                # make and start the VM from config/build-vm.template.yaml
bash tools/vm.sh shell                # enter it; the commands below run inside
sudo bash /mnt/port/tools/provision-x86-runtime.sh  # qemu and the libraries AOSP's x86 host tools need
bash /mnt/port/tools/provision-aosp-chroot.sh
bash /mnt/port/tools/sync-aosp.sh     # fetch AOSP as source-lock.json pins it
bash /mnt/port/tools/build-test-libc.sh  # static ARM musl for the entry and the installer; put the archive source-lock.json's test_libc names in /mnt/build-share/toolchains/ first
bash /mnt/port/tools/build-kernel.sh android-core
PW3_AOSP_INSTALLCLEAN=1 bash /mnt/port/tools/run-aosp-build-job.sh  # required when a package list changed
python3 /mnt/port/tools/export-aosp-images.py --output /mnt/build-share/<export dir>
```

**A system build always goes through `tools/run-aosp-build-job.sh`**, never
straight to `build-aosp-system.sh`: the job shell binds the images it produced
into a receipt by content, and the export and the payload believe that receipt.
Going around it makes an export cite another build's receipt. It takes its
options from the environment only:

| Variable | Default | When it has to be given |
|---|---|---|
| `PW3_AOSP_INSTALLCLEAN` | `0` | Must be `1` after any `.mk` under `device/amazon/pw3` changed: a module that no longer installs would leave its file in the staging tree and the image would carry it. Without it, a build whose `.mk` files changed stops before entering the chroot |
| `PW3_BUILD_VARIANT` | `userdebug` | `user` for a release |
| `PW3_RELEASE_KEY_DIR` | none | Required for a `user` build: a path as the build chroot sees it, never inside the source tree or the shared build directory |
| `PW3_BUILD_VERSION` | none | Give it for a release. It becomes the Settings > About tablet > Build number line (`ro.build.display.id`) and goes only into `build.prop`, leaving `BUILD_ID`, the fingerprint and the boot image alone |
| `PW3_BUILD_DATETIME` | the current time | To rebuild a release's `build.prop` and fingerprint, pass the value its release notes record |

Not done yet: a build reproducible in one command, and building on a Linux
host.

## Tests

```bash
python3 tools/run-tests.py                       # what runs on the host
# In the VM, where a dozen more run, including the ones that need the AOSP tree and the build output
bash tools/vm.sh shell
cd /mnt/port && python3 tools/run-tests.py --cc gcc --cxx g++
```

The suite prints what it could not run here and what each of those is missing.
**Do not make something pass by loosening what it checks** -- this repository
has had a few "skipped because" lines that were not the real reason. The way
out is to make the missing thing exist.

A new check is verified in reverse: break the thing it checks on purpose and
confirm the check fails. A check that only ever passes proves nothing about
itself. And a test that is in the tree and in nobody's list of what to run is a
hole in a green suite -- `tools/tests/test_every_test_runs.py` refuses that.

## The patch series

Changes to AOSP and to the kernel are patch files, applied in numbered order
(`tools/apply-patch-series.py`).

That tool is **append-only**: it records the patches it applied and their
hashes in `.pw3-applied-patches.json` inside the source tree, and refuses a
change to one it has already recorded. To change one, put the tree back and
apply the series again:

```bash
git -C <source tree> checkout -- . && git -C <source tree> clean -fdq
```

Above the body of a patch, write prose saying **why** the change is made and
what it rests on. Those paragraphs are one of this project's main records.

## Two rules about framework resources

When overlaying a `frameworks/base` resource:

- **Change values, never add names.** A new resource name changes `R.java`,
  which changes the boot image.
- The comment above an overridden entry is copied **word for word from AOSP**
  (`aapt2` copies it into `R.java`).
- Compare the ART boot files under `/system/framework/arm` after every build. A
  change there means installing the new version recompiles the applications in
  `/data`, and the release notes have to say so.

## Porting to another model

The maintainer has only a PW3, so every other model depends on someone who
has one. One repository holds several models: kernels group by version, and
one kernel version shares one patch series; what belongs to a model alone is a
boot profile (`boot/profiles/<model>-<firmware>.json`), a device directory
(`device/amazon/<model>/`) and a kernel model fragment
(`config/models/<model>.config`). How far each model is from the PW3, and what
a port involves, are in `docs/design/porting-to-other-models.en.md`. Open a
"Port" issue to keep track of the work; releasing from your own fork first is
fine. The four hard rules above hold for every model.

To bring a model back into this repository, four more:

1. **A model's pull request adds only what belongs to that model**: its boot
   profile, device directory and kernel model fragment, plus the lines that
   register the model with the build scripts (such as the model list in
   `tools/build-kernel.sh`, which the tests require to match `config/models/`).
   A change to how shared code behaves (`boot/`, `installer/`,
   `device/amazon/pw3/`, the shared patch series, the rest of the build
   scripts) is a pull request of its own that says which models need it, how
   it is limited to them, and why the others are unaffected. Before merging,
   the maintainer compares the PW3 build outputs from before and after the
   change on the build machine; where they differ, the pull request says why
   the change is right on the PW3 as well, and it has been checked on one.
2. **Code that exists only for an emulator or a test is kept apart the way this
   repository already does it.** Kernel patches go in `patches/test-kernel/`,
   not into the release series; a test path in the boot programs is a separate
   build-time configuration. A release build contains none of it, and no
   command-line parameter can turn it on in a release.
3. **Device results come from what this repository's build produces.** A
   hand-repacked image does not count. Attach what the device itself recorded
   -- the folder for that start under `android/logs/` on the Kindle drive (it
   holds no serial number, MAC address or network name; see
   `docs/install.en.md`) -- and what the screen showed. Something that only ran
   in an emulator says "emulator", not "device".
4. **A merged model has a maintainer**: someone who has that machine at hand,
   reviews changes to that model's files, and before every release installs and
   starts the release on it and reports back. Support is stated in two tiers:
   the PW3 is "verified on the maintainer's device"; any other model is
   "community-maintained, verified on a device by <name>". A model with no
   device report before a release gets no installer in that release; a model
   with none for two releases in a row is marked "currently unmaintained".

### Before a model is merged

A model's pull request, and the pull request that changes shared code for it,
each go through the four steps below in order; one that fails a step is not
merged.

1. **Automatic checks** (on every pull request, `.github/workflows/tests.yml`):
   the host tests pass (`tools/run-tests.py`); every file carries its licence
   (`reuse lint`); no file holds private data such as a MAC address, a serial
   number or a key (`tools/check-private-data.py`); no binary file comes in
   except an image (png, jpg, webp, pgm, and its content has to be one) --
   kernel modules, firmware, waveforms, update packages and jailbreaks all
   count; and a pull request that touches a model's own files is about that
   one model and touches only its files and its line in
   `tools/build-kernel.sh` (the last two are `tools/check-pr-scope.py`). These
   catch mistakes, not someone working around them on purpose: for a pull
   request that changes a check, GitHub runs the changed copy. An Amazon file
   or a jailbreak script in text form is not something they can recognise
   either; the review in step four reads for those.
2. **The PW3 is unaffected**: the maintainer builds the PW3 from before and
   after the change on the build machine and compares. The system image's
   ext4 container differs on every build, so what is compared is the content
   of each file in it (both builds with the same `PW3_BUILD_DATETIME`); the
   entry `Readom.sh` carries the system image's hash, so it is rebuilt with
   the same system image before it is compared; the kernel (`zImage`,
   modules, `.config`) and the other outputs are compared byte for byte.
   Where anything differs, the pull request says why it is right on the PW3
   as well, and it has been checked on one.
3. **The device evidence matches**: besides the record rule 3 above asks for,
   attach the commit that was built, the entry directory's `build-result.json`
   (it records the SHA-256 of the `android/system.img` it installs) and
   `launcher/build-result.json` (it records the SHA-256 of `Readom.sh`), and
   the SHA-256 of those two files on the Kindle drive, computed on a computer
   (`shasum -a 256 android/system.img documents/Readom.sh`). When they agree,
   the drive holds what this build produced, not a repacked image; this finds
   a wrong image or a repacked file mixed in. It does not find a deliberate
   forgery, and it does not prove which commit the receipts came from: the
   receipts and the record are in the contributor's hands, and the start's
   record cannot yet be traced to one particular build.
4. **A written review, and the maintainer decides**: the maintainer writes a
   review of each such pull request that lists every problem with its file and
   line. Once those are dealt with, the maintainer decides whether to merge.

For now some PW3 values are still written into shared code (the path of the
boot profile, the hashes of the stock boot files, the kernel version string
and more), so even the Voyage or the Oasis 1, on the same kernel as the PW3,
cannot be ported the first time without a pull request that changes shared
code, which goes on its own under rule 1. Models on a different kernel
version (the Kindle 8; the PW4, Oasis 2, Oasis 3 and Kindle 10) also need
changes to the handover, the storage layout and the display driver's
interface, and those are designed together with the first person to port
a model of that group.

The `pw3` in names is the name of this platform (i.MX6SL, the 3.0.35 kernel),
not only of one model: `gralloc.pw3`, `ro.hardware=pw3`, `init.pw3*.rc`,
`sys.pw3.*` and the like are used as they are by the other models, not
renamed. Renaming them would change what the PW3 build produces.

Once merged, the model's support tier and the person who verifies it on a
device are stated under "Other models" in the README; a model that is
currently unmaintained is marked there too, and the release notes follow it.
The repository uses no CODEOWNERS: GitHub accepts only people with write
access as code owners. When a model's files change, the maintainer asks that
model's maintainer to look, in the model's "Port" issue.

## Commits

- Message: first line `scope: what changed`, lower case, no full stop; the body
  in whole sentences saying **why**, what it rests on, and how far it was
  verified. The commits already here are the examples.
- One commit does one thing; split changes that cross subjects.
- A pull request follows the template: what changed, why, and how far it was
  verified. Every pull request runs the host tests on GitHub
  (`.github/workflows/tests.yml`, on Linux, with `--zstd-archive`), and a
  check of what it changes -- no binary files but images, and a model's pull
  request nowhere else (`tools/check-pr-scope.py`); one that does not pass is
  not merged.
- Enable the hook once per clone:

```bash
git config core.hooksPath tools/git-hooks
```

It runs `tools/check-private-data.py` over what is staged. The same check is
also an entry in the suite (`run-tests.py --filter private-data`), because a
check that only runs in a hook depends on somebody having remembered to enable
it, and this repository is meant to be published. What it checks, and how to
add your own values, is in `SECURITY.en.md`.

## Documents

- Chinese is the first language, but every document written for a user or a
  contributor has an English half: the five a reader needs (`README`,
  `CHANGELOG`, `docs/install`, `docs/known-issues`, `docs/open-items`),
  `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, `THIRD_PARTY`,
  `docs/README`, and every design record under `docs/design/`, with
  `tools/tests/test_doc_pairs.py` holding the two sides to the same
  structure (18 pairs today). Changing one side means changing the other.
  **A directory's own README (`boot/`, `device/`, `installer/`, `patches/`,
  `tools/`) is Chinese only**: those are signposts for somebody changing that
  part of the code, and are not in the pair list.
- References between documents are checked by
  `tools/tests/test_doc_links.py`: a `.md` path with a directory in it has to
  resolve.
- Which document answers what is in `docs/README.en.md`.

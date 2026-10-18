# Configuration cache regression

Run with an extracted OpenWrt SDK, after `make -C /path/to/sdk defconfig`:

```sh
python3 qca-nss-drv/tests/test-config-cache.py --sdk /path/to/sdk
```

This includes the actual driver recipe and the SDK's `rules.mk`,
`include/package.mk`, `confvar`, and `Build/CoreTargets`. Preparation is held
constant. Configuration and compilation use a small native C macro probe so the
SDK stamp graph can be tested without a prepared NSS kernel or firmware.
Staging files and all probe outputs stay in a private temporary directory. The
SDK configuration and framework hashes are checked before and after the test.

Eleven scenarios verify 12.2 to 12.5 switching, repeated identical invocations,
an unrelated configuration change, switching back, switching again, and the
existing CAPWAP dependency. Only changes in relevant inputs cause a rebuild.
The probe's output, compiler invocation count, configure count, and actual SDK
configuration stamp must agree. An invalid or unavailable SDK hash tool is an
error, not an empty stamp accepted as evidence.

To reproduce the old recipe, save its Makefile and pass it explicitly:

```sh
git show 0d970dbf0185e3f53709bd803e8a466598023c57:qca-nss-drv/Makefile > /tmp/nss-old.mk
python3 qca-nss-drv/tests/test-config-cache.py --sdk /path/to/sdk \
  --recipe /tmp/nss-old.mk --expect-stale
```

The counterexample requires the 12.5 compiler flag to be selected while the
configuration stamp, compile count, and previously built 12.x probe remain
unchanged. Without `--expect-stale`, the old recipe fails the normal test.
`--output /path/to/new-directory` retains all logs and a JSON report.

This tests incremental build invalidation. It does not build, load, or validate
an NSS module, firmware ABI, traffic behavior, or target hardware. A clean build
was already correct; users switching between 12.x firmware profiles are the
affected case.

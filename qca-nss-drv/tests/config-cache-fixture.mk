# SPDX-License-Identifier: GPL-2.0-only
# Use the real SDK recipe, confvar and Build/CoreTargets. Substitute only
# source preparation/configuration and compilation with an observable probe.
include $(RECIPE)
define Build/Prepare
	cp $(FIXTURES)/config-cache-probe.c $(PKG_BUILD_DIR)/probe.c
endef
define Build/Configure
	printf '%s\n' '$(STAMP_CONFIGURED)' >> $(LAB)/configured.log
endef
define Build/Compile
	/usr/bin/cc $(filter -DNSS_FIRMWARE_VERSION_%,$(EXTRA_CFLAGS)) $(PKG_BUILD_DIR)/probe.c -o $(PKG_BUILD_DIR)/probe
	printf '%s\n' '$(filter -DNSS_FIRMWARE_VERSION_%,$(EXTRA_CFLAGS))' >> $(LAB)/compiled.log
endef
Build/Install:=
Build/InstallDev:=
$(eval $(call Build/CoreTargets))
.PHONY: state
state:
	@echo STAMP=$(STAMP_CONFIGURED)
	@echo FLAGS=$(filter -DNSS_FIRMWARE_VERSION_%,$(EXTRA_CFLAGS))
	@echo BUILT=$(STAMP_BUILT)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise NSS firmware selection with the actual OpenWrt SDK stamp graph.

The fixture compiles a small native macro probe instead of a kernel module.
It does not replace confvar, STAMP_CONFIGURED, or Build/CoreTargets.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, lab):
    here = Path(__file__).resolve().parent
    sdk = args.sdk.resolve()
    recipe = (args.recipe or here.parent / 'Makefile').resolve()
    for file in ('rules.mk', 'include/kernel.mk', 'include/package.mk', '.config'):
        if not (sdk / file).is_file():
            raise ValueError('SDK input is missing: ' + file)
    before = {file: sha256(sdk / file) for file in
              ('rules.mk', 'include/package.mk', '.config')}
    (lab / 'tmp').mkdir()
    common = ['make', '-s', '-f', str(here / 'config-cache-fixture.mk'),
              'TOPDIR=' + str(sdk), 'RECIPE=' + str(recipe), 'LAB=' + str(lab),
              'FIXTURES=' + str(here), 'PKG_BUILD_DIR=' + str(lab / 'build'),
              # Preparation is fixed: only configuration caching is under test.
              'STAMP_PREPARED=' + str(lab / 'build/.prepared'),
              'STAGING_DIR=' + str(lab / 'stage'), 'TMP_DIR=' + str(lab / 'tmp'),
              'STAGING_DIR_HOST=' + str(sdk / 'staging_dir/host'),
              'PKG_INFO_DIR=' + str(lab / 'pkginfo'), 'KernelPackage=',
              'PKG_SKIP_DOWNLOAD=1', 'CONFIG_AUTOREBUILD=', 'CONFIG_AUTOREMOVE=',
              'CONFIG_NSS_FIRMWARE_VERSION_11_4=']
    report = {'sdk_inputs': before, 'recipe_sha256': sha256(recipe), 'cases': [],
              'kernel_module_built': False, 'production_access': False}

    def count(file):
        path = lab / file
        return len(path.read_text().splitlines()) if path.exists() else 0

    def step(label, selected, expected, calls, unrelated='', capwap=''):
        command = common + [
            'CONFIG_NSS_FIRMWARE_VERSION_12_2=' + ('' if selected else 'y'),
            'CONFIG_NSS_FIRMWARE_VERSION_12_5=' + selected,
            'CONFIG_NSS_CACHE_FIXTURE_UNRELATED=' + unrelated,
            'CONFIG_NSS_DRV_CAPWAP_ENABLE=' + capwap]
        state = subprocess.check_output(command + ['state'], cwd=lab, text=True,
                                        stderr=subprocess.STDOUT, timeout=30)
        fields = dict(line.split('=', 1) for line in state.splitlines() if '=' in line)
        if not re.fullmatch(r'\.configured_[a-f0-9]{32}', Path(fields['STAMP']).name):
            raise RuntimeError('SDK did not compute a valid configuration hash:\n' + state)
        result = subprocess.run(command + [str(lab / 'build/.built')], cwd=lab,
                                text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=60)
        (lab / (label + '.log')).write_text(state + result.stdout)
        result.check_returncode()
        value = subprocess.check_output([str(lab / 'build/probe')], text=True,
                                        timeout=5).strip()
        row = {'name': label, 'selected_12_5': selected, 'probe': value,
               'configure_calls': count('configured.log'),
               'compile_calls': count('compiled.log'),
               'stamp': Path(fields['STAMP']).name, 'flags': fields['FLAGS']}
        report['cases'].append(row)
        (lab / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        if value != expected or row['compile_calls'] != calls or row['configure_calls'] != calls:
            raise AssertionError(label + ': stale or unnecessarily rebuilt artifact: ' + str(row))
        print(label + ': ' + value + ', total builds=' + str(calls), flush=True)
        return row

    step('12_2-cold', '', '12.x', 1)
    step('12_2-noop', '', '12.x', 1)
    if args.expect_stale:
        stale = step('12_5-stale-counterexample', 'y', '12.x', 1)
        assert '-DNSS_FIRMWARE_VERSION_12_5' in stale['flags']
        assert stale['stamp'] == report['cases'][0]['stamp']
        report['original_stale_counterexample'] = True
    else:
        selected = step('12_5-switch', 'y', '12.5', 2)
        assert selected['stamp'] != report['cases'][0]['stamp']
        step('12_5-noop', 'y', '12.5', 2)
        step('unrelated-config-noop', 'y', '12.5', 2, unrelated='y')
        reverse = step('12_2-reverse', '', '12.x', 3)
        assert reverse['stamp'] == report['cases'][0]['stamp']
        step('12_2-reverse-noop', '', '12.x', 3)
        step('12_5-again', 'y', '12.5', 4)
        step('12_5-again-noop', 'y', '12.5', 4)
        step('existing-capwap-dependency', 'y', '12.5', 5, capwap='y')
        step('existing-capwap-noop', 'y', '12.5', 5, capwap='y')
    assert before == {file: sha256(sdk / file) for file in before}, 'SDK input changed'
    report.update(passed=True, sdk_inputs_unchanged=True)
    (lab / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: actual SDK configuration stamps; native macro probe only', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--recipe', type=Path)
    parser.add_argument('--expect-stale', action='store_true',
                        help='verify the original 12.2 to 12.5 stale-cache counterexample')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    # Prevent make from importing flags or goals from the invoking build.
    for name in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL'):
        os.environ.pop(name, None)
    if args.output:
        lab = args.output.resolve()
        lab.mkdir()
        run(args, lab)
    else:
        with tempfile.TemporaryDirectory(prefix='nss-config-cache-') as directory:
            run(args, Path(directory))

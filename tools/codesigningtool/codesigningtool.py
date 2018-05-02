# Copyright 2018 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import base64
import json
import os
import plistlib
import re
import subprocess
import sys


def _check_output(args, inputstr=None):
    proc = subprocess.Popen(args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return proc.communicate(input=inputstr)[0]


def _parse_mobileprovision_file(mobileprovision_file):
    """Reads and parses a mobileprovision file."""
    plist_xml = subprocess.check_output([
        "security", "cms",
        "-D",
        "-i", mobileprovision_file,
    ])
    if hasattr(plistlib, "readPlistFromString"):
        # Python 2
        return plistlib.readPlistFromString(plist_xml)
    else:
        # Python 3
        return plistlib.readPlistFromBytes(plist_xml)


def _certificate_fingerprint(identity):
    """Extracts a fingerprint given identity bytes contained in a
    mobileprovision file."""
    fingerprint = _check_output([
        "openssl", "x509", "-inform", "DER", "-noout", "-fingerprint",
    ], inputstr=identity).strip().decode("utf-8")
    fingerprint = fingerprint.replace("SHA1 Fingerprint=", "")
    fingerprint = fingerprint.replace(":", "")
    return fingerprint


def _get_identities_from_provisioning_profile(mpf):
    """Iterates through all the identities in a provisioning profile, lazily."""
    for identity in mpf["DeveloperCertificates"]:
        yield _certificate_fingerprint(identity.data)


def _find_codesign_identities():
    """Finds code signing identities on the current system."""
    ids = []
    output = _check_output([
        "security", "find-identity", "-v", "-p", "codesigning",
    ]).strip().decode("utf-8")
    for line in output.splitlines():
        m = re.search(r"([A-F0-9]{40})", line)
        if m:
            ids.append(m.group(0))
    return ids


def _find_codesign_identity(mobileprovision):
    """Finds a valid codesign identity on the system given an mobileprovision
    file."""
    mpf = _parse_mobileprovision_file(mobileprovision)
    ids_codesign = set(_find_codesign_identities())
    for id_mpf in _get_identities_from_provisioning_profile(mpf):
        if id_mpf in ids_codesign:
            return id_mpf


def main(argv):
    parser = argparse.ArgumentParser(description="codesign wrapper")
    parser.add_argument("--mobileprovision", type=str, help="mobileprovision file")
    parser.add_argument("--codesign", type=str, help="path to codesign binary")
    parser.add_argument("--identity", type=str, help="specific identity to sign with")
    args, codesign_args = parser.parse_known_args()
    identity = args.identity
    if identity is None:
        identity = _find_codesign_identity(args.mobileprovision)
    # No identity was found, fail
    if identity == None:
        print("Unable to find identity on the system matching the ones in %s" % args.mobileprovision)
        return 1
    os.execve(args.codesign, [args.codesign, "-v", "--sign", identity] + codesign_args, os.environ)


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# RPatchO - Tool for patching dylibs for making use of an rpath setup for bundled distribution.
#
# This is mostly a reduced copy of https://github.com/pyinstaller/pyinstaller/blob/122a99659e4b19bb38475e5c9e35a540e29451c2/PyInstaller/utils/osx.py
# Original Copyright below:
#-----------------------------------------------------------------------------
# Copyright (c) 2014-2023, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License (version 2
# or later) with exception for distributing the bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#
# SPDX-License-Identifier: (GPL-2.0-or-later WITH Bootloader-exception)
#-----------------------------------------------------------------------------
"""
Tool for patching dylibs for making use of an rpath setup for bundled distribution.
"""

import os
import pathlib
import subprocess
import shutil
import sys

from macholib.mach_o import (
    LC_BUILD_VERSION,
    LC_CODE_SIGNATURE,
    LC_ID_DYLIB,
    LC_LOAD_DYLIB,
    LC_LOAD_UPWARD_DYLIB,
    LC_LOAD_WEAK_DYLIB,
    LC_PREBOUND_DYLIB,
    LC_REEXPORT_DYLIB,
    LC_RPATH,
    LC_SEGMENT_64,
    LC_SYMTAB,
    LC_VERSION_MIN_MACOSX,
)
from macholib.MachO import MachO
import macholib.util

def _set_dylib_dependency_paths(filename, target_rpath):
    """
    The actual implementation of set_dylib_dependency_paths functionality.

    Implicitly assumes that a single-arch thin binary is given.
    """

    # Relocatable commands that we should overwrite - same list as used by `macholib`.
    _RELOCATABLE = {
        LC_LOAD_DYLIB,
        LC_LOAD_UPWARD_DYLIB,
        LC_LOAD_WEAK_DYLIB,
        LC_PREBOUND_DYLIB,
        LC_REEXPORT_DYLIB,
    }

    #  :
    #  - LC_LOAD_DYLIB (or any member of _RELOCATABLE list): dylib load commands (dependent libraries)
    #  - LC_RPATH: rpath definitions
    #  - LC_ID_DYLIB: dylib's identity
    binary = MachO(filename)

    dylib_id = None
    rpaths = set()
    linked_libs = set()

    for header in binary.headers:
        for cmd in header.commands:
            lc_type = cmd[0].cmd
            if lc_type not in _RELOCATABLE and lc_type not in {LC_RPATH, LC_ID_DYLIB}:
                continue

            # Decode path, strip trailing NULL characters
            path = cmd[2].decode('utf-8').rstrip('\x00')

            if lc_type in _RELOCATABLE:
                linked_libs.add(path)
            elif lc_type == LC_RPATH:
                rpaths.add(path)
            elif lc_type == LC_ID_DYLIB:
                dylib_id = path

    del binary

    # If dylib has identifier set, compute the normalized version, in form of `@rpath/basename`.
    normalized_dylib_id = None
    if dylib_id:
        normalized_dylib_id = str(pathlib.PurePath('@rpath') / pathlib.PurePath(dylib_id).name)

    # Find dependent libraries that should have their prefix path changed to `@rpath`. If any dependent libraries
    # end up using `@rpath` (originally or due to rewrite), set the `rpath_required` boolean to True, so we know
    # that we need to add our rpath.
    changed_lib_paths = []
    rpath_required = False
    for linked_lib in linked_libs:
        # Leave system dynamic libraries unchanged.
        if macholib.util.in_system_path(linked_lib):
            continue

        # The older python.org builds that use system Tcl/Tk framework have their _tkinter.cpython-*-darwin.so
        # library linked against /Library/Frameworks/Tcl.framework/Versions/8.5/Tcl and
        # /Library/Frameworks/Tk.framework/Versions/8.5/Tk, although the actual frameworks are located in
        # /System/Library/Frameworks. Therefore, they slip through the above in_system_path() check, and we need to
        # exempt them manually.
        _exemptions = [
            '/Library/Frameworks/Tcl.framework/',
            '/Library/Frameworks/Tk.framework/',
        ]
        if any([x in linked_lib for x in _exemptions]):
            continue

        # This linked library will end up using `@rpath`, whether modified or not...
        rpath_required = True

        new_path = str(pathlib.PurePath('@rpath') / pathlib.PurePath(linked_lib).name)
        if linked_lib == new_path:
            continue

        changed_lib_paths.append((linked_lib, new_path))

    # Gather arguments for `install-name-tool`
    install_name_tool_args = []

    # Modify the dylib identifier if necessary
    if normalized_dylib_id and normalized_dylib_id != dylib_id:
        install_name_tool_args += ["-id", normalized_dylib_id]

    # Changed libs
    for original_path, new_path in changed_lib_paths:
        install_name_tool_args += ["-change", original_path, new_path]

    # Remove all existing rpaths except for the target rpath (if it already exists). `install_name_tool` disallows using
    # `-delete_rpath` and `-add_rpath` with the same argument.
    for rpath in rpaths:
        if rpath == target_rpath:
            continue
        install_name_tool_args += [
            "-delete_rpath",
            rpath,
        ]

    # If any of linked libraries use @rpath now and our target rpath is not already added, add it.
    # NOTE: @rpath in the dylib identifier does not actually require the rpath to be set on the binary...
    if rpath_required and target_rpath not in rpaths:
        install_name_tool_args += [
            "-add_rpath",
            target_rpath,
        ]

    # If we have no arguments, finish immediately.
    if not install_name_tool_args:
        return

    # Run `install_name_tool`
    cmd_args = ["install_name_tool", *install_name_tool_args, filename]
    p = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if p.returncode:
        raise SystemError(
            f"install_name_tool command ({cmd_args}) failed with error code {p.returncode}!\noutput: {p.stdout}"
        )

# main

# Example:
# $ rpatcho "@loader_dir/../Frameworks" libtest.dylib
#

n = len(sys.argv)

if n < 3:
    print(f"{sys.argv[0]} [rpath] [file]")
    print(f"{sys.argv[0]} \"@loader_dir/../Frameworks\" libtest.dylib")
    exit(1)

_set_dylib_dependency_paths(sys.argv[n-1], sys.argv[n-2])

# RPatchO

Tool for patching dylibs for making use of an rpath setup for bundled distribution.

Normalizes the `LC_ID_DYLIB` of the dylib to allow for bundled distribution. Adjusts all `LC_LOAD_DYLIB` commands that load a non system library to make use of the `rpath`. Adds a `LC_RPATH` that points to the provided path.

### Setup

```
pip3 install -r requirements.txt
```

### Running

The first parameter is the rpath we want to use in the bundle. Commonly "@loader_dir/../Frameworks" is the right choice.
The second parameter is the library we want to mutate. Note: Modifications are done in place - create backups before running!

```
python3 rpatcho.py "@loader_dir/../Frameworks" libtest.dylib
```

### Validation

Use `otool` for getting the load commands.

```
otool -l libtest.dylib
```

Make sure the dylib filename matches the `LC_ID_DYLIB` filename portion - adjust the dylib filename to match if needed.

### Credits

This is mostly a reduced copy of a piece of [PyInstaller](https://github.com/pyinstaller/pyinstaller) - see [PyInstaller/utils/osx.py](https://github.com/pyinstaller/pyinstaller/blob/122a99659e4b19bb38475e5c9e35a540e29451c2/PyInstaller/utils/osx.py)

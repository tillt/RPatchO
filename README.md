# RPatchO

Tool for patching dylibs for making use of an rpath setup for bundled distribution.

### Setup

pip3 install -r requirements.txt

### Running

python3 rpatcho.py "@loader_dir/../Frameworks" libtest.dylib

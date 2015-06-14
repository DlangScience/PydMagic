# PydMagic
Ipython/Jupyter magic for inline D code in a python notebook

The very basics, nothing pretty so far. Depends on pyd (https://github.com/ariovistus/pyd)

To install, just enter
```
%install_ext https://raw.githubusercontent.com/DlangScience/PydMagic/master/pyd_magic.py
```
in any ipython instance.

To use, first enter
```
%load_ext pyd_magic
```

then write your pyd extension in a cell marked with ```%%pyd``` e.g.

```
%%pyd
import pyd.pyd;
import std.stdio;

string hello() {
    return "Hello World!";
}

string hello(int b)
{
    import std.conv;
    return b.to!string;
}

extern(C) void PydMain() {
    def!(hello)();
    def!(hello, PyName!"hello_int", string function(int))();
    module_init();
}
```
and run. After it has finished building, your extension should be automatically imported and ready to use. Builds are cached just like with cython magic. Some basic flags are supported as arguments to ```%%pyd``` such as ```--compile-args```, please see the calls marked ```@magic_arguments.argument(``` in the source code for more info.

I have tested on OS X and linux. Everything works fine on linux, but on OS X you can't import more than one extension per python instance (including modifications of the same extension) or python will crash. This is due to shared libraries not being supported on OS X.

This code is heavily based on and partially verbatim from the the ```%%cython``` magic implementation.

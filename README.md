# PydMagic
Ipython/Jupyter magic for inline D code in a python notebook

The very basics, nothing pretty so far. Depends on pyd (https://github.com/ariovistus/pyd)

To install, just enter
```
%install_ext https://raw.githubusercontent.com/debjan/ipython-recipes-magic/master/recipes.py
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
and run. After it has finished building, your extension should be automatically imported and ready to use. Builds are cached just like with cython magic.

This code is heavily based on and partially verbatim from the the '''%%cython''' magic implementation.

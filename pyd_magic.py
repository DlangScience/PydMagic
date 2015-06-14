from IPython.core import magic_arguments
from IPython.core.magic import cell_magic, magics_class, Magics
from IPython.utils.path import get_ipython_cache_dir
from IPython.utils import py3compat
import sys
import os
import io
import time
import imp

sys.stdout.errors = ''
sys.stderr.errors = ''

try:
    import hashlib
except ImportError:
    import md5 as hashlib

from distutils.core import Distribution
from distutils.command.build_ext import build_ext

import pyd.support

_loaded = False

@magics_class
class PydMagics(Magics):
    def __init__(self, shell):
        super(PydMagics, self).__init__(shell)
        self._reloads = {}
        self._code_cache = {}
        
    def _import_all(self, module):
        for k,v in module.__dict__.items():
            if not k.startswith('__'):
                self.shell.push({k:v})
        
    @magic_arguments.magic_arguments()
    @magic_arguments.argument(
        '-c', '--compile-args', action='append', default=[],
        help="Extra flags to pass to compiler via the `extra_compile_args` "
             "Extension flag (can be specified  multiple times)."
    )
    @magic_arguments.argument(
        '--link-args', action='append', default=[],
        help="Extra flags to pass to linker via the `extra_link_args` "
             "Extension flag (can be specified  multiple times)."
    )
    @magic_arguments.argument(
        '-l', '--lib', action='append', default=[],
        help="Add a library to link the extension against (can be specified "
             "multiple times)."
    )
    @magic_arguments.argument(
        '-n', '--name',
        help="Specify a name for the Pyd module."
    )
    @magic_arguments.argument(
        '-L', dest='library_dirs', metavar='dir', action='append', default=[],
        help="Add a path to the list of libary directories (can be specified "
             "multiple times)."
    )
    @magic_arguments.argument(
        '-I', '--include', action='append', default=[],
        help="Add a path to the list of include directories (can be specified "
             "multiple times)."
    )
    @magic_arguments.argument(
        '-f', '--force', action='store_true', default=False,
        help="Force the compilation of a new module, even if the source has been "
             "previously compiled."
    )
    @magic_arguments.argument(
        '--compiler', action='store', default='dmd',
        help="Specify the D compiler to be used. Default is DMD"
    )
    
    @cell_magic
    def pyd(self, line, cell):
        args = magic_arguments.parse_argstring(self.pyd, line)
        code = cell if cell.endswith('\n') else cell+'\n'
        lib_dir = os.path.join(get_ipython_cache_dir(), 'pyd')
        key = code, line, sys.version_info, sys.executable
        
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)
        
        if args.force:
            # Force a new module name by adding the current time to the
            # key which is hashed to determine the module name.
            key += time.time()
            
        if args.name:
            module_name = py3compat.unicode_to_str(args.name)
        else:
            module_name = "_cython_magic_" + hashlib.md5(str(key).encode('utf-8')).hexdigest()
        module_path = os.path.join(lib_dir, module_name + self.so_ext)

        have_module = os.path.isfile(module_path)
        need_pydize = not have_module
    
        if need_pydize:
            d_include_dirs = args.include
            pyd_file = os.path.join(lib_dir, module_name + '.d')
            pyd_file = py3compat.cast_bytes_py2(pyd_file, encoding=sys.getfilesystemencoding())
            with io.open(pyd_file, 'w', encoding='utf-8') as f:
                f.write(code)
            extension = pyd.support.Extension(module_name, [pyd_file],
                include_dirs = d_include_dirs,
                library_dirs = args.library_dirs,
                extra_compile_args = args.compile_args,
                extra_link_args = args.link_args,
                libraries = args.lib,
                build_deimos=True,
                d_lump=True
            )
            pyd.support.setup(ext_modules=[extension],script_name="setup.py",script_args=["build", "--build-lib", lib_dir, "-q", "--compiler="+args.compiler])
            
        if not have_module:
            self._code_cache[key] = module_name

        module = imp.load_dynamic(module_name, module_path)
        self._import_all(module)
            
    @property
    def so_ext(self):
        """The extension suffix for compiled modules."""
        try:
            return self._so_ext
        except AttributeError:
            self._so_ext = self._get_build_extension().get_ext_filename('')
            return self._so_ext
        
    def _clear_distutils_mkpath_cache(self):
        """clear distutils mkpath cache
        prevents distutils from skipping re-creation of dirs that have been removed
        """
        try:
            from distutils.dir_util import _path_created
        except ImportError:
            pass
        else:
            _path_created.clear()
        
    def _get_build_extension(self):
        self._clear_distutils_mkpath_cache()
        dist = Distribution()
        config_files = dist.find_config_files()
        try:
            config_files.remove('setup.cfg')
        except ValueError:
            pass
        dist.parse_config_files(config_files)
        build_extension = build_ext(dist)
        build_extension.finalize_options()
        return build_extension

def load_ipython_extension(ip):
    global _loaded
    if not _loaded:
        ip.register_magics(PydMagics)
        _loaded = True

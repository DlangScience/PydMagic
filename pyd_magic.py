from IPython.core import magic_arguments
from IPython.core.magic import cell_magic, magics_class, Magics
from IPython.utils.path import get_ipython_cache_dir
from IPython.utils import py3compat
import sys
import os
import io
import time
import imp
import json
import subprocess
import shutil
import ast

from mergedict import ConfigDict

try:
    import hashlib
except ImportError:
    import md5 as hashlib

from distutils.core import Distribution
from distutils.command.build_ext import build_ext

import pyd.support

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
        '-n', '--name',
        help="Specify a name for the Pyd module."
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
        help="Specify the D compiler to be used. Default is dmd"
    )
    @magic_arguments.argument(
        '--compiler_type', action='store', default='dmd',
        help="Specify the compiler type, as in dmd, gdc, ldc or sdc. Needed if "
             "you are using a non-standard compiler name e.g. dmd_HEAD for your"
             "own personal build of dmd from git master HEAD"
    )
    @magic_arguments.argument(
        '--pyd_version', action='store', default='>=0.9.7',
        help="Specify the pyd version to use, as a dub version specifier "
             "see http://code.dlang.org/package-format#version-specs"
    )
    @magic_arguments.argument(
        '--dub_config', action='store', default='{}',
        help='''add your own compilation flags, dependencies etc. as json '''
             '''to be merged with dub.json e.g. {"libs":"fftw3"}. Note '''
             '''that spaces will be interpreted as starting a new argument, '''
             '''If you want spaces in your argument, wrap it in a string'''
    )
    @magic_arguments.argument(
        '--dub_args', action='store', default='',
        help="command line flags to dub. wrap in a string if you want to list "
             "multiple arguments."
    )
    @magic_arguments.argument(
        '--print_compiler_output', action='store_true',
        help="Print the output from the compilation process, even if compilation "
             "runs sucessfully"
    )
    
    @cell_magic
    def pyd(self, line, cell):
        
        args = magic_arguments.parse_argstring(self.pyd, line)
        code = 'import ppyd;\n\n\
                extern(C) void PydMain()\n{\n   \
                registerAll!(Alias!(__traits(parent, PydMain)))();\n\
                }\n\n'\
                + cell
        code = code if code.endswith('\n') else code+'\n'
        
        key = code, line, sys.version_info, sys.executable

        try:
            args.dub_config = json.loads(args.dub_config)
        except:
            args.dub_config = json.loads(ast.literal_eval(args.dub_config))
            pass

        try:
            args.dub_args = ast.literal_eval(args.dub_args)
        except:
            pass

        if args.force:
            # Force a new module name by adding the current time to the
            # key which is hashed to determine the module name.
            key += (time.time(),)
            args.dub_args = '--force ' + args.dub_args
            
        if args.name:
            module_name = py3compat.unicode_to_str(args.name)
        else:
            module_name = "_pyd_magic_" + hashlib.md5(str(key).encode('utf-8')).hexdigest()

        lib_dir = os.path.join(get_ipython_cache_dir(), 'pyd', module_name)
        
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)

        if os.name == 'nt':
            so_ext = '.dll'
        else:
            so_ext = '.so' #might have to go to dylib on OS X at some point???
        module_path = os.path.join(lib_dir, 'lib' + module_name + so_ext)

        have_module = os.path.isfile(module_path)
        need_pydize = not have_module
    
        if need_pydize:
            d_include_dirs = args.include
            pyd_file = os.path.join(lib_dir, module_name + '.d')
            pyd_file = py3compat.cast_bytes_py2(pyd_file, encoding=sys.getfilesystemencoding())
            with io.open(pyd_file, 'w', encoding='utf-8') as f:
                f.write(code)
                
            pyd_dub_file = os.path.join(lib_dir, 'dub.json')
            pyd_dub_file = py3compat.cast_bytes_py2(pyd_dub_file, encoding=sys.getfilesystemencoding())
            pyd_dub_selections_file = os.path.join(lib_dir, 'dub.selections.json')
            pyd_dub_selections_file = py3compat.cast_bytes_py2(pyd_dub_selections_file, encoding=sys.getfilesystemencoding())


            pyd_dub_json = json.loads('{}')
            pyd_dub_json['name'] = module_name
            pyd_dub_json['dependencies'] = { "pyd": args.pyd_version, "ppyd": ">=0.1.3" }
            pyd_dub_json['subConfigurations'] = { "pyd": "python{0}{1}".format(sys.version_info.major, sys.version_info.minor) }
            pyd_dub_json['sourceFiles'] = [pyd_file]
            pyd_dub_json['targetType'] = 'dynamicLibrary'
            pyd_dub_json['dflags'] = ['-fPIC']
            pyd_dub_json['libs'] = ['phobos2']
            pyd_dub_json['versions'] = ['PydPythonExtension']

            with io.open(pyd_dub_file, 'w', encoding='utf-8') as f:
                f.write(unicode(json.dumps(pyd_dub_json)+'\n', encoding='utf-8'))
            try:
                os.remove(pyd_dub_selections_file)
            except:
                pass

            dub_desc = json.loads(subprocess.check_output(["dub", "describe", "--root=" + lib_dir], universal_newlines = True))
            for pack in dub_desc['packages']:
                if pack['name'] == 'pyd':
                    _infraDir = os.path.join(pack['path'], 'infrastructure')
                    break

            if os.name == 'nt':
                boilerplatePath = os.path.join(_infraDir, 'd',
                        'python_dll_windows_boilerplate.d'
                        )
            else:
                boilerplatePath = os.path.join(_infraDir, 'd',
                        'python_so_linux_boilerplate.d'
                        )
            pyd_dub_json['sourceFiles'].append(boilerplatePath)

            if args.compiler == 'dmd':
                so_ctor_path = os.path.join(_infraDir, 'd', 'so_ctor.c')
                so_ctor_object_path = os.path.join(lib_dir, "so_ctor.o")
                subprocess.check_call(['cc', "-c", "-fPIC", "-o" + so_ctor_object_path, so_ctor_path])
                pyd_dub_json['sourceFiles'].append(so_ctor_object_path)

            mainTemplate = os.path.join(_infraDir, 'd', 'pydmain_template.d')
            mainTemplate = py3compat.cast_bytes_py2(mainTemplate, encoding=sys.getfilesystemencoding())
            mainTemplateOut = os.path.join(lib_dir, 'pydmain.d')
            mainTemplateOut = py3compat.cast_bytes_py2(mainTemplateOut, encoding=sys.getfilesystemencoding())
            with io.open(mainTemplate, 'r', encoding='utf-8') as t, io.open(mainTemplateOut, 'w', encoding='utf-8') as m:
                m.write(t.read() % {'modulename' : module_name})
            pyd_dub_json['sourceFiles'].append(mainTemplateOut)

            pyd_dub_json = ConfigDict(pyd_dub_json)
            pyd_dub_json.merge(args.dub_config)

            with io.open(pyd_dub_file, 'w', encoding='utf-8') as f:
                f.write(unicode(json.dumps(pyd_dub_json)+'\n', encoding='utf-8'))

            try:
                output = subprocess.check_output(["dub", "build", "--root=" + lib_dir] + args.dub_args.split(' '),
                        universal_newlines=True, stderr=subprocess.STDOUT)
            except (subprocess.CalledProcessError) as e:
                print(e.output)
                raise e
            if args.print_compiler_output:
                print(output)
            
        if not have_module:
            self._code_cache[key] = module_name

        module = imp.load_dynamic(module_name, module_path)
        self._import_all(module)
            
def load_ipython_extension(ip):
    ip.register_magics(PydMagics)

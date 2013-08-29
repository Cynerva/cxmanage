"""Generates .rst files for .py files encountered in the SRC_DIR

:author: Eric Vasquez
:contact: eric.vasquez@calxeda.com
:copyright: (c) 2012, Calxeda Inc.

"""

import os
import sys
import glob

# #
# The actual NAME of your API, as if you were to import it.
API_NAME = 'cxmanage_api'

# #
# SRC_DIR is one directory level up from the docs dir
# assuming a file structure like:
# +--API/
#       |---src_file1.py
#       |---src_fileN.py
#       +---docs/
#               |--Makefile
#               +--generate_api_rst.py
SRC_DIR = os.path.dirname(os.path.abspath('.'))
RST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'source')

# #
# Any files you don't want docs generated for (no extension needed)
#
# EXAMPLE: To exclude foo.py and bar.py ...
# BLACK_LIST = ['foo', 'bar']
#
BLACKLIST = ['__init__']

# #
# Add any custom title you want for a specific python source file.
#
# EXAMPLE:
# TITLES = {'some_obscure_script_name' : 'Some Less Obscure Title'}
#
TITLES = {
          'simg' : 'SIMG',
          'crc32' : 'CRC32',
          'ubootenv' : 'U-Boot Environment',
         }

def get_source(source_dir):
    """Iterates recursively over dirs and gets all of the <filename>.py files.


    :param source_dir: The (absolute) path to the source directory.
    :type source_dir: string

    :return: A mapping of file names to filename Titles.
    :rtype: dictionary
    """
    if (not source_dir.endswith('/')):
        source_dir += '/'

    source = {API_NAME : {}}
    paths = glob.glob(os.path.join(source_dir, '*.py'))
    for path in paths:
        f_path, _ = os.path.splitext(path)
        f_name = f_path.split(source_dir)[1]
        if (not f_name in BLACKLIST):
            if TITLES.has_key(f_name):
                source[API_NAME][f_name] = TITLES[f_name]
            else:
                source[API_NAME][f_name] = f_name.title()
        else:
            print 'Skipping docgen for source file: %s' % path

    return source

def parse_source(src_file):
    """Parses a given source file to get class and function names.

    :param src_file: A file path. (abspath)
    :type src_file: string
    :return: a dictionary mapping class to methods and a list of functions
    :rtype: dictionary

    """
    def _get_object_name(line):
        """Takes a class, function or method declaration and gets the name."""
        name = line.split()[1].split('(')[0].strip()
        return name.rstrip(':')

    #
    # Parse Source
    #
    classes, functions = {}, []
    with open(src_file, 'r') as file_:
        class_ = None
        lines = file_.readlines()

        for line in lines:
            if (line.startswith('class ')):
                name = _get_object_name(line)
                class_ = name
                classes[name] = []
            elif (line.startswith('    def ') and line.count('(')):
                if (class_):
                    name = _get_object_name(line)
                    if (not name.startswith('_')):
                        classes[class_].append(name)
            elif (line.startswith('def ') and line.count('(')):
                functions.append(_get_object_name(line))

    for class_name, function_names in classes.items():
        classes[class_name] = sorted(list(set(function_names)))

    return classes, sorted(list(set(functions)))

def main():
    """Entry point for this script."""
    src_files = get_source(SRC_DIR)
    for package, module in src_files.items():
        for module_name, module_title in module.items():
            doc = os.path.join(RST_DIR, '%s.rst' % module_name)
            with open('%s' % doc, 'w') as rst_file:
                print 'Generating Sphinx Docs for: %s' % doc
                py_src = os.path.join(SRC_DIR, '%s.py' % module_name)
                classes, functions = parse_source(py_src)
                rst_file.write(module_title + '\n')
                rst_file.write('_' * len(module_title) + '\n\n')

                if (len(functions) > 0):
                    rst_file.write('.. currentmodule:: %s.%s\n\n' %
                                   (package, module_name))
                    rst_file.write('.. autosummary::\n')
                    rst_file.write('    :nosignatures:\n\n')
                    for func in functions:
                        rst_file.write('    %s\n' % func)
                    rst_file.write('\n')

                if (classes != {}):
                    rst_file.write('.. currentmodule:: %s.%s\n\n' %
                                   (package, module_name))
                    rst_file.write('.. autosummary::\n')
                    rst_file.write('    :nosignatures:\n\n')
                    for class_name in classes.keys():
                        rst_file.write('    %s\n' % class_name)
                    rst_file.write('\n')
                    for class_name, function_list in classes.items():
                        if (len(function_list) > 0):
                            rst_file.write('    .. automethod::\n')
                            for function_name in function_list:
                                rst_file.write('        %s.%s\n' %
                                               (class_name, function_name))
                        rst_file.write('\n\n')

                for func in functions:
                    rst_file.write('.. autofunction:: %s\n' % func)

                for class_name in classes.keys():
                    rst_file.write('.. autoclass:: %s\n' % class_name)
                    rst_file.write('    :members:\n')
                    if (module_name not in BLACKLIST):
                        rst_file.write('    :inherited-members:\n')
                    rst_file.write('    :show-inheritance:\n')
                    rst_file.write('\n')


# Go!
if __name__ == '__main__':
    sys.exit(main())


# End of file: ./docs/generate_api_rst.py

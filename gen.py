#!/usr/bin/env python
#coding=utf-8
import sys
import clang.cindex
from clang.cindex import Config
from clang.cindex import CursorKind
from clang.cindex import _CXString
Config.set_compatibility_check(False)
#Config.set_library_path("/usr/lib")
clang.cindex.Config.set_library_path("/Library/Developer/CommandLineTools/usr/lib")

global todo 

def dumpnode(node, clas, output):
    spell = node.spelling or node.displayname
    #kind = str(node.kind)[str(node.kind).index('.')+1:]
    kind = node.kind
    access = node.access_specifier
    typ = node.type

    if output == None and spell == clas and (kind == CursorKind.CLASS_DECL or CursorKind.STRUCT_DECL):
        output = open(sys.argv[2]+'_decode.h','w')
        output.write('void decode(const char* j, void *c){'+ '\n')
        output.write('Document d;'+ '\n')
        output.write('d.Parse(json);'+ '\n')
        for i in node.get_children():
            dumpnode(i, clas, output)
        output.write('}'+ '\n')
        output.close()
    else:
#        if output != None and kind == CursorKind.FIELD_DECL:

        for i in node.get_children():
            dumpnode(i, clas, output)


    #print ' ' * indent,'spell {} access {} kind {} {}'.format(spell,access, kind, typ)
    #print '\n'.join(['%s:%s' % item for item in typ.__dict__.items()])

def check_argv():
    if len(sys.argv) != 3:
        print("Usage: gen.py [file name] [class name]")
        sys.exit()

def main():
    check_argv()
    index = clang.cindex.Index.create()
    tu = index.parse(sys.argv[1], ['-x', 'c++', '-std=c++11', '-D__CODE_GENERATOR__'])
    dumpnode(tu.cursor, sys.argv[2], None)

if __name__ == '__main__':
    main()

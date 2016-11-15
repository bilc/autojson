#!/usr/bin/env python
#coding=utf-8
import sys
import re
from string import Template

import clang.cindex
from clang.cindex import Config
from clang.cindex import TypeKind
from clang.cindex import CursorKind
from clang.cindex import AccessSpecifier
from clang.cindex import _CXString
Config.set_compatibility_check(False)
#Config.set_library_path("/usr/lib")
clang.cindex.Config.set_library_path("/Library/Developer/CommandLineTools/usr/lib")

outer_include_tpl = Template('''#include "$userfile"
#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"
#include <iostream>
using namespace rapidjson;
''')
outer_func_tpl = Template('''
void encode($typ &x, string &s) {
    Document d(kObjectType);
    encode_$typ(x, d, d.GetAllocator());
    StringBuffer buffer;
    Writer<StringBuffer> writer(buffer);
    d.Accept(writer);
    s=buffer.GetString();
}

''')

func_def_tpl = Template('''void encode_$objtype($objtype &x,Value &v, Document::AllocatorType& allocat)''')

simple_tpl = Template('''v.AddMember("$key", Value($obj).Move(), allocat);  
''')
string_tpl = Template('''v.AddMember("$key", Value($obj.c_str(), $obj.size()).Move(), allocat);  
''')
array_tpl = Template('''
{
Value tmp(kArrayType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){
    tmp.PushBack(Value($derefer*i).Move(), allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')
array_string_tpl = Template('''
{
Value tmp(kArrayType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){
    tmp.PushBack(Value(($derefer*i).c_str(), ($derefer*i).size()).Move(), allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')

class_tpl = Template('''
{
Value tmp(kObjectType);
encode_$typ($obj, tmp, allocat);
v.AddMember("$key", tmp, allocat);
}
''')

global shoplist
shoplist = {}

def has_one(origin, li):
    for a in li:
        if origin.find(a) != -1:
            return True
    return False

def dumpnode(node, wanted, output):
    name = node.spelling or node.displayname
    kind = node.kind
    kind_str = str(node.kind)[str(node.kind).index('.')+1:]
    access = node.access_specifier
    typ = node.type
    typ_kind = node.type.kind
    if typ_kind == TypeKind.POINTER:
        typ_str = typ.get_pointee().spelling
    else :
        typ_str = typ.spelling
    if output == False and kind == CursorKind.NAMESPACE:
        return 
    elif output == False and typ_str ==wanted and (kind == CursorKind.CLASS_DECL or kind == CursorKind.STRUCT_DECL):
        shoplist[wanted] = func_def_tpl.substitute(objtype=typ_str) + '{\n'
        for i in node.get_children():
            dumpnode(i, wanted, True)
        shoplist[wanted] += '}\n'
    else:
        if output == True and kind == CursorKind.FIELD_DECL and access == AccessSpecifier.PUBLIC and typ.is_const_qualified()== False:
            print name
            if typ_kind == TypeKind.POINTER:
                class_member = '(*(x.'+name+'))'
            else:
                class_member = 'x.'+name

            if has_one(typ_str, ['vector<', 'list<']):
                inner_typ = re.findall(r"< *(.+?) *>", typ_str)[0]
                if inner_typ.find('*') != -1:
                    derefe = '*'
                else:
                    derefe = ''
                if inner_typ.find('string') != -1:
                    shoplist[wanted] += array_string_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
                else:
                    shoplist[wanted] += array_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
            elif has_one(typ_str,['int','uint','float','double']):
                shoplist[wanted] += simple_tpl.substitute(key=name, typ=typ_str, obj=class_member)
            elif has_one(typ_str,['string']):
                shoplist[wanted] += string_tpl.substitute(key=name, typ=typ_str, obj=class_member)
            else:
                #shoplist[typ_str] = ''
                shoplist[wanted] += class_tpl.substitute(key=name, typ=typ_str, obj=class_member)

        for i in node.get_children():
            dumpnode(i, wanted, output)

def check_argv():
    if len(sys.argv) != 3:
        print("Usage: gen.py [file name] [class name]")
        sys.exit()

def main():
    check_argv()
    index = clang.cindex.Index.create()
    tu = index.parse(sys.argv[1], ['-x', 'c++', '-std=c++11', '-D__CODE_GENERATOR__'])

    shoplist[sys.argv[2]] = ''
    todo = True
    while todo:
        todo = False
        for k,v in shoplist.items():
            if v == '':
                todo = True
                dumpnode(tu.cursor, k, False)
    f = file('encode.cpp', 'w')
    f.write(outer_include_tpl.substitute(userfile=sys.argv[1]))
    #generate function declaration
    for k,v in shoplist.items():
        f.write(func_def_tpl.substitute(objtype=k)+';\n')
    #generate outer function 
    f.write(outer_func_tpl.substitute(typ=sys.argv[2]))
    #generate function implementation
    for k,v in shoplist.items():
        f.write(v)
        f.write('\n')
    f.close()
if __name__ == '__main__':
    main()

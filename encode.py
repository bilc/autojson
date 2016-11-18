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
class_tpl = Template('''
{
Value tmp(kObjectType);
encode_$typ($obj, tmp, allocat);
v.AddMember("$key", tmp, allocat);
}
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

array_class_tpl = Template('''
{
Value tmp(kArrayType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){

    Value tmp1(kObjectType);
    encode_$intyp(($derefer*i), tmp1, allocat);
    tmp.PushBack(tmp1, allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')

map_tpl = Template('''
{
Value tmp(kObjectType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){
    tmp.AddMember((*i).first, Value((*i).second).Move(), allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')

map_string_tpl = Template('''
{
Value tmp(kObjectType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){
    tmp.AddMember(i->first.c_str(), 
        Value(($derefer2 i->second).c_str(), ($derefer2 i->second).size()).Move(), allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')

map_class_tpl = Template('''
{
Value tmp(kObjectType);
for ($typ::iterator i = $obj.begin(); i!=$obj.end(); i++){
    Value tmp1(kObjectType);
    encode_$intyp($derefer (i->second), tmp1, allocat);
    tmp.AddMember(i->first.c_str(), tmp1, allocat);
}
v.AddMember("$key", tmp, allocat);
}
''')

global shoplist
shoplist = {}

def is_int(k):
    if k == TypeKind.CHAR_U or \
    k == TypeKind.CHAR16 or \
    k == TypeKind.CHAR32 or \
    k == TypeKind.CHAR_S or \
    k == TypeKind.SCHAR or \
    k == TypeKind.WCHAR or \
    k == TypeKind.SHORT or \
    k == TypeKind.INT or \
    k == TypeKind.LONG or \
    k == TypeKind.LONGLONG or \
    k == TypeKind.INT128 :
        return True
def is_uint(k):
    if k == TypeKind.UCHAR or \
    k == TypeKind.USHORT or \
    k == TypeKind.UINT or \
    k == TypeKind.ULONG or \
    k == TypeKind.ULONGLONG or \
    k == TypeKind.UINT128 :
        return True

def is_double(k):
    if k == TypeKind.FLOAT or \
    k == TypeKind.DOUBLE or \
    k == TypeKind.LONGDOUBLE:
        return True

def dumpnode(node, wanted):
    name = node.spelling or node.displayname
    kind = node.kind
    typ = node.type
    typ_str = typ.spelling

    if typ_str==wanted and (kind == CursorKind.CLASS_DECL or kind == CursorKind.STRUCT_DECL):
        shoplist[wanted] = func_def_tpl.substitute(objtype=typ_str) + '{\n'
        for i in node.get_children():
            dumpfield(i, wanted)
        shoplist[wanted] += '}\n'
    else:
        for i in node.get_children():
            dumpnode(i, wanted)

def dumpfield(node, wanted):
    kind = node.kind
    typ = node.type
    if kind != CursorKind.FIELD_DECL or node.access_specifier != AccessSpecifier.PUBLIC or typ.is_const_qualified()==True:
        return
    name = node.spelling or node.displayname
    typ_kind = node.type.kind
    typ_str = node.type.spelling
    class_member = 'x.'+name
    if typ_kind == TypeKind.POINTER:
        point_typ = typ.get_pointee()
        typ_kind = point_typ.kind
        typ_str = point_typ.spelling
        class_member = '(*(x.'+name+'))'

    if is_int(typ_kind) or is_uint(typ_kind) or is_double(typ_kind):#basic type
        shoplist[wanted] += simple_tpl.substitute(key=name, typ=typ_str, obj=class_member)
    elif typ_kind == TypeKind.RECORD:#class
        shoplist[typ_str] = ''
        shoplist[wanted] += class_tpl.substitute(key=name, typ=typ_str, obj=class_member)
    elif typ_str == 'string' or typ_str == 'std::string': #std::string  TypeKind::UNEXPOSED; string TypeKind.TYPEDEF
        shoplist[wanted] += string_tpl.substitute(key=name, typ=typ_str, obj=class_member)
    elif typ_kind == TypeKind.UNEXPOSED:#stl
        arg_typ = []
        template = ''
        for i in node.get_children():
            if i.kind == CursorKind.TEMPLATE_REF :
                template = i.spelling
            elif i.kind == CursorKind.TYPE_REF:
                arg_typ.append(i.type)
        #deal array stl
        if template == 'vector' or template == 'list':
            derefe = ''
            if typ_str.find('*') != -1:
                derefe = '*'

            if is_int(arg_typ[0]) or is_uint(arg_typ[0]) or is_double(arg_typ[0]):
                shoplist[wanted] += array_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
            elif arg_typ[0].spelling == 'string':
                shoplist[wanted] += array_string_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
            elif arg_typ[0].kind == TypeKind.RECORD:
                shoplist[arg_typ[0].spelling] = ''
                shoplist[wanted] += array_class_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe,intyp=arg_typ[0].spelling)
            else:
                print '%s.%s not support. line %s'% (wanted, name,sys._getframe().f_lineno)
                return
        #deal map
        elif template == 'map':
            derefe = ''
            if typ_str.find('*') != -1:
                derefe = '*'
            if arg_typ[0].spelling != 'string' and arg_typ[0].spelling != 'std::string':
                print '%s.%s not support. line %s'% (wanted, name, sys._getframe().f_lineno) 
                return
            if is_int(arg_typ[1]) or is_uint(arg_typ[1]) or is_double(arg_typ[1]):
                shoplist[wanted] += map_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
            elif arg_typ[1].spelling == 'string':
                shoplist[wanted] += map_string_tpl.substitute(key=name, typ=typ_str, obj=class_member, derefer=derefe)
            elif arg_typ[1].kind == TypeKind.RECORD:
                shoplist[arg_typ[1].spelling] = ''
                shoplist[wanted] += map_class_tpl.substitute(key=name, typ=typ_str, intyp=arg_typ[1].spelling, obj=class_member, derefer=derefe )
            else:
                print '%s.%s not support. line %s'% (wanted, name, sys._getframe().f_lineno)
                return
        else :
            print '%s.%s not support[type:%s, kind:%s]. line %s'% (wanted, name, typ_str, typ_kind, sys._getframe().f_lineno)
        
    else:
        print '%s.%s[type:%s, kind:%s] not support. line %s'% (wanted, name, typ_str, typ_kind, sys._getframe().f_lineno)

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
                dumpnode(tu.cursor, k)
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

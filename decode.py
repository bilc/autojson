#!/usr/bin/env python
#coding=utf-8
import sys
import re
import os
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
void decode(const char *s, $typ  &x) {
    Document d;
    d.Parse(s);
    decode_$typ(d, x);
}
''')

func_def_tpl = Template('''void decode_$objtype(const Value &d, $objtype &x)''')

pointer_init_tpl = Template(''' 
    if($obj == NULL) {
        $obj = new $typ();   
    }
''')

simple_tpl = Template('''if($doc.HasMember("$key") && $doc["$key"].Is$typ()) {
    $obj=$doc["$key"].Get$typ();
}
''')

array_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsArray()){
    const Value& a = d["$key"];
    for (SizeType i = 0; i < a.Size(); i++) 
        $obj.push_back(a[i].Get$typ());
}''')

class_tpl = Template('''
if($doc.HasMember("$key") && $doc.IsObject()){
    decode_$typ($doc["$key"], $obj);
}
''')

array_class_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsArray()){
    const Value& a = d["$key"];
    for (SizeType i = 0; i < a.Size(); i++) {
        $typ tmp;
        decode_$typ(a[i], tmp);
        $obj.push_back(tmp);
    }
}''')

array_class_pointer_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsArray()){
    const Value& a = d["$key"];
    for (SizeType i = 0; i < a.Size(); i++) {
        $typ *tmp = new $typ();
        decode_$typ(a[i], *tmp);
        $obj.push_back(tmp);
    }
}''')

map_tpl = Template('''
if($doc.HasMember("$key") && $doc.IsObject()){
    const Value& a = d["$key"];
    for(Value::ConstMemberIterator i = a.MemberBegin(); i!=a.MemberEnd(); i++){
        $obj[i->name.GetString()] = i->value.Get$typ();
    }
}
''')
map_class_tpl = Template('''
if($doc.HasMember("$key") && $doc.IsObject()){
    const Value& a = d["$key"];
    for(Value::ConstMemberIterator i = a.MemberBegin(); i!=a.MemberEnd(); i++){
        $typ tmp;
        decode_$typ(i->value, tmp);
        $obj[i->name.GetString()] = tmp;
    }
}
''')
map_class_pointer_tpl = Template('''
if($doc.HasMember("$key") && $doc.IsObject()){
    const Value& a = d["$key"];
    for(Value::ConstMemberIterator i = a.MemberBegin(); i!=a.MemberEnd(); i++){
        $typ *tmp = new $typ();
        decode_$typ(i->value, *tmp);
        $obj[i->name.GetString()] = tmp;
    }
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
    elif typ_str == 'std' and kind == CursorKind.NAMESPACE:
        return
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
        #unlock the pointer
        point_typ = typ.get_pointee()
        typ_kind = point_typ.kind
        typ_str = point_typ.spelling
        shoplist[wanted] += pointer_init_tpl.substitute(obj='x.'+name, typ=typ_str)
        class_member = '(*(x.'+name+'))'

    if is_int(typ_kind):
        shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
    elif is_uint(typ_kind):
        shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='Uint64', obj=class_member)
    elif is_double(typ_kind):
        shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
    elif typ_str == 'string' or typ_str == 'std::string': #std::string  TypeKind::UNEXPOSED; string TypeKind.TYPEDEF
        shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
    elif typ_kind == TypeKind.RECORD:
        shoplist[typ_str] = ''
        shoplist[wanted] += class_tpl.substitute(doc='d', key=name, typ=typ_str, obj=class_member)
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
            if is_int(arg_typ[0]):
                shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
            elif is_uint(arg_typ[0]):
                shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='Uint64', obj=class_member)
            elif is_double(arg_typ[0]):
                shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
            elif arg_typ[0].spelling == 'string':
                shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
            elif arg_typ[0].kind == TypeKind.RECORD:
                shoplist[arg_typ[0].spelling] = ''
                if typ_str.find('*') == -1:
                    shoplist[wanted] += array_class_tpl.substitute(doc='d', key=name, typ=arg_typ[0].spelling, obj=class_member)
                else:
                     shoplist[wanted] += array_class_pointer_tpl.substitute(doc='d', key=name, typ=arg_typ[0].spelling, obj=class_member)
            else:
                print '%s.%s not support. line %s'% (wanted, name,sys._getframe().f_lineno)
                return
        elif template == 'map': #map<string, T>  map<string, T*>
            if arg_typ[0].spelling != 'string' and arg_typ[0].spelling != 'std::string':
                print '%s.%s not support. line %s'% (wanted, name, sys._getframe().f_lineno)
                return
            if is_int(arg_typ[1]):
                shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
            elif is_uint(arg_typ[1]):
                shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='Uint64', obj=class_member)
            elif is_double(arg_typ[1]):
                shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
            elif arg_typ[1].spelling == 'string':
                shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
            elif arg_typ[1].kind == TypeKind.RECORD:
                if typ_str.find('*') != -1:
                    shoplist[wanted] += map_class_pointer_tpl.substitute(doc='d', key=name, typ=arg_typ[1].spelling, obj=class_member)
                else:
                    shoplist[wanted] += map_class_tpl.substitute(doc='d', key=name, typ=arg_typ[1].spelling, obj=class_member)
            else:
                print '%s.%s not support. line %s'% (wanted, name, sys._getframe().f_lineno)
                return
        else:
            print '%s.%s[type:%s, kind:%s] not support. line %s'% (wanted, name, typ_str, typ_kind, sys._getframe().f_lineno)
            return

def check_argv():
    if len(sys.argv) != 3:
        print("Usage: decode.py [file name] [class name]")
        sys.exit()

def main():
    check_argv()
    index = clang.cindex.Index.create()
    tu = index.parse(sys.argv[1], ['-x', 'c++', '-std=c++11', '-D__CODE_GENERATOR__'])

    shoplist[sys.argv[2]] = ''
    goon = True
    while goon:
        goon = False
        for k,v in shoplist.items():
            if v == '':
                goon = True
                dumpnode(tu.cursor, k)
    #if os.path.exists('gen') == False:
    #    os.mkdir('gen')
    f_h = file('decode_%s.h'%sys.argv[2], 'w')
    f_h.write('#include "%s"\nvoid decode(const char *s, %s &x);'%(sys.argv[1], sys.argv[2]))
    f_h.close()

    f = file('decode_%s.cpp'%sys.argv[2], 'w')
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


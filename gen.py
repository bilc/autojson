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

func_head_tpl = Template('''void decode_$objtype(const Value &d, $objtype &x)''')

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
    #clas = typ.get_canonical()
    if output == False and kind == CursorKind.NAMESPACE:
        return 
    elif output == False and typ_str ==wanted and (kind == CursorKind.CLASS_DECL or kind == CursorKind.STRUCT_DECL):
        shoplist[wanted] = func_head_tpl.substitute(objtype=typ_str) + '{\n'
        for i in node.get_children():
            dumpnode(i, wanted, True)
        shoplist[wanted] += '}\n'
    else:
        if output == True and kind == CursorKind.FIELD_DECL and access == AccessSpecifier.PUBLIC and typ.is_const_qualified()== False:
            if typ_kind == TypeKind.POINTER:
                class_member = '*(x.'+name+')'
            else:
                class_member = 'x.'+name
            #print 'member:', wanted, name,'real_type:', typ_str,' ok ', class_member
            if has_one(typ_str, ['map<']):
                inner_typ1 = re.findall(r"map< *(.+?),", typ_str)[0]
                inner_typ2 = re.findall(r", *(.+?) *>", typ_str)[0]
                if inner_typ1 != 'string' and inner_typ1 != 'std::string':
                    print '%s.%s cannot work: key must be string'%(wanted,name)
                    return
                if has_one(inner_typ2, ['int', 'uint', 'char']):
                    shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
                elif has_one(inner_typ2, ['float', 'double']):
                    shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
                elif has_one(inner_typ2, ['string']):
                    shoplist[wanted] += map_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
                else:
                    if inner_typ2.find('*') != -1 :
                        inner_typ2 = re.findall(r'([^ ]{1,})', inner_typ2)[0]
                        shoplist[wanted] += map_class_pointer_tpl.substitute(doc='d', key=name, typ=inner_typ2, obj=class_member)
                    else:
                        shoplist[wanted] += map_class_tpl.substitute(doc='d', key=name, typ=inner_typ2, obj=class_member)
                    shoplist[inner_typ2] = ''
                
            elif  has_one(typ_str, ['vector<', 'list<']):
                #get inner type in <>
                inner_typ = re.findall(r"< *(.+?) *>", typ_str)[0]
                if has_one(typ_str, ['int', 'uint', 'char']):
                    shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
                elif has_one(typ_str, ['float', 'double']):
                    shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
                elif has_one(typ_str, ['string']):
                    shoplist[wanted] += array_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
                else:
                    if inner_typ.find('*') != -1 :
                        inner_typ = re.findall(r'([^ ]{1,})', inner_typ)[0]
                        shoplist[wanted] += array_class_pointer_tpl.substitute(doc='d', key=name, typ=inner_typ, obj=class_member)
                    else:
                        shoplist[wanted] += array_class_tpl.substitute(doc='d', key=name, typ=inner_typ, obj=class_member)
                    shoplist[inner_typ] = ''
            elif has_one(typ_str, ['int', 'uint']):
                shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='Int64', obj=class_member)
            elif has_one(typ_str, ['float', 'double']):
                shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='Double', obj=class_member)
            elif has_one(typ_str, ['string']):
                shoplist[wanted] += simple_tpl.substitute(doc='d',key=name, typ='String', obj=class_member)
            else:
                shoplist[typ_str] = ''
                shoplist[wanted] += class_tpl.substitute(doc='d', key=name, typ=typ_str, obj=class_member)

        for i in node.get_children():
            dumpnode(i, wanted, output)


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

    shoplist[sys.argv[2]] = ''
    todo = True
    while todo:
        todo = False
        for k,v in shoplist.items():
            if v == '':
                todo = True
                dumpnode(tu.cursor, k, False)

    f = file('decode.cpp', 'w')
    f.write('#include "'+sys.argv[1]+'"\n')
    f.write('''#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"

using namespace rapidjson;
''')
    #generate function declaration
    for k,v in shoplist.items():
        f.write(func_head_tpl.substitute(objtype=k)+';\n')
    f.write('\n')
    #generate called function 
    f.write('void decode(const char *json, ' +sys.argv[2]+ ' &x) {\n' +
'Document d;\nd.Parse(json);\n' +
'decode_'+sys.argv[2]+'(d,x);\n' +
'}\n\n'
)
    #generate function implementation
    for k,v in shoplist.items():
        f.write(v)
        f.write('\n')
    f.close()
if __name__ == '__main__':
    main()

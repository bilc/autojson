#!/usr/bin/env python
#coding=utf-8
import sys
from string import Template

import clang.cindex
from clang.cindex import Config
from clang.cindex import CursorKind
from clang.cindex import _CXString
Config.set_compatibility_check(False)
#Config.set_library_path("/usr/lib")
clang.cindex.Config.set_library_path("/Library/Developer/CommandLineTools/usr/lib")

func_head_tpl = Template('''
void decode_$objtype(Value &d, $objtype &x){
''')
simple_tpl = Template('''if($doc.HasMember("$key") && $doc["$key"].Is$typ()) $obj=$doc["$key"].Get$typ();''')

array_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsArray()){
    const Value& a = d["$key"];
    for (SizeType i = 0; i < a.Size(); i++) 
        $obj.push_back(a[i].Get$typ());
}''')

class_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsObject()){
    decode_$typ($doc["$key"].GetObject(), $obj);
}
''')

array_class_tpl = Template('''
if($doc.HasMember("$key") && $doc["$key"].IsArray()){
    const Value& a = d["$key"];
    for (SizeType i = 0; i < a.Size(); i++) {
        $typ tmp;
        decode_$typ($doc["$key"].GetObject(), tmp);
        $obj.push_back(tmp);
    }
}''')


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
    typ_str = typ.spelling
    #clas = typ.get_canonical()
    if output == False and kind == CursorKind.NAMESPACE:
        return 
    elif output == False and typ_str ==wanted and (kind == CursorKind.CLASS_DECL or kind == CursorKind.STRUCT_DECL):
        print func_head_tpl.substitute(objtype=typ_str)
        for i in node.get_children():
            dumpnode(i, wanted, True)
        print  '}\n'
        shoplist[typ_str] = True

    else:
        if output == True and kind == CursorKind.FIELD_DECL:
            if  has_one(typ_str, ['vector<', 'list<']):
                if has_one(typ_str, ['int', 'uint']):
                    print array_tpl.substitute(doc='d',key=name, typ='Int64', obj='x.'+name)
                elif has_one(typ_str, ['float', 'double']):
                    print array_tpl.substitute(doc='d',key=name, typ='Double', obj='x.'+name)
                elif has_one(typ_str, ['string']):
                    print array_tpl.substitute(doc='d',key=name, typ='String', obj='x.'+name)
                else:
                    print array_class_tpl.substitute(doc='d', key=name, typ=typ_str, obj='x.'+name)
            elif has_one(typ_str, ['int', 'uint']):
                print simple_tpl.substitute(doc='d',key=name, typ='Int64', obj='x.'+name)
            elif has_one(typ_str, ['float', 'double']):
                print simple_tpl.substitute(doc='d',key=name, typ='Double', obj='x.'+name)
            elif has_one(typ_str, ['string']):
                print simple_tpl.substitute(doc='d',key=name, typ='String', obj='x.'+name)
            else:
                shoplist[typ_str] = False
                print class_tpl.substitute(doc='d', key=name, typ=typ_str, obj='x.'+name )

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

    shoplist[sys.argv[2]] = False
    todo = True
    while todo:
        todo = False
        for k,v in shoplist.items():
            if v == False:
                todo = True
                dumpnode(tu.cursor, k, False)

if __name__ == '__main__':
    main()

#include "stu.h"
#include "encode_Stu.h"
#include "decode_Stu.h"

int main(){
    Stu stu;
    string str;
    stu.id = 1;
    stu.school = "NEU";
    Per *p = new Per();
    p->name = "father";
    p->age = 50;
    p->desc = new string("farmer");
    stu.pFather = p;

    Per f1;
    f1.name = "Tom";
    f1.age =20;
    f1.desc = new string("boy");
    stu.friends.push_back(f1);
    encode(stu, str);
    printf("%s\n", str.c_str());

    Stu stu2;
    decode(str.c_str(), stu2);
    string str2;
    encode(stu2, str2);
    printf("%s\n", str2.c_str());
}

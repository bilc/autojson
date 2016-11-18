#ifndef _STU_H
#define _STU_H

#include <string>
#include <vector>
#include <list>
#include <map>

using std::string;
using std::vector;

struct Per {
    std::string name;
    int age;
    string *desc;
    Per():desc(new string()){}
};

class Stu {
    public:
    int id;
    string school;
    Per *pFather;
    Per mother;
    vector<Per> friends;
    std::list<Per*>  teachers;
    std::map<string, Per*>  mates;
    Stu():pFather(new Per()){
    }
};
#endif

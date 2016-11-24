Introduction  
---
Autojson can generate cpp code for converting between cpp class and json. Its result code is based on rapidjson.   
-dev language: python  
-platforms: mac and linux  
-json character: utf8  
-depend libclang and rapidjson  

Install  
---
generate tool need:   
pip install clang  

generated code need:   
install https://github.com/miloyip/rapidjson    

Support Grammar  
---
-T i; T * i; T can be basic data type(int,uint,long,float,double...), string, and user-defined class.  
-Container<T> i; Container<T*> i; Container * i; Container can be list, vector.  
-Map< string, T> i; Map< string, T*> i; Map< string, T> * i;  

Incompatible Grammar  
---
-c-style array like 'int a[10];' or 'char * str; int strLen;'. It should be 'vector<int> a;' or 'string str;'.  
-container embed container, like vector< list< T>>  
-the other containers, except list,vector and map  
-user-defined template  

Usage  
---
>encode.py  file  className  
>decode.py  file  className  

generate file:  
encode_className.h  encode_className.cpp  
decode_className.h  decode_className.cpp  

function:  
void encode(className &x, std::string &s);  
void decode(const char *s, className &x);  


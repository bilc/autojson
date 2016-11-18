Introduction  
---
Autojson is a tool generating rapidjson code for converting between cpp class and json.   
It is written by python.  
-platforms: mac and linux.  
-json character: utf8  

Install  
---
pip install clang  
install https://github.com/miloyip/rapidjson    

Incompatible Grammar  
---
-container embed container, like vector<list<T>>  
-except list,vector and map, the other containers     
-user-defined template  
-user-defined class without default constructor  

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


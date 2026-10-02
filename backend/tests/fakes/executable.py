"""Solutions are data for fake agents; never compiled or executed on the host."""

import json

from app.infrastructure.application import StarterProjectRepository


def executable_solution(slug: str, quality="good"):
    source = StarterProjectRepository().starter_dir(slug)
    app = (source / "src/App.tsx").read_text(encoding="utf-8")
    if slug == "broken-signup-validation":
        app = app.replace(
            "setEmail(e.target.value);setDone(false)",
            "setEmail(e.target.value);setErrors(validate(e.target.value,password));setDone(false)",
        )
        app = app.replace(
            "setPassword(e.target.value);setDone(false)",
            "setPassword(e.target.value);setErrors(validate(email,e.target.value));setDone(false)",
        )
        helper = "validation.ts"
        content = """export function validate(email:string,password:string):{email?:string;password?:string}{
 const errors:{email?:string;password?:string}={};
 if(!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email.trim())) errors.email='Enter a valid email address.';
 if(password.length<8) errors.password='Use at least 8 characters.';
 return errors;
}"""
    else:
        app = app.replace(
            "onClick={()=>setQuery('')}", "onClick={()=>{setQuery('');setCategory('all')}}"
        )
        helper = "filter.ts"
        content = """type Product={id:number;name:string;category:string;price:number};
export function filterProducts(items:Product[],query:string,category:string){
return items.filter(p=>(category==='all'||p.category===category)&&p.name.toLowerCase().includes(query.trim().toLowerCase()));
}"""
    if quality == "partial":
        app = (source / "src/App.tsx").read_text(encoding="utf-8")
    if quality == "bad":
        content = (source / ("src/" + helper)).read_text(
            encoding="utf-8"
        ) + "\n// no behavioral change\n"
        app = (source / "src/App.tsx").read_text(encoding="utf-8")
    if quality == "build_failure":
        content = "invalid TypeScript {"
    if quality == "unsafe":
        return json.dumps({"files": [{"path": "package.json", "content": "{}"}]})
    return json.dumps(
        {
            "files": [
                {"path": "src/App.tsx", "content": app},
                {"path": "src/" + helper, "content": content},
            ]
        }
    )

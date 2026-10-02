import React, {useState} from 'react';
import {validate} from './validation';
export default function App(){
 const [email,setEmail]=useState(''),[password,setPassword]=useState('');
 const [errors,setErrors]=useState<{email?:string;password?:string}>({});
 const [done,setDone]=useState(false);
 function submit(e:React.FormEvent){e.preventDefault();const next=validate(email,password);setErrors(next);setDone(!Object.keys(next).length)}
 return <><p className="eyebrow">YOUR NEXT CHAPTER</p><h1>A little space.<br/>For big ideas.</h1><p>Join Forma and make room for your next project.</p><section><h2>Create your account</h2><form noValidate onSubmit={submit}><label>Email address<input name="email" aria-label="Email address" value={email} onChange={e=>{setEmail(e.target.value);setDone(false)}} aria-describedby="email-error"/></label><p id="email-error" role="alert">{errors.email}</p><label>Password<input name="password" aria-label="Password" type="password" value={password} onChange={e=>{setPassword(e.target.value);setDone(false)}} aria-describedby="password-error"/></label><p id="password-error" role="alert">{errors.password}</p><small>Use at least 8 characters.</small><button type="submit">Create account</button><p role="status">{done?'Account created':''}</p></form></section></>;
}

"use client";
import { API_ORIGIN as api } from "../api-client";
import {useState} from "react";
import Link from "next/link";
import {apiErrorMessage} from "../api-errors";
export default function Reset(){
  const [email,setEmail]=useState(""),[msg,setMsg]=useState("");
  async function submit(e:React.FormEvent){
    e.preventDefault();
    try{const response=await fetch(`${api}/api/auth/password-reset`,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"include",body:JSON.stringify({email})});const data=await response.json();setMsg(data.detail||"Request could not be completed.")}
    catch(error){setMsg(apiErrorMessage(error,"The password reset service is unavailable."))}
  }
  return <main className="formpage"><form className="formcard" onSubmit={submit}><Link className="brand" href="/"><span className="mark">V</span>voicedesk realty</Link><h1 style={{marginTop:28}}>Reset password</h1><p>Enter your account email to request a reset link.</p><label className="field">Email address<input className="fieldinput" type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label>{msg&&<div role="alert" className="error">{msg}</div>}<button className="button full">Request reset link</button><div className="foot"><Link href="/login">Back to login</Link></div></form></main>
}

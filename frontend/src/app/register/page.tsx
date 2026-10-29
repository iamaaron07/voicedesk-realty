"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { registrationError, safeInternalPath } from "../auth-utils";
import { apiErrorMessage } from "../api-errors";

const api=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
function RegisterForm(){
  const [email,setEmail]=useState(""),[password,setPassword]=useState(""),[confirm,setConfirm]=useState(""),[err,setErr]=useState("");
  const router=useRouter(),params=useSearchParams();
  async function submit(e:React.FormEvent){e.preventDefault();const validationError=registrationError(password,confirm);if(validationError){setErr(validationError);return}setErr("");try{const r=await fetch(`${api}/api/auth/register`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Unable to create account.");router.push(safeInternalPath(params.get("next")))}catch(e){setErr(apiErrorMessage(e,"Unable to create account."))}}
  return <main className="formpage"><form className="formcard" onSubmit={submit}><Link className="brand" href="/"><span className="mark">V</span>voicedesk realty</Link><h1 style={{marginTop:28}}>Create your account</h1><p>Start with just an email and password.</p><label className="field">Email address<input className="fieldinput" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="field">Set password<input className="fieldinput" type="password" required minLength={10} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}/><span className="muted">At least 10 characters, with a letter and number.</span></label><label className="field">Confirm password<input className="fieldinput" type="password" required autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)}/></label>{err&&<div role="alert" className="error">{err}</div>}<button className="button full">Create account</button><div className="foot">Already have an account? <Link href={`/login${params.get("next")?`?next=${encodeURIComponent(safeInternalPath(params.get("next")))}`:""}`}>Log in</Link></div></form></main>
}
export default function Register(){return <Suspense fallback={<main className="formpage">Loading…</main>}><RegisterForm/></Suspense>}

"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { safeInternalPath } from "../auth-utils";
import { apiErrorMessage } from "../api-errors";

const api=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
function LoginForm(){
  const [email,setEmail]=useState(""),[password,setPassword]=useState(""),[show,setShow]=useState(false),[err,setErr]=useState("");
  const router=useRouter(),params=useSearchParams();
  async function submit(e:React.FormEvent){e.preventDefault();setErr("");try{const r=await fetch(`${api}/api/auth/login`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const d=await r.json();if(!r.ok)throw Error(d.detail||"Unable to log in.");router.push(safeInternalPath(params.get("next")))}catch(e){setErr(apiErrorMessage(e,"Unable to log in."))}}
  return <main className="formpage"><form className="formcard" onSubmit={submit}><Link className="brand" href="/"><span className="mark">V</span>voicedesk realty</Link><h1 style={{marginTop:28}}>Welcome back</h1><p>Log in to continue to your VoiceDesk account.</p><label className="field">Email address<input className="fieldinput" type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="field">Password<div style={{display:"flex",position:"relative"}}><input className="fieldinput" type={show?"text":"password"} required autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={show?"Hide password":"Show password"} onClick={()=>setShow(!show)} style={{position:"absolute",right:12,top:12,border:0,background:"transparent",cursor:"pointer"}}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label><div style={{textAlign:"right",fontSize:13}}><Link href="/reset-password">Forgot password?</Link></div>{err&&<div role="alert" className="error">{err}</div>}<button className="button full">Log in</button><div className="foot">New to VoiceDesk? <Link href={`/register${params.get("next")?`?next=${encodeURIComponent(safeInternalPath(params.get("next")))}`:""}`}>Create an account</Link></div></form></main>
}
export default function Login(){return <Suspense fallback={<main className="formpage">Loading…</main>}><LoginForm/></Suspense>}

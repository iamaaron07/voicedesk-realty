"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const api=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type Booking={id:number;property_title:string;start_at:string;status:string;calendar_mode:string};
type Property={id:number;title:string;locality:string;price:number};
type Call={id:string;status:string;summary:string|null;duration_seconds:number|null;started_at:string};

export default function Account(){
  const router=useRouter();
  const [bookings,setBookings]=useState<Booking[]>([]),[saved,setSaved]=useState<Property[]>([]),[calls,setCalls]=useState<Call[]>([]),[msg,setMsg]=useState("Loading your account…");
  const load=useCallback(async()=>{
    try {
    const [bookingResponse,savedResponse,callResponse]=await Promise.all([
      fetch(`${api}/api/bookings`,{credentials:"include"}),
      fetch(`${api}/api/customer/saved-properties`,{credentials:"include"}),
      fetch(`${api}/api/private/calls`,{credentials:"include"}),
    ]);
    if([bookingResponse,savedResponse,callResponse].some(r=>r.status===401)){router.replace("/login?next=%2Faccount");return}
    if(!bookingResponse.ok||!savedResponse.ok||!callResponse.ok){setMsg("Could not load your account data.");return}
    setBookings(await bookingResponse.json());setSaved(await savedResponse.json());setCalls(await callResponse.json());setMsg("");
    } catch { setMsg("Could not reach the VoiceDesk API. Check your connection and try again."); }
  },[router]);
  useEffect(()=>{void load()},[load]);
  async function cancel(id:number){
    const response=await fetch(`${api}/api/bookings/${id}/cancel`,{method:"POST",credentials:"include"});
    if(!response.ok){setMsg("Could not cancel that appointment.");return}
    setMsg("Appointment cancelled.");void load();
  }
  return <main className="wrap"><header className="nav"><Link className="brand" href="/">← VoiceDesk Realty</Link><button className="button light" onClick={async()=>{await fetch(`${api}/api/auth/logout`,{method:"POST",credentials:"include"});router.push("/")}}>Log out</button></header><section className="section"><div className="eyebrow">Your VoiceDesk account</div><h1 style={{fontFamily:"Manrope"}}>Your home search</h1>{msg&&<p role="status" className="muted">{msg}</p>}<h2>Saved homes</h2>{saved.length?<div className="grid">{saved.map(p=><Link href={`/properties/${p.id}`} className="card cardbody" key={p.id}><h3>{p.title}</h3><p className="muted">{p.locality}</p><div className="price">₹{p.price.toLocaleString("en-IN")} / month</div></Link>)}</div>:<p className="muted">You have no saved homes yet. <Link href="/properties">Explore listings.</Link></p>}<h2 style={{marginTop:38}}>Appointments</h2>{bookings.length?<div className="grid" style={{gridTemplateColumns:"1fr 1fr"}}>{bookings.map(b=><article className="card cardbody" key={b.id}><h3>{b.property_title}</h3><p className="muted">{new Date(b.start_at).toLocaleString()} · {b.status}</p><p className="muted">{b.calendar_mode}</p>{(b.status==="requested"||b.status==="rescheduled"||b.status==="confirmed")&&<button className="button light" onClick={()=>cancel(b.id)}>Cancel appointment</button>}</article>)}</div>:<p className="muted">No appointments yet.</p>}<h2 style={{marginTop:38}}>Voice call history</h2>{calls.length?<div className="grid">{calls.map(c=><article className="card cardbody" key={c.id}><h3>{c.summary||"Summary pending"}</h3><p className="muted">{new Date(c.started_at).toLocaleString()} · {c.status}{c.duration_seconds!==null?` · ${Math.floor(c.duration_seconds/60)} min`:""}</p></article>)}</div>:<p className="muted">Your completed call summaries will appear here.</p>}</section></main>
}

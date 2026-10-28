import "./globals.css";
import type { Metadata } from "next";
export const metadata: Metadata={title:"VoiceDesk Realty | Find a place to call home",description:"Explore considered homes across Bengaluru with VoiceDesk Realty."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
const supabase=createClient('https://zrjmflymsbukwvsyqrkl.supabase.co','sb_publishable_mmO4XOewe9A6vS8mkxWg7Q_-fwpbHy5');
const authPanel=document.getElementById('authPanel');
const workspace=document.getElementById('quizWorkspace');
const status=document.getElementById('authStatus');
const login=document.getElementById('googleLoginBtn');
function setSignedIn(user){
 if(user){authPanel.classList.add('hidden');workspace.classList.remove('hidden');}
 else{workspace.classList.add('hidden');authPanel.classList.remove('hidden');}
}
login.addEventListener('click',async()=>{
 login.disabled=true;status.textContent='Connecting to Google…';
 const {error}=await supabase.auth.signInWithOAuth({provider:'google',options:{redirectTo:window.location.href.split('#')[0]}});
 if(error){status.textContent='Login error: '+error.message;login.disabled=false;}
});
const {data:{session},error}=await supabase.auth.getSession();
if(error){status.textContent='Could not verify login. Refresh and try again.';}
setSignedIn(session?.user||null);
supabase.auth.onAuthStateChange((_event,nextSession)=>setSignedIn(nextSession?.user||null));

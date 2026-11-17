import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const reduceMotion=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const canWebGL=(()=>{try{const c=document.createElement("canvas");return !!(window.WebGLRenderingContext&&(c.getContext("webgl")||c.getContext("experimental-webgl")));}catch{return false;}})();
const definitions=[
 ["Iridescence","A thin-film colour response that shifts as the viewing angle changes."],
 ["Index of refraction","The measure of how strongly light bends as it enters a material."],
 ["Dispersion","The separation of light into colours because wavelengths travel differently."],
 ["Transmission","The portion of light that passes through a material."],
 ["Roughness","The microscopic surface variation that softens reflections."]
];
function mount(){
 const hero=document.querySelector(".hero-section");
 if(!hero||hero.dataset.facetMounted)return;
 hero.dataset.facetMounted="1";
 hero.classList.add("facet-hero");
 const art=hero.querySelector(".hero-art"); if(art)art.style.display="none";
 const canvas=document.createElement("canvas");canvas.className="facet-canvas";canvas.setAttribute("aria-hidden","true");hero.prepend(canvas);
 const copy=hero.querySelector(".hero-copy");if(copy)copy.classList.add("facet-copy");
 const actions=hero.querySelector(".hero-actions");
 if(actions){
  const link=document.createElement("a");link.href="#facet-paper";link.className="facet-paper-link";link.textContent="Read paper →";link.addEventListener("click",e=>{e.preventDefault();shatter();});
  actions.append(link);
 }
 const paper=document.createElement("section");paper.className="facet-definitions";paper.id="facet-paper";paper.setAttribute("aria-hidden","true");
 paper.innerHTML='<button class="facet-back" type="button">← Back</button><div class="facet-def-inner"><span class="facet-eyebrow">PREPGRID MATERIAL NOTES</span><h2>Real learning, in five terms.</h2><div class="facet-terms">'+definitions.map(([a,b])=>'<p><strong>'+a+'</strong> — '+b+'</p>').join("")+'</div></div>';
 hero.after(paper);paper.querySelector(".facet-back").addEventListener("click",assemble);
 if(reduceMotion||!canWebGL){hero.classList.add("facet-static");return;}
 let renderer,scene,camera,group,raycaster,mouse,clock,raf,hovered=null,shattered=false,parts=[];
 try{
  renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:"high-performance"});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
  scene=new THREE.Scene();
  const w=hero.clientWidth,h=hero.clientHeight;
  camera=new THREE.PerspectiveCamera(30,w/h,.1,5000);camera.position.set(0,0,Math.max(w,h)*2.05);
  const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;pmrem.dispose();
  scene.environmentIntensity=.42;
  scene.add(new THREE.AmbientLight(0x9ea5c4,.55));
  const key=new THREE.DirectionalLight(0xdceaff,3.1);key.position.set(-w*.35,h*.55,Math.max(w,h)*.65);scene.add(key);
  const fill=new THREE.PointLight(0xb9abff,45,Math.max(w,h)*1.3);fill.position.set(w*.25,-h*.25,Math.max(w,h)*.3);scene.add(fill);
  group=new THREE.Group();scene.add(group);raycaster=new THREE.Raycaster();mouse=new THREE.Vector2(5,5);clock=new THREE.Clock();
  const S=w/900, gap=9*S, depth=13*S;
  const coords=[[[-.48,.42],[-.24,.42],[-.08,-.04],[-.32,-.42],[-.48,-.42]],[[-.24,.42],[.05,.42],[.18,.02],[-.08,-.04]],[ [.05,.42],[.47,.42],[.47,-.42],[.18,-.12],[.18,.02]],[[-.08,-.04],[.18,.02],[.18,-.12],[-.18,-.42],[-.32,-.42]],[[.18,.02],[.18,-.12],[.47,-.42],[.47,.42]]];
  const mat=()=>new THREE.MeshPhysicalMaterial({color:0x17171b,roughness:.36,metalness:.08,clearcoat:.7,clearcoatRoughness:.12,iridescence:.55,iridescenceIOR:1.3,iridescenceThicknessRange:[250,650],envMapIntensity:1.2,transparent:false});
  coords.forEach((pts,i)=>{
   const shape=new THREE.Shape();pts.forEach(([x,y],n)=>n?shape.lineTo(x*w*.88,y*h*.72):shape.moveTo(x*w*.88,y*h*.72));shape.closePath();
   const g=new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:2.6*S,bevelThickness:2.6*S,curveSegments:5});
   g.computeVertexNormals();const m=mat();const mesh=new THREE.Mesh(g,m);mesh.position.z=(i%2)*.7*S;mesh.userData={home:mesh.position.clone(),lift:0,tilt:0,idx:i,phase:i*.7};group.add(mesh);parts.push(mesh);
  });
  const planeW=w*.92,planeH=h*.84;
  const slab=new THREE.Mesh(new THREE.BoxGeometry(planeW,Math.max(12*S,8),depth*.8),new THREE.MeshPhysicalMaterial({color:0x19191f,roughness:.4,clearcoat:.75,envMapIntensity:1.2}));
  slab.position.set(0,0,-depth*.95);group.add(slab);
  function resize(){const r=hero.getBoundingClientRect();renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.position.z=Math.max(r.width,r.height)*2.05;camera.updateProjectionMatrix();}
  const ro=new ResizeObserver(resize);ro.observe(hero);resize();
  function pointer(e){const r=hero.getBoundingClientRect();mouse.x=((e.clientX-r.left)/r.width)*2-1;mouse.y=-((e.clientY-r.top)/r.height)*2+1;raycaster.setFromCamera(mouse,camera);const hits=raycaster.intersectObjects(parts,false);const next=hits[0]?.object||null;if(next!==hovered){hovered=next;parts.forEach(p=>{p.material.iridescence=p===hovered?1:.55;p.material.envMapIntensity=p===hovered?1.9:1.2;});}}
  hero.addEventListener("pointermove",pointer);
  hero.addEventListener("pointerleave",()=>{hovered=null;});
  let targetX=0,targetY=0,rotX=0,rotY=0;
  function animate(){
   raf=requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.04),t=clock.elapsedTime;
   if(!shattered){const r=hero.getBoundingClientRect();targetY=(mouse.x||0)*.12;targetX=-(mouse.y||0)*.09;rotX+=(targetX-rotX)*Math.min(1,dt*3.3);rotY+=(targetY-rotY)*Math.min(1,dt*3.3);group.rotation.x=rotX;group.rotation.y=rotY;
    parts.forEach((p,i)=>{const active=p===hovered;const target=active?50*S:0;p.userData.lift+=(target-p.userData.lift)*Math.min(1,dt*10);p.position.z=p.userData.home.z+p.userData.lift;p.rotation.x+=(active?.12:0-p.rotation.x)*Math.min(1,dt*7);p.rotation.y+=(active?.16:0-p.rotation.y)*Math.min(1,dt*7);p.position.x=p.userData.home.x+Math.sin(t*.35+p.userData.phase)*1.2*S;});
   }
   renderer.render(scene,camera);
  }
  animate();
  hero._facet={parts,group,renderer,raf};
 }catch(err){hero.classList.add("facet-static");canvas.remove();}
 function shatter(){if(shattered)return;shattered=true;paper.classList.add("visible");paper.setAttribute("aria-hidden","false");hero.classList.add("facet-shattering");if(hero._facet){hero._facet.parts.forEach((p,i)=>{p.userData.fly={x:(p.position.x||0)+(i-2)*95,y:-(i+1)*55,z:650+i*45,rx:(Math.random()-.5)*5,ry:(Math.random()-.5)*5,rz:(Math.random()-.5)*5};});const start=performance.now();function fly(now){const t=Math.min(1,(now-start)/760);hero._facet.parts.forEach((p,i)=>{const q=Math.max(0,Math.min(1,(t-i*.045)*1.12));const e=q*q*q;p.position.x+=((p.userData.fly.x-p.position.x)*e)*.08;p.position.y+=((p.userData.fly.y-p.position.y)*e)*.08;p.position.z+=((p.userData.fly.z-p.position.z)*e)*.08;p.rotation.x+=p.userData.fly.rx*.012;p.rotation.y+=p.userData.fly.ry*.012;p.rotation.z+=p.userData.fly.rz*.012;});if(t<1)requestAnimationFrame(fly);}requestAnimationFrame(fly);}}
 function assemble(){if(!shattered)return;shattered=false;paper.classList.remove("visible");paper.setAttribute("aria-hidden","true");hero.classList.remove("facet-shattering");if(hero._facet){hero._facet.parts.forEach(p=>{p.position.copy(p.userData.home);p.rotation.set(0,0,0);});}}
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",mount);else mount();
new MutationObserver(()=>{const h=document.querySelector(".hero-section");if(h&&!h.dataset.facetMounted)mount();}).observe(document.getElementById("viewContainer")||document.body,{childList:true,subtree:true});

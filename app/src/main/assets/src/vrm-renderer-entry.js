import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

let renderer=null,scene=null,camera=null,canvas=null,currentVrm=null,raf=0;
let lastTime=performance.now(),loadToken=0,motion={action:'IDLE',start:0,duration:0,context:{},fromRootX:0,toRootX:0};
let motionQueue=[],lookTarget=null,resizeObserver=null,visible=true;
let ground=null,groundRing=null,heldProp=null,heldObject=null,rootBaseX=0,visualRootX=0;

const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const ease=(x)=>0.5-0.5*Math.cos(Math.PI*clamp(x,0,1));

function ensure(canvasEl){
  if(renderer&&canvas===canvasEl)return;
  disposeRendererOnly();
  canvas=canvasEl;
  renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.08;
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  scene=new THREE.Scene();
  camera=new THREE.PerspectiveCamera(28,1,0.05,30);
  camera.position.set(0,1.05,3.15);
  camera.lookAt(0,1.0,0);
  scene.add(new THREE.HemisphereLight(0xbfefff,0x281d1a,1.42));
  const key=new THREE.DirectionalLight(0xffe7cf,3.1);key.position.set(1.7,3.1,2.4);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-2.5;key.shadow.camera.right=2.5;key.shadow.camera.top=3;key.shadow.camera.bottom=-1;scene.add(key);
  const rim=new THREE.DirectionalLight(0x65dfff,2.15);rim.position.set(-2.2,2.0,-2.0);scene.add(rim);
  const fill=new THREE.DirectionalLight(0x8affdf,0.72);fill.position.set(0.3,0.8,2.5);scene.add(fill);
  ground=new THREE.Mesh(new THREE.CircleGeometry(1.55,64),new THREE.MeshStandardMaterial({color:0x101923,roughness:.94,metalness:.04,transparent:true,opacity:.78}));
  ground.rotation.x=-Math.PI/2;ground.position.set(0,-0.008,0);ground.receiveShadow=true;scene.add(ground);
  groundRing=new THREE.Mesh(new THREE.RingGeometry(.72,1.18,64),new THREE.MeshBasicMaterial({color:0x64f2db,transparent:true,opacity:.055,side:THREE.DoubleSide}));
  groundRing.rotation.x=-Math.PI/2;groundRing.position.set(0,-0.002,0);scene.add(groundRing);
  lookTarget=new THREE.Object3D();lookTarget.position.set(0,1.35,4);scene.add(lookTarget);
  resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas);
  resize();
  if(!raf){lastTime=performance.now();raf=requestAnimationFrame(loop)}
}
function resize(){
  if(!renderer||!canvas)return;
  const r=canvas.getBoundingClientRect(),w=Math.max(1,Math.floor(r.width)),h=Math.max(1,Math.floor(r.height));
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
}
function disposeHeldProp(){
  if(!heldProp)return;
  try{heldProp.parent?.remove(heldProp)}catch(_){}
  try{heldProp.geometry?.dispose()}catch(_){}
  try{heldProp.material?.dispose()}catch(_){}
  heldProp=null;heldObject=null;
}
function disposeCurrent(){
  disposeHeldProp();motionQueue=[];visualRootX=0;rootBaseX=0;
  if(currentVrm){
    try{scene.remove(currentVrm.scene)}catch(_){}
    try{VRMUtils.deepDispose(currentVrm.scene)}catch(_){}
  }
  currentVrm=null;
}
function disposeRendererOnly(){
  if(resizeObserver){try{resizeObserver.disconnect()}catch(_){}resizeObserver=null}
  disposeCurrent();
  if(renderer){try{renderer.dispose()}catch(_){}renderer=null}
  scene=null;camera=null;canvas=null;
}
function frameVrm(vrm){
  vrm.scene.updateMatrixWorld(true);
  let box=new THREE.Box3().setFromObject(vrm.scene),size=new THREE.Vector3(),center=new THREE.Vector3();
  box.getSize(size);box.getCenter(center);
  if(size.y>0.05&&isFinite(size.y)){
    const scale=clamp(1.72/size.y,0.15,8);
    vrm.scene.scale.multiplyScalar(scale);vrm.scene.updateMatrixWorld(true);
    box=new THREE.Box3().setFromObject(vrm.scene);box.getCenter(center);
  }
  vrm.scene.position.x-=center.x;vrm.scene.position.z-=center.z;
  vrm.scene.position.y-=box.min.y;
  rootBaseX=vrm.scene.position.x;visualRootX=0;
  vrm.scene.updateMatrixWorld(true);
  box=new THREE.Box3().setFromObject(vrm.scene);box.getSize(size);
  const h=Math.max(.8,size.y),targetY=h*.54;
  camera.position.set(0,targetY+0.02,Math.max(2.1,h*1.72));
  camera.lookAt(0,targetY,0);
  lookTarget.position.set(0,targetY+0.12,4);
}
async function load(url,canvasId='vrmCanvas'){
  const el=document.getElementById(canvasId);if(!el)throw new Error('VRM_CANVAS_MISSING');
  ensure(el);const token=++loadToken;disposeCurrent();
  const loader=new GLTFLoader();loader.crossOrigin='anonymous';loader.register(parser=>new VRMLoaderPlugin(parser));
  const gltf=await loader.loadAsync(url);
  if(token!==loadToken){try{VRMUtils.deepDispose(gltf.scene)}catch(_){}throw new Error('VRM_LOAD_SUPERSEDED')}
  const vrm=gltf.userData.vrm;if(!vrm){try{VRMUtils.deepDispose(gltf.scene)}catch(_){}throw new Error('NOT_VRM')}
  try{VRMUtils.rotateVRM0(vrm)}catch(_){}
  try{VRMUtils.removeUnnecessaryVertices(vrm.scene)}catch(_){}
  try{VRMUtils.combineSkeletons(vrm.scene)}catch(_){}
  try{VRMUtils.combineMorphs(vrm)}catch(_){}
  vrm.scene.traverse(o=>{o.frustumCulled=false;if(o.isMesh){o.castShadow=true;o.receiveShadow=true}});
  currentVrm=vrm;scene.add(vrm.scene);frameVrm(vrm);
  if(vrm.lookAt)vrm.lookAt.target=lookTarget;
  motion={action:'IDLE',start:performance.now(),duration:0,context:{},fromRootX:0,toRootX:0};motionQueue=[];heldObject=null;disposeHeldProp();
  const expressions=vrm.expressionManager?Object.keys(vrm.expressionManager.expressionMap||{}):[];
  const bones=vrm.humanoid?Object.keys(vrm.humanoid.normalizedHumanBones||{}):[];
  return {ok:true,metaVersion:String(vrm.meta?.metaVersion??''),name:String(vrm.meta?.name??vrm.meta?.title??''),expressions,bones,springBones:!!vrm.springBoneManager};
}
function bone(name){try{return currentVrm?.humanoid?.getNormalizedBoneNode(name)||null}catch(_){return null}}
function rot(name,x=0,y=0,z=0,weight=1){
  const b=bone(name);if(!b)return;
  const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(x,y,z,'XYZ'));
  b.quaternion.slerp(q,clamp(weight,0,1));
}
function pos(name,x=0,y=0,z=0){
  const b=bone(name);if(!b)return;b.position.x+=x;b.position.y+=y;b.position.z+=z;
}
function setExpression(name,value){
  try{if(currentVrm?.expressionManager?.getExpression(name))currentVrm.expressionManager.setValue(name,clamp(value,0,1))}catch(_){}
}
function emitStatus(){
  try{window.dispatchEvent(new CustomEvent('c4-vrm-status',{detail:status()}))}catch(_){}
}
function targetX(context={}){
  const loc=String(context?.after?.location||context?.target||context?.before?.location||'').toLowerCase();
  if(loc.includes('left')||loc==='shelf')return -.55;
  if(loc.includes('right')||loc==='basket')return .58;
  if(loc==='desk')return .32;
  return 0;
}
function curlRightFingers(amount){
  const a=clamp(amount,0,1);
  ['rightIndexProximal','rightMiddleProximal','rightRingProximal','rightLittleProximal'].forEach(n=>rot(n,0,0,-1.0*a,a));
  ['rightIndexIntermediate','rightMiddleIntermediate','rightRingIntermediate','rightLittleIntermediate'].forEach(n=>rot(n,0,0,-.72*a,a));
  ['rightThumbProximal','rightThumbDistal'].forEach(n=>rot(n,0,-.22*a,-.58*a,a));
}
function makeHeldProp(id){
  id=String(id||'').toUpperCase();if(!id)return null;
  let geometry,material;
  if(id==='BALL'){geometry=new THREE.SphereGeometry(.075,28,20);material=new THREE.MeshStandardMaterial({color:0xf05f73,roughness:.42,metalness:.04})}
  else if(id==='BOOK'){geometry=new THREE.BoxGeometry(.115,.16,.028);material=new THREE.MeshStandardMaterial({color:0x5a77cc,roughness:.62,metalness:.02})}
  else{geometry=new THREE.BoxGeometry(.105,.105,.105);material=new THREE.MeshStandardMaterial({color:0xe7a65a,roughness:.55,metalness:.03})}
  const mesh=new THREE.Mesh(geometry,material);mesh.castShadow=true;mesh.receiveShadow=true;return mesh;
}
function setHeldObject(id){
  id=id?String(id).toUpperCase():null;
  if(id===heldObject&&heldProp)return;
  disposeHeldProp();heldObject=id;if(!id||!currentVrm)return;
  const hand=bone('rightHand');if(!hand)return;
  heldProp=makeHeldProp(id);if(!heldProp)return;
  heldProp.position.set(.015,-.055,.045);heldProp.rotation.set(.15,0,.12);hand.add(heldProp);
}
function queueMotor(action,context={}){
  if(action==='IDLE'){motionQueue=[];return}
  motionQueue.push({action,context});if(motionQueue.length>8)motionQueue=motionQueue.slice(-8);
}
function beginMotion(action,context,now){
  const durations={WAVE:1550,NOD:980,LOOK_AROUND:1850,STEP_LEFT:1250,STEP_RIGHT:1250,TAKE:1250,GRASP:1200,RELEASE:1120,PLACE:1160,MOVE:1320,LOOK:1050,IDLE:0};
  const hostX=Number(context?.after?.x),toX=Number.isFinite(hostX)?clamp(hostX,-2,2)*.18:visualRootX;
  motion={action,start:now,duration:durations[action]??0,context:context||{},fromRootX:visualRootX,toRootX:toX};
  emitStatus();
}
function advanceQueue(now){
  if(motion.action!=='IDLE')return;
  const next=motionQueue.shift();if(next)beginMotion(next.action,next.context,now);
}

function applyBlink(t){
  if(!currentVrm?.expressionManager)return;
  const cycle=4.35,phase=(t%cycle);
  let v=0;if(phase<.13){const q=phase/.13;v=Math.sin(Math.PI*q)}
  setExpression('blink',v);
}
function applyIdle(t){
  const breath=Math.sin(t*1.38);
  rot('spine',0.012*breath,0,0.006*Math.sin(t*.72),1);
  rot('chest',0.018*breath,0,0.008*Math.sin(t*.67),1);
  rot('neck',0.004*Math.sin(t*.83),0.006*Math.sin(t*.41),0,1);
}
function resetPose(){
  try{currentVrm?.humanoid?.resetNormalizedPose()}catch(_){}
}
function applyMotion(now){
  if(!currentVrm)return;
  const t=now/1000;resetPose();applyIdle(t);
  currentVrm.scene.position.x=rootBaseX+visualRootX;
  const action=motion.action||'IDLE';if(action==='IDLE'){advanceQueue(now);return}
  const p=motion.duration>0?clamp((now-motion.start)/motion.duration,0,1):1;
  const e=Math.sin(Math.PI*ease(p)),ctx=motion.context||{},tx=targetX(ctx);
  if(action==='WAVE'){
    rot('rightShoulder',0,0,-.16*e,e);rot('rightUpperArm',-0.18,0,-1.28,e);rot('rightLowerArm',0.02,0,-1.05,e);
    rot('rightHand',0.05*Math.sin(p*Math.PI*10),0,0.42*Math.sin(p*Math.PI*10),e);curlRightFingers(.06*e);
    rot('chest',0,0,-0.07*e,e);rot('neck',0,0.05*e,0,e);
  }else if(action==='NOD'){
    rot('neck',0.17*Math.sin(p*Math.PI*4)*e,0,0,e);rot('head',0.18*Math.sin(p*Math.PI*4)*e,0,0,e);
  }else if(action==='LOOK_AROUND'){
    rot('neck',0,0.35*Math.sin(p*Math.PI*2)*e,0,e);rot('head',0,0.28*Math.sin(p*Math.PI*2)*e,0,e);
    if(lookTarget)lookTarget.position.x=.78*Math.sin(p*Math.PI*2);
  }else if(action==='STEP_LEFT'||action==='STEP_RIGHT'){
    const gait=Math.sin(p*Math.PI*4),s=gait*e,lean=(action==='STEP_LEFT'?-1:1)*.055*e;
    rot('hips',0,0,lean,e);rot('chest',0,0,-lean*.7,e);
    rot('leftUpperLeg',0.30*s,0,0,e);rot('rightUpperLeg',-0.30*s,0,0,e);
    rot('leftLowerLeg',Math.max(0,-s)*0.34,0,0,e);rot('rightLowerLeg',Math.max(0,s)*0.34,0,0,e);
    rot('leftFoot',Math.max(0,s)*-.13,0,0,e);rot('rightFoot',Math.max(0,-s)*-.13,0,0,e);
    rot('leftUpperArm',-0.18*s,0,0.05,e);rot('rightUpperArm',0.18*s,0,-0.05,e);
    pos('hips',0,.022*Math.abs(gait)*e,0);
    visualRootX=motion.fromRootX+(motion.toRootX-motion.fromRootX)*ease(p);currentVrm.scene.position.x=rootBaseX+visualRootX;
  }else if(['TAKE','GRASP','RELEASE','PLACE','MOVE','LOOK'].includes(action)){
    if(lookTarget)lookTarget.position.x=tx;
    const side=tx<-.15?-1:tx>.15?1:0;
    rot('hips',0,-.05*side*e,0,e);rot('chest',.055,-.19*side,0.045*side,e);rot('neck',.03,-.15*side,0,e);
    rot('rightShoulder',0,-.08*side,-.12*e,e);rot('rightUpperArm',-.72,-.24*side,-.72,e);rot('rightLowerArm',-.70,0,-.30,e);rot('rightHand',-.08,0,-.08,e);
    const closing=(action==='TAKE'||action==='GRASP')?clamp((p-.38)/.32,0,1):(action==='RELEASE'||action==='PLACE')?1-clamp((p-.34)/.28,0,1):(heldObject?1:0);
    curlRightFingers(closing*e+(heldObject&&action==='LOOK'?.82:0));
    if((action==='TAKE'||action==='GRASP')&&p>.67&&!heldObject)setHeldObject(ctx.object||ctx.after?.held);
    if((action==='RELEASE'||action==='PLACE')&&p>.53&&heldObject)setHeldObject(null);
  }
  if(p>=1){
    if(Number.isFinite(motion.toRootX))visualRootX=motion.toRootX;
    const afterHeld=ctx?.after?.held;if(action==='TAKE'||action==='GRASP'){if(afterHeld)setHeldObject(afterHeld)}
    if(action==='RELEASE'||action==='PLACE'){if(!afterHeld)setHeldObject(null)}
    motion={action:'IDLE',start:now,duration:0,context:{},fromRootX:visualRootX,toRootX:visualRootX};if(lookTarget)lookTarget.position.x=0;emitStatus();advanceQueue(now);
  }
}
function motor(action,context={}){
  if(!currentVrm)return false;
  action=String(action||'IDLE').toUpperCase();
  const allowed=new Set(['WAVE','NOD','LOOK_AROUND','STEP_LEFT','STEP_RIGHT','TAKE','GRASP','RELEASE','PLACE','MOVE','LOOK','IDLE']);
  if(!allowed.has(action))return false;
  if(action==='IDLE'){motionQueue=[];motion={action:'IDLE',start:performance.now(),duration:0,context:{},fromRootX:visualRootX,toRootX:visualRootX};emitStatus();return true}
  if(motion.action==='IDLE')beginMotion(action,context,performance.now());else queueMotor(action,context);
  emitStatus();return true;
}
function loop(now){
  raf=requestAnimationFrame(loop);if(!renderer||!scene||!camera||!visible)return;
  const dt=Math.min(.05,(now-lastTime)/1000||.016);lastTime=now;
  if(currentVrm){applyMotion(now);applyBlink(now/1000);try{currentVrm.update(dt)}catch(_){}}
  renderer.render(scene,camera);
}
function setVisible(v){visible=!!v}
function status(){return {ready:!!currentVrm,action:motion.action,queue:motionQueue.map(x=>x.action),queueLength:motionQueue.length,heldObject,rootX:visualRootX,metaVersion:String(currentVrm?.meta?.metaVersion??''),springBones:!!currentVrm?.springBoneManager,expressions:currentVrm?.expressionManager?Object.keys(currentVrm.expressionManager.expressionMap||{}):[],bones:currentVrm?.humanoid?Object.keys(currentVrm.humanoid.normalizedHumanBones||{}):[]}}
function dispose(){++loadToken;disposeRendererOnly()}
window.C4VRM={load,motor,status,setVisible,dispose};
window.dispatchEvent(new CustomEvent('c4-vrm-ready'));

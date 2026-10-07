import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

let renderer=null,scene=null,camera=null,canvas=null,currentVrm=null,raf=0;
let lastTime=performance.now(),loadToken=0,motion={action:'IDLE',start:0,duration:0};
let lookTarget=null,resizeObserver=null,visible=true;

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
  renderer.toneMappingExposure=1.05;
  scene=new THREE.Scene();
  camera=new THREE.PerspectiveCamera(28,1,0.05,30);
  camera.position.set(0,1.05,3.15);
  camera.lookAt(0,1.0,0);
  scene.add(new THREE.HemisphereLight(0xbfefff,0x281d1a,1.55));
  const key=new THREE.DirectionalLight(0xffe7cf,3.2);key.position.set(1.7,3.1,2.4);scene.add(key);
  const rim=new THREE.DirectionalLight(0x65dfff,2.4);rim.position.set(-2.2,2.0,-2.0);scene.add(rim);
  const fill=new THREE.DirectionalLight(0x8affdf,0.8);fill.position.set(0.3,0.8,2.5);scene.add(fill);
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
function disposeCurrent(){
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
  vrm.scene.traverse(o=>{o.frustumCulled=false});
  currentVrm=vrm;scene.add(vrm.scene);frameVrm(vrm);
  if(vrm.lookAt)vrm.lookAt.target=lookTarget;
  motion={action:'IDLE',start:performance.now(),duration:0};
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
  const action=motion.action||'IDLE';
  if(action==='IDLE')return;
  const p=motion.duration>0?clamp((now-motion.start)/motion.duration,0,1):1;
  const e=Math.sin(Math.PI*ease(p));
  if(action==='WAVE'){
    rot('rightUpperArm',-0.22,0,-1.18,e);rot('rightLowerArm',0,0,-1.18,e);
    rot('rightHand',0.05*Math.sin(p*Math.PI*8),0,0.38*Math.sin(p*Math.PI*8),e);
    rot('chest',0,0,-0.08*e,e);
  }else if(action==='NOD'){
    rot('neck',0.18*Math.sin(p*Math.PI*4)*e,0,0,e);rot('head',0.16*Math.sin(p*Math.PI*4)*e,0,0,e);
  }else if(action==='LOOK_AROUND'){
    rot('neck',0,0.34*Math.sin(p*Math.PI*2)*e,0,e);rot('head',0,0.28*Math.sin(p*Math.PI*2)*e,0,e);
    if(lookTarget)lookTarget.position.x=0.75*Math.sin(p*Math.PI*2);
  }else if(action==='STEP_LEFT'||action==='STEP_RIGHT'){
    const dir=action==='STEP_LEFT'?-1:1,s=Math.sin(p*Math.PI*4)*e;
    rot('leftUpperLeg',0.22*s,0,0,e);rot('rightUpperLeg',-0.22*s,0,0,e);
    rot('leftLowerLeg',Math.max(0,-s)*0.28,0,0,e);rot('rightLowerLeg',Math.max(0,s)*0.28,0,0,e);
    rot('leftUpperArm',-0.12*s,0,0.08,e);rot('rightUpperArm',0.12*s,0,-0.08,e);
    pos('hips',0,0.018*Math.abs(s),0);currentVrm.scene.position.x+=dir*0.0008;
  }else if(['TAKE','GRASP','RELEASE','PLACE','MOVE','LOOK'].includes(action)){
    rot('rightUpperArm',-0.82,0,-0.72,e);rot('rightLowerArm',-0.62,0,-0.32,e);
    rot('chest',0.05,-0.13,0.04,e);rot('neck',0.02,-0.10,0,e);
  }
  if(p>=1){motion={action:'IDLE',start:now,duration:0};if(lookTarget)lookTarget.position.x=0}
}
function motor(action){
  if(!currentVrm)return false;
  action=String(action||'IDLE').toUpperCase();
  const durations={WAVE:1500,NOD:950,LOOK_AROUND:1800,STEP_LEFT:1250,STEP_RIGHT:1250,TAKE:1150,GRASP:1150,RELEASE:1100,PLACE:1100,MOVE:1250,LOOK:1000,IDLE:0};
  if(!(action in durations))return false;
  motion={action,start:performance.now(),duration:durations[action]};return true;
}
function loop(now){
  raf=requestAnimationFrame(loop);if(!renderer||!scene||!camera||!visible)return;
  const dt=Math.min(.05,(now-lastTime)/1000||.016);lastTime=now;
  if(currentVrm){applyMotion(now);applyBlink(now/1000);try{currentVrm.update(dt)}catch(_){}}
  renderer.render(scene,camera);
}
function setVisible(v){visible=!!v}
function status(){return {ready:!!currentVrm,action:motion.action,metaVersion:String(currentVrm?.meta?.metaVersion??''),springBones:!!currentVrm?.springBoneManager,expressions:currentVrm?.expressionManager?Object.keys(currentVrm.expressionManager.expressionMap||{}):[]}}
function dispose(){++loadToken;disposeRendererOnly()}
window.C4VRM={load,motor,status,setVisible,dispose};
window.dispatchEvent(new CustomEvent('c4-vrm-ready'));

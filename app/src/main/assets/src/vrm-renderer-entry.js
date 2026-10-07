import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

let renderer=null,scene=null,camera=null,canvas=null,currentVrm=null,raf=0;
let lastTime=performance.now(),loadToken=0,motion={action:'IDLE',start:0,duration:0,context:{},fromRootX:0,toRootX:0};
let motionQueue=[],lookTarget=null,resizeObserver=null,visible=true,vocal={until:0,startedAt:0,level:0,f0:220};
let presence={nextBlinkAt:0,blinkStart:0,blinkDuration:135},lookBaseY=1.35;
let ground=null,groundRing=null,heldProp=null,heldObject=null,rootBaseX=0,visualRootX=0;
let environment=null,roomProps=new Map(),environmentOrb=null,environmentMonitor=null,baseCameraY=1.05,keyLight=null;
let qualityMode='BALANCED',targetFps=45,lastRenderAt=0;

const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const ease=(x)=>0.5-0.5*Math.cos(Math.PI*clamp(x,0,1));

function ensure(canvasEl){
  if(renderer&&canvas===canvasEl)return;
  disposeRendererOnly();
  canvas=canvasEl;
  renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.35));
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
  keyLight=new THREE.DirectionalLight(0xffe7cf,3.1);keyLight.position.set(1.7,3.1,2.4);keyLight.castShadow=true;keyLight.shadow.mapSize.set(512,512);keyLight.shadow.camera.left=-2.5;keyLight.shadow.camera.right=2.5;keyLight.shadow.camera.top=3;keyLight.shadow.camera.bottom=-1;scene.add(keyLight);
  const rim=new THREE.DirectionalLight(0x65dfff,2.15);rim.position.set(-2.2,2.0,-2.0);scene.add(rim);
  const fill=new THREE.DirectionalLight(0x8affdf,0.72);fill.position.set(0.3,0.8,2.5);scene.add(fill);
  ground=new THREE.Mesh(new THREE.CircleGeometry(1.55,64),new THREE.MeshStandardMaterial({color:0x101923,roughness:.94,metalness:.04,transparent:true,opacity:.78}));
  ground.rotation.x=-Math.PI/2;ground.position.set(0,-0.008,0);ground.receiveShadow=true;scene.add(ground);
  groundRing=new THREE.Mesh(new THREE.RingGeometry(.72,1.18,64),new THREE.MeshBasicMaterial({color:0x64f2db,transparent:true,opacity:.055,side:THREE.DoubleSide}));
  groundRing.rotation.x=-Math.PI/2;groundRing.position.set(0,-0.002,0);scene.add(groundRing);
  lookTarget=new THREE.Object3D();lookTarget.position.set(0,1.35,4);scene.add(lookTarget);

  buildEnvironment();applyQuality();
  resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas);
  resize();
  if(!raf){lastTime=performance.now();raf=requestAnimationFrame(loop)}
}
function resize(){
  if(!renderer||!canvas)return;
  const r=canvas.getBoundingClientRect(),w=Math.max(1,Math.floor(r.width)),h=Math.max(1,Math.floor(r.height));
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
}
function applyQuality(){
  if(!renderer)return;
  const dpr=window.devicePixelRatio||1;
  const pr=qualityMode==='HIGH'?Math.min(dpr,2):qualityMode==='ECO'?Math.min(dpr,.9):Math.min(dpr,1.35);
  targetFps=qualityMode==='HIGH'?60:qualityMode==='ECO'?30:45;
  renderer.setPixelRatio(pr);
  renderer.shadowMap.enabled=qualityMode!=='ECO';
  if(keyLight){
    keyLight.castShadow=qualityMode!=='ECO';
    const size=qualityMode==='HIGH'?1024:512;
    if(keyLight.shadow.mapSize.x!==size){keyLight.shadow.mapSize.set(size,size);if(keyLight.shadow.map){try{keyLight.shadow.map.dispose()}catch(_){}keyLight.shadow.map=null}}
  }
  if(groundRing)groundRing.visible=qualityMode!=='ECO';
  resize();emitStatus();
}
function setQuality(mode){
  mode=String(mode||'BALANCED').toUpperCase();
  if(!['HIGH','BALANCED','ECO'].includes(mode))mode='BALANCED';
  qualityMode=mode;applyQuality();return status();
}

function mat(color,rough=.8,metal=.02,emissive=0x000000,ei=0){
  return new THREE.MeshStandardMaterial({color,roughness:rough,metalness:metal,emissive,emissiveIntensity:ei});
}
function box(w,h,d,material,x,y,z){
  const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;return m;
}
function buildEnvironment(){
  if(!scene||environment)return;
  environment=new THREE.Group();environment.name='C4_CINEMATIC_HOME_V1';scene.add(environment);
  scene.fog=new THREE.FogExp2(0x081018,.055);

  const floorMat=mat(0x1c2025,.93,.02);
  const floor3=box(5.8,.08,4.7,floorMat,0,-.06,-.42);environment.add(floor3);
  const back=box(5.8,3.45,.08,mat(0x18242d,.91,.02),0,1.66,-2.1);environment.add(back);
  const side=box(.08,3.45,4.7,mat(0x151f26,.94,.01),-2.86,1.66,-.42);environment.add(side);

  const windowFrame=box(1.72,1.58,.10,mat(0x2b3036,.62,.18),1.27,1.89,-2.00);environment.add(windowFrame);
  const windowGlow=box(1.49,1.34,.035,mat(0x4d6d8b,.25,.08,0x244f80,1.35),1.27,1.89,-1.93);environment.add(windowGlow);
  const skyline=new THREE.Group();
  for(let i=0;i<9;i++){
    const h=.20+((i*37)%7)*.08,w=.08+((i*19)%4)*.035;
    const b=box(w,h,.035,mat(0x101820,.8,.04,0x163c5b,.38),.66+i*.15,1.30+h/2,-1.88);
    skyline.add(b);
  }
  environment.add(skyline);

  const bedBase=box(1.60,.27,.88,mat(0x313d48,.92,.01),-1.47,.20,-.82);environment.add(bedBase);
  const bedTop=box(1.52,.13,.82,mat(0x56606b,.96,.01),-1.47,.41,-.82);environment.add(bedTop);
  const pillow=box(.52,.14,.37,mat(0x8b9399,.98,0),-1.92,.53,-.92);pillow.rotation.z=-.05;environment.add(pillow);

  const deskTop=box(1.38,.12,.56,mat(0x5b4337,.78,.03),1.34,.77,-.52);environment.add(deskTop);
  environment.add(box(.10,.75,.10,mat(0x2a2522,.86,.02),.82,.37,-.52));
  environment.add(box(.10,.75,.10,mat(0x2a2522,.86,.02),1.86,.37,-.52));

  const monitorFrame=box(.67,.44,.08,mat(0x111820,.50,.18),1.34,1.15,-.64);environment.add(monitorFrame);
  environmentMonitor=box(.57,.34,.025,mat(0x0a1d26,.25,.08,0x2fe3ff,1.35),1.34,1.15,-.58);environment.add(environmentMonitor);
  const stand=box(.08,.26,.08,mat(0x171c20,.62,.15),1.34,.91,-.62);environment.add(stand);

  for(let r=0;r<3;r++){
    environment.add(box(.92,.055,.24,mat(0x3b2b25,.82,.02),-2.12,1.12+r*.48,-1.88));
    for(let c=0;c<4;c++){
      const colors=[0x7c5e49,0x3f6478,0x694d78,0x657447];
      const book=box(.11,.26+.035*((r+c)%2),.17,mat(colors[(r+c)%colors.length],.78,.02),-2.42+c*.18,1.27+r*.48,-1.78);
      book.rotation.z=(c%2?-.03:.025);environment.add(book);
    }
  }

  environmentOrb=new THREE.Mesh(
    new THREE.SphereGeometry(.105,28,20),
    new THREE.MeshStandardMaterial({color:0x82fff1,emissive:0x42f3dc,emissiveIntensity:2.1,roughness:.18,metalness:.20})
  );
  environmentOrb.position.set(.62,.92,-.22);environmentOrb.castShadow=true;environment.add(environmentOrb);
  const orbLight=new THREE.PointLight(0x5ff9e8,2.4,1.7,2);orbLight.position.copy(environmentOrb.position);environment.add(orbLight);

  const rug=new THREE.Mesh(new THREE.CircleGeometry(1.22,64),new THREE.MeshStandardMaterial({color:0x1c3237,roughness:.97,metalness:.01}));
  rug.rotation.x=-Math.PI/2;rug.position.set(0,.012,-.25);rug.receiveShadow=true;environment.add(rug);

  ensureRoomProps();
}
function ensureRoomProps(){
  if(!environment)return;
  const specs={
    BALL:()=>new THREE.Mesh(new THREE.SphereGeometry(.085,28,20),mat(0x66d9c8,.42,.04)),
    BLOCK:()=>new THREE.Mesh(new THREE.BoxGeometry(.13,.13,.13),mat(0xd89a61,.58,.02)),
    BOOK:()=>new THREE.Mesh(new THREE.BoxGeometry(.13,.19,.035),mat(0x5473c8,.72,.01)),
  };
  for(const [id,mk] of Object.entries(specs)){
    if(roomProps.has(id))continue;
    const m=mk();m.name='ROOM_'+id;m.castShadow=true;m.receiveShadow=true;roomProps.set(id,m);environment.add(m);
  }
}
function roomLocation(name,id){
  const loc=String(name||'').toLowerCase();
  const map={
    'floor-left':[-.72,.10,.42],
    'floor-right':[.72,.10,.42],
    'shelf':[-2.08,1.50,-1.60],
    'desk':[1.12,.92,-.26],
    'basket':[1.92,.17,.12],
    'corner':[-2.35,.10,.25],
  };
  let p=map[loc]||[0,.10,.48];
  if(id==='BOOK'&&loc==='shelf')p=[-2.02,1.53,-1.56];
  return p;
}
function setRoomObjects(objects={}){
  ensureRoomProps();
  for(const [id,m] of roomProps.entries()){
    const o=objects?.[id]||null;
    if(!o||String(o.location||'').toLowerCase()==='held'){m.visible=false;continue}
    const p=roomLocation(o.location,id);m.visible=true;m.position.set(p[0],p[1],p[2]);
    m.rotation.set(id==='BOOK'?.08:0,id==='BOOK'?-.18:0,id==='BOOK'?.06:0);
  }
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
  environment=null;roomProps=new Map();environmentOrb=null;environmentMonitor=null;keyLight=null;scene=null;camera=null;canvas=null;
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
  baseCameraY=targetY+0.02;camera.position.set(0,baseCameraY,Math.max(2.25,h*1.72));
  camera.lookAt(0,targetY,-.08);
  lookBaseY=targetY+0.12;lookTarget.position.set(0,lookBaseY,4);
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
  motion={action:'IDLE',start:performance.now(),duration:0,context:{},fromRootX:0,toRootX:0};motionQueue=[];heldObject=null;disposeHeldProp();presence={nextBlinkAt:performance.now()+2100,blinkStart:0,blinkDuration:135};
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

function setBlink(value){
  if(!currentVrm?.expressionManager)return;
  const v=clamp(value,0,1);
  try{if(currentVrm.expressionManager.getExpression('blink')){currentVrm.expressionManager.setValue('blink',v);return}}catch(_){}
  try{if(currentVrm.expressionManager.getExpression('blinkLeft'))currentVrm.expressionManager.setValue('blinkLeft',v)}catch(_){}
  try{if(currentVrm.expressionManager.getExpression('blinkRight'))currentVrm.expressionManager.setValue('blinkRight',v)}catch(_){}
}
function applyBlink(now){
  if(!currentVrm?.expressionManager)return;
  if(!presence.nextBlinkAt)presence.nextBlinkAt=now+2200;
  if(!presence.blinkStart&&now>=presence.nextBlinkAt){
    presence.blinkStart=now;
    presence.blinkDuration=115+35*(.5+.5*Math.sin(now*.00113));
    const gap=2100+2600*(.5+.5*Math.sin(now*.00073+1.7));
    presence.nextBlinkAt=now+presence.blinkDuration+gap;
  }
  let v=0;
  if(presence.blinkStart){
    const p=(now-presence.blinkStart)/Math.max(80,presence.blinkDuration);
    if(p>=1)presence.blinkStart=0;else v=Math.sin(Math.PI*clamp(p,0,1));
  }
  setBlink(v);
}
function setAnyExpression(names,value){
  for(const name of names){try{if(currentVrm?.expressionManager?.getExpression(name)){currentVrm.expressionManager.setValue(name,clamp(value,0,1));return true}}catch(_){}}
  return false;
}
function applyVocal(now){
  if(!currentVrm?.expressionManager)return;
  if(now<vocal.until){
    const total=Math.max(80,vocal.until-vocal.startedAt),p=clamp((now-vocal.startedAt)/total,0,1);
    const envelope=Math.min(1,p/.10,Math.max(0,(1-p)/.14));
    const cadence=.012+clamp((vocal.f0-70)/630,0,1)*.004;
    const pulse=.48+.52*Math.pow(Math.sin(now*cadence),2);
    setAnyExpression(['aa','a'],clamp(vocal.level*pulse*envelope,0,1));
  }else{
    setAnyExpression(['aa','a'],0);vocal.level=0;
  }
}
function vocalize(durationMs=500,amplitude=.2,f0=220){
  if(!currentVrm)return false;
  const dur=clamp(Number(durationMs)||500,60,2200),amp=clamp(Number(amplitude)||0,0,0.35),now=performance.now();
  vocal.startedAt=now;vocal.until=now+dur;vocal.level=clamp(.16+amp*1.85,0,0.86);vocal.f0=clamp(Number(f0)||220,70,700);emitStatus();return true;
}

function applyIdle(t){
  const breath=Math.sin(t*1.38),slow=Math.sin(t*.31),counter=Math.sin(t*.23+1.2);
  pos('hips',.0045*slow,.004*(.5+.5*breath),0);
  rot('hips',0,.006*counter,.010*slow,1);
  rot('spine',0.013*breath,.004*counter,.007*Math.sin(t*.72),1);
  rot('chest',0.020*breath,-.006*counter,.010*Math.sin(t*.67),1);
  rot('leftShoulder',.005*breath,0,.007*breath,1);
  rot('rightShoulder',.005*breath,0,-.007*breath,1);
  rot('neck',.005*Math.sin(t*.83),.010*Math.sin(t*.41),.003*slow,1);
  rot('head',.003*Math.sin(t*.57),.006*Math.sin(t*.29+1.1),.0025*counter,1);
}
function applyPresenceGaze(now){
  if(!lookTarget||motion.action!=='IDLE')return;
  const t=now/1000;
  lookTarget.position.x=.035*Math.sin(t*.41)+.018*Math.sin(t*1.17+1.8);
  lookTarget.position.y=lookBaseY+.014*Math.sin(t*.37+.6);
  lookTarget.position.z=4;
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
    curlRightFingers(closing*e+((heldObject&&action==='LOOK')?0.82:0));
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
  const minFrame=1000/Math.max(1,targetFps);if(lastRenderAt&&now-lastRenderAt<minFrame)return;lastRenderAt=now;
  const dt=Math.min(.07,(now-lastTime)/1000||.016);lastTime=now;
  if(currentVrm){applyMotion(now);applyPresenceGaze(now);applyBlink(now);applyVocal(now);try{currentVrm.update(dt)}catch(_){}}
  const t=now/1000;
  if(environmentOrb){environmentOrb.position.y=.92+Math.sin(t*.9)*.018;environmentOrb.rotation.y=t*.5}
  if(environmentMonitor?.material)environmentMonitor.material.emissiveIntensity=1.20+.18*Math.sin(t*1.35);
  if(camera&&currentVrm){if(qualityMode==='ECO'){camera.position.y=baseCameraY;camera.position.x=0}else{camera.position.y=baseCameraY+Math.sin(t*.28)*.008;camera.position.x=Math.sin(t*.17)*.015}}
  renderer.render(scene,camera);
}
function updateWorld(state={}){
  if(!currentVrm)return false;
  if(state?.roomObjects)setRoomObjects(state.roomObjects);
  if(Object.prototype.hasOwnProperty.call(state,'heldObject'))setHeldObject(state.heldObject||null);
  emitStatus();return true;
}
function sync(state={}){
  if(!currentVrm)return false;
  const x=Number(state?.x);if(Number.isFinite(x))visualRootX=clamp(x,-2,2)*.18;
  setHeldObject(state?.heldObject||null);
  if(state?.roomObjects)setRoomObjects(state.roomObjects);
  motionQueue=[];motion={action:'IDLE',start:performance.now(),duration:0,context:{},fromRootX:visualRootX,toRootX:visualRootX};
  currentVrm.scene.position.x=rootBaseX+visualRootX;emitStatus();return true;
}
function setVisible(v){visible=!!v}
function status(){return {ready:!!currentVrm,action:motion.action,queue:motionQueue.map(x=>x.action),queueLength:motionQueue.length,heldObject,rootX:visualRootX,vocalActive:performance.now()<vocal.until,presence:'PHYSICAL_IDLE_V2',lookAt:!!currentVrm?.lookAt,environment:'CINEMATIC_HOME_3D_V1',qualityMode,targetFps,pixelRatio:renderer?renderer.getPixelRatio():0,shadows:renderer?renderer.shadowMap.enabled:false,roomProps:[...roomProps.keys()],metaVersion:String(currentVrm?.meta?.metaVersion??''),springBones:!!currentVrm?.springBoneManager,expressions:currentVrm?.expressionManager?Object.keys(currentVrm.expressionManager.expressionMap||{}):[],bones:currentVrm?.humanoid?Object.keys(currentVrm.humanoid.normalizedHumanBones||{}):[]}}
function dispose(){++loadToken;disposeRendererOnly()}
window.C4VRM={load,motor,vocalize,sync,updateWorld,setQuality,status,setVisible,dispose};
window.dispatchEvent(new CustomEvent('c4-vrm-ready'));

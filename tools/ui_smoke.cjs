// Browser transport/UI smoke only; Native below is an explicitly isolated test double.
const {chromium}=require('playwright');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:393,height:851}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  let running=false;let state={};
  window.NurseryNative=new Proxy({}, {get:(_,key)=>{
   const values={capabilities:()=>JSON.stringify({}),loadState:()=>JSON.stringify(state),commitState:s=>(state=JSON.parse(s),true),now:()=>Date.now(),
    runtimeInfo:()=>JSON.stringify({state:running?'RUNNING':'STOPPED',researchOnly:true}),organismInfo:()=>JSON.stringify({selected:true,runtimeAvailable:true,name:'TEST_ONLY.c4m',sha256:'TEST_ONLY'}),
    listOrganisms:()=>JSON.stringify([]),listSources:()=>JSON.stringify([]),copyText:()=>true,
    runtimeCommand:()=>JSON.stringify({accepted:false,error:'TEST_ONLY_USE_ASYNC'}),
    runtimeCommandAsync:s=>{const q=JSON.parse(s);setTimeout(()=>{
     if(q.type==='OPEN_SESSION')running=true;if(q.type==='CLOSE_SESSION')running=false;
     window.C4RuntimeResult(q.requestId,{accepted:true,requestId:q.requestId});
     if(q.type==='USER_MESSAGE')window.C4RuntimeEvent('DIAGNOSTIC',{text:'TEST ONLY · UNKNOWN',origin:'ADAPTER_DIAGNOSTIC',isNativeGeneratedSpeech:false,eventId:'test-'+q.requestId});
    },20)}
   };return values[key]||(()=>JSON.stringify({available:false,state:'TEST_ONLY',bodies:[]}));
  }});
 });
 await page.goto('file://'+path.resolve('app/src/main/assets/index.html'));await page.waitForTimeout(250);
 await page.locator('#brainStartChat').click();await page.waitForTimeout(100);
 for(let i=0;i<3;i++){await page.locator('#input').fill('Сообщение '+i);await page.locator('#form').evaluate(el=>el.requestSubmit())}
 await page.waitForTimeout(250);
 const result=await page.evaluate(()=>{
  window.C4RuntimeEvent('ASK',{eventId:'test-native-ask',origin:'NATIVE_G29_ASK',text:'TEST ONLY · native question'});
  window.C4RuntimeEvent('ASK',{eventId:'test-native-ask',origin:'NATIVE_G29_ASK',text:'TEST ONLY · native question'});
  return {training:buildTrainingBundle().lanes.trainingConversation,analysis:document.querySelector('#researchAnalysis').textContent,overflow:document.documentElement.scrollWidth>window.innerWidth+2};
 });
 if(errors.length)throw Error(errors.join('\n'));
 if(result.training.filter(m=>m.role==='user').length!==3)throw Error('Input lost');
 if(result.training.filter(m=>m.eventId==='test-native-ask').length!==1)throw Error('Duplicate ASK');
 if(result.training.some(m=>m.text==='TEST ONLY · UNKNOWN'))throw Error('Diagnostic contaminated conversation');
 if(!result.analysis.includes('UNKNOWN'))throw Error('Missing analysis');
 if(result.overflow)throw Error('Mobile overflow');
 console.log('BROWSER UI SMOKE PASS: async input, UNKNOWN lane, ASK dedup, training separation, 393px layout; not Android');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

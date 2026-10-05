import assert from 'node:assert/strict';
import {NurseryRuntime} from '../www/js/runtime.js';
class Mem { constructor(seed){this.m=new Map(seed?[["c4.nursery.state.v1",seed]]:[])} getItem(k){return this.m.get(k)||null} setItem(k,v){this.m.set(k,v)} }
const mem=new Mem(); const r=new NurseryRuntime(mem);
assert.equal(r.snapshot().mode,'AWAKE');
const id=r.openTextSource();
for(let i=0;i<10000;i++) assert.equal(r.ingestText('blue ',{sourceId:id}).accepted,true);
let s=r.snapshot(); assert.equal(s.sourceSeq,1); assert.equal(s.activeSource.id,id); assert.equal(s.activeSource.cursor,50000); assert.equal(s.eventSeq,10000); assert.equal(new Set(s.events.map(e=>e.sourceId)).size,1);
r.setMode('FROZEN'); const before=JSON.stringify(r.snapshot()); assert.equal(r.ingestText('MUST NOT MUTATE').accepted,false); assert.equal(JSON.stringify(r.snapshot()),before);
const restored=new NurseryRuntime(mem); assert.equal(restored.snapshot().mode,'FROZEN'); assert.equal(restored.snapshot().activeSource.cursor,50000);
restored.setMode('AWAKE'); assert.equal(restored.ingestText('resume',{sourceId:id}).accepted,true); assert.equal(restored.snapshot().activeSource.cursor,50006);
console.log('PASS runtime: 10k chunks = 1 provenance source; freeze immutable; durable cursor resumes');

// Execute the generated dashboard's actual JS. DOM-contract test, not layout.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const page=fs.readFileSync(process.argv[2], 'utf8');
const script=page.match(/<script>([\s\S]*?)<\/script>/)[1];
const identity=script.match(/const identity="([a-f0-9]{64})"/)[1];
const saved=new Map();
function load(source) {
  const notes={value:''}, button={}, players={nes:{pause(){this.paused=true;},play(){this.played=true;}},snes:{pause(){this.paused=true;},play(){this.played=true;}}};
  const seek={dataset:{player:'snes',time:'12.5'}};
  let exported;
  const document={getElementById(id){return id==='notes'?notes:id==='export'?button:players[id];},
    querySelectorAll(selector){return selector==='audio'?Object.values(players):[seek];},createElement(){return {click(){}};}};
  vm.runInNewContext(source,{document,Blob,JSON,Number,
    localStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)},
    URL:{createObjectURL(blob){exported=blob;return 'blob:test';},revokeObjectURL(){}}},{timeout:1000});
  return {notes,button,players,seek,exported:()=>exported};
}
const first=load(script);
first.notes.value='Silent walk; investigate packet transport';first.notes.oninput();
const reopened=load(script);assert.equal(reopened.notes.value,first.notes.value);
reopened.seek.onclick();assert.equal(reopened.players.snes.currentTime,12.5);
assert.equal(reopened.players.snes.played,true);assert.equal(reopened.players.nes.paused,true);
reopened.button.onclick();const exported=JSON.parse(await reopened.exported().text());
assert.equal(exported.evidence_sha256,identity);assert.equal(exported.release_approval,false);
assert.equal(exported.notes,first.notes.value);
const changed=load(script.replaceAll(identity,'f'.repeat(64)));
assert.equal(changed.notes.value,'');
console.log('Audio seeking, mutual pause, review save/reload/export and changed-hash reset passed.');

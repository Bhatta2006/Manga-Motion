import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';
const source=await fs.readFile(new URL('../src/music.ts',import.meta.url),'utf8');
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '(\.\/[^']+)'/g,(_,relative)=>`from '${new URL('../src/'+relative.slice(2),import.meta.url).href}'`);
const {canonicalSceneOffset,incomingTransition,loopOffset}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
test('canonical scene seeking follows reader incoming glides and page fades, never bed length',()=>{
  const panel=(scene,type='cut',dur=0)=>({scene,timeline:[{type:'camera',t:0,dur:1}],transition_out:{type,dur}});
  const script={version:2,scenes:{s:{beds:[{duration:120}]}},pages:[{panels:[panel('s','glide',.25),panel('s')]},{panels:[panel('s'),panel('s'),panel('other'),panel('s')]}]};
  assert.equal(incomingTransition(script,2),.2);assert.ok(Math.abs(canonicalSceneOffset(script,3)-4.65)<1e-9);
  assert.equal(canonicalSceneOffset(script,5),0);assert.equal(canonicalSceneOffset({...script,version:1},3),0);
  assert.equal(loopOffset({loop:[2,6]},9),3);
});

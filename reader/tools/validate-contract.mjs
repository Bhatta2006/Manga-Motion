import fs from 'node:fs';
import Ajv from 'ajv';
import {validateSupportedScript} from '../src/contract-v2.js';
const ajv=new Ajv({allErrors:true});
const validators=Object.fromEntries([1,2].map(v=>[v,ajv.compile(JSON.parse(fs.readFileSync(new URL(`../../schema/motionscript-v${v}.schema.json`,import.meta.url),'utf8')))]));
try {
  const script=await validateSupportedScript(JSON.parse(fs.readFileSync(0,'utf8')),validators);
  process.stdout.write(JSON.stringify({version:script.version,pages:script.pages.length,panels:script.pages.reduce((s,p)=>s+p.panels.length,0)}));
} catch(error) {
  process.stderr.write(String(error));process.exitCode=2;
}

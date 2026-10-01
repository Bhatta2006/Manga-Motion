import fs from 'node:fs';
import Ajv from 'ajv';
import {validateMotionScript} from '../src/contract.js';
const schema=JSON.parse(fs.readFileSync(new URL('../../schema/motionscript-v1.schema.json',import.meta.url),'utf8'));
const validate=new Ajv({allErrors:true}).compile(schema);
try {
  const script=validateMotionScript(JSON.parse(fs.readFileSync(0,'utf8')),validate);
  process.stdout.write(JSON.stringify({version:script.version,pages:script.pages.length,panels:script.pages.reduce((s,p)=>s+p.panels.length,0)}));
} catch(error) {
  process.stderr.write(String(error));process.exitCode=2;
}

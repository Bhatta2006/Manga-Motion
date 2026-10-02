// Bounded generator for this repository's local draft-07 schemas; no remote refs.
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../..');
const name=(version,key)=>`V${version}${key[0].toUpperCase()+key.slice(1)}`;
function render(s,v){
  if(s.$ref){if(!/^#\/definitions\/[A-Za-z0-9]+$/.test(s.$ref))throw Error('Nonlocal schema reference');return name(v,s.$ref.split('/').at(-1));}
  if(s.const!==undefined)return JSON.stringify(s.const);
  if(s.enum)return s.enum.map(x=>JSON.stringify(x)).join(' | ');
  if(s.oneOf)return s.oneOf.map(x=>`(${render(x,v)})`).join(' | ');
  if(Array.isArray(s.type))return s.type.map(type=>render({...s,type},v)).join(' | ');
  if(s.type==='array')return s.minItems===s.maxItems&&s.maxItems<=16?`[${Array.from({length:s.maxItems},()=>render(s.items,v)).join(', ')}]`:`Array<${render(s.items,v)}>`;
  if(s.type==='object'){
    const props=s.properties??{},required=new Set(s.required??[]);
    if(!Object.keys(props).length&&s.additionalProperties&&typeof s.additionalProperties==='object')return `Record<string, ${render(s.additionalProperties,v)}>`;
    if(s.additionalProperties!==false)throw Error('Unsupported mixed object type');
    return `{ ${Object.entries(props).map(([key,value])=>`${JSON.stringify(key)}${required.has(key)?'':'?'}: ${render(value,v)};`).join(' ')} }`;
  }
  if(s.type==='number'||s.type==='integer')return 'number';
  if(['string','boolean','null'].includes(s.type))return s.type;
  throw Error('Unsupported schema shape');
}
let output='// Generated from canonical MotionScript v1/v2 and corrections v1 schemas. Do not edit.\n';
for(const v of [1,2]){
  const schema=JSON.parse(await fs.readFile(path.join(root,`schema/motionscript-v${v}.schema.json`),'utf8'));
  for(const [key,value] of Object.entries(schema.definitions))output+=`export type ${name(v,key)} = ${render(value,v)};\n`;
  output+=`export type MotionScriptV${v} = ${render(schema,v)};\n`;
}
const corrections=JSON.parse(await fs.readFile(path.join(root,'schema/corrections-v1.schema.json'),'utf8'));
for(const [key,value] of Object.entries(corrections.definitions))output+=`export type ${name('Corrections',key)} = ${render(value,'Corrections')};\n`;
output+=`export type CorrectionsV1 = ${render(corrections,'Corrections')};\n`;
const file=path.join(root,'reader/src/generated/motionscript.ts');
if(process.argv.includes('--check')){if((await fs.readFile(file,'utf8')).replaceAll('\r\n','\n')!==output)throw Error('Generated contract types are stale');}
else{await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file,output);}
console.log('Shared v1/v2 contract types '+(process.argv.includes('--check')?'verified':'generated'));

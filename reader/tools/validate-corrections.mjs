import fs from 'node:fs';
import Ajv from 'ajv';
const schema=JSON.parse(fs.readFileSync(new URL('../../schema/corrections-v1.schema.json',import.meta.url),'utf8'));
const validate=new Ajv({allErrors:true}).compile(schema);
try{const value=JSON.parse(fs.readFileSync(0,'utf8'));if(!validate(value))throw Error(JSON.stringify(validate.errors));process.stdout.write('{}');}
catch(e){process.stderr.write(String(e));process.exitCode=2;}

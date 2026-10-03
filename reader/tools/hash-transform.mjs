// One canonical numeric/JSON encoding shared with the reader's v2 guard.
import {contentHash} from '../src/contract-v2.js';
let input='';for await(const part of process.stdin){input+=part;if(input.length>65536)throw Error('Transform input too large');}
const value=JSON.parse(input);
if(Object.keys(value).sort().join(',')!=='anchor,poses,source_bbox')throw Error('Expected only canonical transform fields');
console.log(await contentHash(value));

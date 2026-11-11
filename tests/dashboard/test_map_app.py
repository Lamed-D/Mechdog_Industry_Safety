"""Browser preview and hub must agree on every occupancy-cell transition."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from host.map_review import Grid, review_edit

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('node'), 'Node is optional for browser behavior tests')
class MapAppTests(unittest.TestCase):
    def test_all_cell_transitions_match_hub_and_private_transport(self):
        cases = []
        for before in range(-1, 101):
            for after in range(-1, 101):
                try:
                    value = review_edit(Grid(1,1,1,(0,0,0),(before,)), Grid(1,1,1,(0,0,0),(after,)))
                    expected = list(value.cleared_cells)
                except ValueError:
                    expected = None
                cases.append([before,after,expected])
        script = r'''
import assert from 'node:assert/strict';
import {grid,review,approved,cellAt,verifiedGrid,objectPath} from './dashboard/app/map-review.mjs';
import {Cloud} from './dashboard/app/client.mjs';
let input='';for await(const chunk of process.stdin)input+=chunk;
const g={width:1,height:1,resolution:1,origin:[0,0,0],frame:'map',cells:[0]};
for(const [before,after,expected] of JSON.parse(input)) {
 const run=()=>review({...g,cells:[before]},{...g,cells:[after]});
 if(expected===null)assert.throws(run);else assert.deepEqual(run().cleared,expected);
}
for(const bad of [true,null,NaN,Infinity,'1',-2,101])assert.throws(()=>grid({...g,cells:[bad]}));
for(const bad of [true,0,-1,Infinity,'1'])assert.throws(()=>grid({...g,resolution:bad}));
assert.throws(()=>review(g,{...g,origin:[1,0,0]}));
assert.throws(()=>review(g,{...g,frame:'other'}));
const source={...g,cells:[100]}, checked=review(source,g);source.cells[0]=0;
assert.equal(checked.base.cells[0],100);
assert.throws(()=>approved(checked,new Set()));
assert.throws(()=>approved(checked,new Set([1])));
assert.deepEqual(approved(checked,new Set([0])),[0]);
assert.throws(()=>approved(checked,new Set([0,1])));
const square={...g,width:2,height:2,cells:[0,0,0,0]};
assert.equal(cellAt(square,0,0,100,100),2);assert.equal(cellAt(square,99,99,100,100),1);
assert.equal(cellAt(square,100,0,100,100),null);assert.equal(cellAt(square,-1,0,100,100),null);
for(const path of ['../x','/x','x//y','x/%2e%2e/y','x?query','x\\y'])assert.throws(()=>objectPath(path));
const raw=new TextEncoder().encode(JSON.stringify(g));
const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('');
const id='00000000-0000-4000-8000-000000000001';
const {cells,...geometry}=g;
const meta={id,hub_id:id,version:1,state:'draft',object_path:'synthetic/grid.json',sha256:sha,geometry};
assert.deepEqual(await verifiedGrid(meta,raw),g);
await assert.rejects(()=>verifiedGrid({...meta,sha256:'0'.repeat(64)},raw));
await assert.rejects(()=>verifiedGrid({...meta,geometry:{...geometry,width:2}},raw));
const calls=[];
const cloud=new Cloud({url:'https://synthetic.invalid',key:'sb_publishable_synthetic',hub:id,device:id},async(url,options)=>{
 calls.push({url,options});
 return {ok:true,body:new ReadableStream({start(c){c.enqueue(raw);c.close();}})};
});
await assert.rejects(()=>cloud.mapGrid(meta));cloud.token='synthetic';
assert.deepEqual(await cloud.mapGrid(meta),g);
assert.equal(calls[0].url,'https://synthetic.invalid/storage/v1/object/authenticated/maps/synthetic/grid.json');
assert.equal(calls[0].options.redirect,'error');
await assert.rejects(()=>cloud.mapGrid({...meta,hub_id:'foreign'}));
let cancelled=false;
cloud.transport=async()=>({ok:true,body:new ReadableStream({start(c){c.enqueue(new Uint8Array(4194305));},cancel(){cancelled=true;}})});
await assert.rejects(()=>cloud.mapGrid(meta));assert.equal(cancelled,true);
'''
        result = subprocess.run([shutil.which('node'),'--input-type=module','-e',script],
                                cwd=ROOT,input=json.dumps(cases),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)

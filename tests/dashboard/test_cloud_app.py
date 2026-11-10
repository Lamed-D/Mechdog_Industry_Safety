from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CloudAppTests(unittest.TestCase):
    def test_static_app_has_no_direct_hub_or_persistent_credentials(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'dashboard/app').glob('*.mjs'))
        for forbidden in ('localStorage','sessionStorage','innerHTML','http://','20108','8000'):
            self.assertNotIn(forbidden,source)
        html = (ROOT/'dashboard/app/index.html').read_text(encoding='utf-8')
        self.assertIn('Content-Security-Policy',html)
        self.assertIn('form-action',html)

    @unittest.skipUnless(shutil.which('node'),'Node is optional for browser module behavioral tests')
    def test_browser_policy_and_rest_with_injected_transport(self):
        script = r'''
import assert from 'node:assert/strict';
import {Cloud,command,configuration,statusView} from './dashboard/app/client.mjs';
const id='00000000-0000-4000-8000-000000000001';
const config={url:'https://synthetic.invalid',key:'sb_publishable_synthetic',hub:id,device:id};
assert.throws(()=>configuration({...config,url:'http://synthetic.invalid'}));
assert.throws(()=>configuration({...config,key:'service_role'}));
assert.throws(()=>command(config,'reset',{robot:'A',confirmed:false,context:'0'.repeat(32)+':1'}));
const stop=command(config,'estop',{},0,id);
assert.equal(stop.kind,'estop');assert.equal(stop.robot_id,null);
assert.equal(Date.parse(stop.expires_at)-Date.parse(stop.created_at),10000);
assert.equal(statusView([],100)[0].fresh,false);
assert.equal(statusView([{robot_id:'A',updated_at:new Date(0).toISOString(),summary:{reset_context:'old'}}],10000)[0].context,null);
const calls=[];
const transport=async(url,options)=>{
 calls.push({url,options});
 assert.equal(new URL(url).origin,'https://synthetic.invalid');
 let data=[];
 if(url.includes('/auth/v1/token'))data={access_token:'synthetic-token',user:{id}};
 if(url.includes('/devices?'))data=[{id,auth_user_id:id,kind:'dashboard',role:'operator'}];
 return {ok:true,text:async()=>JSON.stringify(data)};
};
const cloud=new Cloud(config,transport);
await assert.rejects(()=>cloud.send('estop'));
await cloud.login('synthetic@example.invalid','synthetic');
await cloud.send('estop');
await cloud.send('reset',{robot:'A',confirmed:true,context:'0'.repeat(32)+':1'});
const posts=calls.filter(c=>c.url.endsWith('/rest/v1/commands'));
assert.equal(posts.length,2);
assert.equal(JSON.parse(posts[1].options.body).payload.confirmed,true);
assert.equal(posts[0].options.redirect,'error');
assert.equal(posts[0].options.credentials,'omit');
await cloud.snapshot();
await cloud.logout();assert.equal(cloud.token,null);
'''
        result = subprocess.run([shutil.which('node'),'--input-type=module','-e',script],
                                cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_readme_orders_camera_pc_and_robot(self):
        text = (ROOT/'README.md').read_text(encoding='utf-8')
        self.assertLess(text.index('**카메라 준비·업로드:**'),text.index('**PC로 카메라 확인:**'))
        self.assertLess(text.index('**PC로 카메라 확인:**'),text.index('**통과 후 로봇 본체 시험:**'))

import {Cloud,statusView} from './client.mjs';
import {mapPanel} from './map-panel.mjs';
const $ = id => document.getElementById(id);
let cloud = null, snapshot = null, generation = 0, timer = null;
const clearMaps = mapPanel(()=>cloud);
const banner = message => { $('banner').textContent = message; };
const action = message => { $('action').textContent = message; };
function controls() {
  const operator = cloud?.role === 'operator';
  $('estop').disabled = !operator;
  for (const view of statusView(snapshot?.status || []))
    $(`reset${view.robot}`).disabled = !operator || !view.context;
}
async function poll(current, version) {
  try {
    const data = await current.snapshot();
    if (version !== generation) return;
    snapshot = data;
    const views = statusView(data.status);
    $('robots').textContent = JSON.stringify(views.map(({context,...view})=>view),null,2);
    $('alerts').textContent = JSON.stringify(data.alerts,null,2);
    $('results').textContent = JSON.stringify(data.commands.map(({id,kind,status,result})=>({id,kind,status,result})),null,2);
    banner(views.every(view=>view.fresh) ? '클라우드 조회 정상 · 실제 로봇 상태와 명령 결과를 확인하세요.' : '허브/로봇 상태 지연 또는 미수신 · 자동 재개하지 않습니다.');
  } catch {
    if (version !== generation) return;
    snapshot = null;
    banner('클라우드 연결 실패 또는 세션 만료 · 정지 전송도 보장되지 않습니다. 상태 확인 후 다시 로그인하세요.');
  } finally {
    if (version === generation) { controls(); timer = setTimeout(()=>poll(current,version),1000); }
  }
}
$('login').addEventListener('submit',async event=>{
  event.preventDefault();
  generation++; clearTimeout(timer); cloud = null; snapshot = null; controls();
  clearMaps();
  const version = generation;
  try {
    const current = new Cloud(Object.fromEntries(['url','key','hub','device'].map(id=>[id,$(id).value.trim()])));
    await current.login($('email').value,$('password').value);
    if (version !== generation) return;
    cloud = current; controls(); poll(current,version);
  } catch { banner('로그인 실패 · 프로젝트·계정·기기 등록을 확인하세요.'); }
  finally { $('password').value = ''; }
});
$('logout').addEventListener('click',async()=>{
  const old = cloud; generation++; clearTimeout(timer); cloud = null; snapshot = null; controls();
  clearMaps();
  for (const id of ['robots','alerts','results']) $(id).textContent = '로그아웃';
  banner('로그아웃 · 메모리 세션 제거');
  try { await old?.logout(); } catch { banner('로컬 로그아웃 완료 · 원격 세션 폐기는 미확인'); }
});
$('estop').addEventListener('click',async()=>{
  // Deliberately no confirmation and no wait for an in-flight status poll.
  try { const id = await cloud.send('estop'); action(`전체 정지 전송: ${id} · 허브 처리 결과와 텔레메트리를 확인하세요.`); }
  catch { action('전체 정지 전송 실패 · 현장에서 안전을 확보하세요.'); }
});
for (const robot of ['A','B']) $(`reset${robot}`).addEventListener('click',async()=>{
  const context = statusView(snapshot?.status || []).find(view=>view.robot===robot)?.context;
  if (!context || !confirm(`로봇 ${robot}를 현장에서 보고 있고 주변이 안전합니까?`)) return;
  try { const id = await cloud.send('reset',{robot,context,confirmed:true}); action(`래치 해제 요청: ${id} · 해제 텔레메트리 대기`); }
  catch { action('래치 해제 요청 실패 · 현재 상태를 다시 확인하세요.'); }
});

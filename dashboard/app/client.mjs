import {objectPath,verifiedGrid} from './map-review.mjs';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function configuration(value) {
  const url = new URL(value.url);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/')
    throw Error('HTTPS 프로젝트 주소를 확인하세요.');
  if (!UUID.test(value.hub) || !UUID.test(value.device) || !value.key?.startsWith('sb_publishable_'))
    throw Error('허브·기기 UUID와 publishable 키가 필요합니다.');
  return Object.freeze({...value, url: url.origin});
}
export function command(config, kind, {robot = null, context = null, confirmed = false} = {}, now = Date.now(), id = crypto.randomUUID()) {
  if (!UUID.test(id) || !Number.isFinite(now)) throw Error('명령 ID·시각 오류');
  let payload = {};
  if (kind === 'reset') {
    if (!['A','B'].includes(robot) || confirmed !== true || !/^[a-f0-9]{32}:[1-9][0-9]{0,15}$/.test(context || ''))
      throw Error('현재 상태 확인과 사람 확인이 필요합니다.');
    payload = {confirmed: true, reset_context: context};
  } else if (kind !== 'estop' || robot !== null) throw Error('지원하지 않는 조작');
  return {v:1, id, hub_id:config.hub, device_id:config.device, robot_id:robot, kind,
    created_at:new Date(now).toISOString(), expires_at:new Date(now+10000).toISOString(), payload};
}
export function statusView(rows, now = Date.now()) {
  return ['A','B'].map(robot => {
    const row = rows.find(item => item.robot_id === robot);
    const age = now - Date.parse(row?.updated_at || '');
    const fresh = Number.isFinite(age) && age >= 0 && age < 10000;
    return {robot, fresh, summary:row?.summary || {}, context:fresh ? row?.summary?.reset_context : null};
  });
}
export class Cloud {
  constructor(config, transport = fetch) { this.config = configuration(config); this.transport = transport; this.token = null; }
  async request(path, {method='GET', body=null, auth=true} = {}) {
    if (auth && !this.token) throw Error('로그인 필요');
    const headers = {apikey:this.config.key, 'Content-Type':'application/json'};
    if (auth) headers.Authorization = `Bearer ${this.token}`;
    const response = await this.transport(this.config.url+path, {method, headers,
      body:body === null ? null : JSON.stringify(body), redirect:'error', credentials:'omit',
      referrerPolicy:'no-referrer', signal:AbortSignal.timeout(3000)});
    if (!response.ok) throw Error(`클라우드 요청 실패 (${response.status})`);
    const text = await response.text();
    if (text.length > 1048576) throw Error('응답 크기 초과');
    return text ? JSON.parse(text) : null;
  }
  async login(email, password) {
    this.token = null;
    const session = await this.request('/auth/v1/token?grant_type=password', {method:'POST', body:{email,password}, auth:false});
    if (typeof session.access_token !== 'string') throw Error('로그인 응답 오류');
    this.token = session.access_token;
    try {
      const rows = await this.request(`/rest/v1/devices?id=eq.${this.config.device}&hub_id=eq.${this.config.hub}&enabled=eq.true&select=id,role,kind,auth_user_id`);
      if (rows.length !== 1 || rows[0].auth_user_id !== session.user?.id || rows[0].kind !== 'dashboard')
        throw Error('등록된 대시보드 기기가 아닙니다.');
      this.role = rows[0].role;
      return this.role;
    } catch (error) { this.token = null; throw error; }
  }
  async logout() {
    try { if (this.token) await this.request('/auth/v1/logout', {method:'POST'}); }
    finally { this.token = null; this.role = null; }
  }
  async snapshot() {
    const query = `hub_id=eq.${this.config.hub}`;
    const [status, alerts, commands] = await Promise.all([
      this.request(`/rest/v1/robot_status?${query}&select=robot_id,updated_at,summary&limit=2`),
      this.request(`/rest/v1/alerts?${query}&state=neq.resolved&order=updated_at.desc&limit=30`),
      this.request(`/rest/v1/commands?${query}&order=created_at.desc&limit=20`)]);
    if (![status, alerts, commands].every(Array.isArray)) throw Error('잘못된 상태 응답');
    return {status, alerts, commands};
  }
  async send(kind, options) {
    if (this.role !== 'operator') throw Error('관리자 권한 필요');
    const row = command(this.config,kind,options);
    await this.request('/rest/v1/commands', {method:'POST',body:row});
    return row.id;
  }
  async maps() {
    const rows = await this.request(`/rest/v1/maps?hub_id=eq.${this.config.hub}&state=neq.archived&order=version.desc&limit=100`);
    if (!Array.isArray(rows) || rows.some(row=>!UUID.test(row.id) || row.hub_id !== this.config.hub ||
        !Number.isInteger(row.version) || row.version < 1 || !['draft','confirmed'].includes(row.state)))
      throw Error('지도 목록 오류');
    return rows;
  }
  async mapGrid(meta) {
    if (!this.token || meta.hub_id !== this.config.hub || !UUID.test(meta.id)) throw Error('지도 접근 거부');
    // Private maps bucket; never use a public/signed URL or another origin.
    const response = await this.transport(this.config.url+'/storage/v1/object/authenticated/maps/'+objectPath(meta.object_path), {
      headers:{apikey:this.config.key,Authorization:`Bearer ${this.token}`},
      redirect:'error',credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(3000)});
    if (!response.ok || !response.body) throw Error('지도 다운로드 실패');
    const reader = response.body.getReader(), chunks = [];
    let size = 0;
    try {
      while (true) {
        const {done,value} = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 4194304) throw Error('지도 파일 크기 초과');
        chunks.push(value);
      }
    } finally { await reader.cancel(); }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.byteLength; }
    return verifiedGrid(meta,bytes);
  }
}

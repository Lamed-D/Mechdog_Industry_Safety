// Browser review is advisory; the hub repeats validation before activation.
const fields = ['cells','frame','height','origin','resolution','width'];
export function grid(value) {
  if (!value || Object.keys(value).sort().join() !== fields.join() ||
      !Number.isInteger(value.width) || !Number.isInteger(value.height) ||
      value.width < 1 || value.height < 1 || value.width * value.height > 1000000 ||
      !Number.isFinite(value.resolution) || value.resolution <= 0 ||
      !Array.isArray(value.origin) || value.origin.length !== 3 || !value.origin.every(Number.isFinite) ||
      typeof value.frame !== 'string' || !/^[A-Za-z0-9_/]{1,64}$/.test(value.frame) ||
      !Array.isArray(value.cells) || value.cells.length !== value.width * value.height ||
      !value.cells.every(v => Number.isInteger(v) && v >= -1 && v <= 100))
    throw Error('지도 격자 형식 오류');
  return Object.freeze({...value,origin:Object.freeze([...value.origin]),cells:Object.freeze([...value.cells])});
}
export function review(base, proposal) {
  base = grid(base); proposal = grid(proposal);
  for (const key of ['width','height','resolution','frame'])
    if (base[key] !== proposal[key]) throw Error('지도 기하·좌표계 불일치');
  if (!base.origin.every((v,i)=>v === proposal.origin[i])) throw Error('지도 원점 불일치');
  const cleared = [], changed = [];
  base.cells.forEach((before,i)=>{
    const after = proposal.cells[i];
    if (before === -1 && after === 0) throw Error('미확인 칸을 빈 칸으로 바꿀 수 없습니다.');
    if (before !== after) changed.push(i);
    if (before > 0 && after === 0) cleared.push(i);
  });
  return Object.freeze({base,proposal,cleared:Object.freeze(cleared),changed:Object.freeze(changed)});
}
export function approved(reviewed, approvals) {
  if (!(approvals instanceof Set) || approvals.size !== reviewed.cleared.length ||
      !reviewed.cleared.every(i=>approvals.has(i))) throw Error('장애물 삭제 칸을 각각 승인하세요.');
  return [...reviewed.cleared];
}
export function cellAt(g, x, y, width, height) {
  if (![x,y,width,height].every(Number.isFinite) || width <= 0 || height <= 0 ||
      x < 0 || y < 0 || x >= width || y >= height) return null;
  return (g.height - 1 - Math.floor(y/height*g.height))*g.width + Math.floor(x/width*g.width);
}
export function objectPath(value) {
  if (typeof value !== 'string' || value.length > 1024 ||
      !value.split('/').every(p=>/^[A-Za-z0-9_.-]+$/.test(p) && p !== '.' && p !== '..'))
    throw Error('비공개 지도 경로 오류');
  return value.split('/').map(encodeURIComponent).join('/');
}
export async function verifiedGrid(meta, raw) {
  if (!(raw instanceof Uint8Array) || raw.byteLength > 4194304 || !/^[a-f0-9]{64}$/.test(meta.sha256))
    throw Error('지도 파일 크기·해시 오류');
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('');
  if (hash !== meta.sha256) throw Error('지도 파일 해시 불일치');
  const result = grid(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw)));
  const expected = meta.geometry;
  if (!expected || Object.keys(expected).sort().join() !== 'frame,height,origin,resolution,width' ||
      ['width','height','resolution','frame'].some(k=>expected[k] !== result[k]) ||
      !Array.isArray(expected.origin) || expected.origin.length !== 3 ||
      !expected.origin.every((v,i)=>v === result.origin[i])) throw Error('지도 메타데이터 불일치');
  return result;
}

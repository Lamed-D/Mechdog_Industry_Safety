import {review,approved,cellAt} from './map-review.mjs';
export function mapPanel(getCloud) {
  const $ = id=>document.getElementById(id);
  const canvas = $('mapCanvas'), ctx = canvas.getContext('2d');
  let epoch = 0, rows = [], compared = null, approvals = new Set();
  const message = text=>{ $('mapMessage').textContent = text; };
  function clear() {
    epoch++; compared = null; approvals = new Set();
    ctx.clearRect(0,0,canvas.width,canvas.height);
    $('clearingList').replaceChildren();
    $('checkReview').disabled = true;
  }
  function draw() {
    if (!compared) return;
    const g = compared.proposal, base = compared.base, alpha = Number($('mapBlend').value)/100;
    canvas.width = g.width; canvas.height = g.height;
    const image = ctx.createImageData(g.width,g.height);
    const shade = value=>value === -1 ? 130 : value === 0 ? 250 : 25;
    const clearing = new Set(compared.cleared);
    for (let i=0;i<g.cells.length;i++) {
      const dest = ((g.height-1-Math.floor(i/g.width))*g.width+i%g.width)*4;
      let color = Array(3).fill(Math.round(shade(base.cells[i])*(1-alpha)+shade(g.cells[i])*alpha));
      if (base.cells[i] !== g.cells[i]) color = [color[0]*.8,color[1]*.9,Math.min(255,color[2]+40)];
      if (clearing.has(i)) color = approvals.has(i) ? [0,160,100] : [220,80,20];
      image.data.set([...color,255],dest);
    }
    ctx.putImageData(image,0,0);
    message(`변경 ${compared.changed.length}칸 · 장애물 삭제 승인 ${approvals.size}/${compared.cleared.length} · 초안 좌표 (0,0)은 왼쪽 아래`);
  }
  function toggle(index) {
    if (!compared?.cleared.includes(index)) return;
    approvals.has(index) ? approvals.delete(index) : approvals.add(index);
    const checkbox = document.getElementById('clearCell'+index);
    if (checkbox) checkbox.checked = approvals.has(index);
    draw();
  }
  for (const id of ['baseMap','proposalMap']) $(id).addEventListener('change',clear);
  $('mapBlend').addEventListener('input',draw);
  canvas.addEventListener('click',event=>{
    if (!compared) return;
    const rect = canvas.getBoundingClientRect();
    toggle(cellAt(compared.proposal,event.clientX-rect.left,event.clientY-rect.top,rect.width,rect.height));
  });
  $('loadMaps').addEventListener('click',async()=>{
    clear(); rows = [];
    for (const id of ['baseMap','proposalMap']) $(id).replaceChildren();
    const current = getCloud(), version = epoch;
    try {
      if (!current) throw Error('먼저 로그인하세요.');
      const loaded = await current.maps();
      if (version !== epoch || current !== getCloud()) return;
      rows = loaded;
      for (const id of ['baseMap','proposalMap']) for (const row of rows) {
        const option = document.createElement('option'); option.value = row.id;
        option.textContent = `버전 ${row.version} · ${row.state} · ${row.id}`; $(id).append(option);
      }
      message('초안과 제안본을 선택한 뒤 비교하세요. 최근 100개 지도만 표시합니다.');
    } catch (error) { if (version === epoch) message(error.message); }
  });
  $('compareMaps').addEventListener('click',async()=>{
    clear(); const version = epoch, current = getCloud();
    try {
      if (!current) throw Error('먼저 로그인하세요.');
      const base = rows.find(r=>r.id === $('baseMap').value), proposal = rows.find(r=>r.id === $('proposalMap').value);
      if (!base || !proposal || base.id === proposal.id) throw Error('서로 다른 초안과 제안본을 선택하세요.');
      const grids = await Promise.all([current.mapGrid(base),current.mapGrid(proposal)]);
      if (version !== epoch || current !== getCloud()) return;
      compared = review(...grids);
      for (const index of compared.cleared.slice(0,1000)) {
        const label = document.createElement('label'), input = document.createElement('input');
        input.type = 'checkbox'; input.id = 'clearCell'+index;
        input.addEventListener('change',()=>toggle(index));
        label.append(input,document.createTextNode(`삭제 칸 (${index%base.geometry.width}, ${Math.floor(index/base.geometry.width)})`));
        $('clearingList').append(label);
      }
      $('checkReview').disabled = false; draw();
    } catch (error) { if (version === epoch) { clear(); message(error.message); } }
  });
  $('checkReview').addEventListener('click',()=>{
    try {
      approved(compared,approvals);
      message('셀 검토 완료 · 서버 확정 전송은 아직 연결되지 않았습니다. 지도를 활성화하지 않았습니다.');
    } catch (error) { message(error.message); }
  });
  return ()=>{
    clear(); rows = [];
    for (const id of ['baseMap','proposalMap']) $(id).replaceChildren();
    message('로그인 후 지도 목록을 불러오세요.');
  };
}

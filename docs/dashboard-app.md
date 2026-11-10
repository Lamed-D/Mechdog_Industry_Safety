# 인터넷 대시보드 앱: 안전 조작 단계

`dashboard/app/`은 정적 HTML + ES modules + fetch로 구현한다. SDK·런타임 의존성을 추가하지 않는다.
기존 dashboard/web은 개발/시험용으로 유지하며 이 앱은 Pi에 직접 접속하지 않는다.
노트북의 정적 파일 서버는 화면 파일만 제공하고 모든 상태/조작은 HTTPS Supabase REST로 보낸다.

```powershell
python -m http.server 8080 --bind 127.0.0.1 --directory dashboard/app
```

브라우저에서 `http://127.0.0.1:8080`을 연다. 사용자 프로젝트 URL·publishable 키·등록한 허브/노트북 UUID와
계정을 입력해야 로그인한다. 실제 계정이 없으면 화면 구조만 확인할 수 있다. 실제 접속 시험은 수행하지 않았다.
브라우저에 service_role/secret 키를 넣지 않는다. 이 앱은 publishable 형식만 허용한다.

이 단계에서 로그인, 기기 등록/계정 일치 확인, 상태·알림·명령 결과, 연결 지연 배너,
확인 창 없는 전체 정지와 확인 창을 거치는 RESET을 구현했다. 모든 변경은 commands INSERT다.
클라이언트의 권한 표시는 편의 기능이며 실제 권한은 RLS와 허브의 명령 검사기가 결정한다.
토큰은 메모리에만 두며 새로고침·로그아웃 시 사라진다. 비밀번호 입력도 로그인 후 비운다.
세션 자동 갱신은 미구현이며 만료 시 다시 로그인한다. 응답은 textContent로만 표시한다.

허브는 robot_status.summary.reset_context에 Processor가 발급한 현재 공개 확인 ID를 게시해야 한다.
현재 서비스 게시 연결은 미구현이므로 실제 RESET 준비가 완료됐다고 볼 수 없다.
전송 성공은 물리 정지/해제를 뜻하지 않으며 commands 결과와 텔레메트리를 확인한다.
노트북 시각으로 계산한 상태 신선도도 보조 표시일 뿐, 허브가 실제 조건을 다시 확인한다.

남은 화면: 지도 초안/제안 겹치기·셀 승인, 구역/지점/경로 편집, 루틴 편집, 0.5초 정찰 조종.
이 조작들은 기존 봉투/SQL 허용 종류를 확장하고 허브 처리기를 연결한 뒤 활성화한다.
새 버튼만 만들어 직접 설정 표에 쓰는 방식은 사용하지 않는다.
브라우저 실제 렌더링·접근성·CORS·로그인/RLS·서비스 연결은 미검증이다.
PC 검증은 정적 계약과 주입한 fetch의 모듈 동작 검사다. Node가 없으면 동작 검사는 skip이며
Python 3.12 표준 unittest와 앱 실행에는 Node가 필요하지 않다.

근거: [공식 비밀번호 인증](https://supabase.com/docs/guides/auth/passwords),
[공식 Auth REST 명세](https://github.com/supabase/auth/blob/master/openapi.yaml),
[PostgREST](https://docs.postgrest.org/en/stable/references/api/tables_views.html).

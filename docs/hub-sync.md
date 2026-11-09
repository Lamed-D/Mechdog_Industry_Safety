# 외부 연결 전용 동기화

`host.hub.sync.Sync`는 전용 작업자에서 실행한다. 제어 루프와 ESTOP 경로에서 SQLite나 HTTP를 기다리지 않는다. 생성자는 연결하지 않는다. 실행 서비스 연결은 다음 단위에서 다룬다.

- Gateway는 upload와 commands 인터페이스다. FakeSupabase는 메모리에서만 장애를 주입하며 SQL/RLS 에뮬레이터가 아니다.
- tick마다 대기열 선두 한 건만 보내며 UUID와 created_at을 유지한다. 서버가 같은 UUID를 돌려준 경우에만 로컬 선두를 ACK한다. 빈 RLS 결과는 성공으로 처리하지 않는다.
- 실패 시 1, 2, 4초 순서로 재시도 간격을 늘린다. 상한은 설정값이며 기본 60초다. 후속 항목이 앞지르지 않는다.
- 명령은 1초 간격으로 가져온다. 업로드 실패 중에도 명령을 조회한다. ESTOP와 일반 명령을 별도 조회하여 각각 최대 100건 받고 ESTOP를 먼저 반환한다. 실제 실행과 중복 방지는 명령 처리기가 담당한다.
- 마지막 성공한 클라우드 연결의 단조 시각으로 인터넷 상태를 판단한다. 기본 10초 미만이 정상이다. 순찰 복귀와 재개 판단은 연결 상태기계의 책임이며 자동 재개하지 않는다.
- RestGateway는 HTTPS 프로젝트 origin만 받고 리다이렉트를 거부한다. API key와 현재 사용자 access token은 외부에서 주입한다. URL에 키를 넣지 않는다. service_role을 사용하지 않는다. 세션 갱신·배포·계정 생성은 아직 구현하지 않았다.
- upsert는 기존 UUID를 사용한다. command_result는 status/result/updated_at만 PATCH한다. POST/PATCH 반환 UUID를 확인한다. 응답은 1MB로 제한하며 기본 타임아웃은 2초다.

REST 근거: [PostgREST 공식 upsert·필터 문서](https://docs.postgrest.org/en/stable/references/api/tables_views.html).
실제 SQL/RLS, Supabase, 인터넷과 Pi는 미검증이다. 테스트는 주입한 opener로만 실행하며 실제 접속하지 않는다.

전체 정지를 가져왔으면 업로드를 건너뛰고 즉시 처리기에 넘긴다. 이후 일반 명령 조회가 실패해도 이미 가져온 전체 정지를 버리지 않는다.

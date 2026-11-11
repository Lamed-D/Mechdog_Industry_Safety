# Supabase·허브 통합 모의 실행

```powershell
python -m tools.mock.hub_cloud_demo
python -m tools.mock.hub_cloud_demo --finder B
python -m tools.mock.hub_cloud_demo --no-navigator
```

모든 기록은 `source=synthetic`, `hardware=false`다. 표준 라이브러리와 가짜 시계·메모리 SQLite만 쓰며
소켓·외부 서비스·계정·장치·모델을 열지 않는다. 결과는 JSON Lines로 출력하며 파일을 저장하지 않는다.

확정 합성 격자와 필수 4종 지점/경로를 ConfigSync로 검증하고 Store에 활성화한다. 모의 사람 RESET을
FakeSupabase → Sync → Processor → SimLink → 해제 텔레메트리 → 명령 결과 업로드로 보낸다.
영속 예약 뒤 루틴 시작 의도를 만들고 합성 감지로 루틴을 중지한다. 알림과 이벤트는 outbox로 보내고,
Supabase 경유 사람 확인 명령으로 사건을 확인한다. FakeSupabase는 RLS/SQL/실제 HTTP를 흉내 내지 않는다.

10초를 넘긴 인터넷 단절은 사고 시나리오와 루틴을 먼저 보류하고 서버 복귀 의도를 만든다.
Navigator가 없으면 제자리 정지 의도로 바뀐다. 복귀 도착/연결 회복 뒤에도 순찰과 사고 안내는 자동 재개하지 않는다.
약한 링크 기준과 준비 상태·안전 경로는 합성 입력이다. 현장 임계값이나 주행 안전성의 근거로 쓰지 않는다.

이 데모는 **정책과 의도 연결 검사**다. 경로 실행기는 없으며 합성 Navigator는 요청 수락만 기록한다.
두 로봇 이동·위치 추정·정지 지연·낙상 정확도·실제 클라우드 권한·Python 3.12/Pi 실행을 검증하지 않는다.
지도 검토/확정 요청과 화면 편집은 별도 테스트가 담당한다. 실제 서비스 스레드·인증 갱신·원격 설정 조회,
정찰/루틴 명령·사건별 사람 확인 토큰은 후속 구현이다. 장비 업로드·구동·계정/키 준비는 사용자만 수행한다.

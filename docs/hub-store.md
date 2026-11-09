# Pi 허브 로컬 저장소

`host.hub.store.Store(path, hub_id, device_id)`는 표준 sqlite3와 기존 CommandJournal을 사용합니다.
생성/조회/쓰기/close는 **동기화 작업자에서만** 수행합니다. 10Hz 제어 잠금 안에서는 호출하지 않습니다.
Store 자체가 ESTOP을 보내거나 장치·Supabase에 접속하지 않습니다.

- DB는 허브·기기 UUID 한 쌍에 묶습니다. 다른 대상의 DB를 열면 거절합니다.
- `enqueue`는 메타데이터만 sync_outbox에 커밋합니다. 바이너리·NaN·과대 JSON·잘못된 목적지/종류는 실패 처리합니다.
  큐 한도는 기본 10,000건, 행은 16KB입니다. 용량 초과 시 기존 항목을 지우지 않습니다.
  event_id를 지정하면 대기 중 같은 ID/내용은 중복 추가하지 않고, 같은 ID/다른 내용은 거절합니다.
- `peek`는 가장 오래된 항목의 사본을 주며, 성공 업로드 후 그 머리 항목만 acknowledge할 수 있습니다.
  업로드 후 로컬 ACK가 실패하면 같은 UUID 행을 재전송합니다. 원본 id·created_at은 재생성하지 않습니다.
  command_result는 원래 명령 봉투 없이 status/result/updated_at만 담습니다.
- `save_status`는 robot_status 업로드 접수와 로컬 상태 사본을 한 트랜잭션으로 저장합니다.
  큐가 가득 차면 이전 상태 사본을 유지합니다. updated_at의 신선도 판단은 호출 계층이 맡습니다.
- `activate_config`는 confirmed 상태·허브·버전·canonical JSON 해시를 대조하고 사본/활성 버전을 원자 교체합니다.
  낮은 버전·같은 버전의 다른 내용·해시 오류·디스크 실패이면 이전 활성을 유지합니다.
  복사 한도는 4MB입니다. 이 해시는 지도 파일 SHA-256이나 map_review의 Grid 해시와 별개입니다.
  **지도·지점·권한 검증은 config_sync가 선행해야 하며 이 저장 성공 자체는 실행 허가가 아닙니다.**
- `store.journal`은 기존 처리 ID 영속 저널입니다. 재시작의 reserved는 자동 재실행하지 않습니다.
  별도의 명령 중복 테이블이나 자동 RESET을 만들지 않았습니다.

쓰기 실패는 failures를 올리고 False를 반환합니다. 조회/초기화 실패는 작업자가 처리해야 합니다.
SQLite가 느리거나 막힐 수 있으므로 제어/정지 경로는 디스크를 기다리지 않아야 합니다.
WAL·synchronous=FULL을 사용하지만 Pi 파일시스템/정전 내구성은 미검증입니다.
DB·실제 설정은 저장소 밖 사용자 운영 경로에 둡니다. PC 테스트 DB는 작업 폴더 build 안에서만 만들고 정리합니다.

스키마 초안은 확정 지도도 같은 UUID·같은 내용의 재전송만 no-op으로 허용하도록 보완했습니다.
실제 PostgreSQL 실행/RLS, 전체 JSON 스키마, 클라우드 전송·장치 적용은 이 단위에서 검증하지 않았습니다.

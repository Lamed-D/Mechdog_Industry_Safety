# Supabase 스키마 초안 0001

`supabase/migrations/0001_init.sql`은 **실행하지 않은 검토용 초안**입니다.
정적 테스트는 표·열·권한 선언의 일치만 검사하며 SQL 문법/실제 RLS 격리를 입증하지 않습니다.
사용자 프로젝트의 별도 시험 환경에서 두 허브·관리자·읽기 계정·익명 권한 시험 후에만 배포합니다.
계정·키 생성, 실제 접속, Storage bucket/정책 생성은 수행하지 않았습니다.

## 표와 열 계약

공통 열: `id`, `hub_id`, `robot_id`, `device_id`, `created_at`.
id는 UUID 기본키와 gen_random_uuid 기본값, hub_id는 허브 기기 UUID입니다. robot_id는 A/B 또는 해당 없으면 null입니다.
device_id는 기록 작성/마지막 변경 기기입니다. devices의 device_id만 등록 작업의 선택 메타데이터입니다.
UTC는 timestamptz, JSON은 메타데이터 전용입니다. 사진/영상/얼굴 바이트 열은 없습니다.

| 표 | 추가 열 | 클라이언트 쓰기 |
| --- | --- | --- |
| `devices` | `auth_user_id`, `kind`, `role`, `enabled` | 없음. 사용자 관리 작업으로 등록 |
| `robot_status` | `updated_at`, `summary` | 허브 |
| `alerts` | `updated_at`, `state`, `evidence` | 허브 |
| `events` | `kind`, `detail` | 허브 |
| `operator_actions` | `command_id`, `outcome` | 허브. 명령 결과 감사 기록 |
| `commands` | `v`, `expires_at`, `kind`, `payload`, `status`, `result`, `updated_at` | 관리자 insert, 허브 결과 열만 update |
| `notifications` | `alert_id`, `state`, `detail` | 현재 없음. 미래 명세용 |
| `maps` | `version`, `state`, `geometry`, `object_path`, `sha256`, `base_sha256`, `approved_clearings`, `confirmed_by`, `confirmed_at` | 허브 |
| `zones` | `map_id`, `kind`, `geometry` | 허브 |
| `waypoints` | `map_id`, `kind`, `pose` | 허브 |
| `routes` | `map_id`, `points` | 허브 |
| `routines` | `route_id`, `schedule`, `enabled` | 허브 |
| `routine_runs` | `routine_id`, `started_at`, `ended_at`, `state`, `reason` | 허브 |

지도·경로·루틴의 복합 외래키는 hub_id와 참조 ID를 함께 대조합니다. 다른 허브의 설정을 참조하지 않습니다.
map version은 허브 안에서 고유하며 confirmed 지도는 내용 변경 없이 archived로만 전환 가능합니다.
미확인 칸·지점·경로·JSON 구조·파일 해시는 허브의 map_review/config_sync 계층에서 별도로 검증합니다.
필수 지점 종류는 start_wait/manager/server/inspection입니다. 지도 이미지/격자는 비공개 파일 저장소의 경로·해시로 참조합니다.

## 권한과 조작 경로

- 모든 표에 RLS를 켜고 익명/PUBLIC/기존 authenticated 권한을 제거한 뒤 필요한 권한만 부여합니다. 삭제 권한은 주지 않습니다.
- 사용자 관리 작업으로 devices를 먼저 등록합니다. 허브 기기 행은 id=hub_id, kind/role=hub입니다.
  로봇 등록 행에는 Supabase 계정이 없으며 A/B 표시만 둡니다. 관리자=operator, 읽기 계정/휴대폰=viewer입니다.
- hub_access는 auth.uid()와 활성 기기/허브 등록을 대조합니다. JWT 본문의 사용자가 바꿀 수 있는 메타데이터를 역할로 쓰지 않습니다.
  devices RLS 재귀를 피하는 security definer 함수는 빈 search_path와 스키마 명시를 사용합니다.
  실제 배포에서는 함수 소유자와 기기 등록 권한을 사용자가 따로 검토해야 합니다.
- 관리자는 자기 허브의 commands만 추가합니다. 상태·지도·구역·루틴을 직접 변경하지 않습니다.
  허브가 명령을 검증해 실행하고 결과/설정을 반영합니다. 확정 요청·정찰·루틴 편집 종류는 후속 단위에서 봉투/허용 목록을 함께 확장합니다.
- 허브는 자기 명령의 status/result/updated_at만 갱신할 수 있습니다. 관리자 원본 봉투는 갱신 권한이 없습니다.
  모든 행의 id/hub_id/created_at 변경도 트리거로 거절합니다.
- 허브/관리자/읽기 계정은 등록된 자기 허브만 읽습니다. 관리자 권한 키를 브라우저에 넣지 않습니다.
  Android/푸시 코드는 만들지 않았습니다.

근거: [공식 RLS 안내](https://supabase.com/docs/guides/database/postgres/row-level-security),
[공식 열 권한 안내](https://supabase.com/docs/guides/database/postgres/column-level-security).

## 명령 봉투와 REST 경계

commands의 봉투 열은 [기존 v1 계약](remote-command-envelope.md)의 10개 필드 그대로입니다.
status/result/updated_at은 저장 결과이며 validate_envelope에 전달하기 전에 제외합니다.
REST가 반환하는 UTC offset 시각은 게이트웨이가 UTC Z 문자열로 정규화해야 합니다.
현재 kind는 estop/reset/operator이고 수명은 10초 이하입니다. 정지는 만료됐어도 허브가 처리하며 SQL은 만료 행을 숨기지 않습니다.
reset은 confirmed=true와 공개 reset_context가 필요합니다. confirmed JSON 문자열이나 누락 필드는 정상으로 수락하지 않습니다.
형식 검사·권한·처리 ID 저널·실행 직전 상태/신선도 검사는 SQL만으로 대체하지 않습니다.

실물 미검증. 실제 PostgreSQL/Supabase 실행·RLS·Storage 권한·API 성능은 모두 미검증입니다.

동일 UUID와 동일 내용의 재전송은 변경 없는 재시도로 허용한다. 확정 지도 내용 변경은 계속 거부한다.

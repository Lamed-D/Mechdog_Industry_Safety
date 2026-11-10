# 확정 설정 검증과 로컬 활성화

`host.hub.config_sync.ConfigSync`는 Supabase에서 가져온 설정 스냅샷을 검증한 뒤에만
Store의 활성 버전을 바꾼다. fetch(path, max_bytes)는 비공개 저장소 읽기 인터페이스이며
현재 구현 테스트는 메모리 파일만 사용한다. 실제 파일 저장소 접속은 하지 않는다.

스냅샷은 state=confirmed, hub_id, 양의 version과 map/base_map/zones/waypoints/routes/routines를 가진다.
각 행 열은 supabase-schema 계약을 따른다. base_map은 검토 당시 초안 파일 참조다.
지도 파일은 width/height/resolution/origin/frame/cells만 가진 UTF-8 JSON이다.
파일 SHA-256과 별개로 Grid 해시를 재계산하여 기존 map_review의 미확인→빈 칸 금지,
장애물 삭제 셀 전체 승인 규칙을 다시 검사한다. 중복 JSON 키와 경로 탈출을 거부한다.
파일 경로는 비공개 버킷 안 상대 경로이며 전송 크기는 4MB 이하로 제한한다.

기하 필드는 파일과 같아야 한다. 사람이 확정한 기기의 권한을 authorize_confirmation으로 대조한다.
이 콜백은 이미 검증한 확정 명령·기기 레지스트리를 근거로 해야 하며 문자열이 있다는 이유만으로
승인하면 안 된다. 원격 확정 명령과 감사 기록의 서비스 연결은 후속 단위다.
정적 hash는 무결성 값이며 사람 인증을 대신하지 않는다.

- 구역 geometry는 세계 좌표 m 단위 polygon이다. 3~256개 꼭짓점, 단순한 비퇴화 다각형만 허용한다.
  kind는 forbidden/patrol/slow다. 금지 구역 경계도 금지한다. slow의 실제 속도는 아직 확정하지 않는다.
- 지점 pose는 x/y/yaw이며 지도 안 0인 셀이고 금지 구역 밖이어야 한다.
  start_wait, manager, server, inspection 네 종류가 모두 필요하다.
- routes.points는 같은 지도 지점 UUID 순서다. 지점 사이 직선의 금지 구역 교차를 거부한다.
  routines는 검증한 경로를 참조해야 한다. 루틴 schedule 의미 검사는 다음 스케줄러가 담당한다.
- 구역·지점·경로 각각 최대 1,000행이며 다른 허브·지도 참조와 중복 ID를 거부한다.

검증한 격자 셀도 validated_grid로 SQLite 사본에 함께 보관하므로 인터넷이 끊겨도 지도 참조만
남는 문제가 없다. 전체 사본 4MB 제한을 넘으면 이전 활성 설정을 유지한다.
검증 실패/활성화 실패 이유를 report 콜백으로 넘긴다. 게시 실패는 report_failures로 드러난다.
실제 서비스에서는 이 콜백을 허브 events 업로드 대기열에 연결해야 한다.

이 검사는 주행 허가가 아니다. 지점 간 장애물 없는 경로, 로봇 외형·안전 여유·금지 구역 근접,
위치 신뢰도·지도 신선도는 Navigator와 실행 전 점검이 별도로 확인해야 한다.
모든 파일·해시·격자 검사는 제어 잠금 밖에서 한다. ROS, 실제 지도/파일 저장소/RLS/장비는 미검증이다.

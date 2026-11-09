-- 검토용 초안. 실행하지 않았으며 실제 권한 분리 시험 전 배포하지 않습니다.
begin;
create table public.devices (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid,
  auth_user_id uuid references auth.users(id), kind text not null, role text not null,
  enabled boolean not null default true, created_at timestamptz not null default now(),
  unique (hub_id,id),
  check ((kind='hub' and role='hub' and id=hub_id and auth_user_id is not null and robot_id is null)
    or (kind='dashboard' and role in ('operator','viewer') and auth_user_id is not null and robot_id is null)
    or (kind='phone' and role='viewer' and auth_user_id is not null and robot_id is null)
    or (kind='robot' and role='viewer' and auth_user_id is null and robot_id is not null))
);
create table public.robot_status (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text not null check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), updated_at timestamptz not null,
  summary jsonb not null check (jsonb_typeof(summary)='object'), unique(hub_id,robot_id)
);
create table public.alerts (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), updated_at timestamptz not null,
  state text not null check (state in ('open','acked','resolved')), evidence jsonb not null
);
create table public.events (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), kind text not null, detail jsonb not null
);
create table public.operator_actions (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), command_id uuid not null, outcome jsonb not null
);
create table public.commands (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null, v integer not null check (v=1),
  expires_at timestamptz not null, kind text not null check (kind in ('estop','reset','operator')),
  payload jsonb not null check (jsonb_typeof(payload)='object'),
  status text not null default 'pending' check (status in ('pending','accepted','rejected','expired','done')),
  result jsonb not null default '{}' check(jsonb_typeof(result)='object'), updated_at timestamptz not null default now(),
  check (expires_at > created_at and expires_at <= created_at + interval '10 seconds'),
  check (((kind='estop' and robot_id is null and payload='{}'::jsonb)
    or (kind='reset' and robot_id is not null and payload->'confirmed'='true'::jsonb
      and payload->>'reset_context' ~ '^[a-f0-9]{32}:[1-9][0-9]{0,15}$'
      and payload-'confirmed'-'reset_context'='{}'::jsonb)
    or (kind='operator' and robot_id is null and jsonb_typeof(payload->'event')='string'
      and payload->>'event' in ('start_patrol','operator_ack','start_guide','retry','resolved','guide_clear')
      and payload-'event'='{}'::jsonb)) is true),
  unique(hub_id,id)
);
alter table public.operator_actions add foreign key(hub_id,command_id) references public.commands(hub_id,id);
create table public.notifications (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), alert_id uuid references public.alerts(id),
  state text not null default 'pending', detail jsonb not null default '{}'
);
create table public.maps (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), version integer not null check(version>0),
  state text not null check(state in ('draft','confirmed','archived')),
  geometry jsonb not null, object_path text not null, sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
  base_sha256 text, approved_clearings jsonb not null default '[]',
  confirmed_by uuid references public.devices(id), confirmed_at timestamptz,
  check(state <> 'confirmed' or (confirmed_by is not null and confirmed_at is not null)),
  unique(hub_id,id), unique(hub_id,version)
);
create table public.zones (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), map_id uuid not null,
  kind text not null check(kind in ('patrol','forbidden','slow')), geometry jsonb not null,
  foreign key(hub_id,map_id) references public.maps(hub_id,id)
);
create table public.waypoints (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), map_id uuid not null,
  kind text not null check(kind in ('start_wait','manager','server','inspection')), pose jsonb not null,
  foreign key(hub_id,map_id) references public.maps(hub_id,id)
);
create table public.routes (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), map_id uuid not null, points jsonb not null,
  foreign key(hub_id,map_id) references public.maps(hub_id,id), unique(hub_id,id)
);
create table public.routines (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text not null check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), route_id uuid not null,
  schedule jsonb not null, enabled boolean not null default false,
  foreign key(hub_id,route_id) references public.routes(hub_id,id), unique(hub_id,id)
);
create table public.routine_runs (
  id uuid primary key default gen_random_uuid(), hub_id uuid not null references public.devices(id),
  robot_id text not null check (robot_id in ('A','B')), device_id uuid not null references public.devices(id),
  created_at timestamptz not null default now(), routine_id uuid not null,
  started_at timestamptz not null, ended_at timestamptz, state text not null, reason text,
  foreign key(hub_id,routine_id) references public.routines(hub_id,id)
);

-- 기기 등록은 사용자 관리 작업. 클라이언트는 스스로 역할/허브를 바꾸지 못합니다.
create function public.hub_access(p_hub uuid, p_roles text[], p_device uuid default null)
returns boolean language sql stable security definer set search_path='' as $$
  select exists(select 1 from public.devices d join public.devices h on h.id=d.hub_id
    where h.id=h.hub_id and h.kind='hub' and h.enabled and d.enabled
      and d.hub_id=p_hub and d.auth_user_id=(select auth.uid()) and d.role=any(p_roles)
      and (p_device is null or d.id=p_device));
$$;
revoke all on function public.hub_access(uuid,text[],uuid) from public, anon, authenticated;
grant execute on function public.hub_access(uuid,text[],uuid) to authenticated;

alter table public.devices enable row level security;
alter table public.robot_status enable row level security;
alter table public.alerts enable row level security;
alter table public.events enable row level security;
alter table public.operator_actions enable row level security;
alter table public.commands enable row level security;
alter table public.notifications enable row level security;
alter table public.maps enable row level security;
alter table public.zones enable row level security;
alter table public.waypoints enable row level security;
alter table public.routes enable row level security;
alter table public.routines enable row level security;
alter table public.routine_runs enable row level security;

-- 모든 표의 익명/기본 권한을 제거하고 허용한 조작만 부여합니다.
do $$ declare t text; begin
  foreach t in array array['devices','robot_status','alerts','events','operator_actions','commands',
      'notifications','maps','zones','waypoints','routes','routines','routine_runs'] loop
    execute format('revoke all on public.%I from public, anon, authenticated',t);
    execute format('grant select on public.%I to authenticated',t);
    execute format('create policy read_hub on public.%I for select to authenticated using (public.hub_access(hub_id, array[''hub'',''operator'',''viewer'']))',t);
  end loop;
  foreach t in array array['robot_status','alerts','events','operator_actions','maps','zones','waypoints','routes','routines','routine_runs'] loop
    execute format('grant insert, update on public.%I to authenticated',t);
    execute format('create policy hub_insert on public.%I for insert to authenticated with check (public.hub_access(hub_id,array[''hub''],device_id))',t);
    execute format('create policy hub_update on public.%I for update to authenticated using (public.hub_access(hub_id,array[''hub''])) with check (public.hub_access(hub_id,array[''hub''],device_id))',t);
  end loop;
end $$;
-- 모든 관리자 조작은 commands 경유. 대시보드의 상태/설정 직접 갱신은 허용하지 않습니다.
grant insert on public.commands to authenticated;
grant update(status,result,updated_at) on public.commands to authenticated;
create policy operator_command on public.commands for insert to authenticated with check (
  public.hub_access(hub_id,array['operator'],device_id) and status='pending' and result='{}'::jsonb);
create policy hub_result on public.commands for update to authenticated
  using(public.hub_access(hub_id,array['hub'])) with check(public.hub_access(hub_id,array['hub']));
-- notifications는 미래용 표만 준비합니다. Android/발송 처리는 구현하지 않습니다.

create function public.protect_identity() returns trigger language plpgsql set search_path='' as $$
begin
  if (new.id,new.hub_id,new.created_at) is distinct from (old.id,old.hub_id,old.created_at) then
    raise exception 'immutable row identity';
  end if;
  if to_jsonb(new)=to_jsonb(old) then
    return new; -- 같은 UUID의 완전히 같은 재전송만 허용
  end if;
  if tg_table_name='maps' then
    if old.state in ('confirmed','archived') then
      if not (old.state='confirmed' and new.state='archived'
        and (to_jsonb(new)-'state'-'device_id')=(to_jsonb(old)-'state'-'device_id')) then
        raise exception 'confirmed map is immutable';
      end if;
    end if;
  end if;
  return new;
end $$;
do $$ declare t text; begin
  foreach t in array array['devices','robot_status','alerts','events','operator_actions','commands',
      'notifications','maps','zones','waypoints','routes','routines','routine_runs'] loop
    execute format('create trigger identity_guard before update on public.%I for each row execute function public.protect_identity()',t);
  end loop;
end $$;
create index devices_principal on public.devices(auth_user_id,hub_id) where enabled;
create index commands_poll on public.commands(hub_id,status,created_at,id);
commit;

create table if not exists core.recording_session (
  id uuid primary key,
  workspace_id uuid not null references core.workspace(id),
  application_id uuid not null references core.application(id),
  environment_id uuid not null references core.environment(id),
  worker_session_id varchar(80) not null unique,
  scenario_name varchar(200) not null,
  module_name varchar(120),
  feature_name varchar(120),
  status varchar(40) not null,
  start_url varchar(2048) not null,
  browser varchar(30) not null,
  raw_event_count integer not null default 0,
  semantic_action_count integer not null default 0,
  ir_json text,
  error_text text,
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_recording_session_app_time on core.recording_session(application_id, created_at desc);
create index if not exists ix_recording_session_workspace_status on core.recording_session(workspace_id, status);

create table if not exists core.test_scenario (
  id uuid primary key,
  workspace_id uuid not null references core.workspace(id),
  application_id uuid not null references core.application(id),
  module_name varchar(120),
  feature_name varchar(120),
  name varchar(200) not null,
  status varchar(30) not null default 'ACTIVE',
  current_version integer not null default 1,
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_test_scenario_app on core.test_scenario(application_id, status, module_name, feature_name, name);

create table if not exists core.scenario_version (
  id uuid primary key,
  scenario_id uuid not null references core.test_scenario(id),
  version_no integer not null,
  source_recording_session_id uuid references core.recording_session(id),
  automation_ir text not null,
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  unique(scenario_id, version_no)
);
create index if not exists ix_scenario_version_scenario on core.scenario_version(scenario_id, version_no desc);

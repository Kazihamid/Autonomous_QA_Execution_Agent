create table if not exists core.automation_implementation (
  id uuid primary key,
  workspace_id uuid not null references core.workspace(id),
  application_id uuid not null references core.application(id),
  scenario_id uuid not null references core.test_scenario(id),
  scenario_version_id uuid not null references core.scenario_version(id),
  implementation_version integer not null,
  target_profile varchar(40) not null,
  generator_version varchar(40) not null,
  status varchar(40) not null,
  ir_canonical_hash varchar(64) not null,
  source_hash varchar(64) not null,
  files_json text not null,
  source_map_json text not null,
  validation_json text not null,
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  unique(scenario_version_id, target_profile, implementation_version)
);
create index if not exists ix_automation_impl_scenario on core.automation_implementation(scenario_id, created_at desc);
create index if not exists ix_automation_impl_target on core.automation_implementation(scenario_version_id, target_profile, implementation_version desc);

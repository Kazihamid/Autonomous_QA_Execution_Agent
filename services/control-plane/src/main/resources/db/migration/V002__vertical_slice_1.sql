create table if not exists iam.user_account (
  id uuid primary key,
  subject varchar(255) not null unique,
  email varchar(320) not null,
  display_name varchar(200) not null,
  status varchar(30) not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_user_account_email on iam.user_account(lower(email));

alter table core.workspace add column if not exists workspace_key varchar(40);
alter table core.workspace add column if not exists description varchar(1000);
alter table core.workspace add column if not exists created_by uuid;
alter table core.workspace add column if not exists updated_at timestamptz not null default now();
update core.workspace set workspace_key = upper(substr(replace(id::text, '-', ''), 1, 12)) where workspace_key is null;
alter table core.workspace alter column workspace_key set not null;
create unique index if not exists ux_workspace_key on core.workspace(workspace_key);

create table if not exists core.workspace_member (
  id uuid primary key,
  workspace_id uuid not null references core.workspace(id),
  user_id uuid not null references iam.user_account(id),
  role varchar(40) not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id, user_id)
);
create index if not exists ix_workspace_member_user on core.workspace_member(user_id, active);

create table if not exists core.application (
  id uuid primary key,
  workspace_id uuid not null references core.workspace(id),
  name varchar(200) not null,
  description varchar(2000),
  status varchar(30) not null default 'ACTIVE',
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id, name)
);
create index if not exists ix_application_workspace on core.application(workspace_id, status);

create table if not exists core.environment (
  id uuid primary key,
  application_id uuid not null references core.application(id),
  name varchar(120) not null,
  base_url varchar(2048) not null,
  default_browser varchar(30) not null default 'CHROMIUM',
  headless_default boolean not null default true,
  allow_recording boolean not null default true,
  allow_execution boolean not null default true,
  validation_status varchar(30) not null default 'UNVERIFIED',
  status varchar(30) not null default 'ACTIVE',
  created_by uuid not null references iam.user_account(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(application_id, name)
);
create index if not exists ix_environment_application on core.environment(application_id, status);

create table if not exists audit.audit_event (
  id uuid primary key,
  workspace_id uuid,
  actor_user_id uuid,
  action varchar(100) not null,
  resource_type varchar(80) not null,
  resource_id uuid,
  outcome varchar(30) not null,
  metadata_text text,
  occurred_at timestamptz not null default now()
);
create index if not exists ix_audit_workspace_time on audit.audit_event(workspace_id, occurred_at desc);
create index if not exists ix_audit_actor_time on audit.audit_event(actor_user_id, occurred_at desc);

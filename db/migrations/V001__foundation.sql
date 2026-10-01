create schema if not exists iam;
create schema if not exists core;
create schema if not exists automation;
create schema if not exists execution;
create schema if not exists audit;

create table if not exists core.workspace (
  id uuid primary key,
  name varchar(200) not null,
  status varchar(30) not null default 'ACTIVE',
  created_at timestamptz not null default now()
);

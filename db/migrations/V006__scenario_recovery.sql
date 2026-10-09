-- Scenario recovery: a deleted scenario is kept (status DELETED) so it can be restored; all of its versions stay in place.
alter table core.test_scenario add column if not exists deleted_at timestamptz;
alter table core.test_scenario add column if not exists deleted_by uuid;
create index if not exists ix_test_scenario_deleted on core.test_scenario(application_id, status, deleted_at);

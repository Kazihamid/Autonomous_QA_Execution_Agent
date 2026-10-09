-- A recording that was removed on purpose (its scenario was deleted permanently, or the user dismissed it) is not offered for recovery again.
alter table core.recording_session add column if not exists recovery_dismissed boolean not null default false;

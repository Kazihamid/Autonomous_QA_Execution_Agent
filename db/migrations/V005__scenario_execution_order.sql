-- Explicit, user-controlled execution order for scenarios (order-based runs).
alter table core.test_scenario add column if not exists execution_order integer;

-- Backfill using the order the repository list already displayed.
update core.test_scenario s
   set execution_order = r.rn
  from (
        select id,
               row_number() over (
                   partition by application_id
                   order by coalesce(module_name, ''), coalesce(feature_name, ''), name, created_at, id
               ) as rn
          from core.test_scenario
       ) r
 where r.id = s.id
   and s.execution_order is null;

create index if not exists ix_test_scenario_order on core.test_scenario(application_id, execution_order);

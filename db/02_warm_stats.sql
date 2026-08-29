-- Warm pg_stat_user_tables so a freshly seeded DB shows representative read
-- traffic (incl. heavy reads on the near-dead order_items). Absolute counts are
-- illustrative; the STRUCTURAL findings (broken FK, orphans) are exact regardless.
DO $$
DECLARE t text; i int;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'order_items','orders','orders_v2','users','workspaces',
    'user_prefs','products','payments','analytics_events'
  ] LOOP
    BEGIN
      FOR i IN 1..40 LOOP
        EXECUTE format('SELECT count(*) FROM %I', t);
      END LOOP;
    EXCEPTION WHEN undefined_table THEN
      NULL;
    END;
  END LOOP;
END $$;

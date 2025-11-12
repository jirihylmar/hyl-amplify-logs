CREATE OR REPLACE VIEW ana.ana___danse_tech__amplify_logs AS 
WITH
  prepro AS (
   SELECT
     DATE(date) date
   , CAST(concat(concat(date, ' '), time) AS timestamp) timestamp
   , "c-ip" ip_address
   , "cs(user-agent)" user_agent
   , concat("c-ip", '___', "cs(user-agent)") ip___user_agent
   , CAST('danse_tech' AS VARCHAR) app
   , DATE(date_export) date_export
   FROM
     parcor_1820591004622.danse_tech___type_amplify_logs
   WHERE (("sc-status" = 200) AND (NOT ("cs(user-agent)" LIKE '%bot%')) AND (NOT ("cs(user-agent)" LIKE '%webarchiv%')))
) 
, UserAgentCalls AS (
   SELECT
     date
   , timestamp
   , ip___user_agent
   , app
   , date_export
   , LAG(timestamp) OVER (PARTITION BY ip___user_agent ORDER BY timestamp ASC) prev_timestamp
   FROM
     prepro
) 
, UserAgentCount AS (
   SELECT
     date
   , timestamp
   , ip___user_agent
   , app
   , date_export
   , COUNT(*) OVER (PARTITION BY ip___user_agent ORDER BY timestamp ASC RANGE BETWEEN INTERVAL  '9' SECOND PRECEDING AND CURRENT ROW) call_count
   FROM
     UserAgentCalls
) 
, not_humans AS (
   SELECT DISTINCT
     ip___user_agent ip___user_agent
   , CAST(1 AS int) exclude
   FROM
     UserAgentCount
   WHERE (call_count > 3)
) 
, humans AS (
   SELECT
     a.*
   , b.exclude
   FROM
     (UserAgentCount a
   LEFT JOIN not_humans b ON (a.ip___user_agent = b.ip___user_agent))
) 
, clean AS (
   SELECT
     date
   , timestamp
   , ip___user_agent
   , app
   , date_export
   FROM
     humans
   WHERE (exclude IS NOT NULL)
) 
SELECT *
FROM
  clean
ORDER BY timestamp ASC, ip___user_agent ASC

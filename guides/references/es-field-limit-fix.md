# ES Field-Limit Incident: sinilind docs missing (2026-08-05)

## Symptom

- `VESSEL-SINILIND` docs in Elasticsearch stopped at **2026-08-03T15:28:31Z** and never resumed,
  even while the Pi was online and harisd was writing fresh snapshots locally
  (`/opt/haris/logs/signalk_snapshots.jsonl`, ~10s cadence).
- Arthur (`VESSEL-ARTHUR`) kept flowing (~6 docs/min). Only sinilind was affected.

## Diagnosis chain (in order — this is the recipe)

1. **Services on sinilind**: signalk/harisd/filebeat/zabbix-agent2 all `active`.
2. **filebeat config**: `output.logstash` → `haris-citadel:5044` correct.
3. **filebeat connectivity**: `filebeat test output` → `dial up... OK`, `talk to server... OK`.
4. **filebeat registry** (`/var/lib/filebeat/registry/filebeat/log.json`): cursor **advancing**
   (offset grows, `updated` timestamps current) → filebeat IS reading and shipping.
5. **Logstash pipeline rate** (`127.0.0.1:9600/_node/stats/pipelines`):
   `in=12 filtered=12 out=12` over 60s → **both vessels' events arrive and leave the pipeline**.
   Zero dropped inside Logstash.
6. **ES count by `vessel_id` / `haris_host`**: 0 docs for sinilind in the last 30 min,
   latest doc still yesterday 15:28Z. Events reach Logstash but never land in ES.
7. **Logstash log** (`/var/log/logstash/logstash-plain.log`) — the smoking gun:

   ```
   [WARN ][logstash.outputs.elasticsearch][main] Could not index event to Elasticsearch.
   {:status=>400, ... "_index"=>"haris-signalk-2026.08.05", ... "vessel_id"=>"VESSEL-SINILIND",
   :response=>{"index"=>{"status"=>400, "error"=>{"type"=>"document_parsing_exception",
   "reason"=>"[1:14755] failed to parse: Limit of total fields [1000] has been exceeded
   while adding new fields [866]"}}}}
   ```

## Root cause

Elasticsearch's default `index.mapping.total_fields.limit` is **1000**. Sinilind's Signal K
snapshot is the **full N2K vessel tree** — ~30 electrical switches (`electrical.switches.bank.0.<n>`),
per-source `values` maps (can0.16, can0.10, can0.18, can0.6, can0.35, can0.4, can0.8, can0.9,
can0.36...), `meta` blocks with descriptions on nearly every path, `gnss.satellitesInView`
arrays of objects. Each new doc adds ~866 **new** dynamic fields → every doc rejected with 400,
logged as a Logstash warning, never indexed.

Arthur's payload is small (simulator heading/depth/position) → stays under the limit → flows.

## Fix

```bash
# Live index (applies immediately):
curl -u elastic:$PW -X PUT http://127.0.0.1:9200/haris-signalk-2026.08.05/_settings \
  -d '{"index.mapping.total_fields.limit": 10000}'

# Index template (future indices inherit):
# add settings.index.mapping.total_fields.limit: 10000 to the haris-signalk template
```

- Committed to the provisioning role: `roles/elk_stack/tasks/main.yml` (both security-enabled
  and disabled branches), commit `0898fbf`.
- **Verified**: `VESSEL-SINILIND` docs reappeared in ES ~1 min after the live-index change;
  latest doc with fresh Tallinn GNSS position (59.459/24.721).

## Prevention / follow-up (offered, not adopted)

- Proper long-term fix: prune the aggregator payload before writing (strip `meta` blocks and
  per-source `values` maps). Changes the ES schema for BOTH vessels → deliberate change, not hotfix.
- Watchdog extension: sinilind ES-arrival check so a silent drop self-alerts.

## Key observation

`events.in = filtered = out` at Logstash is **not sufficient** proof that data reached ES —
output errors are logged but the pipeline counters still increment. The per-vessel ES query
(`q=vessel_id:VESSEL-<NODE>`) is the only definitive check. See `elk-arrival-verification.md`.

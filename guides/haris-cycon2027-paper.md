# CyCon 2027 — Project Haris Paper

**Draft file:** `~/user-notes/cycon-2027/haris-cycon2027-paper.md`  
**Status:** Full draft complete (~4,400 words)  
**Abstract submitted:** No (second paper, alongside ShipCrawler CyCon abstract)

## Submission Details

| Field | Value |
|-------|-------|
| Conference | CyCon 2027 (19th Intl Conf on Cyber Conflict) |
| Theme | Unified Response |
| Organizer | NATO CCDCOE |
| Track | Technology |
| Authors | Nasr, Zaitseva-Pärnaste, Kujala |
| Co-submission | ShipCrawler CyCon paper (same authors, first author same) |

## Paper Structure (8 sections, ~4,400 words)

| # | Section | Words | Content |
|---|---------|-------|---------|
| 1 | Introduction | ~700 | 112,500 vessels, no monitoring, 103% incident surge, academic gap (implementations nonexistent), Haris as solution, 3 contributions |
| 2 | Related Work & The Gap | ~600 | M-SOC SLR, commercial landscape limitations, the implementation gap |
| 3 | Architecture | ~1,200 | Edge (RPi 5 + PiCAN-M → Signal K → data_aggregator.py → JSONL → Filebeat) → Core (Logstash → ES → Kibana + Zabbix) → Supporting (tailscale-topography, vsat-honeypot) → Ansible deployment |
| 4 | Use Cases | ~1,000 | Fleet operator (single-pane), Port authority (OSINT+telemetry), Class society (continuous E26) |
| 5 | Limitations | ~400 | Sensor protocol coverage, connectivity dependency, edge compute limits, OSINT complementarity, crew interface |
| 6 | Toward Open M-SOCs | ~700 | Technical (data models, detection content), Community (reference guides, datasets), Regulatory (PSC, class, flag, insurance) |
| 7 | Conclusion | ~300 | Recap → key insight: unified response needs shared infrastructure, not shared secrets |
| **Total** | | **~4,400** | |

## Differentiation from Journal Paper (paper-v2.tex)

| Element | Journal Paper | CyCon Paper |
|---------|--------------|-------------|
| Core argument | "Here is a working M-SOC implementation" | "Open M-SOC infrastructure is a prerequisite for unified cyber defense" |
| Related work | M-SOC literature, maritime incidents | Info-sharing barriers, governance fragmentation |
| Use cases | Laboratory validation (technical) | 3 stakeholder use cases: fleet operator, port authority, class society |
| Policy | None | Regulatory integration (PSC, class, flag, insurance) |
| Audience | IEEE / maritime technical | NATO CCDCOE / cyber conflict community |

## References (10 total)

[1] UNCTAD Review of Maritime Transport 2025
[2] Kessler, GPS Spoofing and Maritime Industry (2020)
[3] Cydome Maritime OT Cyber Report 2026
[4] CYTUR Maritime Cyber Threat White Paper 2026
[5] Nasr et al., M-SOC SLR, TransNav 2025
[6] Nasr et al., Historical Attacks → M-SOC, SORTA 2024
[7] Nasr et al., OSINT Framework, IEEE Access 2026
[8] Signal K Server (signalk.org)
[9] Nasr et al., ShipCrawler CyCon 2027 (companion submission)
[10] IACS UR E26 Cyber Resilience of Ships

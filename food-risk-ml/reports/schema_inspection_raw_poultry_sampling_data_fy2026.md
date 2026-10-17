# Schema inspection: `raw_poultry_sampling_data_fy2026.zip`

Rows: 21102 | Columns: 30 | Exact duplicate rows: 0

Candidate columns are keyword hints. Confirm each mapping against the official FSIS metadata.

- **sample_id** hints: `form_id`, `sample_number`, `establishment_id`, `establishment_number`, `sample_source_name`
- **sample_date** hints: `collection_date`
- **establishment_id** hints: `establishment_id`, `establishment_number`, `establishment_name`, `establishment_state`
- **product_category** hints: `project_code`, `project_name`, `product_type`
- **salmonella_result** hints: `salmonella_sp_analysis`, `salmonella_sp_analysis_canceled`, `salmonellae_mpn_g`, `salmonellae_mpn_g_canceled`, `salmonellae_mpn_combination`, `salmonella_quantitative_cfu_g`, `salmonella_quantitative_cfu_ml`, `salmonella_mpn_qualitative`

| column | missing | unique | date parse | numeric | leakage denylist | top values |
|---|---|---|---|---|---|---|
| `form_id` | 0 | 21102 |  | 1.0 |  | 103678035 (1); 103675084 (1); 103675083 (1); 103680732 (1); 103679224 (1) |
| `sample_number` | 0 | 21102 |  | 1.0 |  | 300853446 (1); 300853797 (1); 300853413 (1); 300853452 (1); 300854117 (1) |
| `establishment_id` | 0 | 750 | {'ISO8601': 0.609, '%Y%m%d': 0.093} | 1.0 |  | 9259 (137); 41 (124); 589 (123); 2278 (119); 496 (116) |
| `establishment_number` | 0 | 750 |  | 0.0 |  | M27389+P27389+V27389 (137); P1250 (124); P1243 (123); P2178 (119); M18726+P18726 (116) |
| `establishment_name` | 0 | 623 |  | 0.0 |  | Pilgrim's Pride Corporation (1918); Tyson Foods, Inc. (1673); Sanderson Farms, Inc. (660); Wayne Farms LLC (537); Perdue Foods LLC (421) |
| `establishment_state` | 0 | 44 |  | 0.0 |  | GA (2171); AR (1775); CA (1763); TX (1697); AL (1616) |
| `project_code` | 0 | 9 |  | 0.0 |  | HC_CPT_LBW01 (10733); HC_CH_CARC01 (6349); HC_CH_COM01 (1259); HC_TU_COM01 (1000); F_CPT_LBW01 (805) |
| `project_name` | 0 | 9 |  | 0.0 |  | Sampling for Chicken Parts – Legs, Breasts, and  Wings (10733); HACCP Verification for Young Chicken Carcasses (6349); Sampling for Ground and Other Comminuted Chicken (not Mechanically Separated) (1259); Sampling for Ground and Other Comminuted Turkey (not Mechanically Separated) (1000); Follow-up sampling of Chicken Parts – legs, breasts, wings (805) |
| `collection_date` | 0 | 229 | {'ISO8601': 1.0} | 0.0 |  | 2025-11-12 (215); 2026-01-20 (204); 2025-12-29 (200); 2026-02-17 (200); 2025-11-24 (199) |
| `sample_source_name` | 0 | 5 |  | 0.0 |  | Product-Raw-Intact-Chicken (10387); Animal-Chicken-Broiler / Young Chicken Carcass Rinse (6560); Product-Raw-Ground, Comminuted or Otherwise Nonintact-Chicken (2544); Product-Raw-Ground, Comminuted or Otherwise Nonintact-Turkey (1079); Animal-Turkey-Turkey Carcass Sponge (532) |
| `product_type` | 0 | 4 |  | 0.0 |  | NULL (9566); Breast (5491); Leg (4006); Wing (2039) |
| `not_analyzed` | 0 | 3 |  | 1.0 | YES | 00 (21100); 20 (1); 14 (1) |
| `not_analyzed_explain` | 0 | 6 |  | 0.001 | YES | NULL (21097); 0 (1); 103693525 (1); 103771370 (1); 103776702 (1) |
| `salmonella_sp_analysis` | 0 | 3 |  | 0.0 | YES | Negative (19053); Positive (2041); NULL (8) |
| `salmonella_sp_analysis_canceled` | 0 | 3 |  | 0.0 | YES | NULL (21096); 25-21 Lab problem - Quality Control failure, unable to reanalyze (3); 26 Lab closed (3) |
| `salmonellae_mpn_g` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `salmonellae_mpn_g_canceled` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `salmonellae_mpn_combination` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `salmonella_quantitative_cfu_g` | 0 | 23 |  | 0.001 | YES | NULL (20639); <10 (434); 21 (4); 18 (2); 44 (2) |
| `salmonella_quantitative_cfu_ml` | 0 | 77 | {'ISO8601': 0.001} | 0.009 | YES | NULL (20251); <10 (710); 17 (7); 18 (5); 11 (5) |
| `salmonella_mpn_qualitative` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `campylobacter_analysis_1ml` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `campylobacter_analysis_1ml_canceled` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `campylobacter_analysis_30ml` | 0 | 3 |  | 0.0 | YES | NULL (9705); Negative (9222); Positive (2175) |
| `campylobacter_analysis_30ml_canceled` | 0 | 6 |  | 0.0 | YES | NULL (12792); 86 Sample not selected for Campylobacter analysis (8267); 25-21 Lab problem - Quality Control failure, unable to reanalyze (28); 46  Temperature too low (11); 13  Insufficient tissue or sample (3) |
| `aerobic_plate_count_mpn_ml` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `enterobacteriaceae_mpn_ml` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `aerobic_plate_count_mpn_100_sq_cm` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `enterobacteriaceae_mpn_100_sq_cm` | 0 | 1 |  | 0.0 | YES | NULL (21102) |
| `aerobic_plate_count_mpn_g` | 0 | 1 |  | 0.0 | YES | NULL (21102) |

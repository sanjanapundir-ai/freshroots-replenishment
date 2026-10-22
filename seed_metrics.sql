-- Metric owner register from the operating plan. Owner names are filled in by Deepa in week 1
-- (only Raghav's is known); the role is what alerts route to.
INSERT INTO metric_owners (metric_id, metric, owner_role, owner_name, trigger_text, action_text, deadline_hours, sort_order) VALUES
 ('dist_order_drop', 'Distributor order size (top 50)', 'Regional Sales Manager', '', 'Order more than 20% below the distributor''s 4-week average', 'Call the distributor, log the reason (scheme, stock, competitor)', 24, 1),
 ('sales_volume', 'Sales volume', 'Head of Sales', '', 'Week more than 10% below the same week last year', 'Explain the gap by region at the weekly review', 72, 2),
 ('fulfilment', 'Order fulfilment rate', 'Logistics Manager', '', 'Below 95% for the week', 'Name the SKUs and depots that missed, with a fix date', 48, 3),
 ('stockouts', 'Stockout incidents', 'Demand Planner', 'Raghav Kulkarni', 'Any A-class SKU out of stock or at stockout risk', 'Expedite order or substitute, log the cause', 24, 4),
 ('overstock', 'Overstock value', 'Procurement Head', '', 'Over 120% of the monthly target', 'Pause or reduce open POs for those SKUs', 72, 5),
 ('complaints', 'Distributor complaints', 'CS Team Lead', '', '3 or more from one distributor in a week', 'Call the distributor, agree a fix', 48, 6),
 ('cs_response', 'CS first response time', 'CS Team Lead', '', 'Median over 2 working hours for a day', 'Rebalance the inbox, report cause', 24, 7),
 ('po_gate', 'Raw material PO above 5 lakh', 'Procurement Head', '', 'Any such PO waiting for release', 'Check the last 48 hours of alerts, sign off before release', 24, 8),
 ('wape', 'Forecast error (WAPE)', 'Demand Planner', 'Raghav Kulkarni', 'Above 15% for the month', 'Review the worst 10 SKUs at the monthly check', 120, 9),
 ('writeoffs', 'Write-offs', 'Finance Controller', '', 'Any perishable write-off above 50,000', 'Root cause with Raghav and Procurement', 120, 10),
 ('credit', 'Distributor credit overdue', 'Finance Controller', '', 'Over 45 days for any top-50 distributor', 'Hold or agree a payment plan with Sales', 72, 11),
 ('scheme_uptake', 'Scheme uptake', 'Head of Sales', '', 'Under 60% of eligible distributors registered 3 days before the window closes', 'Reps call the unregistered distributors', 24, 12)
ON CONFLICT (metric_id) DO NOTHING;

CREATE FUNCTION IF NOT EXISTS main.demo.sales_rep_filter(rep_email STRING)
RETURNS BOOLEAN
RETURN rep_email = current_user();

ALTER TABLE main.demo.test_sales
SET ROW FILTER main.demo.sales_rep_filter ON (rep_email);

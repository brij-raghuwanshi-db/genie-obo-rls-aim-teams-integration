CREATE SCHEMA IF NOT EXISTS main.demo;

CREATE TABLE IF NOT EXISTS main.demo.test_sales (
  rep_email STRING,
  amount DECIMAL(10,2)
);

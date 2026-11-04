-- Schema-only representation of /Users/stepan/Downloads/Users.sql (PostgreSQL 18 custom dump).
-- No original data or passwords are included in this file.
CREATE TYPE public."Merchant_status" AS ENUM ('ACTIVE','PENDING','BLOCKED');
CREATE TYPE public."Payment_status" AS ENUM ('SUCCESS','DECLINED','PENDING','CANCELED');
CREATE TYPE public."Position_enum" AS ENUM ('visitor','worker','manager');
CREATE TABLE public.merchants (
 merchant_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL, status text NOT NULL, description text
);
CREATE TABLE public.employees (
 employee_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 merchant_id integer NOT NULL REFERENCES public.merchants(merchant_id),
 name text NOT NULL, payment_details text NOT NULL,
 position public."Position_enum", login text, password text
);
CREATE TABLE public.payments (
 payment_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 merchant_id integer NOT NULL REFERENCES public.merchants(merchant_id),
 employee_id integer NOT NULL REFERENCES public.employees(employee_id),
 amount numeric(10,2) NOT NULL, tip numeric(10,2) NOT NULL,
 status public."Payment_status" NOT NULL, timestamp text NOT NULL
);
CREATE TABLE public.qr_links (
 qr_id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 mecrhant_id integer NOT NULL REFERENCES public.merchants(merchant_id),
 employee_id integer NOT NULL REFERENCES public.employees(employee_id),
 receipt_id integer NOT NULL, nonce text NOT NULL, exp text NOT NULL, signature text NOT NULL
);

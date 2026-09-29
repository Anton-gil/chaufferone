-- LifePilot core schema
-- Obligation graph (DAG) + verification signals + Admin Day batching

create extension if not exists "pgcrypto";

create table if not exists obligations (
  id text primary key,
  user_id uuid not null,
  title text not null,
  vendor text,
  vendor_normalized text,
  category text,

  amount numeric,
  currency text default 'INR',
  amount_confidence numeric,

  due_date date,
  flexibility_window integer default 0,
  recurrence jsonb,

  penalty jsonb default '{}'::jsonb,
  risk_score integer default 0,
  urgency_tier text default 'green',

  verification_state text default 'extracted',
  signal_extracted jsonb,
  signal_pre_debit jsonb,
  signal_debit jsonb,
  signal_receipt jsonb,

  batchable boolean default false,
  batch_group text,
  trigger_event jsonb,

  auto_pay_enabled boolean default false,
  sources jsonb default '[]'::jsonb,
  confidence numeric default 0,
  anomaly_flag boolean default false,

  status text default 'upcoming',
  resolved_at timestamptz,

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists obligations_user_due_idx on obligations (user_id, due_date);
create index if not exists obligations_user_status_idx on obligations (user_id, status);

create table if not exists prerequisite_edges (
  id uuid primary key default gen_random_uuid(),
  obligation_id text references obligations(id) on delete cascade,
  prerequisite_id text references obligations(id) on delete cascade,
  lead_time_days integer not null,
  confidence numeric,
  legal_basis text,
  is_blocking boolean default true,
  unique (obligation_id, prerequisite_id)
);

create index if not exists prereq_edges_obligation_idx on prerequisite_edges (obligation_id);
create index if not exists prereq_edges_prereq_idx on prerequisite_edges (prerequisite_id);

create table if not exists dependency_templates (
  id uuid primary key default gen_random_uuid(),
  parent_category text not null,
  prereq_category text not null,
  lead_time_days integer not null,
  legal_basis text,
  confidence numeric default 1.0,
  country text default 'IN'
);

create table if not exists obligation_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  vendor_normalized text not null,
  category text,
  amount numeric,
  due_date date,
  resolved_date date,
  was_late boolean default false,
  verification_final_state text,
  created_at timestamptz default now()
);

create table if not exists vendor_patterns (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  vendor_normalized text not null,
  avg_amount numeric,
  std_dev_amount numeric,
  avg_day_of_month integer,
  recurrence_frequency text,
  recurrence_confidence numeric,
  miss_rate numeric default 0,
  trend text,
  seasonal_multipliers jsonb default '{}'::jsonb,
  next_predicted date,
  sample_count integer default 0,
  unique (user_id, vendor_normalized)
);

create table if not exists processed_signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  source_type text,
  source_ref text not null,
  obligation_id text references obligations(id) on delete set null,
  processed_at timestamptz default now(),
  unique (user_id, source_type, source_ref)
);

create table if not exists admin_day_config (
  user_id uuid primary key,
  anchor_day integer,
  salary_date integer,
  enabled boolean default true
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  title text not null,
  document_type text,
  file_path text,
  extracted_data jsonb default '{}'::jsonb,
  expiry_date date,
  linked_obligation_id text references obligations(id) on delete set null,
  created_at timestamptz default now()
);

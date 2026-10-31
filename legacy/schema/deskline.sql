-- Deskline helpdesk, the SaaS support desk Larkspur bought in 2021
-- Simulated here as a separate schema with its own API

create schema if not exists hd;

create table if not exists hd.tickets (
  id                bigserial primary key,
  external_ref      varchar(40),
  channel           varchar(10) not null,      -- email phone portal
  requester_email   varchar(80),
  requester_name    varchar(60),
  requester_company varchar(60),
  subject           varchar(160),
  status            varchar(12) not null default 'new',  -- new open pending solved closed
  priority          varchar(8) default 'normal',
  assignee          varchar(40),
  tags              text[] default '{}',
  created_at        timestamptz not null,
  updated_at        timestamptz not null,
  first_response_at timestamptz,
  solved_at         timestamptz,
  reopened_count    integer default 0
);
create index if not exists tickets_created on hd.tickets (created_at);
create index if not exists tickets_status on hd.tickets (status);

create table if not exists hd.messages (
  id          bigserial primary key,
  ticket_id   bigint not null,
  author_type varchar(10) not null,   -- customer agent system
  author_name varchar(60),
  body        text not null,
  created_at  timestamptz not null
);
create index if not exists messages_ticket on hd.messages (ticket_id, created_at);

create table if not exists hd.api_tokens (
  token      varchar(64) primary key,
  label      varchar(40),
  created_at timestamptz default now()
);

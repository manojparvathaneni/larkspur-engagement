-- FREIGHTCORE master schema
-- orig. conversion from FC400 files 2009-11 (rk)
-- 2012-04 added RWGLOG for reweigh project
-- 2014-06 PKUREQ for web pickups (soap svc)
-- 2016-02 EDIPRT moved here from translator box
-- DO NOT ADD FKs, batch reloads tables out of order

create schema if not exists fc;
create schema if not exists ops;
create schema if not exists tel;

-- terminal master
create table if not exists fc.trmmst (
  trmcd   char(3) primary key,
  trmnm   varchar(30),
  trmct   varchar(30),
  trmst   char(2),
  trmzp   char(5),
  trmtyp  char(1),          -- T terminal B breakbulk
  trmlat  numeric(8,5),
  trmlon  numeric(8,5),
  trmprl  integer,          -- pro range low (8 digit base)
  trmprh  integer,          -- pro range high
  trmact  char(1) default 'Y'
);

-- customer master
create table if not exists fc.cusmst (
  cusno   char(8) primary key,
  cusnm   varchar(40),
  cusad1  varchar(40),
  cusct   varchar(30),
  cusst   char(2),
  cuszp   char(5),
  custrm  char(3),          -- home terminal
  cusedi  char(1) default 'N',
  cuscon  varchar(40),      -- contact name
  cuseml  varchar(60),
  cusphn  varchar(14),
  cusrstr char(1) default 'N',
  cusdsc  numeric(4,2),     -- discount pct off tariff
  cuscrt  date,
  cusupd  timestamp
);

-- shipment master
create table if not exists fc.shpmst (
  shppro   char(9) primary key,
  shpbol   varchar(15),
  shppo    varchar(15),
  shpdt    date,             -- pickup date
  shporg   char(3),
  shpdst   char(3),
  shpshp   char(8),          -- shipper cusno
  shpcnm   varchar(40),      -- consignee name
  shpcad   varchar(40),
  shpcct   varchar(30),
  shpcst   char(2),
  shpczp   char(5),
  shpcon   char(8),          -- consignee cusno if customer, else blank
  shpbto   char(8),          -- bill to cusno
  shpfrt   char(2),          -- PP prepaid CC collect TP third party
  shppcs   integer,
  shpwgt   integer,
  shpcuf   numeric(7,1),     -- cubic feet
  shpcls   numeric(4,1),
  shphzm   char(1) default 'N',
  shpacc   varchar(20),      -- accessorial codes comma sep
  shpchg   numeric(9,2),
  shpstscd char(2),
  shpstsdt timestamp,
  shptrm   char(3),          -- current terminal
  shpeta   date,
  shpapt   timestamp,        -- delivery appt
  shpdlvdt timestamp,
  shppod   varchar(30),      -- signed by
  shpexc   char(1) default 'N',
  shpupd   timestamp,
  shpusr   char(10)
);
create index if not exists shpmst_bol on fc.shpmst (shpbol);
create index if not exists shpmst_shp on fc.shpmst (shpshp, shpdt);
create index if not exists shpmst_bto on fc.shpmst (shpbto);
create index if not exists shpmst_sts on fc.shpmst (shpstscd);

-- shipment events
create table if not exists fc.shpevt (
  evtid   bigserial primary key,
  evtpro  char(9),
  evtcd   char(2),
  evtrsn  char(2),
  evttrm  char(3),
  evtts   timestamp,
  evtusr  char(10)
);
create index if not exists shpevt_pro on fc.shpevt (evtpro, evtts);

-- status code xref to EDI 214 AT701/AT702
-- trm *** = all terminals, terminal row overrides
create table if not exists fc.stsxrf (
  xrftrm char(3),
  xrfcd  char(2),
  xrfedi char(2),
  xrfrsn char(2),
  xrfdsc varchar(30),
  primary key (xrftrm, xrfcd)
);

-- invoices
create table if not exists fc.invhdr (
  invno   char(10) primary key,
  invpro  char(9),
  invbto  char(8),
  invdt   date,
  invamt  numeric(9,2),
  invfsc  numeric(9,2),
  invsts  char(1),          -- O open P paid D disputed C credited
  invrbl  char(1) default 'N', -- rebill after reweigh
  invupd  timestamp
);
create index if not exists invhdr_pro on fc.invhdr (invpro);
create table if not exists fc.invdtl (
  invno   char(10),
  invln   integer,
  chgcd   char(4),
  chgamt  numeric(9,2),
  primary key (invno, invln)
);

-- reweigh / reclass log
create table if not exists fc.rwglog (
  rwgid   bigserial primary key,
  rwgpro  char(9),
  rwgtrm  char(3),
  rwgsrc  char(1),          -- S scale D dimensioner
  rwgow   integer,
  rwgnw   integer,
  rwgocf  numeric(7,1),
  rwgncf  numeric(7,1),
  rwgocl  numeric(4,1),
  rwgncl  numeric(4,1),
  rwgts   timestamp
);

-- over short damage
create table if not exists fc.osdrec (
  osdid   bigserial primary key,
  osdpro  char(9),
  osdtyp  char(1),          -- O S D
  osdtrm  char(3),
  osddt   date,
  osdpcs  integer,
  osdcon  char(1),          -- C concealed found after delivery
  osdnt   varchar(80)
);

-- claims
create table if not exists fc.clmmst (
  clmno   char(8) primary key,
  clmpro  char(9),
  clmcus  char(8),
  clmtyp  char(1),          -- D damage S shortage L loss
  clmfld  date,
  clmamt  numeric(9,2),
  clmsts  char(1),          -- N A I P D S
  clmack  date,
  clmrsd  date,
  clmpd   numeric(9,2),
  clmupd  timestamp
);

-- pickup requests (soap svc + phone)
create table if not exists fc.pkureq (
  pkuid   serial primary key,
  pkuconf char(10),
  pkucus  char(8),
  pkudt   date,
  pkurdy  time,
  pkucls  time,
  pkupcs  integer,
  pkuwgt  integer,
  pkusrc  char(1),          -- W web S soap P phone
  pkusts  char(1),          -- O open D dispatched C complete X cancelled
  pkupro  char(9),
  pkucrt  timestamp
);

-- edi trading partners
create table if not exists fc.ediprt (
  ediid   varchar(15) primary key,
  edicus  char(8),
  edi214  char(1),
  edi210  char(1),
  edimap  varchar(20),
  edilak  timestamp,        -- last 997 received
  ediupd  timestamp
);

-- rates, cwt by class and zone
create table if not exists fc.rtetbl (
  rtecls  numeric(4,1),
  rtezn   integer,
  rtecwt  numeric(7,2),
  rtemin  numeric(7,2),
  primary key (rtecls, rtezn)
);

-- contracts (summary only, docs on imaging)
create table if not exists fc.cntrct (
  cntno   char(8) primary key,
  cntcus  char(8),
  cnteff  date,
  cntexp  date,
  cntrstr char(1) default 'N',
  cntdoc  varchar(40)
);

-- trailer / truck assignment for linehaul and city
create table if not exists fc.eqpasn (
  eqpno   char(6),
  eqpts   timestamp,
  eqpfrm  char(3),
  eqpto   char(3),
  eqppros text
);

-- system control flags (batch, outages)
create table if not exists fc.sysctl (
  ctlkey  varchar(20) primary key,
  ctlval  varchar(80),
  ctlupd  timestamp
);

-- telematics staging (eld vendor feed, every 15 min)
create table if not exists tel.posn (
  posid   bigserial primary key,
  trkno   char(6),
  posts   timestamp,
  poslat  numeric(8,5),
  poslon  numeric(8,5),
  posspd  integer,
  posdrv  char(2)           -- ON DR OF SB
);
create index if not exists posn_trk on tel.posn (trkno, posts);

-- claim notes, ops screens only
create table if not exists ops.clmnote (
  nteid   bigserial primary key,
  nteclm  char(8),
  ntets   timestamp,
  nteusr  char(10),
  ntetxt  varchar(240)
);

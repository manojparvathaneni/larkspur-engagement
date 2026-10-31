#!/usr/bin/env bash
# Checks that Larkspur is alive: database, FREIGHTCORE's SOAP service, Deskline and the world clock.
set -uo pipefail
cd "$(dirname "$0")"
set -a; . ../.env; set +a
fail=0
ok()  { echo "ok    $1"; }
bad() { echo "FAIL  $1"; fail=1; }
q()   { docker compose exec -T db psql -U larkspur -d larkspur -tAc "$1" 2>/dev/null; }

n=$(q "select count(*) from fc.shpmst"); [ "${n:-0}" -gt 1000 ] && ok "database: $n shipments" || bad "database: no shipments"
t=$(q "select count(*) from hd.tickets"); [ "${t:-0}" -gt 1000 ] && ok "deskline data: $t tickets" || bad "deskline data: no tickets"

code=$(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8080/fcws/FreightCoreService?wsdl')
[ "$code" = 200 ] && ok "freightcore wsdl" || bad "freightcore wsdl http $code"
pro=$(q "select shppro from fc.shpmst where shpstscd='DL' limit 1")
resp=$(curl -s -m 20 -H 'Content-Type: text/xml' http://127.0.0.1:8080/fcws/FreightCoreService --data "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:fc=\"http://www.larkspurfreight.example/fcws/2014\"><soapenv:Header><fc:AuthHeader><fc:UserId>${FCWS_USER}</fc:UserId><fc:Password>${FCWS_PASSWORD}</fc:Password></fc:AuthHeader></soapenv:Header><soapenv:Body><fc:Trace><fc:ProNumber>${pro}</fc:ProNumber></fc:Trace></soapenv:Body></soapenv:Envelope>")
echo "$resp" | grep -q "<fc:StatusCode>DL</fc:StatusCode>" && ok "freightcore trace $pro" || bad "freightcore trace: ${resp:0:120}"

code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/api/v2/tickets)
[ "$code" = 401 ] && ok "deskline rejects missing token" || bad "deskline without token http $code"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${DESKLINE_TOKEN}" http://127.0.0.1:8090/api/v2/tickets?per_page=1)
[ "$code" = 200 ] && ok "deskline api" || bad "deskline api http $code"

sleep 5
clock=$(q "select v->>'clock' from sim.state where k='world'")
age=$(q "select extract(epoch from (now() at time zone 'America/New_York') - (v->>'clock')::timestamp)::int from sim.state where k='world'")
[ -n "$age" ] && [ "$age" -lt 600 ] && ok "world clock $clock" || bad "world clock stale: $clock; check 'docker compose logs world'"

[ $fail = 0 ] && echo "Larkspur is up." || { echo "Something's wrong; see above."; exit 1; }

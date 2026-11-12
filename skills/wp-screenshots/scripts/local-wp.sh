#!/bin/bash
# WP-CLI against a running Local (localwp.com) site on macOS.
#   bash scripts/local-wp.sh <Local site name> <wp args...>
# Use it as a brief's "wp" prefix: "wp": "bash /path/to/scripts/local-wp.sh mysite"
SITE="$1"; shift
SITES="$HOME/Library/Application Support/Local/sites.json"
[ -f "$SITES" ] || { echo "local-wp: no Local install found ($SITES)" >&2; exit 1; }
read -r ID SPATH < <(/usr/bin/python3 -c "import json,sys; d=json.load(open(sys.argv[1])); s=[(k,v['path']) for k,v in d.items() if v['name']==sys.argv[2]]; print(*s[0]) if s else sys.exit('local-wp: no Local site named '+sys.argv[2])" "$SITES" "$SITE") || exit 1
SOCK="$HOME/Library/Application Support/Local/run/$ID/mysql/mysqld.sock"
[ -S "$SOCK" ] || { echo "local-wp: site '$SITE' is not running. Start it in Local first." >&2; exit 1; }
ARCH=darwin; [ "$(uname -m)" = arm64 ] && ARCH=darwin-arm64
PHPBIN=$(ls -d "$HOME/Library/Application Support/Local/lightning-services/"php-*/bin/$ARCH/bin/php 2>/dev/null | sort -V | tail -1)
[ -x "$PHPBIN" ] || { echo "local-wp: no PHP binary found in Local's lightning-services" >&2; exit 1; }
cd "${SPATH/#\~/$HOME}/app/public" || exit 1
exec "$PHPBIN" -d memory_limit=1024M -d mysqli.default_socket="$SOCK" \
  /Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/wp-cli.phar "$@"

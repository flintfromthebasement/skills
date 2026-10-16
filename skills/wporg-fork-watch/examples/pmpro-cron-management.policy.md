This fork is **PMPro Cron Management** (`strangerstudios/pmpro-cron-management`), a fork of WP Crontrol maintained by the Paid Memberships Pro team. It exists because WP Crontrol 2.0.0, the first release after the Awesome Motive acquisition, added in-admin promotions and one-click installers for other Awesome Motive plugins. The fork keeps everything else.

### Keep (port from upstream)

- Bug fixes, security hardening, performance work, accessibility and translation fixes.
- Features that work entirely on the site: cron events, logs, insights, alerts sent through `wp_mail`, schedules, WP-CLI commands, the WordPress Abilities API integration.
- Chart.js and other assets that are bundled locally.
- Changelog entries for the kept changes.

### Drop (never port)

- Anything under `src/promos.php` or `images/promos/`, and any replacement for them: welcome panels, "from the same team" cards, plugin suggestion cards, install-and-activate buttons, referral or "referred plugins" tracking, and the CSS/JS that only serves them (`.crontrol-promo*`, `.crontrol-featured*`, `.crontrol-columns`, the `.crontrol-promo-dismiss` fetch handler).
- Notices or tips that recommend another plugin: Duplicator backup notices, WPCode tips, WP Mail SMTP cards or sentences, WPVibe cards. The Cron AI screen keeps the Abilities API table and a plain "Connect an AI assistant that supports the WordPress Abilities API" card.
- Any integration that calls or depends on an Awesome Motive service, account, API, or hosted endpoint: usage tracking, telemetry, remote notices or announcement feeds, license or account connections, "Pro" or upgrade upsells, review nags, newsletter forms.
- Remote assets of any kind (scripts, styles, images, fonts loaded from a third-party host).
- Rebranding: author, plugin URI, and support links that point at Awesome Motive, Duplicator, or wp-crontrol.com marketing pages. Documentation links to `wp-crontrol.com/docs/` and `/help/` may stay.

When upstream wires a dropped feature into shared code (a filter call, a menu entry, a `require_once`, an uninstall cleanup line, a CSS block), remove the wiring too. Prefer deleting over stubbing: do not leave empty functions or dead namespaces behind.

### Fork identity (preserve on every merge)

- The main plugin file is `pmpro-cron-management.php` (upstream is `wp-crontrol.php`; git tracks the rename). If upstream edits its main file, apply those edits to `pmpro-cron-management.php` and never let `wp-crontrol.php` reappear.
- The plugin header keeps `Plugin Name: PMPro Cron Management`, `Author: Paid Memberships Pro`, `Plugin URI`/`Update URI: https://github.com/strangerstudios/pmpro-cron-management`, and the fork description. The fork's name and slug never contain "Crontrol" (renamed from PMPro Crontrol on 2026-10-16 so it does not trade on the upstream brand); "fork of WP Crontrol" attribution in the description and readmes stays.
- `src/coexist.php` and the guard in `pmpro-cron-management.php` that keeps the plugin inactive while WP Crontrol is active stay as they are.
- `README.md`, `SECURITY.md`, and the `composer.json` name and support links keep pointing at this repo. The readme's "Who this plugin is for", "Switching from WP Crontrol", and "Installation" sections stay; update the switching steps only if upstream changes what its uninstall removes.
- Text domain is `pmpro-cron-management` (upstream uses `wp-crontrol`). Every merged upstream string must use the fork's domain. After the merge, re-run the rename over the tree instead of resolving it line by line:

  ```bash
  perl -0pi -e "s/(,\s*)'wp-crontrol'(\s*\))/\$1'pmpro-cron-management'\$2/g" $(git ls-files '*.php' | grep -v '^vendor/')
  sed -i "s/load_plugin_textdomain( 'wp-crontrol'/load_plugin_textdomain( 'pmpro-cron-management'/" src/bootstrap.php
  sed -i 's/tr\[data-slug="wp-crontrol"\]/tr[data-slug="pmpro-cron-management"]/' js/wp-crontrol.js
  ```

  Page slugs (`'page' => 'wp-crontrol'`), the `wp-crontrol` script and style handles, and the Abilities category stay as upstream has them; only i18n domain arguments, the textdomain loader, the plugin-row selector, and the `Text Domain` header use `pmpro-cron-management`. Then regenerate `languages-seed/pmpro-cron-management.pot` with `wp i18n make-pot . languages-seed/pmpro-cron-management.pot --slug=pmpro-cron-management --domain=pmpro-cron-management --exclude=vendor,languages-seed,README.md` and leave `languages-seed/po/` alone (translations are managed on translate.strangerstudios.com).
- The `Crontrol` namespace, option names, table names, and admin page slugs stay identical to upstream so a site can switch between the plugins.

### Version and changelog

- Set `Version:` in the plugin header, the `WP_CRONTROL_VERSION` constant, and `Stable tag:` in `readme.txt` to the upstream version being ported. The fork's version always equals the upstream version it is based on; fork-only releases between upstream releases use a fourth segment (2.0.0.1), and an upstream port resets to the plain upstream number.
- Add a `### <version> (PMPro Cron Management) ###` entry at the top of the readme changelog that lists what was ported and what was dropped in one or two sentences, and keep the upstream changelog entry below it so the history stays readable.

### Verification before you finish

- `php -l` on every changed PHP file.
- `grep -rn "'wp-crontrol' )" --include=*.php src pmpro-cron-management.php uninstall.php` returns nothing (no i18n call still uses the upstream domain).
- `grep -rn "Promos\\|crontrol-promo\\|crontrol-featured\\|awesomemotive\\|WPVibe\\|Duplicator\\|WPCode\\|Mail SMTP" --include=*.php --include=*.js --include=*.css .` returns only readme changelog history lines.
- `ls wp-crontrol.php src/promos.php images/promos` all fail (the files do not exist).

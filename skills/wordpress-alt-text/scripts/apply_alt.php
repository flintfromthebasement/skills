<?php
/**
 * wordpress-alt-text — Phase 1 write-back. Updates _wp_attachment_image_alt ONLY.
 * Does NOT touch post_content. Idempotent: skips any attachment that already has alt.
 *
 * Build the input first (array of {"id":N,"alt":"..."}) from the pipeline DB:
 *   python3 export_updates.py --db alt.db --out alt_updates.json
 * (After a successful LIVE run: python3 export_updates.py --db alt.db --mark-applied alt_updates.json)
 *
 * Run from WP root:  ALT_JSON=alt_updates.json wp eval-file apply_alt.php
 * Env: ALT_JSON (required) | DRY_RUN=1 | IDS=1,2 | LIMIT=n | DELAY_MIN_MS/DELAY_MAX_MS (jitter) | ALT_LOG
 */
error_reporting(E_ALL & ~E_DEPRECATED & ~E_NOTICE & ~E_WARNING);

$path = getenv('ALT_JSON');
if (!$path || !file_exists($path)) { fwrite(STDERR, "ALT_JSON missing: $path\n"); exit(1); }
$dry   = getenv('DRY_RUN') === '1';
$only  = getenv('IDS') ? array_map('intval', array_filter(array_map('trim', explode(',', getenv('IDS'))))) : null;
$limit = (int)(getenv('LIMIT') ?: 0);
$dmin  = (int)(getenv('DELAY_MIN_MS') ?: 0); $dmax = (int)(getenv('DELAY_MAX_MS') ?: 0);
$logf  = getenv('ALT_LOG') ?: (dirname($path) . '/apply_alt.log');

$data = json_decode(file_get_contents($path), true);
if (!is_array($data)) { fwrite(STDERR, "bad JSON: $path\n"); exit(1); }
$log = fopen($logf, 'a');
fwrite($log, "\n== " . date('c') . " mode=" . ($dry?'DRY':'LIVE') . " ids=" . (getenv('IDS')?:'all') . " ==\n");

$updated=$would=$skip_has=$skip_missing=$skip_notimg=$skip_empty=$fail=0; $n=0;
foreach ($data as $rec) {
  $id = (int)($rec['id'] ?? 0); $alt = trim((string)($rec['alt'] ?? ''));
  if ($only !== null && !in_array($id, $only, true)) continue;
  $p = get_post($id);
  if (!$p || $p->post_type !== 'attachment') { $skip_missing++; fwrite($log, "SKIP-missing $id\n"); continue; }
  if (strpos((string)$p->post_mime_type, 'image/') !== 0) { $skip_notimg++; fwrite($log, "SKIP-notimg $id\n"); continue; }
  if (trim((string)get_post_meta($id, '_wp_attachment_image_alt', true)) !== '') { $skip_has++; fwrite($log, "SKIP-has $id\n"); continue; }
  if ($alt === '') { $skip_empty++; fwrite($log, "SKIP-emptyalt $id\n"); continue; }
  if ($dry) { $would++; fwrite($log, "WOULD $id : $alt\n"); }
  else {
    update_post_meta($id, '_wp_attachment_image_alt', $alt);
    $ok = trim((string)get_post_meta($id, '_wp_attachment_image_alt', true)) === $alt;
    if ($ok) { $updated++; fwrite($log, "OK $id : $alt\n"); } else { $fail++; fwrite($log, "FAIL $id\n"); }
    if ($dmax > 0) usleep(mt_rand(min($dmin,$dmax), $dmax) * 1000);
  }
  $n++; if ($limit && $n >= $limit) break;
}
$s = sprintf("RESULT mode=%s processed=%d updated=%d would=%d skip_has=%d missing=%d notimg=%d emptyalt=%d fail=%d\n",
  $dry?'DRY':'LIVE', $n, $updated, $would, $skip_has, $skip_missing, $skip_notimg, $skip_empty, $fail);
fwrite($log, $s); fclose($log); echo $s;

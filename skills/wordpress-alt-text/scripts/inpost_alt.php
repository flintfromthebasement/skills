<?php
/**
 * wordpress-alt-text — Phase 2 (optional). Fill EMPTY alt in <img> tags inside post_content.
 *
 * SAFETY: per-<img>-tag callback only (never a blind site-wide regex); only fills empty/missing
 * alt; never overwrites a non-empty alt; only acts on <img> that are WP images (wp-image-N) or
 * uploaded files (wp-content/uploads src) — never external/example-code imgs. Writes content
 * VERBATIM via $wpdb->update (no wp_update_post kses/normalization). Saves each post's original
 * to ORIG_DIR. Idempotent.
 *
 * Resolution per empty-alt img: (1) wp-image-{ID} -> that attachment's _wp_attachment_image_alt;
 * (2) fallback: match src filename (size + -scaled stripped) to an attachment that has alt;
 * ambiguous filename collisions are skipped (never guessed).
 *
 * Run from WP root:  DRY_RUN=1 wp eval-file inpost_alt.php   (then IDS=<one>, then full)
 * Env: DRY_RUN=1 | IDS=postid,.. | LIMIT=n | DELAY_MIN_MS/DELAY_MAX_MS | POST_TYPES (default "post,page")
 *      | PHASE2_LOG | ORIG_DIR (default ./alt-post-originals)
 */
error_reporting(E_ALL & ~E_DEPRECATED & ~E_NOTICE & ~E_WARNING);
global $wpdb;

$dry   = getenv('DRY_RUN') === '1';
$only  = getenv('IDS') ? array_map('intval', array_filter(array_map('trim', explode(',', getenv('IDS'))))) : null;
$limit = (int)(getenv('LIMIT') ?: 0);
$dmin  = (int)(getenv('DELAY_MIN_MS') ?: 0); $dmax = (int)(getenv('DELAY_MAX_MS') ?: 0);
$types = array_filter(array_map('trim', explode(',', getenv('POST_TYPES') ?: 'post,page')));
$types_sql = "'" . implode("','", array_map('esc_sql', $types)) . "'";
$logf   = getenv('PHASE2_LOG') ?: (getcwd() . '/inpost_alt.log');
$origdir= getenv('ORIG_DIR')   ?: (getcwd() . '/alt-post-originals');
@mkdir($origdir, 0775, true);

function media_alt($id) {
  static $c = array();
  if (!array_key_exists($id, $c)) $c[$id] = trim((string)get_post_meta($id, '_wp_attachment_image_alt', true));
  return $c[$id];
}
function norm_base($s) {
  $s = preg_replace('/\?.*$/', '', (string)$s);
  $b = strtolower(basename($s));
  return preg_replace(array('/-\d+x\d+(\.\w+)$/', '/-scaled(\.\w+)$/'), '$1', $b);
}

// filename -> alt lookup (one bulk query)
$baseMap = array(); $dup = array();
foreach ($wpdb->get_results(
  "SELECT pm1.meta_value file, pm2.meta_value alt FROM {$wpdb->postmeta} pm1
     LEFT JOIN {$wpdb->postmeta} pm2 ON pm2.post_id=pm1.post_id AND pm2.meta_key='_wp_attachment_image_alt'
    WHERE pm1.meta_key='_wp_attached_file'", ARRAY_A) as $r) {
  $alt = trim((string)$r['alt']); if ($alt === '') continue;
  $b = norm_base($r['file']);
  if (isset($baseMap[$b])) { if ($baseMap[$b] !== $alt) $dup[$b] = true; } else $baseMap[$b] = $alt;
}
foreach (array_keys($dup) as $b) unset($baseMap[$b]);

$log = fopen($logf, 'a');
fwrite($log, "\n== " . date('c') . " mode=" . ($dry?'DRY':'LIVE') . " ids=" . (getenv('IDS')?:'all') . " fnmap=" . count($baseMap) . " ==\n");

$where = "post_status='publish' AND post_type IN ($types_sql) AND (post_content LIKE '%wp-image-%' OR post_content LIKE '%wp-content/uploads%')";
if ($only) $where .= " AND ID IN (" . implode(',', array_map('intval', $only)) . ")";
$posts = $wpdb->get_results("SELECT ID, post_type, post_content FROM {$wpdb->posts} WHERE $where", ARRAY_A);

$cnt = array('fill_id'=>0,'fill_file'=>0,'skip_hasalt'=>0,'skip_nomedia'=>0,'skip_ambig'=>0);
$posts_changed = 0; $n = 0;
foreach ($posts as $p) {
  $pid = (int)$p['ID']; $orig = $p['post_content']; $diffs = array();
  $new = preg_replace_callback('/<img\b[^>]*>/i', function ($m) use (&$diffs, &$cnt, $baseMap, $dup) {
    $tag = $m[0];
    $altToken = null;
    if (preg_match('/\salt\s*=\s*"\s*"/i', $tag, $am))      $altToken = $am[0];
    elseif (preg_match("/\salt\s*=\s*'\s*'/i", $tag, $am))  $altToken = $am[0];
    elseif (preg_match('/\salt\s*=\s*"[^"]*"/i', $tag))     { $cnt['skip_hasalt']++; return $tag; }
    elseif (preg_match("/\salt\s*=\s*'[^']*'/i", $tag))     { $cnt['skip_hasalt']++; return $tag; }
    $aid = preg_match('/wp-image-(\d+)/', $tag, $mm) ? (int)$mm[1] : 0;
    $src = '';
    if (preg_match('/\ssrc\s*=\s*"([^"]+)"/i', $tag, $sm)) $src = $sm[1];
    elseif (preg_match("/\ssrc\s*=\s*'([^']+)'/i", $tag, $sm)) $src = $sm[1];
    $isUpload = ($src !== '' && stripos($src, 'wp-content/uploads') !== false);
    if (!$aid && !$isUpload) return $tag;
    $alt = $aid ? media_alt($aid) : '';
    $method = 'id';
    if ($alt === '' && $src !== '') {
      $b = norm_base($src);
      if (isset($dup[$b])) { $cnt['skip_ambig']++; return $tag; }
      if (isset($baseMap[$b])) { $alt = $baseMap[$b]; $method = 'filename'; }
    }
    if ($alt === '') { $cnt['skip_nomedia']++; return $tag; }
    $esc = htmlspecialchars($alt, ENT_QUOTES, 'UTF-8');
    if ($altToken !== null) $newtag = str_replace($altToken, ' alt="' . $esc . '"', $tag);
    else { $newtag = preg_replace('/<img\b/i', '<img@@A@@', $tag, 1); $newtag = str_replace('@@A@@', ' alt="' . $esc . '"', $newtag); }
    $cnt[$method === 'id' ? 'fill_id' : 'fill_file']++;
    $diffs[] = array($aid, $method, $tag, $newtag);
    return $newtag;
  }, $orig);

  if ($new === $orig || empty($diffs)) continue;
  $posts_changed++;
  fwrite($log, "POST $pid ({$p['post_type']}) — " . count($diffs) . " img(s):\n");
  foreach ($diffs as $d) fwrite($log, "  att {$d[0]} via {$d[1]}\n    OLD: {$d[2]}\n    NEW: {$d[3]}\n");
  if (!$dry) {
    if (!file_exists("$origdir/post-$pid.orig.html")) file_put_contents("$origdir/post-$pid.orig.html", $orig);
    $res = $wpdb->update($wpdb->posts, array('post_content' => $new), array('ID' => $pid));
    if ($res === false) fwrite($log, "  DB-FAIL $pid: " . $wpdb->last_error . "\n");
    else { clean_post_cache($pid); fwrite($log, "  WROTE $pid (rows=$res)\n"); }
    if ($dmax > 0) usleep(mt_rand(min($dmin,$dmax), $dmax) * 1000);
  }
  $n++; if ($limit && $n >= $limit) break;
}
$s = sprintf("RESULT mode=%s posts_with_fillable=%d fill_by_id=%d fill_by_filename=%d skip_hasalt=%d skip_nomedia=%d skip_ambiguous=%d\n",
  $dry?'DRY':'LIVE', $posts_changed, $cnt['fill_id'], $cnt['fill_file'], $cnt['skip_hasalt'], $cnt['skip_nomedia'], $cnt['skip_ambig']);
fwrite($log, $s); fclose($log); echo $s;

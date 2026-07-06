<?php
/**
 * wordpress-alt-text — Stage 1 inventory. READ ONLY (no writes).
 * Run from the WP root:  wp eval-file inventory.php   (capture stdout = manifest JSON)
 *
 * Emits one JSON object: { summary, images: [...] } — every image attachment with its
 * current alt + a usage map (featured via _thumbnail_id, in-content via wp-image-N + filename),
 * tiered: P1_content (used in post content), P2_featured (featured only), P3_orphan (unused).
 *
 * Env:
 *   POST_TYPES   comma list of post types to scan for in-content usage (default "post,page").
 *                Add your site's content CPTs, e.g. "post,page,docs,webinar".
 */
error_reporting(E_ALL & ~E_DEPRECATED & ~E_NOTICE & ~E_WARNING);
global $wpdb;

$types  = array_filter(array_map('trim', explode(',', getenv('POST_TYPES') ?: 'post,page')));
$types_sql = "'" . implode("','", array_map(function ($t) use ($wpdb) { return esc_sql($t); }, $types)) . "'";

$upload  = wp_get_upload_dir();
$baseurl = $upload['baseurl'] ?? home_url('/wp-content/uploads');

// 1. all image attachments
$atts = $wpdb->get_results(
  "SELECT ID, post_title, post_excerpt, post_content, post_mime_type, post_parent, post_date
     FROM {$wpdb->posts}
    WHERE post_type='attachment' AND post_mime_type LIKE 'image/%'", ARRAY_A);

// 2. attached files + normalized-basename lookup (size + -scaled suffixes stripped)
$file_by_id = array(); $id_by_base = array();
foreach ($wpdb->get_results("SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key='_wp_attached_file'", ARRAY_A) as $r) {
  $file_by_id[(int)$r['post_id']] = $r['meta_value'];
  $b = strtolower(basename($r['meta_value']));
  $b = preg_replace(array('/-\d+x\d+(\.\w+)$/', '/-scaled(\.\w+)$/'), '$1', $b);
  $id_by_base[$b] = (int)$r['post_id'];
}

// 3. current alt + dimensions
$alt_by_id = array();
foreach ($wpdb->get_results("SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key='_wp_attachment_image_alt'", ARRAY_A) as $r)
  $alt_by_id[(int)$r['post_id']] = $r['meta_value'];
$dim_by_id = array();
foreach ($wpdb->get_results("SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key='_wp_attachment_metadata'", ARRAY_A) as $r) {
  $m = @maybe_unserialize($r['meta_value']);
  if (is_array($m) && isset($m['width'])) $dim_by_id[(int)$r['post_id']] = array((int)$m['width'], (int)$m['height']);
}

// 4. featured-image usage (published)
$featured = array();
foreach ($wpdb->get_results(
  "SELECT pm.meta_value att, pm.post_id used, p.post_type ptype, p.post_title ptitle, p.post_name pslug
     FROM {$wpdb->postmeta} pm JOIN {$wpdb->posts} p ON p.ID = pm.post_id
    WHERE pm.meta_key='_thumbnail_id' AND p.post_status='publish'", ARRAY_A) as $r)
  $featured[(int)$r['att']][] = array('id'=>(int)$r['used'],'type'=>$r['ptype'],'title'=>$r['ptitle'],'slug'=>$r['pslug']);

// 5. in-content usage: scan published content for wp-image-{ID} + block "id":N + upload-URL filenames
$content_use = array();
$posts = $wpdb->get_results(
  "SELECT ID, post_type, post_title, post_name, post_content
     FROM {$wpdb->posts}
    WHERE post_status='publish' AND post_type IN ($types_sql)
      AND (post_content LIKE '%wp-image-%' OR post_content LIKE '%wp-content/uploads%')", ARRAY_A);
foreach ($posts as $p) {
  $found = array();
  if (preg_match_all('/wp-image-(\d+)/', $p['post_content'], $m)) foreach ($m[1] as $id) $found[(int)$id] = true;
  if (preg_match_all('/"id"\s*:\s*(\d+)/', $p['post_content'], $m)) foreach ($m[1] as $id) if (isset($file_by_id[(int)$id])) $found[(int)$id] = true;
  if (preg_match_all('#wp-content/uploads/[^"\'\s)]+\.(?:jpe?g|png|gif|webp)#i', $p['post_content'], $m)) {
    foreach ($m[0] as $u) {
      $b = strtolower(basename($u));
      $b = preg_replace(array('/-\d+x\d+(\.\w+)$/', '/-scaled(\.\w+)$/'), '$1', $b);
      if (isset($id_by_base[$b])) $found[$id_by_base[$b]] = true;
    }
  }
  foreach (array_keys($found) as $aid)
    $content_use[$aid][] = array('id'=>(int)$p['ID'],'type'=>$p['post_type'],'title'=>$p['post_title'],'slug'=>$p['post_name']);
}

// 6. assemble + tier
$images = array();
$summary = array('total_images'=>0,'has_alt'=>0,'missing_alt'=>0,'P1_content'=>0,'P2_featured'=>0,'P3_orphan'=>0,'by_mime'=>array());
foreach ($atts as $a) {
  $id = (int)$a['ID'];
  $file = $file_by_id[$id] ?? '';
  $alt  = isset($alt_by_id[$id]) ? trim($alt_by_id[$id]) : '';
  $has  = ($alt !== '');
  $uc   = $content_use[$id] ?? array();
  $uf   = $featured[$id] ?? array();
  $tier = $has ? 'has_alt' : (count($uc) ? 'P1_content' : (count($uf) ? 'P2_featured' : 'P3_orphan'));

  $summary['total_images']++;
  $summary['by_mime'][$a['post_mime_type']] = ($summary['by_mime'][$a['post_mime_type']] ?? 0) + 1;
  if ($has) $summary['has_alt']++; else { $summary['missing_alt']++; $summary[$tier]++; }

  $images[] = array(
    'id'=>$id, 'file'=>$file, 'url'=>$file ? ($baseurl.'/'.$file) : '', 'mime'=>$a['post_mime_type'],
    'dim'=>$dim_by_id[$id] ?? null, 'title'=>$a['post_title'], 'caption'=>$a['post_excerpt'],
    'parent'=>(int)$a['post_parent'], 'date'=>$a['post_date'], 'cur_alt'=>$alt, 'has_alt'=>$has,
    'tier'=>$tier, 'used_content'=>$uc, 'used_featured'=>$uf,
  );
}
echo json_encode(array('summary'=>$summary, 'images'=>$images));

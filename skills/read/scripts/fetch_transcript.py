#!/usr/bin/env python3
"""Fetch a YouTube transcript and print it as JSON (text, segments, duration)."""
import sys
import json

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
except ImportError:
    print(json.dumps({'success': False, 'error': 'MISSING_DEPENDENCY'}))
    sys.exit(1)


def fetch_transcript(video_id):
    try:
        api = YouTubeTranscriptApi()
        try:
            transcript = api.fetch(video_id)
        except NoTranscriptFound:
            # No English track: take whatever language exists, manual captions first.
            available = sorted(api.list(video_id), key=lambda t: t.is_generated)
            if not available:
                raise
            transcript = available[0].fetch()
        segments = [
            {'text': e.text, 'start': e.start, 'duration': e.duration}
            for e in transcript
        ]
        last = segments[-1] if segments else None
        return {
            'success': True,
            'video_id': video_id,
            'text': ' '.join(s['text'] for s in segments),
            'segment_count': len(segments),
            'language': getattr(transcript, 'language_code', None),
            # End of the last caption: a close lower bound on the video length.
            'duration': round(last['start'] + last['duration']) if last else None,
        }
    except TranscriptsDisabled:
        return {'success': False, 'error': 'TRANSCRIPTS_DISABLED'}
    except NoTranscriptFound:
        return {'success': False, 'error': 'NO_TRANSCRIPT'}
    except VideoUnavailable:
        return {'success': False, 'error': 'VIDEO_UNAVAILABLE'}
    except Exception as e:
        return {'success': False, 'error': f'{type(e).__name__}: {e}'[:500]}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No video ID provided'}))
        sys.exit(1)
    result = fetch_transcript(sys.argv[1])
    print(json.dumps(result))
    sys.exit(0 if result['success'] else 1)

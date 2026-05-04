#!/usr/bin/env python3
"""Fetch YouTube transcript and return as JSON."""
import sys
import json
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

def fetch_transcript(video_id):
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)

        segments = []
        for entry in transcript:
            segments.append({
                'text': entry.text,
                'start': entry.start,
                'duration': entry.duration
            })

        full_text = ' '.join(s['text'] for s in segments)

        return {
            'success': True,
            'video_id': video_id,
            'text': full_text,
            'segments': segments,
            'segment_count': len(segments)
        }

    except TranscriptsDisabled:
        return {'success': False, 'error': 'TRANSCRIPTS_DISABLED'}
    except NoTranscriptFound:
        return {'success': False, 'error': 'NO_TRANSCRIPT'}
    except VideoUnavailable:
        return {'success': False, 'error': 'VIDEO_UNAVAILABLE'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No video ID provided'}))
        sys.exit(1)

    result = fetch_transcript(sys.argv[1])
    print(json.dumps(result))
    sys.exit(0 if result['success'] else 1)

"""Validation rapide des schémas Pydantic Agent #1."""
import json
import sys
sys.path.insert(0, '/home/ilyas/video-automation/docs')

from agent1_schemas import *

# Test 1: Transcript minimal
t = Transcript(
    video_filename='test.mp4',
    duration_seconds=60.0,
    words=[
        Word(text='Bonjour', start=0.0, end=0.5, confidence=0.95, source='fused'),
        Word(text='le', start=0.5, end=0.7, confidence=0.90, source='fused'),
        Word(text='monde', start=0.7, end=1.0, confidence=0.88, source='fused'),
    ],
    silences=[
        Silence(start=1.0, end=1.5, duration_seconds=0.5, source='vad', confidence=0.9),
    ],
    sentences=[
        Sentence(text='Bonjour le monde.', start=0.0, end=1.0, words=[]),
    ],
    speakers=[SpeakerInfo(speaker_id='SPEAKER_00', total_words=3, total_duration_seconds=1.0, segment_count=1)],
    total_words=3,
    total_silences=1,
    average_confidence=0.91,
    processing_time_seconds=12.34,
)

j = t.model_dump_json(indent=2)
print('=== Transcript JSON valide ===')
print(j[:600])
print('...')

# Test 2: ScribeResult
scribe = ScribeResult(
    segments=[
        ScribeSegment(
            text='Bonjour le monde.',
            start=0.0, end=1.0,
            words=[
                ScribeWord(text='Bonjour', start=0.0, end=0.5, confidence=0.98),
                ScribeWord(text='le', start=0.5, end=0.7, confidence=0.97),
                ScribeWord(text='monde', start=0.7, end=1.0, confidence=0.96),
            ],
            language='fr'
        )
    ],
    full_text='Bonjour le monde.',
    language='fr',
    language_confidence=0.99,
    processing_time_ms=5000,
    api_call_id='call_abc123',
)
print('\n=== ScribeResult valide ===')
print(f'  Mots: {len(scribe.segments[0].words)}')
print(f'  Cache hit: {scribe.cached}')

# Test 3: Contraintes
errors = 0
try:
    Word(text='test', start=0.0, end=1.0, confidence=5.0)
    print('ERREUR: confidence=5.0 aurait dû être rejeté!')
    errors += 1
except Exception as e:
    print(f'  ✓ Contrainte confidence [0,1] respectée')

try:
    Word(text='test', start=0.0, end=1.0, confidence=0.5, source='invalid')
    errors += 1
except Exception as e:
    print(f'  ✓ Contrainte Literal source respectée')

try:
    t2 = Transcript.model_validate_json(json.dumps({'extra_field': True}))
    print('ERREUR: extra_forbid aurait dû rejeter!')
    errors += 1
except Exception as e:
    print(f'  ✓ Contrainte extra=forbid respectée')

# Test 4: WhisperXResult
wx = WhisperXResult(
    segments=[],
    word_segments=[
        WhisperXWord(text='Bonjour', start=0.0, end=0.5, confidence=0.85),
    ],
    silences=[WhisperXSilence(start=1.0, end=1.5, duration_seconds=0.5)],
    language='fr',
    model_name='tiny',
    processing_time_seconds=18.2,
    speakers_detected=1,
)
print(f'\n=== WhisperXResult valide ===')
print(f'  Mots: {len(wx.word_segments)}, Silences: {len(wx.silences)}')

# Test 5: VADResult
vad = VADResult(
    segments=[VADSegment(start=0.0, end=1.0, is_speech=True, confidence=0.9)],
    sample_rate=16000,
    frame_duration_ms=30,
    processing_time_ms=830.0,
    silence_segments=[VADSegment(start=1.0, end=1.5, is_speech=False, confidence=0.85)],
    speech_segments=[VADSegment(start=0.0, end=1.0, is_speech=True, confidence=0.9)],
)
print(f'  VAD segments: {len(vad.segments)}, Silences: {len(vad.silence_segments)}')

print(f'\n{"✅" if errors == 0 else "❌"} Tous les schémas Pydantic sont valides ({errors} erreurs).')

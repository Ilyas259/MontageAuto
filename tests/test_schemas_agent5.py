#!/usr/bin/env python3
"""Validation rapide des schémas Pydantic de l'Agent #5."""
import sys
sys.path.insert(0, '/home/ilyas/video-automation')

from agents.agent5_quality.schemas import (
    QualityReport, FeedbackItem, CorrectionRequest, IterationResult,
    QualityConfig, FeedbackCategory, Severity, TargetAgent, StopReason,
)

# Test 1: FeedbackItem
fb = FeedbackItem(
    category=FeedbackCategory.BROLL,
    severity=Severity.HIGH,
    timestamp='00:02:15',
    description='Le B-roll arrive 2 secondes trop tard',
    suggestion='Décaler le B-roll de -2s',
    target_agent=TargetAgent.AGENT3_MONTAGE,
    auto_fixable=True,
)
print(f'✅ FeedbackItem: {fb.category.value} / {fb.severity.value}')

# Test 2: QualityReport
report = QualityReport(
    video_path='/output/final.mp4',
    video_duration_seconds=185.0,
    criteria_scores={
        FeedbackCategory.RYTHME: 0.65,
        FeedbackCategory.CLARTE: 0.80,
        FeedbackCategory.TRANSITION: 0.70,
        FeedbackCategory.BROLL: 0.55,
        FeedbackCategory.AUDIO_SYNC: 0.90,
        FeedbackCategory.COUPURE: 0.75,
        FeedbackCategory.COHERENCE: 0.85,
    },
    overall_score=0.72,
    issues=[fb],
    positives=['Bon rythme général'],
    analysis_mode='keyframes',
    frames_analyzed=12,
    gemini_model='gemini-2.5-pro',
    token_usage={'prompt_tokens': 4500, 'completion_tokens': 1200},
    passed=True,
)
print(f'✅ QualityReport: score={report.overall_score}, issues={len(report.issues)}')

# Test 3: JSON serialization
json_str = report.model_dump_json(indent=2)
print(f'✅ JSON: {len(json_str)} chars')

# Test 4: Config
config = QualityConfig()
print(f'✅ Config: min_score={config.min_score}, max_iterations={config.max_iterations}')

# Test 5: IterationResult
result = IterationResult(
    success=True,
    final_iteration=2,
    final_score=0.78,
    improvement=0.16,
    total_issues_found=4,
    total_issues_fixed=3,
    stopped_reason=StopReason.QUALITY_MET,
    duration_seconds=272.0,
)
print(f'✅ IterationResult: success={result.success}, improvement={result.improvement_percent()}%')

# Test 6: CorrectionRequest with gemini_override
corr = CorrectionRequest(
    report_id='rep_001',
    iteration=1,
    target_agent=TargetAgent.AGENT3_MONTAGE,
    priority='high',
    items=[fb],
    context={'video_path': '/output/final.mp4'},
    gemini_override=True,
)
print(f'✅ CorrectionRequest: override={corr.gemini_override}, priority={corr.priority}')

print()
print('🎯 Tous les tests Pydantic passent !')
